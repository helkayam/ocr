# Project: Document-Oriented OCR + RAG System (Hebrew Supported)

## 🎯 System Goal
Build an incremental, highly structured PDF processing and RAG system. The system ingests PDFs, uses an **EXISTING** Hebrew-optimized OCR engine, chunks the text, creates embeddings, stores them in a Vector DB, and provides a RAG interface with rigorous evaluation.

## 🧰 Tech Stack
* **Core:** Python 3.x
* **Validation & Config:** `pydantic`, `python-dotenv`
* **Testing & Evaluation:** `pytest`, Custom Evaluation Script (Recall@K)
* **Logging:** `loguru`
* **OCR:** Custom `OCRService` (already implemented using `pdfplumber`, `pytesseract`). Location: `\\wsl.localhost\Ubuntu\home\helkayam\ProtocolGenesis\ocr\ocr_service.py`
* **Embeddings — Stage 1 (Bi-Encoder):** `sentence-transformers` using **`intfloat/multilingual-e5-large`** (1024 dimensions). Mandatory prefix `"passage: "` for indexed chunks; `"query: "` for query embedding at retrieval time.
* **Reranking — Stage 2 (Cross-Encoder):** **Jina Reranker API** (`jina-reranker-v2-base-multilingual`) via HTTP — no local model load. Requires `JINA_API_KEY` in `.env`.
* **Vector DB:** ChromaDB (local storage in `./data/index`)
* **LLM / RAG:** Groq API using **`llama-3.3-70b-versatile`** (with Rate-Limit handling)
* **API Layer:** FastAPI, Uvicorn
* **Message Queue (PROD):** Redis, RQ

## 🌍 Environments (DEV vs. PROD)
The system must be designed to support two environments smoothly:
* **DEV Environment (Local):** Synchronous processing (for easy debugging), local ChromaDB storage in `./data/index`, local `.env` file for secrets, venv-based execution.
* **PROD Environment (Future):** Asynchronous processing using Redis/RQ (Workers handle OCR and Indexing), REST API endpoints via FastAPI, robust logging (`loguru`), scalable database integration.

## 🧠 Architectural Rules for Claude
1. **Incremental Phases:** You MUST develop this system phase by phase. Do NOT start a new phase until the current phase is fully implemented and passes its tests.
2. **Existing OCR:** Do NOT write a new OCR engine. Review the existing `OCRService` code at its specific WSL path before integration to understand its exact JSON schema.
3. **Data Persistence:** Every pipeline step must save its output (OCR JSON, Chunks JSON) to the filesystem in the `data/` directory. No transient-only states.
4. **Secrets Management:** NEVER hardcode API keys. Always use `python-dotenv` to load variables like `GROQ_API_KEY` and `JINA_API_KEY` from a `.env` file.
5. **Environment & Dependencies:** Assume an active Python virtual environment. Update `requirements.txt` and install packages (`pip install`) into the active venv as needed.
6. **Metadata-Awareness:** Leverage OCR metadata (block types, headers, etc.) to drive semantic decisions, especially during chunking.
7. **Resilience:** Implement basic retry logic/error handling for external API calls (e.g., Groq) to handle rate limits (HTTP 429) or transient failures.
8. **Logging:** Use `loguru` extensively. Log every major pipeline step start/end, validation failures, deletion events, and API errors.
9. **Prefix Discipline:** The `multilingual-e5-large` model requires task-specific prefixes. ALWAYS prepend `"passage: "` before embedding chunks at index time, and `"query: "` before embedding user queries at retrieval time. Omitting these prefixes degrades retrieval quality significantly.
10. **Self-Healing DB:** On startup, the ChromaDB layer must validate that the stored vector dimensionality matches the active embedding model (1024 for `multilingual-e5-large`). If a mismatch is detected (e.g., a legacy 768-dim collection), the collection must be automatically deleted and recreated, and a warning must be logged.

---

## 📂 Phase 1: Foundation & Registry Management
**Objective:** Set up directories, Pydantic models, and the Registry.
* **Tasks:**
  1. Create the folder structure: `app/` (with subfolders `ingest`, `ocr`, `chunking`, `indexing`, `retrieval`, `rag`, `api`, `worker`) and `data/` (with `raw`, `ocr`, `chunks`, `index`).
  2. Create `app/models.py`. Define Pydantic models:
     * `DocumentRecord` (fields: `document_id`, `file_name`, `status`, `created_at`, `file_hash`).
     * `Block` and `OCRPage` matching the exact output of our existing `OCRService`.
     * `Chunk` (fields: `chunk_id`, `document_id`, `page`, `text`, `metadata`).
  3. Create `app/registry.py` to manage `data/registry.json` (add, update status, check exists, delete).
* **Testing:** Write `tests/test_registry.py` using `pytest`. Ensure adding a doc, updating its status, and deleting it works correctly.

## 📥 Phase 2: Ingestion & Validation
**Objective:** Handle file entry and deduplication.
* **Tasks:**
  1. Create `app/ingest/validator.py`: Validate file is a PDF, check size, and ensure it's not empty.
  2. Create `app/ingest/manager.py`: Generate SHA256 file hash. Check `registry.py` to prevent duplicates. Generate a unique `document_id`, copy the file to `data/raw/{document_id}.pdf`, and add a "pending" record to the registry.
* **Testing:** Write `tests/test_ingest.py`. Pass a dummy PDF and verify the hash generation and deduplication logic.

## 🔍 Phase 3: OCR Integration
**Objective:** Connect the existing `OCRService` to the pipeline.
* **Tasks:**
  1. **Code Audit:** The existing `OCRService` is located at `\\wsl.localhost\Ubuntu\home\helkayam\ProtocolGenesis\ocr\ocr_service.py`. Import or copy it to `app/ocr/service.py`. Review its output format.
  2. Create `app/ocr/processor.py`. It should:
     * Take a `document_id`.
     * Read the PDF from `data/raw/`.
     * Call `OCRService().process_file()`.
     * Parse the returned JSON string into the Pydantic models.
     * Save the validated JSON to `data/ocr/{document_id}.json`.
     * Update registry status to `ocr_completed`.
* **Testing:** Write `tests/test_ocr_integration.py`. Run a real Hebrew PDF through the processor and assert the JSON file is created locally.

## 🧩 Phase 4: Metadata-Aware Semantic Chunking
**Objective:** Split the OCR blocks into semantic chunks using structural metadata and semantic aggregation.
* **Tasks:**
  1. Create `app/chunking/splitter.py` and read `data/ocr/{document_id}.json`.
  2. **Semantic Aggregation (Pre-Chunking):** Before applying the sliding-window split, iterate over the raw OCR blocks and concatenate consecutive small blocks until a minimum character threshold of **300 characters** is reached. This prevents the embedder from receiving sub-sentence, content-free fragments that collapse to near-identical vectors. Apply this aggregation within page boundaries; do not merge across pages.
  3. **Metadata Intelligence:** Iterate over the aggregated blocks. Use `block_type` and hierarchy to group related blocks. Ensure headers are contextually attached to their following paragraphs.
  4. **Configurable Splitting:** Implement `chunk_size` and `chunk_overlap` parameters (e.g., 500 chars with 10–15% overlap) on the aggregated content to prevent loss of context mid-sentence. Keep tables intact as single chunks regardless of size.
  5. **Metadata Propagation:** Maintain metadata for EVERY chunk (`document_id`, `page_num`, `block_id`, `is_header`). When multiple source blocks are merged during aggregation, record all contributing `block_id`s.
  6. Save to `data/chunks/{document_id}_chunks.json` and update registry to `chunked`.
* **Testing:** Write `tests/test_chunking.py`. Verify that:
  * No chunk shorter than the aggregation threshold (300 chars) exists unless it is the final fragment of a page.
  * Headers stay attached to their following content.
  * Chunk sizes and overlaps are within configured bounds.
  * Metadata integrity is maintained for every chunk.

## 🗄️ Phase 5: Embeddings & Vector DB (Chroma)
**Objective:** Vectorize chunks with the Bi-Encoder and store them with Self-Healing DB initialization.
* **Tasks:**
  1. Install `chromadb`, `sentence-transformers`.
  2. Create `app/indexing/embedder.py`. Load the **`intfloat/multilingual-e5-large`** model (outputs 1024-dimensional vectors). When embedding chunks for storage, ALWAYS prepend the `"passage: "` prefix to each chunk's text before passing it to the model.
  3. Create `app/indexing/db.py` to initialize a local ChromaDB client pointing to `data/index`.
     * **Self-Healing Initialization:** On client creation, inspect the existing ChromaDB collection's configured dimensionality. If it does not match the active model's output size (1024), log a warning, delete the stale collection, and create a fresh one. This handles seamless migration from any previously used model (e.g., a legacy 768-dim model).
  4. Write logic to read the chunks JSON, generate `"passage: "`-prefixed embeddings, and upsert them into ChromaDB along with their metadata. Update registry to `indexed`.
  5. **Implement Deletion:** Add logic to delete all chunks of a specific `document_id` from ChromaDB.
* **Testing:** Write `tests/test_indexing.py`. Verify that:
  * Stored vectors have dimensionality 1024.
  * Inserting a mock chunk with a 768-dim model followed by re-initialization with the 1024-dim model triggers the self-healing reset.
  * Deletion leaves no ghost vectors for the target `document_id`.

## 🤖 Phase 6: Two-Stage Retrieval & Constraint-Aware RAG
**Objective:** Answer questions with high precision using a two-stage retrieval pipeline and a grounding-validated LLM generator.

### Stage 1 — Dense Retrieval (Bi-Encoder)
* Create `app/retrieval/search.py`.
* Embed the user query using `multilingual-e5-large` with the mandatory `"query: "` prefix.
* Query ChromaDB and retrieve the **Top-20** candidate chunks (deliberately over-fetches to give the reranker enough signal).

### Stage 2 — Precision Reranking (Jina API)
* Create `app/retrieval/reranker.py`.
* Call the **Jina Reranker API** (`jina-reranker-v2-base-multilingual`) with the query and all 20 candidate texts in a single HTTP request.
* Load `JINA_API_KEY` from `.env` via `python-dotenv`. Never hardcode it.
* Sort results by descending relevance score and return only the **Top-5** chunks to the generator.
* Log the score of every candidate at `DEBUG` level to allow reranking audits.
* Apply the same retry/back-off logic as Groq calls to handle API rate limits.

### Generator — Constraint-Aware Grounding
* `app/rag/generator.py` enforces a **four-step internal protocol** (written in English in the system prompt for token efficiency; all reasoning stays invisible — never surfaced to the user):

  **Step 1 — Extract Query Constraints:** Identify specific constraints in the query (section numbers, dates, clause IDs, named entities, numeric identifiers).

  **Step 2 — Classify Each Passage (internal only):** For every retrieved passage assign one internal label — never printed in output:
  * `EXPLICIT MATCH` — constraint is directly and unambiguously named in the passage text.
  * `PARTIAL MATCH` — passage is topically related but does not explicitly name the constraint.
  * `IRRELEVANT` — passage does not address the query.

  **Step 3 — Apply Grounding Rules:**
  * `EXPLICIT MATCH` found → answer from those passages only.
  * Only `PARTIAL MATCH` found → do NOT infer or bridge to the specific constraint; acknowledge the mismatch explicitly.
  * No relevant passage → reply verbatim: `"המידע המבוקש לא נמצא במסמכים שסופקו."` — nothing else.

  **Step 4 — Hard Constraints (always enforced):**
  * Answer only in Hebrew.
  * Use only provided passages — no outside knowledge.
  * Proximity or topic similarity does NOT satisfy a specific constraint.
  * Prioritize factual integrity over appearing helpful.
  * **No English labels** (`EXPLICIT MATCH`, etc.) in the final answer.
  * **No JSON source blocks** or structured metadata blocks in the final answer.
  * **No step-headers** or internal reasoning visible to the user.

* **Output Format ("Bottom-line first"):** Every answer (when context supports one) must follow this exact structure:
  1. **Concise summary** — one or two sentences stating the direct answer.
  2. **Detailed Hebrew explanation** — full context with inline page citations formatted as `(עמוד X)` embedded naturally in the prose.
  3. **Footer line** — `מספרי העמודים עליהם הסתמכתי: X, Y, Z` listing every page cited.

* Implement robust retry logic for Groq API calls to handle HTTP 429 (Rate Limit) errors using exponential back-off (`tenacity`).

### Tasks
1. Install `groq`. Ensure `python-dotenv` loads `GROQ_API_KEY`.
2. Implement `app/retrieval/search.py` (Stage 1, Top-20).
3. Implement `app/retrieval/reranker.py` (Stage 2, Top-5).
4. Implement `app/rag/generator.py` with the constraint-aware system prompt as described above.

### Testing
* Write `tests/test_rag.py`. Mock the ChromaDB return (Top-20) and the reranker scoring. Verify that:
  * Only the Top-5 reranked chunks reach the generator.
  * When the context contains a `PARTIAL MATCH` for a specific constraint in the query, the answer acknowledges the mismatch rather than hallucinating an attribution.
  * When no relevant context exists, the fixed "not found" phrase is returned verbatim.

## 🛠️ Phase 7: Synchronous MVP Orchestration (DEV)
**Objective:** Create a unified CLI to test the full system operations end-to-end.
* **Tasks:**
  1. Create `main.py` with CLI arguments using `argparse` or `click`.
  2. Command `ingest <path>`: Runs Phases 2 → 3 → 4 → 5 synchronously.
  3. Command `ask <query>`: Runs Phase 6 (Stage 1 → Stage 2 → Generator).
  4. Command `delete <doc_id>`: Removes doc from registry, deletes files from `data/`, and removes vectors from ChromaDB.
  5. Command `reindex <doc_id>`: Deletes vectors from ChromaDB and re-runs Phase 5 for the specific doc.
* **Testing:** Perform a manual E2E run in the terminal: Ingest → Ask (with a constraint-bearing query) → Delete → Ask (to confirm it's gone).

## 🌐 Phase 8: API Layer (FastAPI)
**Objective:** Expose the system via REST API.
* **Tasks:**
  1. Install `fastapi` and `uvicorn`.
  2. Create `app/api/main.py` with endpoints:
     * `POST /documents/` (Upload PDF)
     * `GET /documents/` (List registry status)
     * `DELETE /documents/{doc_id}` (Full deletion)
     * `POST /documents/{doc_id}/reindex` (Trigger reindex)
     * `POST /query/` (RAG search — invokes the full two-stage pipeline)
* **Testing:** Write `tests/test_api.py` using `TestClient`.

## ⚡ Phase 9: Asynchronous Workers (PROD Ready)
**Objective:** Decouple ingest from processing using Redis and RQ.
* **Tasks:**
  1. Install `redis` and `rq`.
  2. Update API `POST /documents/`: Save file, mark `pending`, push job to RQ.
  3. Create `app/worker/main.py`: Listens to queue and executes Phases 3–5 in background.
* **Testing:** Ensure API returns fast 200 OK while worker processes in background.

## 📊 Phase 10: RAG Evaluation (Quality Assurance)
**Objective:** Build a mechanism to test retrieval and grounding accuracy.
* **Tasks:**
  1. Create `app/rag/evaluate.py`.
  2. Define a small, hardcoded dataset of "Golden Questions." Each entry must include:
     * `query` — the question, at least some of which include specific constraints (section numbers, dates, etc.).
     * `expected_doc_id` and `expected_page` — the ground-truth source.
     * `constraint_type` — one of `"specific"` or `"general"`, to allow separate evaluation of constraint-handling behavior.
  3. Run each query through the full two-stage pipeline (`search.py` → `reranker.py`) and calculate:
     * **Recall@K** (K = 3, 5, 20) measured after Stage 1 (Bi-Encoder only).
     * **Recall@5** measured after Stage 2 (Reranker output) — this is the primary quality metric.
     * **Grounding Accuracy** for `"specific"` queries: what fraction of answers correctly acknowledged a mismatch rather than hallucinating an attribution.
  4. Output a summary report (console + `loguru`).
* **Testing:** Run `python app/rag/evaluate.py` and verify all three metrics are calculated and printed correctly.
