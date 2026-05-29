from dataclasses import dataclass, field
from typing import Literal
from pydantic import BaseModel, Field


# Validated by FastAPI on every incoming request.
class UserProfile(BaseModel):
    weight:         float = Field(..., gt=0, description="Body weight in kg")
    height:         float = Field(..., gt=0, description="Height in cm")
    age:            int   = Field(..., gt=0, lt=120)
    gender:         Literal["male", "female"] = "male"
    activity_level: Literal["sedentary", "light", "moderate", "active", "very_active"] = "moderate"
    goal:           Literal["fat_loss", "muscle_gain", "maintenance"]
    diet:           Literal["keto", "high_protein", "balanced"]
    allergies:      list[str] = Field(default_factory=list, description="e.g. ['nuts','dairy','gluten']")


# Internal meal representation loaded from the database.
@dataclass
class Meal:
    meal_id: int
    name: str
    calories: float
    sodium_mg: float = 0.0
    sugar_grams: float = 0.0
    calcium_mg: float = 0.0
    cholesterol: float = 0.0
    dietary_fiber: float = 0.0
    iron_mg: float = 0.0
    potassium_mg: float = 0.0
    protein: float = 0.0
    saturated_fat: float = 0.0
    total_carbohydrate: float = 0.0
    total_fat: float = 0.0
    trans_fat: float = 0.0
    vitamin_a_mcg: float = 0.0
    vitamin_c_mg: float = 0.0
    vitamin_d: float = 0.0
    tags: list[str] = field(default_factory=list)


# Meal with its computed score and per-component breakdown.
@dataclass
class ScoredMeal:
    meal_id: int
    name: str
    score: float
    calorie_score: float
    protein_score: float
    diet_score: float
    breakdown: dict
