from __future__ import annotations

import json
from pathlib import Path
from typing import List

from loguru import logger

import app.registry as registry
from app import indexing
from app.indexing import db, embedder
from app.models import Chunk, DocumentStatus

CHUNKS_DIR = Path("data/chunks")
INDEX_DIR = Path("data/index")

# Maximum chunks sent to ChromaDB in a single upsert call.
_UPSERT_BATCH_SIZE = 100


def _load_chunks(document_id: str) -> List[Chunk]:
    path = CHUNKS_DIR / f"{document_id}_chunks.json"
    if not path.exists():
        raise FileNotFoundError(f"Chunks file not found for document_id={document_id}: {path}")
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [Chunk(**item) for item in raw]


def _to_chroma_metadata(chunk: Chunk) -> dict:
    """Flatten ChunkMetadata to a ChromaDB-compatible dict (scalar values only)."""
    return {
        "document_id": chunk.metadata.document_id,
        "page_num": chunk.metadata.page_num,
        "block_id": chunk.metadata.block_id,
        "is_header": chunk.metadata.is_header,
        "block_type": chunk.metadata.block_type,
        "extra": json.dumps(chunk.metadata.extra, ensure_ascii=False),
    }


def index(document_id: str) -> int:
    """Embed and upsert all chunks for *document_id* into ChromaDB.

    Returns the number of chunks indexed.
    Raises FileNotFoundError if the chunks file is missing.
    """
    chunks = _load_chunks(document_id)
    logger.info("Indexing start: document_id={} chunks={}", document_id, len(chunks))

    if not chunks:
        logger.warning("No chunks to index for document_id={}", document_id)
        registry.update_status(document_id, DocumentStatus.indexed)
        return 0

    collection = db.get_collection(INDEX_DIR)

    # Process in batches to keep memory bounded for large documents
    for batch_start in range(0, len(chunks), _UPSERT_BATCH_SIZE):
        batch = chunks[batch_start: batch_start + _UPSERT_BATCH_SIZE]
        vectors = embedder.embed([c.text for c in batch])
        collection.upsert(
            ids=[c.chunk_id for c in batch],
            embeddings=vectors,
            documents=[c.text for c in batch],
            metadatas=[_to_chroma_metadata(c) for c in batch],
        )
        logger.debug(
            "Upserted batch [{}-{}] for document_id={}",
            batch_start, batch_start + len(batch) - 1, document_id,
        )

    registry.update_status(document_id, DocumentStatus.indexed)
    logger.info("Indexing complete: document_id={} chunks={}", document_id, len(chunks))
    return len(chunks)


def delete_document(document_id: str) -> None:
    """Remove every chunk belonging to *document_id* from ChromaDB.

    Safe to call even if the document has no vectors (no-op in that case).
    """
    logger.info("Deleting vectors: document_id={}", document_id)
    collection = db.get_collection(INDEX_DIR)
    collection.delete(where={"document_id": document_id})
    logger.info("Vectors deleted: document_id={}", document_id)
