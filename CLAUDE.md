# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Protocol Genesis** is a knowledge-ingestion engine for municipal and emergency-related documents, with strong Hebrew language support. The active codebase is an OCR + RAG (Retrieval-Augmented Generation) pipeline in the `ocr/` directory. The original FastAPI backend, React frontend, and Docker infrastructure have been removed from the working tree (but remain in git history).

## Running the Pipeline

All scripts must be run from within the `ocr/` directory, as they use relative imports:

```bash
cd ocr

# Step 1: OCR — extract text from PDFs/images → JSON
python main.py
# Reads from: ocr/test_pdf/   Writes to: ocr/test_files_json/

# Step 2: Chunk — split JSON output into semantic chunks
python chunker.py
# Reads from: ocr/test_files_json/*.json   Writes to: ocr/chunks.json

# Step 3: RAG — interactive Q&A over the chunked documents
python rag_pipeline.py
# Reads: ocr/chunks.json   Requires: GROQ_API_KEY
```

### System dependencies
- **Tesseract OCR** must be installed system-wide (used as fallback by `ocr_service.py`)
- `ffmpeg` for image format conversion
- Python packages: `pip install -r ocr/requirements.txt`
- Additional runtime deps not in requirements.txt: `sentence-transformers`, `groq`, `torch`, `python-bidi`, `numpy`

## Architecture

The pipeline is strictly sequential:

```
PDFs/Images (ocr/test_pdf/)
    ↓ ocr_service.py (OCRService)
JSON files (ocr/test_files_json/)
    ↓ chunker.py (SmartChunker)
chunks.json
    ↓ search_engine.py (LocalVectorSearch)  ← embedded on every rag_pipeline.py run
    ↓ rag_pipeline.py (HebrewRAG + Groq API)
Interactive Q&A
```

### Key modules

**`ocr_service.py` — OCRService**
- Primary extraction via `pdfplumber`; fallback to Tesseract via `PyMuPDF` when text is sparse
- Detects and fixes reversed Hebrew text (Unicode range U+0590–U+05FF)
- Extracts tables and formats them as Markdown (protected from splitting in chunker)
- Emits structured JSON: `{ file_name, pages: [{ page_num, blocks: [{ text, type, font_size, ratio_to_body }] }] }`

**`chunker.py` — SmartChunker**
- Token-based chunking with `tiktoken` (cl100k_base encoding), falls back to word-count estimate
- Default: max 500 tokens, 50-token overlap
- Headers detected by `ratio_to_body > 1.15` (font size relative to body text)
- Tables are never split across chunks
- Chunk IDs are deterministic: `{filename}_p{page}_{hash}`
- Output includes `text_with_context` (prepends h1/h2 headers for richer embeddings)

**`search_engine.py` — LocalVectorSearch**
- Loads all chunks and embeds them at startup using `paraphrase-multilingual-MiniLM-L12-v2` (supports Hebrew + English)
- Cosine similarity search via `sentence_transformers.util`
- Searches `text_with_context` field, not raw `text`

**`rag_pipeline.py` — HebrewRAG**
- Retrieves top-4 chunks, builds context string with source citations
- Calls Groq's `llama-3.3-70b-versatile` at temperature 0.2
- `print_rtl()` helper uses `python-bidi` to render Hebrew correctly in terminal
- **`GROQ_API_KEY` is currently hardcoded** at line 12 — move to `.env` when refactoring

## Important Conventions

- **Hebrew-first**: The system is designed for Hebrew documents. Prompts, variable names in comments, and output formatting all assume Hebrew RTL text as primary content.
- **No package structure**: All `ocr/` files use bare imports (`from ocr_service import OCRService`), requiring execution from within the `ocr/` directory.
- **Intermediate files are local**: `chunks.json` is written to the current working directory (`ocr/`), not a configurable path.
- **Supported input formats**: `.pdf`, `.png`, `.jpg`, `.jpeg`, `.tif`, `.tiff`, `.bmp`
