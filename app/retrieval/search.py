from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from loguru import logger

from app.indexing import db, embedder
from app.models import SearchResult

INDEX_DIR = Path("data/index")


def search(
    query: str,
    top_k: int = 5,
    document_id: Optional[str] = None,
) -> List[SearchResult]:
    """Embed *query* and return the top-k most similar chunks from ChromaDB.

    Args:
        query: The user's natural-language question.
        top_k: Maximum number of chunks to retrieve.
        document_id: Optional filter — restrict results to a single document.

    Returns:
        List of SearchResult ordered by ascending distance (most relevant first).
    """
    logger.debug("Search: query={!r} top_k={} filter={}", query, top_k, document_id)

    vector = embedder.embed([query])[0]
    collection = db.get_collection(INDEX_DIR)

    # ChromaDB raises if n_results > collection size; clamp defensively
    total = collection.count()
    if total == 0:
        logger.warning("Search on empty collection — returning no results")
        return []
    n = min(top_k, total)

    kwargs: dict = dict(
        query_embeddings=[vector],
        n_results=n,
        include=["documents", "metadatas", "distances"],
    )
    if document_id:
        kwargs["where"] = {"document_id": document_id}

    raw = collection.query(**kwargs)

    results: List[SearchResult] = []
    for chunk_id, text, meta, dist in zip(
        raw["ids"][0],
        raw["documents"][0],
        raw["metadatas"][0],
        raw["distances"][0],
    ):
        results.append(
            SearchResult(
                chunk_id=chunk_id,
                document_id=meta["document_id"],
                page_num=meta["page_num"],
                text=text,
                score=dist,
            )
        )

    logger.debug("Search returned {} results", len(results))
    return results
