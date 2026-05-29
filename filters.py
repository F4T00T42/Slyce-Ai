from models import Meal, UserProfile
from nutrition import DIET_MACRO_RANGES, CALS_PER_G


def passes_allergen_check(meal: Meal, allergies: list[str]) -> bool:
    # Returns False if any user allergen appears in the meal's tags.
    if not allergies:
        return True
    lowered_tags = {t.lower() for t in meal.tags}
    return not any(a.lower() in lowered_tags for a in allergies)


def _macro_pcts(meal: Meal) -> dict[str, float]:
    # Returns each macro as a fraction of total meal calories.
    if meal.calories <= 0:
        return {"carb": 0.0, "protein": 0.0, "fat": 0.0}

    carb_cals    = meal.total_carbohydrate * CALS_PER_G["carb"]
    protein_cals = meal.protein            * CALS_PER_G["protein"]
    fat_cals     = meal.total_fat          * CALS_PER_G["fat"]

    return {
        "carb":    carb_cals    / meal.calories,
        "protein": protein_cals / meal.calories,
        "fat":     fat_cals     / meal.calories,
    }


def passes_keto(meal: Meal) -> bool:
    rules = DIET_MACRO_RANGES["keto"]
    pct = _macro_pcts(meal)
    return (
        pct["carb"] <= rules["carb_max_pct"]
        and pct["fat"] >= rules["fat_min_pct"]
    )


def passes_high_protein(meal: Meal) -> bool:
    rules = DIET_MACRO_RANGES["high_protein"]
    pct = _macro_pcts(meal)
    return (
        pct["carb"]    <= rules["carb_max_pct"]
        and pct["fat"] <= rules["fat_max_pct"]
        and pct["protein"] >= rules["protein_min_pct"]
    )


def passes_balanced(meal: Meal) -> bool:
    rules = DIET_MACRO_RANGES["balanced"]
    pct = _macro_pcts(meal)
    carb_ok    = rules["carb_range"][0]    <= pct["carb"]    <= rules["carb_range"][1]
    fat_ok     = rules["fat_range"][0]     <= pct["fat"]     <= rules["fat_range"][1]
    protein_ok = rules["protein_range"][0] <= pct["protein"] <= rules["protein_range"][1]
    return carb_ok and fat_ok and protein_ok


# Maps each diet string to its hard-pass filter function.
DIET_FILTERS = {
    "keto":         passes_keto,
    "high_protein": passes_high_protein,
    "balanced":     passes_balanced,
}


def filter_meals(meals: list[Meal], profile: UserProfile) -> list[Meal]:
    # Removes meals that fail allergen or diet checks.
    diet_fn = DIET_FILTERS.get(profile.diet)

    filtered = []
    for meal in meals:
        if not passes_allergen_check(meal, profile.allergies):
            continue
        if diet_fn and not diet_fn(meal):
            continue
        filtered.append(meal)

    return filtered
