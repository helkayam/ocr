from fastapi import APIRouter, Query
from typing import Optional, List
from datetime import datetime
from .schemas import (
    FileItem,
    FileType,
    FileStatus,
    UploadUrlRequest,
    UploadUrlResponse,
    ConfirmUploadRequest,
    ConfirmUploadResponse
)
from services.storage_service import generate_presigned_upload_url
import uuid
import os
import psycopg2



router = APIRouter(prefix="/files", tags=["files"])


@router.post("/upload-url", response_model=UploadUrlResponse)
def get_upload_url(request: UploadUrlRequest):
    file_id = uuid.uuid4()
    object_name = f"{request.workspace_id}/{file_id}/{request.filename}"

    upload_url = generate_presigned_upload_url(object_name)

    db_url = os.getenv("DATABASE_URL")
    if db_url:
        conn = psycopg2.connect(db_url)
        conn.autocommit = True
        cur = conn.cursor()

        # אופציונלי: להבטיח שה-workspace קיים (לא חובה אבל נחמד)
        cur.execute(
            "INSERT INTO workspaces (workspace_id) VALUES (%s) ON CONFLICT DO NOTHING",
            (request.workspace_id,)
        )

        cur.execute(
            """
            INSERT INTO files (file_id, workspace_id, filename, content_type, file_size, object_name)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (str(file_id), request.workspace_id, request.filename, request.content_type, request.file_size, object_name)
        )

        cur.close()
        conn.close()




    return UploadUrlResponse(
    upload_url=upload_url,
    file_id=str(file_id),
    expires_in=3600
)



@router.post("/confirm-upload", response_model=ConfirmUploadResponse)
def confirm_upload(request: ConfirmUploadRequest):
    """Confirm upload status"""
    # Stub implementation - no persistence yet
    # Determine file type from filename extension
    filename_lower = request.filename.lower()
    if filename_lower.endswith('.pdf'):
        file_type = FileType.PDF
    elif filename_lower.endswith('.docx'):
        file_type = FileType.DOCX
    elif filename_lower.endswith('.geojson'):
        file_type = FileType.GEOJSON
    elif filename_lower.endswith(('.shp', '.shapefile')):
        file_type = FileType.SHAPEFILE
    else:
        file_type = FileType.PDF  # Default fallback
    
    file_item = FileItem(
        id=request.file_id,
        name=request.filename,
        type=file_type,
        size=request.file_size,
        date=datetime.now(),
        status=FileStatus.COMPLETED
    )
    return ConfirmUploadResponse(file=file_item)


@router.get("", response_model=List[FileItem])
def list_files(workspace_id: Optional[str] = Query(None, description="Filter by workspace ID")):
    """List files"""
    # Stub implementation - no persistence yet
    return []

