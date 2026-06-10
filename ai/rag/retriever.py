"""Retrieval: embed query -> vector search -> score-filtered chunks."""
from ai.config import settings
from ai.rag.embedder import Embedder
from ai.rag.vector_store import VectorStore


class Retriever:
    # Embeds a query and returns the top knowledge-base chunks above min score.
    def __init__(self, embedder: Embedder | None = None, store: VectorStore | None = None):
        # Inputs: embedder (Embedder or default), store (VectorStore or default).
        self.embedder = embedder or Embedder()
        self.store = store or VectorStore()

    def search(self, query: str, top_k: int | None = None) -> list:
        # Inputs: query (text), top_k (max hits; defaults to settings.rag_top_k).
        # Returns chunks {text, title, source, score} with score >= rag_min_score.
        top_k = top_k or settings.rag_top_k
        vector = self.embedder.embed_query(query)
        hits = self.store.search(vector, top_k=top_k)
        results = []
        for h in hits:
            if h.get("score", 0.0) < settings.rag_min_score:
                continue
            results.append(
                {
                    "text": h.get("text", ""),
                    "title": h.get("title", ""),
                    "source": h.get("source", ""),
                    "score": round(h.get("score", 0.0), 4),
                }
            )
        return results
