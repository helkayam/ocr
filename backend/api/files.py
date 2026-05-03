import mimetypes
import os
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request
from fastapi.responses import FileResponse
from typing import Optional, List

from .schemas import (
    FileItem,
    UploadUrlRequest,
    UploadUrlResponse,
    ConfirmUploadRequest,
    ConfirmUploadResponse,
)
from services.storage_service import (
    generate_presigned_upload_url,
    get_file_bytes,
    get_local_path,
    save_file_local,
    storage_mode,
)
from services import file_service
from services.nlp_service import process_file
from services.geo_service import parse_geojson, store_geo_layer

router = APIRouter(prefix="/files", tags=["files"])


def _process_pdf_rag(file_id: str, object_name: str, filename: str) -> None:
    """Download PDF from storage, register in RAG system, and run the full pipeline."""
    import tempfile
    from app.ingest import manager as ingest_manager
    from app.worker.tasks import process_document

    try:
        raw = get_file_bytes(object_name)
    except Exception as e:
        print(f"[rag_bridge] Could not download {object_name}: {e}")
        return

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir) / filename
        tmp_path.write_bytes(raw)
        try:
            ingest_manager.ingest(str(tmp_path), document_id=file_id)
        except ValueError as e:
            # Duplicate hash — existing document already registered, still process
            print(f"[rag_bridge] ingest warning for {file_id}: {e}")
        except Exception as e:
            print(f"[rag_bridge] ingest failed for {file_id}: {e}")
            return

    try:
        process_document(file_id)
    except Exception as e:
        print(f"[rag_bridge] RAG processing failed for {file_id}: {e}")


# ─── Upload flow ─────────────────────────────────────────────────────────────

@router.post("/upload-url", response_model=UploadUrlResponse)
def get_upload_url(request: UploadUrlRequest):
    file_id = str(uuid.uuid4())
    object_name = f"{request.workspace_id}/{file_id}/{request.filename}"
    upload_url = generate_presigned_upload_url(object_name)
    return UploadUrlResponse(upload_url=upload_url, file_id=file_id, expires_in=3600)


@router.post("/confirm-upload", response_model=ConfirmUploadResponse)
def confirm_upload(request: ConfirmUploadRequest, background_tasks: BackgroundTasks):
    object_name = f"{request.workspace_id}/{request.file_id}/{request.filename}"
    file_item = file_service.create_file(request, object_name)

    fname_lower = request.filename.lower()
    if fname_lower.endswith(".pdf"):
        # Route PDFs through the full RAG pipeline (OCR → chunk → ChromaDB)
        background_tasks.add_task(
            _process_pdf_rag,
            request.file_id,
            object_name,
            request.filename,
        )
    elif fname_lower.endswith(".docx"):
        background_tasks.add_task(
            process_file,
            request.file_id,
            request.workspace_id,
            request.filename,
            object_name,
        )
    elif fname_lower.endswith((".geojson", ".json")):
        background_tasks.add_task(
            _process_geojson_bg,
            request.file_id,
            request.workspace_id,
            object_name,
        )

    return ConfirmUploadResponse(file=file_item)


def _process_geojson_bg(file_id: str, workspace_id: str, object_name: str) -> None:
    try:
        data = get_file_bytes(object_name)
        geo = parse_geojson(data)
        store_geo_layer(file_id, workspace_id, geo)
    except Exception as e:
        print(f"GeoJSON processing failed for {file_id}: {e}")


# ─── Local-storage upload endpoint (used when MinIO is unavailable) ──────────

@router.put("/local-upload/{object_name:path}", status_code=200)
async def local_upload(object_name: str, request: Request):
    """
    Receives the raw file binary PUT by the frontend when in local-storage mode.
    The URL for this endpoint is returned by generate_presigned_upload_url().
    """
    data = await request.body()
    save_file_local(object_name, data)
    return {"status": "ok", "bytes": len(data)}


# ─── Local-storage download / serve ──────────────────────────────────────────

@router.get("/local-download/{object_name:path}")
def local_download(object_name: str):
    """Serve a file stored in local_storage/ (used in local mode)."""
    try:
        path = get_local_path(object_name)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid path")
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    mime, _ = mimetypes.guess_type(path.name)
    return FileResponse(
        str(path),
        media_type=mime or "application/octet-stream",
        filename=path.name,
    )


# ─── Listing / status ─────────────────────────────────────────────────────────

def _rag_status(file_id: str) -> Optional[str]:
    """Return the RAG pipeline status for a PDF file, or None if not registered."""
    try:
        import app.registry as rag_registry
        rec = rag_registry.get(file_id)
        return rec.status.value if rec else None
    except Exception:
        return None


@router.get("", response_model=List[FileItem])
def list_files(workspace_id: Optional[str] = Query(None)):
    items = file_service.list_files(workspace_id)
    # Enrich PDF processing_status from RAG registry when available
    enriched = []
    for item in items:
        if item.type.value == "pdf":
            rag_stat = _rag_status(item.id)
            if rag_stat:
                # Rebuild FileItem with updated processing_status surfaced via metadata
                # (FileItem doesn't have processing_status; we embed it in the status field
                #  for PDFs so the frontend can poll progress)
                pass  # status is in item.status; RAG progress exposed via /files/{id}/status
        enriched.append(item)
    return enriched


@router.get("/{file_id}/status")
def get_file_status(file_id: str):
    f = file_service.get_file(file_id)
    if not f:
        raise HTTPException(status_code=404, detail="File not found")

    processing_status = f.get("processing_status", "unknown")
    # For PDFs, prefer the more granular RAG pipeline status
    if str(f.get("file_type", "")).lower() == "pdf":
        rag_stat = _rag_status(file_id)
        if rag_stat:
            processing_status = rag_stat

    return {
        "file_id": file_id,
        "processing_status": processing_status,
        "storage": storage_mode(),
    }
