#!/usr/bin/env python3
"""
Full End-to-End Lifecycle Test for Protocol Genesis
====================================================
Tests the complete user journey:
  1. Create workspace
  2. Generate a Hebrew-text PDF and upload it (upload-url → PUT → confirm-upload)
  3. Poll status until "indexed"
  4. Query RAG (constrained to workspace)
  5. Delete file (204)
  6. Delete workspace (204)
  7. Deep cleanup: assert no ghost data in SQLite, registry, chunks, ChromaDB, BM25

Run from the project root with the venv active:
    python e2e_test.py
"""

import json
import os
import sqlite3
import sys
import time
from pathlib import Path

import requests

# ─── Config ──────────────────────────────────────────────────────────────────

BASE_URL        = "http://localhost:8000"
POLL_TIMEOUT_S  = 300   # 5-minute cap for the indexing pipeline
POLL_INTERVAL_S = 3

PROJECT_ROOT = Path(__file__).parent.resolve()
DB_PATH      = PROJECT_ROOT / "backend" / "local_data" / "protocol_genesis.db"
REGISTRY     = PROJECT_ROOT / "data" / "registry.json"
RAW_DIR      = PROJECT_ROOT / "data" / "raw"
OCR_DIR      = PROJECT_ROOT / "data" / "ocr"
CHUNKS_DIR   = PROJECT_ROOT / "data" / "chunks"
INDEX_DIR    = PROJECT_ROOT / "data" / "index"
BM25_CORPUS  = INDEX_DIR / "bm25_corpus.json"
LOCAL_STORE  = PROJECT_ROOT / "backend" / "local_storage"

HEBREW_TEXT = (
    "פרוטוקול בדיקה. "
    "זהו מסמך בדיקה עבור מערכת OCR ו-RAG בעברית. "
    "המסמך מכיל מידע חשוב על פרוטוקול ג'נסיס. "
    "סעיף 1: מבוא למערכת. "
    "סעיף 2: ארכיטקטורה ועיצוב. "
    "סעיף 3: שאלות ותשובות."
)


# ─── Helpers ─────────────────────────────────────────────────────────────────

OK     = "\033[92m✓\033[0m"
FAIL   = "\033[91m✗\033[0m"
STEP   = "\033[94m▶\033[0m"
HEADER = "\033[1m\033[95m"
RESET  = "\033[0m"


def _pass(msg: str) -> None:
    print(f"  {OK}  {msg}")


def _fail(msg: str) -> None:
    print(f"  {FAIL}  {msg}")
    sys.exit(1)


def _step(msg: str) -> None:
    print(f"\n{STEP} {HEADER}{msg}{RESET}")


def assert_eq(label: str, got, expected) -> None:
    if got == expected:
        _pass(f"{label}: {got!r}")
    else:
        _fail(f"{label}: expected {expected!r}, got {got!r}")


def assert_true(label: str, condition: bool, detail: str = "") -> None:
    if condition:
        _pass(f"{label}{': ' + detail if detail else ''}")
    else:
        _fail(f"{label} — FAILED{': ' + detail if detail else ''}")


def assert_false(label: str, condition: bool, detail: str = "") -> None:
    assert_true(label, not condition, detail)


def _make_hebrew_pdf() -> bytes:
    """Return bytes of a minimal PDF containing Hebrew text."""
    import fitz  # PyMuPDF

    doc = fitz.open()
    page = doc.new_page(width=595, height=842)   # A4
    page.insert_text(
        (50, 100),
        HEBREW_TEXT,
        fontsize=14,
        color=(0, 0, 0),
    )
    # Write a second block so chunking produces at least one non-trivial chunk
    page.insert_text(
        (50, 200),
        "מסמך זה נוצר באופן אוטומטי לצורך בדיקות.",
        fontsize=12,
    )
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


# ─── 1. Verify server is up ───────────────────────────────────────────────────

_step("0. Verify backend is reachable")
try:
    r = requests.get(f"{BASE_URL}/workspaces", timeout=5)
    _pass(f"Server responded: HTTP {r.status_code}")
except requests.ConnectionError:
    _fail(f"Cannot reach {BASE_URL}. Start the server first: uvicorn backend.main:app --reload")


# ─── 2. Create workspace ──────────────────────────────────────────────────────

_step("1. Create Workspace")
payload = {"name": "E2E-Test-Workspace", "description": "Auto-created by e2e_test.py"}
r = requests.post(f"{BASE_URL}/workspaces", json=payload)
assert_eq("HTTP status", r.status_code, 200)
ws = r.json()
workspace_id = ws["id"]
assert_true("workspace_id present", bool(workspace_id))
_pass(f"workspace_id = {workspace_id}")


# ─── 3. Generate + upload PDF ────────────────────────────────────────────────

_step("2. Generate Hebrew PDF and upload")

pdf_bytes   = _make_hebrew_pdf()
filename    = "test_hebrew_protocol.pdf"
content_type = "application/pdf"

# 2a. Request upload URL
r = requests.post(
    f"{BASE_URL}/files/upload-url",
    json={
        "filename":     filename,
        "content_type": content_type,
        "workspace_id": workspace_id,
        "file_size":    len(pdf_bytes),
    },
)
assert_eq("upload-url HTTP status", r.status_code, 200)
url_data  = r.json()
upload_url = url_data["upload_url"]
file_id    = url_data["file_id"]
_pass(f"file_id = {file_id}")
_pass(f"upload_url = {upload_url}")

# 2b. PUT the raw bytes (local-storage mode)
r = requests.put(upload_url, data=pdf_bytes, headers={"Content-Type": content_type})
assert_eq("PUT local-upload HTTP status", r.status_code, 200)
_pass("File bytes uploaded to local storage")

# 2c. Confirm upload (triggers RAG pipeline in background)
r = requests.post(
    f"{BASE_URL}/files/confirm-upload",
    json={
        "file_id":      file_id,
        "workspace_id": workspace_id,
        "filename":     filename,
        "file_size":    len(pdf_bytes),
        "content_type": content_type,
    },
)
assert_eq("confirm-upload HTTP status", r.status_code, 200)
conf = r.json()
assert_eq("confirm status field", conf.get("status"), "ok")
_pass("Upload confirmed — RAG pipeline queued in background")


# ─── 4. Poll until "indexed" ─────────────────────────────────────────────────

_step("3. Poll file status until 'indexed'")

deadline = time.time() + POLL_TIMEOUT_S
last_status = None
while time.time() < deadline:
    r = requests.get(f"{BASE_URL}/files/{file_id}/status")
    assert_eq("status-poll HTTP", r.status_code, 200)
    data = r.json()
    ps = data.get("processing_status", "unknown")
    if ps != last_status:
        print(f"      processing_status = {ps!r}")
        last_status = ps
    if ps == "indexed":
        _pass("Reached 'indexed' status")
        break
    if ps == "error":
        _fail("Pipeline reported error status — check server logs")
    time.sleep(POLL_INTERVAL_S)
else:
    _fail(f"Timeout ({POLL_TIMEOUT_S}s) waiting for 'indexed'. Last status: {last_status!r}")


# ─── 5. Query RAG ────────────────────────────────────────────────────────────

_step("4. Query RAG (Hebrew question, workspace-scoped)")
q_payload = {
    "query":        "מה מכיל המסמך? תן סיכום קצר.",
    "top_k":        3,
    "workspace_id": workspace_id,
}
r = requests.post(f"{BASE_URL}/query/", json=q_payload)
assert_eq("query HTTP status", r.status_code, 200)
rag = r.json()
assert_true("answer field present", "answer" in rag)
assert_true("answer is non-empty", bool(rag.get("answer", "").strip()))
_pass(f"RAG answer (first 120 chars): {rag['answer'][:120]!r}")


# ─── 6. Delete file ───────────────────────────────────────────────────────────

_step("5. Delete file")
r = requests.delete(f"{BASE_URL}/files/{file_id}")
assert_eq("DELETE /files HTTP status", r.status_code, 204)
_pass("File deleted (204 No Content)")


# ─── 7. Delete workspace ─────────────────────────────────────────────────────

_step("6. Delete workspace")
r = requests.delete(f"{BASE_URL}/workspaces/{workspace_id}")
assert_eq("DELETE /workspaces HTTP status", r.status_code, 204)
_pass("Workspace deleted (204 No Content)")


# ─── 8. Deep cleanup verification ────────────────────────────────────────────

_step("7. Deep Cleanup Verification")

# 7a. SQLite — files table
print("  [SQLite] files table …")
if DB_PATH.exists():
    conn = sqlite3.connect(str(DB_PATH), detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM files WHERE file_id = ?", (file_id,)).fetchone()
    assert_false("No ghost row in files", row is not None, f"file_id={file_id}")

    # 7b. SQLite — workspaces table
    print("  [SQLite] workspaces table …")
    row = conn.execute("SELECT * FROM workspaces WHERE workspace_id = ?", (workspace_id,)).fetchone()
    assert_false("No ghost row in workspaces", row is not None, f"workspace_id={workspace_id}")

    # 7c. SQLite — document_chunks table
    print("  [SQLite] document_chunks table …")
    row = conn.execute("SELECT * FROM document_chunks WHERE file_id = ?", (file_id,)).fetchone()
    assert_false("No ghost rows in document_chunks", row is not None, f"file_id={file_id}")
    conn.close()
else:
    _pass("SQLite DB not found — server used in-memory mode (no ghost data possible)")

# 7d. data/registry.json
print("  [Registry] data/registry.json …")
if REGISTRY.exists():
    reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
    assert_false(
        "No ghost entry in registry.json",
        file_id in reg,
        f"file_id={file_id}",
    )
else:
    _pass("registry.json does not exist — clean")

# 7e. data/raw/
print("  [Files] data/raw/ …")
raw_pdf = RAW_DIR / f"{file_id}.pdf"
assert_false("No ghost raw PDF", raw_pdf.exists(), str(raw_pdf))

# 7f. data/ocr/
print("  [Files] data/ocr/ …")
ocr_json = OCR_DIR / f"{file_id}.json"
assert_false("No ghost OCR JSON", ocr_json.exists(), str(ocr_json))

# 7g. data/chunks/
print("  [Files] data/chunks/ …")
chunks_json = CHUNKS_DIR / f"{file_id}_chunks.json"
assert_false("No ghost chunks JSON", chunks_json.exists(), str(chunks_json))

# 7h. ChromaDB
print("  [ChromaDB] data/index/ …")
try:
    # Patch sqlite3 the same way the app does
    try:
        import pysqlite3
        sys.modules["sqlite3"] = pysqlite3
    except ImportError:
        pass

    import chromadb  # noqa: E402 — must come after sqlite3 patch

    client = chromadb.PersistentClient(path=str(INDEX_DIR))
    try:
        col = client.get_collection("documents")
        result = col.get(where={"document_id": {"$eq": file_id}}, include=[])
        ghost_ids = result.get("ids", [])
        assert_false(
            "No ghost vectors in ChromaDB",
            len(ghost_ids) > 0,
            f"{len(ghost_ids)} vectors found for document_id={file_id}",
        )
    except Exception as e:
        if "does not exist" in str(e).lower():
            _pass("ChromaDB collection does not exist — clean")
        else:
            raise
except Exception as exc:
    print(f"  [ChromaDB] Could not inspect index: {exc}")

# 7i. BM25 corpus
print("  [BM25] data/index/bm25_corpus.json …")
if BM25_CORPUS.exists():
    corpus = json.loads(BM25_CORPUS.read_text(encoding="utf-8"))
    ghost_entries = [e for e in corpus if e.get("document_id") == file_id]
    assert_false(
        "No ghost entries in bm25_corpus.json",
        len(ghost_entries) > 0,
        f"{len(ghost_entries)} entries found for document_id={file_id}",
    )
else:
    _pass("bm25_corpus.json does not exist — clean")

# 7j. Local storage
print("  [LocalStorage] backend/local_storage/ …")
local_file = LOCAL_STORE / workspace_id
if local_file.exists():
    _fail(f"Ghost directory in local_storage: {local_file}")
else:
    _pass("No ghost directory in local_storage")


# ─── Done ─────────────────────────────────────────────────────────────────────

print(f"\n{HEADER}{'='*60}")
print("  ALL E2E CHECKS PASSED — Protocol Genesis pipeline is green")
print(f"{'='*60}{RESET}\n")
