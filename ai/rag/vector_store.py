"""Qdrant vector store wrapper for the nutrition knowledge base.

A SEPARATE datastore from the main app DB (which stays read-only). The Qdrant
client is imported lazily.
"""
import uuid

from ai.config import settings

# Stable namespace so the same chunk always maps to the same point id (makes
# re-ingest idempotent instead of inserting duplicates with random uuids).
_POINT_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "slyce-nutrition-kb")

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

    def ensure_collection(self, dim: int, recreate: bool = False) -> None:
        # Inputs: dim (vector size), recreate (drop + recreate if it exists).
        # Creates the cosine collection if missing (or recreates it on request).
        from qdrant_client.models import Distance, VectorParams

        client = self._ensure_client()
        existing = [c.name for c in client.get_collections().collections]
        if recreate and self.collection in existing:
            client.delete_collection(collection_name=self.collection)
            existing = [c.name for c in client.get_collections().collections]
        if self.collection not in existing:
            client.create_collection(
                collection_name=self.collection,
                vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
            )

    def upsert(self, vectors: list[list[float]], payloads: list[dict]) -> int:
        # Inputs: vectors (embeddings), payloads (per-vector metadata).
        # Each point id is derived deterministically from its content, so
        # re-ingesting the same chunk updates it in place instead of duplicating.
        # Returns the number upserted.
        from qdrant_client.models import PointStruct

        client = self._ensure_client()
        points = []
        for v, p in zip(vectors, payloads):
            key = "|".join(
                [
                    self.collection,
                    str(p.get("source", "")),
                    str(p.get("title", "")),
                    str(p.get("text", "")),
                ]
            )
            pid = str(uuid.uuid5(_POINT_NAMESPACE, key))
            points.append(PointStruct(id=pid, vector=v, payload=p))
        client.upsert(collection_name=self.collection, points=points)
        return len(points)

    def search(self, vector: list[float], top_k: int = 5) -> list:
        # Inputs: vector (query embedding), top_k (max hits).
        # Returns [{score, **payload}] for the nearest points.
        client = self._ensure_client()
        response = client.query_points(
            collection_name=self.collection, query=vector, limit=top_k
        )
        out = []
        for h in response.points:
            payload = h.payload or {}
            out.append({"score": float(h.score), **payload})
        return out
