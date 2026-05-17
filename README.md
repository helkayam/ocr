# Protocol Genesis

> **A production-ready, multi-stage PDF processing and Retrieval-Augmented Generation (RAG) system with native Hebrew OCR support.**

Upload PDFs through a modern web interface, extract text with Hebrew-optimized OCR, chunk semantically, embed into a vector store, and query via a constraint-aware RAG pipeline — all with workspace isolation, hybrid search, emergency geo-simulation, and an interactive full-screen map interface.

---

## Key Features

- **Multi-stage ingestion pipeline** — SHA-256 deduplication → OCR → semantic chunking → vector indexing, with real-time status polling in the UI
- **Hebrew-first OCR** — PyMuPDF + Tesseract with `heb` language pack for accurate Hebrew/mixed-language document extraction
- **Two-level semantic chunking** — child chunks (400 chars) for precision retrieval; parent chunks (1500 chars) sent to the LLM for richer context
- **Hybrid retrieval with RRF** — dense vector search (ChromaDB) fused with BM25 sparse retrieval via Reciprocal Rank Fusion (k=60)
- **Jina cross-encoder reranking** — API-based multilingual reranker narrows top-20 candidates to top-5 before LLM generation
- **Constraint-aware RAG generator** — Hebrew-only output with inline page citations; refuses to hallucinate when context is insufficient
- **Emergency simulation** — sensor-triggered RAG → intent extraction → nearest geo-feature routing → directive generation
- **Geo-feature layer management** — 7 canonical feature types (shelter, camera, building, exit, muster_point, extinguisher, assembly) with CRUD and map visualization
- **Workspace isolation** — every document, chunk, embedding, and event is scoped to a workspace; no data leaks between projects
- **Dual storage/DB** — MinIO + PostgreSQL preferred; falls back to local filesystem + SQLite automatically

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Frontend** | React 18, TypeScript, Vite, TailwindCSS, Lucide icons, TanStack React Query |
| **Backend API** | FastAPI, Uvicorn, Python 3.10+ |
| **Database** | PostgreSQL (preferred) · SQLite auto-fallback |
| **File Storage** | MinIO (preferred) · local filesystem auto-fallback |
| **Task Queue** | Redis + RQ · synchronous fallback in dev |
| **OCR Engine** | PyMuPDF, Tesseract (`heb` pack), pdfplumber |
| **Embeddings** | `intfloat/multilingual-e5-small` — 384-dim, run locally |
| **Vector DB** | ChromaDB (local `data/index/`) |
| **Sparse Index** | rank-bm25 (BM25Okapi), persisted as JSON |
| **Reranker** | Jina API — `jina-reranker-v2-base-multilingual` |
| **LLM** | Groq `llama-3.3-70b-versatile` (default) · OpenAI `gpt-4o-mini` (optional) |
| **Validation** | Pydantic v2 |
| **Logging** | Loguru |

---

## Prerequisites

Ensure the following are installed on your system **before** starting:

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.10+ | `python3 --version` |
| Node.js | 18+ | `node --version` |
| npm | 9+ | `npm --version` |
| Tesseract OCR | 4.x / 5.x | See install note below |
| Hebrew language pack | — | `tesseract-ocr-heb` |

**Install Tesseract with Hebrew support:**

```bash
# Ubuntu / Debian
sudo apt-get install tesseract-ocr tesseract-ocr-heb

# macOS (Homebrew)
brew install tesseract
brew install tesseract-lang   # includes heb
```

---

## Quick Start

### 1. Clone the repository

```bash
git clone <your-repo-url>
cd ocr
```

### 2. Create and activate the Python virtual environment

> **Important:** Every `pip install` and `python` command in this project **must** run inside the virtual environment. Never install packages globally — you will get wrong versions or missing dependencies.

```bash
python3 -m venv venv
source venv/bin/activate      # Linux / macOS
# venv\Scripts\activate       # Windows
```

Your shell prompt should now show `(venv)`.

### 3. Install backend dependencies

```bash
pip install -r requirements.txt
```

### 4. Install frontend dependencies

```bash
cd front
npm install
cd ..
```

---

## Environment Configuration

Create a `.env` file in the **project root** (next to `main.py`):

```env
# --- LLM Providers ---
GROQ_API_KEY=your_groq_api_key_here
OPENAI_API_KEY=your_openai_api_key_here   # only needed if LLM_PROVIDER=openai
LLM_PROVIDER=groq                          # "groq" (default) or "openai"

# --- Reranker ---
JINA_API_KEY=your_jina_api_key_here

# --- Database (optional) ---
DATABASE_URL=postgresql://user:password@localhost:5432/protocol_genesis
# Leave unset to use SQLite auto-fallback

# --- Object Storage (optional) ---
MINIO_ENDPOINT=localhost:9000
# Leave unset to use local filesystem fallback
```

**Where to get free API keys:**
- **Groq** — [console.groq.com](https://console.groq.com) — free tier, fast inference
- **Jina** — [jina.ai](https://jina.ai) — free tier for reranker API
- **OpenAI** — [platform.openai.com](https://platform.openai.com) — only needed if switching provider

> **Important:** Never hardcode API keys in source files. The `.env` file is in `.gitignore` — keep it that way.

---

## How to Run

Open **three terminal windows** from the project root.

### Terminal 1 — Backend (FastAPI)

```bash
source venv/bin/activate
uvicorn backend.main:app --reload
```

The API is now available at `http://localhost:8000`. Interactive docs at `http://localhost:8000/docs`.

### Terminal 2 — Frontend (Vite dev server)

```bash
cd front
npm run dev
```

The UI is now available at `http://localhost:5173`.

### Terminal 3 — Background Worker (optional, for async processing)

Only required if you have Redis running and want asynchronous OCR jobs:

```bash
source venv/bin/activate
python -m backend.worker.main
```

> **Note:** Without Redis, ingestion runs synchronously in the API process — this works fine for development and small document sets.

---

## Interacting with the System

### Via CLI

All CLI commands require the virtual environment to be active.

```bash
source venv/bin/activate

# Ingest a PDF into the pipeline
python main.py ingest path/to/document.pdf

# Query the indexed documents
python main.py ask "מהן דרישות הבטיחות לפי סעיף 4?"

# Delete a document by its ID
python main.py delete <document_id>

# Re-run indexing for an existing document
python main.py reindex <document_id>
```

### Via Web UI

1. **Open** `http://localhost:5173` in your browser.
2. **Create a Workspace** — give it a name (e.g., "Safety Protocols Q2").
3. **Upload a PDF** — drag and drop a Hebrew or English PDF into the upload area. Select the geo layer category if applicable.
4. **Watch the status badge** — it polls every 3 seconds and transitions through: `pending → ocr_completed → chunked → indexed`.
5. **Query** — once the file reaches `indexed`, use the QueryBox to ask questions in Hebrew or English. The system replies in Hebrew with page-level citations.

### Via Emergency Simulation

The simulation requires geo-features and sensors to be configured in the workspace.

1. Navigate to the **Map View** for your workspace.
2. **Place your evacuation origin pin** — click the map to set your starting position. The "Simulate" button remains disabled until you confirm this point.

> **Important:** A user-supplied origin coordinate is mandatory. The system will not fall back to the sensor location as a routing origin — this is a hard architectural rule.

3. Select a sensor from the panel and click **Simulate**.
4. The system runs: RAG query → intent extraction → nearest geo-feature search (Haversine from your origin) → directive generation.
5. Results display in the **Emergency Result Card**: detected intent, urgency level, nearest safe feature, distance, and the generated evacuation directive.

---

## Architecture & Data Flow

### 5-Phase Ingestion Pipeline

```
  ┌─────────────┐
  │  PDF Upload │  (drag-drop in UI or CLI ingest)
  └──────┬──────┘
         │
         ▼
  Phase 2 │ INGEST      app/ingest/manager.py
           │             SHA-256 dedup · copy to data/raw/ · status: pending
         │
         ▼
  Phase 3 │ OCR         app/ocr/processor.py
           │             PyMuPDF + Tesseract (heb) · saves data/ocr/{id}.json · status: ocr_completed
         │
         ▼
  Phase 4 │ CHUNK       app/chunking/splitter.py
           │             Child chunks 400 chars · Parent chunks 1500 chars
           │             saves data/chunks/{id}_chunks.json · status: chunked
         │
         ▼
  Phase 5 │ INDEX       app/indexing/indexer.py
           │             Embed with multilingual-e5-small (384-dim)
           │             Upsert to ChromaDB · Update BM25 corpus · status: indexed
         │
         ▼
  ┌──────────────────────────────────────┐
  │            RAG QUERY FLOW            │
  │                                      │
  │  User query                          │
  │      │                               │
  │      ▼                               │
  │  Dense retrieval (ChromaDB top-20)   │
  │  + BM25 sparse → RRF fusion          │
  │      │                               │
  │      ▼                               │
  │  Jina reranker → top-5 chunks        │
  │      │                               │
  │      ▼                               │
  │  LLM (Groq / OpenAI)                 │
  │  Hebrew answer + page citations      │
  └──────────────────────────────────────┘
```

### Workspace Isolation

Every ChromaDB query, BM25 lookup, and registry read filters on `workspace_id`. Documents from different workspaces are never mixed. Legacy documents (pre-workspace) use the `"__legacy__"` sentinel.

---

## Project Structure (Abbreviated)

```
ocr/
├── app/                  # RAG pipeline logic (OCR, chunking, indexing, retrieval, LLM)
├── backend/              # FastAPI app (HTTP API, DB, storage, services)
│   ├── api/              # Routers: files, workspaces, RAG, emergency
│   └── services/         # Business logic: geo, sensor, emergency, file, workspace
├── front/                # React + TypeScript UI
│   └── src/
│       ├── pages/        # WorkspaceList, WorkspaceDetails, MapView
│       └── components/   # QueryBox, FileListTable, EmergencyResultCard, GeoFeatureManager
├── data/                 # Pipeline outputs (never committed to git)
├── main.py               # CLI entry point
├── requirements.txt
└── .env                  # Secrets — never commit
```

---

## Common Issues

| Problem | Fix |
|---|---|
| `ModuleNotFoundError` on startup | Run `source venv/bin/activate` before any Python command |
| Tesseract not found | Install `tesseract-ocr` and ensure it's on your `PATH` |
| Hebrew OCR returns garbage | Confirm `tesseract-ocr-heb` language pack is installed |
| ChromaDB dimension mismatch | Self-healing init will auto-delete and recreate the collection on next startup |
| `Simulate` button disabled | You must place your evacuation origin pin on the map first |
| Files stuck at `pending` | Check that the backend is running; without Redis the worker runs inline |

---

## License

This project is provided for evaluation and educational purposes.
