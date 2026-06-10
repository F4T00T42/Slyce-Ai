"""Hard pass/fail gates: allergen check + per-diet macro gates.

Allergen detection reads meal.tags, which the repository layer populates with
allergen names derived from each meal's ingredients. Macro fractions come from
nutrition.macro_calorie_fractions (shared with the scorer).
"""
from models import Meal, UserProfile
from nutrition import DIET_MACRO_RANGES, macro_calorie_fractions


def passes_allergen_check(meal: Meal, allergies: list[str]) -> bool:
    # Inputs: meal (Meal), allergies (user allergen names). False if any overlap.
    if not allergies:
        return True
    lowered_tags = {t.lower() for t in meal.tags}
    return not any(a.lower() in lowered_tags for a in allergies)


def _in_range(value: float, bounds) -> bool:
    # Inputs: value (macro fraction), bounds ((lo, hi)). True if lo <= value <= hi.
    return bounds[0] <= value <= bounds[1]


def passes_keto(meal: Meal) -> bool:
    # Input: meal (Meal). True if carbs low enough and fat high enough for keto.
    rules = DIET_MACRO_RANGES["keto"]
    pct = macro_calorie_fractions(meal)
    return pct["carb"] <= rules["carb_max_pct"] and pct["fat"] >= rules["fat_min_pct"]


def passes_low_carb(meal: Meal) -> bool:
    # Input: meal (Meal). True if carb fraction is at or below the low-carb cap.
    rules = DIET_MACRO_RANGES["low_carb"]
    return macro_calorie_fractions(meal)["carb"] <= rules["carb_max_pct"]


def passes_high_protein(meal: Meal) -> bool:
    # Input: meal (Meal). True if carbs/fat capped and protein high enough.
    rules = DIET_MACRO_RANGES["high_protein"]
    pct = macro_calorie_fractions(meal)
    return (
        pct["carb"] <= rules["carb_max_pct"]
        and pct["fat"] <= rules["fat_max_pct"]
        and pct["protein"] >= rules["protein_min_pct"]
    )


def _passes_macro_ranges(meal: Meal, diet: str) -> bool:
    # Inputs: meal (Meal), diet (range-based diet key). Shared gate for the
    # range-based diets (balanced, mediterranean): every macro fraction must sit
    # within its configured range.
    rules = DIET_MACRO_RANGES[diet]
    pct = macro_calorie_fractions(meal)
    return (
        _in_range(pct["carb"], rules["carb_range"])
        and _in_range(pct["fat"], rules["fat_range"])
        and _in_range(pct["protein"], rules["protein_range"])
    )


def passes_balanced(meal: Meal) -> bool:
    # Input: meal (Meal). True if all macro fractions sit within balanced ranges.
    return _passes_macro_ranges(meal, "balanced")


def passes_mediterranean(meal: Meal) -> bool:
    # Input: meal (Meal). True if all macro fractions sit within Mediterranean ranges.
    return _passes_macro_ranges(meal, "mediterranean")


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
