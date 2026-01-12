import os
import json

INPUT_DIR = "Test_files_types_txt"
OUTPUT_DIR = "output/ocr_json"


def ensure_dirs():
    os.makedirs(OUTPUT_DIR, exist_ok=True)


def read_text(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()


def build_ocr_json(document_id, text):
    return {
        "document_id": document_id,
        "language": "he",
        "source": "ocr",
        "text": text
    }


def main():
    ensure_dirs()

    for filename in os.listdir(INPUT_DIR):
        if not filename.endswith(".txt"):
            continue

        doc_id = filename.replace(".txt", "")
        text = read_text(os.path.join(INPUT_DIR, filename))

        ocr_json = build_ocr_json(doc_id, text)

        out_path = os.path.join(OUTPUT_DIR, f"{doc_id}.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(ocr_json, f, ensure_ascii=False, indent=2)

        print(f"Created OCR JSON for {doc_id}")


if __name__ == "__main__":
    main()
