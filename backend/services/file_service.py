from datetime import datetime
from typing import List, Dict
from uuid import uuid4

from api.schemas import (
    FileItem,
    FileType,
    FileStatus,
    ConfirmUploadRequest
)
from services.workspace_service import increment_file_stats


# In-memory storage
_files: Dict[str, FileItem] = {}


def create_file(request: ConfirmUploadRequest) -> FileItem:
    file_id = request.file_id or str(uuid4())

    filename_lower = request.filename.lower()
    if filename_lower.endswith(".pdf"):
        file_type = FileType.PDF
    elif filename_lower.endswith(".docx"):
        file_type = FileType.DOCX
    elif filename_lower.endswith(".geojson"):
        file_type = FileType.GEOJSON
    elif filename_lower.endswith((".shp", ".shapefile")):
        file_type = FileType.SHAPEFILE
    else:
        file_type = FileType.PDF  # fallback

    file_item = FileItem(
        id=file_id,
        name=request.filename,
        type=file_type,
        size=request.file_size,
        date=datetime.now(),
        status=FileStatus.COMPLETED,
        progress=100
    )

    _files[file_id] = file_item

    # Update workspace counters
    increment_file_stats(request.workspace_id, request.file_size)

    return file_item


def list_files(workspace_id: str | None = None) -> List[FileItem]:
    if not workspace_id:
        return list(_files.values())

    # NOTE: currently FileItem doesn't store workspace_id
    # this will be added later with DB
    return list(_files.values())
