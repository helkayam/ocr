from __future__ import annotations

from datetime import datetime, timezone
from typing import List
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.main import app
from app.models import (
    CitedSource,
    DocumentRecord,
    DocumentStatus,
    RAGResponse,
)

# ---------------------------------------------------------------------------
# Shared test data
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

_PENDING_RECORD = DocumentRecord(
    document_id="doc-001",
    file_name="test.pdf",
    status=DocumentStatus.pending,
    created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    file_hash="abcdef1234567890",
)

_RAG_RESPONSE = RAGResponse(
    query="מה נושא המסמך?",
    answer="המסמך עוסק בפרוטוקול ישיבה.",
    sources=[CitedSource(document_id="doc-001", page_num=2)],
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_queue():
    """Return a mock Queue whose enqueue() call can be asserted."""
    mock_q = MagicMock()
    return mock_q


# ---------------------------------------------------------------------------
# Client fixture
# ---------------------------------------------------------------------------

@pytest.fixture()
def client() -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# POST /documents/  (async — Phase 2 sync, Phases 3-5 enqueued)
# ---------------------------------------------------------------------------

class TestUploadDocument:
    def _upload(self, client, filename="report.pdf", content=_MINIMAL_PDF,
                doc_id="doc-001", record=None):
        """Shared helper: patches ingest_manager, registry, and _get_queue."""
        record = record or _PENDING_RECORD
        mock_q = _mock_queue()
        with patch("app.api.main.ingest_manager.ingest", return_value=doc_id), \
             patch("app.api.main.registry.get", return_value=record), \
             patch("app.api.main._get_queue", return_value=mock_q):
            resp = client.post(
                "/documents/",
                files={"file": (filename, content, "application/pdf")},
            )
        return resp, mock_q

    def test_returns_202_on_success(self, client):
        resp, _ = self._upload(client)
        assert resp.status_code == 202

    def test_response_contains_document_id(self, client):
        resp, _ = self._upload(client)
        assert resp.json()["document_id"] == "doc-001"

    def test_response_contains_file_name(self, client):
        resp, _ = self._upload(client)
        assert resp.json()["file_name"] == "test.pdf"

    def test_response_status_is_pending(self, client):
        resp, _ = self._upload(client)
        assert resp.json()["status"] == "pending"

    def test_job_enqueued_on_success(self, client):
        """process_document must be enqueued with the new doc_id."""
        from app.worker.tasks import process_document
        resp, mock_q = self._upload(client, doc_id="doc-001")
        assert resp.status_code == 202
        mock_q.enqueue.assert_called_once_with(process_document, "doc-001")

    def test_duplicate_returns_409(self, client):
        mock_q = _mock_queue()
        with patch("app.api.main.ingest_manager.ingest",
                   side_effect=ValueError("Duplicate file rejected")), \
             patch("app.api.main._get_queue", return_value=mock_q):
            resp = client.post("/documents/", files={"file": ("r.pdf", _MINIMAL_PDF, "application/pdf")})
        assert resp.status_code == 409

    def test_duplicate_does_not_enqueue(self, client):
        """If Phase 2 rejects a duplicate, no job should be queued."""
        mock_q = _mock_queue()
        with patch("app.api.main.ingest_manager.ingest",
                   side_effect=ValueError("Duplicate file rejected")), \
             patch("app.api.main._get_queue", return_value=mock_q):
            client.post("/documents/", files={"file": ("r.pdf", _MINIMAL_PDF, "application/pdf")})
        mock_q.enqueue.assert_not_called()

    def test_invalid_pdf_returns_422(self, client):
        mock_q = _mock_queue()
        with patch("app.api.main.ingest_manager.ingest",
                   side_effect=ValueError("File is not a valid PDF")), \
             patch("app.api.main._get_queue", return_value=mock_q):
            resp = client.post("/documents/", files={"file": ("r.pdf", b"not a pdf", "application/pdf")})
        assert resp.status_code == 422

    def test_ingest_error_returns_500(self, client):
        mock_q = _mock_queue()
        with patch("app.api.main.ingest_manager.ingest",
                   side_effect=RuntimeError("disk full")), \
             patch("app.api.main._get_queue", return_value=mock_q):
            resp = client.post("/documents/", files={"file": ("r.pdf", _MINIMAL_PDF, "application/pdf")})
        assert resp.status_code == 500

    def test_queue_error_returns_500(self, client):
        """If Redis is unreachable, the endpoint should return 500."""
        mock_q = _mock_queue()
        mock_q.enqueue.side_effect = ConnectionError("Redis unavailable")
        with patch("app.api.main.ingest_manager.ingest", return_value="doc-001"), \
             patch("app.api.main.registry.get", return_value=_PENDING_RECORD), \
             patch("app.api.main._get_queue", return_value=mock_q):
            resp = client.post("/documents/", files={"file": ("r.pdf", _MINIMAL_PDF, "application/pdf")})
        assert resp.status_code == 500

    def test_missing_file_field_returns_422(self, client):
        resp = client.post("/documents/")
        assert resp.status_code == 422

    def test_ingest_manager_receives_correct_filename(self, client):
        """The temp path handed to ingest_manager must end with the uploaded name."""
        captured = {}

        def capture(path):
            captured["path"] = path
            return "doc-001"

        mock_q = _mock_queue()
        with patch("app.api.main.ingest_manager.ingest", side_effect=capture), \
             patch("app.api.main.registry.get", return_value=_PENDING_RECORD), \
             patch("app.api.main._get_queue", return_value=mock_q):
            client.post("/documents/", files={"file": ("מסמך.pdf", _MINIMAL_PDF, "application/pdf")})

        assert captured["path"].endswith("מסמך.pdf")


# ---------------------------------------------------------------------------
# GET /documents/
# ---------------------------------------------------------------------------

class TestListDocuments:
    def test_returns_200(self, client):
        with patch("app.api.main.registry.list_all", return_value=[]):
            resp = client.get("/documents/")
        assert resp.status_code == 200

    def test_returns_empty_list_when_no_documents(self, client):
        with patch("app.api.main.registry.list_all", return_value=[]):
            resp = client.get("/documents/")
        assert resp.json() == []

    def test_returns_all_documents(self, client):
        records = [
            _PENDING_RECORD,
            DocumentRecord(
                document_id="doc-002",
                file_name="other.pdf",
                status=DocumentStatus.pending,
                created_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
                file_hash="deadbeef",
            ),
        ]
        with patch("app.api.main.registry.list_all", return_value=records):
            resp = client.get("/documents/")
        data = resp.json()
        assert len(data) == 2

    def test_document_fields_present(self, client):
        with patch("app.api.main.registry.list_all", return_value=[_PENDING_RECORD]):
            resp = client.get("/documents/")
        doc = resp.json()[0]
        for field in ("document_id", "file_name", "status", "created_at", "file_hash"):
            assert field in doc

    def test_status_serialised_as_string(self, client):
        with patch("app.api.main.registry.list_all", return_value=[_PENDING_RECORD]):
            resp = client.get("/documents/")
        assert isinstance(resp.json()[0]["status"], str)


# ---------------------------------------------------------------------------
# DELETE /documents/{doc_id}
# ---------------------------------------------------------------------------

class TestDeleteDocument:
    def test_returns_204_on_success(self, client):
        with patch("app.api.main.pipeline.delete_pipeline"):
            resp = client.delete("/documents/doc-001")
        assert resp.status_code == 204

    def test_response_body_is_empty_on_204(self, client):
        with patch("app.api.main.pipeline.delete_pipeline"):
            resp = client.delete("/documents/doc-001")
        assert resp.content == b""

    def test_not_found_returns_404(self, client):
        with patch("app.api.main.pipeline.delete_pipeline",
                   side_effect=KeyError("doc-999")):
            resp = client.delete("/documents/doc-999")
        assert resp.status_code == 404

    def test_404_body_contains_doc_id(self, client):
        with patch("app.api.main.pipeline.delete_pipeline",
                   side_effect=KeyError("doc-999")):
            resp = client.delete("/documents/doc-999")
        assert "doc-999" in resp.json()["detail"]

    def test_pipeline_error_returns_500(self, client):
        with patch("app.api.main.pipeline.delete_pipeline",
                   side_effect=OSError("disk error")):
            resp = client.delete("/documents/doc-001")
        assert resp.status_code == 500

    def test_pipeline_called_with_doc_id(self, client):
        with patch("app.api.main.pipeline.delete_pipeline") as mock:
            client.delete("/documents/doc-abc")
        mock.assert_called_once_with("doc-abc")


# ---------------------------------------------------------------------------
# POST /documents/{doc_id}/reindex
# ---------------------------------------------------------------------------

class TestReindexDocument:
    def test_returns_200_on_success(self, client):
        with patch("app.api.main.pipeline.reindex_pipeline", return_value=10):
            resp = client.post("/documents/doc-001/reindex")
        assert resp.status_code == 200

    def test_response_contains_document_id(self, client):
        with patch("app.api.main.pipeline.reindex_pipeline", return_value=10):
            resp = client.post("/documents/doc-001/reindex")
        assert resp.json()["document_id"] == "doc-001"

    def test_response_contains_chunks_indexed(self, client):
        with patch("app.api.main.pipeline.reindex_pipeline", return_value=42):
            resp = client.post("/documents/doc-001/reindex")
        assert resp.json()["chunks_indexed"] == 42

    def test_not_found_returns_404(self, client):
        with patch("app.api.main.pipeline.reindex_pipeline",
                   side_effect=KeyError("doc-999")):
            resp = client.post("/documents/doc-999/reindex")
        assert resp.status_code == 404

    def test_missing_chunks_returns_422(self, client):
        with patch("app.api.main.pipeline.reindex_pipeline",
                   side_effect=FileNotFoundError("chunks missing")):
            resp = client.post("/documents/doc-001/reindex")
        assert resp.status_code == 422

    def test_pipeline_error_returns_500(self, client):
        with patch("app.api.main.pipeline.reindex_pipeline",
                   side_effect=RuntimeError("chroma error")):
            resp = client.post("/documents/doc-001/reindex")
        assert resp.status_code == 500

    def test_pipeline_called_with_doc_id(self, client):
        with patch("app.api.main.pipeline.reindex_pipeline", return_value=5) as mock:
            client.post("/documents/doc-xyz/reindex")
        mock.assert_called_once_with("doc-xyz")


# ---------------------------------------------------------------------------
# POST /query/
# ---------------------------------------------------------------------------

class TestQuery:
    def test_returns_200_on_success(self, client):
        with patch("app.api.main.pipeline.ask_pipeline", return_value=_RAG_RESPONSE):
            resp = client.post("/query/", json={"query": "מה שם המסמך?"})
        assert resp.status_code == 200

    def test_response_contains_answer(self, client):
        with patch("app.api.main.pipeline.ask_pipeline", return_value=_RAG_RESPONSE):
            resp = client.post("/query/", json={"query": "שאלה"})
        assert resp.json()["answer"] == _RAG_RESPONSE.answer

    def test_response_contains_query(self, client):
        with patch("app.api.main.pipeline.ask_pipeline", return_value=_RAG_RESPONSE):
            resp = client.post("/query/", json={"query": _RAG_RESPONSE.query})
        assert resp.json()["query"] == _RAG_RESPONSE.query

    def test_response_contains_sources(self, client):
        with patch("app.api.main.pipeline.ask_pipeline", return_value=_RAG_RESPONSE):
            resp = client.post("/query/", json={"query": "שאלה"})
        sources = resp.json()["sources"]
        assert len(sources) == 1
        assert sources[0]["document_id"] == "doc-001"
        assert sources[0]["page_num"] == 2

    def test_default_top_k_is_5(self, client):
        with patch("app.api.main.pipeline.ask_pipeline", return_value=_RAG_RESPONSE) as mock:
            client.post("/query/", json={"query": "שאלה"})
        mock.assert_called_once_with("שאלה", top_k=5)

    def test_custom_top_k_passed_through(self, client):
        with patch("app.api.main.pipeline.ask_pipeline", return_value=_RAG_RESPONSE) as mock:
            client.post("/query/", json={"query": "שאלה", "top_k": 15})
        mock.assert_called_once_with("שאלה", top_k=15)

    def test_missing_query_field_returns_422(self, client):
        resp = client.post("/query/", json={})
        assert resp.status_code == 422

    def test_empty_query_returns_422(self, client):
        resp = client.post("/query/", json={"query": ""})
        assert resp.status_code == 422

    def test_top_k_zero_returns_422(self, client):
        resp = client.post("/query/", json={"query": "שאלה", "top_k": 0})
        assert resp.status_code == 422

    def test_top_k_above_limit_returns_422(self, client):
        resp = client.post("/query/", json={"query": "שאלה", "top_k": 51})
        assert resp.status_code == 422

    def test_pipeline_error_returns_500(self, client):
        with patch("app.api.main.pipeline.ask_pipeline",
                   side_effect=RuntimeError("groq unavailable")):
            resp = client.post("/query/", json={"query": "שאלה"})
        assert resp.status_code == 500

    def test_empty_sources_returned_correctly(self, client):
        no_source_resp = RAGResponse(
            query="שאלה",
            answer="המידע המבוקש לא נמצא במסמכים שסופקו.",
            sources=[],
        )
        with patch("app.api.main.pipeline.ask_pipeline", return_value=no_source_resp):
            resp = client.post("/query/", json={"query": "שאלה"})
        assert resp.json()["sources"] == []
        assert resp.status_code == 200
