import json
from pathlib import Path
from typing import Optional

from loguru import logger

try:
    from rank_bm25 import BM25Okapi
except ImportError as _exc:
    raise ImportError(
        "rank_bm25 is required. Add it to requirements.txt and run: pip install rank_bm25"
    ) from _exc

_CORPUS_FILE = "bm25_corpus.json"


def _tokenize(text: str) -> list[str]:
    """Whitespace tokenizer that lowercases for BM25 term matching.

    Hebrew words are space-separated so a simple split is both fast and
    correct.  Lowercasing is a no-op for Hebrew but normalises Latin tokens
    (e.g. section IDs like 'Section3' and 'section3' collapse to the same
    term).
    """
    return text.lower().split()


class BM25Store:
    """Persistent BM25 sparse index over chunk texts.

    The corpus is stored as a plain JSON file at ``index_dir/bm25_corpus.json``.
    The BM25Okapi in-memory object is rebuilt from that file on every
    instantiation — this is intentional: BM25Okapi is not safely picklable
    across library upgrades, and for typical corpus sizes the rebuild cost is
    under a second.

    All public methods are safe to call on an empty or non-existent store.
    The ``add_chunks`` method performs a single rebuild after inserting all
    new entries, so callers should batch inserts rather than calling it
    per-chunk.
    """

    def __init__(self, index_dir: Path) -> None:
        self._dir          = Path(index_dir)
        self._corpus_path  = self._dir / _CORPUS_FILE
        # list[{"chunk_id": str, "document_id": str, "workspace_id": str, "text": str}]
        self._corpus: list[dict] = []
        self._bm25: Optional[BM25Okapi] = None
        self._load()

    # ── persistence ──────────────────────────────────────────────────────────

    def _load(self) -> None:
        if not self._corpus_path.exists():
            return
        self._corpus = json.loads(self._corpus_path.read_text(encoding="utf-8"))
        self._rebuild()
        logger.debug("BM25: loaded {} entries from corpus", len(self._corpus))

    def _save(self) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        self._corpus_path.write_text(
            json.dumps(self._corpus, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _rebuild(self) -> None:
        """Rebuild the in-memory BM25Okapi index from the current corpus list."""
        if not self._corpus:
            self._bm25 = None
            return
        self._bm25 = BM25Okapi([_tokenize(d["text"]) for d in self._corpus])

    # ── public API ───────────────────────────────────────────────────────────

    def add_chunks(self, entries: list[dict]) -> None:
        """Upsert *entries* into the index (idempotent on chunk_id).

        Each entry must be a dict with keys ``chunk_id``, ``document_id``,
        and ``text``.  Existing entries with the same chunk_id are replaced.
        A single corpus rebuild happens after all entries are inserted.
        """
        new_ids = {e["chunk_id"] for e in entries}
        self._corpus = [c for c in self._corpus if c["chunk_id"] not in new_ids]
        self._corpus.extend(entries)
        self._rebuild()
        self._save()
        logger.debug(
            "BM25: upserted {} entries — corpus total: {}",
            len(entries), len(self._corpus),
        )

    def delete_document(self, document_id: str) -> int:
        """Remove all chunks belonging to *document_id*.  Returns count removed."""
        before       = len(self._corpus)
        self._corpus = [c for c in self._corpus if c["document_id"] != document_id]
        removed      = before - len(self._corpus)
        if removed:
            self._rebuild()
            self._save()
        logger.info("BM25: removed {} entries for document_id={}", removed, document_id)
        return removed

    def search(
        self,
        query: str,
        top_k: int = 20,
        workspace_id: Optional[str] = None,
    ) -> list[tuple[str, float]]:
        """Return up to *top_k* ``(chunk_id, bm25_score)`` pairs, descending by score.

        When *workspace_id* is provided only entries belonging to that workspace
        are considered.  Legacy entries without a ``workspace_id`` key are
        treated as ``"__legacy__"`` for backwards compatibility.

        Returns an empty list when the index is empty.
        """
        if self._bm25 is None or not self._corpus:
            logger.debug("BM25: search on empty index — returning []")
            return []
        scores = self._bm25.get_scores(_tokenize(query))
        pairs = list(zip([c["chunk_id"] for c in self._corpus], scores.tolist()))
        if workspace_id is not None:
            ws_map = {c["chunk_id"]: c.get("workspace_id", "__legacy__") for c in self._corpus}
            pairs = [(cid, sc) for cid, sc in pairs if ws_map.get(cid) == workspace_id]
        return sorted(pairs, key=lambda x: x[1], reverse=True)[:top_k]

    def get_text(self, chunk_id: str) -> Optional[str]:
        """Return the stored text for *chunk_id*, or None if not found."""
        for entry in self._corpus:
            if entry["chunk_id"] == chunk_id:
                return entry["text"]
        return None

    def reset(self) -> None:
        """Erase all data from memory and disk."""
        self._corpus = []
        self._bm25   = None
        if self._corpus_path.exists():
            self._corpus_path.unlink()
        logger.info("BM25: index reset")

    @property
    def count(self) -> int:
        return len(self._corpus)
