import os
import json
from groq import Groq
from search_engine import LocalVectorSearch
from bidi.algorithm import get_display
import arabic_reshaper


def fix_hebrew(text):
    # מפצלים את הטקסט לשורות נפרדות
    lines = text.split('\n')
    fixed_lines = []
    
    for line in lines:
        # מתקנים כל שורה בנפרד
        reshaped_line = arabic_reshaper.reshape(line)
        display_line = get_display(reshaped_line)
        fixed_lines.append(display_line)
        
    # מחברים את השורות חזרה עם ירידת שורה
    return '\n'.join(fixed_lines)

# ==========================================
#  הגדרות
# ==========================================
groq_api_key = os.getenv("GROQ_API_KEY")
CHUNKS_FILE = "chunks.json" # הקובץ שנוצר מהצאנקר שלך

class HebrewRAG:


    def __init__(self, api_key: str, chunks_path: str):
        self.client = Groq(api_key=api_key)
        # טעינת מנוע החיפוש המקומי שכתבנו
        self.searcher = LocalVectorSearch(chunks_path)

    def generate_answer(self, query: str):
        # 1. שליפה (Retrieval)
        # אנחנו לוקחים את 4 הצ'אנקים הכי רלוונטיים
        print(f"Searching for relevant info...")
        results = self.searcher.search(query, top_k=4)
        
        # 2. בניית ההקשר (Augmentation)
        # אנחנו משתמשים בטקסט הגולמי של הצ'אנקים מה-JSON שלך
        context_text = ""
        for i, res in enumerate(results):
            context_text += f"\n--- מקור {i+1} (מתוך {res['metadata']['source']}, עמוד {res['metadata']['pages']}) ---\n"
            context_text += res['text'] + "\n"

        # 3. יצירת הפרומפט (Prompt Engineering)
        prompt = f"""
        אתה עוזר מחקר חכם שמתבסס אך ורק על המידע המצורף מטה.
        עליך לענות על שאלת המשתמש בעברית רהוטה ומדויקת.
        
        הוראות קשיחות:
        1. אם התשובה לא נמצאת במידע המצורף, אמור במפורש שאינך יודע.
        2. אל תשתמש בידע קודם שלך, אלא רק במה שכתוב כאן.
        3. בסוף התשובה, ציין מאילו עמודים לקחת את המידע.

        המידע מהמסמכים:
        {context_text}

        השאלה של המשתמש: {query}
        """

        # 4. יצירה (Generation) דרך Groq
        print(f"Generating answer with Groq...")
        completion = self.client.chat.completions.create(
            model="llama-3.3-70b-versatile", # מודל חזק מאוד ומהיר בטירוף
            messages=[
                {"role": "system", "content": "אתה מומחה לניתוח מסמכים בעברית."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2, # ערך נמוך כדי שהתשובות יהיו עובדתיות ולא יצירתיות
        )
        
        return completion.choices[0].message.content, results

# ==========================================
#  הרצה
# ==========================================
if __name__ == "__main__":
    rag_system = HebrewRAG(GROQ_API_KEY, CHUNKS_FILE)
    
    while True:
        # מדפיסים את ההנחיה בשורה נפרדת עם התיקון
        print(fix_hebrew("\nשאלי שאלה על הקובץ (או 'exit' ליציאה):"))
        # מקבלים קלט נקי בלי שום פונקציה מסביב
        user_input = input("> ") 
        
        if user_input.lower() == 'exit':
            break
        
        if not user_input.strip():
            continue

        answer, sources = rag_system.generate_answer(user_input)
        
        print("\n" + "="*50)
        print(f"תשובה:\n{answer}")
        print("="*50)