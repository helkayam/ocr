import json
from pathlib import Path
from typing import Optional

from loguru import logger

import app.registry as registry
from app.models import Block, Chunk, ChunkMetadata, DocumentStatus, OCRPage, OCRResult

OCR_DIR    = Path("data/ocr")
CHUNKS_DIR = Path("data/chunks")

# ── Sizing constants (agreed in the architectural review) ─────────────────────
# Small consecutive text blocks are aggregated until the combined character
# count reaches MIN_CHUNK_SIZE.  Hebrew is dense — 300 chars gives the LLM
# enough context without risking context-free micro-chunks.
MIN_CHUNK_SIZE = 300

# Blocks (or aggregated groups) that exceed MAX_CHUNK_SIZE are split with a
# sliding window.  1500 chars ≈ 400–500 Hebrew tokens, well within LLM limits
# while keeping each chunk semantically self-contained.
MAX_CHUNK_SIZE = 1500

# Overlap carried into each split chunk.  10% of MAX_CHUNK_SIZE ensures
# sentences that straddle a boundary appear in both adjacent chunks.
CHUNK_OVERLAP = 150

# ── Header detection ──────────────────────────────────────────────────────────
# Primary signal: OCR now emits type="header" directly (service.py).
# Fallback: font-ratio heuristic for OCR files produced before this change.
_HEADER_RATIO_THRESHOLD = 1.2

_SENTENCE_END = frozenset(".!?")
_SEPARATORS   = ["\n\n", "\n", " "]


# ── Block classification ──────────────────────────────────────────────────────

def _is_header(block: Block) -> bool:
    """True if this block is a section header.

    Checks the OCR-assigned type first (fast path for files produced by the
    updated service.py).  Falls back to the font-ratio heuristic so that older
    OCR JSON files continue to work correctly.
    """
    if block.type == "header":
        return True
    return (
        block.type == "text"
        and block.ratio_to_body >= _HEADER_RATIO_THRESHOLD
        and block.line_count <= 2
    )


# ── Text splitting ────────────────────────────────────────────────────────────

def _find_split_point(text: str, limit: int) -> int:
    """Return the rightmost natural split index at or before *limit* (never mid-word).

    Tries paragraph, line, and word separators in priority order, searching
    backwards from *limit*.  Falls back to scanning backwards for any whitespace;
    hard-cuts only when the text contains absolutely no whitespace.
    """
    for sep in _SEPARATORS:
        pos = text.rfind(sep, 0, limit)
        if pos > 0:
            return pos + len(sep)
    for i in range(limit - 1, 0, -1):
        if text[i] in (" ", "\n"):
            return i + 1
    return limit


def _split_text(text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    """Sliding-window split that respects word and sentence boundaries.

    Split priority: paragraph → line → space — never mid-word.
    Overlap: seeks the last sentence-ending punctuation inside the overlap window
    so carried-over context always begins at a complete sentence boundary.
    """
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
        chunk_id=f"{document_id}_{page_num}_{block_id}_{chunk_idx}",
        document_id=document_id,
        page=page_num,
        text=text,
        metadata=ChunkMetadata(
            document_id=document_id,
            page_num=page_num,
            block_id=block_id,
            is_header=is_header,
            block_type=block_type,
            extra=extra or {},
        ),
    )


# ── Step A: block aggregation ─────────────────────────────────────────────────

def _aggregate_blocks(blocks: list[Block]) -> list[Block]:
    """Combine consecutive small text blocks into MIN_CHUNK_SIZE-or-larger units.

    Walks the block list and accumulates adjacent "text" blocks into a running
    buffer.  The buffer is flushed into a single merged Block when:
      - Its combined character count reaches MIN_CHUNK_SIZE, or
      - A header or table block is encountered (these are hard boundaries).

    Any buffer content still pending at the end of the list is flushed as-is,
    so no text is ever lost even if it never reaches MIN_CHUNK_SIZE.

    Blocks that are individually >= MIN_CHUNK_SIZE pass through the accumulator
    and are flushed immediately; they may be split in Step B if they exceed
    MAX_CHUNK_SIZE.
    """
    result: list[Block] = []

    buf: list[str]       = []
    buf_chars: int       = 0
    buf_lines: int       = 0
    anchor: Optional[Block] = None   # first block → provides y_top / font metadata
    tail:   Optional[Block] = None   # last  block → provides y_bottom

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

        # Accumulate this text block
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
    """Prepend an incomplete sentence tail from page N to the first body block on page N+1.

    If the last non-header text block on page N does not end with sentence-
    terminating punctuation, its text is merged into the first non-table text
    block on page N+1.  The merged block stays on page N; the donor block is
    removed from page N+1.
    """
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
    chunk_size: int = MAX_CHUNK_SIZE,
    chunk_overlap: int = CHUNK_OVERLAP,
) -> list[Chunk]:
    """Load OCR JSON, produce metadata-aware chunks, persist, and update the registry.

    Three-step pipeline per page:

      A. Aggregate  — combine consecutive small text blocks into MIN_CHUNK_SIZE+
                       units so the LLM always receives meaningful context.
                       Headers and tables act as hard flush boundaries.

      B. Split      — apply a sliding window to any block that exceeds chunk_size,
                       respecting sentence and word boundaries.

      C. Annotate   — prepend the in-scope section header to each non-header chunk
                       so every chunk is self-contained for retrieval.

    Cross-page sentence repair runs before the per-page loop.
    Headers are carried forward across page boundaries until consumed by a body block.
    """
    ocr_path = OCR_DIR / f"{document_id}.json"
    if not ocr_path.exists():
        raise FileNotFoundError(f"OCR JSON not found for document_id={document_id}: {ocr_path}")

    ocr_result = OCRResult.model_validate_json(ocr_path.read_text(encoding="utf-8"))
    logger.info("Chunking start: document_id={} pages={}", document_id, len(ocr_result.pages))

    # Cross-page sentence repair
    pages = _merge_hanging_text(ocr_result.pages)

    all_chunks: list[Chunk]            = []
    pending_headers: list[tuple[int, str]] = []   # carried across page boundaries

    for page in pages:
        page_start = len(all_chunks)

        # Step A: aggregate small consecutive text blocks
        aggregated = _aggregate_blocks(page.blocks)

        for block_id, block in enumerate(aggregated):
            if _is_header(block):
                # Accumulate — will be prepended to the next body block
                pending_headers.append((block_id, block.text))
                continue

            # Step C: build the header annotation for this block
            header_prefix    = "\n".join(t for _, t in pending_headers)
            header_block_ids = [bid for bid, _ in pending_headers]
            extra            = {"header_block_ids": header_block_ids} if header_block_ids else {}
            pending_headers  = []

            content = f"{header_prefix}\n{block.text}".strip() if header_prefix else block.text

            if block.type == "table":
                # Tables are atomic — never split regardless of size
                all_chunks.append(
                    _make_chunk(document_id, page.page_num, block_id, 0,
                                content, "table", False, extra)
                )
            else:
                # Step B: split if over chunk_size
                for idx, sub in enumerate(_split_text(content, chunk_size, chunk_overlap)):
                    all_chunks.append(
                        _make_chunk(
                            document_id, page.page_num, block_id, idx,
                            sub, "text", False,
                            extra if idx == 0 else {},
                        )
                    )

        logger.debug(
            "Page {}: {} chunks ({} aggregated blocks from {} raw blocks)",
            page.page_num,
            len(all_chunks) - page_start,
            len(aggregated),
            len(page.blocks),
        )

    # Flush headers that trailed the last content block in the document
    if pending_headers:
        last_page = pages[-1].page_num if pages else 0
        for bid, header_text in pending_headers:
            all_chunks.append(
                _make_chunk(document_id, last_page, bid, 0, header_text, "text", True)
            )
        logger.debug("Flushed {} trailing header(s) at document end", len(pending_headers))

    CHUNKS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = CHUNKS_DIR / f"{document_id}_chunks.json"
    out_path.write_text(
        json.dumps(
            [c.model_dump(mode="json") for c in all_chunks],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    logger.debug("Chunks saved: {}", out_path)

    registry.update_status(document_id, DocumentStatus.chunked)
    logger.info(
        "Chunking complete: document_id={} total_chunks={}",
        document_id, len(all_chunks),
    )
    return all_chunks
