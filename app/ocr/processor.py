from __future__ import annotations

import json
from pathlib import Path

from loguru import logger

import app.registry as registry
from app.models import DocumentStatus, OCRResult
from app.ocr.service import OCRService

RAW_DIR = Path("data/raw")
OCR_DIR = Path("data/ocr")


def process(document_id: str) -> OCRResult:
    """Run OCR on the raw PDF for *document_id*, validate, persist, and update registry.

    Returns the validated OCRResult.
    Raises FileNotFoundError if the raw PDF is missing.
    Raises RuntimeError if OCRService reports an error.
    Raises ValueError if the OCR output fails Pydantic validation.
    """
    pdf_path = RAW_DIR / f"{document_id}.pdf"
    if not pdf_path.exists():
        raise FileNotFoundError(f"Raw PDF not found for document_id={document_id}: {pdf_path}")

    logger.info("OCR start: document_id={}", document_id)

    raw_json: str = OCRService().process_file(str(pdf_path))

    payload: dict = json.loads(raw_json)
    if "error" in payload:
        raise RuntimeError(f"OCRService returned error for document_id={document_id}: {payload['error']}")

    result = OCRResult.model_validate(payload)
    logger.debug("OCR parsed: document_id={} pages={}", document_id, len(result.pages))

    OCR_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OCR_DIR / f"{document_id}.json"
    out_path.write_text(
        result.model_dump_json(indent=2),
        encoding="utf-8",
    )
    logger.debug("OCR JSON saved: {}", out_path)

    registry.update_status(document_id, DocumentStatus.ocr_completed)
    logger.info("OCR complete: document_id={} pages={}", document_id, len(result.pages))

    return result
