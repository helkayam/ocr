import os
import time
from typing import Optional

import requests
from dotenv import load_dotenv
from loguru import logger

from app.models import SearchResult

load_dotenv()

JINA_MODEL = "jina-reranker-v2-base-multilingual"
_JINA_URL = "https://api.jina.ai/v1/rerank"
_REQUEST_TIMEOUT = 30  # seconds


def rerank(query: str, candidates: list[SearchResult], top_k: int) -> list[SearchResult]:
    """Rerank candidates using the Jina AI API.

    Sends all candidates in a single batch request and returns the top_k
    results sorted by descending relevance score.

    Falls back to the original bi-encoder order if the API call fails,
    so the pipeline always returns something rather than crashing.
    """
    if not candidates:
        return []

    api_key = os.getenv("JINA_API_KEY")
    if not api_key:
        logger.warning("JINA_API_KEY not set — returning candidates in original order")
        return candidates[:top_k]

    documents = [r.text for r in candidates]

    payload = {
        "model": JINA_MODEL,
        "query": query,
        "documents": documents,
        "top_n": top_k,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    _t1 = time.perf_counter()
    try:
        response = requests.post(
            _JINA_URL,
            json=payload,
            headers=headers,
            timeout=_REQUEST_TIMEOUT,
        )
        response.raise_for_status()
    except requests.exceptions.Timeout:
        logger.error(
            "Jina rerank API timed out after {}s — falling back to bi-encoder order",
            _REQUEST_TIMEOUT,
        )
        return candidates[:top_k]
    except requests.exceptions.RequestException as exc:
        logger.error("Jina rerank API error: {} — falling back to bi-encoder order", exc)
        return candidates[:top_k]

    duration = time.perf_counter() - _t1

    try:
        results = response.json()["results"]
    except (KeyError, ValueError) as exc:
        logger.error("Jina rerank: unexpected response shape: {} — falling back", exc)
        return candidates[:top_k]

    # results is already sorted by relevance_score descending by the API.
    # Each entry has an 'index' field pointing back to the original candidates list.
    reranked: list[SearchResult] = []
    for entry in results:
        original_index: int = entry["index"]
        score: float = entry["relevance_score"]
        result = candidates[original_index]
        result.score = score
        reranked.append(result)

    logger.info(
        "Latency - Reranking (Stage 2): {:.2f}s ({} candidates → top {} | Jina API)",
        duration,
        len(candidates),
        top_k,
    )
    if reranked:
        logger.debug(
            "Reranker scores — best: {:.3f}  worst: {:.3f}",
            reranked[0].score,
            reranked[-1].score,
        )

    return reranked
