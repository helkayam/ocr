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

# ── Paragraph-merging thresholds ──────────────────────────────────────────────
# Lines whose ratio_to_body meets this threshold are treated as headers and
# never merged with adjacent body text.
_HEADER_RATIO = 1.2

# Maximum vertical gap (as a multiple of the current line's font size) that is
# still considered "within the same paragraph".  Real-world PDFs with 1.15–1.5×
# leading produce inter-line gaps up to ~2× the font size; 2.8× leaves a
# comfortable margin before we start merging across genuine paragraph breaks
# (which typically produce gaps of 3–5× the font size).
_GAP_BODY_FACTOR = 2.8

# When the current line does not end with sentence-terminating punctuation the
# gap tolerance is relaxed further: an unfinished sentence is strong evidence
# we are still inside the same paragraph.
_GAP_CONT_FACTOR = 4.2

# Maximum font-size difference (pt) allowed between two consecutive body lines
# before they are split into separate blocks.  OCR routinely reports 0.5–2 pt
# variation for visually identical fonts; 3.0 pt catches real font changes.
_FONT_DIFF_BODY = 3.0

# Sentence-terminating characters in both Latin and Hebrew typography.
_SENTENCE_END_OCR = frozenset(".!?״׃")


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
        hebrew_pattern = re.compile(r"[֐-׿]")
        hebrew_chars = hebrew_pattern.findall(text)
        total_chars = len(re.sub(r"\s", "", text))
        if total_chars == 0:
            return False
        return (len(hebrew_chars) / total_chars) >= 0.15

    def looks_like_reversed_hebrew(self, text: str) -> bool:
        FINAL_LETTERS = set("םןץףך")
        tokens = re.findall(r"\S+", text)
        heb_tokens = [t for t in tokens if len(re.findall(r"[֐-׿]", t)) >= 2]

        if len(heb_tokens) < 5:
            return False

        starts_final = 0
        for tok in heb_tokens:
            first_heb = next((ch for ch in tok if "֐" <= ch <= "׿"), None)
            if first_heb in FINAL_LETTERS:
                starts_final += 1

        return (starts_final / len(heb_tokens)) > 0.15

    def fix_reversed_hebrew_words(self, text: str) -> str:
        def should_reverse(tok: str) -> bool:
            if re.search(r"[A-Za-z]", tok):
                return False
            heb = len(re.findall(r"[֐-׿]", tok))
            if heb < 2:
                return False
            digits = len(re.findall(r"\d", tok))
            non_space = len(re.sub(r"\s", "", tok))
            if non_space == 0:
                return False
            return heb / non_space >= 0.5 and digits / non_space <= 0.4

        tokens = re.findall(r"\s+|[^\s]+", text)
        out = []
        for tok in tokens:
            if tok.isspace():
                out.append(tok)
            elif should_reverse(tok):
                out.append(tok[::-1])
            else:
                out.append(tok)
        return "".join(out)

    def fix_reversed_hebrew_word_order(self, text: str) -> str:
        tokens = re.findall(r"\s+|[^\s]+", text)
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
        return "".join(out)

    def _apply_hebrew_fixes(self, text: str, is_reversed_page: bool) -> str:
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
            processed_row = [self._apply_hebrew_fixes(str(cell or ""), is_reversed_page) for cell in row]
            processed_rows.append(processed_row)

        md = "| " + " | ".join(processed_rows[0]) + " |\n"
        md += "| " + " | ".join(["---"] * len(processed_rows[0])) + " |\n"
        for row in processed_rows[1:]:
            md += "| " + " | ".join(row) + " |\n"

        return md.strip()

    # =========================================================================
    #  PARAGRAPH MERGING
    # =========================================================================

    def _merge_lines_into_blocks(self, lines: List[Dict], median_font_size: float) -> List[Dict]:
        """Merge per-line dicts into paragraph-level blocks.

        Lines whose ratio_to_body >= _HEADER_RATIO are treated as standalone
        headers and are never merged with adjacent body text.  For body lines,
        the vertical gap tolerance is 2.8× the font size (relaxed to 4.2× when
        the current line ends mid-sentence), and the font-size tolerance is 3 pt.
        After merging, blocks that are visually prominent (high ratio, ≤2 lines)
        are promoted to type="header" so Phase 4 can consume them unambiguously.
        """
        if not lines:
            return []

        merged: List[Dict] = []
        cur = lines[0].copy()
        cur["line_count"] = 1

        for nxt in lines[1:]:
            cur_is_hdr = cur.get("ratio_to_body", 1.0) >= _HEADER_RATIO
            nxt_is_hdr = nxt.get("ratio_to_body", 1.0) >= _HEADER_RATIO

            # Headers are always standalone — never merge into or out of one
            if cur_is_hdr or nxt_is_hdr:
                merged.append(cur)
                cur = nxt.copy()
                cur["line_count"] = 1
                continue

            gap       = nxt["y_top"] - cur["y_bottom"]
            font_diff = abs(nxt["font_size"] - cur["font_size"])

            tail         = cur["text"].rstrip()
            continuation = bool(tail) and tail[-1] not in _SENTENCE_END_OCR
            gap_limit    = cur["font_size"] * (_GAP_CONT_FACTOR if continuation else _GAP_BODY_FACTOR)

            if font_diff <= _FONT_DIFF_BODY and gap < gap_limit:
                cur["text"]       += " " + nxt["text"]
                cur["y_bottom"]    = nxt["y_bottom"]
                cur["line_count"] += 1
            else:
                merged.append(cur)
                cur = nxt.copy()
                cur["line_count"] = 1

        merged.append(cur)

        # Promote visually prominent single/double lines to type="header".
        # Phase 4 (splitter.py) reads this field directly and no longer needs
        # to re-derive headers from font ratios.
        for blk in merged:
            if (
                blk.get("ratio_to_body", 1.0) >= _HEADER_RATIO
                and blk.get("line_count", 1) <= 2
            ):
                blk["type"] = "header"

        return merged

    # =========================================================================
    #  PDF PROCESSING
    # =========================================================================

    def _process_pdfplumber_page(self, page, page_num) -> Optional[Dict]:
        all_raw_text = page.extract_text() or ""
        is_page_reversed = self.is_hebrew_text(all_raw_text) and self.looks_like_reversed_hebrew(all_raw_text)

        all_blocks = []

        words = page.extract_words(extra_attrs=["fontname", "size", "top", "bottom"])
        if not words:
            return None

        sizes       = [w["size"] for w in words]
        median_size = statistics.median(sizes)
        max_size    = max(sizes)

        lines = []
        current_line = [words[0]]
        for word in words[1:]:
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
                "text":          line_text,
                "font_size":     round(max([w["size"] for w in line_words]), 2),
                "y_top":         round(min([w["top"] for w in line_words]), 2),
                "y_bottom":      round(max([w["bottom"] for w in line_words]), 2),
                "ratio_to_body": round(max([w["size"] for w in line_words]) / median_size, 2) if median_size > 0 else 1.0,
                "type":          "text",
            })

        text_blocks = self._merge_lines_into_blocks(raw_text_lines, median_size)
        all_blocks.extend(text_blocks)
        all_blocks.sort(key=lambda x: x["y_top"])

        return {
            "page_num": page_num,
            "stats": {
                "median_font_size": round(median_size, 2),
                "max_font_size":    round(max_size, 2),
            },
            "blocks": all_blocks,
        }

    def _process_tesseract_image(self, image, page_num) -> Optional[Dict]:
        data     = pytesseract.image_to_data(image, lang="heb", output_type=Output.DICT)
        n_boxes  = len(data["text"])
        lines_map: Dict[Any, Any] = {}

        for i in range(n_boxes):
            text = data["text"][i].strip()
            if not text:
                continue
            line_key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
            if line_key not in lines_map:
                lines_map[line_key] = {"words": [], "heights": [], "tops": [], "bottoms": []}
            lines_map[line_key]["words"].append(text)
            lines_map[line_key]["heights"].append(data["height"][i])
            lines_map[line_key]["tops"].append(data["top"][i])
            lines_map[line_key]["bottoms"].append(data["top"][i] + data["height"][i])

        if not lines_map:
            return None

        all_heights   = [h for val in lines_map.values() for h in val["heights"]]
        median_height = statistics.median(all_heights)
        max_height    = max(all_heights)
        sorted_keys   = sorted(lines_map.keys(), key=lambda k: min(lines_map[k]["tops"]))

        raw_lines_dicts = []
        for key in sorted_keys:
            val      = lines_map[key]
            line_text = " ".join(val["words"])
            avg_height = sum(val["heights"]) / len(val["heights"])
            raw_lines_dicts.append({
                "text":          line_text,
                "font_size":     round(avg_height, 2),
                "y_top":         round(min(val["tops"]), 2),
                "y_bottom":      round(max(val["bottoms"]), 2),
                "ratio_to_body": round(avg_height / median_height, 2) if median_height > 0 else 1.0,
                "type":          "text",
            })

        return {
            "page_num": page_num,
            "stats": {
                "median_font_size": round(median_height, 2),
                "max_font_size":    round(max_height, 2),
            },
            "blocks": self._merge_lines_into_blocks(raw_lines_dicts, median_height),
        }

    def extract_structured_from_pdf(self, pdf_path: str) -> List[Dict]:
        try:
            pages_data = []
            with pdfplumber.open(pdf_path) as pdf:
                for i, page in enumerate(pdf.pages):
                    p_data = self._process_pdfplumber_page(page, i + 1)
                    if p_data:
                        pages_data.append(p_data)

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
                mat  = fitz.Matrix(2, 2)
                pix  = page.get_pixmap(matrix=mat)
                img  = Image.open(io.BytesIO(pix.tobytes("png")))
                page_data = self._process_tesseract_image(img, page_num + 1)
                if page_data:
                    structured_output.append(page_data)
            doc.close()
            return structured_output
        except Exception:
            return []

    def process_file(self, file_path: str) -> str:
        if not os.path.exists(file_path):
            return json.dumps({"error": "File not found"})
        file_type      = self.detect_file_type(file_path)
        final_structure: List[Dict] = []
        if file_type == "application/pdf":
            final_structure = self.extract_structured_from_pdf(file_path)
        elif file_type.startswith("image/"):
            try:
                img       = Image.open(file_path)
                page_data = self._process_tesseract_image(img, 1)
                if page_data:
                    final_structure = [page_data]
            except Exception:
                pass
        result = {"file_name": os.path.basename(file_path), "pages": final_structure}
        return json.dumps(result, ensure_ascii=False, indent=2)
