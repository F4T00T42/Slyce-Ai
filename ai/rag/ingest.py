"""Ingest the knowledge base into Qdrant.

Reads `.md` / `.txt` files from a directory (default: knowledge_base/docs),
splits them into overlapping chunks, embeds with BGE, and upserts to Qdrant.

Each file may start with a YAML-ish front matter:
    ---
    title: Dietary Fiber
    source: https://ods.od.nih.gov/factsheets/Fiber
    ---

Usage:
    python -m ai.rag.ingest --docs knowledge_base/docs
"""
import argparse
import os
import re

from ai.rag.embedder import Embedder
from ai.rag.vector_store import VectorStore


def _parse_front_matter(text: str, filename: str) -> tuple[dict, str]:
    meta = {"title": os.path.splitext(os.path.basename(filename))[0], "source": ""}
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    if m:
        for line in m.group(1).splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip()] = v.strip()
        text = text[m.end():]
    return meta, text


def chunk_text(text: str, size: int = 800, overlap: int = 150) -> list[str]:
    words = text.split()
    chunks = []
    step = max(size - overlap, 1)
    for i in range(0, len(words), step):
        chunk = " ".join(words[i : i + size])
        if chunk.strip():
            chunks.append(chunk)
        if i + size >= len(words):
            break
    return chunks


def ingest(docs_dir: str) -> int:
    embedder = Embedder()
    store = VectorStore()
    store.ensure_collection(embedder.dim)

    texts, payloads = [], []
    for root, _, files in os.walk(docs_dir):
        for fn in files:
            if not fn.lower().endswith((".md", ".txt")):
                continue
            path = os.path.join(root, fn)
            with open(path, encoding="utf-8") as fh:
                raw = fh.read()
            meta, body = _parse_front_matter(raw, path)
            for chunk in chunk_text(body):
                texts.append(chunk)
                payloads.append(
                    {"text": chunk, "title": meta.get("title", ""), "source": meta.get("source", "")}
                )

    if not texts:
        print(f"No documents found in {docs_dir}")
        return 0
    vectors = embedder.embed_documents(texts)
    count = store.upsert(vectors, payloads)
    print(f"Ingested {count} chunks from {docs_dir} into '{store.collection}'.")
    return count


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--docs", default="knowledge_base/docs")
    args = parser.parse_args()
    ingest(args.docs)
