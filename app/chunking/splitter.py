from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional, Tuple

from loguru import logger

import app.registry as registry
from app.models import Block, Chunk, ChunkMetadata, DocumentStatus, OCRPage, OCRResult

OCR_DIR = Path("data/ocr")
CHUNKS_DIR = Path("data/chunks")

# Blocks whose font is this multiple above the page median are treated as headers.
_HEADER_RATIO_THRESHOLD = 1.2
# Short lines under this length without terminal punctuation are header candidates.
_HEADER_MAX_LEN = 60
# Sentence-ending punctuation used for overlap snapping.
_SENTENCE_END = frozenset(".!?")
# Split separators tried in priority order (never split mid-word).
_SEPARATORS = ["\n\n", "\n", " "]


def _is_header(block: Block) -> bool:
    """Font-ratio heuristic: a text block whose font is ≥1.2× the body median."""
    return block.type == "text" and block.ratio_to_body >= _HEADER_RATIO_THRESHOLD


def _looks_like_header(block: Block, next_block: Optional[Block]) -> bool:
    """Look-ahead heuristic: short line without terminal punctuation before a longer body.

    Applied as a secondary check inside _chunk_page when the font-ratio heuristic
    misses headers (common when the OCR reports uniform ratio_to_body values).
    Only fires when the immediately following block is text and at least 3× longer,
    which distinguishes a genuine heading from a short sentence mid-paragraph.
    """
    if block.type != "text":
        return False
    text = block.text.strip()
    if not text or len(text) > _HEADER_MAX_LEN or text[-1] in _SENTENCE_END:
        return False
    if next_block is None or next_block.type != "text":
        return False
    return len(next_block.text) > len(text) * 3


def _find_split_point(text: str, limit: int) -> int:
    """Return the rightmost natural split index at or before *limit* (never mid-word).

    Tries paragraph, line, and word separators in priority order, searching
    *backwards* from *limit* so the left slice never exceeds the budget.
    Falls back to scanning backwards for any whitespace; only hard-cuts when
    the text contains absolutely no whitespace (e.g. a continuous run of chars).
    """
    for sep in _SEPARATORS:
        pos = text.rfind(sep, 0, limit)
        if pos > 0:
            return pos + len(sep)
    # Fallback: scan backward for any whitespace — avoids mid-word cuts
    for i in range(limit - 1, 0, -1):
        if text[i] in (" ", "\n"):
            return i + 1
    return limit  # only when the slice has zero whitespace (e.g. solid Hebrew run)


def _split_text(text: str, chunk_size: int, chunk_overlap: int) -> List[str]:
    """Sliding-window split that respects word and sentence boundaries.

    Split priority: paragraph (\\n\\n) → line (\\n) → space — never mid-word.
    Overlap: seeks the last sentence-ending punctuation inside the overlap window
    so the carried-over context always begins at a complete sentence boundary.
    Falls back to a word boundary, then the raw character offset.
    """
    text = text.strip()
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]

    chunks: List[str] = []
    start = 0

    while start < len(text):
        remaining = text[start:]
        if len(remaining) <= chunk_size:
            chunks.append(remaining)
            break

        cut = _find_split_point(remaining, chunk_size)
        chunks.append(remaining[:cut].rstrip())

        # Semantic overlap: prefer starting at a sentence boundary.
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
            # Snap to word boundary
            pos = raw
            while pos < cut and remaining[pos] not in (" ", "\n"):
                pos += 1
            while pos < cut and remaining[pos] in (" ", "\n"):
                pos += 1
            overlap_start = pos if pos < cut else raw

        start += overlap_start if 0 < overlap_start < cut else cut

    return chunks


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


def _chunk_page(
    document_id: str,
    page_num: int,
    blocks: List[Block],
    chunk_size: int,
    chunk_overlap: int,
    pending_headers: Optional[List[Tuple[int, str]]] = None,
) -> List[Chunk]:
    """Produce chunks for a single OCR page.

    *pending_headers* injects cross-page header context (a header at the bottom
    of page N carried into the first content block of page N+1).  Any headers
    still unconsumed at the end of the page are emitted as standalone
    ``is_header=True`` chunks so the caller always receives a complete list.

    Tables are treated as atomic units: they are never split, regardless of size,
    to preserve row integrity.
    """
    ph: List[Tuple[int, str]] = list(pending_headers) if pending_headers else []
    chunks: List[Chunk] = []

    for block_id, block in enumerate(blocks):
        next_block = blocks[block_id + 1] if block_id + 1 < len(blocks) else None
        is_hdr = _is_header(block) or _looks_like_header(block, next_block)

        if is_hdr:
            ph.append((block_id, block.text))
            continue

        header_prefix = "\n".join(t for _, t in ph)
        header_block_ids = [bid for bid, _ in ph]
        extra = {"header_block_ids": header_block_ids} if header_block_ids else {}
        ph = []

        content = f"{header_prefix}\n{block.text}".strip() if header_prefix else block.text
        block_type = block.type

        if block_type == "table":
            # Tables are atomic: keep the entire block as one chunk.
            chunks.append(
                _make_chunk(document_id, page_num, block_id, 0, content, block_type, False, extra)
            )
        else:
            for idx, sub in enumerate(_split_text(content, chunk_size, chunk_overlap)):
                chunks.append(
                    _make_chunk(
                        document_id, page_num, block_id, idx,
                        sub, block_type, False,
                        extra if idx == 0 else {},
                    )
                )

    # Flush any headers that had no following content on this page.
    for bid, header_text in ph:
        chunks.append(
            _make_chunk(document_id, page_num, bid, 0, header_text, "text", True)
        )

    return chunks


def _merge_hanging_text(pages: List[OCRPage]) -> List[OCRPage]:
    """Merge text fragments that span page boundaries.

    If the last non-header text block on page N does not end with sentence-
    terminating punctuation (.!?), its text is prepended to the first non-table
    text block on page N+1.  The merged block stays on page N; the donor block
    is removed from page N+1.  This repairs sentences cut by PDF page breaks.
    """
    if len(pages) <= 1:
        return pages

    page_blocks: List[List[Block]] = [list(p.blocks) for p in pages]

    for i in range(len(pages) - 1):
        # Locate the last non-header text block on page i.
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
            continue  # sentence is complete — no merge needed

        # Locate the first non-table text block on the next page.
        first_idx: Optional[int] = None
        for j, b in enumerate(page_blocks[i + 1]):
            if b.type == "text" and not _is_header(b):
                first_idx = j
                break
        if first_idx is None:
            continue

        donor = page_blocks[i + 1][first_idx]
        merged_text = tail_text + " " + donor.text.lstrip()
        src = page_blocks[i][last_idx]
        page_blocks[i][last_idx] = Block(
            text=merged_text,
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


def split(document_id: str, chunk_size: int = 500, chunk_overlap: int = 50) -> List[Chunk]:
    """Load the OCR JSON, produce metadata-aware chunks, persist, and update the registry.

    Processing order:
    1. Cross-page sentence merging — hanging text joined across page breaks.
    2. Per-page chunking with cross-page header carry-over (a header at the
       bottom of page N is held and prepended to the first body block of page N+1).
    3. Trailing header flush at document end.
    """
    ocr_path = OCR_DIR / f"{document_id}.json"
    if not ocr_path.exists():
        raise FileNotFoundError(f"OCR JSON not found for document_id={document_id}: {ocr_path}")

    ocr_result = OCRResult.model_validate_json(ocr_path.read_text(encoding="utf-8"))
    logger.info("Chunking start: document_id={} pages={}", document_id, len(ocr_result.pages))

    pages = _merge_hanging_text(ocr_result.pages)

    all_chunks: List[Chunk] = []
    # Headers carried forward across page boundaries (not flushed mid-document).
    pending_headers: List[Tuple[int, str]] = []

    for page in pages:
        ph = pending_headers  # carry in from previous page
        pending_headers = []
        page_chunks: List[Chunk] = []

        for block_id, block in enumerate(page.blocks):
            next_block = page.blocks[block_id + 1] if block_id + 1 < len(page.blocks) else None
            is_hdr = _is_header(block) or _looks_like_header(block, next_block)

            if is_hdr:
                ph.append((block_id, block.text))
                continue

            header_prefix = "\n".join(t for _, t in ph)
            header_block_ids = [bid for bid, _ in ph]
            extra = {"header_block_ids": header_block_ids} if header_block_ids else {}
            ph = []

            content = f"{header_prefix}\n{block.text}".strip() if header_prefix else block.text

            if block.type == "table":
                page_chunks.append(
                    _make_chunk(document_id, page.page_num, block_id, 0,
                                content, block.type, False, extra)
                )
            else:
                for idx, sub in enumerate(_split_text(content, chunk_size, chunk_overlap)):
                    page_chunks.append(
                        _make_chunk(
                            document_id, page.page_num, block_id, idx,
                            sub, block.type, False,
                            extra if idx == 0 else {},
                        )
                    )

        # Carry unconsumed headers to the next page — do NOT flush here.
        pending_headers = ph

        all_chunks.extend(page_chunks)
        logger.debug("Page {}: {} chunks", page.page_num, len(page_chunks))

    # Flush any headers that trailed the last content block in the document.
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
    logger.info("Chunking complete: document_id={} total_chunks={}", document_id, len(all_chunks))
    return all_chunks
