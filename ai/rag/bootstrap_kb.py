"""Idempotently ensure the nutrition knowledge base is ingested into Qdrant.

Safe to run on every startup: it ingests only when the target collection is
missing or empty, avoiding duplicate chunks. Set FORCE_INGEST=true to override.

Usage:
    python -m ai.rag.bootstrap_kb                    # auto-skip if already populated
    FORCE_INGEST=true python -m ai.rag.bootstrap_kb  # ingest regardless
"""
import os

from ai.rag.vector_store import VectorStore
from ai.rag.ingest import ingest

def _collection_count(store: VectorStore):
    # Input: store (VectorStore). Returns point count, or None if unreachable.
    try:
        client = store._ensure_client()
        return client.count(collection_name=store.collection, exact=True).count
    except Exception:
        return None

def main() -> None:
    # Ingest knowledge base docs unless the collection is already populated.
    # Env: KB_DOCS_DIR (docs path), FORCE_INGEST (ingest even if populated).
    docs_dir = os.getenv("KB_DOCS_DIR", "knowledge_base/docs")
    force = os.getenv("FORCE_INGEST", "false").strip().lower() == "true"
    store = VectorStore()

    count = _collection_count(store)
    if not force and count and count > 0:
        print(
            f"[bootstrap_kb] Collection '{store.collection}' already has "
            f"{count} points; skipping ingest."
        )
        return

    print(f"[bootstrap_kb] Ingesting knowledge base from '{docs_dir}'...")
    # recreate=force so a forced run rebuilds cleanly instead of layering points.
    ingest(docs_dir, recreate=force)

if __name__ == "__main__":
    main()
