# Project: Document-Oriented OCR + RAG System (Hebrew Supported)

## 🎯 System Goal
Build an incremental, highly structured PDF processing and RAG system. The system ingests PDFs, uses an **EXISTING** Hebrew-optimized OCR engine, chunks the text, creates embeddings, stores them in a Vector DB, and provides a RAG interface with rigorous evaluation.

## 🧰 Tech Stack
* **Core:** Python 3.x
* **Validation & Config:** `pydantic`, `python-dotenv`
* **Testing & Evaluation:** `pytest`, Custom Evaluation Script (Recall@K)
* **Logging:** `loguru`
* **OCR:** Custom `OCRService` (already implemented using `pdfplumber`, `pytesseract`). Location: `\\wsl.localhost\Ubuntu\home\helkayam\ProtocolGenesis\ocr\ocr_service.py`
* **Embeddings:** `sentence-transformers` using **`dicta-il/alephbert`** (Optimized for Hebrew)
* **Vector DB:** ChromaDB
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
4. **Secrets Management:** NEVER hardcode API keys. Always use `python-dotenv` to load variables like `GROQ_API_KEY` from a `.env` file.
5. **Environment & Dependencies:** Assume an active Python virtual environment. Update `requirements.txt` and install packages (`pip install`) into the active venv as needed.
6. **Metadata-Awareness:** Leverage OCR metadata (block types, headers, etc.) to drive semantic decisions, especially during chunking.
7. **Resilience:** Implement basic retry logic/error handling for external API calls (e.g., Groq) to handle rate limits (HTTP 429) or transient failures.
8. **Logging:** Use `loguru` extensively. Log every major pipeline step start/end, validation failures, deletion events, and API errors.

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
**Objective:** Split the OCR blocks into semantic chunks using structural metadata.
* **Tasks:**
  1. Create `app/chunking/splitter.py` and read `data/ocr/{document_id}.json`.
  2. **Metadata Intelligence:** Iterate over pages and blocks. Use `block_type` and hierarchy to group related blocks. Ensure headers are contextually attached to their following paragraphs.
  3. **Configurable Splitting:** Implement `chunk_size` and `chunk_overlap` parameters (e.g., 500 chars with 10-15% overlap) to prevent loss of context mid-sentence. Keep tables intact.
  4. Crucial: Maintain metadata for EVERY chunk (`document_id`, `page_num`, `block_id`, `is_header`).
  5. Save to `data/chunks/{document_id}_chunks.json` and update registry to `chunked`.
* **Testing:** Write `tests/test_chunking.py`. Verify that headers stay with their content, chunk sizes/overlaps are correct, and metadata integrity is maintained.

## 🗄️ Phase 5: Embeddings & Vector DB (Chroma)
**Objective:** Vectorize chunks and store them.
* **Tasks:**
  1. Install `chromadb` and `sentence-transformers`.
  2. Create `app/indexing/embedder.py`. Load the **`dicta-il/alephbert`** model.
  3. Create `app/indexing/db.py` to initialize a local ChromaDB client pointing to `data/index`.
  4. Write logic to read the chunks JSON, generate embeddings, and upsert them into ChromaDB along with their metadata. Update registry to `indexed`.
  5. **Implement Deletion:** Add logic to delete all chunks of a specific `document_id` from ChromaDB.
* **Testing:** Write `tests/test_indexing.py`. Insert a mock chunk, query ChromaDB, and test the deletion logic to ensure no ghost vectors remain.

## 🤖 Phase 6: Retrieval & RAG (Groq)
**Objective:** Answer questions based on the Vector DB with high resilience.
* **Tasks:**
  1. Install `groq`. Ensure `python-dotenv` loads `GROQ_API_KEY`.
  2. Create `app/retrieval/search.py`: Embed the user query (using AlephBERT), search ChromaDB, return Top-K chunks.
  3. Create `app/rag/generator.py`: Construct a prompt containing the retrieved chunks. Initialize the Groq client (`llama-3.3-70b-versatile`). Instruct the LLM to answer ONLY based on the context in Hebrew and cite the source (`document_id` + `page_num`).
  4. **API Reliability:** Implement robust retry logic for Groq API calls to handle 429 (Rate Limit) errors.
* **Testing:** Write `tests/test_rag.py`. Mock a Chroma return and verify the Groq LLM correctly answers and cites the provided context.

## 🛠️ Phase 7: Synchronous MVP Orchestration (DEV)
**Objective:** Create a unified CLI to test the full system operations.
* **Tasks:**
  1. Create `main.py` with CLI arguments using `argparse` or `click`.
  2. Command `ingest <path>`: Runs Phases 2 -> 3 -> 4 -> 5 synchronously.
  3. Command `ask <query>`: Runs Phase 6.
  4. Command `delete <doc_id>`: Removes doc from registry, deletes files from `data/`, and removes vectors from ChromaDB.
  5. Command `reindex <doc_id>`: Deletes vectors from ChromaDB and re-runs Phase 5 for the specific doc.
* **Testing:** Perform a manual E2E run in the terminal: Ingest -> Ask -> Delete -> Ask (to ensure it's gone).

## 🌐 Phase 8: API Layer (FastAPI)
**Objective:** Expose the system via REST API.
* **Tasks:**
  1. Install `fastapi` and `uvicorn`.
  2. Create `app/api/main.py` with endpoints: 
     * `POST /documents/` (Upload PDF)
     * `GET /documents/` (List registry status)
     * `DELETE /documents/{doc_id}` (Full deletion)
     * `POST /documents/{doc_id}/reindex` (Trigger reindex)
     * `POST /query/` (RAG search)
* **Testing:** Write `tests/test_api.py` using `TestClient`.

## ⚡ Phase 9: Asynchronous Workers (PROD Ready)
**Objective:** Decouple ingest from processing using Redis and RQ.
* **Tasks:**
  1. Install `redis` and `rq`.
  2. Update API `POST /documents/`: Save file, mark `pending`, push job to RQ.
  3. Create `app/worker/main.py`: Listens to queue and executes Phases 3-5 in background.
* **Testing:** Ensure API returns fast 200 OK while worker processes in background.

## 📊 Phase 10: RAG Evaluation (Quality Assurance)
**Objective:** Build a mechanism to test retrieval accuracy.
* **Tasks:**
  1. Create `app/rag/evaluate.py`.
  2. Define a small, hardcoded dataset of "Golden Questions" (e.g., [{"query": "...", "expected_doc_id": "...", "expected_page": ...}]).
  3. Implement logic to run these queries through `app/retrieval/search.py` and calculate **Recall@K** (e.g., Recall@3, Recall@5).
  4. Output a summary report (Console + `loguru`).
* **Testing:** Run `python app/rag/evaluate.py` and verify metrics are calculated correctly.


