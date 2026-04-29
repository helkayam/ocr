import sys
from pathlib import Path

try:
    import pysqlite3
    sys.modules["sqlite3"] = pysqlite3
except ImportError:
    pass

import chromadb

INDEX_DIR = Path("data/index")
COLLECTION_NAME = "documents"


def get_collection(index_dir: Path = INDEX_DIR) -> chromadb.Collection:
    """Return (or create) the ChromaDB collection stored at *index_dir*.

    A new PersistentClient is created for every call so that callers
    (including tests) can freely vary the storage path without module-level
    state getting in the way.
    """
    index_dir.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(index_dir))
    return client.get_or_create_collection(COLLECTION_NAME)


def reset_collection(index_dir: Path = INDEX_DIR) -> chromadb.Collection:
    """Delete and recreate the ChromaDB collection, erasing all vectors.

    Used when the embedding model changes and the stored vectors have the
    wrong dimensionality.  Safe to call on an empty or non-existent collection.
    """
    index_dir.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(index_dir))
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass
    return client.create_collection(COLLECTION_NAME)
