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


class OCRResult(BaseModel):
    file_name: str
    pages: List[OCRPage]


# ---------------------------------------------------------------------------
# Chunking schema
# ---------------------------------------------------------------------------

class ChunkMetadata(BaseModel):
    document_id: str
    page_num: int
    block_id: int
    is_header: bool
    block_type: str
    extra: Dict[str, Any] = Field(default_factory=dict)


class Chunk(BaseModel):
    chunk_id: str
    document_id: str
    page: int
    text: str
    metadata: ChunkMetadata


# ---------------------------------------------------------------------------
# Retrieval & RAG schema
# ---------------------------------------------------------------------------

class SearchResult(BaseModel):
    chunk_id: str
    document_id: str
    page_num: int
    text: str
    score: float  # lower = more similar (ChromaDB L2 / cosine distance)


class CitedSource(BaseModel):
    document_id: str
    page_num: int


class RAGResponse(BaseModel):
    query: str
    answer: str
    sources: List[CitedSource]


# ---------------------------------------------------------------------------
# Evaluation schema (Phase 10)
# ---------------------------------------------------------------------------

class GoldenQuestion(BaseModel):
    query: str
    query_type: str = "in_context"  # "in_context" | "out_of_context"
    expected_doc_id: Optional[str] = None
    expected_page: Optional[int] = None


class EvalResult(BaseModel):
    query: str
    query_type: str
    recall_hit: Optional[bool] = None       # None when not applicable
    faithfulness_pass: Optional[bool] = None  # None when not applicable
    answer: str = ""
