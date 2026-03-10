import json
import numpy as np
from typing import List, Dict
from sentence_transformers import SentenceTransformer

class LocalVectorSearch:
    def __init__(self, chunks_path: str, model_name: str = 'paraphrase-multilingual-MiniLM-L12-v2'):
        """
        :param model_name: מודל שתומך היטב בעברית ובאנגלית
        """
        print(f"Loading model: {model_name}...")
        self.model = SentenceTransformer(model_name)
        
        print(f"Loading chunks from {chunks_path}...")
        with open(chunks_path, 'r', encoding='utf-8') as f:
            self.chunks = json.load(f)
        
        # יצירת ה-Embeddings לכל הצ'אנקים (זה עשוי לקחת כמה שניות)
        print(f"Embedding {len(self.chunks)} chunks. Please wait...")
        texts_to_embed = [chunk['text_with_context'] for chunk in self.chunks]
        self.chunk_embeddings = self.model.encode(texts_to_embed, convert_to_tensor=True)
        print("Done!")

    def search(self, query: str, top_k: int = 3) -> List[Dict]:
        """חיפוש סמנטי לפי דמיון קוסינוס"""
        query_embedding = self.model.encode([query], convert_to_tensor=True)
        
        # חישוב דמיון קוסינוס (Cosine Similarity)
        import torch
        from sentence_transformers import util
        
        cos_scores = util.cos_sim(query_embedding, self.chunk_embeddings)[0]
        top_results = torch.topk(cos_scores, k=min(top_k, len(self.chunks)))
        
        results = []
        for score, idx in zip(top_results.values, top_results.indices):
            idx = idx.item()
            results.append({
                "score": round(float(score), 4),
                "chunk_id": self.chunks[idx]['id'],
                "text": self.chunks[idx]['text'],
                "metadata": self.chunks[idx]['metadata']
            })
        return results

# ==========================================
#  הרצה לדוגמה
# ==========================================
if __name__ == "__main__":
    searcher = LocalVectorSearch("chunks.json")
    
    while True:
        query = input("\nהכנס שאלה לחיפוש (או 'q' ליציאה): ")
        if query.lower() == 'q':
            break
            
        results = searcher.search(query)
        
        print(f"\n--- תוצאות עבור: '{query}' ---")
        for i, res in enumerate(results):
            print(f"\n[{i+1}] ציון דמיון: {res['score']}")
            print(f"מקור: {res['metadata']['source']} (עמוד {res['metadata']['pages']})")
            print(f"טקסט: {res['text'][:200]}...")