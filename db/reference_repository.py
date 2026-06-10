"""Lookup tables: allergens and diet preferences (id <-> name)."""
from functools import lru_cache

from sqlalchemy import select

from db.schema import allergens_table, food_preferences_table


class ReferenceRepository:
    def __init__(self, engine):
        self._engine = engine

    @lru_cache(maxsize=1)
    def allergens(self) -> dict:
        """Return {id: name}."""
        with self._engine.connect() as conn:
            rows = conn.execute(
                select(allergens_table.c.Id, allergens_table.c.Name)
            ).all()
        return {str(r.Id): r.Name for r in rows}

    def allergen_names(self) -> list:
        return list(self.allergens().values())

    @lru_cache(maxsize=1)
    def food_preferences(self) -> dict:
        with self._engine.connect() as conn:
            rows = conn.execute(
                select(food_preferences_table.c.Id, food_preferences_table.c.Name)
            ).all()
        return {str(r.Id): r.Name for r in rows}

    def names_for_ids(self, mapping: dict, ids) -> list:
        if not ids:
            return []
        return [mapping[str(i)] for i in ids if str(i) in mapping]
