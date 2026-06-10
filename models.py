"""Core data models shared across the recommender and the AI layer.

`UserProfile` is intentionally lenient: the chatbot may receive a partial
profile (e.g. a user describing a friend), so `goal` and `diet` have safe
defaults. The application DB does not store `goal`, so it always originates
from caller input.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, Field

Gender = Literal["male", "female"]
ActivityLevel = Literal["sedentary", "light", "moderate", "active", "very_active"]
Goal = Literal["fat_loss", "muscle_gain", "maintenance"]
Diet = Literal["keto", "high_protein", "balanced"]


class UserProfile(BaseModel):
    """Validated nutrition profile used by the recommender and planner."""

    weight: float = Field(..., gt=0, description="Body weight in kg")
    height: float = Field(..., gt=0, description="Height in cm")
    age: int = Field(..., gt=0, lt=120)
    gender: Gender = "male"
    activity_level: ActivityLevel = "moderate"
    goal: Goal = "maintenance"
    diet: Diet = "balanced"
    allergies: list[str] = Field(
        default_factory=list, description="Allergen names, e.g. ['Milk','Peanuts']"
    )


@dataclass
class Meal:
    """A single orderable meal *size* (menus.MealSizes), enriched with the
    parent meal's descriptive fields and detected allergens.
    """

    meal_id: str  # menus.MealSizes.Id (the size-level id the app orders by)
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
    # --- extended fields mapped from the real schema ---
    menu_meal_id: str = ""  # menus.MenuMeals.Id (the conceptual meal)
    size_name: str = ""  # e.g. "small" / "large"
    description: str = ""
    price: float = 0.0
    currency: str = ""
    restaurant_id: str = ""
    available: bool = True
    ingredients: list[str] = field(default_factory=list)


@dataclass
class ScoredMeal:
    meal_id: str
    name: str
    score: float
    calorie_score: float
    protein_score: float
    diet_score: float
    breakdown: dict
