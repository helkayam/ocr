import os
import json

OCR_JSON_DIR = "output/ocr_json"
CHUNKS_OUTPUT = "output/chunks.json"

MAX_CHARS = 450
MIN_CHARS = 120


def load_ocr_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def smart_split(text):
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    blocks = []
    current = ""

    for line in lines:
        # כותרת קצרה - מתחילים בלוק חדש
        if len(line) < 60 and current:
            blocks.append(current.strip())
            current = line
            continue

        if len(current) + len(line) <= MAX_CHARS:
            current = current + " " + line if current else line
        else:
            blocks.append(current.strip())
            current = line

    if current:
        blocks.append(current.strip())

    return blocks


def normalize_chunks(blocks):
    normalized = []

    buffer = ""
    for block in blocks:
        if len(block) < MIN_CHARS:
            buffer += " " + block
        else:
            if buffer:
                normalized.append(buffer.strip())
                buffer = ""
            normalized.append(block)

    if buffer:
        normalized.append(buffer.strip())

    return normalized


def build_chunks():
    all_chunks = []

    for filename in os.listdir(OCR_JSON_DIR):
        if not filename.endswith(".json"):
            continue

        data = load_ocr_json(os.path.join(OCR_JSON_DIR, filename))
        doc_id = data["document_id"]

        raw_blocks = smart_split(data["text"])
        chunks = normalize_chunks(raw_blocks)

        for idx, chunk in enumerate(chunks):
            all_chunks.append({
                "document_id": doc_id,
                "chunk_id": f"{doc_id}_{idx}",
                "text": chunk
            })

    with open(CHUNKS_OUTPUT, "w", encoding="utf-8") as f:
        json.dump(all_chunks, f, ensure_ascii=False, indent=2)

    print(f"Created {len(all_chunks)} chunks")
    print(f"Saved to {CHUNKS_OUTPUT}")


if __name__ == "__main__":
    build_chunks()
