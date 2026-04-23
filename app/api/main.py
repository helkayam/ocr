"""FastAPI application — ProtocolGenesis OCR REST API.

Run with:
    uvicorn app.api.main:app --reload
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import List

from fastapi import FastAPI, File, HTTPException, UploadFile, status
from loguru import logger
from redis import Redis
from rq import Queue

import app.registry as registry
from app import pipeline
from app.api.schemas import (
    CitedSourceOut,
    DocumentOut,
    IngestResponse,
    QueryRequest,
    QueryResponse,
    ReindexResponse,
)
from app.ingest import manager as ingest_manager
from app.worker.tasks import process_document

app = FastAPI(
    title="ProtocolGenesis OCR API",
    description="Hebrew-optimised document ingestion, indexing, and RAG.",
    version="0.1.0",
)

_REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
_QUEUE_NAME = "ocr"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_queue() -> Queue:
    """Return a fresh RQ Queue bound to Redis.  Isolated here for easy mocking."""
    return Queue(_QUEUE_NAME, connection=Redis.from_url(_REDIS_URL))


def _record_to_out(record) -> DocumentOut:
    return DocumentOut(
        document_id=record.document_id,
        file_name=record.file_name,
        status=record.status.value,
        created_at=record.created_at,
        file_hash=record.file_hash,
    )


# ---------------------------------------------------------------------------
# POST /documents/  — register a PDF and queue async processing
# ---------------------------------------------------------------------------

@app.post(
    "/documents/",
    response_model=IngestResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload a PDF document and queue it for async processing",
)
async def upload_document(file: UploadFile = File(...)) -> IngestResponse:
    """Accept a PDF upload, run Phase 2 (validate + register) synchronously,
    then enqueue Phases 3-5 (OCR → chunk → embed/index) for background
    processing by the RQ worker.

    Returns 202 Accepted immediately with the document_id and status=pending.
    """
    content = await file.read()

    # Preserve the original filename so the registry records it correctly.
    original_name = Path(file.filename).name if file.filename else "upload.pdf"

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir) / original_name
        tmp_path.write_bytes(content)

        try:
            # Phase 2 only: validate, hash, dedup, copy to data/raw/, register.
            doc_id = ingest_manager.ingest(str(tmp_path))
        except ValueError as exc:
            msg = str(exc)
            if "Duplicate" in msg:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=msg)
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=msg)
        except Exception as exc:
            logger.exception("Unhandled error during ingest registration")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))

    # File is now safely in data/raw/; temp dir may be cleaned up.
    # Enqueue Phases 3-5 for background execution.
    try:
        q = _get_queue()
        q.enqueue(process_document, doc_id)
    except Exception as exc:
        logger.exception("Failed to enqueue processing job for document_id={}", doc_id)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))

    record = registry.get(doc_id)
    logger.info("API: document queued — document_id={}", doc_id)
    return IngestResponse(
        document_id=doc_id,
        file_name=record.file_name,
        status=record.status.value,
    )


# ---------------------------------------------------------------------------
# GET /documents/  — list all documents with their current status
# ---------------------------------------------------------------------------

@app.get(
    "/documents/",
    response_model=List[DocumentOut],
    summary="List all ingested documents",
)
def list_documents() -> List[DocumentOut]:
    """Return every document currently in the registry with its processing status."""
    records = registry.list_all()
    logger.debug("API: list_documents count={}", len(records))
    return [_record_to_out(r) for r in records]


# ---------------------------------------------------------------------------
# DELETE /documents/{doc_id}  — full deletion
# ---------------------------------------------------------------------------

@app.delete(
    "/documents/{doc_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a document from all storage layers",
)
def delete_document(doc_id: str) -> None:
    """Remove the document from the registry, raw/OCR/chunk files, and ChromaDB."""
    try:
        pipeline.delete_pipeline(doc_id)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {doc_id!r} not found",
        )
    except Exception as exc:
        logger.exception("Unhandled error during delete")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))

    logger.info("API: delete complete document_id={}", doc_id)


# ---------------------------------------------------------------------------
# POST /documents/{doc_id}/reindex  — re-embed and re-index
# ---------------------------------------------------------------------------

@app.post(
    "/documents/{doc_id}/reindex",
    response_model=ReindexResponse,
    summary="Re-run Phase 5 indexing for an existing document",
)
def reindex_document(doc_id: str) -> ReindexResponse:
    """Delete existing vectors and regenerate embeddings from the stored chunks."""
    try:
        count = pipeline.reindex_pipeline(doc_id)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {doc_id!r} not found",
        )
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        )
    except Exception as exc:
        logger.exception("Unhandled error during reindex")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))

    logger.info("API: reindex complete document_id={} chunks={}", doc_id, count)
    return ReindexResponse(document_id=doc_id, chunks_indexed=count)


# ---------------------------------------------------------------------------
# POST /query/  — RAG question answering
# ---------------------------------------------------------------------------

@app.post(
    "/query/",
    response_model=QueryResponse,
    summary="Ask a question and receive a Hebrew answer with source citations",
)
def query_documents(req: QueryRequest) -> QueryResponse:
    """Retrieve the top-k most relevant chunks and generate a grounded Hebrew answer."""
    try:
        rag = pipeline.ask_pipeline(req.query, top_k=req.top_k)
    except Exception as exc:
        logger.exception("Unhandled error during query")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))

    logger.info("API: query complete query={!r}", req.query)
    return QueryResponse(
        query=rag.query,
        answer=rag.answer,
        sources=[
            CitedSourceOut(document_id=s.document_id, page_num=s.page_num)
            for s in rag.sources
        ],
    )
