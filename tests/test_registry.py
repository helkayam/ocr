from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

import app.registry as registry
from app.models import DocumentRecord, DocumentStatus


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def isolated_registry(tmp_path, monkeypatch):
    """Redirect REGISTRY_PATH to a temp file for every test."""
    monkeypatch.setattr(registry, "REGISTRY_PATH", tmp_path / "registry.json")


def _make_record(doc_id: str = "doc-001", file_hash: str = "abc123") -> DocumentRecord:
    return DocumentRecord(
        document_id=doc_id,
        file_name="test.pdf",
        status=DocumentStatus.pending,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        file_hash=file_hash,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestAdd:
    def test_adds_record_and_persists(self):
        record = _make_record()
        registry.add(record)

        retrieved = registry.get("doc-001")
        assert retrieved is not None
        assert retrieved.document_id == "doc-001"
        assert retrieved.file_name == "test.pdf"
        assert retrieved.status == DocumentStatus.pending
        assert retrieved.file_hash == "abc123"

    def test_raises_on_duplicate_id(self):
        registry.add(_make_record())
        with pytest.raises(ValueError, match="already exists"):
            registry.add(_make_record())


class TestUpdateStatus:
    def test_updates_status(self):
        registry.add(_make_record())
        registry.update_status("doc-001", DocumentStatus.ocr_completed)

        record = registry.get("doc-001")
        assert record.status == DocumentStatus.ocr_completed

    def test_raises_for_unknown_id(self):
        with pytest.raises(KeyError):
            registry.update_status("nonexistent", DocumentStatus.indexed)


class TestDelete:
    def test_deletes_record(self):
        registry.add(_make_record())
        registry.delete("doc-001")
        assert registry.get("doc-001") is None

    def test_raises_for_unknown_id(self):
        with pytest.raises(KeyError):
            registry.delete("ghost-id")

    def test_deleted_record_not_in_list(self):
        registry.add(_make_record("a", "hash-a"))
        registry.add(_make_record("b", "hash-b"))
        registry.delete("a")
        ids = [r.document_id for r in registry.list_all()]
        assert "a" not in ids
        assert "b" in ids


class TestExistsByHash:
    def test_returns_true_for_known_hash(self):
        registry.add(_make_record(file_hash="unique-hash"))
        assert registry.exists_by_hash("unique-hash") is True

    def test_returns_false_for_unknown_hash(self):
        assert registry.exists_by_hash("does-not-exist") is False


class TestListAll:
    def test_returns_all_records(self):
        registry.add(_make_record("x", "h1"))
        registry.add(_make_record("y", "h2"))
        records = registry.list_all()
        assert len(records) == 2

    def test_empty_registry(self):
        assert registry.list_all() == []


class TestRegistryPersistence:
    def test_data_survives_between_calls(self, tmp_path, monkeypatch):
        """Simulate two separate 'process runs' sharing the same file."""
        path = tmp_path / "shared_registry.json"
        monkeypatch.setattr(registry, "REGISTRY_PATH", path)

        registry.add(_make_record())
        registry.update_status("doc-001", DocumentStatus.chunked)

        # Read the raw JSON to confirm on-disk state
        raw = json.loads(path.read_text())
        assert raw["doc-001"]["status"] == "chunked"
