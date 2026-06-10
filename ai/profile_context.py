"""Resolve a UserProfile from the request, supporting three sources:

1. Explicit `profile` fields supplied by the backend or described by the user
   (e.g. a friend's stats).
2. A `user_id` -> fetch the stored profile from customers.Customers.
3. A merge of (2) overridden by (1).

The app DB has no fitness `goal`; it defaults to "maintenance" unless supplied.
Stored diet preferences (Keto, High Protein, ...) are mapped to the
recommender's coarse `diet` enum.
"""
from models import UserProfile

# Map stored FoodPreferences names to the recommender's diet enum.
DIET_PREFERENCE_MAP = {
    "keto": "keto",
    "low carb": "keto",
    "high protein": "high_protein",
}


def _coarse_diet(diet_preferences: list[str], explicit: str | None) -> str:
    if explicit:
        return explicit
    for pref in diet_preferences or []:
        key = pref.strip().lower()
        if key in DIET_PREFERENCE_MAP:
            return DIET_PREFERENCE_MAP[key]
    return "balanced"


def resolve_profile(
    explicit: dict | None,
    user_id: str | None,
    customer_repo=None,
) -> tuple[UserProfile | None, list[str]]:
    """Return (profile_or_None, missing_required_fields).

    If required numeric fields are missing, returns (None, [missing...]) so the
    caller / LLM can ask a follow-up question.
    """
    data: dict = {}
    diet_preferences: list[str] = []

    if user_id and customer_repo is not None:
        stored = customer_repo.get_profile(user_id) or {}
        diet_preferences = stored.pop("diet_preferences", []) or []
        data.update({k: v for k, v in stored.items() if v not in (None, [], "")})

    if explicit:
        diet_preferences = explicit.get("diet_preferences", diet_preferences)
        data.update({k: v for k, v in explicit.items() if v is not None})

    required = ["weight", "height", "age"]
    missing = [f for f in required if not data.get(f)]
    if missing:
        return None, missing

    profile = UserProfile(
        weight=float(data["weight"]),
        height=float(data["height"]),
        age=int(data["age"]),
        gender=data.get("gender", "male"),
        activity_level=data.get("activity_level", "moderate"),
        goal=data.get("goal", "maintenance"),
        diet=_coarse_diet(diet_preferences, data.get("diet")),
        allergies=data.get("allergies", []) or [],
    )
    return profile, []
