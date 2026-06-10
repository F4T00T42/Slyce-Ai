"""Qdrant vector store wrapper for the nutrition knowledge base.

A SEPARATE datastore from the main app DB (which stays read-only). The Qdrant
client is imported lazily.
"""
import uuid

from ai.config import settings


class VectorStore:
    # Manages the KB collection (create/upsert/search) in Qdrant.
    def __init__(self, collection: str | None = None):
        # Input: collection (override the configured collection name).
        self.collection = collection or settings.kb_collection
        self._client = None

    def _ensure_client(self):
        # Build the Qdrant client on first use (url + optional api key from env).
        if self._client is None:
            from qdrant_client import QdrantClient  # lazy

            self._client = QdrantClient(
                url=settings.qdrant_url,
                api_key=settings.qdrant_api_key or None,
            )
        return self._client

    def ensure_collection(self, dim: int) -> None:
        # Input: dim (vector size). Creates the cosine collection if missing.
        from qdrant_client.models import Distance, VectorParams

        client = self._ensure_client()
        existing = [c.name for c in client.get_collections().collections]
        if self.collection not in existing:
            client.create_collection(
                collection_name=self.collection,
                vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
            )

    def upsert(self, vectors: list[list[float]], payloads: list[dict]) -> int:
        # Inputs: vectors (embeddings), payloads (per-vector metadata).
        # Each point gets a fresh uuid; returns the number upserted.
        from qdrant_client.models import PointStruct

        client = self._ensure_client()
        points = [
            PointStruct(id=str(uuid.uuid4()), vector=v, payload=p)
            for v, p in zip(vectors, payloads)
        ]
        client.upsert(collection_name=self.collection, points=points)
        return len(points)

    def search(self, vector: list[float], top_k: int = 5) -> list:
        # Inputs: vector (query embedding), top_k (max hits).
        # Returns [{score, **payload}] for the nearest points.
        client = self._ensure_client()
        hits = client.search(
            collection_name=self.collection, query_vector=vector, limit=top_k
        )
        out = []
        for h in hits:
            payload = h.payload or {}
            out.append({"score": float(h.score), **payload})
        return out
