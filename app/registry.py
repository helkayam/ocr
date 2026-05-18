from __future__ import annotations

import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from loguru import logger

from app.models import DocumentRecord, DocumentStatus

REGISTRY_PATH = Path("data/registry.json")

# Protects all read-modify-write cycles on registry.json.
# Without this lock, concurrent background tasks interleave _load()/_save()
# and silently overwrite each other's status updates.
_lock = threading.Lock()


def _load() -> Dict[str, dict]:
    if not REGISTRY_PATH.exists():
        return {}
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def _save(data: Dict[str, dict]) -> None:
    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    REGISTRY_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )


def add(record: DocumentRecord) -> None:
    with _lock:
        data = _load()
        if record.document_id in data:
            raise ValueError(f"Document {record.document_id!r} already exists in registry")
        data[record.document_id] = record.model_dump(mode="json")
        _save(data)
    logger.info("Registry: added document_id={}", record.document_id)


def update_status(document_id: str, status: DocumentStatus) -> None:
    with _lock:
        data = _load()
        if document_id not in data:
            raise KeyError(f"Document {document_id!r} not found in registry")
        data[document_id]["status"] = status.value
        _save(data)
    logger.info("Registry: document_id={} -> status={}", document_id, status.value)


def get(document_id: str) -> Optional[DocumentRecord]:
    with _lock:
        data = _load()
    raw = data.get(document_id)
    if not raw:
        return None
    raw.setdefault("workspace_id", "__legacy__")
    return DocumentRecord(**raw)


def exists_by_hash(file_hash: str) -> bool:
    with _lock:
        data = _load()
    return any(v["file_hash"] == file_hash for v in data.values())


def get_id_by_hash(file_hash: str) -> Optional[str]:
    with _lock:
        data = _load()
    for doc_id, v in data.items():
        if v["file_hash"] == file_hash:
            return doc_id
    return None


def upsert(record: DocumentRecord) -> None:
    with _lock:
        data = _load()
        data[record.document_id] = record.model_dump(mode="json")
        _save(data)
    logger.info("Registry: upserted document_id={}", record.document_id)


def delete(document_id: str) -> None:
    with _lock:
        data = _load()
        if document_id not in data:
            raise KeyError(f"Document {document_id!r} not found in registry")
        del data[document_id]
        _save(data)
    logger.info("Registry: deleted document_id={}", document_id)


def list_all() -> List[DocumentRecord]:
    with _lock:
        data = _load()
    records = []
    for v in data.values():
        v.setdefault("workspace_id", "__legacy__")
        records.append(DocumentRecord(**v))
    return records


def get_by_workspace(workspace_id: str) -> List[DocumentRecord]:
    """Return all records belonging to *workspace_id*."""
    return [r for r in list_all() if r.workspace_id == workspace_id]
