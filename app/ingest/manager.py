from __future__ import annotations

import hashlib
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger

import app.registry as registry
from app.ingest.validator import validate_pdf
from app.models import DocumentRecord, DocumentStatus

RAW_DIR = Path("data/raw")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(65_536), b""):
            h.update(block)
    return h.hexdigest()


def ingest(file_path: Path | str) -> str:
    """Validate, deduplicate, copy, and register a PDF.

    Returns the newly created document_id.
    Raises ValueError on duplicate or invalid file.
    """
    path = Path(file_path)

    logger.info("Ingest start: {}", path)
    validate_pdf(path)

    file_hash = _sha256(path)
    logger.debug("SHA-256: {}", file_hash)

    if registry.exists_by_hash(file_hash):
        raise ValueError(
            f"Duplicate file rejected — hash {file_hash!r} already exists in registry"
        )

    document_id = str(uuid.uuid4())

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    dest = RAW_DIR / f"{document_id}.pdf"
    shutil.copy2(path, dest)
    logger.debug("Copied to {}", dest)

    record = DocumentRecord(
        document_id=document_id,
        file_name=path.name,
        status=DocumentStatus.pending,
        created_at=datetime.now(timezone.utc),
        file_hash=file_hash,
    )
    registry.add(record)

    logger.info("Ingest complete: file={} document_id={}", path.name, document_id)
    return document_id
