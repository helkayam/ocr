from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional, Tuple

from loguru import logger

import app.registry as registry
from app.models import Block, Chunk, ChunkMetadata, DocumentStatus, OCRResult

OCR_DIR = Path("data/ocr")
CHUNKS_DIR = Path("data/chunks")

# Blocks whose font is this multiple above the page median are treated as headers.
_HEADER_RATIO_THRESHOLD = 1.2

# Separators tried in priority order when looking for a natural split point.
_SEPARATORS = ["\n\n", "\n", ". ", " "]


def _is_header(block: Block) -> bool:
    return block.type == "text" and block.ratio_to_body >= _HEADER_RATIO_THRESHOLD


def _find_split_point(text: str, limit: int) -> int:
    """Return the best index at which to cut *text* so the left part is ≤ *limit* chars.

    Tries each separator in priority order, scanning backwards from *limit* to find
    the last occurrence that keeps the left slice within the budget.  Falls back to
    the nearest space before *limit*, and only hard-cuts at *limit* when no word
    boundary exists at all (avoids cutting mid-word for Hebrew or any script).
    """
    for sep in _SEPARATORS:
        pos = text.rfind(sep, 0, limit + len(sep))
        if pos > 0:
            return pos + len(sep)  # include the separator in the left chunk
    # Last resort: hard cut at limit (should be extremely rare)
    return limit


def _split_text(text: str, chunk_size: int, chunk_overlap: int) -> List[str]:
    """Semantic sliding-window split that never cuts mid-word.

    Algorithm:
    1. If the text fits in one chunk, return it as-is.
    2. Find the best split point within *chunk_size* characters using natural
       language boundaries (paragraph → newline → sentence → word).
    3. The next window starts *chunk_overlap* characters before the split point,
       snapped forward to the nearest whole-word boundary so the overlap always
       begins cleanly.
    4. Repeat until the remainder fits in one chunk.
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

        # Compute overlap start: go back *chunk_overlap* chars from the cut,
        # then snap forward to the next word boundary so we never begin mid-word.
        overlap_start = max(0, cut - chunk_overlap)
        # Snap to start of next word (skip non-space characters that we landed on)
        while overlap_start < cut and remaining[overlap_start] not in (" ", "\n"):
            overlap_start += 1
        # Skip any leading whitespace at the overlap boundary
        while overlap_start < cut and remaining[overlap_start] in (" ", "\n"):
            overlap_start += 1

        start += overlap_start if overlap_start < cut else cut

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
    pending_headers: List[Tuple[int, str]],
) -> Tuple[List[Chunk], List[Tuple[int, str]]]:
    """Produce chunks for a single OCR page.

    *pending_headers* carries any headers that arrived from the previous page so
    that cross-page header context is preserved.  Any headers that remain
    unconsumed at the end of this page are returned to the caller so they can be
    forwarded to the next page (or flushed at document end).

    All blocks — regardless of their ``block.type`` — are treated identically:
    headers are prepended and the combined text is passed through the semantic
    splitter.  This avoids the misidentification problem where the OCR labels
    Hebrew prose as a table.

    Returns:
        (chunks_for_this_page, unconsumed_pending_headers)
    """
    chunks: List[Chunk] = []

    for block_id, block in enumerate(blocks):
        if _is_header(block):
            pending_headers.append((block_id, block.text))
            continue

        header_prefix = "\n".join(text for _, text in pending_headers)
        header_block_ids = [bid for bid, _ in pending_headers]
        extra = {"header_block_ids": header_block_ids} if header_block_ids else {}
        pending_headers = []

        content = f"{header_prefix}\n{block.text}".strip() if header_prefix else block.text
        block_type = block.type  # preserve original type in metadata for traceability

        for idx, sub in enumerate(_split_text(content, chunk_size, chunk_overlap)):
            # Only the first sub-chunk carries the header reference
            chunks.append(
                _make_chunk(
                    document_id, page_num, block_id, idx,
                    sub, block_type, False,
                    extra if idx == 0 else {},
                )
            )

    # Return unconsumed headers to the caller — do NOT flush them here
    return chunks, pending_headers


def split(document_id: str, chunk_size: int = 500, chunk_overlap: int = 50) -> List[Chunk]:
    """Load the OCR JSON for *document_id*, produce metadata-aware chunks,
    persist to ``data/chunks/``, and update the registry to *chunked*.

    Cross-page header context is preserved: a header at the bottom of page N is
    carried forward and prepended to the first content block on page N+1.
    Unconsumed headers are flushed as standalone header chunks only at the very
    end of the document.

    Returns the full list of Chunk objects.
    Raises FileNotFoundError if the OCR JSON is missing.
    """
    ocr_path = OCR_DIR / f"{document_id}.json"
    if not ocr_path.exists():
        raise FileNotFoundError(f"OCR JSON not found for document_id={document_id}: {ocr_path}")

    ocr_result = OCRResult.model_validate_json(ocr_path.read_text(encoding="utf-8"))
    logger.info("Chunking start: document_id={} pages={}", document_id, len(ocr_result.pages))

    all_chunks: List[Chunk] = []
    # Headers carried across page boundaries
    pending_headers: List[Tuple[int, str]] = []

    for page in ocr_result.pages:
        page_chunks, pending_headers = _chunk_page(
            document_id, page.page_num, page.blocks,
            chunk_size, chunk_overlap,
            pending_headers,
        )
        all_chunks.extend(page_chunks)
        logger.debug("Page {}: {} chunks", page.page_num, len(page_chunks))

    # Flush any headers that appeared after the last content block in the document
    if pending_headers:
        last_page = ocr_result.pages[-1].page_num if ocr_result.pages else 0
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
