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


def _is_header(block: Block) -> bool:
    return block.type == "text" and block.ratio_to_body >= _HEADER_RATIO_THRESHOLD


def _split_text(text: str, chunk_size: int, chunk_overlap: int) -> List[str]:
    """Sliding-window character split with overlap. Returns at least one element."""
    text = text.strip()
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]

    step = max(1, chunk_size - chunk_overlap)
    chunks: List[str] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunks.append(text[start:end])
        if end == len(text):
            break
        start += step
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
) -> List[Chunk]:
    """Produce chunks for a single OCR page.

    Headers are accumulated and prepended to the next content block so that
    every content chunk carries its full heading context. If a header has no
    following content on the page it is emitted as a standalone header chunk.
    """
    chunks: List[Chunk] = []

    # Each entry: (block_id, header_text)
    pending_headers: List[Tuple[int, str]] = []

    for block_id, block in enumerate(blocks):
        if _is_header(block):
            pending_headers.append((block_id, block.text))
            continue

        # Build heading prefix from all accumulated headers
        header_prefix = "\n".join(text for _, text in pending_headers)
        header_block_ids = [bid for bid, _ in pending_headers]
        extra = {"header_block_ids": header_block_ids} if header_block_ids else {}
        pending_headers = []

        if block.type == "table":
            content = f"{header_prefix}\n{block.text}".strip() if header_prefix else block.text
            chunks.append(
                _make_chunk(document_id, page_num, block_id, 0, content, "table", False, extra)
            )
        else:
            content = f"{header_prefix}\n{block.text}".strip() if header_prefix else block.text
            for idx, sub in enumerate(_split_text(content, chunk_size, chunk_overlap)):
                # Only the first sub-chunk carries the header reference in extra
                chunks.append(
                    _make_chunk(
                        document_id, page_num, block_id, idx,
                        sub, "text", False,
                        extra if idx == 0 else {},
                    )
                )

    # Flush trailing headers that had no following content block on this page
    for bid, header_text in pending_headers:
        chunks.append(
            _make_chunk(document_id, page_num, bid, 0, header_text, "text", True)
        )

    return chunks


def split(document_id: str, chunk_size: int = 500, chunk_overlap: int = 50) -> List[Chunk]:
    """Load the OCR JSON for *document_id*, produce metadata-aware chunks,
    persist to ``data/chunks/``, and update the registry to *chunked*.

    Returns the full list of Chunk objects.
    Raises FileNotFoundError if the OCR JSON is missing.
    """
    ocr_path = OCR_DIR / f"{document_id}.json"
    if not ocr_path.exists():
        raise FileNotFoundError(f"OCR JSON not found for document_id={document_id}: {ocr_path}")

    ocr_result = OCRResult.model_validate_json(ocr_path.read_text(encoding="utf-8"))
    logger.info("Chunking start: document_id={} pages={}", document_id, len(ocr_result.pages))

    all_chunks: List[Chunk] = []
    for page in ocr_result.pages:
        page_chunks = _chunk_page(
            document_id, page.page_num, page.blocks, chunk_size, chunk_overlap
        )
        all_chunks.extend(page_chunks)
        logger.debug("Page {}: {} chunks", page.page_num, len(page_chunks))

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
