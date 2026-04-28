import chromadb
from pathlib import Path
import app.registry as registry # ודאי שהקובץ קיים ב-app/

# 1. הגדרות
doc_id = "43358c29-64fe-4865-b6a2-71d0c3b68ccd"
client = chromadb.PersistentClient(path="./data/index")
collection = client.get_collection(name="documents")

print(f"--- מריץ ניקוי מלא עבור מסמך: {doc_id} ---")

# 2. מחיקה מ-ChromaDB
initial_count = collection.count()
collection.delete(where={"document_id": doc_id})
print(f"✅ נמחקו {initial_count - collection.count()} וקטורים מ-ChromaDB.")

# 3. מחיקת קבצים פיזיים (לפי מבנה התיקיות ב-Phase 1)
paths_to_delete = [
    Path(f"data/raw/{doc_id}.pdf"),
    Path(f"data/ocr/{doc_id}.json"),
    Path(f"data/chunks/{doc_id}_chunks.json")
]

for p in paths_to_delete:
    if p.exists():
        p.unlink() # מוחק את הקובץ
        print(f"✅ הקובץ נמחק: {p}")
    else:
        print(f"⚠️ קובץ לא נמצא (ייתכן שכבר נמחק): {p}")

# 4. עדכון ה-Registry (לפי Phase 1)
try:
    # כאן את קוראת לפונקציית המחיקה שמימשת ב-Phase 1
    registry.delete_document(doc_id) 
    print(f"✅ המסמך הוסר מה-Registry.")
except Exception as e:
    print(f"❌ שגיאה בעדכון ה-Registry: {e}")

print("\n--- הניקוי הסתיים בהצלחה ---")