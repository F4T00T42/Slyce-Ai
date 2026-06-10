"""Idempotently ensure the nutrition knowledge base is ingested into Qdrant.

Safe to run on every startup (e.g. from the Docker entrypoint): it checks
whether the target collection already contains points and only ingests when it
is missing or empty. This avoids duplicating chunks, since `VectorStore.upsert`
assigns a fresh id to every point on each run.

Usage:
    python -m ai.rag.bootstrap_kb            # auto-skip if already populated
    FORCE_INGEST=true python -m ai.rag.bootstrap_kb   # ingest regardless
"""
import os

from ai.rag.vector_store import VectorStore
from ai.rag.ingest import ingest


def _collection_count(store: VectorStore):
    """Return the number of points in the collection, or None if it doesn't
    exist yet / can't be reached."""
    try:
        client = store._ensure_client()
        return client.count(collection_name=store.collection, exact=True).count
    except Exception:
        return None


def main() -> None:
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
    ingest(docs_dir)


if __name__ == "__main__":
    main()
