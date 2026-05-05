"""Background tasks executed by the RQ worker.

Each function here is a unit of work enqueued by the API and executed
asynchronously by the worker process.
"""
from __future__ import annotations

from loguru import logger

import app.registry as registry
from app.chunking import splitter
from app.indexing import indexer
from app.models import DocumentStatus
from app.ocr import processor as ocr_processor


def process_document(doc_id: str, workspace_id: str = "__legacy__") -> None:
    """Run Phases 3 → 4 → 5 for a document already registered by Phase 2.

    *workspace_id* is forwarded to the chunker so it is written to the JSON
    root and subsequently injected into every ChromaDB metadata record at
    index time.

    On failure the registry status is set to ``error`` and the exception is
    re-raised so RQ can mark the job as failed and retain the traceback.
    """
    logger.info("Worker: processing start — document_id={} workspace={}", doc_id, workspace_id)
    try:
        ocr_processor.process(doc_id)
        logger.info("  [1/3] OCR complete")

        splitter.split(doc_id, workspace_id=workspace_id)
        logger.info("  [2/3] Chunked")

        indexer.index(doc_id)
        logger.info("  [3/3] Indexed")
    except Exception:
        logger.exception("Worker: processing failed — document_id={}", doc_id)
        registry.update_status(doc_id, DocumentStatus.error)
        raise

    logger.info("Worker: processing complete — document_id={}", doc_id)
