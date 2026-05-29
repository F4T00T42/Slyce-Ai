from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from db.connection import get_engine
from models import UserProfile
from recommender import MealRecommender

recommender: MealRecommender | None = None

# Builds the recommender once at startup and holds it in memory for all requests.
@asynccontextmanager
async def lifespan(app: FastAPI):
    global recommender
    engine = get_engine()
    recommender = MealRecommender(engine)
    print("✓ Connected to database and meals loaded")
    yield

app = FastAPI(
    title="Fitness Meal Recommender",
    description="Send a customer profile, get back ranked meal IDs.",
    version="1.0.0",
    lifespan=lifespan,
)

# Opens the API to all origins so external clients can call it directly.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class RecommendResponse(BaseModel):
    # Ranked meal IDs, best match first.
    meal_ids: list[int]


@app.post("/recommend", response_model=RecommendResponse)
def recommend(
    profile: UserProfile,
    top_n: int = Query(default=10, ge=1, le=50, description="Number of meals to return"),
):
    """
    Accepts a user profile and returns the top N ranked meal IDs.

    Example request body:
    ```json
    {
        "weight": 85,
        "height": 182,
        "age": 28,
        "gender": "male",
        "activity_level": "active",
        "goal": "muscle_gain",
        "diet": "high_protein",
        "allergies": ["nuts", "dairy"]
    }
    ```
    """
    if recommender is None:
        raise HTTPException(status_code=503, detail="Recommender not initialised")

    result = recommender.recommend(profile, top_n=top_n)

    # Strips all meal data from the response — returns IDs only.
    return RecommendResponse(
        meal_ids=[m.meal_id for m in result.ranked_meals]
    )


@app.get("/health")
def health():
    # Liveness probe — returns 200 if the server is up.
    return {"status": "ok"}
