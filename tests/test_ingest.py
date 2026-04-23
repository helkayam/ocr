from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

import app.registry as registry
from app.ingest import manager
from app.ingest.validator import validate_pdf
from app.models import DocumentStatus

# ---------------------------------------------------------------------------
# Minimal valid PDF bytes (spec-compliant enough for magic-byte checks)
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


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def pdf_file(tmp_path) -> Path:
    p = tmp_path / "sample.pdf"
    p.write_bytes(_MINIMAL_PDF)
    return p


@pytest.fixture(autouse=True)
def isolated_env(tmp_path, monkeypatch):
    """Redirect registry and RAW_DIR to temp paths for every test."""
    monkeypatch.setattr(registry, "REGISTRY_PATH", tmp_path / "registry.json")
    monkeypatch.setattr(manager, "RAW_DIR", tmp_path / "raw")


# ---------------------------------------------------------------------------
# Validator tests
# ---------------------------------------------------------------------------

class TestValidator:
    def test_valid_pdf_passes(self, pdf_file):
        validate_pdf(pdf_file)  # must not raise

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            validate_pdf(tmp_path / "nonexistent.pdf")

    def test_empty_file_raises(self, tmp_path):
        empty = tmp_path / "empty.pdf"
        empty.write_bytes(b"")
        with pytest.raises(ValueError, match="empty"):
            validate_pdf(empty)

    def test_non_pdf_bytes_raises(self, tmp_path):
        fake = tmp_path / "fake.pdf"
        fake.write_bytes(b"PK\x03\x04" + b"\x00" * 100)  # ZIP magic
        with pytest.raises(ValueError, match="magic bytes"):
            validate_pdf(fake)

    def test_oversized_file_raises(self, tmp_path, monkeypatch):
        from app.ingest import validator
        monkeypatch.setattr(validator, "_MAX_SIZE_BYTES", 10)
        oversized = tmp_path / "big.pdf"
        oversized.write_bytes(_MINIMAL_PDF)  # > 10 bytes
        with pytest.raises(ValueError, match="exceeds limit"):
            validate_pdf(oversized)

    def test_directory_raises(self, tmp_path):
        with pytest.raises(ValueError, match="not a regular file"):
            validate_pdf(tmp_path)


# ---------------------------------------------------------------------------
# Hash tests
# ---------------------------------------------------------------------------

class TestHashGeneration:
    def test_sha256_is_correct(self, pdf_file):
        expected = hashlib.sha256(_MINIMAL_PDF).hexdigest()
        assert manager._sha256(pdf_file) == expected

    def test_different_content_different_hash(self, tmp_path):
        a = tmp_path / "a.pdf"
        b = tmp_path / "b.pdf"
        a.write_bytes(_MINIMAL_PDF)
        b.write_bytes(_MINIMAL_PDF + b"\n% different")
        assert manager._sha256(a) != manager._sha256(b)


# ---------------------------------------------------------------------------
# Ingest manager tests
# ---------------------------------------------------------------------------

class TestIngestManager:
    def test_returns_document_id(self, pdf_file):
        doc_id = manager.ingest(pdf_file)
        assert isinstance(doc_id, str) and len(doc_id) == 36  # UUID4

    def test_copies_file_to_raw(self, pdf_file, tmp_path):
        doc_id = manager.ingest(pdf_file)
        dest = tmp_path / "raw" / f"{doc_id}.pdf"
        assert dest.exists()
        assert dest.read_bytes() == _MINIMAL_PDF

    def test_registry_record_created_as_pending(self, pdf_file):
        doc_id = manager.ingest(pdf_file)
        record = registry.get(doc_id)
        assert record is not None
        assert record.status == DocumentStatus.pending
        assert record.file_name == pdf_file.name
        assert len(record.file_hash) == 64  # SHA-256 hex digest

    def test_registry_stores_correct_hash(self, pdf_file):
        expected_hash = hashlib.sha256(_MINIMAL_PDF).hexdigest()
        doc_id = manager.ingest(pdf_file)
        record = registry.get(doc_id)
        assert record.file_hash == expected_hash

    def test_deduplication_raises_on_second_ingest(self, pdf_file, tmp_path):
        manager.ingest(pdf_file)
        # Second copy with identical content
        duplicate = tmp_path / "duplicate.pdf"
        duplicate.write_bytes(_MINIMAL_PDF)
        with pytest.raises(ValueError, match="Duplicate"):
            manager.ingest(duplicate)

    def test_deduplication_does_not_add_second_registry_entry(self, pdf_file, tmp_path):
        manager.ingest(pdf_file)
        duplicate = tmp_path / "dup.pdf"
        duplicate.write_bytes(_MINIMAL_PDF)
        try:
            manager.ingest(duplicate)
        except ValueError:
            pass
        assert len(registry.list_all()) == 1

    def test_different_files_both_ingested(self, pdf_file, tmp_path):
        other = tmp_path / "other.pdf"
        other.write_bytes(_MINIMAL_PDF + b"\n% v2")
        id1 = manager.ingest(pdf_file)
        id2 = manager.ingest(other)
        assert id1 != id2
        assert len(registry.list_all()) == 2

    def test_invalid_pdf_not_registered(self, tmp_path):
        bad = tmp_path / "bad.pdf"
        bad.write_bytes(b"not a pdf at all")
        with pytest.raises(ValueError):
            manager.ingest(bad)
        assert registry.list_all() == []

    def test_raw_dir_created_if_missing(self, pdf_file, tmp_path):
        raw_dir = tmp_path / "raw"
        assert not raw_dir.exists()
        manager.ingest(pdf_file)
        assert raw_dir.exists()
