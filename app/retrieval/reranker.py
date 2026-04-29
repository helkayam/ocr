from typing import Optional

from loguru import logger
from sentence_transformers import CrossEncoder

from app.models import SearchResult

MODEL_NAME = "BAAI/bge-reranker-v2-m3"

_model: Optional[CrossEncoder] = None


def get_model() -> CrossEncoder:
    """Lazy-load and cache the BGE reranker (loaded once per process)."""
    global _model
    if _model is None:
        logger.info("Loading reranker model: {}", MODEL_NAME)
        _model = CrossEncoder(MODEL_NAME)
        logger.info("Reranker model loaded")
    return _model


def rerank(query: str, candidates: list[SearchResult], top_k: int) -> list[SearchResult]:
    """Score each (query, chunk) pair and return the top_k by descending relevance.

    BGE reranker outputs a float score per pair; higher = more relevant.
    The input candidates come from the bi-encoder's wide-net retrieval (e.g. top-20).
    """
    if not candidates:
        return []

    model = get_model()
    pairs = [(query, r.text) for r in candidates]
    scores: list[float] = model.predict(pairs).tolist()

    scored = sorted(zip(scores, candidates), key=lambda x: x[0], reverse=True)
    top = scored[:top_k]

    logger.debug(
        "Reranker: {} candidates → top {} | scores [{:.3f} … {:.3f}]",
        len(candidates),
        top_k,
        scored[0][0],
        scored[-1][0],
    )
    return [r for _, r in top]
