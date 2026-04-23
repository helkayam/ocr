from __future__ import annotations

from typing import List

from loguru import logger
from sentence_transformers import SentenceTransformer

MODEL_NAME = "onlplab/alephbert-base"

_model: SentenceTransformer | None = None


def get_model() -> SentenceTransformer:
    """Lazy-load and cache the AlephBERT model (loaded once per process)."""
    global _model
    if _model is None:
        logger.info("Loading embedding model: {}", MODEL_NAME)
        _model = SentenceTransformer(MODEL_NAME)
        logger.info("Embedding model loaded")
    return _model


def embed(texts: List[str]) -> List[List[float]]:
    """Return L2-normalised embeddings for *texts* as plain Python lists."""
    if not texts:
        return []
    vectors = get_model().encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return vectors.tolist()
