from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class DocumentStatus(str, Enum):
    pending = "pending"
    ocr_completed = "ocr_completed"
    chunked = "chunked"
    indexed = "indexed"
    error = "error"


class DocumentRecord(BaseModel):
    document_id: str
    file_name: str
    status: DocumentStatus
    created_at: datetime
    file_hash: str
    workspace_id: str = "__legacy__"


# ---------------------------------------------------------------------------
# OCR output schema — mirrors OCRService.process_file() JSON structure
# ---------------------------------------------------------------------------

class PageStats(BaseModel):
    median_font_size: float
    max_font_size: float


class Block(BaseModel):
    text: str
    type: str  # "text" | "table" | "header"
    y_top: float
    y_bottom: float
    font_size: float
    ratio_to_body: float
    line_count: int


class OCRPage(BaseModel):
    page_num: int
    stats: PageStats
    blocks: List[Block]
    page_width: float = 0.0
    page_height: float = 0.0


class OCRResult(BaseModel):
    file_name: str
    pages: List[OCRPage]


# ---------------------------------------------------------------------------
# Chunking schema
# ---------------------------------------------------------------------------

class ChunkMetadata(BaseModel):
    page_num: int
    block_id: int
    is_header: bool
    block_type: str
    extra: Dict[str, Any] = Field(default_factory=dict)


class Chunk(BaseModel):
    chunk_id: str
    document_id: str = ""   # populated from root envelope at load time; excluded from disk
    page: int
    text: str
    metadata: ChunkMetadata


# ---------------------------------------------------------------------------
# Retrieval & RAG schema
# ---------------------------------------------------------------------------

class BBox(BaseModel):
    y_top: float
    y_bottom: float
    page_width: float
    page_height: float


class SearchResult(BaseModel):
    chunk_id: str
    document_id: str
    page_num: int
    text: str
    score: float  # lower = more similar (ChromaDB L2 / cosine distance)
    bbox: Optional[BBox] = None


class CitedSource(BaseModel):
    document_id: str
    file_name: str = ""
    page_num: int
    chunk_id: str = ""
    text_snippet: str = ""
    bbox: Optional[BBox] = None


class RAGResponse(BaseModel):
    query: str
    answer: str
    sources: List[CitedSource]


# ---------------------------------------------------------------------------
# Evaluation schema (Phase 10)
# ---------------------------------------------------------------------------

class GoldenQuestion(BaseModel):
    question_id: str
    document_id: str
    workspace_id: str
    query: str
    expected_answer: str
    expected_pages: List[int]
    question_type: str  # "explicit" | "constraint" | "multi-hop" | "negative"


class EvalResult(BaseModel):
    question_id: str
    query: str
    question_type: str
    document_id: str
    workspace_id: str
    recall: float           # 0.0 or 1.0
    accuracy: float         # 0.0 or 1.0
    accuracy_reason: str = ""
    generated_answer: str = ""
    returned_pages: List[int] = Field(default_factory=list)
