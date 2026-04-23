from __future__ import annotations

from pathlib import Path

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
