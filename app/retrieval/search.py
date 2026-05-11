import json
import time
from pathlib import Path
from typing import Optional

from loguru import logger

from app.indexing import db, embedder
from app.models import BBox, SearchResult
from app.retrieval import reranker

INDEX_DIR = Path("data/index")

_QUERY_PREFIX   = "query: "
_TOP_CANDIDATES = 20


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_bbox(extra_json: str) -> Optional[BBox]:
    try:
        d = json.loads(extra_json or "{}")
        pw, ph = d.get("page_width", 0), d.get("page_height", 0)
        if pw > 0 and ph > 0 and "y_top" in d and "y_bottom" in d:
            # Normalise inverted coordinates produced by multi-column / RTL OCR quirks
            y_top    = min(d["y_top"],    d["y_bottom"])
            y_bottom = max(d["y_top"],    d["y_bottom"])
            if y_bottom > y_top:  # discard zero-height degenerate boxes
                return BBox(y_top=y_top, y_bottom=y_bottom, page_width=pw, page_height=ph)
    except Exception:
        pass
    return None


def _parent_text(child_text: str, extra_json: str) -> str:
    """Return the parent chunk text from metadata, falling back to child text.

    ChromaDB documents store the small child (embedded) text.  The full
    parent context is in metadata.extra["parent_text"].  Returning the parent
    here means the reranker and LLM always receive rich context while the
    dense index stays tight and precise.
    """
    try:
        return json.loads(extra_json or "{}").get("parent_text") or child_text
    except (json.JSONDecodeError, TypeError):
        return child_text


def _rrf_score(rank: int, k: int = 60) -> float:
    """Standard Reciprocal Rank Fusion score for a result at position *rank* (0-indexed)."""
    return 1.0 / (k + rank + 1)


def _fuse_rrf(dense_ids: list[str], sparse_ids: list[str]) -> list[str]:
    """Merge two ranked ID lists with RRF and return unique IDs sorted by descending score."""
    scores: dict[str, float] = {}
    for rank, cid in enumerate(dense_ids):
        scores[cid] = scores.get(cid, 0.0) + _rrf_score(rank)
    for rank, cid in enumerate(sparse_ids):
        scores[cid] = scores.get(cid, 0.0) + _rrf_score(rank)
    return sorted(scores, key=lambda cid: scores[cid], reverse=True)


# ── Dense-only search (default pipeline) ─────────────────────────────────────

def _build_where(
    workspace_id: Optional[str],
    document_id: Optional[str],
) -> Optional[dict]:
    """Return a ChromaDB ``where`` filter dict, or None for an unfiltered query.

    ``document_id`` is the stricter scope and takes precedence when both are
    supplied — it already implies a specific workspace.
    """
    if document_id:
        return {"document_id": document_id}
    if workspace_id:
        return {"workspace_id": workspace_id}
    return None


def search(
    query: str,
    top_k: int = 5,
    workspace_id: Optional[str] = None,
    document_id: Optional[str] = None,
) -> list[SearchResult]:
    """Two-stage dense retrieval: bi-encoder recall (top-20) → Jina reranker (top-k).

    Pass *workspace_id* to restrict results to a single workspace.  Pass
    *document_id* for an even stricter single-document scope (takes precedence).
    The text in each SearchResult is the *parent* chunk so the LLM always
    receives full semantic context regardless of child chunk size.
    """
    logger.debug(
        "Search start: query={!r} top_k={} candidates={} workspace={} doc_filter={}",
        query, top_k, _TOP_CANDIDATES, workspace_id, document_id,
    )

    _t1 = time.perf_counter()

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

    n_candidates = max(min(_TOP_CANDIDATES, total), min(top_k, total))

    kwargs: dict = dict(
        query_embeddings=[query_vector],
        n_results=n_candidates,
        include=["documents", "metadatas", "distances"],
    )
    where = _build_where(workspace_id, document_id)
    if where:
        kwargs["where"] = where

    raw = collection.query(**kwargs)

    candidates: list[SearchResult] = []
    for chunk_id, child_text, meta, dist in zip(
        raw["ids"][0],
        raw["documents"][0],
        raw["metadatas"][0],
        raw["distances"][0],
    ):
        extra_json = meta.get("extra", "{}")
        candidates.append(
            SearchResult(
                chunk_id=chunk_id,
                document_id=meta["document_id"],
                page_num=meta["page_num"],
                text=_parent_text(child_text, extra_json),
                score=dist,
                bbox=_parse_bbox(extra_json),
            )
        )

    logger.info(
        "Latency - Retrieval (Stage 1): {:.2f}s ({} candidates)",
        time.perf_counter() - _t1, len(candidates),
    )

    logger.info("── Stage 1 candidates before reranking ──────────────────────────────")
    for i, c in enumerate(candidates, start=1):
        logger.info(
            "\n--- Candidate {:>2}/{} (Page {}, doc={}, bi-encoder distance={:.4f}) ---\n{}\n",
            i, len(candidates), c.page_num, c.document_id, c.score, c.text,
        )
    logger.info("─────────────────────────────────────────────────────────────────────")

    results = reranker.rerank(query, candidates, top_k)

    for i, r in enumerate(results, start=1):
        logger.info(
            "\n--- Chunk {} (Page {}, doc={}, reranker_rank={}) ---\n{}\n",
            i, r.page_num, r.document_id, i, r.text,
        )

    logger.debug("Search complete: returned {} results after reranking", len(results))
    return results


# ── Hybrid search (Dense + BM25 → RRF → reranker) ────────────────────────────

def hybrid_search(
    query: str,
    top_k: int = 5,
    workspace_id: Optional[str] = None,
    document_id: Optional[str] = None,
    bm25_candidates: int = _TOP_CANDIDATES,
    dense_candidates: int = _TOP_CANDIDATES,
) -> list[SearchResult]:
    """Hybrid retrieval: Dense + BM25 fused via RRF → Jina reranker (top-k).

    Pass *workspace_id* to restrict both the dense and sparse retrieval stages
    to a single workspace.  *document_id* is the stricter scope and takes
    precedence when both are supplied.

    Stage 1a — Dense recall:
        Embed query with E5 'query: ' prefix, fetch *dense_candidates* from
        ChromaDB (filtered by workspace/document if provided).

    Stage 1b — Sparse recall:
        Tokenise query, fetch *bm25_candidates* from the BM25 corpus
        (filtered by workspace_id if provided).
        Falls back gracefully to dense-only when the BM25 index is empty.

    Stage 1c — RRF fusion:
        Merge both ranked lists with Reciprocal Rank Fusion (k=60).  Chunk
        IDs present only in the BM25 results are fetched from ChromaDB to
        populate their metadata.

    Stage 2 — Precision reranking:
        All fused candidates → Jina reranker → top_k returned.

    BM25 particularly helps for constraint-bearing queries (section IDs,
    dates, named entities) that may not surface from semantic similarity alone.
    """
    logger.debug(
        "Hybrid search start: query={!r} top_k={} dense={} bm25={} workspace={} doc_filter={}",
        query, top_k, dense_candidates, bm25_candidates, workspace_id, document_id,
    )
    _t0 = time.perf_counter()

    collection = db.get_collection(INDEX_DIR)
    total      = collection.count()
    if total == 0:
        logger.warning("Hybrid search on empty collection — returning no results")
        return []

    # ── Stage 1a: dense retrieval ─────────────────────────────────────────
    query_vector = embedder.get_model().encode(
        [_QUERY_PREFIX + query],
        normalize_embeddings=True,
        show_progress_bar=False,
    )[0].tolist()

    n_dense = max(min(dense_candidates, total), min(top_k, total))
    dense_kwargs: dict = dict(
        query_embeddings=[query_vector],
        n_results=n_dense,
        include=["documents", "metadatas", "distances"],
    )
    where = _build_where(workspace_id, document_id)
    if where:
        dense_kwargs["where"] = where

    raw_dense  = collection.query(**dense_kwargs)
    dense_ids  = raw_dense["ids"][0]

    # chunk_id → SearchResult for quick lookup during merge
    dense_map: dict[str, SearchResult] = {}
    for chunk_id, child_text, meta, dist in zip(
        raw_dense["ids"][0],
        raw_dense["documents"][0],
        raw_dense["metadatas"][0],
        raw_dense["distances"][0],
    ):
        extra_json = meta.get("extra", "{}")
        dense_map[chunk_id] = SearchResult(
            chunk_id=chunk_id,
            document_id=meta["document_id"],
            page_num=meta["page_num"],
            text=_parent_text(child_text, extra_json),
            score=dist,
            bbox=_parse_bbox(extra_json),
        )

    logger.debug("Dense stage: {} candidates in {:.2f}s", len(dense_ids), time.perf_counter() - _t0)

    # ── Stage 1b: BM25 sparse retrieval ──────────────────────────────────
    # Use workspace_id filter (document_id supersedes it, but BM25 doesn't
    # have per-document scope; fall back to workspace filter in that case).
    bm25_workspace = workspace_id if not document_id else None
    _t1        = time.perf_counter()
    bm25_store = db.get_bm25_store(INDEX_DIR)
    bm25_hits  = bm25_store.search(query, top_k=bm25_candidates, workspace_id=bm25_workspace)
    sparse_ids = [cid for cid, _ in bm25_hits]
    logger.debug("BM25 stage: {} candidates in {:.2f}s", len(sparse_ids), time.perf_counter() - _t1)

    # ── Stage 1c: RRF fusion ──────────────────────────────────────────────
    fused_ids = _fuse_rrf(dense_ids, sparse_ids)

    # Fetch ChromaDB metadata for any ID that only appeared in BM25
    bm25_only = [cid for cid in fused_ids if cid not in dense_map]
    if bm25_only:
        fetched = collection.get(
            ids=bm25_only,
            include=["documents", "metadatas"],
        )
        for chunk_id, child_text, meta in zip(
            fetched["ids"], fetched["documents"], fetched["metadatas"]
        ):
            extra_json = meta.get("extra", "{}")
            dense_map[chunk_id] = SearchResult(
                chunk_id=chunk_id,
                document_id=meta["document_id"],
                page_num=meta["page_num"],
                text=_parent_text(child_text, extra_json),
                score=0.0,
                bbox=_parse_bbox(extra_json),
            )

    candidates: list[SearchResult] = [
        dense_map[cid] for cid in fused_ids if cid in dense_map
    ]

    logger.info(
        "Latency - Hybrid Retrieval (Stage 1): {:.2f}s ({} fused candidates)",
        time.perf_counter() - _t0, len(candidates),
    )

    # ── Stage 2: Jina reranker ────────────────────────────────────────────
    results = reranker.rerank(query, candidates, top_k)
    logger.debug("Hybrid search complete: returned {} results after reranking", len(results))
    return results
