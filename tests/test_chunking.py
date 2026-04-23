from __future__ import annotations

import json
from pathlib import Path
from typing import List

import pytest

import app.registry as registry
from app.chunking import splitter
from app.chunking.splitter import _chunk_page, _is_header, _split_text
from app.models import Block, Chunk, DocumentStatus, OCRResult


# ---------------------------------------------------------------------------
# Helpers to build Block / OCRResult fixtures
# ---------------------------------------------------------------------------

def _block(
    text: str,
    block_type: str = "text",
    ratio: float = 1.0,
    font_size: float = 12.0,
    line_count: int = 1,
) -> Block:
    return Block(
        text=text,
        type=block_type,
        y_top=0.0,
        y_bottom=font_size,
        font_size=font_size,
        ratio_to_body=ratio,
        line_count=line_count,
    )


def _ocr_json(blocks_by_page: List[List[Block]], file_name: str = "test.pdf") -> str:
    pages = [
        {
            "page_num": i + 1,
            "stats": {"median_font_size": 12.0, "max_font_size": 18.0},
            "blocks": [b.model_dump(mode="json") for b in page_blocks],
        }
        for i, page_blocks in enumerate(blocks_by_page)
    ]
    return json.dumps({"file_name": file_name, "pages": pages}, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def isolated_env(tmp_path, monkeypatch):
    monkeypatch.setattr(registry, "REGISTRY_PATH", tmp_path / "registry.json")
    monkeypatch.setattr(splitter, "OCR_DIR", tmp_path / "ocr")
    monkeypatch.setattr(splitter, "CHUNKS_DIR", tmp_path / "chunks")


@pytest.fixture()
def registered_doc(tmp_path) -> str:
    """Write a registry entry and return a document_id."""
    from datetime import datetime, timezone
    from app.models import DocumentRecord
    doc_id = "doc-test-001"
    registry.add(DocumentRecord(
        document_id=doc_id,
        file_name="test.pdf",
        status=DocumentStatus.ocr_completed,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        file_hash="abc123",
    ))
    return doc_id


def _write_ocr(tmp_path, doc_id: str, blocks_by_page: List[List[Block]]) -> None:
    ocr_dir = tmp_path / "ocr"
    ocr_dir.mkdir(parents=True, exist_ok=True)
    (ocr_dir / f"{doc_id}.json").write_text(
        _ocr_json(blocks_by_page), encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# _is_header unit tests
# ---------------------------------------------------------------------------

class TestIsHeader:
    def test_high_ratio_text_is_header(self):
        assert _is_header(_block("כותרת", ratio=1.5)) is True

    def test_exact_threshold_is_header(self):
        assert _is_header(_block("כותרת", ratio=1.2)) is True

    def test_below_threshold_is_not_header(self):
        assert _is_header(_block("גוף", ratio=1.19)) is False

    def test_table_block_is_never_header(self):
        assert _is_header(_block("| א | ב |", block_type="table", ratio=2.0)) is False

    def test_body_text_is_not_header(self):
        assert _is_header(_block("פסקה רגילה", ratio=1.0)) is False


# ---------------------------------------------------------------------------
# _split_text unit tests
# ---------------------------------------------------------------------------

class TestSplitText:
    def test_short_text_returns_single_chunk(self):
        assert _split_text("hello", 500, 50) == ["hello"]

    def test_text_exactly_chunk_size_returns_single_chunk(self):
        text = "a" * 500
        result = _split_text(text, 500, 50)
        assert result == [text]

    def test_long_text_splits_into_multiple_chunks(self):
        text = "a" * 1100
        chunks = _split_text(text, 500, 50)
        assert len(chunks) > 1

    def test_chunk_sizes_do_not_exceed_limit(self):
        text = "b" * 2000
        for chunk in _split_text(text, 500, 50):
            assert len(chunk) <= 500

    def test_overlap_is_respected(self):
        text = "abcdefghij"  # 10 chars
        chunks = _split_text(text, 6, 2)
        # chunk 0: [0:6] = "abcdef", chunk 1: [4:10] = "efghij"
        assert chunks[0][-2:] == chunks[1][:2]

    def test_full_text_is_covered(self):
        text = "x" * 1300
        chunks = _split_text(text, 500, 50)
        # Last chunk must reach the end of the text
        assert chunks[-1] == text[len(text) - len(chunks[-1]):]
        assert text.endswith(chunks[-1])

    def test_empty_text_returns_empty_list(self):
        assert _split_text("", 500, 50) == []

    def test_whitespace_only_returns_empty_list(self):
        assert _split_text("   \n  ", 500, 50) == []


# ---------------------------------------------------------------------------
# _chunk_page unit tests
# ---------------------------------------------------------------------------

class TestChunkPage:
    DOC_ID = "doc-001"
    PAGE = 1

    def _run(self, blocks, chunk_size=500, chunk_overlap=50):
        return _chunk_page(self.DOC_ID, self.PAGE, blocks, chunk_size, chunk_overlap)

    # --- Header attachment ---

    def test_header_prepended_to_following_text(self):
        blocks = [
            _block("פרק ראשון", ratio=1.5),    # header
            _block("תוכן הפרק"),               # body
        ]
        chunks = self._run(blocks)
        assert len(chunks) == 1
        assert "פרק ראשון" in chunks[0].text
        assert "תוכן הפרק" in chunks[0].text

    def test_header_appears_before_content_in_text(self):
        blocks = [
            _block("כותרת", ratio=1.5),
            _block("פסקה"),
        ]
        chunks = self._run(blocks)
        text = chunks[0].text
        assert text.index("כותרת") < text.index("פסקה")

    def test_multiple_consecutive_headers_all_prepended(self):
        blocks = [
            _block("פרק א", ratio=1.8),
            _block("סעיף 1", ratio=1.4),
            _block("תוכן"),
        ]
        chunks = self._run(blocks)
        assert len(chunks) == 1
        assert "פרק א" in chunks[0].text
        assert "סעיף 1" in chunks[0].text
        assert "תוכן" in chunks[0].text

    def test_trailing_header_emitted_as_standalone(self):
        blocks = [_block("כותרת בסוף עמוד", ratio=1.5)]
        chunks = self._run(blocks)
        assert len(chunks) == 1
        assert chunks[0].metadata.is_header is True
        assert chunks[0].text == "כותרת בסוף עמוד"

    def test_content_chunk_is_not_flagged_as_header(self):
        blocks = [
            _block("כותרת", ratio=1.5),
            _block("תוכן"),
        ]
        chunks = self._run(blocks)
        assert chunks[0].metadata.is_header is False

    def test_header_block_ids_stored_in_extra(self):
        blocks = [
            _block("כותרת", ratio=1.5),   # block_id=0
            _block("תוכן"),                # block_id=1
        ]
        chunks = self._run(blocks)
        assert chunks[0].metadata.extra["header_block_ids"] == [0]

    def test_multiple_header_block_ids_in_extra(self):
        blocks = [
            _block("פרק", ratio=1.8),    # block_id=0
            _block("סעיף", ratio=1.4),   # block_id=1
            _block("תוכן"),               # block_id=2
        ]
        chunks = self._run(blocks)
        assert chunks[0].metadata.extra["header_block_ids"] == [0, 1]

    def test_chunk_without_header_has_empty_extra(self):
        blocks = [_block("פשוט")]
        chunks = self._run(blocks)
        assert chunks[0].metadata.extra == {}

    # --- Table integrity ---

    def test_table_kept_as_single_chunk(self):
        table_text = "| א | ב |\n| --- | --- |\n" + "| x | y |\n" * 50
        blocks = [_block(table_text, block_type="table")]
        chunks = self._run(blocks, chunk_size=100)
        assert len(chunks) == 1
        assert chunks[0].text == table_text
        assert chunks[0].metadata.block_type == "table"

    def test_header_prepended_to_table(self):
        blocks = [
            _block("טבלת תוצאות", ratio=1.5),
            _block("| א | ב |", block_type="table"),
        ]
        chunks = self._run(blocks)
        assert len(chunks) == 1
        assert "טבלת תוצאות" in chunks[0].text
        assert "| א | ב |" in chunks[0].text

    def test_table_chunk_is_not_split_regardless_of_size(self):
        long_table = "| col |\n| --- |\n" + "| row |\n" * 200
        blocks = [_block(long_table, block_type="table")]
        chunks = self._run(blocks, chunk_size=50)
        assert len(chunks) == 1

    # --- Chunk size / overlap ---

    def test_long_text_produces_multiple_chunks(self):
        long_text = "א" * 1200
        blocks = [_block(long_text)]
        chunks = self._run(blocks, chunk_size=500, chunk_overlap=50)
        assert len(chunks) > 1

    def test_all_sub_chunks_within_size_limit(self):
        long_text = "ב" * 2000
        blocks = [_block(long_text)]
        for chunk in self._run(blocks, chunk_size=500, chunk_overlap=50):
            assert len(chunk.text) <= 500

    def test_overlap_links_consecutive_sub_chunks(self):
        long_text = "abcdefghijklmnopqrstuvwxyz" * 30  # 780 chars
        blocks = [_block(long_text)]
        chunks = self._run(blocks, chunk_size=200, chunk_overlap=40)
        for i in range(len(chunks) - 1):
            tail = chunks[i].text[-40:]
            head = chunks[i + 1].text[:40]
            assert tail == head, "Overlap boundary mismatch"

    # --- Metadata integrity ---

    def test_every_chunk_has_correct_document_id(self):
        blocks = [_block("טקסט"), _block("| t |", block_type="table")]
        for chunk in self._run(blocks):
            assert chunk.document_id == self.DOC_ID
            assert chunk.metadata.document_id == self.DOC_ID

    def test_every_chunk_has_correct_page_num(self):
        blocks = [_block("טקסט")]
        for chunk in self._run(blocks):
            assert chunk.page == self.PAGE
            assert chunk.metadata.page_num == self.PAGE

    def test_block_type_propagated_to_metadata(self):
        blocks = [
            _block("טקסט"),
            _block("| a |", block_type="table"),
        ]
        chunks = self._run(blocks)
        types = {c.metadata.block_type for c in chunks}
        assert "text" in types
        assert "table" in types

    def test_chunk_ids_are_unique(self):
        long_text = "ג" * 2000
        blocks = [_block(long_text), _block("| t |", block_type="table")]
        chunks = self._run(blocks, chunk_size=500, chunk_overlap=50)
        ids = [c.chunk_id for c in chunks]
        assert len(ids) == len(set(ids))

    # --- Edge cases ---

    def test_empty_block_list_returns_no_chunks(self):
        assert self._run([]) == []

    def test_only_headers_no_text(self):
        blocks = [_block("כותרת א", ratio=1.5), _block("כותרת ב", ratio=1.5)]
        chunks = self._run(blocks)
        assert len(chunks) == 2
        assert all(c.metadata.is_header for c in chunks)

    def test_header_resets_after_content_block(self):
        blocks = [
            _block("כותרת 1", ratio=1.5),
            _block("תוכן 1"),
            _block("כותרת 2", ratio=1.5),
            _block("תוכן 2"),
        ]
        chunks = self._run(blocks)
        assert len(chunks) == 2
        assert "כותרת 1" in chunks[0].text and "תוכן 1" in chunks[0].text
        assert "כותרת 2" in chunks[1].text and "תוכן 2" in chunks[1].text
        assert "כותרת 1" not in chunks[1].text


# ---------------------------------------------------------------------------
# split() integration tests (full pipeline: OCR JSON → chunks file → registry)
# ---------------------------------------------------------------------------

class TestSplitFunction:
    def test_returns_chunks_list(self, registered_doc, tmp_path):
        _write_ocr(tmp_path, registered_doc, [[_block("טקסט")]])
        result = splitter.split(registered_doc)
        assert isinstance(result, list)
        assert all(isinstance(c, Chunk) for c in result)

    def test_chunks_file_created(self, registered_doc, tmp_path):
        _write_ocr(tmp_path, registered_doc, [[_block("טקסט")]])
        splitter.split(registered_doc)
        out = tmp_path / "chunks" / f"{registered_doc}_chunks.json"
        assert out.exists()

    def test_chunks_file_valid_json_roundtrip(self, registered_doc, tmp_path):
        _write_ocr(tmp_path, registered_doc, [[_block("תוכן")]])
        original = splitter.split(registered_doc)
        out = tmp_path / "chunks" / f"{registered_doc}_chunks.json"
        reloaded = [Chunk(**c) for c in json.loads(out.read_text(encoding="utf-8"))]
        assert len(reloaded) == len(original)
        assert reloaded[0].chunk_id == original[0].chunk_id

    def test_registry_updated_to_chunked(self, registered_doc, tmp_path):
        _write_ocr(tmp_path, registered_doc, [[_block("טקסט")]])
        splitter.split(registered_doc)
        assert registry.get(registered_doc).status == DocumentStatus.chunked

    def test_chunks_dir_created_if_missing(self, registered_doc, tmp_path):
        _write_ocr(tmp_path, registered_doc, [[_block("טקסט")]])
        assert not (tmp_path / "chunks").exists()
        splitter.split(registered_doc)
        assert (tmp_path / "chunks").exists()

    def test_missing_ocr_json_raises(self):
        with pytest.raises(FileNotFoundError, match="OCR JSON not found"):
            splitter.split("ghost-doc-id")

    def test_multipage_document_chunks_all_pages(self, registered_doc, tmp_path):
        _write_ocr(tmp_path, registered_doc, [
            [_block("עמוד 1")],
            [_block("עמוד 2")],
            [_block("עמוד 3")],
        ])
        chunks = splitter.split(registered_doc)
        pages = {c.page for c in chunks}
        assert pages == {1, 2, 3}

    def test_configurable_chunk_size(self, registered_doc, tmp_path):
        long_text = "ד" * 2000
        _write_ocr(tmp_path, registered_doc, [[_block(long_text)]])
        chunks = splitter.split(registered_doc, chunk_size=300, chunk_overlap=30)
        assert all(len(c.text) <= 300 for c in chunks)

    def test_empty_ocr_produces_no_chunks(self, registered_doc, tmp_path):
        _write_ocr(tmp_path, registered_doc, [])
        chunks = splitter.split(registered_doc)
        assert chunks == []
