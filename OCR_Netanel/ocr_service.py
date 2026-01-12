import io
import os
import re
import subprocess
import tempfile
import json
import statistics
from typing import Optional, List, Dict, Any

import fitz  # pymupdf
import magic
import pdfplumber
import pytesseract
from pytesseract import Output
from PIL import Image


class OCRService:
    def __init__(self):
        pass

    # =========================================================================
    #  FILE UTILS
    # =========================================================================

    def detect_file_type(self, file_path: str) -> str:
        try:
            mime = magic.Magic(mime=True)
            return mime.from_file(file_path)
        except Exception as e:
            print(f"Error detecting file type: {e}")
            return ""

    def convert_image_with_ffmpeg(self, input_path: str, output_format: str = "png") -> Optional[str]:
        try:
            with tempfile.NamedTemporaryFile(suffix=f".{output_format}", delete=False) as temp_file:
                output_path = temp_file.name

            cmd = ["ffmpeg", "-i", input_path, "-vf", "scale=iw:ih", "-y", output_path]
            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode == 0:
                return output_path
            else:
                if os.path.exists(output_path):
                    os.unlink(output_path)
                return None
        except Exception:
            if "output_path" in locals() and os.path.exists(output_path):
                os.unlink(output_path)
            return None

    # =========================================================================
    #  HEBREW HANDLING
    # =========================================================================

    def is_hebrew_text(self, text: str) -> bool:
        if not text or len(text.strip()) < 2:
            return False
        hebrew_pattern = re.compile(r"[\u0590-\u05FF]")
        hebrew_chars = hebrew_pattern.findall(text)
        total_chars = len(re.sub(r"\s", "", text))
        if total_chars == 0:
            return False
        return (len(hebrew_chars) / total_chars) >= 0.15

    def looks_like_reversed_hebrew(self, text: str) -> bool:
        FINAL_LETTERS = set("םןץףך")
        tokens = re.findall(r"\S+", text)
        heb_tokens = [t for t in tokens if len(re.findall(r"[\u0590-\u05FF]", t)) >= 2]
        
        if len(heb_tokens) < 5: return False

        starts_final = 0
        for tok in heb_tokens:
            first_heb = next((ch for ch in tok if "\u0590" <= ch <= "\u05FF"), None)
            if first_heb in FINAL_LETTERS:
                starts_final += 1

        return (starts_final / len(heb_tokens)) > 0.15

    def fix_reversed_hebrew_words(self, text: str) -> str:
        def should_reverse(tok: str) -> bool:
            if re.search(r"[A-Za-z]", tok): return False
            heb = len(re.findall(r"[\u0590-\u05FF]", tok))
            if heb < 2: return False
            digits = len(re.findall(r"\d", tok))
            non_space = len(re.sub(r"\s", "", tok))
            if non_space == 0: return False
            return heb / non_space >= 0.5 and digits / non_space <= 0.4

        tokens = re.findall(r"\s+|[^\s]+", text)
        out = []
        for tok in tokens:
            if tok.isspace(): out.append(tok)
            elif should_reverse(tok): out.append(tok[::-1])
            else: out.append(tok)
        return "".join(out)

    def fix_reversed_hebrew_word_order(self, text: str) -> str:
        tokens = re.findall(r"\s+|[^\s]+", text)
        words = [t for t in tokens if not t.isspace()]
        words.reverse()
        out = []
        wi = 0
        for t in tokens:
            if t.isspace(): out.append(t)
            else:
                out.append(words[wi])
                wi += 1
        return "".join(out)

    # =========================================================================
    #  NEW LOGIC: MERGING LINES INTO BLOCKS
    # =========================================================================

    def _merge_lines_into_blocks(self, lines: List[Dict], median_font_size: float) -> List[Dict]:
        """
        מאחדת שורות בודדות לפסקאות/בלוקים על בסיס קרבה וגודל פונט.
        """
        if not lines:
            return []

        merged_blocks = []
        
        # מתחילים את הבלוק הראשון עם השורה הראשונה
        current_block = lines[0].copy()
        current_block["line_count"] = 1 # מעקב כמה שורות איחדנו

        for i in range(1, len(lines)):
            next_line = lines[i]
            
            # 1. חישוב המרחק האנכי בין תחתית הבלוק הנוכחי לתחילת השורה הבאה
            gap = next_line["y_top"] - current_block["y_bottom"]
            
            # 2. בדיקת דמיון בגודל פונט (טולרנס של 1.5 נקודות)
            font_diff = abs(next_line["font_size"] - current_block["font_size"])
            is_same_font = font_diff < 1.5

            # 3. סף לרווח (Gap Threshold):
            # אם הרווח קטן מ-1.5 מגובה השורה הנוכחית, זה כנראה המשך פסקה.
            # אם הרווח גדול, זו פסקה חדשה.
            # (ב-OCR/PDF לעיתים הרווח הוא שלילי או אפס אם יש חפיפה, גם זה נחשב קרוב)
            max_gap_allowed = current_block["font_size"] * 1.5
            is_close_enough = gap < max_gap_allowed

            # תנאי האיחוד: אותו פונט (בערך) + קרובים פיזית
            if is_same_font and is_close_enough:
                # איחוד: מוסיפים את הטקסט ומעדכנים את הגבול התחתון
                current_block["text"] += " " + next_line["text"]
                current_block["y_bottom"] = next_line["y_bottom"] # הבלוק גדל למטה
                current_block["line_count"] += 1
                
                # מעדכנים גודל פונט לממוצע או למקסימום (לבחירתך, נשאיר את המקורי לשמירת היררכיה)
            else:
                # סגירת הבלוק הנוכחי ופתיחת חדש
                merged_blocks.append(current_block)
                current_block = next_line.copy()
                current_block["line_count"] = 1

        # הוספת הבלוק האחרון שנשאר
        merged_blocks.append(current_block)
        return merged_blocks

    # =========================================================================
    #  PDF PROCESSING
    # =========================================================================

    def _process_pdfplumber_page(self, page, page_num) -> Optional[Dict]:
        words = page.extract_words(extra_attrs=["fontname", "size", "top", "bottom"])
        if not words: return None

        # בדיקה גלובלית אם העמוד הפוך
        all_text = " ".join([w["text"] for w in words])
        is_page_reversed = False
        if self.is_hebrew_text(all_text):
            is_page_reversed = self.looks_like_reversed_hebrew(all_text)

        # סטטיסטיקות
        sizes = [w["size"] for w in words]
        if not sizes: return None
        median_size = statistics.median(sizes)
        max_size = max(sizes)

        # שלב 1: יצירת שורות (כמו קודם)
        lines = []
        current_line = [words[0]]
        for word in words[1:]:
            if abs(word["top"] - current_line[-1]["top"]) < 3:
                current_line.append(word)
            else:
                lines.append(current_line)
                current_line = [word]
        lines.append(current_line)

        # המרת אובייקטי PDFPlumber למילון פשוט
        raw_lines_dicts = []
        for line_words in lines:
            line_text = " ".join([w["text"] for w in line_words])
            
            # תיקון עברית (כולל התיקון הגלובלי שהוספנו קודם)
            if self.is_hebrew_text(line_text):
                if is_page_reversed or self.looks_like_reversed_hebrew(line_text):
                    line_text = self.fix_reversed_hebrew_words(line_text)
                    line_text = self.fix_reversed_hebrew_word_order(line_text)

            line_max_size = max([w["size"] for w in line_words])
            line_top = min([w["top"] for w in line_words])
            line_bottom = max([w["bottom"] for w in line_words])

            raw_lines_dicts.append({
                "text": line_text,
                "font_size": round(line_max_size, 2),
                "y_top": round(line_top, 2),
                "y_bottom": round(line_bottom, 2),
                "ratio_to_body": round(line_max_size / median_size, 2) if median_size > 0 else 1.0
            })

        # שלב 2: איחוד השורות לבלוקים (החלק החדש)
        merged_blocks = self._merge_lines_into_blocks(raw_lines_dicts, median_size)

        return {
            "page_num": page_num,
            "stats": {
                "median_font_size": round(median_size, 2),
                "max_font_size": round(max_size, 2)
            },
            "blocks": merged_blocks # שיניתי את השם מ-lines ל-blocks
        }

    # =========================================================================
    #  OCR PROCESSING
    # =========================================================================

    def _process_tesseract_image(self, image, page_num) -> Optional[Dict]:
        data = pytesseract.image_to_data(image, lang="heb", output_type=Output.DICT)
        n_boxes = len(data['text'])
        
        lines_map = {} 
        for i in range(n_boxes):
            text = data['text'][i].strip()
            if not text: continue
            
            line_key = (data['block_num'][i], data['par_num'][i], data['line_num'][i])
            if line_key not in lines_map:
                lines_map[line_key] = {"words": [], "heights": [], "tops": [], "bottoms": []}
            
            lines_map[line_key]["words"].append(text)
            lines_map[line_key]["heights"].append(data['height'][i])
            lines_map[line_key]["tops"].append(data['top'][i])
            lines_map[line_key]["bottoms"].append(data['top'][i] + data['height'][i])

        if not lines_map: return None

        all_heights = [h for val in lines_map.values() for h in val["heights"]]
        if not all_heights: return None
        
        median_height = statistics.median(all_heights)
        max_height = max(all_heights)

        # המרה למילון שורות פשוט ומיון לפי Top
        sorted_keys = sorted(lines_map.keys(), key=lambda k: min(lines_map[k]["tops"]))
        raw_lines_dicts = []

        for key in sorted_keys:
            val = lines_map[key]
            line_text = " ".join(val["words"])
            avg_height = sum(val["heights"]) / len(val["heights"])
            min_top = min(val["tops"])
            max_bottom = max(val["bottoms"])

            raw_lines_dicts.append({
                "text": line_text,
                "font_size": round(avg_height, 2),
                "y_top": round(min_top, 2),
                "y_bottom": round(max_bottom, 2),
                "ratio_to_body": round(avg_height / median_height, 2) if median_height > 0 else 1.0,
                "source": "ocr"
            })

        # שלב האיחוד לבלוקים גם ב-OCR
        merged_blocks = self._merge_lines_into_blocks(raw_lines_dicts, median_height)

        return {
            "page_num": page_num,
            "stats": {
                "median_font_size": round(median_height, 2),
                "max_font_size": round(max_height, 2)
            },
            "blocks": merged_blocks
        }

    # =========================================================================
    #  MAIN METHODS
    # =========================================================================

    def extract_structured_from_pdf(self, pdf_path: str) -> List[Dict]:
        try:
            pages_data = []
            has_valid_text = False
            
            with pdfplumber.open(pdf_path) as pdf:
                for i, page in enumerate(pdf.pages):
                    p_data = self._process_pdfplumber_page(page, i + 1)
                    if p_data:
                        pages_data.append(p_data)
            
            if pages_data:
                sample_text = " ".join([b['text'] for b in pages_data[0]['blocks'][:3]])
                if self.is_hebrew_text(sample_text):
                    return pages_data
            
            print("Direct extraction poor. Switching to OCR...")
            return self.extract_structured_from_pdf_images(pdf_path)

        except Exception as e:
            print(f"Error in PDF extraction: {e}. Switching to OCR...")
            return self.extract_structured_from_pdf_images(pdf_path)

    def extract_structured_from_pdf_images(self, pdf_path: str) -> List[Dict]:
        structured_output = []
        try:
            doc = fitz.open(pdf_path)
            for page_num in range(len(doc)):
                page = doc[page_num]
                mat = fitz.Matrix(2, 2)
                pix = page.get_pixmap(matrix=mat)
                img = Image.open(io.BytesIO(pix.tobytes("png")))
                
                page_data = self._process_tesseract_image(img, page_num + 1)
                if page_data:
                    structured_output.append(page_data)
            doc.close()
            return structured_output
        except Exception:
            return []

    def process_file(self, file_path: str) -> str:
        if not os.path.exists(file_path):
            return json.dumps({"error": "File not found"}, ensure_ascii=False)

        file_type = self.detect_file_type(file_path)
        final_structure = []

        if file_type == "application/pdf":
            final_structure = self.extract_structured_from_pdf(file_path)
        elif file_type.startswith("image/"):
            # טיפול בתמונות (בקיצור)
            image_path = file_path
            # ... המרת ffmpeg אם צריך ...
            try:
                img = Image.open(image_path)
                page_data = self._process_tesseract_image(img, 1)
                if page_data: final_structure = [page_data]
            except Exception: pass
        
        else:
            return json.dumps({"error": "Unsupported"}, ensure_ascii=False)

        result = {
            "file_name": os.path.basename(file_path),
            "pages": final_structure
        }
        return json.dumps(result, ensure_ascii=False, indent=2)