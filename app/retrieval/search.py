from pathlib import Path
from typing import Optional

from loguru import logger

from app.indexing import db, embedder
from app.models import SearchResult
from app.retrieval import reranker

INDEX_DIR = Path("data/index")

_QUERY_PREFIX = "query: "

# Stage-1: how many candidates to pull from ChromaDB before reranking.
# Wide net compensates for bi-encoder imprecision; reranker then picks the best.
_TOP_CANDIDATES = 20


def search(
    query: str,
    top_k: int = 5,
    document_id: Optional[str] = None,
) -> list[SearchResult]:
    """Two-stage retrieval: bi-encoder recall (top-20) → cross-encoder rerank (top-k).

    Stage 1 — Recall:
        Embed *query* with the E5 'query: ' prefix and run ANN search in ChromaDB
        to retrieve _TOP_CANDIDATES candidates.

    Stage 2 — Precision:
        Pass every (query, chunk) pair through the BGE cross-encoder reranker and
        return the top_k results ordered by descending reranker score.

    Args:
        query:       The user's natural-language question.
        top_k:       Number of final chunks to return after reranking (default 5).
        document_id: Optional filter — restrict to a single document.
    """
    logger.debug(
        "Search start: query={!r} top_k={} candidates={} filter={}",
        query, top_k, _TOP_CANDIDATES, document_id,
    )

    # ── Stage 1: bi-encoder retrieval ────────────────────────────────────────
    query_vector = embedder.get_model().encode(
        [_QUERY_PREFIX + query],
        normalize_embeddings=True,
        show_progress_bar=False,
    )[0].tolist()

    collection = db.get_collection(INDEX_DIR)
    total = collection.count()
    if total == 0:
        logger.warning("Search on empty collection — returning no results")
        return []

    n_candidates = min(_TOP_CANDIDATES, total)
    # Always fetch at least top_k even if _TOP_CANDIDATES was reduced
    n_candidates = max(n_candidates, min(top_k, total))

    kwargs: dict = dict(
        query_embeddings=[query_vector],
        n_results=n_candidates,
        include=["documents", "metadatas", "distances"],
    )
    if document_id:
        kwargs["where"] = {"document_id": document_id}

    raw = collection.query(**kwargs)

    candidates: list[SearchResult] = []
    for chunk_id, text, meta, dist in zip(
        raw["ids"][0],
        raw["documents"][0],
        raw["metadatas"][0],
        raw["distances"][0],
    ):
        candidates.append(
            SearchResult(
                chunk_id=chunk_id,
                document_id=meta["document_id"],
                page_num=meta["page_num"],
                text=text,
                score=dist,
            )
        )

    logger.debug("Stage 1 returned {} candidates", len(candidates))

    # ── Stage 2: cross-encoder reranking ─────────────────────────────────────
    results = reranker.rerank(query, candidates, top_k)

    for i, r in enumerate(results, start=1):
        logger.info(
            "\n--- Chunk {} (Page {}, doc={}, reranker_rank={}) ---\n{}\n",
            i, r.page_num, r.document_id, i, r.text,
        )

    logger.debug("Search complete: returned {} results after reranking", len(results))
    return results
