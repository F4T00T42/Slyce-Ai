"""Ingredient-level access: composition + nutrition aggregation + allergen
detection.

A meal's ingredients are reached via menus.MenuMeals.Id -> menus.MealIngredient
(FoodId) -> Food.Foods. Per-size quantities live in menus.IngredientQuantities
(MealSizeId, MealIngredientId == Food.Foods.Id).
"""
from sqlalchemy import select

from db.schema import (
    foods_table,
    ingredient_quantities_table,
    meal_ingredient_table,
)

# Map allergen names to substrings that, if found in an ingredient/food name,
# imply the allergen is present. Heuristic (no explicit Food->Allergen table).
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
    def __init__(self, engine):
        self._engine = engine

    def ingredient_names_for_meals(self, menu_meal_ids: list) -> dict:
        """Return {menu_meal_id: [ingredient_name, ...]} for the given meals."""
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
        """Return ingredient rows for a meal size with quantity (grams) and the
        ingredient's per-100g nutrition from Food.Foods.
        """
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

    @staticmethod
    def detect_allergens(ingredient_names: list) -> list:
        """Heuristic allergen detection from ingredient names."""
        found = set()
        blob = " ".join(n.lower() for n in ingredient_names if n)
        for allergen, keywords in ALLERGEN_KEYWORDS.items():
            if any(kw in blob for kw in keywords):
                found.add(allergen)
        return sorted(found)
