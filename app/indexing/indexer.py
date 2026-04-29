import json
from pathlib import Path

from loguru import logger

import app.registry as registry
from app.indexing import db, embedder
from app.models import Chunk, DocumentStatus

CHUNKS_DIR = Path("data/chunks")
INDEX_DIR  = Path("data/index")

UPSERT_BATCH_SIZE = 100


def _load_chunks(document_id: str) -> list[Chunk]:
    path = CHUNKS_DIR / f"{document_id}_chunks.json"
    if not path.exists():
        raise FileNotFoundError(f"Chunks file not found: {path}")
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [Chunk(**item) for item in raw]


def _to_chroma_metadata(chunk: Chunk) -> dict:
    """Flatten ChunkMetadata to a ChromaDB-compatible dict (scalar values only)."""
    return {
        "document_id": chunk.metadata.document_id,
        "page_num":    chunk.metadata.page_num,
        "block_id":    chunk.metadata.block_id,
        "is_header":   chunk.metadata.is_header,
        "block_type":  chunk.metadata.block_type,
        "extra":       json.dumps(chunk.metadata.extra, ensure_ascii=False),
    }


def _collection_embedding_dim(collection) -> int | None:
    """Return the dimension of the first stored vector, or None if the collection is empty."""
    if collection.count() == 0:
        return None
    try:
        result = collection.get(limit=1, include=["embeddings"])
        embs = result.get("embeddings") or []
        if embs and embs[0]:
            return len(embs[0])
    except Exception:
        pass
    return None


def index(document_id: str) -> int:
    """Embed and upsert all chunks for *document_id* into ChromaDB.

    Processes chunks in batches of UPSERT_BATCH_SIZE to keep memory bounded.
    Detects embedding dimension mismatches (e.g. after a model change) and
    resets the entire collection before indexing so no stale vectors remain.
    Registry is updated to DocumentStatus.indexed ONLY after:
      1. All batches upsert without exception.
      2. A post-loop count query confirms every vector landed in ChromaDB.
    On any failure the registry is set to DocumentStatus.error and the
    exception is re-raised so the caller can surface it.

    Returns the number of chunks indexed.
    """
    chunks = _load_chunks(document_id)
    total  = len(chunks)
    logger.info("Indexing start: document_id={} chunks={}", document_id, total)

    if not chunks:
        logger.warning("No chunks to index for document_id={}", document_id)
        registry.update_status(document_id, DocumentStatus.indexed)
        return 0

    collection   = db.get_collection(INDEX_DIR)
    expected_dim = embedder.get_embedding_dim()
    existing_dim = _collection_embedding_dim(collection)

    if existing_dim is not None and existing_dim != expected_dim:
        logger.warning(
            "Dimension mismatch: collection has {}d vectors, embedder produces {}d "
            "— deleting and recreating collection",
            existing_dim, expected_dim,
        )
        collection = db.reset_collection(INDEX_DIR)

    num_batches = (total + UPSERT_BATCH_SIZE - 1) // UPSERT_BATCH_SIZE
    batch_num   = 0

    try:
        for batch_num, batch_start in enumerate(
            range(0, total, UPSERT_BATCH_SIZE), start=1
        ):
            batch = chunks[batch_start : batch_start + UPSERT_BATCH_SIZE]
            vectors = embedder.embed([c.text for c in batch])
            collection.upsert(
                ids=[c.chunk_id for c in batch],
                embeddings=vectors,
                documents=[c.text for c in batch],
                metadatas=[_to_chroma_metadata(c) for c in batch],
            )
            logger.debug(
                "Upserted batch {}/{} ({} chunks) for document_id={}",
                batch_num, num_batches, len(batch), document_id,
            )
    except Exception as exc:
        logger.error(
            "Indexing failed at batch {}/{} for document_id={}: {}",
            batch_num, num_batches, document_id, exc,
        )
        registry.update_status(document_id, DocumentStatus.error)
        raise

    # Verify every vector actually landed before marking the document as indexed.
    result = collection.get(
        where={"document_id": {"$eq": document_id}},
        include=[],
    )
    stored = len(result["ids"])
    if stored != total:
        msg = (
            f"ChromaDB count mismatch after indexing document_id={document_id}: "
            f"expected {total}, got {stored}"
        )
        logger.error(msg)
        registry.update_status(document_id, DocumentStatus.error)
        raise RuntimeError(msg)

    registry.update_status(document_id, DocumentStatus.indexed)
    logger.info("Indexing complete: document_id={} vectors={}", document_id, total)
    return total


def delete_document(document_id: str) -> None:
    """Remove every chunk belonging to *document_id* from ChromaDB.

    Safe to call even if the document has no vectors (no-op in that case).
    """
    logger.info("Deleting vectors: document_id={}", document_id)
    collection = db.get_collection(INDEX_DIR)
    collection.delete(where={"document_id": document_id})
    logger.info("Vectors deleted: document_id={}", document_id)
