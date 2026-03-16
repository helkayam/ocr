import json
import os
from typing import List, Dict
import torch
from sentence_transformers import SentenceTransformer

CACHE_PATH = "embeddings_cache.pt"

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

        if not self.chunks:
            raise ValueError(f"No chunks found in {chunks_path}. Run chunker.py first.")

        self.chunk_embeddings = self._load_or_compute_embeddings(chunks_path)
        print("Done!")

    def _load_or_compute_embeddings(self, chunks_path: str) -> torch.Tensor:
        """Load embeddings from cache if valid, otherwise recompute and save."""
        if os.path.exists(CACHE_PATH):
            cache_mtime = os.path.getmtime(CACHE_PATH)
            chunks_mtime = os.path.getmtime(chunks_path)
            if cache_mtime > chunks_mtime:
                print(f"Loading embeddings from cache ({CACHE_PATH})...")
                return torch.load(CACHE_PATH, weights_only=True)
            else:
                print("Cache is stale (chunks.json is newer). Recomputing embeddings...")
        else:
            print(f"No cache found. Computing embeddings for {len(self.chunks)} chunks. Please wait...")

        texts_to_embed = [chunk['text_with_context'] for chunk in self.chunks]
        embeddings = self.model.encode(texts_to_embed, convert_to_tensor=True)
        torch.save(embeddings, CACHE_PATH)
        print(f"Embeddings saved to cache ({CACHE_PATH}).")
        return embeddings

    def search(self, query: str, top_k: int = 3) -> List[Dict]:
        """חיפוש סמנטי לפי דמיון קוסינוס"""
        query_embedding = self.model.encode([query], convert_to_tensor=True)
        
        # חישוב דמיון קוסינוס (Cosine Similarity)
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