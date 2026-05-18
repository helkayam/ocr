import sys
import threading
from pathlib import Path
from typing import Optional

try:
    import pysqlite3
    sys.modules["sqlite3"] = pysqlite3
except ImportError:
    pass

import chromadb

from app.indexing.bm25_store import BM25Store

INDEX_DIR       = Path("data/index")
COLLECTION_NAME = "documents"

# One PersistentClient per (index_dir) path — shared across all threads.
# Creating multiple clients on the same path simultaneously causes ChromaDB's
# internal SQLite to raise "database is locked" under concurrent writes.
_client_cache: dict[Path, chromadb.PersistentClient] = {}
_client_lock  = threading.Lock()


def _get_client(index_dir: Path) -> chromadb.PersistentClient:
    with _client_lock:
        if index_dir not in _client_cache:
            index_dir.mkdir(parents=True, exist_ok=True)
            _client_cache[index_dir] = chromadb.PersistentClient(path=str(index_dir))
        return _client_cache[index_dir]


def _evict_client(index_dir: Path) -> None:
    """Remove a cached client so the next call creates a fresh one."""
    with _client_lock:
        _client_cache.pop(index_dir, None)


def get_collection(index_dir: Path = INDEX_DIR) -> chromadb.Collection:
    """Return (or create) the ChromaDB collection stored at *index_dir*."""
    return _get_client(index_dir).get_or_create_collection(COLLECTION_NAME)


def reset_collection(index_dir: Path = INDEX_DIR) -> chromadb.Collection:
    """Delete and recreate the ChromaDB collection, erasing all vectors.

    Called when the embedding model changes and stored vectors have the wrong
    dimensionality.  Safe to call on an empty or non-existent collection.
    The caller is responsible for also resetting the BM25 index via
    ``get_bm25_store(index_dir).reset()`` when appropriate.
    """
    client = _get_client(index_dir)
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass
    # Evict and recreate so subsequent callers get a clean collection object.
    _evict_client(index_dir)
    return _get_client(index_dir).get_or_create_collection(COLLECTION_NAME)


def get_bm25_store(index_dir: Path = INDEX_DIR) -> BM25Store:
    """Return a BM25Store backed by *index_dir*."""
    return BM25Store(index_dir)
