"""RAG pipeline adapter — exposes the OCR/RAG system via the Protocol Genesis server.

All heavy logic lives in app/; this module is a thin HTTP adapter.
document_id == file_id so no additional mapping table is needed.
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import List

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

from app import pipeline
import app.registry as rag_registry
from app.ingest import manager as ingest_manager
from app.worker.tasks import process_document


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class DocumentOut(BaseModel):
    document_id: str
    file_name: str
    status: str
    created_at: str
    file_hash: str


class IngestResponse(BaseModel):
    document_id: str
    file_name: str
    status: str


class ReindexResponse(BaseModel):
    document_id: str
    chunks_indexed: int


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1)
    top_k: int = Field(default=5, ge=1, le=50)


class QueryResponse(BaseModel):
    query: str
    answer: str


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
async def upload_document(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    content = await file.read()
    original_name = Path(file.filename).name if file.filename else "upload.pdf"

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir) / original_name
        tmp_path.write_bytes(content)
        try:
            doc_id = ingest_manager.ingest(str(tmp_path))
        except ValueError as exc:
            msg = str(exc)
            code = status.HTTP_409_CONFLICT if "Duplicate" in msg else status.HTTP_422_UNPROCESSABLE_ENTITY
            raise HTTPException(status_code=code, detail=msg)
        except Exception as exc:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))

    background_tasks.add_task(process_document, doc_id)
    record = rag_registry.get(doc_id)
    return IngestResponse(document_id=doc_id, file_name=record.file_name, status=record.status.value)


# ---------------------------------------------------------------------------
# DELETE /documents/{doc_id}
# ---------------------------------------------------------------------------

@documents_router.delete("/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(doc_id: str):
    # Look up storage object_name before pipeline wipes the registry
    from services import file_service
    from services.storage_service import delete_object

    file_rec = file_service.get_file(doc_id)
    object_name = file_rec.get("object_name") if file_rec else None

    try:
        pipeline.delete_pipeline(doc_id)
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Document {doc_id!r} not found")
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))

    # Clean up SQL DB and object storage (best-effort — RAG registry already gone)
    try:
        file_service.delete_file(doc_id)
    except Exception as exc:
        print(f"[rag_router] SQL delete failed for {doc_id}: {exc}")

    if object_name:
        delete_object(object_name)


# ---------------------------------------------------------------------------
# POST /documents/{doc_id}/reindex
# ---------------------------------------------------------------------------

@documents_router.post("/{doc_id}/reindex", response_model=ReindexResponse)
def reindex_document(doc_id: str):
    try:
        count = pipeline.reindex_pipeline(doc_id)
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Document {doc_id!r} not found")
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))
    return ReindexResponse(document_id=doc_id, chunks_indexed=count)


# ---------------------------------------------------------------------------
# POST /query/
# ---------------------------------------------------------------------------

@query_router.post("/query/", response_model=QueryResponse)
def query_documents(req: QueryRequest):
    try:
        rag = pipeline.ask_pipeline(req.query, top_k=req.top_k)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))
    return QueryResponse(query=rag.query, answer=rag.answer)
