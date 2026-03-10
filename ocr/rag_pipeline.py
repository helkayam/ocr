import os
import json
from groq import Groq
from search_engine import LocalVectorSearch

# ==========================================
#  הגדרות
# ==========================================
GROQ_API_KEY = "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"
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
        user_input = input("\nשאלי שאלה על הקובץ (או 'exit' ליציאה): ")
        if user_input.lower() == 'exit':
            break
            
        answer, sources = rag_system.generate_answer(user_input)
        
        print("\n" + "="*50)
        print(f"תשובה:\n{answer}")
        print("="*50)
        
        print("\nהצ'אנקים ששימשו את המודל:")
        for s in sources:
            # מדפיס את ה-ID והעמודים כפי שמופיעים ב-JSON
            print(f"- {s['chunk_id']} (ציון דמיון: {s['score']})")