__import__('pysqlite3')
import sys
sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')

import chromadb
from app.indexing.db import get_collection
from app.indexing.embedder import embed

# 1. אתחול
collection = get_collection()
embedder = embed()

def test_query(user_query):
    print(f"\n🔎 שאילתה: '{user_query}'")
    
    # המרת השאילתה לוקטור באמצעות AlephBERT
    query_vector = embedder.embed_text(user_query)
    
    # שליפה מ-ChromaDB
    results = collection.query(
        query_embeddings=[query_vector],
        n_results=3,
        include=["documents", "metadatas", "distances"]
    )
    
    # 2. ניתוח התוצאות
    for i in range(len(results['ids'][0])):
        dist = results['distances'][0][i]
        text = results['documents'][0][i][:100] # הצגת התחלת הטקסט
        page = results['metadatas'][0][i]['page_num']
        
        # הערכת איכות לפי המרחק (Distance)
        quality = "🌟 מצוין" if dist < 0.5 else "⚠️ רחוק/רעש"
        print(f"[{i+1}] מרחק: {dist:.4f} ({quality}) | עמוד: {page} | טקסט: {text}...")

# 3. הרצת הבדיקות
# שאילתה רלוונטית (Top-K Test)
test_query("מה זה גנרטיב AI?")

# שאילתת רעש (Noise Test)
test_query("איך מכינים פיצה בבית?")