"""
NLP Service — text extraction, chunking, embedding, semantic search.

Requires:
  - pypdf          (pip install pypdf)
  - python-docx    (pip install python-docx)
  - openai         (pip install openai)
  - numpy          (pip install numpy)

If OPENAI_API_KEY is not set the system falls back to simple keyword search.
"""

import io
import json
import math
import os
import uuid
from typing import List, Optional

import pypdf
from docx import Document

from db import get_db, db_available

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIM = 1536
CHUNK_SIZE = 800
CHUNK_OVERLAP = 150


# ---------------------------------------------------------------------------
# Text extraction
# ---------------------------------------------------------------------------

def extract_text(file_bytes: bytes, filename: str) -> str:
    fname = filename.lower()
    if fname.endswith(".pdf"):
        return _extract_pdf(file_bytes)
    if fname.endswith(".docx"):
        return _extract_docx(file_bytes)
    return ""


def _extract_pdf(data: bytes) -> str:
    reader = pypdf.PdfReader(io.BytesIO(data))
    parts = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            parts.append(text)
    return "\n\n".join(parts)


def _extract_docx(data: bytes) -> str:
    doc = Document(io.BytesIO(data))
    return "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

def chunk_text(text: str) -> List[str]:
    """Split text into overlapping chunks using paragraph/sentence boundaries."""
    if not text.strip():
        return []
    if len(text) <= CHUNK_SIZE:
        return [text.strip()]

    paragraphs = [p for p in text.split("\n\n") if p.strip()]
    chunks: List[str] = []
    current = ""

    for para in paragraphs:
        if len(current) + len(para) + 2 > CHUNK_SIZE:
            if current:
                chunks.append(current.strip())
                # carry-over overlap
                current = current[-CHUNK_OVERLAP:].lstrip() + "\n\n" + para
            else:
                # single paragraph longer than CHUNK_SIZE — split on sentences
                chunks.extend(_split_long(para))
                current = ""
        else:
            current = (current + "\n\n" + para).strip()

    if current.strip():
        chunks.append(current.strip())

    return [c for c in chunks if len(c) > 20]


def _split_long(text: str) -> List[str]:
    chunks: List[str] = []
    start = 0
    while start < len(text):
        end = start + CHUNK_SIZE
        if end < len(text):
            for sep in (". ", "\n", " "):
                idx = text.rfind(sep, start, end)
                if idx > start:
                    end = idx + len(sep)
                    break
        chunks.append(text[start:end].strip())
        start = end - CHUNK_OVERLAP
    return [c for c in chunks if c]


# ---------------------------------------------------------------------------
# Embeddings
# ---------------------------------------------------------------------------

def get_embeddings(texts: List[str]) -> List[List[float]]:
    if not OPENAI_API_KEY or not texts:
        return [[0.0] * EMBEDDING_DIM for _ in texts]
    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)
        # OpenAI limits batch size to 2048 inputs
        result: List[List[float]] = []
        for i in range(0, len(texts), 100):
            batch = texts[i:i + 100]
            resp = client.embeddings.create(input=batch, model=EMBEDDING_MODEL)
            result.extend(item.embedding for item in resp.data)
        return result
    except Exception as e:
        print(f"Embedding error: {e}")
        return [[0.0] * EMBEDDING_DIM for _ in texts]


def _cosine(a: List[float], b: List[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


# ---------------------------------------------------------------------------
# Background processing task
# ---------------------------------------------------------------------------

def process_file(file_id: str, workspace_id: str, filename: str, object_name: str) -> None:
    """Download, extract, chunk, embed, persist. Runs as a background task."""
    if not db_available():
        return

    _set_status(file_id, "processing")
    try:
        from services.storage_service import get_file_bytes
        raw = get_file_bytes(object_name)
    except Exception as e:
        print(f"[nlp] Could not download {object_name}: {e}")
        _set_status(file_id, "error")
        return

    text = extract_text(raw, filename)
    if not text.strip():
        _set_status(file_id, "done")
        return

    chunks = chunk_text(text)
    embeddings = get_embeddings(chunks)

    try:
        with get_db() as cur:
            cur.execute("DELETE FROM document_chunks WHERE file_id = %s", (file_id,))
            for idx, (chunk, emb) in enumerate(zip(chunks, embeddings)):
                cur.execute(
                    """
                    INSERT INTO document_chunks
                        (chunk_id, file_id, workspace_id, content, chunk_index, embedding)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (str(uuid.uuid4()), file_id, workspace_id, chunk, idx, json.dumps(emb)),
                )
            cur.execute(
                "UPDATE files SET processing_status = 'done' WHERE file_id = %s",
                (file_id,),
            )
        print(f"[nlp] {filename}: {len(chunks)} chunks stored")
    except Exception as e:
        print(f"[nlp] DB write error for {file_id}: {e}")
        _set_status(file_id, "error")


def _set_status(file_id: str, status: str) -> None:
    try:
        with get_db() as cur:
            cur.execute(
                "UPDATE files SET processing_status = %s WHERE file_id = %s",
                (status, file_id),
            )
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Semantic search
# ---------------------------------------------------------------------------

def search_chunks(workspace_id: str, query: str, top_k: int = 5) -> List[dict]:
    if not db_available():
        return []

    try:
        with get_db() as cur:
            cur.execute(
                """
                SELECT dc.chunk_id, dc.file_id, dc.content, dc.embedding, f.filename
                FROM document_chunks dc
                JOIN files f ON f.file_id = dc.file_id
                WHERE dc.workspace_id = %s
                """,
                (workspace_id,),
            )
            rows = [dict(r) for r in cur.fetchall()]
    except Exception as e:
        print(f"[nlp] search DB error: {e}")
        return []

    if not rows:
        return []

    # Fallback: keyword search when embeddings are zero vectors / no API key
    if not OPENAI_API_KEY:
        q = query.lower()
        hits = [r for r in rows if q in r["content"].lower()]
        return [
            {
                "chunk_id": r["chunk_id"],
                "file_id": r["file_id"],
                "filename": r["filename"],
                "content": r["content"],
                "score": 1.0,
            }
            for r in hits[:top_k]
        ]

    query_vec = get_embeddings([query])[0]
    scored = []
    for r in rows:
        emb = r["embedding"]
        if emb is None:
            continue
        if isinstance(emb, str):
            emb = json.loads(emb)
        score = _cosine(query_vec, emb)
        scored.append((score, r))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [
        {
            "chunk_id": r["chunk_id"],
            "file_id": r["file_id"],
            "filename": r["filename"],
            "content": r["content"],
            "score": round(score, 4),
        }
        for score, r in scored[:top_k]
        if score > 0.1
    ]
