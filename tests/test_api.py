from __future__ import annotations

import sys
import os

# Ensure backend/ internals (api, services, db) resolve when imported from the project root.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from app.models import CitedSource, DocumentRecord, DocumentStatus, RAGResponse

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


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# POST /documents/
# ---------------------------------------------------------------------------

class TestUploadDocument:
    def _upload(self, client, filename="report.pdf", content=_MINIMAL_PDF,
                doc_id="doc-001", record=None):
        record = record or _PENDING_RECORD
        with patch("backend.api.rag_router.ingest_manager.ingest", return_value=doc_id), \
             patch("backend.api.rag_router.rag_registry.get", return_value=record), \
             patch("backend.api.rag_router.process_document"):
            resp = client.post(
                "/documents/",
                files={"file": (filename, content, "application/pdf")},
            )
        return resp

    def test_returns_202_on_success(self, client):
        assert self._upload(client).status_code == 202

    def test_response_contains_document_id(self, client):
        assert self._upload(client).json()["document_id"] == "doc-001"

    def test_response_contains_file_name(self, client):
        assert self._upload(client).json()["file_name"] == "test.pdf"

    def test_response_status_is_pending(self, client):
        assert self._upload(client).json()["status"] == "pending"

    def test_duplicate_returns_409(self, client):
        with patch("backend.api.rag_router.ingest_manager.ingest",
                   side_effect=ValueError("Duplicate file rejected")):
            resp = client.post("/documents/", files={"file": ("r.pdf", _MINIMAL_PDF, "application/pdf")})
        assert resp.status_code == 409

    def test_invalid_pdf_returns_422(self, client):
        with patch("backend.api.rag_router.ingest_manager.ingest",
                   side_effect=ValueError("File is not a valid PDF")):
            resp = client.post("/documents/", files={"file": ("r.pdf", b"not a pdf", "application/pdf")})
        assert resp.status_code == 422

    def test_ingest_error_returns_500(self, client):
        with patch("backend.api.rag_router.ingest_manager.ingest",
                   side_effect=RuntimeError("disk full")):
            resp = client.post("/documents/", files={"file": ("r.pdf", _MINIMAL_PDF, "application/pdf")})
        assert resp.status_code == 500

    def test_missing_file_field_returns_422(self, client):
        resp = client.post("/documents/")
        assert resp.status_code == 422

    def test_ingest_manager_receives_correct_filename(self, client):
        captured: dict = {}

        def capture(path, workspace_id="__legacy__"):
            captured["path"] = path
            return "doc-001"

        with patch("backend.api.rag_router.ingest_manager.ingest", side_effect=capture), \
             patch("backend.api.rag_router.rag_registry.get", return_value=_PENDING_RECORD), \
             patch("backend.api.rag_router.process_document"):
            client.post("/documents/", files={"file": ("מסמך.pdf", _MINIMAL_PDF, "application/pdf")})

        assert captured["path"].endswith("מסמך.pdf")


# ---------------------------------------------------------------------------
# GET /documents/
# ---------------------------------------------------------------------------

class TestListDocuments:
    def test_returns_200(self, client):
        with patch("backend.api.rag_router.rag_registry.list_all", return_value=[]):
            assert client.get("/documents/").status_code == 200

    def test_returns_empty_list_when_no_documents(self, client):
        with patch("backend.api.rag_router.rag_registry.list_all", return_value=[]):
            assert client.get("/documents/").json() == []

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
        with patch("backend.api.rag_router.rag_registry.list_all", return_value=records):
            assert len(client.get("/documents/").json()) == 2

    def test_document_fields_present(self, client):
        with patch("backend.api.rag_router.rag_registry.list_all", return_value=[_PENDING_RECORD]):
            doc = client.get("/documents/").json()[0]
        for field in ("document_id", "file_name", "status", "created_at", "file_hash"):
            assert field in doc

    def test_status_serialised_as_string(self, client):
        with patch("backend.api.rag_router.rag_registry.list_all", return_value=[_PENDING_RECORD]):
            assert isinstance(client.get("/documents/").json()[0]["status"], str)


# ---------------------------------------------------------------------------
# POST /query/
# ---------------------------------------------------------------------------

class TestQuery:
    def test_returns_200_on_success(self, client):
        with patch("backend.api.rag_router.pipeline.ask_pipeline", return_value=_RAG_RESPONSE):
            assert client.post("/query/", json={"query": "מה שם המסמך?"}).status_code == 200

    def test_response_contains_answer(self, client):
        with patch("backend.api.rag_router.pipeline.ask_pipeline", return_value=_RAG_RESPONSE):
            assert client.post("/query/", json={"query": "שאלה"}).json()["answer"] == _RAG_RESPONSE.answer

    def test_response_contains_query(self, client):
        with patch("backend.api.rag_router.pipeline.ask_pipeline", return_value=_RAG_RESPONSE):
            assert client.post("/query/", json={"query": _RAG_RESPONSE.query}).json()["query"] == _RAG_RESPONSE.query

    def test_default_top_k_is_5(self, client):
        with patch("backend.api.rag_router.pipeline.ask_pipeline", return_value=_RAG_RESPONSE) as mock:
            client.post("/query/", json={"query": "שאלה"})
        mock.assert_called_once_with("שאלה", top_k=5, workspace_id=None)

    def test_custom_top_k_passed_through(self, client):
        with patch("backend.api.rag_router.pipeline.ask_pipeline", return_value=_RAG_RESPONSE) as mock:
            client.post("/query/", json={"query": "שאלה", "top_k": 15})
        mock.assert_called_once_with("שאלה", top_k=15, workspace_id=None)

    def test_workspace_id_passed_through(self, client):
        with patch("backend.api.rag_router.pipeline.ask_pipeline", return_value=_RAG_RESPONSE) as mock:
            client.post("/query/", json={"query": "שאלה", "workspace_id": "ws-123"})
        mock.assert_called_once_with("שאלה", top_k=5, workspace_id="ws-123")

    def test_missing_query_field_returns_422(self, client):
        assert client.post("/query/", json={}).status_code == 422

    def test_empty_query_returns_422(self, client):
        assert client.post("/query/", json={"query": ""}).status_code == 422

    def test_top_k_zero_returns_422(self, client):
        assert client.post("/query/", json={"query": "שאלה", "top_k": 0}).status_code == 422

    def test_top_k_above_limit_returns_422(self, client):
        assert client.post("/query/", json={"query": "שאלה", "top_k": 51}).status_code == 422

    def test_pipeline_error_returns_500(self, client):
        with patch("backend.api.rag_router.pipeline.ask_pipeline",
                   side_effect=RuntimeError("groq unavailable")):
            assert client.post("/query/", json={"query": "שאלה"}).status_code == 500
