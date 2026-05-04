import sys
from pathlib import Path

try:
    import pysqlite3
    sys.modules["sqlite3"] = pysqlite3
except ImportError:
    pass

import chromadb

from app.indexing.bm25_store import BM25Store

INDEX_DIR       = Path("data/index")
COLLECTION_NAME = "documents"


def get_collection(index_dir: Path = INDEX_DIR) -> chromadb.Collection:
    """Return (or create) the ChromaDB collection stored at *index_dir*.

    A new PersistentClient is created for every call so callers (including
    tests) can freely vary the storage path without module-level state.
    """
    index_dir.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(index_dir))
    return client.get_or_create_collection(COLLECTION_NAME)


def reset_collection(index_dir: Path = INDEX_DIR) -> chromadb.Collection:
    """Delete and recreate the ChromaDB collection, erasing all vectors.

    Called when the embedding model changes and stored vectors have the wrong
    dimensionality.  Safe to call on an empty or non-existent collection.
    The caller is responsible for also resetting the BM25 index via
    ``get_bm25_store(index_dir).reset()`` when appropriate.
    """
    index_dir.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(index_dir))
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass
    return client.create_collection(COLLECTION_NAME)


def get_bm25_store(index_dir: Path = INDEX_DIR) -> BM25Store:
    """Return a BM25Store backed by *index_dir*.

    Loads the corpus from disk on every call.  Reuse the returned instance
    within a single request to avoid redundant I/O.
    """
    return BM25Store(index_dir)
