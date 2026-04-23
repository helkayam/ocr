"""Pydantic models that define the API's public contract.

These are deliberately kept separate from the internal domain models in
``app/models.py`` so that the API surface can evolve independently.
"""
from __future__ import annotations

from datetime import datetime
from typing import List

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Shared sub-objects
# ---------------------------------------------------------------------------

class CitedSourceOut(BaseModel):
    document_id: str
    page_num: int


# ---------------------------------------------------------------------------
# Document endpoints
# ---------------------------------------------------------------------------

class DocumentOut(BaseModel):
    """Mirrors DocumentRecord; used in GET /documents/ and POST /documents/."""
    document_id: str
    file_name: str
    status: str
    created_at: datetime
    file_hash: str


class IngestResponse(BaseModel):
    """Response body for a successful POST /documents/."""
    document_id: str
    file_name: str
    status: str


class ReindexResponse(BaseModel):
    """Response body for POST /documents/{doc_id}/reindex."""
    document_id: str
    chunks_indexed: int


# ---------------------------------------------------------------------------
# Query endpoint
# ---------------------------------------------------------------------------

class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Natural-language question in Hebrew or English.")
    top_k: int = Field(default=5, ge=1, le=50, description="Number of context chunks to retrieve.")


class QueryResponse(BaseModel):
    query: str
    answer: str
    sources: List[CitedSourceOut]
