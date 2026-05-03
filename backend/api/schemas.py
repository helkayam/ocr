from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class FileType(str, Enum):
    PDF = "pdf"
    DOCX = "docx"
    GEOJSON = "geojson"
    SHAPEFILE = "shapefile"


class FileStatus(str, Enum):
    PENDING = "pending"
    UPLOADING = "uploading"
    COMPLETED = "completed"
    ERROR = "error"


class ValidationResult(BaseModel):
    type: str  # 'success' | 'warning' | 'error'
    message: str


class GeoData(BaseModel):
    type: str
    features: Optional[int] = None
    bounds: Optional[List[float]] = None  # [min_lon, min_lat, max_lon, max_lat]
    crs: Optional[str] = None


class FileMetadata(BaseModel):
    pages: Optional[int] = None
    author: Optional[str] = None
    createdAt: Optional[datetime] = None
    modifiedAt: Optional[datetime] = None
    validationResults: Optional[List[ValidationResult]] = None
    missingComponents: Optional[List[str]] = None
    previewUrl: Optional[str] = None
    geoData: Optional[GeoData] = None


class FileItem(BaseModel):
    id: str
    name: str
    type: FileType
    size: int
    date: datetime
    status: FileStatus
    progress: Optional[int] = None
    error: Optional[str] = None
    metadata: Optional[FileMetadata] = None
    download_url: Optional[str] = None


class Workspace(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    createdAt: datetime
    updatedAt: datetime
    fileCount: int
    totalSize: int


# Request schemas
class WorkspaceCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, description="Workspace name")
    description: Optional[str] = None


class UploadUrlRequest(BaseModel):
    filename: str
    content_type: str
    workspace_id: str
    file_size: int


class ConfirmUploadRequest(BaseModel):
    file_id: str
    workspace_id: str
    filename: str
    file_size: int
    content_type: str


# Response schemas
class UploadUrlResponse(BaseModel):
    upload_url: str
    file_id: str
    expires_in: int  # seconds


class ConfirmUploadResponse(BaseModel):
    file: FileItem
    status: str = "ok"

