"""FastAPI entrypoint: serves /health, /recommend, and the /chat assistant."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from models import UserProfile
from recommender import MealRecommender
from db.connection import build_engine
from ai.api.chat_router import router as chat_router, init_chat

# Singletons built once at startup (read-only DB engine + recommender).
_resources: dict = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Build DB engine + recommender, wire the chat layer, dispose on shutdown.
    engine = build_engine()
    recommender = MealRecommender(engine)
    _resources["engine"] = engine
    _resources["recommender"] = recommender
    init_chat(engine, recommender)
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
