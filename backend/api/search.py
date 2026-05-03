from fastapi import APIRouter
from pydantic import BaseModel
from typing import List

from services.nlp_service import search_chunks

router = APIRouter(prefix="/search", tags=["search"])


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


@router.post("", response_model=List[SearchResult])
def semantic_search(request: SearchRequest):
    results = search_chunks(request.workspace_id, request.query, request.top_k)
    return [SearchResult(**r) for r in results]
