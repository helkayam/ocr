from typing import Optional

from loguru import logger
from sentence_transformers import SentenceTransformer

MODEL_NAME = "intfloat/multilingual-e5-large"

_PASSAGE_PREFIX = "passage: "

_model: Optional[SentenceTransformer] = None


def get_model() -> SentenceTransformer:
    """Lazy-load and cache the multilingual-e5-large model (loaded once per process)."""
    global _model
    if _model is None:
        logger.info("Loading embedding model: {}", MODEL_NAME)
        _model = SentenceTransformer(MODEL_NAME)
        logger.info("Embedding model loaded")
    return _model


def get_embedding_dim() -> int:
    """Return the output dimension of the current embedding model."""
    model = get_model()
    # get_embedding_dimension() is the current API; fall back to the deprecated
    # get_sentence_embedding_dimension() for older sentence-transformers versions.
    getter = getattr(model, "get_embedding_dimension", None) or getattr(
        model, "get_sentence_embedding_dimension"
    )
    return getter()


def embed(texts: list[str]) -> list[list[float]]:
    """Return L2-normalised passage embeddings for *texts* as plain Python lists.

    Prepends the E5 'passage: ' prefix required for correct asymmetric retrieval.
    Use search.py's query embedding (which prepends 'query: ') for queries.
    """
    if not texts:
        return []
    prefixed = [_PASSAGE_PREFIX + t for t in texts]
    vectors = get_model().encode(prefixed, normalize_embeddings=True, show_progress_bar=False)
    return vectors.tolist()
