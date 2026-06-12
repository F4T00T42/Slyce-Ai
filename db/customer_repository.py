"""Read-only access to a customer's stored profile (customers.Customers).

Maps DB fields to the UserProfile shape. The app DB has no fitness goal.
Not every customer row is complete: any unknown field is simply omitted, so the
caller (resolve_profile) can report which required fields are still missing.
DB reads are wrapped in run_with_retry to survive transient pooler hiccups.
"""
from datetime import date

from sqlalchemy import select

from db.connection import run_with_retry
from db.schema import customers_table as C
from db.reference_repository import ReferenceRepository

def _age_from_bday(bday) -> int | None:
    # Input: bday (date or None). Returns age in years, or None if invalid/placeholder.
    if not isinstance(bday, date):
        return None
    if bday.year < 1900:  # guards '-infinity' / placeholder dates
        return None
    today = date.today()
    return today.year - bday.year - ((today.month, today.day) < (bday.month, bday.day))

class CustomerRepository:
    # Loads stored profiles and resolves allergen/preference ids to names.
    def __init__(self, engine):
        # Input: engine (SQLAlchemy engine).
        self._engine = engine
        self._ref = ReferenceRepository(engine)

    def get_profile(self, user_id: str) -> dict | None:
        # Input: user_id (customers.Customers.Id).
        # Returns a partial profile dict (unknown fields omitted), or None if the
        # customer row doesn't exist. Retries transient DB/connection errors.
        def _load() -> dict | None:
            stmt = select(C).where(C.c.Id == user_id)
            with self._engine.connect() as conn:
                row = conn.execute(stmt).first()
            if row is None:
                return None

            allergen_map = self._ref.allergens()
            pref_map = self._ref.food_preferences()
            profile: dict = {}

            if row.Weight is not None and float(row.Weight) > 0:
                profile["weight"] = float(row.Weight)
            if row.Height is not None and int(row.Height) > 0:
                profile["height"] = float(row.Height)
            age = _age_from_bday(row.Bday)
            if age:
                profile["age"] = age
            if row.Gender:
                g = str(row.Gender).strip().lower()
                if g in ("male", "female"):
                    profile["gender"] = g
            if row.ActivityRate:
                # Stored verbatim; UserProfile normalizes any label to the enum.
                profile["activity_level"] = str(row.ActivityRate).strip()

            profile["allergies"] = self._ref.names_for_ids(
                allergen_map, row.allergen_ids or []
            )
            profile["diet_preferences"] = self._ref.names_for_ids(
                pref_map, row.diet_preference_ids or []
            )
            return profile

        return run_with_retry(_load)
