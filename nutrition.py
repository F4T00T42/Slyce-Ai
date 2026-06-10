"""Nutrition math: BMR -> TDEE -> goal adjustment -> per-meal targets."""
from dataclasses import dataclass

from models import UserProfile

# Activity level -> TDEE multiplier (PAL).
ACTIVITY_MULTIPLIERS = {
    "sedentary": 1.2,
    "lightly_active": 1.375,
    "moderately_active": 1.55,
    "very_active": 1.725,
    "super_active": 1.9,
}

# Goal -> fractional calorie adjustment on top of TDEE.
GOAL_CALORIE_ADJUSTMENT = {
    "fat_loss": -0.20,
    "muscle_gain": +0.10,
    "maintenance": 0.00,
}

# Goal -> daily protein target (grams per kg body weight).
PROTEIN_TARGETS_G_PER_KG = {
    "fat_loss": 1.8,
    "muscle_gain": 2.2,
    "maintenance": 1.4,
}

# Diet -> macro ratio limits, used by both the filter and the scorer.
DIET_MACRO_RANGES = {
    "keto": {"carb_max_pct": 0.05, "fat_min_pct": 0.65, "protein_min_pct": 0.20},
    "low_carb": {"carb_max_pct": 0.26, "protein_min_pct": 0.20},
    "high_protein": {"carb_max_pct": 0.40, "fat_max_pct": 0.35, "protein_min_pct": 0.30},
    "mediterranean": {
        "carb_range": (0.35, 0.60),
        "fat_range": (0.20, 0.45),
        "protein_range": (0.10, 0.35),
    },
    "balanced": {
        "carb_range": (0.45, 0.65),
        "fat_range": (0.20, 0.35),
        "protein_range": (0.10, 0.35),
    },
}

# Calories per gram per macronutrient.
CALS_PER_G = {"carb": 4.0, "protein": 4.0, "fat": 9.0}


def macro_calorie_fractions(meal) -> dict:
    # Input: meal (Meal). Returns {carb, protein, fat} as fractions of total
    # calories (0.0 each when calories are missing). Single source of truth for
    # the macro math shared by the diet filters and the scorer.
    if meal.calories <= 0:
        return {"carb": 0.0, "protein": 0.0, "fat": 0.0}
    return {
        "carb": (meal.total_carbohydrate * CALS_PER_G["carb"]) / meal.calories,
        "protein": (meal.protein * CALS_PER_G["protein"]) / meal.calories,
        "fat": (meal.total_fat * CALS_PER_G["fat"]) / meal.calories,
    }


@dataclass
class NutritionTargets:
    # Computed daily + per-meal calorie/protein targets, plus BMR/TDEE.
    daily_calories: float
    meal_calories: float
    daily_protein_g: float
    meal_protein_g: float
    bmr: float
    tdee: float
    meals_per_day: int = 3


def compute_bmr(profile: UserProfile) -> float:
    # Input: profile (UserProfile). Returns BMR via Mifflin-St Jeor.
    base = 10 * profile.weight + 6.25 * profile.height - 5 * profile.age
    return base + 5 if profile.gender == "male" else base - 161


def compute_targets(profile: UserProfile, meals_per_day: int = 3) -> NutritionTargets:
    # Inputs: profile (UserProfile), meals_per_day (split target across meals).
    bmr = compute_bmr(profile)
    multiplier = ACTIVITY_MULTIPLIERS.get(profile.activity_level, 1.55)
    tdee = bmr * multiplier
    adjustment = GOAL_CALORIE_ADJUSTMENT.get(profile.goal, 0.0)
    daily_calories = tdee * (1 + adjustment)
    daily_protein_g = PROTEIN_TARGETS_G_PER_KG[profile.goal] * profile.weight

    return NutritionTargets(
        bmr=round(bmr, 1),
        tdee=round(tdee, 1),
        daily_calories=round(daily_calories, 1),
        meal_calories=round(daily_calories / meals_per_day, 1),
        daily_protein_g=round(daily_protein_g, 1),
        meal_protein_g=round(daily_protein_g / meals_per_day, 1),
        meals_per_day=meals_per_day,
    )
