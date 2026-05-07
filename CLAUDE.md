# Project: Protocol Genesis — Full-Stack OCR + RAG System (Hebrew Supported)

## System Goal
Build a production-ready, multi-stage PDF processing and RAG system named **Protocol Genesis**. The system ingests PDFs via a web UI, performs Hebrew-optimized OCR, chunks text semantically, creates embeddings, stores them in a Vector DB, and provides a constraint-aware RAG interface with rigorous evaluation.

---

## CRITICAL: Environment Rules

### Python Virtual Environment (MANDATORY)
All Python packages MUST be installed within the project virtual environment. Never install globally.

```bash
# Always activate before running Python or pip
source venv/bin/activate
```

Never run `pip install` without first activating the venv. If the venv is not active and you try to run Python files, they will fail or use wrong package versions.

### Required Environment Variables (`.env` in project root)
```
GROQ_API_KEY=...
OPENAI_API_KEY=...     # required only when LLM_PROVIDER=openai
LLM_PROVIDER=groq      # optional; "groq" (default) or "openai"
JINA_API_KEY=...
DATABASE_URL=...       # optional; falls back to SQLite if not set
MINIO_ENDPOINT=...     # optional; falls back to local storage if not set
```

Never hardcode API keys. Always load via `python-dotenv`.

---

## Build & Run Commands

### Backend (FastAPI) — run from project root
```bash
source venv/bin/activate
uvicorn backend.main:app --reload
```
Listens on `http://localhost:8000`. The entry point is `backend/main.py`.

### Frontend (React/TypeScript) — run from `front/` directory
```bash
cd front
npm run dev
```
Talks to backend at `http://localhost:8000` (configurable via `VITE_API_URL`).

### Core RAG CLI — run from project root
```bash
source venv/bin/activate
python main.py ingest <path-to-pdf>
python main.py ask "<query>"
python main.py delete <doc_id>
python main.py reindex <doc_id>
```

---

## Folder Structure

```
ocr/
├── app/                        # Core RAG pipeline logic
│   ├── models.py               # Pydantic models: DocumentRecord, Block, Chunk, etc.
│   ├── registry.py             # JSON-based document registry (data/registry.json)
│   ├── pipeline.py             # Synchronous orchestration: ingest/ask/delete/reindex
│   ├── ingest/
│   │   ├── manager.py          # SHA256 dedup, file copy to data/raw/, registry entry
│   │   └── validator.py        # PDF magic bytes + size validation
│   ├── ocr/
│   │   ├── service.py          # OCRService (PyMuPDF + Tesseract, Hebrew support)
│   │   └── processor.py        # Runs OCR, parses to Pydantic, saves data/ocr/
│   ├── chunking/
│   │   └── splitter.py         # Two-level semantic chunking (parent 1500, child 400)
│   ├── indexing/
│   │   ├── embedder.py         # multilingual-e5-small, 384-dim, prefix discipline
│   │   ├── db.py               # ChromaDB client + self-healing init
│   │   ├── indexer.py          # Batch embed + upsert to ChromaDB + BM25
│   │   └── bm25_store.py       # Persistent BM25 sparse index
│   ├── retrieval/
│   │   ├── search.py           # Hybrid retrieval: dense (top-20) + BM25 via RRF
│   │   └── reranker.py         # Jina API reranker → top-5
│   ├── rag/
│   │   ├── generator.py        # Groq/OpenAI LLM switcher with constraint-aware Hebrew system prompt
│   │   └── evaluate.py         # Recall@K + grounding accuracy evaluation
│   └── worker/
│       ├── main.py             # RQ worker listener
│       └── tasks.py            # Background task: OCR → chunk → index
├── backend/                    # Full-stack FastAPI application
│   ├── main.py                 # App entry point, routers, CORS, DB init
│   ├── db.py                   # Dual DB: PostgreSQL (preferred) or SQLite fallback
│   ├── api/
│   │   ├── files.py            # Upload, confirm-upload, bridges to app/ingest
│   │   ├── rag_router.py       # /documents/ and /query endpoints (imports from schemas.py)
│   │   ├── workspaces.py       # Workspace CRUD incl. DELETE
│   │   └── schemas.py          # ALL API-layer Pydantic models (FileItem, Workspace, RAG schemas)
│   └── services/
│       ├── file_service.py     # DB persistence for file metadata
│       ├── storage_service.py  # MinIO or local_storage fallback
│       ├── workspace_service.py
│       ├── nlp_service.py
│       ├── sensor_service.py
│       ├── geo_service.py
│       └── report_service.py
├── front/                      # React + TypeScript frontend
│   ├── src/
│   │   ├── App.tsx             # React Router routes
│   │   ├── lib/api.ts          # Typed API client (BASE: http://localhost:8000)
│   │   ├── pages/
│   │   │   ├── WorkspaceDetails.tsx   # Main page: file list + RAG query
│   │   │   └── WorkspaceList.tsx
│   │   ├── components/
│   │   │   ├── QueryBox.tsx           # RAG query input + answer display
│   │   │   ├── FileListTable.tsx      # File table with status badges
│   │   │   ├── FileStatusBadge.tsx    # Polling badge (refetches every 3s if processing)
│   │   │   └── FileUploadArea.tsx     # Drag-drop upload
│   │   └── types/files.ts      # TypeScript interfaces: FileItem, Workspace, RagAnswer
│   └── package.json
├── data/                       # All persistent pipeline data (never commit to git)
│   ├── raw/                    # {document_id}.pdf
│   ├── ocr/                    # {document_id}.json (OCR result)
│   ├── chunks/                 # {document_id}_chunks.json
│   ├── index/                  # ChromaDB + bm25_corpus.json
│   ├── registry.json           # Central document registry
│   └── goldset.json            # Evaluation golden dataset
├── backend/local_storage/      # Fallback file storage when MinIO unavailable
├── main.py                     # CLI entry point (argparse)
├── requirements.txt
└── .env                        # Secrets (never commit)
```

---

## Architecture: Data Flows

### Ingestion Flow (Web Upload Path)
```
User drag-drops PDF in browser
    ↓
frontend: POST /files/upload-url → backend/api/files.py
    ↓
backend returns presigned URL (MinIO) or local upload URL
    ↓
frontend: PUT file bytes to presigned URL
    ↓
frontend: POST /files/confirm-upload → backend/api/files.py
    ↓
backend: writes temp file, calls app/ingest/manager.py
    ↓
Phase 2: SHA256 hash, dedup check, copy to data/raw/{doc_id}.pdf, registry entry "pending"
    ↓
Enqueue RQ job (or run synchronously in dev)
    ↓
Phase 3: OCR → data/ocr/{doc_id}.json, registry "ocr_completed"
Phase 4: Chunk → data/chunks/{doc_id}_chunks.json, registry "chunked"
Phase 5: Embed + index → ChromaDB + BM25, registry "indexed"
    ↓
frontend polls file status every 3s until "indexed" or "error"
```

### RAG Query Flow
```
User types query in QueryBox
    ↓
frontend: POST /query {query, top_k, workspace_id}
    ↓
backend/api/rag_router.py → app/pipeline.ask_pipeline()
    ↓
Stage 1 — Dense retrieval: embed query with "query: " prefix → ChromaDB top-20
         + BM25 sparse retrieval → Reciprocal Rank Fusion (RRF k=60)
    ↓
Stage 2 — Jina reranker API → top-5 chunks (parent_text sent to LLM)
    ↓
LLM (Groq `llama-3.3-70b-versatile` or OpenAI `gpt-4o-mini`, selected via `LLM_PROVIDER`) with constraint-aware Hebrew system prompt
    ↓
Answer: concise summary + detailed Hebrew prose with (עמוד X) citations + footer
```

---

## Architecture: Workspace Isolation

Every document and chunk is tagged with a `workspace_id`. All retrieval, indexing, and deletion operations filter by this field.

- ChromaDB `where` filter: `{"workspace_id": workspace_id}`
- BM25 also filters by workspace before scoring
- Registry exposes `get_by_workspace(workspace_id)`
- Legacy documents without a workspace use `"__legacy__"` as sentinel

When adding new retrieval or indexing code, always pass and filter on `workspace_id`.

---

## Tech Stack (Actual, As-Built)

| Layer | Technology |
|---|---|
| Pydantic models | `pydantic` v2 |
| Logging | `loguru` |
| OCR engine | `PyMuPDF`, `pytesseract`, `pdfplumber` (Hebrew via Tesseract) |
| Bi-encoder | `intfloat/multilingual-e5-small` — **384 dimensions** |
| Reranker | Jina API `jina-reranker-v2-base-multilingual` (HTTP, no local load) |
| Vector DB | ChromaDB (local `data/index/`) |
| Sparse index | `rank-bm25` (BM25Okapi, persisted as `bm25_corpus.json`) |
| LLM | Groq API `llama-3.3-70b-versatile` (default) or OpenAI `gpt-4o-mini`; switched via `LLM_PROVIDER` env var |
| Backend API | FastAPI + Uvicorn |
| DB | PostgreSQL (preferred) or SQLite (auto-fallback) |
| Storage | MinIO (preferred) or `backend/local_storage/` (auto-fallback) |
| Task queue | Redis + RQ (async) or synchronous fallback (dev) |
| Frontend | React 18, TypeScript, Vite, TailwindCSS, Lucide icons, TanStack React Query |

> **Note on embedding model:** The active model is `multilingual-e5-small` (384-dim), NOT `multilingual-e5-large` (1024-dim) as originally planned. The self-healing ChromaDB init checks for the active model's actual output size. Do not assume 1024-dim.

---

## Architectural Rules

1. **Venv always active.** All `pip install` and `python` commands require `source venv/bin/activate` first. Never install system-wide.

2. **Data persistence.** Every pipeline phase must write its output to `data/`. No transient-only state. Phases are: raw PDF → OCR JSON → chunks JSON → ChromaDB vectors.

3. **Prefix discipline.** The e5 model requires task prefixes:
   - Index time: prepend `"passage: "` to chunk text
   - Query time: prepend `"query: "` to user query
   Omitting these degrades retrieval quality significantly.

4. **Self-healing ChromaDB.** On init, check stored dimensionality vs. active model output. If mismatch → log warning, delete stale collection, recreate. This handles model migrations automatically.

5. **Workspace isolation everywhere.** Every read/write to ChromaDB, BM25, or the registry must include `workspace_id` scoping.

6. **Secrets via dotenv.** `GROQ_API_KEY`, `OPENAI_API_KEY`, `LLM_PROVIDER`, `JINA_API_KEY`, `DATABASE_URL`, `MINIO_ENDPOINT` — all from `.env`, never hardcoded.

7. **LLM provider switcher.** `app/rag/generator.py` reads `LLM_PROVIDER` at call time via `_get_client()`. Defaults to `"groq"` (`llama-3.3-70b-versatile`); set to `"openai"` to use `gpt-4o-mini` instead. Both providers use the OpenAI-compatible client (`openai.OpenAI`); Groq is accessed via its OpenAI-compatible base URL. Never hardcode the provider — always read from the env var.

8. **Retry logic.** All external API calls (Groq, OpenAI, Jina) use exponential backoff for HTTP 429. Use `tenacity` (`retry_if_exception_type(openai.RateLimitError)`) for LLM calls. BM25 failures are non-fatal (dense index is primary).

9. **Loguru everywhere.** Log pipeline step start/end, status transitions, API errors, deletion events. Use `logger.debug()` for reranker scores.

10. **Two-level chunking.** Child chunks (400 chars) are embedded and retrieved from ChromaDB. Parent chunks (1500 chars) are stored in child metadata as `parent_text` and sent to the LLM for richer context.

11. **Backend vs. app separation.** `backend/` is the ONLY HTTP entry point — `app/api/` has been removed. `backend/` owns the HTTP API, DB, and file storage. `app/` owns the RAG pipeline logic. The bridge is `backend/api/files.py` calling `app/ingest/manager.py` and `app/worker/tasks.py`.

12. **Unified schemas.** All API-layer Pydantic schemas live in `backend/api/schemas.py` — this includes file/workspace schemas AND RAG schemas (DocumentOut, QueryRequest, QueryResponse, etc.). `backend/api/rag_router.py` imports from there; it does not define its own inline schemas.

13. **Workspace lifecycle.** `DELETE /workspaces/{id}` is implemented in `backend/api/workspaces.py` + `backend/services/workspace_service.py`. Always clean up workspace documents via the RAG pipeline delete before deleting the workspace record.

---

## Engineering Principles & Code Hygiene

1. **Architectural Integrity.** Maintain strict separation between `backend/` (API/DB/Storage) and `app/` (RAG logic).
2. **Modular & Concise.** Keep files focused (SRP). Avoid large, multi-purpose modules. If a file exceeds 400 lines, split it.
3. **DRY (Don't Repeat Yourself).** Reuse logic from `app/pipeline.py` or shared schemas in `backend/api/schemas.py`. Never duplicate RAG logic.
4. **Proactive Refactoring.** If you spot inefficient code (e.g., O(N) registry lookups), fix it immediately. Optimize as you go.
5. **Zero Warning Tolerance.** Fix bugs and warnings before adding new features. Never build on top of unstable code.
6. **Elegant Simplicity.** Write smart, readable, and well-partitioned code. Logic should be easy to follow at a glance.

## Code Style

### Backend (Python)
- Use type hints on all function signatures
- Pydantic models for all request/response schemas
- `loguru` for all logging — no `print()` statements in production paths
- Structured error handling with HTTP status codes
- SQLite cursor wrapper (`_DBCursor`) handles `%s` → `?` translation automatically — do not use raw psycopg2 syntax in SQLite branches

### Frontend (TypeScript/React)
- Strict TypeScript interfaces for all API responses (see `front/src/types/files.ts`)
- Tailwind CSS utility classes — no inline styles
- Lucide icons for all iconography
- TanStack React Query for all server state (`useQuery`, `useMutation`)
- Poll for status with `refetchInterval` (3s) when files are still processing
- API calls go through `front/src/lib/api.ts` — never call `fetch` directly in components

---

## Key Pydantic Models (`app/models.py`)

| Model | Purpose |
|---|---|
| `DocumentRecord` | Registry entry: document_id, file_name, status, created_at, file_hash, workspace_id |
| `Block` / `OCRPage` / `OCRResult` | OCR engine output schema |
| `ChunkMetadata` / `Chunk` | Indexed chunk with parent_text, block_ids, page_num, is_header |
| `SearchResult` | Retrieved chunk with relevance score |
| `RAGResponse` | LLM answer + cited sources (document_id, page_num) |
| `GoldenQuestion` / `EvalResult` | Evaluation framework models |

Document statuses (in order): `pending` → `ocr_completed` → `chunked` → `indexed` (or `error` at any step).

---

## RAG Generator: System Prompt Protocol

The generator (`app/rag/generator.py`) uses a four-step internal protocol (invisible to users):

1. **Extract constraints** from the query (section numbers, dates, clause IDs, named entities)
2. **Classify each passage** internally: `EXPLICIT MATCH` / `PARTIAL MATCH` / `IRRELEVANT`
3. **Apply grounding rules:**
   - EXPLICIT MATCH found → answer from those passages only
   - Only PARTIAL MATCH → acknowledge mismatch, do NOT infer
   - No relevant passage → reply verbatim: `"המידע המבוקש לא נמצא במסמכים שסופקו."`
4. **Hard constraints:** Hebrew-only, no outside knowledge, no English labels in output, no JSON blocks, no step headers

**Output format (every answer):**
1. Concise summary (1-2 sentences)
2. Detailed Hebrew prose with inline `(עמוד X)` citations
3. Footer: `מספרי העמודים עליהם הסתמכתי: X, Y, Z`

---

## Database Schema (`backend/main.py`)

```sql
workspaces (workspace_id, name, description, file_count, total_size)
files      (file_id, workspace_id, filename, file_type, content_type,
            file_size, object_name, status, processing_status)
document_chunks (chunk_id, file_id, workspace_id, content, chunk_index, embedding)
sensors    (sensor_id, workspace_id, ...)
geo_layers (layer_id, workspace_id, ...)
```

---

## Pipeline Phases Reference

| Phase | Module | Input | Output | Registry Status |
|---|---|---|---|---|
| 2 | `app/ingest/manager.py` | PDF path | `data/raw/{id}.pdf` | `pending` |
| 3 | `app/ocr/processor.py` | doc_id | `data/ocr/{id}.json` | `ocr_completed` |
| 4 | `app/chunking/splitter.py` | doc_id | `data/chunks/{id}_chunks.json` | `chunked` |
| 5 | `app/indexing/indexer.py` | doc_id | ChromaDB + BM25 | `indexed` |
| 6a | `app/retrieval/search.py` | query + workspace_id | top-20 chunks (hybrid) | — |
| 6b | `app/retrieval/reranker.py` | top-20 + query | top-5 chunks | — |
| 6c | `app/rag/generator.py` | top-5 chunks + query | Hebrew answer | — |
