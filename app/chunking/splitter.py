import json
from pathlib import Path
from typing import Optional

from loguru import logger

import app.registry as registry
from app.models import Block, Chunk, ChunkMetadata, DocumentStatus, OCRPage, OCRResult

OCR_DIR    = Path("data/ocr")
CHUNKS_DIR = Path("data/chunks")

# ── Sizing constants ──────────────────────────────────────────────────────────
# Parent chunks (1500 chars) carry full semantic context — sent to the LLM.
# Child chunks (400 chars) are the units actually embedded and stored in
# ChromaDB.  Each child stores parent_text in its extra so retrieval can
# return rich context without sacrificing embedding precision.
MIN_CHUNK_SIZE      = 300    # aggregate consecutive small blocks up to this floor
PARENT_CHUNK_SIZE   = 1500   # max chars for a parent (context) chunk
PARENT_CHUNK_OVERLAP = 150
CHILD_CHUNK_SIZE    = 400    # max chars for a child (embedding) chunk
CHILD_CHUNK_OVERLAP = 50

# ── Header detection ──────────────────────────────────────────────────────────
_HEADER_RATIO_THRESHOLD = 1.2
_SENTENCE_END = frozenset(".!?")
_SEPARATORS   = ["\n\n", "\n", " "]


# ── Block classification ──────────────────────────────────────────────────────

def _is_header(block: Block) -> bool:
    if block.type == "header":
        return True
    return (
        block.type == "text"
        and block.ratio_to_body >= _HEADER_RATIO_THRESHOLD
        and block.line_count <= 2
    )


# ── Text splitting ────────────────────────────────────────────────────────────

def _find_split_point(text: str, limit: int) -> int:
    for sep in _SEPARATORS:
        pos = text.rfind(sep, 0, limit)
        if pos > 0:
            return pos + len(sep)
    for i in range(limit - 1, 0, -1):
        if text[i] in (" ", "\n"):
            return i + 1
    return limit


def _split_text(text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    """Sliding-window split that respects word and sentence boundaries."""
    text = text.strip()
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]

    min_step = max(1, chunk_size - chunk_overlap)
    chunks: list[str] = []
    start = 0

    while start < len(text):
        remaining = text[start:]
        if len(remaining) <= chunk_size:
            chunks.append(remaining)
            break

        cut = _find_split_point(remaining, chunk_size)
        chunks.append(remaining[:cut].rstrip())

        if len(remaining) - cut > chunk_size:
            raw = max(0, cut - chunk_overlap)
            overlap_start: Optional[int] = None

            for i in range(raw, cut):
                if remaining[i] in _SENTENCE_END:
                    j = i + 1
                    while j < cut and remaining[j] in (" ", "\n"):
                        j += 1
                    if j < cut:
                        overlap_start = j
                        break

            if overlap_start is None:
                pos = raw
                while pos < cut and remaining[pos] not in (" ", "\n"):
                    pos += 1
                while pos < cut and remaining[pos] in (" ", "\n"):
                    pos += 1
                overlap_start = pos if pos < cut else raw

            advance = overlap_start if 0 < overlap_start < cut else cut
        else:
            advance = cut

        start += max(advance, min_step)

    return chunks


# ── Chunk construction ────────────────────────────────────────────────────────

def _doc_prefix(document_id: str) -> str:
    """First 12 hex chars of UUID (dashes stripped) for compact, unique chunk IDs."""
    return document_id.replace("-", "")[:12]


def _make_chunk(
    document_id: str,
    page_num: int,
    block_id: int,
    chunk_idx: int,
    text: str,
    block_type: str,
    is_header: bool,
    extra: Optional[dict] = None,
) -> Chunk:
    return Chunk(
        chunk_id=f"{_doc_prefix(document_id)}_{page_num}_{block_id}_{chunk_idx}",
        document_id=document_id,
        page=page_num,
        text=text,
        metadata=ChunkMetadata(
            page_num=page_num,
            block_id=block_id,
            is_header=is_header,
            block_type=block_type,
            extra=extra or {},
        ),
    )


def _chunk_to_disk(c: Chunk) -> dict:
    """Serialize a chunk for disk, omitting document_id (stored once at root)."""
    d = c.model_dump(mode="json")
    d.pop("document_id", None)
    return d


def _child_chunks_from_parent(parent: Chunk) -> list[Chunk]:
    """Split a parent chunk into smaller child chunks for embedding.

    Each child embeds a focused ~400-char window while carrying the full
    parent text in extra["parent_text"].  At retrieval time the caller
    returns parent_text to the LLM so it always gets rich context.

    Tables are never sub-split — a table child equals its parent verbatim.
    """
    parent_extra = {
        **parent.metadata.extra,
        "parent_text": parent.text,
        "parent_chunk_id": parent.chunk_id,
    }

    if parent.metadata.block_type == "table":
        return [Chunk(
            chunk_id=f"{parent.chunk_id}_0",
            document_id=parent.document_id,
            page=parent.page,
            text=parent.text,
            metadata=ChunkMetadata(
                page_num=parent.metadata.page_num,
                block_id=parent.metadata.block_id,
                is_header=parent.metadata.is_header,
                block_type=parent.metadata.block_type,
                extra=parent_extra,
            ),
        )]

    child_texts = _split_text(parent.text, CHILD_CHUNK_SIZE, CHILD_CHUNK_OVERLAP)
    return [
        Chunk(
            chunk_id=f"{parent.chunk_id}_{i}",
            document_id=parent.document_id,
            page=parent.page,
            text=text,
            metadata=ChunkMetadata(
                page_num=parent.metadata.page_num,
                block_id=parent.metadata.block_id,
                is_header=parent.metadata.is_header,
                block_type=parent.metadata.block_type,
                extra=parent_extra,
            ),
        )
        for i, text in enumerate(child_texts)
    ]


# ── Step A: block aggregation ─────────────────────────────────────────────────

def _aggregate_blocks(blocks: list[Block]) -> list[Block]:
    """Combine consecutive small text blocks into MIN_CHUNK_SIZE-or-larger units."""
    result: list[Block] = []

    buf: list[str]          = []
    buf_chars: int          = 0
    buf_lines: int          = 0
    anchor: Optional[Block] = None
    tail:   Optional[Block] = None

    def flush_buffer() -> None:
        nonlocal buf, buf_chars, buf_lines, anchor, tail
        if not buf:
            return
        result.append(Block(
            text="\n".join(buf),
            type="text",
            y_top=anchor.y_top,
            y_bottom=tail.y_bottom,
            font_size=anchor.font_size,
            ratio_to_body=anchor.ratio_to_body,
            line_count=buf_lines,
        ))
        buf       = []
        buf_chars = 0
        buf_lines = 0
        anchor    = None
        tail      = None

    for block in blocks:
        if _is_header(block) or block.type == "table":
            flush_buffer()
            result.append(block)
            continue

        buf.append(block.text)
        buf_chars += len(block.text)
        buf_lines += block.line_count
        if anchor is None:
            anchor = block
        tail = block

        if buf_chars >= MIN_CHUNK_SIZE:
            flush_buffer()

    flush_buffer()
    return result


# ── Cross-page sentence repair ────────────────────────────────────────────────

def _merge_hanging_text(pages: list[OCRPage]) -> list[OCRPage]:
    """Prepend an incomplete sentence tail from page N to the first body block on page N+1."""
    if len(pages) <= 1:
        return pages

    page_blocks: list[list[Block]] = [list(p.blocks) for p in pages]

    for i in range(len(pages) - 1):
        last_idx: Optional[int] = None
        for j in range(len(page_blocks[i]) - 1, -1, -1):
            b = page_blocks[i][j]
            if b.type == "text" and not _is_header(b):
                last_idx = j
                break
        if last_idx is None:
            continue

        tail_text = page_blocks[i][last_idx].text.rstrip()
        if tail_text and tail_text[-1] in _SENTENCE_END:
            continue

        first_idx: Optional[int] = None
        for j, b in enumerate(page_blocks[i + 1]):
            if b.type == "text" and not _is_header(b):
                first_idx = j
                break
        if first_idx is None:
            continue

        donor = page_blocks[i + 1][first_idx]
        src   = page_blocks[i][last_idx]
        page_blocks[i][last_idx] = Block(
            text=tail_text + " " + donor.text.lstrip(),
            type=src.type,
            y_top=src.y_top,
            y_bottom=src.y_bottom,
            font_size=src.font_size,
            ratio_to_body=src.ratio_to_body,
            line_count=src.line_count + donor.line_count,
        )
        page_blocks[i + 1].pop(first_idx)
        logger.debug(
            "Cross-page merge: page {} last block ← page {} first block",
            pages[i].page_num, pages[i + 1].page_num,
        )

    return [
        OCRPage(page_num=p.page_num, stats=p.stats, blocks=page_blocks[idx])
        for idx, p in enumerate(pages)
    ]


# ── Main entry point ──────────────────────────────────────────────────────────

def split(
    document_id: str,
    workspace_id: str = "__legacy__",
    chunk_size: int = PARENT_CHUNK_SIZE,
    chunk_overlap: int = PARENT_CHUNK_OVERLAP,
) -> list[Chunk]:
    """Load OCR JSON, produce parent-child chunks, persist, and update registry.

    Pipeline per page:
      A. Aggregate  — merge consecutive small text blocks into MIN_CHUNK_SIZE+
                       units.  Headers and tables are hard flush boundaries.
      B. Annotate   — prepend the in-scope section header to body blocks.
      C. Split      — apply sliding window (chunk_size / chunk_overlap) to get
                       parent chunks (~1500 chars).
      D. Sub-split  — divide each parent into child chunks (CHILD_CHUNK_SIZE)
                       for embedding.  Every child stores parent_text in
                       metadata.extra so the LLM receives full context.

    Cross-page sentence repair runs before the per-page loop.
    The file saved to disk wraps child chunks under a root object that carries
    ``workspace_id`` once, avoiding per-chunk duplication.
    """
    ocr_path = OCR_DIR / f"{document_id}.json"
    if not ocr_path.exists():
        raise FileNotFoundError(f"OCR JSON not found for document_id={document_id}: {ocr_path}")

    ocr_result = OCRResult.model_validate_json(ocr_path.read_text(encoding="utf-8"))
    logger.info(
        "Chunking start: document_id={} workspace={} pages={}",
        document_id, workspace_id, len(ocr_result.pages),
    )

    pages = _merge_hanging_text(ocr_result.pages)

    all_children: list[Chunk]                = []
    pending_headers: list[tuple[int, str]]   = []

    for page in pages:
        page_child_start = len(all_children)

        aggregated = _aggregate_blocks(page.blocks)

        for block_id, block in enumerate(aggregated):
            if _is_header(block):
                pending_headers.append((block_id, block.text))
                continue

            header_prefix    = "\n".join(t for _, t in pending_headers)
            header_block_ids = [bid for bid, _ in pending_headers]
            extra            = {"header_block_ids": header_block_ids} if header_block_ids else {}
            pending_headers  = []

            content = f"{header_prefix}\n{block.text}".strip() if header_prefix else block.text

            if block.type == "table":
                parent = _make_chunk(
                    document_id, page.page_num, block_id, 0,
                    content, "table", False, extra,
                )
                all_children.extend(_child_chunks_from_parent(parent))
            else:
                for idx, sub in enumerate(_split_text(content, chunk_size, chunk_overlap)):
                    parent = _make_chunk(
                        document_id, page.page_num, block_id, idx,
                        sub, "text", False,
                        extra if idx == 0 else {},
                    )
                    all_children.extend(_child_chunks_from_parent(parent))

        logger.debug(
            "Page {}: {} child chunks ({} aggregated blocks from {} raw blocks)",
            page.page_num,
            len(all_children) - page_child_start,
            len(aggregated),
            len(page.blocks),
        )

    # Flush headers that trailed the last content block in the document
    if pending_headers:
        last_page = pages[-1].page_num if pages else 0
        for bid, header_text in pending_headers:
            parent = _make_chunk(document_id, last_page, bid, 0, header_text, "text", True)
            all_children.extend(_child_chunks_from_parent(parent))
        logger.debug("Flushed {} trailing header(s) at document end", len(pending_headers))

    CHUNKS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = CHUNKS_DIR / f"{document_id}_chunks.json"
    out_path.write_text(
        json.dumps(
            {
                "document_id": document_id,
                "workspace_id": workspace_id,
                "chunks": [_chunk_to_disk(c) for c in all_children],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    logger.debug("Chunks saved: {}", out_path)

    registry.update_status(document_id, DocumentStatus.chunked)
    logger.info(
        "Chunking complete: document_id={} total_child_chunks={}",
        document_id, len(all_children),
    )
    return all_children
