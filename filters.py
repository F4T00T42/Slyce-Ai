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


# --- Allergen synonym matching (shared by the allergy assistant) -------------
# Maps user-facing synonyms to the canonical allergen names used in
# Food.Allergens. Keys are lowercased and stripped of non-alphanumerics.
_ALLERGEN_SYNONYMS = {
    "milk": "milk", "dairy": "milk", "lactose": "milk", "cheese": "milk",
    "egg": "egg", "eggs": "egg",
    "fish": "fish",
    "shellfish": "shellfish", "crustacean": "shellfish",
    "crustaceans": "shellfish", "shrimp": "shellfish", "prawn": "shellfish",
    "prawns": "shellfish", "crab": "shellfish", "lobster": "shellfish",
    "treenut": "tree nuts", "treenuts": "tree nuts", "nut": "tree nuts",
    "nuts": "tree nuts", "almond": "tree nuts", "almonds": "tree nuts",
    "cashew": "tree nuts", "cashews": "tree nuts", "walnut": "tree nuts",
    "walnuts": "tree nuts", "hazelnut": "tree nuts", "hazelnuts": "tree nuts",
    "pistachio": "tree nuts", "pistachios": "tree nuts",
    "peanut": "peanut", "peanuts": "peanut", "groundnut": "peanut",
    "groundnuts": "peanut",
    "wheat": "wheat", "gluten": "wheat",
    "soy": "soy", "soya": "soy", "soybean": "soy", "soybeans": "soy",
    "sesame": "sesame",
    "mustard": "mustard",
}

def _canonical_allergen(name: str) -> str:
    # Input: name (allergen or synonym). Returns the canonical allergen key when
    # a synonym is known, else a space-normalized lowercase form so unknown
    # allergens still compare by equality (never by substring).
    key = "".join(c for c in str(name).lower() if c.isalnum())
    if key in _ALLERGEN_SYNONYMS:
        return _ALLERGEN_SYNONYMS[key]
    return " ".join(str(name).lower().split())

def allergy_conflicts(user_allergies, detected) -> list[str]:
    # Inputs: user_allergies (the user's declared allergies, possibly using
    # synonyms such as "dairy" or "nuts"), detected (allergen names found in a
    # meal, using Food.Allergens canonical names). Returns the detected allergens
    # the user is allergic to, matched on canonical key only (so "fish" never
    # matches "shellfish"). Order and uniqueness of `detected` are preserved.
    if not user_allergies or not detected:
        return []
    user_keys = {_canonical_allergen(a) for a in user_allergies}
    conflicts: list[str] = []
    seen = set()
    for d in detected:
        if d in seen:
            continue
        if _canonical_allergen(d) in user_keys:
            conflicts.append(d)
            seen.add(d)
    return conflicts
