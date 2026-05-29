import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import select
from sqlalchemy.engine import Engine

from models import Meal
from db.schema import meal_sizes_table as mst


class MealRepository:
    # Read-only access to the MealSizes table.

    def __init__(self, engine: Engine):
        self._engine = engine

    def get_all(self) -> list[Meal]:
        # Fetches every row and returns them as Meal objects.
        stmt = select(mst)
        with self._engine.connect() as conn:
            rows = conn.execute(stmt).mappings().all()
        return [self._map(row) for row in rows]

    def get_by_id(self, meal_id: int) -> Meal | None:
        # Returns the Meal with the given ID, or None if not found.
        stmt = select(mst).where(mst.c.MealId == meal_id)
        with self._engine.connect() as conn:
            row = conn.execute(stmt).mappings().first()
        return self._map(row) if row else None

    def get_by_ids(self, meal_ids: list[int]) -> list[Meal]:
        # Fetches multiple meals by ID in a single query.
        if not meal_ids:
            return []
        stmt = select(mst).where(mst.c.MealId.in_(meal_ids))
        with self._engine.connect() as conn:
            rows = conn.execute(stmt).mappings().all()
        return [self._map(row) for row in rows]

    @staticmethod
    def _map(row) -> Meal:
        # Converts a DB row to a Meal dataclass; NULL nutrients become 0.0.
        def f(val) -> float:
            return float(val) if val is not None else 0.0

        return Meal(
            meal_id=row["MealId"],
            name=row["Name"],
            calories=f(row["Calories"]),
            sodium_mg=f(row.get("SodiumMg")),
            sugar_grams=f(row.get("SugarGrams")),
            calcium_mg=f(row.get("CalciumMg")),
            cholesterol=f(row.get("Cholesterol")),
            dietary_fiber=f(row.get("DietaryFiber")),
            iron_mg=f(row.get("IronMg")),
            potassium_mg=f(row.get("PotassiumMg")),
            protein=f(row.get("Protein")),
            saturated_fat=f(row.get("SaturatedFat")),
            total_carbohydrate=f(row.get("TotalCarbohydrate")),
            total_fat=f(row.get("TotalFat")),
            trans_fat=f(row.get("TransFat")),
            vitamin_a_mcg=f(row.get("VitaminAMcg")),
            vitamin_c_mg=f(row.get("VitaminCMg")),
            vitamin_d=f(row.get("VitaminD")),
            tags=list(row.get("Tags") or []),
        )
