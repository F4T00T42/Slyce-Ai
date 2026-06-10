"""Hard pass/fail gates: allergen check + per-diet macro gates.

Allergen detection reads meal.tags, which the repository layer populates with
allergen names derived from each meal's ingredients.
"""
from models import Meal, UserProfile
from nutrition import DIET_MACRO_RANGES, CALS_PER_G


def passes_allergen_check(meal: Meal, allergies: list[str]) -> bool:
    # Inputs: meal (Meal), allergies (user allergen names). False if any overlap.
    if not allergies:
        return True
    lowered_tags = {t.lower() for t in meal.tags}
    return not any(a.lower() in lowered_tags for a in allergies)


def _macro_pcts(meal: Meal) -> dict[str, float]:
    # Input: meal (Meal). Returns {carb, protein, fat} as fractions of calories.
    if meal.calories <= 0:
        return {"carb": 0.0, "protein": 0.0, "fat": 0.0}
    carb_cals = meal.total_carbohydrate * CALS_PER_G["carb"]
    protein_cals = meal.protein * CALS_PER_G["protein"]
    fat_cals = meal.total_fat * CALS_PER_G["fat"]
    return {
        "carb": carb_cals / meal.calories,
        "protein": protein_cals / meal.calories,
        "fat": fat_cals / meal.calories,
    }


def passes_keto(meal: Meal) -> bool:
    # Input: meal (Meal). True if carbs low enough and fat high enough for keto.
    rules = DIET_MACRO_RANGES["keto"]
    pct = _macro_pcts(meal)
    return pct["carb"] <= rules["carb_max_pct"] and pct["fat"] >= rules["fat_min_pct"]


def passes_high_protein(meal: Meal) -> bool:
    # Input: meal (Meal). True if carbs/fat capped and protein high enough.
    rules = DIET_MACRO_RANGES["high_protein"]
    pct = _macro_pcts(meal)
    return (
        pct["carb"] <= rules["carb_max_pct"]
        and pct["fat"] <= rules["fat_max_pct"]
        and pct["protein"] >= rules["protein_min_pct"]
    )


def passes_balanced(meal: Meal) -> bool:
    # Input: meal (Meal). True if all macro fractions sit within balanced ranges.
    rules = DIET_MACRO_RANGES["balanced"]
    pct = _macro_pcts(meal)
    carb_ok = rules["carb_range"][0] <= pct["carb"] <= rules["carb_range"][1]
    fat_ok = rules["fat_range"][0] <= pct["fat"] <= rules["fat_range"][1]
    protein_ok = rules["protein_range"][0] <= pct["protein"] <= rules["protein_range"][1]
    return carb_ok and fat_ok and protein_ok


def passes_low_carb(meal: Meal) -> bool:
    # Input: meal (Meal). True if carb fraction is at or below the low-carb cap.
    rules = DIET_MACRO_RANGES["low_carb"]
    pct = _macro_pcts(meal)
    return pct["carb"] <= rules["carb_max_pct"]


def passes_mediterranean(meal: Meal) -> bool:
    # Input: meal (Meal). True if all macro fractions sit within Mediterranean ranges.
    rules = DIET_MACRO_RANGES["mediterranean"]
    pct = _macro_pcts(meal)
    carb_ok = rules["carb_range"][0] <= pct["carb"] <= rules["carb_range"][1]
    fat_ok = rules["fat_range"][0] <= pct["fat"] <= rules["fat_range"][1]
    protein_ok = rules["protein_range"][0] <= pct["protein"] <= rules["protein_range"][1]
    return carb_ok and fat_ok and protein_ok


# Canonical diet -> hard gate function.
DIET_FILTERS = {
    "keto": passes_keto,
    "low_carb": passes_low_carb,
    "high_protein": passes_high_protein,
    "mediterranean": passes_mediterranean,
    "balanced": passes_balanced,
}


def filter_meals(meals: list[Meal], profile: UserProfile, apply_diet: bool = True) -> list[Meal]:
    # Inputs: meals (list[Meal]), profile (UserProfile), apply_diet (when False,
    # only the allergen safety gate runs — used by the recommender so the home
    # page is never empty; diet then influences ranking instead of excluding).
    # Drops meals failing the allergen check, and (when apply_diet) the diet gate.
    diet_fn = DIET_FILTERS.get(profile.diet) if apply_diet else None
    filtered = []
    for meal in meals:
        if not passes_allergen_check(meal, profile.allergies):
            continue
        if diet_fn and not diet_fn(meal):
            continue
        filtered.append(meal)
    return filtered
