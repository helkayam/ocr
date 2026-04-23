from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from app.models import CitedSource, RAGResponse
from main import cli

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _runner() -> CliRunner:
    return CliRunner()


def _rag_response(answer: str = "תשובה לדוגמה", sources=None) -> RAGResponse:
    return RAGResponse(
        query="שאלה",
        answer=answer,
        sources=sources or [CitedSource(document_id="doc-001", page_num=3)],
    )


# ---------------------------------------------------------------------------
# CLI group / help
# ---------------------------------------------------------------------------

class TestCLIGroup:
    def test_help_exits_zero(self):
        result = _runner().invoke(cli, ["--help"])
        assert result.exit_code == 0

    def test_help_lists_commands(self):
        result = _runner().invoke(cli, ["--help"])
        for cmd in ("ingest", "ask", "delete", "reindex"):
            assert cmd in result.output

    def test_unknown_command_exits_nonzero(self):
        result = _runner().invoke(cli, ["nonexistent"])
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# ingest command
# ---------------------------------------------------------------------------

class TestIngestCommand:
    def test_calls_pipeline_with_path(self, tmp_path):
        pdf = tmp_path / "doc.pdf"
        pdf.write_bytes(b"%PDF-1.4\nminimal")
        with patch("app.pipeline.ingest_pipeline", return_value="doc-abc") as mock:
            result = _runner().invoke(cli, ["ingest", str(pdf)])
        mock.assert_called_once_with(str(pdf))

    def test_prints_document_id_on_success(self, tmp_path):
        pdf = tmp_path / "doc.pdf"
        pdf.write_bytes(b"%PDF-1.4\nminimal")
        with patch("app.pipeline.ingest_pipeline", return_value="doc-abc"):
            result = _runner().invoke(cli, ["ingest", str(pdf)])
        assert "doc-abc" in result.output
        assert result.exit_code == 0

    def test_prints_source_file_on_success(self, tmp_path):
        pdf = tmp_path / "doc.pdf"
        pdf.write_bytes(b"%PDF-1.4\nminimal")
        with patch("app.pipeline.ingest_pipeline", return_value="doc-xyz"):
            result = _runner().invoke(cli, ["ingest", str(pdf)])
        assert str(pdf) in result.output

    def test_nonexistent_path_exits_nonzero(self):
        result = _runner().invoke(cli, ["ingest", "/no/such/file.pdf"])
        assert result.exit_code != 0

    def test_pipeline_error_exits_nonzero(self, tmp_path):
        pdf = tmp_path / "doc.pdf"
        pdf.write_bytes(b"%PDF-1.4\nminimal")
        with patch("app.pipeline.ingest_pipeline", side_effect=ValueError("duplicate")):
            result = _runner().invoke(cli, ["ingest", str(pdf)])
        assert result.exit_code != 0

    def test_pipeline_error_shows_friendly_message(self, tmp_path):
        pdf = tmp_path / "doc.pdf"
        pdf.write_bytes(b"%PDF-1.4\nminimal")
        with patch("app.pipeline.ingest_pipeline", side_effect=ValueError("duplicate file")):
            result = _runner().invoke(cli, ["ingest", str(pdf)])
        # Exit code 1, no raw Python traceback in stdout
        assert "Traceback" not in result.output

    def test_debug_flag_reraises_exception(self, tmp_path):
        pdf = tmp_path / "doc.pdf"
        pdf.write_bytes(b"%PDF-1.4\nminimal")
        with patch("app.pipeline.ingest_pipeline", side_effect=RuntimeError("boom")):
            result = _runner().invoke(cli, ["--debug", "ingest", str(pdf)])
        assert result.exception is not None
        assert isinstance(result.exception, RuntimeError)


# ---------------------------------------------------------------------------
# ask command
# ---------------------------------------------------------------------------

class TestAskCommand:
    def test_calls_pipeline_with_query(self):
        with patch("app.pipeline.ask_pipeline", return_value=_rag_response()) as mock:
            _runner().invoke(cli, ["ask", "מה שם המסמך?"])
        mock.assert_called_once_with("מה שם המסמך?", top_k=5)

    def test_top_k_option_passed_through(self):
        with patch("app.pipeline.ask_pipeline", return_value=_rag_response()) as mock:
            _runner().invoke(cli, ["ask", "שאלה", "--top-k", "10"])
        mock.assert_called_once_with("שאלה", top_k=10)

    def test_answer_printed(self):
        with patch("app.pipeline.ask_pipeline", return_value=_rag_response("זוהי התשובה")):
            result = _runner().invoke(cli, ["ask", "שאלה"])
        assert "זוהי התשובה" in result.output

    def test_sources_printed(self):
        sources = [
            CitedSource(document_id="doc-001", page_num=3),
            CitedSource(document_id="doc-002", page_num=7),
        ]
        with patch("app.pipeline.ask_pipeline", return_value=_rag_response(sources=sources)):
            result = _runner().invoke(cli, ["ask", "שאלה"])
        assert "doc-001" in result.output
        assert "doc-002" in result.output
        assert "3" in result.output
        assert "7" in result.output

    def test_duplicate_sources_deduplicated(self):
        sources = [
            CitedSource(document_id="doc-001", page_num=3),
            CitedSource(document_id="doc-001", page_num=3),
        ]
        with patch("app.pipeline.ask_pipeline", return_value=_rag_response(sources=sources)):
            result = _runner().invoke(cli, ["ask", "שאלה"])
        assert result.output.count("doc-001") == 1

    def test_empty_sources_shown_gracefully(self):
        with patch("app.pipeline.ask_pipeline", return_value=_rag_response(sources=[])):
            result = _runner().invoke(cli, ["ask", "שאלה"])
        assert result.exit_code == 0
        assert "none" in result.output.lower() or "Sources" in result.output

    def test_pipeline_error_exits_nonzero(self):
        with patch("app.pipeline.ask_pipeline", side_effect=RuntimeError("groq error")):
            result = _runner().invoke(cli, ["ask", "שאלה"])
        assert result.exit_code != 0

    def test_invalid_top_k_exits_nonzero(self):
        result = _runner().invoke(cli, ["ask", "שאלה", "--top-k", "0"])
        assert result.exit_code != 0

    def test_exit_code_zero_on_success(self):
        with patch("app.pipeline.ask_pipeline", return_value=_rag_response()):
            result = _runner().invoke(cli, ["ask", "שאלה"])
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# delete command
# ---------------------------------------------------------------------------

class TestDeleteCommand:
    def test_calls_pipeline_with_doc_id(self):
        with patch("app.pipeline.delete_pipeline") as mock:
            _runner().invoke(cli, ["delete", "doc-001"])
        mock.assert_called_once_with("doc-001")

    def test_prints_confirmation_on_success(self):
        with patch("app.pipeline.delete_pipeline"):
            result = _runner().invoke(cli, ["delete", "doc-001"])
        assert "doc-001" in result.output
        assert result.exit_code == 0

    def test_not_found_exits_nonzero(self):
        with patch("app.pipeline.delete_pipeline", side_effect=KeyError("doc-999")):
            result = _runner().invoke(cli, ["delete", "doc-999"])
        assert result.exit_code != 0

    def test_not_found_shows_friendly_message(self):
        with patch("app.pipeline.delete_pipeline", side_effect=KeyError("doc-999")):
            result = _runner().invoke(cli, ["delete", "doc-999"])
        assert "Traceback" not in result.output

    def test_pipeline_error_exits_nonzero(self):
        with patch("app.pipeline.delete_pipeline", side_effect=OSError("disk error")):
            result = _runner().invoke(cli, ["delete", "doc-001"])
        assert result.exit_code != 0

    def test_debug_flag_reraises(self):
        with patch("app.pipeline.delete_pipeline", side_effect=KeyError("doc-999")):
            result = _runner().invoke(cli, ["--debug", "delete", "doc-999"])
        assert isinstance(result.exception, KeyError)


# ---------------------------------------------------------------------------
# reindex command
# ---------------------------------------------------------------------------

class TestReindexCommand:
    def test_calls_pipeline_with_doc_id(self):
        with patch("app.pipeline.reindex_pipeline", return_value=42) as mock:
            _runner().invoke(cli, ["reindex", "doc-001"])
        mock.assert_called_once_with("doc-001")

    def test_prints_vector_count_on_success(self):
        with patch("app.pipeline.reindex_pipeline", return_value=42):
            result = _runner().invoke(cli, ["reindex", "doc-001"])
        assert "42" in result.output
        assert result.exit_code == 0

    def test_prints_doc_id_on_success(self):
        with patch("app.pipeline.reindex_pipeline", return_value=5):
            result = _runner().invoke(cli, ["reindex", "doc-abc"])
        assert "doc-abc" in result.output

    def test_not_found_exits_nonzero(self):
        with patch("app.pipeline.reindex_pipeline", side_effect=KeyError("doc-999")):
            result = _runner().invoke(cli, ["reindex", "doc-999"])
        assert result.exit_code != 0

    def test_missing_chunks_exits_nonzero(self):
        with patch("app.pipeline.reindex_pipeline", side_effect=FileNotFoundError("chunks missing")):
            result = _runner().invoke(cli, ["reindex", "doc-001"])
        assert result.exit_code != 0

    def test_friendly_message_without_debug(self):
        with patch("app.pipeline.reindex_pipeline", side_effect=KeyError("doc-999")):
            result = _runner().invoke(cli, ["reindex", "doc-999"])
        assert "Traceback" not in result.output

    def test_exit_zero_on_success(self):
        with patch("app.pipeline.reindex_pipeline", return_value=0):
            result = _runner().invoke(cli, ["reindex", "doc-001"])
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# app/pipeline.py unit tests (no CLI)
# ---------------------------------------------------------------------------

class TestPipelineFunctions:
    """Test orchestration logic directly, without invoking the CLI."""

    def test_ingest_pipeline_calls_all_phases(self, tmp_path):
        with patch("app.pipeline.ingest_manager.ingest", return_value="d1") as p2, \
             patch("app.pipeline.ocr_processor.process") as p3, \
             patch("app.pipeline.splitter.split", return_value=[MagicMock()]) as p4, \
             patch("app.pipeline.indexer.index", return_value=1) as p5:
            from app.pipeline import ingest_pipeline
            doc_id = ingest_pipeline("fake.pdf")

        assert doc_id == "d1"
        p2.assert_called_once_with("fake.pdf")
        p3.assert_called_once_with("d1")
        p4.assert_called_once_with("d1")
        p5.assert_called_once_with("d1")

    def test_ask_pipeline_calls_generator(self):
        with patch("app.pipeline.generator.answer", return_value=_rag_response()) as mock:
            from app.pipeline import ask_pipeline
            result = ask_pipeline("שאלה", top_k=7)
        mock.assert_called_once_with("שאלה", top_k=7)
        assert isinstance(result, RAGResponse)

    def test_delete_pipeline_calls_all_deletions(self):
        import app.registry as registry
        from datetime import datetime, timezone
        from app.models import DocumentRecord, DocumentStatus

        with patch("app.pipeline.registry.get", return_value=MagicMock()), \
             patch("app.pipeline.indexer.delete_document") as del_vecs, \
             patch("app.pipeline.registry.delete") as del_reg:
            # Simulate no files on disk
            with patch("pathlib.Path.exists", return_value=False):
                from app.pipeline import delete_pipeline
                delete_pipeline("doc-x")

        del_vecs.assert_called_once_with("doc-x")
        del_reg.assert_called_once_with("doc-x")

    def test_delete_pipeline_raises_for_unknown_doc(self):
        with patch("app.pipeline.registry.get", return_value=None):
            from app.pipeline import delete_pipeline
            with pytest.raises(KeyError):
                delete_pipeline("ghost-doc")

    def test_reindex_pipeline_deletes_then_indexes(self):
        with patch("app.pipeline.registry.get", return_value=MagicMock()), \
             patch("pathlib.Path.exists", return_value=True), \
             patch("app.pipeline.indexer.delete_document") as del_vecs, \
             patch("app.pipeline.indexer.index", return_value=10) as idx:
            from app.pipeline import reindex_pipeline
            count = reindex_pipeline("doc-y")

        del_vecs.assert_called_once_with("doc-y")
        idx.assert_called_once_with("doc-y")
        assert count == 10

    def test_reindex_pipeline_raises_for_unknown_doc(self):
        with patch("app.pipeline.registry.get", return_value=None):
            from app.pipeline import reindex_pipeline
            with pytest.raises(KeyError):
                reindex_pipeline("ghost-doc")

    def test_reindex_pipeline_raises_when_chunks_missing(self):
        with patch("app.pipeline.registry.get", return_value=MagicMock()), \
             patch("pathlib.Path.exists", return_value=False):
            from app.pipeline import reindex_pipeline
            with pytest.raises(FileNotFoundError, match="Chunks file not found"):
                reindex_pipeline("doc-no-chunks")
