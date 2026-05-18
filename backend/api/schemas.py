from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class FileType(str, Enum):
    PDF = "pdf"
    DOCX = "docx"
    GEOJSON = "geojson"


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
    preview_url: Optional[str] = None
    processing_status: Optional[str] = None


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
    geo_category: Optional[str] = None  # "cameras" | "shelters" | "buildings" — GeoJSON only


# Response schemas
class UploadUrlResponse(BaseModel):
    upload_url: str
    file_id: str
    expires_in: int  # seconds


class ConfirmUploadResponse(BaseModel):
    file: FileItem
    status: str = "ok"


# ── NLP / semantic search schemas ────────────────────────────────────────────

class SearchRequest(BaseModel):
    workspace_id: str
    query: str
    top_k: int = 5


class SearchResult(BaseModel):
    chunk_id: str
    file_id: str
    filename: str
    content: str
    score: float


# ── RAG pipeline schemas ──────────────────────────────────────────────────────

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
    workspace_id: Optional[str] = Field(default=None)


class BBoxOut(BaseModel):
    y_top: float
    y_bottom: float
    page_width: float
    page_height: float


class CitedSourceOut(BaseModel):
    document_id: str
    file_name: str
    page_num: int
    chunk_id: str
    text_snippet: str
    bbox: Optional[BBoxOut] = None


class QueryResponse(BaseModel):
    query: str
    answer: str
    sources: List[CitedSourceOut] = []


# ── Emergency simulation schemas ──────────────────────────────────────────────

class GeoFeatureCreate(BaseModel):
    workspace_id: str
    feature_type: str = Field(..., description="shelter|exit|muster_point|extinguisher|assembly")
    label: str
    lat: float
    lng: float
    floor: Optional[str] = None
    metadata: Optional[dict] = None


class GeoFeatureOut(BaseModel):
    feature_id: str
    workspace_id: str
    feature_type: str
    label: str
    lat: float
    lng: float
    floor: Optional[str] = None
    metadata: Optional[dict] = None


class SensorLocationUpdate(BaseModel):
    lat: float
    lng: float


class EmergencySimRequest(BaseModel):
    workspace_id: str
    sensor_id: str
    alert_level: str = Field(default="high")
    override_query: Optional[str] = None
    origin_lat: Optional[float] = None   # user-selected evacuation origin
    origin_lng: Optional[float] = None


class IntentOut(BaseModel):
    action: str
    target_type: str
    urgency: str


class EmergencySimResponse(BaseModel):
    event_id: str
    sensor: dict
    alert_level: str
    rag_query: str
    rag_answer: str
    rag_sources: List[dict] = []
    intent: IntentOut
    nearest_feature: Optional[dict] = None
    directive: str


class EmergencyEventOut(BaseModel):
    event_id: str
    workspace_id: str
    sensor_name: Optional[str] = None
    sensor_type: Optional[str] = None
    alert_level: str = "high"
    intent_action: Optional[str] = None
    intent_target: Optional[str] = None
    intent_urgency: Optional[str] = None
    nearest_feature_label: Optional[str] = None
    nearest_distance_m: Optional[float] = None
    directive: Optional[str] = None
    status: str = "simulated"
    created_at: Optional[datetime] = None

