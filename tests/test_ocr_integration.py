from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import app.registry as registry
from app.ingest import manager as ingest_manager
from app.models import DocumentStatus, OCRResult
from app.ocr import processor

# ---------------------------------------------------------------------------
# Shared fixtures / helpers
# ---------------------------------------------------------------------------

_MINIMAL_PDF = (
    b"%PDF-1.4\n"
    b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
    b"3 0 obj<</Type/Page/MediaBox[0 0 3 3]>>endobj\n"
    b"xref\n0 4\n"
    b"0000000000 65535 f \n"
    b"0000000009 00000 n \n"
    b"0000000058 00000 n \n"
    b"0000000115 00000 n \n"
    b"trailer<</Size 4/Root 1 0 R>>\n"
    b"startxref\n190\n%%EOF\n"
)

# A realistic OCR payload that OCRService would return for a Hebrew document
_MOCK_OCR_PAYLOAD = {
    "file_name": "test.pdf",
    "pages": [
        {
            "page_num": 1,
            "stats": {"median_font_size": 12.0, "max_font_size": 18.0},
            "blocks": [
                {
                    "text": "פרוטוקול ישיבה",
                    "type": "text",
                    "y_top": 50.0,
                    "y_bottom": 68.0,
                    "font_size": 18.0,
                    "ratio_to_body": 1.5,
                    "line_count": 1,
                },
                {
                    "text": "נושא: בדיקת מערכת ה-OCR",
                    "type": "text",
                    "y_top": 80.0,
                    "y_bottom": 95.0,
                    "font_size": 12.0,
                    "ratio_to_body": 1.0,
                    "line_count": 1,
                },
                {
                    "text": "| עמודה א | עמודה ב |\n| --- | --- |\n| ערך 1 | ערך 2 |",
                    "type": "table",
                    "y_top": 110.0,
                    "y_bottom": 160.0,
                    "font_size": 11.0,
                    "ratio_to_body": 1.0,
                    "line_count": 3,
                },
            ],
        }
    ],
}


@pytest.fixture(autouse=True)
def isolated_env(tmp_path, monkeypatch):
    """Redirect all I/O paths and registry to temp dirs for every test."""
    monkeypatch.setattr(registry, "REGISTRY_PATH", tmp_path / "registry.json")
    monkeypatch.setattr(processor, "RAW_DIR", tmp_path / "raw")
    monkeypatch.setattr(processor, "OCR_DIR", tmp_path / "ocr")
    monkeypatch.setattr(ingest_manager, "RAW_DIR", tmp_path / "raw")


@pytest.fixture()
def ingested_doc(tmp_path) -> str:
    """Ingest a minimal PDF and return its document_id."""
    src = tmp_path / "source.pdf"
    src.write_bytes(_MINIMAL_PDF)
    return ingest_manager.ingest(src)


def _mock_ocr(return_payload: dict = _MOCK_OCR_PAYLOAD):
    """Return a context manager that patches OCRService.process_file."""
    return patch(
        "app.ocr.processor.OCRService",
        return_value=MagicMock(
            process_file=MagicMock(
                return_value=json.dumps(return_payload, ensure_ascii=False)
            )
        ),
    )


# ---------------------------------------------------------------------------
# Unit tests (mocked OCR)
# ---------------------------------------------------------------------------

class TestProcessorUnit:
    def test_returns_ocr_result(self, ingested_doc):
        with _mock_ocr():
            result = processor.process(ingested_doc)
        assert isinstance(result, OCRResult)

    def test_result_has_correct_structure(self, ingested_doc):
        with _mock_ocr():
            result = processor.process(ingested_doc)
        assert result.file_name == "test.pdf"
        assert len(result.pages) == 1
        page = result.pages[0]
        assert page.page_num == 1
        assert page.stats.median_font_size == 12.0
        assert page.stats.max_font_size == 18.0
        assert len(page.blocks) == 3

    def test_block_types_parsed(self, ingested_doc):
        with _mock_ocr():
            result = processor.process(ingested_doc)
        types = [b.type for b in result.pages[0].blocks]
        assert "text" in types
        assert "table" in types

    def test_ocr_json_saved_to_disk(self, ingested_doc, tmp_path):
        with _mock_ocr():
            processor.process(ingested_doc)
        out_path = tmp_path / "ocr" / f"{ingested_doc}.json"
        assert out_path.exists()

    def test_saved_json_is_valid_and_parseable(self, ingested_doc, tmp_path):
        with _mock_ocr():
            processor.process(ingested_doc)
        out_path = tmp_path / "ocr" / f"{ingested_doc}.json"
        raw = json.loads(out_path.read_text(encoding="utf-8"))
        assert "file_name" in raw
        assert "pages" in raw

    def test_saved_json_roundtrips_to_model(self, ingested_doc, tmp_path):
        with _mock_ocr():
            original = processor.process(ingested_doc)
        out_path = tmp_path / "ocr" / f"{ingested_doc}.json"
        reloaded = OCRResult.model_validate_json(out_path.read_text(encoding="utf-8"))
        assert reloaded.file_name == original.file_name
        assert len(reloaded.pages) == len(original.pages)

    def test_registry_updated_to_ocr_completed(self, ingested_doc):
        with _mock_ocr():
            processor.process(ingested_doc)
        record = registry.get(ingested_doc)
        assert record.status == DocumentStatus.ocr_completed

    def test_ocr_dir_created_if_missing(self, ingested_doc, tmp_path):
        ocr_dir = tmp_path / "ocr"
        assert not ocr_dir.exists()
        with _mock_ocr():
            processor.process(ingested_doc)
        assert ocr_dir.exists()

    def test_missing_raw_pdf_raises_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="Raw PDF not found"):
            processor.process("nonexistent-doc-id")

    def test_ocr_service_error_payload_raises_runtime_error(self, ingested_doc):
        error_payload = {"error": "File not found"}
        with _mock_ocr(error_payload):
            with pytest.raises(RuntimeError, match="OCRService returned error"):
                processor.process(ingested_doc)

    def test_error_does_not_update_registry(self, ingested_doc):
        error_payload = {"error": "File not found"}
        with _mock_ocr(error_payload):
            try:
                processor.process(ingested_doc)
            except RuntimeError:
                pass
        record = registry.get(ingested_doc)
        assert record.status == DocumentStatus.pending

    def test_empty_pages_handled_gracefully(self, ingested_doc):
        empty_pages_payload = {"file_name": "test.pdf", "pages": []}
        with _mock_ocr(empty_pages_payload):
            result = processor.process(ingested_doc)
        assert result.pages == []

    def test_multiple_pages_parsed(self, ingested_doc):
        multi_page_payload = {
            "file_name": "test.pdf",
            "pages": [
                {
                    "page_num": i,
                    "stats": {"median_font_size": 11.0, "max_font_size": 14.0},
                    "blocks": [
                        {
                            "text": f"עמוד {i}",
                            "type": "text",
                            "y_top": 10.0,
                            "y_bottom": 25.0,
                            "font_size": 11.0,
                            "ratio_to_body": 1.0,
                            "line_count": 1,
                        }
                    ],
                }
                for i in range(1, 4)
            ],
        }
        with _mock_ocr(multi_page_payload):
            result = processor.process(ingested_doc)
        assert len(result.pages) == 3
        assert [p.page_num for p in result.pages] == [1, 2, 3]


# ---------------------------------------------------------------------------
# Integration test (real OCRService, minimal PDF)
# ---------------------------------------------------------------------------

class TestOCRIntegration:
    def test_real_ocr_creates_output_file(self, ingested_doc, tmp_path):
        """Run the actual OCRService (no mocks). The minimal PDF has no text,
        so pages may be empty — but the processor must complete without error
        and persist the JSON file with the correct structure."""
        result = processor.process(ingested_doc)

        # JSON file must exist
        out_path = tmp_path / "ocr" / f"{ingested_doc}.json"
        assert out_path.exists(), "OCR JSON output file was not created"

        # File must be valid JSON conforming to OCRResult schema
        reloaded = OCRResult.model_validate_json(out_path.read_text(encoding="utf-8"))
        assert isinstance(reloaded.pages, list)

        # Registry must be updated
        record = registry.get(ingested_doc)
        assert record.status == DocumentStatus.ocr_completed

        # Returned value must match what was saved
        assert result.file_name == reloaded.file_name
