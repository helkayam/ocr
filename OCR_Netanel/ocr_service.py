import io
import os
import re
import subprocess
import tempfile
from typing import Optional

import fitz  # pymupdf
import magic
import pdfplumber
import pytesseract
from PIL import Image


class OCRService:
    def __init__(self):
        pass

    def detect_file_type(self, file_path: str) -> str:
        try:
            mime = magic.Magic(mime=True)
            file_type = mime.from_file(file_path)
            return file_type
        except Exception as e:
            print(f"Error detecting file type: {e}")
            return ""

    def convert_image_with_ffmpeg(
        self, input_path: str, output_format: str = "png"
    ) -> Optional[str]:
        try:
            with tempfile.NamedTemporaryFile(
                suffix=f".{output_format}", delete=False
            ) as temp_file:
                output_path = temp_file.name

            cmd = ["ffmpeg", "-i", input_path, "-vf", "scale=iw:ih", "-y", output_path]

            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode == 0:
                return output_path
            else:
                print(f"FFmpeg conversion failed: {result.stderr}")
                os.unlink(output_path)
                return None
        except Exception as e:
            print(f"Error converting image with ffmpeg: {e}")
            if "output_path" in locals() and os.path.exists(output_path):
                os.unlink(output_path)
            return None

    def extract_text_from_image(self, image_path: str) -> Optional[str]:
        try:
            image = Image.open(image_path)
            text = pytesseract.image_to_string(image, lang="heb")
            return text.strip()
        except Exception as e:
            print(f"Error extracting text from image: {e}")
            return None

    def is_hebrew_text(self, text: str) -> bool:
        if not text or len(text.strip()) < 3:
            return False

        # Check for Hebrew Unicode characters
        hebrew_pattern = re.compile(r"[\u0590-\u05FF]")
        hebrew_chars = hebrew_pattern.findall(text)

        # Consider it Hebrew if at least 10% of characters are Hebrew
        total_chars = len(re.sub(r"\s", "", text))
        if total_chars == 0:
            return False

        hebrew_ratio = len(hebrew_chars) / total_chars
        return hebrew_ratio >= 0.1

    def extract_text_from_pdf_images(self, pdf_path: str) -> Optional[str]:
        try:
            text = ""
            doc = fitz.open(pdf_path)

            for page_num in range(len(doc)):
                page = doc[page_num]

                # Convert page to image with 2x resolution for better OCR
                mat = fitz.Matrix(2, 2)
                pix = page.get_pixmap(matrix=mat)

                # Convert to PIL Image
                img_data = pix.tobytes("png")
                image = Image.open(io.BytesIO(img_data))

                # Use pytesseract with Hebrew language support
                page_text = pytesseract.image_to_string(image, lang="heb")
                if page_text.strip():
                    text += page_text.strip() + "\n"

            doc.close()
            return text.strip()
        except Exception as e:
            print(f"Error extracting text from PDF images: {e}")
            return None

    def extract_text_from_pdf(self, pdf_path: str) -> Optional[str]:
        try:
            # 1) Try direct extraction (pdfplumber)
            direct_text = ""
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text() or ""
                    if page_text.strip():
                        direct_text += page_text + "\n"
            direct_text = direct_text.strip()

            # 2) If direct extraction yielded Hebrew but looks reversed -> fix it
            if self.is_hebrew_text(direct_text) and self.looks_like_reversed_hebrew(direct_text):
                print("Direct extraction looks reversed -> fixing words...")
                fixed = self.fix_reversed_hebrew_words(direct_text)
                fixed = self.fix_reversed_hebrew_word_order(fixed)
                return fixed.strip()


            # 3) If direct extraction yielded good Hebrew (not reversed) -> use it
            if self.is_hebrew_text(direct_text):
                print("Using DIRECT text extraction (pdfplumber).")
                return direct_text

            # 4) Otherwise fallback to OCR
            print("FALLBACK to OCR (scanned render + tesseract)...")
            ocr_text = self.extract_text_from_pdf_images(pdf_path)

            # Optional debug: print OCR result (not the direct text)
            # print("\nOCR Text:\n" + "=" * 50)
            # print(ocr_text or "")
            # print("=" * 50)

            return ocr_text.strip() if ocr_text else None

        except Exception as e:
            print(f"Error extracting text from PDF: {e}")
            return None



    def extract_text(self, file_path: str) -> Optional[str]:
        if not os.path.exists(file_path):
            print(f"File not found: {file_path}")
            return None

        # Use magic library to detect file type
        file_type = self.detect_file_type(file_path)

        # Handle PDF files
        if file_type == "application/pdf":
            return self.extract_text_from_pdf(file_path)

        # Handle image files
        elif file_type.startswith("image/"):
            file_extension = os.path.splitext(file_path)[1].lower()

            # Standard image formats that PIL can handle directly
            if file_extension in [".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif"]:
                return self.extract_text_from_image(file_path)

            # Non-standard image formats - convert with ffmpeg first
            else:
                print(
                    f"Converting non-standard image format ({file_type}) using ffmpeg..."
                )
                converted_path = self.convert_image_with_ffmpeg(file_path, "png")

                if converted_path:
                    try:
                        text = self.extract_text_from_image(converted_path)
                        return text
                    finally:
                        # Clean up temporary file
                        os.unlink(converted_path)
                else:
                    return None

        else:
            print(f"Unsupported file format: {file_type}")
            return None
  
    

    

    def fix_reversed_hebrew_words(self, text: str) -> str:
        def should_reverse(tok: str) -> bool:
            # אם יש אותיות לטיניות — לא נוגעים
            if re.search(r"[A-Za-z]", tok):
                return False
            heb = len(re.findall(r"[\u0590-\u05FF]", tok))
            if heb < 2:
                return False
            # לא הופכים טוקנים שהם בעיקר מספרים/תאריכים
            digits = len(re.findall(r"\d", tok))
            non_space = len(re.sub(r"\s", "", tok))
            if non_space == 0:
                return False
            # "בעיקר עברית" => להפוך
            return heb / non_space >= 0.5 and digits / non_space <= 0.4

        tokens = re.findall(r"\s+|[^\s]+", text)  # שומר רווחים
        out = []
        for tok in tokens:
            if tok.isspace():
                out.append(tok)
            elif should_reverse(tok):
                out.append(tok[::-1])
            else:
                out.append(tok)
        return "".join(out)


    def looks_like_reversed_hebrew(self, text: str) -> bool:
        FINAL_LETTERS = set("םןץףך")

        # טוקנים "מילוליים" (לא רק עברית נקייה): כולל גרשיים/גרשים בתוך מילה
        tokens = re.findall(r"\S+", text)
        heb_tokens = []
        for t in tokens:
            # נספור טוקנים שיש בהם לפחות 2 אותיות עבריות
            heb_letters = re.findall(r"[\u0590-\u05FF]", t)
            if len(heb_letters) >= 2:
                heb_tokens.append(t)

        if len(heb_tokens) < 10:
            return False

        # נסתכל על האות העברית הראשונה בטוקן (מדלגים על גרשיים/סימנים)
        def first_hebrew_letter(tok: str):
            for ch in tok:
                if "\u0590" <= ch <= "\u05FF":
                    return ch
            return None

        starts_final = 0
        for tok in heb_tokens:
            first = first_hebrew_letter(tok)
            if first in FINAL_LETTERS:
                starts_final += 1

        ratio = starts_final / len(heb_tokens)
        return ratio > 0.12  # סף נמוך יותר שמתאים למסמכים עם הרבה "ו\"פשת" וכו'


    def fix_reversed_hebrew_word_order(self, text: str) -> str:
        def is_hebrew_dominant(line: str) -> bool:
            # אם יש לטינית - לא ניגע (כדי לא להרוס B.Sc וכו')
            if re.search(r"[A-Za-z]", line):
                return False
            heb = len(re.findall(r"[\u0590-\u05FF]", line))
            non_space = len(re.sub(r"\s", "", line))
            return non_space > 0 and (heb / non_space) >= 0.3  # סף סביר

        fixed_lines = []
        for line in text.splitlines():
            if not line.strip() or not is_hebrew_dominant(line):
                fixed_lines.append(line)
                continue

            tokens = re.findall(r"\s+|[^\s]+", line)  # שומר רווחים
            words = [t for t in tokens if not t.isspace()]
            words.reverse()

            out = []
            wi = 0
            for t in tokens:
                if t.isspace():
                    out.append(t)
                else:
                    out.append(words[wi])
                    wi += 1

            fixed_lines.append("".join(out))

        return "\n".join(fixed_lines)
