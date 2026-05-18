"""RAG pipeline adapter — exposes the OCR/RAG system via the Protocol Genesis server.

All heavy logic lives in app/; this module is a thin HTTP adapter.
document_id == file_id so no additional mapping table is needed.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import List

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse

from app import pipeline
import app.registry as rag_registry
from app.ingest import manager as ingest_manager
from app.worker.tasks import process_document
from .schemas import BBoxOut, CitedSourceOut, DocumentOut, IngestResponse, QueryRequest, QueryResponse


def _sse(event: str, data: str) -> str:
    return f"event: {event}\ndata: {data}\n\n"


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

documents_router = APIRouter(prefix="/documents", tags=["rag-documents"])
query_router = APIRouter(tags=["rag-query"])


# ---------------------------------------------------------------------------
# GET /documents/
# ---------------------------------------------------------------------------

@documents_router.get("/", response_model=List[DocumentOut])
def list_documents():
    records = rag_registry.list_all()
    return [
        DocumentOut(
            document_id=r.document_id,
            file_name=r.file_name,
            status=r.status.value,
            created_at=r.created_at.isoformat(),
            file_hash=r.file_hash,
        )
        for r in records
    ]


# ---------------------------------------------------------------------------
# POST /documents/  — direct PDF upload (bypasses the presigned-URL flow)
# ---------------------------------------------------------------------------

@documents_router.post(
    "/",
    response_model=IngestResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    workspace_id: str = Form(default="__legacy__"),
):
    content = await file.read()
    original_name = Path(file.filename).name if file.filename else "upload.pdf"

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir) / original_name
        tmp_path.write_bytes(content)
        try:
            doc_id = ingest_manager.ingest(str(tmp_path), workspace_id=workspace_id)
        except ValueError as exc:
            msg = str(exc)
            code = status.HTTP_409_CONFLICT if "Duplicate" in msg else status.HTTP_422_UNPROCESSABLE_ENTITY
            raise HTTPException(status_code=code, detail=msg)
        except Exception as exc:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))

    background_tasks.add_task(process_document, doc_id, workspace_id)
    record = rag_registry.get(doc_id)
    return IngestResponse(document_id=doc_id, file_name=record.file_name, status=record.status.value)


# ---------------------------------------------------------------------------
# POST /query/
# ---------------------------------------------------------------------------

@query_router.post("/query/stream")
def stream_query_documents(req: QueryRequest) -> StreamingResponse:
    """
    Stream the RAG answer as Server-Sent Events — same protocol as /emergency/simulate.

    Events emitted:
      status  — "retrieving" | "streaming"
      token   — incremental text chunk from the LLM
      result  — final JSON: {query, answer, sources: CitedSourceOut[]}
      error   — unrecoverable error; stream ends immediately
    """
    def gen():
        try:
            from app.retrieval.search import hybrid_search
            from app.rag.generator import stream_tokens

            yield _sse("status", json.dumps("retrieving"))
            context = []
            try:
                context = hybrid_search(req.query, top_k=req.top_k, workspace_id=req.workspace_id)
            except Exception as exc:
                from loguru import logger
                logger.error("QueryStream: retrieval failed — {}", exc)

            # Build sources now (before streaming) so we can include them in the result.
            sources_out = []
            for r in context:
                rec = rag_registry.get(r.document_id)
                file_name = rec.file_name if rec else r.document_id
                bbox = (
                    {"y_top": r.bbox.y_top, "y_bottom": r.bbox.y_bottom,
                     "page_width": r.bbox.page_width, "page_height": r.bbox.page_height}
                    if r.bbox else None
                )
                sources_out.append({
                    "document_id": r.document_id,
                    "file_name": file_name,
                    "page_num": r.page_num,
                    "chunk_id": r.chunk_id,
                    "text_snippet": r.text[:300],
                    "bbox": bbox,
                })

            yield _sse("status", json.dumps("streaming"))
            full_answer = ""
            try:
                for delta in stream_tokens(req.query, context):
                    full_answer += delta
                    yield _sse("token", json.dumps(delta))
            except Exception as exc:
                from loguru import logger
                logger.error("QueryStream: LLM streaming failed — {}", exc)
                fallback = "המידע המבוקש לא נמצא במסמכים שסופקו."
                full_answer = fallback
                yield _sse("token", json.dumps(fallback))

            yield _sse("result", json.dumps({
                "query": req.query,
                "answer": full_answer,
                "sources": sources_out,
            }))
        except Exception as exc:
            yield _sse("error", json.dumps({"detail": str(exc)}))

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@query_router.post("/query/", response_model=QueryResponse)
def query_documents(req: QueryRequest):
    try:
        rag = pipeline.ask_pipeline(req.query, top_k=req.top_k, workspace_id=req.workspace_id)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))

    sources_out: list[CitedSourceOut] = []
    for s in rag.sources:
        rec = rag_registry.get(s.document_id)
        file_name = rec.file_name if rec else s.document_id
        bbox_out = (
            BBoxOut(
                y_top=s.bbox.y_top,
                y_bottom=s.bbox.y_bottom,
                page_width=s.bbox.page_width,
                page_height=s.bbox.page_height,
            )
            if s.bbox else None
        )
        sources_out.append(CitedSourceOut(
            document_id=s.document_id,
            file_name=file_name,
            page_num=s.page_num,
            chunk_id=s.chunk_id,
            text_snippet=s.text_snippet,
            bbox=bbox_out,
        ))

    return QueryResponse(query=rag.query, answer=rag.answer, sources=sources_out)
