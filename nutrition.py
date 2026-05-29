from dataclasses import dataclass
from models import UserProfile

# Physical activity level multipliers (PAL) for TDEE.
ACTIVITY_MULTIPLIERS = {
    "sedentary":   1.2,
    "light":       1.375,
    "moderate":    1.55,
    "active":      1.725,
    "very_active": 1.9,
}

# Fractional calorie adjustment applied on top of TDEE per goal.
GOAL_CALORIE_ADJUSTMENT = {
    "fat_loss":    -0.20,
    "muscle_gain": +0.10,
    "maintenance":  0.00,
}

# Daily protein targets in grams per kg of body weight.
PROTEIN_TARGETS_G_PER_KG = {
    "fat_loss":    1.8,
    "muscle_gain": 2.2,
    "maintenance": 1.4,
}

# Hard macro ratio limits used by both the filter and the scorer.
DIET_MACRO_RANGES = {
    "keto": {
        "carb_max_pct":    0.05,
        "fat_min_pct":     0.65,
        "protein_min_pct": 0.20,
    },
    "high_protein": {
        "carb_max_pct":    0.40,
        "fat_max_pct":     0.35,
        "protein_min_pct": 0.30,
    },
    "balanced": {
        "carb_range":    (0.45, 0.65),
        "fat_range":     (0.20, 0.35),
        "protein_range": (0.10, 0.35),
    },
}

# Caloric density used to convert macro grams to calories.
CALS_PER_G = {"carb": 4.0, "protein": 4.0, "fat": 9.0}


@dataclass
class NutritionTargets:
    daily_calories: float
    meal_calories: float
    daily_protein_g: float
    meal_protein_g: float
    bmr: float
    tdee: float
    meals_per_day: int = 3


def compute_bmr(profile: UserProfile) -> float:
    # Mifflin-St Jeor equation: most accurate for general populations.
    base = 10 * profile.weight + 6.25 * profile.height - 5 * profile.age
    return base + 5 if profile.gender == "male" else base - 161


def compute_targets(profile: UserProfile, meals_per_day: int = 3) -> NutritionTargets:
    # Chains BMR → TDEE → goal adjustment → per-meal split.
    bmr = compute_bmr(profile)

    multiplier     = ACTIVITY_MULTIPLIERS.get(profile.activity_level, 1.55)
    tdee           = bmr * multiplier
    adjustment     = GOAL_CALORIE_ADJUSTMENT.get(profile.goal, 0.0)
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
