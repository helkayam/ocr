from ocr_service import OCRService
import os

def main():
    ocr = OCRService()

    # base directory = folder of this file (OCR_Netanel)
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

    input_dir = os.path.join(BASE_DIR, "Test_files_types")
    output_dir = os.path.join(BASE_DIR, "Test_files_types_json") # שיניתי את שם התיקייה ל-json

    # safety check
    if not os.path.exists(input_dir):
        raise FileNotFoundError(f"Input directory not found: {input_dir}")

    os.makedirs(output_dir, exist_ok=True)

    # רשימת הסיומות שה-OCR שלנו תומך בהן כרגע
    supported_extensions = (".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp")

    for filename in os.listdir(input_dir):
        # בדיקה אם הקובץ נתמך (PDF או תמונה)
        if not filename.lower().endswith(supported_extensions):
            continue

        file_path = os.path.join(input_dir, filename)
        print(f"Processing: {filename}...")

        # קריאה לפונקציה החדשה שמחזירה JSON string
        json_output = ocr.process_file(file_path)

        if json_output:
            # החלפת הסיומת של קובץ הפלט ל-.json
            # שימוש ב-os.path.splitext עדיף על rsplit למקרים של נקודות בשם הקובץ
            name_without_ext = os.path.splitext(filename)[0]
            out_name = name_without_ext + ".json"
            out_path = os.path.join(output_dir, out_name)

            with open(out_path, "w", encoding="utf-8") as f:
                f.write(json_output)
            
            print(f"Saved JSON: {out_name}")

        else:
            print(f"Failed or empty result for: {filename}")

if __name__ == "__main__":
    main()