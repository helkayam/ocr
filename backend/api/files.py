import mimetypes
import os
import tempfile
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request
from fastapi.responses import FileResponse
from loguru import logger
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


def _run_rag_pipeline(file_id: str, workspace_id: str = "__legacy__") -> None:
    """Run the RAG pipeline for an already-ingested document."""
    from app.worker.tasks import process_document

    try:
        process_document(file_id, workspace_id=workspace_id)
    except Exception:
        logger.exception("[rag_bridge] RAG processing failed for {}", file_id)


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
        from app.ingest import manager as ingest_manager

        # Step 1: pull bytes from storage (MinIO or local_storage/)
        try:
            raw = get_file_bytes(object_name)
            logger.info("[rag_bridge] Step 1 — retrieved {} bytes for file_id={}", len(raw), request.file_id)
        except Exception as e:
            logger.error("[rag_bridge] Could not retrieve {}: {}", object_name, e)
            return ConfirmUploadResponse(file=file_item)

        # Step 2: write to a temp file OUTSIDE data/raw/ so ingest_manager can
        # shutil.copy2() it into data/raw/{file_id}.pdf without SameFileError.
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(raw)
            tmp_path = tmp.name
        logger.info("[rag_bridge] Step 2 — file saved to disk: {}", tmp_path)

        # Step 3: run CLI-equivalent ingest (validate → hash → copy to data/raw/ → registry)
        try:
            ingest_manager.ingest(
                tmp_path,
                document_id=request.file_id,
                workspace_id=request.workspace_id,
                file_name=request.filename,
            )
            logger.info("[rag_bridge] Step 3 — registry updated for document_id={}", request.file_id)
        except ValueError as e:
            # Duplicate hash — already registered; still safe to re-process
            logger.warning("[rag_bridge] ingest duplicate for {}: {}", request.file_id, e)
        except Exception as e:
            logger.exception("[rag_bridge] ingest failed for {}", request.file_id)
            Path(tmp_path).unlink(missing_ok=True)
            return ConfirmUploadResponse(file=file_item)

        Path(tmp_path).unlink(missing_ok=True)

        # Step 4: file is on disk and in registry — safe to queue the pipeline
        logger.info("[rag_bridge] Step 4 — task queued for document_id={}", request.file_id)
        background_tasks.add_task(_run_rag_pipeline, request.file_id, request.workspace_id)
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
def local_download(object_name: str, inline: bool = Query(default=False)):
    """Serve a file stored in local_storage/ (used in local mode)."""
    try:
        path = get_local_path(object_name)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid path")
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    mime, _ = mimetypes.guess_type(path.name)
    if inline:
        return FileResponse(str(path), media_type=mime or "application/octet-stream")
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


def _load_rag_registry() -> dict:
    """Load the entire registry once and return a {doc_id: status} map."""
    try:
        import app.registry as rag_registry
        return {r.document_id: r.status.value for r in rag_registry.list_all()}
    except Exception:
        return {}


@router.get("", response_model=List[FileItem])
def list_files(workspace_id: Optional[str] = Query(None)):
    items = file_service.list_files(workspace_id)
    if not items:
        return items
    # Bulk-load registry once — avoids N file reads for N PDF files
    registry_map = _load_rag_registry()
    enriched = []
    for item in items:
        if item.type.value == "pdf":
            rag_stat = registry_map.get(item.id)
            if rag_stat:
                item = item.model_copy(update={"processing_status": rag_stat})
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
