from fastapi import APIRouter
from typing import List

from .schemas import SearchRequest, SearchResult
from services.nlp_service import search_chunks

router = APIRouter(prefix="/search", tags=["search"])


@router.post("", response_model=List[SearchResult])
def semantic_search(request: SearchRequest):
    results = search_chunks(request.workspace_id, request.query, request.top_k)
    return [SearchResult(**r) for r in results]
