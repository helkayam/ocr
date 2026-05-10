"""RAG pipeline adapter — exposes the OCR/RAG system via the Protocol Genesis server.

All heavy logic lives in app/; this module is a thin HTTP adapter.
document_id == file_id so no additional mapping table is needed.
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import List

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile, status

from app import pipeline
import app.registry as rag_registry
from app.ingest import manager as ingest_manager
from app.worker.tasks import process_document
from .schemas import DocumentOut, IngestResponse, QueryRequest, QueryResponse


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

@query_router.post("/query/", response_model=QueryResponse)
def query_documents(req: QueryRequest):
    try:
        # הקריאה לליבה של ה-RAG נשארת זהה
        rag = pipeline.ask_pipeline(req.query, top_k=req.top_k, workspace_id=req.workspace_id)
        
        # אנו מוסיפים יצירת מערך מקורות מובנה
        # כל מקור יכיל את ה-id של המסמך ומספר העמוד (אם קיים)
        sources_list = []
        if hasattr(rag, 'sources') and rag.sources:
            for source in rag.sources:
                sources_list.append({
                    "document_id": source.document_id,
                    "page_num": source.page_num,
                    "file_name": getattr(source, 'file_name', "Unknown File")
                })

    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))
    
    # עכשיו ה-Response מחזיר גם את רשימת המקורות
    return QueryResponse(
        query=rag.query, 
        answer=rag.answer,
        sources=sources_list # <-- התוספת הקריטית!
    )