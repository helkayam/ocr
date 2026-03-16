import json
import os
import glob
from typing import List, Dict, Any

# נסיון לייבא ספרייה לספירה מדויקת של טוקנים (כמו GPT-4)
# אם לא קיימת, נשתמש בחישוב משוער
try:
    import tiktoken
    ENC = tiktoken.get_encoding("cl100k_base")
except ImportError:
    ENC = None

class SmartChunker:
    def __init__(self, max_tokens: int = 500, overlap_tokens: int = 50):
        """
        :param max_tokens: גודל מקסימלי לצ'אנק (בטוקנים)
        :param overlap_tokens: גודל החפיפה בין צ'אנקים
        """
        self.max_tokens = max_tokens
        self.overlap_tokens = overlap_tokens

    def _count_tokens(self, text: str) -> int:
        """ספירה מדויקת או משוערת של טוקנים"""
        if not text:
            return 0
        if ENC:
            return len(ENC.encode(text))
        else:
            # הערכה גסה: מילה ממוצעת בעברית/אנגלית ~ 1.5 טוקנים
            return int(len(text.split()) * 1.5)

    def _is_header(self, block: Dict) -> bool:
        """מזהה אם הבלוק הוא כותרת לפי המטא-דאטה מה-OCR"""
        # יחס של מעל 1.15 לגודל הטקסט הרגיל מעיד בד"כ על כותרת
        return block.get("ratio_to_body", 1.0) > 1.15

    def create_chunks_from_file_data(self, ocr_data: Dict) -> List[Dict]:
        """מקבל את ה-JSON של ה-OCR ומחזיר צ'אנקים מוגני טבלאות"""
        file_name = ocr_data.get("file_name", "unknown")
        all_blocks = []
        
        # 1. שיטוח הבלוקים
        for page in ocr_data.get("pages", []):
            page_num = page.get("page_num", 0)
            for block in page.get("blocks", []):
                block["page_num"] = page_num 
                all_blocks.append(block)

        chunks = []
        current_chunk_blocks = []
        current_tokens = 0
        last_h1 = ""
        last_h2 = ""

        i = 0
        while i < len(all_blocks):
            block = all_blocks[i]
            block_text = block.get("text", "")
            block_type = block.get("type", "text") # זיהוי אם זו טבלה
            
            if not block_text.strip():
                i += 1
                continue

            block_tokens = self._count_tokens(block_text)
            is_header = self._is_header(block)

            # --- לוגיקת חיתוך חכמה ---
            
            is_full = (current_tokens + block_tokens) > self.max_tokens
            should_split_before_header = is_header and current_tokens > (self.max_tokens * 0.1)

            # הגנה על טבלאות: אם הבלוק הבא הוא טבלה והצ'אנק כבר מלא חלקית, נחתוך לפניו
            should_split_before_table = (block_type == "table") and (current_tokens > self.max_tokens * 0.3)

            if (is_full or should_split_before_header or should_split_before_table) and current_chunk_blocks:
                # סגירת הצ'אנק הנוכחי
                chunks.append(self._finalize_chunk(current_chunk_blocks, file_name, last_h1, last_h2))

                # חפיפה (Overlap) - לא לוקחים טבלאות לחפיפה כדי לא לשבור פורמט
                overlap_blocks = []
                overlap_cnt = 0
                for prev_block in reversed(current_chunk_blocks):
                    if prev_block.get("type") == "table":
                        break # עוצרים חפיפה אם הגענו לטבלה
                    
                    prev_len = self._count_tokens(prev_block["text"])
                    if overlap_cnt + prev_len <= self.overlap_tokens:
                        overlap_blocks.insert(0, prev_block)
                        overlap_cnt += prev_len
                    else:
                        break 
                
                current_chunk_blocks = overlap_blocks[:]
                current_tokens = overlap_cnt

            # עדכון הקשר (Context) - קורה רק אחרי שהחלטנו אם לחתוך
            if is_header:
                ratio = block.get("ratio_to_body", 1.0)
                if ratio > 1.4: 
                    last_h1 = block_text
                    last_h2 = "" 
                else: 
                    last_h2 = block_text

            # הוספת הבלוק לצ'אנק
            current_chunk_blocks.append(block)
            current_tokens += block_tokens
            i += 1

        # שאריות
        if current_chunk_blocks:
            chunks.append(self._finalize_chunk(current_chunk_blocks, file_name, last_h1, last_h2))

        return chunks

    def _finalize_chunk(self, blocks: List[Dict], file_name: str, h1_ctx: str, h2_ctx: str) -> Dict:
        """בניית אובייקט הצ'אנק הסופי"""
        full_text = "\n".join([b["text"] for b in blocks])
        pages = sorted(list(set([b["page_num"] for b in blocks])))
        
        # בניית מחרוזת הקשר
        context_parts = []
        if h1_ctx: context_parts.append(h1_ctx)
        if h2_ctx: context_parts.append(h2_ctx)
        context_str = " > ".join(context_parts)
        
        # טקסט עשיר להטמעה (Embedding)
        text_with_context = f"Context: {context_str}\n---\n{full_text}" if context_str else full_text

        # יצירת ID דטרמיניסטי (כדי שאם נריץ שוב, נקבל אותו ID לאותו טקסט)
        chunk_hash = abs(hash(full_text)) % 1000000
        chunk_id = f"{file_name}_p{pages[0]}_{chunk_hash}"

        return {
            "id": chunk_id,
            "text": full_text,
            "text_with_context": text_with_context,
            "metadata": {
                "source": file_name,
                "pages": pages,
                "token_count": self._count_tokens(full_text),
                "context_h1": h1_ctx,
                "context_h2": h2_ctx
            }
        }

def process_directory(input_dir: str, output_file: str):
    """
    הפונקציה הראשית: עוברת על כל הקבצים ומייצרת קובץ פלט אחד.
    """
    chunker = SmartChunker(max_tokens=600, overlap_tokens=100)
    all_chunks_aggregated = []

    print(f"--- Starting Chunking Process ---")
    print(f"Input Directory: {input_dir}")
    
    if not os.path.exists(input_dir):
        print(f"Error: Input directory '{input_dir}' does not exist.")
        return

    # מציאת כל קבצי ה-JSON בתיקייה
    json_files = glob.glob(os.path.join(input_dir, "*.json"))
    
    if not json_files:
        print("No JSON files found to process.")
        return

    for json_path in json_files:
        filename = os.path.basename(json_path)
        print(f"Processing: {filename}...", end=" ")
        
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # יצירת צ'אנקים לקובץ הנוכחי
            file_chunks = chunker.create_chunks_from_file_data(data)
            all_chunks_aggregated.extend(file_chunks)
            
            print(f"Done ({len(file_chunks)} chunks).")
            
        except Exception as e:
            print(f"Error: {e}")

    # שמירת כל התוצאות לקובץ אחד גדול
    # קודם וודא שתיקיית הפלט קיימת
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    print(f"--- Saving Results ---")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(all_chunks_aggregated, f, indent=2, ensure_ascii=False)
    
    print(f"Successfully saved {len(all_chunks_aggregated)} chunks to: {output_file}")


# ==========================================
#  MAIN EXECUTION
# ==========================================
if __name__ == "__main__":
    # הגדרת נתיבים (ניתן לשנות כאן)
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    
    # תיקיית הקלט (איפה שנמצאים קבצי ה-JSON מהשלב הקודם)
    OCR_JSON_DIR = os.path.join(BASE_DIR, "test_files_json")
    
    # קובץ הפלט הסופי
    CHUNKS_OUTPUT = os.path.join(BASE_DIR, "chunks.json")

    # הפעלת התהליך
    process_directory(OCR_JSON_DIR, CHUNKS_OUTPUT)