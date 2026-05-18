from datetime import datetime, timezone
from typing import List, Optional, Dict
from uuid import uuid4

from api.schemas import FileItem, FileType, FileStatus, ConfirmUploadRequest
from db import get_db, db_available
from services.storage_service import generate_download_url, generate_preview_url

# In-memory fallback
_files_mem: Dict[str, dict] = {}


def _file_type(filename: str) -> FileType:
    fname = filename.lower()
    if fname.endswith(".pdf"):
        return FileType.PDF
    if fname.endswith(".docx"):
        return FileType.DOCX
    if fname.endswith((".geojson", ".json")):
        return FileType.GEOJSON
    return FileType.PDF


def create_file(request: ConfirmUploadRequest, object_name: str = "") -> FileItem:
    file_id = request.file_id or str(uuid4())
    ftype = _file_type(request.filename)
    now = datetime.utcnow()

    if not object_name:
        object_name = f"{request.workspace_id}/{file_id}/{request.filename}"

    # Only PDFs go through the RAG pipeline; non-PDFs have no processing status.
    initial_ps = "pending" if ftype == FileType.PDF else None

    if db_available():
        with get_db() as cur:
            cur.execute(
                """
                INSERT INTO files
                    (file_id, workspace_id, filename, file_type, content_type,
                     file_size, object_name, status, processing_status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'completed', %s)
                ON CONFLICT (file_id) DO UPDATE
                    SET status = 'completed', processing_status = %s
                """,
                (
                    file_id, request.workspace_id, request.filename,
                    ftype.value, request.content_type,
                    request.file_size, object_name,
                    initial_ps, initial_ps,
                ),
            )
            cur.execute(
                """
                UPDATE workspaces
                SET file_count = file_count + 1,
                    total_size = total_size + %s,
                    updated_at  = CURRENT_TIMESTAMP
                WHERE workspace_id = %s
                """,
                (request.file_size, request.workspace_id),
            )
    else:
        _files_mem[file_id] = dict(
            file_id=file_id,
            workspace_id=request.workspace_id,
            filename=request.filename,
            file_type=ftype.value,
            content_type=request.content_type,
            file_size=request.file_size,
            object_name=object_name,
            status="completed",
            processing_status=initial_ps,
            created_at=now,
        )

    return FileItem(
        id=file_id,
        name=request.filename,
        type=ftype,
        size=request.file_size,
        date=now,
        status=FileStatus.COMPLETED,
        progress=100,
        download_url=generate_download_url(object_name),
        preview_url=generate_preview_url(object_name),
    )


def list_files(workspace_id: Optional[str] = None) -> List[FileItem]:
    if db_available():
        with get_db() as cur:
            if workspace_id:
                cur.execute(
                    "SELECT * FROM files WHERE workspace_id = %s ORDER BY created_at DESC",
                    (workspace_id,),
                )
            else:
                cur.execute("SELECT * FROM files ORDER BY created_at DESC")
            rows = cur.fetchall()
        return [_row_to_file_item(dict(r)) for r in rows]

    items = list(_files_mem.values())
    if workspace_id:
        items = [f for f in items if f["workspace_id"] == workspace_id]
    return [_row_to_file_item(f) for f in items]


def get_file(file_id: str) -> Optional[dict]:
    if db_available():
        with get_db() as cur:
            cur.execute("SELECT * FROM files WHERE file_id = %s", (file_id,))
            row = cur.fetchone()
        return dict(row) if row else None
    return _files_mem.get(file_id)


def delete_file(file_id: str) -> None:
    """Remove SQL rows only (files + document_chunks). Use deep_delete_file for full teardown."""
    if db_available():
        with get_db() as cur:
            cur.execute("DELETE FROM document_chunks WHERE file_id = %s", (file_id,))
            cur.execute("DELETE FROM files WHERE file_id = %s", (file_id,))
    else:
        _files_mem.pop(file_id, None)


def deep_delete_file(file_rec: dict) -> None:
    """Full teardown for one file: RAG vectors + disk artifacts + geo entities + SQL + object storage.

    Accepts the file's DB row as a dict (keys: file_id, file_type, object_name).
    Best-effort on each step — logs errors but never raises, so callers (e.g.
    workspace deletion) remain atomic across many files.
    """
    from loguru import logger
    from services.storage_service import delete_object

    file_id: str = file_rec.get("file_id", "")
    object_name: Optional[str] = file_rec.get("object_name")

    # 1. RAG pipeline: ChromaDB vectors + data/raw|ocr|chunks on disk + registry
    if str(file_rec.get("file_type", "")).lower() == "pdf":
        try:
            from app import pipeline
            import app.registry as rag_registry
            if rag_registry.get(file_id):
                pipeline.delete_pipeline(file_id)
                logger.info("[deep_delete] RAG delete complete for {}", file_id)
            else:
                logger.info("[deep_delete] {} not in RAG registry — skipping pipeline delete", file_id)
        except KeyError:
            pass  # already removed from registry
        except Exception as exc:
            logger.error("[deep_delete] RAG delete failed for {}: {}", file_id, exc)

    # 2. Geo layers + emergency geo_features linked to this file
    try:
        from services.geo_service import delete_geo_entities_for_file
        delete_geo_entities_for_file(file_id)
    except Exception as exc:
        logger.error("[deep_delete] Geo entity delete failed for {}: {}", file_id, exc)

    # 3. SQL rows (files + document_chunks)
    try:
        delete_file(file_id)
    except Exception as exc:
        logger.error("[deep_delete] SQL delete failed for {}: {}", file_id, exc)

    # 4. Object storage (best-effort — never block on storage errors)
    if object_name:
        delete_object(object_name)


def _row_to_file_item(d: dict) -> FileItem:
    obj = d.get("object_name") or ""
    return FileItem(
        id=d["file_id"],
        name=d["filename"],
        type=FileType(d["file_type"]),
        size=d.get("file_size") or 0,
        date=d.get("created_at") or datetime.utcnow(),
        status=FileStatus.COMPLETED,
        progress=100,
        download_url=generate_download_url(obj) if obj else None,
        preview_url=generate_preview_url(obj) if obj else None,
        processing_status=d.get("processing_status"),
    )
