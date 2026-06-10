"""FastAPI entrypoint: serves /health, /recommend, and the /chat assistant.

On startup it builds the read-only DB engine + recommender + customer repo,
wires the chat layer, and (when RUN_INGEST=true) kicks off the knowledge-base
ingest in a background thread. The ingest runs off the main thread so the app
can answer /health immediately (important for App Service / Container startup
probes); it is idempotent and skips if the Qdrant collection is already
populated.
"""
import os
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from recommender import MealRecommender
from db.connection import build_engine
from db.customer_repository import CustomerRepository
from ai.api.chat_router import router as chat_router, init_chat
from ai.api.schemas import RecommendRequest
from ai.profile_context import resolve_profile

# Singletons built once at startup (read-only DB engine + recommender + repo).
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
    # Build DB engine + recommender + customer repo, wire the chat layer,
    # optionally ingest the KB, and dispose the engine on shutdown.
    engine = build_engine()
    recommender = MealRecommender(engine)
    _resources["engine"] = engine
    _resources["recommender"] = recommender
    _resources["customer_repo"] = CustomerRepository(engine)
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
def recommend(req: RecommendRequest):
    # Inputs: req (RecommendRequest: user_id?, profile?, top_n=10).
    # Loads the stored profile by user_id (preferred); an explicit profile, if
    # given, overrides stored fields. Returns 422 if required fields are missing.
    explicit = req.profile.model_dump(exclude_none=True) if req.profile else None
    profile, missing = resolve_profile(explicit, req.user_id, _resources.get("customer_repo"))
    if profile is None:
        raise HTTPException(
            status_code=422,
            detail={
                "status": "need_profile",
                "missing_fields": missing,
                "message": "Provide a user_id with a stored profile, or pass the "
                "missing fields explicitly: " + ", ".join(missing) + ".",
            },
        )
    result = _resources["recommender"].recommend(profile, top_n=req.top_n)
    return result.to_dict()
