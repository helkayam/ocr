"""
Storage service — MinIO (S3-compatible) with automatic local-disk fallback.

If MinIO is unreachable on startup, all file I/O is redirected to:
    backend/local_storage/<workspace_id>/<file_id>/<filename>

Upload flow in local mode:
  1. generate_presigned_upload_url() returns http://localhost:8000/files/local-upload/<object>
  2. The frontend PUT-s the raw binary to that endpoint
  3. api/files.py::local_upload() calls save_file_local() to persist it
"""

import os
from datetime import timedelta
from pathlib import Path

# ─── Configuration ────────────────────────────────────────────────────────────

MINIO_ENDPOINT  = os.getenv("MINIO_ENDPOINT",  "localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadmin")
MINIO_BUCKET    = os.getenv("MINIO_BUCKET",    "protocol-files")
PUBLIC_API_URL  = os.getenv("PUBLIC_API_URL",  "http://localhost:8000")

_BASE = Path(__file__).resolve().parent.parent   # backend/
LOCAL_STORAGE   = _BASE / "local_storage"

_use_local: bool = False


# ─── Internal helpers ─────────────────────────────────────────────────────────

def _client():
    from minio import Minio
    return Minio(
        MINIO_ENDPOINT,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=False,
    )


def _safe_local_path(object_name: str) -> Path:
    """Resolve path and guard against directory traversal."""
    target = (LOCAL_STORAGE / object_name).resolve()
    if not str(target).startswith(str(LOCAL_STORAGE.resolve())):
        raise ValueError("Rejected: path traversal attempt")
    return target


# ─── Public API ───────────────────────────────────────────────────────────────

def storage_mode() -> str:
    return "local" if _use_local else "minio"


def ensure_bucket() -> bool:
    """
    Try to connect to MinIO and ensure the bucket exists.
    On failure, switch to local-disk mode silently.
    """
    global _use_local
    try:
        c = _client()
        if not c.bucket_exists(MINIO_BUCKET):
            c.make_bucket(MINIO_BUCKET)
        print(f"Storage: MinIO bucket '{MINIO_BUCKET}' ready")
        _use_local = False
        return True
    except Exception as e:
        print(f"Storage: MinIO unavailable ({e}). Using local_storage/")
        LOCAL_STORAGE.mkdir(parents=True, exist_ok=True)
        _use_local = True
        return False


def generate_download_url(object_name: str) -> str:
    """Return a URL that delivers the object bytes to the browser."""
    if _use_local:
        return f"{PUBLIC_API_URL}/files/local-download/{object_name}"
    return _client().presigned_get_object(
        MINIO_BUCKET, object_name, expires=timedelta(seconds=3600)
    )


def generate_presigned_upload_url(object_name: str, expires: int = 3600) -> str:
    if _use_local:
        return f"{PUBLIC_API_URL}/files/local-upload/{object_name}"
    return _client().presigned_put_object(
        MINIO_BUCKET, object_name, expires=timedelta(seconds=expires)
    )


def save_file_local(object_name: str, data: bytes) -> None:
    """Write bytes to local_storage. Called from the local-upload endpoint."""
    path = _safe_local_path(object_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def get_file_bytes(object_name: str) -> bytes:
    if _use_local:
        return _safe_local_path(object_name).read_bytes()
    c = _client()
    resp = c.get_object(MINIO_BUCKET, object_name)
    try:
        return resp.read()
    finally:
        resp.close()
        resp.release_conn()


def get_local_path(object_name: str) -> Path:
    """Return the absolute Path for a local-mode object (for FileResponse)."""
    return _safe_local_path(object_name)


def delete_object(object_name: str) -> None:
    """Delete an object from MinIO or local storage (best-effort)."""
    if _use_local:
        try:
            _safe_local_path(object_name).unlink(missing_ok=True)
        except Exception as e:
            print(f"Storage: local delete failed for {object_name}: {e}")
    else:
        try:
            _client().remove_object(MINIO_BUCKET, object_name)
        except Exception as e:
            print(f"Storage: MinIO delete failed for {object_name}: {e}")
