import json
from pathlib import Path

from loguru import logger

import app.registry as registry
from app.indexing import db, embedder
from app.indexing.bm25_store import BM25Store
from app.models import Chunk, DocumentStatus

CHUNKS_DIR = Path("data/chunks")
INDEX_DIR  = Path("data/index")

UPSERT_BATCH_SIZE = 100


def _load_chunks(document_id: str) -> tuple[str, list[Chunk]]:
    """Return ``(workspace_id, chunks)`` from the chunks file.

    ``document_id`` is stored only at the root of the JSON envelope — it is
    injected into each Chunk in-memory here so downstream code can use
    ``chunk.document_id`` without knowing the envelope format.
    """
    path = CHUNKS_DIR / f"{document_id}_chunks.json"
    if not path.exists():
        raise FileNotFoundError(f"Chunks file not found: {path}")
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, list):
        # Legacy flat-list format: document_id was stored per-chunk
        return "__legacy__", [Chunk(**item) for item in raw]
    workspace_id = raw.get("workspace_id", "__legacy__")
    doc_id = raw.get("document_id", document_id)
    return workspace_id, [Chunk(**item, document_id=doc_id) for item in raw["chunks"]]


def _to_chroma_metadata(chunk: Chunk, workspace_id: str) -> dict:
    """Flatten ChunkMetadata to a ChromaDB-compatible dict (scalar values only).

    ``document_id`` and ``workspace_id`` are injected from the root envelope,
    not stored inside individual chunk objects on disk.
    """
    return {
        "document_id": chunk.document_id,
        "workspace_id": workspace_id,
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
    """Embed and upsert all child chunks for *document_id* into ChromaDB and BM25.

    Processing order:
      1. Embed child chunks in batches of UPSERT_BATCH_SIZE (memory-bounded).
      2. Upsert each batch into ChromaDB.  On dimension mismatch both the
         ChromaDB collection and the BM25 corpus are reset before retrying.
      3. After all batches succeed, bulk-upsert into BM25 in a single rebuild.
      4. Verify ChromaDB stored count equals chunk count before marking indexed.

    BM25 failure is non-fatal: a warning is logged but the document is still
    marked indexed (ChromaDB is the primary index).

    Returns the number of child chunks indexed.
    """
    workspace_id, chunks = _load_chunks(document_id)
    total  = len(chunks)
    logger.info("Indexing start: document_id={} workspace={} chunks={}", document_id, workspace_id, total)

    if not chunks:
        logger.warning("No chunks to index for document_id={}", document_id)
        registry.update_status(document_id, DocumentStatus.indexed)
        return 0

    collection   = db.get_collection(INDEX_DIR)
    bm25         = BM25Store(INDEX_DIR)
    expected_dim = embedder.get_embedding_dim()
    existing_dim = _collection_embedding_dim(collection)

    if existing_dim is not None and existing_dim != expected_dim:
        logger.warning(
            "Dimension mismatch: collection has {}d vectors, embedder produces {}d "
            "— resetting ChromaDB collection and BM25 index",
            existing_dim, expected_dim,
        )
        collection = db.reset_collection(INDEX_DIR)
        bm25.reset()

    num_batches     = (total + UPSERT_BATCH_SIZE - 1) // UPSERT_BATCH_SIZE
    batch_num       = 0
    _dim_reset_done = False
    bm25_entries: list[dict] = []

    def _upsert(col, batch, vectors):
        col.upsert(
            ids=[c.chunk_id for c in batch],
            embeddings=vectors,
            documents=[c.text for c in batch],
            metadatas=[_to_chroma_metadata(c, workspace_id) for c in batch],
        )

    try:
        for batch_num, batch_start in enumerate(
            range(0, total, UPSERT_BATCH_SIZE), start=1
        ):
            batch   = chunks[batch_start : batch_start + UPSERT_BATCH_SIZE]
            vectors = embedder.embed([c.text for c in batch])
            try:
                _upsert(collection, batch, vectors)
            except Exception as upsert_exc:
                if "dimension" in str(upsert_exc).lower() and not _dim_reset_done:
                    logger.warning(
                        "Dimension mismatch on upsert (batch {}) — resetting and retrying",
                        batch_num,
                    )
                    collection = db.reset_collection(INDEX_DIR)
                    bm25.reset()
                    _dim_reset_done = True
                    _upsert(collection, batch, vectors)
                else:
                    raise

            # Collect BM25 entries during the same pass — single rebuild at the end
            bm25_entries.extend(
                {
                    "chunk_id": c.chunk_id,
                    "document_id": c.document_id,
                    "workspace_id": workspace_id,
                    "text": c.text,
                }
                for c in batch
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

    # Verify every vector actually landed before marking the document as indexed
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

    # BM25 bulk upsert — single rebuild regardless of batch count
    try:
        bm25.add_chunks(bm25_entries)
        logger.info(
            "BM25 indexing complete: document_id={} entries={}", document_id, len(bm25_entries)
        )
    except Exception as bm25_exc:
        logger.warning(
            "BM25 indexing failed for document_id={} (non-fatal, dense index is intact): {}",
            document_id, bm25_exc,
        )

    registry.update_status(document_id, DocumentStatus.indexed)
    logger.info("Indexing complete: document_id={} vectors={}", document_id, total)
    return total


def delete_document(document_id: str) -> None:
    """Remove every chunk belonging to *document_id* from ChromaDB and BM25.

    Safe to call even if the document has no vectors (no-op in that case).
    """
    logger.info("Deleting vectors: document_id={}", document_id)

    collection = db.get_collection(INDEX_DIR)
    collection.delete(where={"document_id": document_id})

    try:
        bm25 = BM25Store(INDEX_DIR)
        bm25.delete_document(document_id)
    except Exception as bm25_exc:
        logger.warning(
            "BM25 deletion failed for document_id={} (non-fatal): {}",
            document_id, bm25_exc,
        )

    logger.info("Vectors deleted: document_id={}", document_id)
