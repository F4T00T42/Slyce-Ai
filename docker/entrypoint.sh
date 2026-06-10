#!/usr/bin/env sh
set -e

echo "[entrypoint] Waiting for dependencies to become reachable..."
python - <<'PY'
import os, socket, time, urllib.parse

def wait(host, port, name, timeout=120):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((host, int(port)), timeout=3):
                print(f"[entrypoint] {name} is up at {host}:{port}")
                return
        except OSError:
            time.sleep(2)
    print(f"[entrypoint] WARNING: timed out waiting for {name} at {host}:{port}; continuing anyway.")

q = urllib.parse.urlparse(os.getenv("QDRANT_URL", "http://qdrant:6333"))
wait(q.hostname or "qdrant", q.port or 6333, "Qdrant")

surl = os.getenv("SESSION_DB_URL", "")
if surl.startswith("postgresql"):
    p = urllib.parse.urlparse(surl)
    if p.hostname:
        wait(p.hostname, p.port or 5432, "Sessions DB")
PY

if [ "${RUN_INGEST:-true}" = "true" ]; then
  echo "[entrypoint] Bootstrapping knowledge base (idempotent)..."
  python -m ai.rag.bootstrap_kb || echo "[entrypoint] KB bootstrap skipped/failed; continuing."
fi

echo "[entrypoint] Starting API on :8000"
exec uvicorn main:app --host 0.0.0.0 --port 8000 --workers "${WEB_CONCURRENCY:-1}"
