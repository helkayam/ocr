#!/root/projects/ocr/venv/bin/python
"""
Standalone debug script to verify that chunks are correctly stored in ChromaDB.

Usage:
    ./venv/bin/python debug_indexing.py              # deep-check first indexed doc
    ./venv/bin/python debug_indexing.py <doc_id>     # deep-check one specific doc
    ./venv/bin/python debug_indexing.py --all        # count-check every doc in registry
"""

import json
import random
import sys
from pathlib import Path

REGISTRY_PATH = Path("data/registry.json")
CHUNKS_DIR    = Path("data/chunks")
INDEX_DIR     = Path("data/index")
COLLECTION    = "documents"


# ── helpers ───────────────────────────────────────────────────────────────────

def load_registry() -> dict:
    if not REGISTRY_PATH.exists():
        sys.exit(f"[ERROR] Registry not found at {REGISTRY_PATH}")
    return json.loads(REGISTRY_PATH.read_text())


def load_chunks(doc_id: str) -> list[dict] | None:
    """Return parsed chunks list, or None if the file is missing."""
    path = CHUNKS_DIR / f"{doc_id}_chunks.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text())
    return data if isinstance(data, list) else None


def get_chroma_collection():
    try:
        import pysqlite3
        sys.modules["sqlite3"] = pysqlite3
    except ImportError:
        pass

    try:
        import chromadb
    except ImportError:
        sys.exit("[ERROR] chromadb is not installed in the active venv.")

    if not INDEX_DIR.exists():
        sys.exit(f"[ERROR] ChromaDB index directory not found: {INDEX_DIR}")

    client = chromadb.PersistentClient(path=str(INDEX_DIR))
    try:
        return client.get_collection(COLLECTION)
    except Exception as exc:
        sys.exit(f"[ERROR] Could not open collection '{COLLECTION}': {exc}")


def separator(char: str = "─", width: int = 64) -> None:
    print(char * width)


def chroma_count_for(collection, doc_id: str) -> int:
    results = collection.get(
        where={"document_id": {"$eq": doc_id}},
        include=[],
    )
    return len(results["ids"])


# ── sweep: count-check every document ────────────────────────────────────────

def run_all(registry: dict, collection) -> None:
    separator("═")
    print("  FULL REGISTRY SWEEP — chunks on disk vs. vectors in Chroma")
    separator("═")

    total = len(registry)
    passed = 0
    failed_docs: list[dict] = []

    col_w = 36   # document_id column width
    name_w = 28  # file_name column width

    header = (
        f"  {'document_id':<{col_w}}  {'file':<{name_w}}  "
        f"{'status':<12}  {'disk':>5}  {'chroma':>6}  result"
    )
    print(header)
    separator()

    for doc_id, rec in registry.items():
        file_name  = rec.get("file_name", "—")
        status     = rec.get("status", "—")
        chunks     = load_chunks(doc_id)

        if chunks is None:
            disk_count   = "N/A"
            chroma_c     = chroma_count_for(collection, doc_id)
            result       = "WARN (no chunks file)"
            failed_docs.append({"doc_id": doc_id, "file": file_name, "reason": result})
        else:
            disk_count   = len(chunks)
            chroma_c     = chroma_count_for(collection, doc_id)
            if disk_count == chroma_c:
                result = "PASS"
                passed += 1
            else:
                diff   = disk_count - chroma_c
                result = f"FAIL (Δ {diff:+d})"
                failed_docs.append({
                    "doc_id": doc_id,
                    "file": file_name,
                    "disk": disk_count,
                    "chroma": chroma_c,
                    "reason": result,
                })

        print(
            f"  {doc_id:<{col_w}}  {file_name:<{name_w}}  "
            f"{status:<12}  {str(disk_count):>5}  {chroma_c:>6}  {result}"
        )

    separator()
    print(f"  SUMMARY : {passed}/{total} documents PASSED")

    if failed_docs:
        print(f"\n  Failed / warned documents:")
        for d in failed_docs:
            print(f"    • {d['file']} ({d['doc_id']})  →  {d['reason']}")
    separator("═")


# ── deep-check: single document ──────────────────────────────────────────────

def run_single(doc_id: str, registry: dict, collection) -> None:
    rec = registry[doc_id]

    separator("═")
    print(f"  DEEP CHECK  —  {rec['file_name']}")
    print(f"  document_id : {doc_id}")
    print(f"  status      : {rec['status']}")
    separator("═")

    # 1. chunks on disk
    chunks = load_chunks(doc_id)
    if chunks is None:
        sys.exit(f"[ERROR] Chunks file missing or malformed for {doc_id}")
    disk_count = len(chunks)
    print(f"\n[STEP 1] Chunks on disk   : {disk_count}")

    # 2. vectors in Chroma
    results      = collection.get(
        where={"document_id": {"$eq": doc_id}},
        include=[],
    )
    chroma_c = len(results["ids"])
    print(f"[STEP 2] Vectors in Chroma : {chroma_c}")

    # 3. count comparison
    separator()
    if disk_count == chroma_c:
        print(f"  [PASS] Counts match ({disk_count} == {chroma_c})")
    else:
        missing = disk_count - chroma_c
        extra   = chroma_c - disk_count
        print(f"  [FAIL] Count mismatch!")
        print(f"         On disk  : {disk_count}")
        print(f"         In Chroma: {chroma_c}")
        if missing > 0:
            print(f"         → {missing} chunk(s) were NOT indexed.")
        if extra > 0:
            print(f"         → {extra} extra vector(s) in Chroma (stale / duplicate?).")

        chroma_ids  = set(results["ids"])
        disk_ids    = {c["chunk_id"] for c in chunks}
        missing_ids = disk_ids - chroma_ids
        extra_ids   = chroma_ids - disk_ids
        if missing_ids:
            print(f"\n  Missing chunk IDs (first 10):")
            for cid in list(missing_ids)[:10]:
                print(f"    - {cid}")
        if extra_ids:
            print(f"\n  Extra Chroma IDs (first 10):")
            for cid in list(extra_ids)[:10]:
                print(f"    - {cid}")
    separator()

    # 4. random spot-check
    print("\n[STEP 4] Spot-check — random chunk lookup")
    sample    = random.choice(chunks)
    sample_id = sample["chunk_id"]
    print(f"  Sampled chunk_id : {sample_id}")

    lookup = collection.get(ids=[sample_id], include=["documents", "metadatas"])

    if not lookup["ids"]:
        print(f"  [FAIL] chunk_id '{sample_id}' NOT FOUND in ChromaDB.")
        separator()
        return

    stored_text     = lookup["documents"][0]
    stored_metadata = lookup["metadatas"][0]

    text_match = stored_text.strip() == sample["text"].strip()
    print(f"\n  Text match  : {'PASS' if text_match else 'FAIL'}")
    if not text_match:
        print(f"    Expected (first 120 chars): {sample['text'][:120]!r}")
        print(f"    Stored   (first 120 chars): {stored_text[:120]!r}")

    chunk_meta    = sample.get("metadata", {})
    meta_failures = [
        (key, expected, stored_metadata.get(key))
        for key, expected in chunk_meta.items()
        if str(stored_metadata.get(key)) != str(expected)
    ]

    if not meta_failures:
        print(f"  Metadata    : PASS ({len(chunk_meta)} key(s) verified)")
    else:
        print(f"  Metadata    : FAIL — {len(meta_failures)} mismatch(es):")
        for key, exp, got in meta_failures:
            print(f"    [{key}]  expected={exp!r}  stored={got!r}")

    separator()
    overall = disk_count == chroma_c and text_match and not meta_failures
    print(f"  OVERALL : {'PASS — indexing looks correct.' if overall else 'FAIL — see details above.'}")
    separator("═")


# ── entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    registry   = load_registry()
    collection = get_chroma_collection()

    if len(sys.argv) > 1 and sys.argv[1] == "--all":
        run_all(registry, collection)
        return

    if len(sys.argv) > 1:
        doc_id = sys.argv[1]
        if doc_id not in registry:
            sys.exit(f"[ERROR] document_id '{doc_id}' not found in registry.")
    else:
        indexed = [k for k, v in registry.items() if v.get("status") == "indexed"]
        if not indexed:
            sys.exit("[ERROR] No documents with status 'indexed' found in registry.")
        doc_id = indexed[0]
        print(f"[INFO]  No argument supplied — deep-checking first indexed doc: {doc_id}")

    run_single(doc_id, registry, collection)


if __name__ == "__main__":
    main()
