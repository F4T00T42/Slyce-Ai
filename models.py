"""Shared data models: validated UserProfile + Meal/ScoredMeal dataclasses.

UserProfile is lenient (partial profiles allowed); goal/diet have safe defaults.
The app DB has no fitness goal, so goal always comes from caller input.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, Field, field_validator

Gender = Literal["male", "female"]
ActivityLevel = Literal[
    "sedentary", "lightly_active", "moderately_active", "very_active", "super_active"
]
Goal = Literal["fat_loss", "muscle_gain", "maintenance"]
Diet = Literal["keto", "low_carb", "high_protein", "mediterranean", "balanced"]

# Activity label (UI text / snake_case / DB ActivityRate) -> canonical level.
# Keys are alphanumeric-only, lowercased.
_ACTIVITY_ALIASES = {
    "sedentary": "sedentary",
    "light": "lightly_active",
    "lightlyactive": "lightly_active",
    "moderate": "moderately_active",
    "moderatelyactive": "moderately_active",
    "active": "very_active",
    "veryactive": "very_active",
    "super": "super_active",
    "superactive": "super_active",
    "extraactive": "super_active",
    "extremelyactive": "super_active",
}


def normalize_activity_level(value):
    # Input: value (any activity label). Returns a canonical ActivityLevel.
    if not value:
        return "moderately_active"
    key = "".join(c for c in str(value).lower() if c.isalnum())
    return _ACTIVITY_ALIASES.get(key, "moderately_active")


# Diet/plan label -> canonical Diet. Ingredient-based plans (vegetarian/vegan/
# pescatarian/gluten free/dairy free) map to "balanced" (not macro-enforceable).
_DIET_ALIASES = {
    "keto": "keto",
    "ketogenic": "keto",
    "lowcarb": "low_carb",
    "highprotein": "high_protein",
    "mediterranean": "mediterranean",
    "balanced": "balanced",
    "vegetarian": "balanced",
    "vegan": "balanced",
    "pescatarian": "balanced",
    "glutenfree": "balanced",
    "dairyfree": "balanced",
}


def normalize_diet(value):
    # Input: value (any diet/plan label). Returns a canonical Diet.
    if not value:
        return "balanced"
    key = "".join(c for c in str(value).lower() if c.isalnum())
    return _DIET_ALIASES.get(key, "balanced")


class UserProfile(BaseModel):
    # Fields: weight(kg), height(cm), age, gender, activity_level, goal, diet,
    # allergies. activity_level and diet are normalized before validation.
    weight: float = Field(..., gt=0, description="Body weight in kg")
    height: float = Field(..., gt=0, description="Height in cm")
    age: int = Field(..., gt=0, lt=120)
    gender: Gender = "male"
    activity_level: ActivityLevel = "moderately_active"
    goal: Goal = "maintenance"
    diet: Diet = "balanced"
    allergies: list[str] = Field(
        default_factory=list, description="Allergen names, e.g. ['Milk','Peanuts']"
    )

    @field_validator("activity_level", mode="before")
    @classmethod
    def _normalize_activity(cls, v):
        # v: raw activity input -> canonical ActivityLevel.
        return normalize_activity_level(v)

    @field_validator("diet", mode="before")
    @classmethod
    def _normalize_diet(cls, v):
        # v: raw diet input -> canonical Diet.
        return normalize_diet(v)


@dataclass
class Meal:
    # One orderable meal size (menus.MealSizes) + parent meal info + allergens.
    meal_id: str  # menus.MealSizes.Id (size-level id the app orders by)
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
    # Extended fields mapped from the real schema:
    menu_meal_id: str = ""  # menus.MenuMeals.Id (conceptual meal)
    size_name: str = ""  # e.g. "small" / "large"
    description: str = ""
    price: float = 0.0
    currency: str = ""
    restaurant_id: str = ""
    available: bool = True
    ingredients: list[str] = field(default_factory=list)


@dataclass
class ScoredMeal:
    # A scored meal: meal_id, name, total score, per-component scores, breakdown.
    meal_id: str
    name: str
    score: float
    calorie_score: float
    protein_score: float
    diet_score: float
    breakdown: dict
