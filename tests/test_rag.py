from __future__ import annotations

from typing import List
from unittest.mock import MagicMock, call, patch

import httpx
import groq as groq_sdk
import pytest

from app.models import CitedSource, RAGResponse, SearchResult
from app.rag import generator
from app.rag.generator import (
    _MAX_RETRY_ATTEMPTS,
    _build_user_message,
    _call_groq_api,
    generate,
)
from app.retrieval import search as retrieval_search

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_search_result(
    doc_id: str = "doc-001",
    page: int = 1,
    text: str = "תוכן לדוגמה מהמסמך",
    score: float = 0.1,
) -> SearchResult:
    return SearchResult(
        chunk_id=f"{doc_id}_1_0_0",
        document_id=doc_id,
        page_num=page,
        text=text,
        score=score,
    )


def _make_groq_response(content: str) -> MagicMock:
    """Build a mock object that mimics groq chat.completions.create() return value."""
    msg = MagicMock()
    msg.content = content
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    return resp


def _rate_limit_error() -> groq_sdk.RateLimitError:
    """Construct a real groq.RateLimitError suitable for use in tests."""
    req = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    resp = httpx.Response(status_code=429, request=req)
    return groq_sdk.RateLimitError(
        "Rate limit exceeded", response=resp, body={"error": {"message": "rate limit"}}
    )


# ---------------------------------------------------------------------------
# _build_user_message tests
# ---------------------------------------------------------------------------

class TestBuildUserMessage:
    def test_contains_query(self):
        msg = _build_user_message("מה שם המסמך?", [])
        assert "מה שם המסמך?" in msg

    def test_no_context_shows_placeholder(self):
        msg = _build_user_message("שאלה", [])
        assert "אין הקשר זמין" in msg

    def test_context_passages_included(self):
        ctx = [_make_search_result(text="קטע חשוב מהמסמך")]
        msg = _build_user_message("שאלה", ctx)
        assert "קטע חשוב מהמסמך" in msg

    def test_source_citation_format_in_message(self):
        ctx = [_make_search_result(doc_id="doc-abc", page=7)]
        msg = _build_user_message("שאלה", ctx)
        assert "doc-abc" in msg
        assert "7" in msg

    def test_multiple_context_chunks_all_included(self):
        ctx = [
            _make_search_result(text="קטע ראשון", page=1),
            _make_search_result(text="קטע שני", page=2),
        ]
        msg = _build_user_message("שאלה", ctx)
        assert "קטע ראשון" in msg
        assert "קטע שני" in msg

    def test_context_chunks_ordered_correctly(self):
        ctx = [
            _make_search_result(text="קטע ראשון", page=1),
            _make_search_result(text="קטע שני", page=2),
        ]
        msg = _build_user_message("שאלה", ctx)
        assert msg.index("קטע ראשון") < msg.index("קטע שני")


# ---------------------------------------------------------------------------
# System prompt content tests
# ---------------------------------------------------------------------------

class TestSystemPrompt:
    def test_instructs_hebrew_reply(self):
        assert "Hebrew" in generator._SYSTEM_PROMPT or "עברית" in generator._SYSTEM_PROMPT

    def test_instructs_context_only(self):
        prompt = generator._SYSTEM_PROMPT.lower()
        assert "only" in prompt or "רק" in prompt

    def test_includes_citation_format(self):
        assert "document_id" in generator._SYSTEM_PROMPT
        assert "page_num" in generator._SYSTEM_PROMPT

    def test_instructs_not_found_response(self):
        assert "לא נמצא" in generator._SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# generate() tests (Groq mocked)
# ---------------------------------------------------------------------------

class TestGenerate:
    def _mock_client(self, answer_text: str) -> MagicMock:
        client = MagicMock(spec=groq_sdk.Groq)
        client.chat.completions.create.return_value = _make_groq_response(answer_text)
        return client

    def test_returns_rag_response(self):
        ctx = [_make_search_result()]
        with patch("app.rag.generator.groq_sdk.Groq", return_value=self._mock_client("תשובה")):
            with patch("os.getenv", return_value="test-key"):
                result = generate("שאלה", ctx)
        assert isinstance(result, RAGResponse)

    def test_answer_from_llm_in_response(self):
        ctx = [_make_search_result()]
        with patch("app.rag.generator.groq_sdk.Groq", return_value=self._mock_client("זוהי תשובה מפורטת")):
            with patch("os.getenv", return_value="test-key"):
                result = generate("שאלה", ctx)
        assert result.answer == "זוהי תשובה מפורטת"

    def test_query_preserved_in_response(self):
        ctx = [_make_search_result()]
        with patch("app.rag.generator.groq_sdk.Groq", return_value=self._mock_client("תשובה")):
            with patch("os.getenv", return_value="test-key"):
                result = generate("מה שם המחבר?", ctx)
        assert result.query == "מה שם המחבר?"

    def test_sources_derived_from_context(self):
        ctx = [
            _make_search_result(doc_id="doc-001", page=3),
            _make_search_result(doc_id="doc-002", page=7),
        ]
        with patch("app.rag.generator.groq_sdk.Groq", return_value=self._mock_client("תשובה")):
            with patch("os.getenv", return_value="test-key"):
                result = generate("שאלה", ctx)
        assert len(result.sources) == 2
        source_pairs = {(s.document_id, s.page_num) for s in result.sources}
        assert ("doc-001", 3) in source_pairs
        assert ("doc-002", 7) in source_pairs

    def test_sources_are_cited_source_objects(self):
        ctx = [_make_search_result()]
        with patch("app.rag.generator.groq_sdk.Groq", return_value=self._mock_client("תשובה")):
            with patch("os.getenv", return_value="test-key"):
                result = generate("שאלה", ctx)
        assert all(isinstance(s, CitedSource) for s in result.sources)

    def test_groq_called_with_system_and_user_messages(self):
        ctx = [_make_search_result(text="תוכן חשוב")]
        mock_client = self._mock_client("תשובה")
        with patch("app.rag.generator.groq_sdk.Groq", return_value=mock_client):
            with patch("os.getenv", return_value="test-key"):
                generate("שאלה", ctx)
        called_messages = mock_client.chat.completions.create.call_args.kwargs["messages"]
        roles = [m["role"] for m in called_messages]
        assert "system" in roles
        assert "user" in roles

    def test_user_message_sent_to_groq_contains_context(self):
        ctx = [_make_search_result(text="מידע קריטי")]
        mock_client = self._mock_client("תשובה")
        with patch("app.rag.generator.groq_sdk.Groq", return_value=mock_client):
            with patch("os.getenv", return_value="test-key"):
                generate("שאלה", ctx)
        msgs = mock_client.chat.completions.create.call_args.kwargs["messages"]
        user_content = next(m["content"] for m in msgs if m["role"] == "user")
        assert "מידע קריטי" in user_content

    def test_correct_model_used(self):
        ctx = [_make_search_result()]
        mock_client = self._mock_client("תשובה")
        with patch("app.rag.generator.groq_sdk.Groq", return_value=mock_client):
            with patch("os.getenv", return_value="test-key"):
                generate("שאלה", ctx)
        model_used = mock_client.chat.completions.create.call_args.kwargs["model"]
        assert model_used == "llama-3.3-70b-versatile"

    def test_empty_context_still_calls_groq(self):
        mock_client = self._mock_client("המידע המבוקש לא נמצא במסמכים שסופקו.")
        with patch("app.rag.generator.groq_sdk.Groq", return_value=mock_client):
            with patch("os.getenv", return_value="test-key"):
                result = generate("שאלה", [])
        assert mock_client.chat.completions.create.called
        assert result.sources == []

    def test_missing_api_key_raises_environment_error(self):
        with patch("os.getenv", return_value=None):
            with pytest.raises(EnvironmentError, match="GROQ_API_KEY"):
                generate("שאלה", [])


# ---------------------------------------------------------------------------
# Retry logic tests
# ---------------------------------------------------------------------------

class TestRetryLogic:
    """Verify that _call_groq_api retries on RateLimitError and stops on success."""

    @staticmethod
    def _client_with_side_effects(*effects) -> MagicMock:
        client = MagicMock(spec=groq_sdk.Groq)
        client.chat.completions.create.side_effect = list(effects)
        return client

    def test_succeeds_on_first_attempt(self):
        client = self._client_with_side_effects(_make_groq_response("תשובה"))
        with patch("time.sleep"):  # prevent actual waiting
            result = _call_groq_api(client, [{"role": "user", "content": "שאלה"}])
        assert result == "תשובה"
        assert client.chat.completions.create.call_count == 1

    def test_retries_once_on_rate_limit_then_succeeds(self):
        client = self._client_with_side_effects(
            _rate_limit_error(),
            _make_groq_response("תשובה לאחר retry"),
        )
        with patch("time.sleep"):
            result = _call_groq_api(client, [{"role": "user", "content": "שאלה"}])
        assert result == "תשובה לאחר retry"
        assert client.chat.completions.create.call_count == 2

    def test_retries_multiple_times_before_succeeding(self):
        client = self._client_with_side_effects(
            _rate_limit_error(),
            _rate_limit_error(),
            _rate_limit_error(),
            _make_groq_response("הצלחה אחרי שלושה ניסיונות"),
        )
        with patch("time.sleep"):
            result = _call_groq_api(client, [{"role": "user", "content": "שאלה"}])
        assert result == "הצלחה אחרי שלושה ניסיונות"
        assert client.chat.completions.create.call_count == 4

    def test_reraises_after_max_attempts_exhausted(self):
        errors = [_rate_limit_error()] * _MAX_RETRY_ATTEMPTS
        client = self._client_with_side_effects(*errors)
        with patch("time.sleep"):
            with pytest.raises(groq_sdk.RateLimitError):
                _call_groq_api(client, [{"role": "user", "content": "שאלה"}])
        assert client.chat.completions.create.call_count == _MAX_RETRY_ATTEMPTS

    def test_non_rate_limit_error_not_retried(self):
        client = self._client_with_side_effects(
            groq_sdk.APIConnectionError(request=MagicMock()),
        )
        with patch("time.sleep"):
            with pytest.raises(groq_sdk.APIConnectionError):
                _call_groq_api(client, [{"role": "user", "content": "שאלה"}])
        # Must NOT retry — should be exactly 1 call
        assert client.chat.completions.create.call_count == 1


# ---------------------------------------------------------------------------
# search.search() tests (ChromaDB and embedder mocked)
# ---------------------------------------------------------------------------

class TestSearch:
    def _make_chroma_result(self, chunk_ids, texts, doc_ids, pages, distances):
        return {
            "ids": [chunk_ids],
            "documents": [texts],
            "metadatas": [[{"document_id": d, "page_num": p} for d, p in zip(doc_ids, pages)]],
            "distances": [distances],
        }

    def test_returns_search_results(self):
        with patch("app.retrieval.search.embedder.embed", return_value=[[0.1, 0.2]]):
            mock_col = MagicMock()
            mock_col.count.return_value = 2
            mock_col.query.return_value = self._make_chroma_result(
                ["c-0", "c-1"], ["טקסט א", "טקסט ב"], ["d1", "d2"], [1, 2], [0.1, 0.3]
            )
            with patch("app.retrieval.search.db.get_collection", return_value=mock_col):
                results = retrieval_search.search("שאלה", top_k=2)

        assert len(results) == 2
        assert all(isinstance(r, SearchResult) for r in results)

    def test_result_fields_populated(self):
        with patch("app.retrieval.search.embedder.embed", return_value=[[0.1]]):
            mock_col = MagicMock()
            mock_col.count.return_value = 1
            mock_col.query.return_value = self._make_chroma_result(
                ["c-0"], ["תוכן חשוב"], ["doc-xyz"], [5], [0.05]
            )
            with patch("app.retrieval.search.db.get_collection", return_value=mock_col):
                results = retrieval_search.search("שאלה")

        r = results[0]
        assert r.chunk_id == "c-0"
        assert r.document_id == "doc-xyz"
        assert r.page_num == 5
        assert r.text == "תוכן חשוב"
        assert r.score == 0.05

    def test_empty_collection_returns_no_results(self):
        with patch("app.retrieval.search.embedder.embed", return_value=[[0.1]]):
            mock_col = MagicMock()
            mock_col.count.return_value = 0
            with patch("app.retrieval.search.db.get_collection", return_value=mock_col):
                results = retrieval_search.search("שאלה")

        assert results == []
        mock_col.query.assert_not_called()

    def test_document_id_filter_passed_to_chroma(self):
        with patch("app.retrieval.search.embedder.embed", return_value=[[0.1]]):
            mock_col = MagicMock()
            mock_col.count.return_value = 1
            mock_col.query.return_value = self._make_chroma_result(
                ["c-0"], ["טקסט"], ["doc-001"], [1], [0.1]
            )
            with patch("app.retrieval.search.db.get_collection", return_value=mock_col):
                retrieval_search.search("שאלה", document_id="doc-001")

        call_kwargs = mock_col.query.call_args.kwargs
        assert call_kwargs.get("where") == {"document_id": "doc-001"}

    def test_no_filter_does_not_pass_where(self):
        with patch("app.retrieval.search.embedder.embed", return_value=[[0.1]]):
            mock_col = MagicMock()
            mock_col.count.return_value = 1
            mock_col.query.return_value = self._make_chroma_result(
                ["c-0"], ["טקסט"], ["d1"], [1], [0.1]
            )
            with patch("app.retrieval.search.db.get_collection", return_value=mock_col):
                retrieval_search.search("שאלה")

        call_kwargs = mock_col.query.call_args.kwargs
        assert "where" not in call_kwargs

    def test_top_k_clamped_to_collection_size(self):
        with patch("app.retrieval.search.embedder.embed", return_value=[[0.1]]):
            mock_col = MagicMock()
            mock_col.count.return_value = 3
            mock_col.query.return_value = self._make_chroma_result(
                ["c-0", "c-1", "c-2"], ["a", "b", "c"], ["d"] * 3, [1, 2, 3], [0.1, 0.2, 0.3]
            )
            with patch("app.retrieval.search.db.get_collection", return_value=mock_col):
                retrieval_search.search("שאלה", top_k=100)

        call_kwargs = mock_col.query.call_args.kwargs
        assert call_kwargs["n_results"] == 3  # clamped from 100 to collection size
