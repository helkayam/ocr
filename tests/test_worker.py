"""Tests for app/worker/tasks.py — the background processing task."""
from __future__ import annotations

from unittest.mock import MagicMock, call, patch

import pytest

from app.models import DocumentStatus
from app.worker.tasks import process_document


# ---------------------------------------------------------------------------
# process_document — happy path
# ---------------------------------------------------------------------------

class TestProcessDocumentSuccess:
    def _run(self, doc_id: str = "doc-001"):
        """Invoke process_document with all external calls mocked out."""
        with patch("app.worker.tasks.ocr_processor.process") as p_ocr, \
             patch("app.worker.tasks.splitter.split", return_value=[MagicMock()]) as p_split, \
             patch("app.worker.tasks.indexer.index", return_value=5) as p_index, \
             patch("app.worker.tasks.registry.update_status") as p_status:
            process_document(doc_id)
        return p_ocr, p_split, p_index, p_status

    def test_calls_ocr_processor(self):
        p_ocr, _, _, _ = self._run()
        p_ocr.assert_called_once_with("doc-001")

    def test_calls_splitter(self):
        _, p_split, _, _ = self._run()
        p_split.assert_called_once_with("doc-001")

    def test_calls_indexer(self):
        _, _, p_index, _ = self._run()
        p_index.assert_called_once_with("doc-001")

    def test_does_not_update_status_on_success(self):
        """Registry status is updated by indexer.index(); tasks.py must not touch it."""
        _, _, _, p_status = self._run()
        p_status.assert_not_called()

    def test_returns_none(self):
        with patch("app.worker.tasks.ocr_processor.process"), \
             patch("app.worker.tasks.splitter.split", return_value=[]), \
             patch("app.worker.tasks.indexer.index", return_value=0):
            result = process_document("doc-001")
        assert result is None

    def test_phases_called_in_order(self):
        """OCR must complete before chunking, chunking before indexing."""
        call_order: list[str] = []

        def record(name):
            def _inner(*_a, **_kw):
                call_order.append(name)
                return [] if name == "split" else 0
            return _inner

        with patch("app.worker.tasks.ocr_processor.process", side_effect=record("ocr")), \
             patch("app.worker.tasks.splitter.split", side_effect=record("split")), \
             patch("app.worker.tasks.indexer.index", side_effect=record("index")):
            process_document("doc-001")

        assert call_order == ["ocr", "split", "index"]


# ---------------------------------------------------------------------------
# process_document — failure handling
# ---------------------------------------------------------------------------

class TestProcessDocumentFailure:
    def test_sets_status_to_error_on_ocr_failure(self):
        with patch("app.worker.tasks.ocr_processor.process",
                   side_effect=RuntimeError("OCR failed")), \
             patch("app.worker.tasks.registry.update_status") as p_status:
            with pytest.raises(RuntimeError):
                process_document("doc-001")
        p_status.assert_called_once_with("doc-001", DocumentStatus.error)

    def test_sets_status_to_error_on_splitter_failure(self):
        with patch("app.worker.tasks.ocr_processor.process"), \
             patch("app.worker.tasks.splitter.split",
                   side_effect=ValueError("bad chunks")), \
             patch("app.worker.tasks.registry.update_status") as p_status:
            with pytest.raises(ValueError):
                process_document("doc-001")
        p_status.assert_called_once_with("doc-001", DocumentStatus.error)

    def test_sets_status_to_error_on_indexer_failure(self):
        with patch("app.worker.tasks.ocr_processor.process"), \
             patch("app.worker.tasks.splitter.split", return_value=[]), \
             patch("app.worker.tasks.indexer.index",
                   side_effect=OSError("Chroma unavailable")), \
             patch("app.worker.tasks.registry.update_status") as p_status:
            with pytest.raises(OSError):
                process_document("doc-001")
        p_status.assert_called_once_with("doc-001", DocumentStatus.error)

    def test_reraises_exception_after_status_update(self):
        """RQ needs the exception to propagate so it can mark the job as failed."""
        exc = RuntimeError("boom")
        with patch("app.worker.tasks.ocr_processor.process", side_effect=exc), \
             patch("app.worker.tasks.registry.update_status"):
            with pytest.raises(RuntimeError) as exc_info:
                process_document("doc-001")
        assert exc_info.value is exc

    def test_indexer_not_called_after_ocr_failure(self):
        with patch("app.worker.tasks.ocr_processor.process",
                   side_effect=RuntimeError("OCR failed")), \
             patch("app.worker.tasks.splitter.split") as p_split, \
             patch("app.worker.tasks.indexer.index") as p_index, \
             patch("app.worker.tasks.registry.update_status"):
            with pytest.raises(RuntimeError):
                process_document("doc-001")
        p_split.assert_not_called()
        p_index.assert_not_called()

    def test_indexer_not_called_after_splitter_failure(self):
        with patch("app.worker.tasks.ocr_processor.process"), \
             patch("app.worker.tasks.splitter.split",
                   side_effect=ValueError("bad")), \
             patch("app.worker.tasks.indexer.index") as p_index, \
             patch("app.worker.tasks.registry.update_status"):
            with pytest.raises(ValueError):
                process_document("doc-001")
        p_index.assert_not_called()

    def test_doc_id_passed_to_status_update(self):
        with patch("app.worker.tasks.ocr_processor.process",
                   side_effect=RuntimeError("err")), \
             patch("app.worker.tasks.registry.update_status") as p_status:
            with pytest.raises(RuntimeError):
                process_document("my-special-doc")
        p_status.assert_called_once_with("my-special-doc", DocumentStatus.error)
