"""Synchronous pipeline orchestration.

Each function represents one user-facing operation and chains the phase
modules in the correct order. Both the CLI (main.py) and the REST API
(app/api/main.py) import from here — never duplicate this logic.
"""
from __future__ import annotations

from pathlib import Path

from loguru import logger

import app.registry as registry
from app.chunking import splitter
from app.indexing import indexer
from app.ingest import manager as ingest_manager
from app.models import RAGResponse
from app.ocr import processor as ocr_processor
from app.rag import generator

# Re-use the path constants defined in each phase module so there is one
# source of truth for every directory location.
from app.ingest.manager import RAW_DIR
from app.ocr.processor import OCR_DIR
from app.chunking.splitter import CHUNKS_DIR


def ingest_pipeline(file_path: str | Path) -> str:
    """Phase 2 → 3 → 4 → 5.  Returns the new document_id."""
    logger.info("Pipeline: ingest start — {}", file_path)

    doc_id = ingest_manager.ingest(file_path)
    logger.info("  [1/4] Ingested  → document_id={}", doc_id)

    ocr_processor.process(doc_id)
    logger.info("  [2/4] OCR complete")

    chunks = splitter.split(doc_id)
    logger.info("  [3/4] Chunked   → {} chunks", len(chunks))

    count = indexer.index(doc_id)
    logger.info("  [4/4] Indexed   → {} vectors", count)

    logger.info("Pipeline: ingest complete — document_id={}", doc_id)
    return doc_id


def ask_pipeline(query: str, top_k: int = 5) -> RAGResponse:
    """Phase 6.  Returns a RAGResponse with answer and cited sources."""
    logger.info("Pipeline: ask — {!r}", query)
    response = generator.answer(query, top_k=top_k)
    logger.info("Pipeline: ask complete")
    return response


def delete_pipeline(doc_id: str) -> None:
    """Remove a document from every layer of storage.

    Deletes (in order):
      1. ChromaDB vectors
      2. data/raw/, data/ocr/, data/chunks/ files
      3. Registry entry

    Safe to call even if only some layers exist (partial ingest).
    Raises KeyError if doc_id is not in the registry.
    """
    # Verify the document exists before doing destructive work
    if not registry.get(doc_id):
        raise KeyError(f"Document not found in registry: {doc_id!r}")

    logger.info("Pipeline: delete start — document_id={}", doc_id)

    indexer.delete_document(doc_id)
    logger.debug("  Vectors deleted from ChromaDB")

    _files = [
        RAW_DIR / f"{doc_id}.pdf",
        OCR_DIR / f"{doc_id}.json",
        CHUNKS_DIR / f"{doc_id}_chunks.json",
    ]
    for f in _files:
        if f.exists():
            f.unlink()
            logger.debug("  Deleted file: {}", f)

    registry.delete(doc_id)
    logger.info("Pipeline: delete complete — document_id={}", doc_id)


def evaluate_pipeline(dataset_path: str | Path, top_k: int = 5) -> None:
    """Phase 10.  Load the golden dataset and run the evaluation suite."""
    from app.rag.evaluate import RAGEvaluator

    logger.info("Pipeline: evaluate start — {}", dataset_path)
    RAGEvaluator(top_k=top_k).run_suite(dataset_path)
    logger.info("Pipeline: evaluate complete")


def reindex_pipeline(doc_id: str) -> int:
    """Delete vectors from ChromaDB and re-run Phase 5 for *doc_id*.

    Assumes the chunks file already exists (i.e., Phase 4 has been run).
    Returns the number of re-indexed chunks.
    Raises FileNotFoundError if the chunks file is missing.
    Raises KeyError if doc_id is not in the registry.
    """
    if not registry.get(doc_id):
        raise KeyError(f"Document not found in registry: {doc_id!r}")

    chunks_path = CHUNKS_DIR / f"{doc_id}_chunks.json"
    if not chunks_path.exists():
        raise FileNotFoundError(
            f"Chunks file not found for document_id={doc_id!r}. "
            "Run ingest first to generate chunks before re-indexing."
        )

    logger.info("Pipeline: reindex start — document_id={}", doc_id)

    indexer.delete_document(doc_id)
    logger.debug("  Old vectors deleted")

    count = indexer.index(doc_id)
    logger.info("Pipeline: reindex complete — document_id={} vectors={}", doc_id, count)
    return count
