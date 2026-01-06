from ocr_service import OCRService
import os

def main():
    ocr = OCRService()
    input_dir = "TEST_FILES"
    output_dir = "OUTPUT_TEXT"

    os.makedirs(output_dir, exist_ok=True)

    for filename in os.listdir(input_dir):
        if not filename.lower().endswith(".pdf"):
            continue

        file_path = os.path.join(input_dir, filename)
        print(f"Processing: {filename}")

        text = ocr.extract_text(file_path)

        if text:
            out_name = filename.replace(".pdf", ".txt")
            out_path = os.path.join(output_dir, out_name)

            with open(out_path, "w", encoding="utf-8") as f:
                f.write(text)

        else:
            print(f"❌ Failed OCR: {filename}")

if __name__ == "__main__":
    main()
