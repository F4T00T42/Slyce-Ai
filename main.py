"""FastAPI entrypoint: serves /health, /recommend, and the /chat assistant.

On startup it builds the read-only DB engine + recommender, wires the chat
layer, and (when RUN_INGEST=true) kicks off the knowledge-base ingest in a
background thread. The ingest runs off the main thread so the app can answer
/health immediately (important for App Service / Container startup probes); it
is idempotent and skips if the Qdrant collection is already populated.
"""
import os
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from models import UserProfile
from recommender import MealRecommender
from db.connection import build_engine
from ai.api.chat_router import router as chat_router, init_chat

# Singletons built once at startup (read-only DB engine + recommender).
_resources: dict = {}


def _maybe_bootstrap_kb() -> None:
    # Ingest the knowledge base in the background when RUN_INGEST=true.
    # Runs regardless of how the app is launched (works without the Docker
    # entrypoint), and is idempotent so repeated boots are safe.
    if os.getenv("RUN_INGEST", "false").strip().lower() != "true":
        return

    def _worker():
        try:
            from ai.rag.bootstrap_kb import main as bootstrap_main

            print("[startup] RUN_INGEST=true — bootstrapping knowledge base...")
            bootstrap_main()
            print("[startup] Knowledge base bootstrap complete.")
        except Exception as exc:  # never block the app on KB issues
            print(f"[startup] KB bootstrap skipped/failed: {exc}")

    threading.Thread(target=_worker, name="kb-bootstrap", daemon=True).start()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Build DB engine + recommender, wire the chat layer, optionally ingest the
    # KB, and dispose the engine on shutdown.
    engine = build_engine()
    recommender = MealRecommender(engine)
    _resources["engine"] = engine
    _resources["recommender"] = recommender
    init_chat(engine, recommender)
    _maybe_bootstrap_kb()
    yield
    engine.dispose()


app = FastAPI(title="Slyce AI", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router)


@app.get("/health")
def health():
    # Liveness probe.
    return {"status": "ok"}


@app.post("/recommend")
def recommend(profile: UserProfile, top_n: int = 10):
    # Inputs: profile (UserProfile), top_n (max meals to return, default 10).
    result = _resources["recommender"].recommend(profile, top_n=top_n)
    return result.to_dict()
