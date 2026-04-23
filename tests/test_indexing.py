from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List
from unittest.mock import MagicMock, patch

import pytest

import app.registry as registry
from app.indexing import db, indexer
from app.models import (
    Block, Chunk, ChunkMetadata, DocumentRecord, DocumentStatus,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Fixed-dimension mock embeddings (4-d is enough for ChromaDB tests)
_EMBED_DIM = 4


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_chunk(
    chunk_id: str,
    document_id: str = "doc-001",
    page: int = 1,
    block_id: int = 0,
    text: str = "טקסט לדוגמה",
    block_type: str = "text",
    is_header: bool = False,
) -> Chunk:
    return Chunk(
        chunk_id=chunk_id,
        document_id=document_id,
        page=page,
        text=text,
        metadata=ChunkMetadata(
            document_id=document_id,
            page_num=page,
            block_id=block_id,
            is_header=is_header,
            block_type=block_type,
            extra={},
        ),
    )


def _fake_embed(texts: List[str]) -> List[List[float]]:
    """Return deterministic unit vectors without loading any model."""
    return [[float(i % _EMBED_DIM == j) for j in range(_EMBED_DIM)] for i, _ in enumerate(texts)]


def _write_chunks(tmp_path: Path, doc_id: str, chunks: List[Chunk]) -> None:
    chunks_dir = tmp_path / "chunks"
    chunks_dir.mkdir(parents=True, exist_ok=True)
    (chunks_dir / f"{doc_id}_chunks.json").write_text(
        json.dumps([c.model_dump(mode="json") for c in chunks], ensure_ascii=False),
        encoding="utf-8",
    )


def _register_doc(doc_id: str, status: DocumentStatus = DocumentStatus.chunked) -> None:
    registry.add(DocumentRecord(
        document_id=doc_id,
        file_name="test.pdf",
        status=status,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        file_hash="deadbeef",
    ))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def isolated_env(tmp_path, monkeypatch):
    """Redirect all paths and registry to temp dirs for every test."""
    monkeypatch.setattr(registry, "REGISTRY_PATH", tmp_path / "registry.json")
    monkeypatch.setattr(indexer, "CHUNKS_DIR", tmp_path / "chunks")
    monkeypatch.setattr(indexer, "INDEX_DIR", tmp_path / "index")
    monkeypatch.setattr(db, "INDEX_DIR", tmp_path / "index")


@pytest.fixture()
def mock_embed():
    """Patch embedder.embed so no model is loaded during tests."""
    with patch("app.indexing.indexer.embedder.embed", side_effect=_fake_embed) as m:
        yield m


# ---------------------------------------------------------------------------
# db.get_collection tests
# ---------------------------------------------------------------------------

class TestGetCollection:
    def test_creates_collection_and_dir(self, tmp_path):
        idx_dir = tmp_path / "idx"
        col = db.get_collection(idx_dir)
        assert idx_dir.exists()
        assert col is not None

    def test_returns_same_logical_collection(self, tmp_path):
        idx_dir = tmp_path / "idx"
        col1 = db.get_collection(idx_dir)
        col2 = db.get_collection(idx_dir)
        assert col1.name == col2.name


# ---------------------------------------------------------------------------
# indexer._to_chroma_metadata tests
# ---------------------------------------------------------------------------

class TestToChromaMetadata:
    def test_all_required_keys_present(self):
        chunk = _make_chunk("c-1", is_header=True, block_type="table")
        meta = indexer._to_chroma_metadata(chunk)
        for key in ("document_id", "page_num", "block_id", "is_header", "block_type", "extra"):
            assert key in meta

    def test_values_are_scalar(self):
        chunk = _make_chunk("c-1")
        chunk.metadata.extra = {"header_block_ids": [0, 1]}
        meta = indexer._to_chroma_metadata(chunk)
        for v in meta.values():
            assert isinstance(v, (str, int, float, bool)), f"Non-scalar value: {v!r}"

    def test_extra_serialised_as_json_string(self):
        chunk = _make_chunk("c-1")
        chunk.metadata.extra = {"header_block_ids": [2, 3]}
        meta = indexer._to_chroma_metadata(chunk)
        parsed = json.loads(meta["extra"])
        assert parsed["header_block_ids"] == [2, 3]

    def test_is_header_bool(self):
        chunk = _make_chunk("c-1", is_header=True)
        assert indexer._to_chroma_metadata(chunk)["is_header"] is True


# ---------------------------------------------------------------------------
# indexer.index tests
# ---------------------------------------------------------------------------

class TestIndex:
    DOC = "doc-001"

    def test_returns_chunk_count(self, tmp_path, mock_embed):
        chunks = [_make_chunk(f"c-{i}", document_id=self.DOC) for i in range(3)]
        _write_chunks(tmp_path, self.DOC, chunks)
        _register_doc(self.DOC)
        assert indexer.index(self.DOC) == 3

    def test_registry_updated_to_indexed(self, tmp_path, mock_embed):
        _write_chunks(tmp_path, self.DOC, [_make_chunk("c-0", document_id=self.DOC)])
        _register_doc(self.DOC)
        indexer.index(self.DOC)
        assert registry.get(self.DOC).status == DocumentStatus.indexed

    def test_missing_chunks_file_raises(self):
        with pytest.raises(FileNotFoundError, match="Chunks file not found"):
            indexer.index("ghost-doc")

    def test_chunks_queryable_after_index(self, tmp_path, mock_embed):
        chunks = [_make_chunk("c-0", document_id=self.DOC, text="פסקה בעברית")]
        _write_chunks(tmp_path, self.DOC, chunks)
        _register_doc(self.DOC)
        indexer.index(self.DOC)

        col = db.get_collection(tmp_path / "index")
        result = col.query(query_embeddings=[_fake_embed(["שאילתה"])[0]], n_results=1)
        assert result["ids"][0] == ["c-0"]
        assert result["documents"][0] == ["פסקה בעברית"]

    def test_metadata_stored_correctly(self, tmp_path, mock_embed):
        chunk = _make_chunk("c-0", document_id=self.DOC, page=3, block_id=5, block_type="table")
        _write_chunks(tmp_path, self.DOC, [chunk])
        _register_doc(self.DOC)
        indexer.index(self.DOC)

        col = db.get_collection(tmp_path / "index")
        result = col.get(ids=["c-0"], include=["metadatas"])
        meta = result["metadatas"][0]
        assert meta["document_id"] == self.DOC
        assert meta["page_num"] == 3
        assert meta["block_id"] == 5
        assert meta["block_type"] == "table"

    def test_embed_called_with_chunk_texts(self, tmp_path, mock_embed):
        texts = ["טקסט א", "טקסט ב"]
        chunks = [_make_chunk(f"c-{i}", document_id=self.DOC, text=t) for i, t in enumerate(texts)]
        _write_chunks(tmp_path, self.DOC, chunks)
        _register_doc(self.DOC)
        indexer.index(self.DOC)
        # embed was called; collect all texts it received
        all_texts = [t for call in mock_embed.call_args_list for t in call.args[0]]
        assert set(all_texts) == set(texts)

    def test_empty_chunks_still_updates_registry(self, tmp_path, mock_embed):
        _write_chunks(tmp_path, self.DOC, [])
        _register_doc(self.DOC)
        count = indexer.index(self.DOC)
        assert count == 0
        assert registry.get(self.DOC).status == DocumentStatus.indexed

    def test_batching_indexes_all_chunks(self, tmp_path, mock_embed, monkeypatch):
        monkeypatch.setattr(indexer, "_UPSERT_BATCH_SIZE", 3)
        chunks = [_make_chunk(f"c-{i}", document_id=self.DOC) for i in range(7)]
        _write_chunks(tmp_path, self.DOC, chunks)
        _register_doc(self.DOC)
        indexer.index(self.DOC)

        col = db.get_collection(tmp_path / "index")
        result = col.get(where={"document_id": self.DOC})
        assert len(result["ids"]) == 7

    def test_upsert_is_idempotent(self, tmp_path, mock_embed):
        chunks = [_make_chunk("c-0", document_id=self.DOC)]
        _write_chunks(tmp_path, self.DOC, chunks)
        _register_doc(self.DOC)
        indexer.index(self.DOC)
        indexer.index(self.DOC)  # second call must not duplicate

        col = db.get_collection(tmp_path / "index")
        result = col.get(where={"document_id": self.DOC})
        assert len(result["ids"]) == 1


# ---------------------------------------------------------------------------
# indexer.delete_document tests
# ---------------------------------------------------------------------------

class TestDeleteDocument:
    DOC_A = "doc-aaa"
    DOC_B = "doc-bbb"

    def _index_doc(self, tmp_path, doc_id: str, n: int, mock_embed) -> None:
        chunks = [_make_chunk(f"{doc_id}-c{i}", document_id=doc_id) for i in range(n)]
        _write_chunks(tmp_path, doc_id, chunks)
        _register_doc(doc_id)
        indexer.index(doc_id)

    def test_delete_removes_all_vectors(self, tmp_path, mock_embed):
        self._index_doc(tmp_path, self.DOC_A, 3, mock_embed)
        indexer.delete_document(self.DOC_A)

        col = db.get_collection(tmp_path / "index")
        result = col.get(where={"document_id": self.DOC_A})
        assert result["ids"] == [], "Vectors still present after delete"

    def test_delete_does_not_remove_other_documents(self, tmp_path, mock_embed):
        self._index_doc(tmp_path, self.DOC_A, 2, mock_embed)
        self._index_doc(tmp_path, self.DOC_B, 2, mock_embed)
        indexer.delete_document(self.DOC_A)

        col = db.get_collection(tmp_path / "index")
        remaining = col.get(where={"document_id": self.DOC_B})
        assert len(remaining["ids"]) == 2, "Deletion leaked into DOC_B"

    def test_delete_nonexistent_document_is_safe(self, tmp_path):
        # Must not raise even when nothing to delete
        indexer.delete_document("i-do-not-exist")

    def test_query_returns_empty_after_delete(self, tmp_path, mock_embed):
        self._index_doc(tmp_path, self.DOC_A, 2, mock_embed)
        indexer.delete_document(self.DOC_A)

        col = db.get_collection(tmp_path / "index")
        result = col.query(
            query_embeddings=[_fake_embed(["שאילתה"])[0]],
            n_results=1,
            where={"document_id": self.DOC_A},
        )
        assert result["ids"] == [[]], "Query returned results for deleted document"

    def test_reindex_after_delete_works(self, tmp_path, mock_embed):
        chunks = [_make_chunk("c-0", document_id=self.DOC_A, text="תוכן")]
        _write_chunks(tmp_path, self.DOC_A, chunks)
        _register_doc(self.DOC_A)
        indexer.index(self.DOC_A)
        indexer.delete_document(self.DOC_A)

        # Re-register (status was updated to indexed; reset for re-index)
        from app.models import DocumentStatus
        registry.update_status(self.DOC_A, DocumentStatus.chunked)
        indexer.index(self.DOC_A)

        col = db.get_collection(tmp_path / "index")
        result = col.get(where={"document_id": self.DOC_A})
        assert len(result["ids"]) == 1
