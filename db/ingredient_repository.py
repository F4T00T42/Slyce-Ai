"""Ingredient access: composition, nutrition aggregation, allergen detection.

Path: menus.MenuMeals.Id -> menus.MealIngredient (FoodId) -> Food.Foods.
Per-size grams live in menus.IngredientQuantities.
"""
from sqlalchemy import select

from db.schema import (
    foods_table,
    ingredient_quantities_table,
    meal_ingredient_table,
)
from db.reference_repository import ReferenceRepository

# Allergen name -> ingredient-name substrings that imply it is present.
# Food.Allergens is the source of truth for WHICH allergens exist; this dict
# only supplies the detection heuristic. detect_allergens() returns only
# allergens that ALSO exist in Food.Allergens. Add keywords for new allergens.
ALLERGEN_KEYWORDS = {
    "Peanuts": ["peanut"],
    "Tree Nuts": ["almond", "walnut", "cashew", "pecan", "hazelnut", "pistachio", "nut"],
    "Milk": ["milk", "cheese", "butter", "cream", "yogurt", "yoghurt", "mozzarella", "ghee", "dairy"],
    "Eggs": ["egg", "mayo", "mayonnaise"],
    "Fish": ["fish", "salmon", "tuna", "cod", "anchovy", "tilapia"],
    "Shellfish": ["shrimp", "prawn", "crab", "lobster", "clam", "oyster", "mussel", "scallop", "seafood"],
    "Wheat": ["wheat", "flour", "bread", "pasta", "focaccia", "bun", "crouton", "barley", "dough"],
    "Soy": ["soy", "soya", "tofu", "edamame", "miso"],
    "Sesame": ["sesame", "tahini"],
    "Mustard": ["mustard"],
}


class IngredientRepository:
    # Reads ingredient composition and detects allergens for meals.
    def __init__(self, engine):
        # Input: engine (SQLAlchemy engine).
        self._engine = engine
        self._ref = ReferenceRepository(engine)

    def ingredient_names_for_meals(self, menu_meal_ids: list) -> dict:
        # Input: menu_meal_ids (list of menus.MenuMeals.Id).
        # Returns {menu_meal_id: [ingredient_name, ...]}.
        if not menu_meal_ids:
            return {}
        stmt = select(
            meal_ingredient_table.c.MealId,
            meal_ingredient_table.c.Name,
        ).where(meal_ingredient_table.c.MealId.in_(menu_meal_ids))
        out: dict = {}
        with self._engine.connect() as conn:
            for row in conn.execute(stmt):
                out.setdefault(str(row.MealId), []).append(row.Name)
        return out

    def composition_for_size(self, meal_size_id: str) -> list:
        # Input: meal_size_id (menus.MealSizes.Id).
        # Returns ingredient rows with grams + per-100g nutrition scaled to grams.
        stmt = (
            select(
                ingredient_quantities_table.c.Quantity,
                foods_table.c.Name,
                foods_table.c.Calories,
                foods_table.c.Protein,
                foods_table.c.TotalCarbohydrate,
                foods_table.c.TotalFat,
            )
            .select_from(
                ingredient_quantities_table.join(
                    foods_table,
                    ingredient_quantities_table.c.MealIngredientId == foods_table.c.Id,
                )
            )
            .where(ingredient_quantities_table.c.MealSizeId == meal_size_id)
        )
        rows = []
        with self._engine.connect() as conn:
            for r in conn.execute(stmt):
                q = float(r.Quantity or 0)
                factor = q / 100.0  # Food nutrition is per 100g
                rows.append(
                    {
                        "name": r.Name,
                        "quantity_g": q,
                        "calories": float(r.Calories or 0) * factor,
                        "protein": float(r.Protein or 0) * factor,
                        "carbs": float(r.TotalCarbohydrate or 0) * factor,
                        "fat": float(r.TotalFat or 0) * factor,
                    }
                )
        return rows

    def detect_allergens(self, ingredient_names: list) -> list:
        # Input: ingredient_names (list of ingredient strings).
        # Returns detected allergens, restricted to Food.Allergens (DB spelling).
        db_by_lower = {
            name.lower(): name for name in self._ref.allergen_names()
        }
        blob = " ".join(n.lower() for n in ingredient_names if n)
        found = set()
        for allergen, keywords in ALLERGEN_KEYWORDS.items():
            canonical = db_by_lower.get(allergen.lower())
            if canonical is None:
                continue  # not tracked in Food.Allergens -> ignore
            if any(kw in blob for kw in keywords):
                found.add(canonical)
        return sorted(found)
