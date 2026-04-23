from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from loguru import logger

from app.models import DocumentRecord, DocumentStatus

REGISTRY_PATH = Path("data/registry.json")


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
    data = _load()
    if record.document_id in data:
        raise ValueError(f"Document {record.document_id!r} already exists in registry")
    data[record.document_id] = record.model_dump(mode="json")
    _save(data)
    logger.info("Registry: added document_id={}", record.document_id)


def update_status(document_id: str, status: DocumentStatus) -> None:
    data = _load()
    if document_id not in data:
        raise KeyError(f"Document {document_id!r} not found in registry")
    data[document_id]["status"] = status.value
    _save(data)
    logger.info("Registry: document_id={} -> status={}", document_id, status.value)


def get(document_id: str) -> Optional[DocumentRecord]:
    data = _load()
    raw = data.get(document_id)
    return DocumentRecord(**raw) if raw else None


def exists_by_hash(file_hash: str) -> bool:
    data = _load()
    return any(v["file_hash"] == file_hash for v in data.values())


def delete(document_id: str) -> None:
    data = _load()
    if document_id not in data:
        raise KeyError(f"Document {document_id!r} not found in registry")
    del data[document_id]
    _save(data)
    logger.info("Registry: deleted document_id={}", document_id)


def list_all() -> List[DocumentRecord]:
    data = _load()
    return [DocumentRecord(**v) for v in data.values()]
