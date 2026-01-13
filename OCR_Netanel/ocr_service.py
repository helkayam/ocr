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
    #  HEBREW HANDLING (הפונקציות המקוריות שלך ללא שינוי)
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

    def _apply_hebrew_fixes(self, text: str, is_reversed_page: bool) -> str:
        """פונקציית עזר להחלת התיקונים שלך בצורה עקבית"""
        if not self.is_hebrew_text(text):
            return text
        if is_reversed_page or self.looks_like_reversed_hebrew(text):
            text = self.fix_reversed_hebrew_words(text)
            text = self.fix_reversed_hebrew_word_order(text)
        return text

    # =========================================================================
    #  TABLE EXTRACTION TO MARKDOWN
    # =========================================================================

    def _format_table_as_markdown(self, table_data: List[List[str]], is_reversed_page: bool) -> str:
        if not table_data:
            return ""
        
        processed_rows = []
        for row in table_data:
            # תיקון עברית לכל תא בנפרד
            processed_row = [self._apply_hebrew_fixes(str(cell or ""), is_reversed_page) for cell in row]
            processed_rows.append(processed_row)

        # בניית מחרוזת Markdown
        md = "| " + " | ".join(processed_rows[0]) + " |\n"
        md += "| " + " | ".join(["---"] * len(processed_rows[0])) + " |\n"
        for row in processed_rows[1:]:
            md += "| " + " | ".join(row) + " |\n"
        
        return md.strip()

    # =========================================================================
    #  NEW LOGIC: MERGING LINES INTO BLOCKS
    # =========================================================================

    def _merge_lines_into_blocks(self, lines: List[Dict], median_font_size: float) -> List[Dict]:
        if not lines: return []
        merged_blocks = []
        current_block = lines[0].copy()
        current_block["line_count"] = 1

        for i in range(1, len(lines)):
            next_line = lines[i]
            gap = next_line["y_top"] - current_block["y_bottom"]
            font_diff = abs(next_line["font_size"] - current_block["font_size"])
            max_gap_allowed = current_block["font_size"] * 1.5

            if font_diff < 1.5 and gap < max_gap_allowed:
                current_block["text"] += " " + next_line["text"]
                current_block["y_bottom"] = next_line["y_bottom"]
                current_block["line_count"] += 1
            else:
                merged_blocks.append(current_block)
                current_block = next_line.copy()
                current_block["line_count"] = 1

        merged_blocks.append(current_block)
        return merged_blocks

    # =========================================================================
    #  PDF PROCESSING
    # =========================================================================

    def _process_pdfplumber_page(self, page, page_num) -> Optional[Dict]:
        # 1. זיהוי טבלאות ומיקומן
        tables = page.find_tables()
        table_bboxes = [t.bbox for t in tables]
        
        # 2. בדיקה אם העמוד הפוך
        all_raw_text = page.extract_text() or ""
        is_page_reversed = self.is_hebrew_text(all_raw_text) and self.looks_like_reversed_hebrew(all_raw_text)

        all_blocks = []

        # 3. חילוץ טבלאות כ-Markdown
        for table_obj in tables:
            raw_table_data = table_obj.extract()
            md_text = self._format_table_as_markdown(raw_table_data, is_page_reversed)
            
            all_blocks.append({
                "text": md_text,
                "type": "table",
                "y_top": table_obj.bbox[1],
                "y_bottom": table_obj.bbox[3],
                "font_size": 11.0, # ברירת מחדל לטבלה
                "ratio_to_body": 1.0,
                "line_count": len(raw_table_data)
            })

        # 4. חילוץ טקסט שאינו בתוך טבלה
        words = page.extract_words(extra_attrs=["fontname", "size", "top", "bottom"])
        if not words and not all_blocks: return None

        # פונקציית עזר לבדוק אם מילה בתוך טבלה
        def is_in_table(w):
            for bbox in table_bboxes:
                if w["x0"] >= bbox[0] and w["top"] >= bbox[1] and w["x1"] <= bbox[2] and w["bottom"] <= bbox[3]:
                    return True
            return False

        non_table_words = [w for w in words if not is_in_table(w)]
        
        if non_table_words:
            sizes = [w["size"] for w in non_table_words]
            median_size = statistics.median(sizes)
            max_size = max(sizes)

            # יצירת שורות מטקסט רגיל
            lines = []
            current_line = [non_table_words[0]]
            for word in non_table_words[1:]:
                if abs(word["top"] - current_line[-1]["top"]) < 3:
                    current_line.append(word)
                else:
                    lines.append(current_line)
                    current_line = [word]
            lines.append(current_line)

            raw_text_lines = []
            for line_words in lines:
                line_text = " ".join([w["text"] for w in line_words])
                line_text = self._apply_hebrew_fixes(line_text, is_page_reversed)

                raw_text_lines.append({
                    "text": line_text,
                    "font_size": round(max([w["size"] for w in line_words]), 2),
                    "y_top": round(min([w["top"] for w in line_words]), 2),
                    "y_bottom": round(max([w["bottom"] for w in line_words]), 2),
                    "ratio_to_body": round(max([w["size"] for w in line_words]) / median_size, 2) if median_size > 0 else 1.0,
                    "type": "text"
                })

            text_blocks = self._merge_lines_into_blocks(raw_text_lines, median_size)
            all_blocks.extend(text_blocks)
        else:
            median_size = 11.0
            max_size = 11.0

        # 5. מיון סופי של כל הבלוקים (טקסט וטבלאות) לפי המיקום בעמוד
        all_blocks.sort(key=lambda x: x["y_top"])

        return {
            "page_num": page_num,
            "stats": {
                "median_font_size": round(median_size, 2),
                "max_font_size": round(max_size, 2)
            },
            "blocks": all_blocks
        }

    # (שאר הפונקציות - _process_tesseract_image, extract_structured_from_pdf וכו' נשארות ללא שינוי מהקוד שלך)

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
        median_height = statistics.median(all_heights)
        max_height = max(all_heights)
        sorted_keys = sorted(lines_map.keys(), key=lambda k: min(lines_map[k]["tops"]))
        raw_lines_dicts = []
        for key in sorted_keys:
            val = lines_map[key]
            line_text = " ".join(val["words"])
            avg_height = sum(val["heights"]) / len(val["heights"])
            raw_lines_dicts.append({
                "text": line_text,
                "font_size": round(avg_height, 2),
                "y_top": round(min(val["tops"]), 2),
                "y_bottom": round(max(val["bottoms"]), 2),
                "ratio_to_body": round(avg_height / median_height, 2) if median_height > 0 else 1.0,
                "type": "text"
            })
        return {
            "page_num": page_num,
            "stats": {"median_font_size": round(median_height, 2), "max_font_size": round(max_height, 2)},
            "blocks": self._merge_lines_into_blocks(raw_lines_dicts, median_height)
        }

    def extract_structured_from_pdf(self, pdf_path: str) -> List[Dict]:
        try:
            pages_data = []
            with pdfplumber.open(pdf_path) as pdf:
                for i, page in enumerate(pdf.pages):
                    p_data = self._process_pdfplumber_page(page, i + 1)
                    if p_data: pages_data.append(p_data)
            
            if pages_data:
                return pages_data
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
                if page_data: structured_output.append(page_data)
            doc.close()
            return structured_output
        except Exception: return []

    def process_file(self, file_path: str) -> str:
        if not os.path.exists(file_path): return json.dumps({"error": "File not found"})
        file_type = self.detect_file_type(file_path)
        final_structure = []
        if file_type == "application/pdf":
            final_structure = self.extract_structured_from_pdf(file_path)
        elif file_type.startswith("image/"):
            try:
                img = Image.open(file_path)
                page_data = self._process_tesseract_image(img, 1)
                if page_data: final_structure = [page_data]
            except Exception: pass
        result = {"file_name": os.path.basename(file_path), "pages": final_structure}
        return json.dumps(result, ensure_ascii=False, indent=2)