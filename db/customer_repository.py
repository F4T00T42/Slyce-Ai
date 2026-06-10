"""Read-only access to a customer's stored profile (customers.Customers).

Maps DB fields to the shape used by `UserProfile`. Note the app DB does NOT
store a fitness `goal`; it must be supplied by the caller/conversation.
"""
from datetime import date

from sqlalchemy import select

from db.schema import customers_table as C
from db.reference_repository import ReferenceRepository

# DB ActivityRate text -> recommender activity_level enum.
ACTIVITY_MAP = {
    "sedentary": "sedentary",
    "light": "light",
    "lightlyactive": "light",
    "moderate": "moderate",
    "moderatelyactive": "moderate",
    "active": "active",
    "veryactive": "very_active",
    "very_active": "very_active",
    "extraactive": "very_active",
}


def _age_from_bday(bday) -> int | None:
    if not isinstance(bday, date):
        return None
    if bday.year < 1900:  # guards '-infinity' / placeholder dates
        return None
    today = date.today()
    return today.year - bday.year - ((today.month, today.day) < (bday.month, bday.day))


class CustomerRepository:
    def __init__(self, engine):
        self._engine = engine
        self._ref = ReferenceRepository(engine)

    def get_profile(self, user_id: str) -> dict | None:
        """Return a partial profile dict, or None if the customer is missing.

        Fields that are unknown/incomplete in the DB are omitted so the caller
        can fall back to conversation or defaults.
        """
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
            key = str(row.ActivityRate).strip().lower().replace(" ", "")
            if key in ACTIVITY_MAP:
                profile["activity_level"] = ACTIVITY_MAP[key]

        profile["allergies"] = self._ref.names_for_ids(allergen_map, row.allergen_ids or [])
        profile["diet_preferences"] = self._ref.names_for_ids(
            pref_map, row.diet_preference_ids or []
        )
        return profile
