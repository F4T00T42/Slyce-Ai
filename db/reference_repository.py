"""Lookup tables: allergens and food preferences (id <-> name)."""
from functools import lru_cache

from sqlalchemy import select

from db.schema import allergens_table, food_preferences_table


class ReferenceRepository:
    # Cached id->name maps for Food.Allergens and Food.FoodPreferences.
    def __init__(self, engine):
        # Input: engine (SQLAlchemy engine).
        self._engine = engine

    @lru_cache(maxsize=1)
    def allergens(self) -> dict:
        # Returns {allergen_id: name} (cached).
        with self._engine.connect() as conn:
            rows = conn.execute(
                select(allergens_table.c.Id, allergens_table.c.Name)
            ).all()
        return {str(r.Id): r.Name for r in rows}

    def allergen_names(self) -> list:
        # Returns the list of known allergen names.
        return list(self.allergens().values())

    @lru_cache(maxsize=1)
    def food_preferences(self) -> dict:
        # Returns {preference_id: name} (cached).
        with self._engine.connect() as conn:
            rows = conn.execute(
                select(food_preferences_table.c.Id, food_preferences_table.c.Name)
            ).all()
        return {str(r.Id): r.Name for r in rows}

    def names_for_ids(self, mapping: dict, ids) -> list:
        # Inputs: mapping (id->name dict), ids (iterable of ids).
        # Returns the names for ids present in mapping.
        if not ids:
            return []
        return [mapping[str(i)] for i in ids if str(i) in mapping]
