"""Weighted meal scoring + ranking (calorie fit, protein fit, diet fit)."""
import math

from models import Meal, UserProfile, ScoredMeal
from nutrition import NutritionTargets, DIET_MACRO_RANGES, macro_calorie_fractions

# Goal -> relative weight of each score component.
SCORE_WEIGHTS = {
    "fat_loss": {"calorie": 0.50, "protein": 0.35, "diet": 0.15},
    "muscle_gain": {"calorie": 0.35, "protein": 0.50, "diet": 0.15},
    "maintenance": {"calorie": 0.40, "protein": 0.25, "diet": 0.35},
}

# Width of the calorie Gaussian as a fraction of the target.
CALORIE_SIGMA_FRACTION = 0.20

def _range_score(value: float, lo: float, hi: float) -> float:
    # Inputs: value (macro fraction), lo/hi (acceptable range bounds).
    # Returns 1.0 at the midpoint, decaying linearly to 0 at the edges.
    mid = (lo + hi) / 2
    half = (hi - lo) / 2
    return max(0.0, 1.0 - abs(value - mid) / max(half, 0.001))

def _calorie_score(meal_cals: float, target_cals: float) -> float:
    # Inputs: meal_cals (meal calories), target_cals (per-meal target).
    sigma = target_cals * CALORIE_SIGMA_FRACTION
    if sigma <= 0:
        return 0.0
    return math.exp(-0.5 * ((meal_cals - target_cals) / sigma) ** 2)

def _protein_score(meal_protein_g: float, target_protein_g: float, goal: str) -> float:
    # Inputs: meal_protein_g, target_protein_g, goal (shapes the curve).
    if target_protein_g <= 0:
        return 0.0
    ratio = meal_protein_g / target_protein_g
    if goal == "muscle_gain":
        return min(ratio, 1.0)
    if goal == "fat_loss":
        if ratio >= 1.0:
            return 1.0
        if ratio <= 0.0:
            return 0.0
        return ratio
    return math.exp(-2.0 * (ratio - 1.0) ** 2)

def _diet_compatibility_score(meal: Meal, diet: str) -> float:
    # Inputs: meal (Meal), diet (canonical Diet). Returns 0..1 macro fit (0.5 if N/A).
    rules = DIET_MACRO_RANGES.get(diet, {})
    if not rules or meal.calories <= 0:
        return 0.5
    pct = macro_calorie_fractions(meal)
    carb_pct, protein_pct, fat_pct = pct["carb"], pct["protein"], pct["fat"]
    sub_scores = []
    if diet == "keto":
        carb_score = max(0.0, 1.0 - (carb_pct / rules["carb_max_pct"]))
        fat_score = min(fat_pct / max(rules["fat_min_pct"], 0.01), 1.0)
        sub_scores = [carb_score, fat_score]
    elif diet == "low_carb":
        sub_scores = [max(0.0, 1.0 - (carb_pct / rules["carb_max_pct"]))]
    elif diet == "high_protein":
        prot_score = min(protein_pct / rules["protein_min_pct"], 1.0)
        sub_scores = [prot_score]
    elif diet in ("mediterranean", "balanced"):
        sub_scores = [
            _range_score(carb_pct, *rules["carb_range"]),
            _range_score(protein_pct, *rules["protein_range"]),
            _range_score(fat_pct, *rules["fat_range"]),
        ]
    return sum(sub_scores) / len(sub_scores) if sub_scores else 0.5

def score_meal(meal: Meal, profile: UserProfile, targets: NutritionTargets) -> ScoredMeal:
    # Inputs: meal (Meal), profile (UserProfile), targets (NutritionTargets).
    weights = SCORE_WEIGHTS.get(profile.goal, SCORE_WEIGHTS["maintenance"])
    cal_score = _calorie_score(meal.calories, targets.meal_calories)
    prot_score = _protein_score(meal.protein, targets.meal_protein_g, profile.goal)
    diet_score = _diet_compatibility_score(meal, profile.diet)
    total = (
        weights["calorie"] * cal_score
        + weights["protein"] * prot_score
        + weights["diet"] * diet_score
    )
    return ScoredMeal(
        meal_id=meal.meal_id,
        name=meal.name,
        score=round(total, 4),
        calorie_score=round(cal_score, 4),
        protein_score=round(prot_score, 4),
        diet_score=round(diet_score, 4),
        breakdown={
            "meal_calories": meal.calories,
            "target_calories": targets.meal_calories,
            "meal_protein_g": meal.protein,
            "target_protein_g": targets.meal_protein_g,
            "weights": weights,
        },
    )

def rank_meals(meals, profile, targets, top_n: int = 10):
    # Inputs: meals (list[Meal]), profile (UserProfile), targets (NutritionTargets),
    # top_n (how many top-scored meals to return). Returns sorted ScoredMeals.
    scored = [score_meal(m, profile, targets) for m in meals]
    scored.sort(key=lambda s: s.score, reverse=True)
    return scored[:top_n]
