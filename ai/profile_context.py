"""Resolve a UserProfile from a request.

Sources, merged in this order: (1) a stored profile loaded by user_id, then
(2) explicit fields from the backend or user (a friend's stats) override it.
The app DB has no fitness goal; it defaults to "maintenance" unless supplied.
"""
from models import UserProfile

# Stored/selected FoodPreference name -> canonical diet enum. Only macro-
# enforceable plans constrain results; ingredient-based plans (vegetarian/vegan/
# pescatarian/gluten free/dairy free) are accepted but map to "balanced".
DIET_PREFERENCE_MAP = {
    "keto": "keto",
    "low carb": "low_carb",
    "high protein": "high_protein",
    "mediterranean": "mediterranean",
    "vegetarian": "balanced",
    "vegan": "balanced",
    "pescatarian": "balanced",
    "gluten free": "balanced",
    "dairy free": "balanced",
}


def _coarse_diet(diet_preferences: list[str], explicit: str | None) -> str:
    # Inputs: diet_preferences (selected/stored plan names), explicit (caller diet).
    # Returns explicit if given, else the first macro-enforceable plan, else "balanced".
    if explicit:
        return explicit
    fallback = "balanced"
    for pref in diet_preferences or []:
        mapped = DIET_PREFERENCE_MAP.get(pref.strip().lower())
        if mapped and mapped != "balanced":
            return mapped
        if mapped:
            fallback = mapped
    return fallback


def resolve_profile(
    explicit: dict | None,
    user_id: str | None,
    customer_repo=None,
) -> tuple[UserProfile | None, list[str]]:
    # Inputs: explicit (per-request profile fields or None), user_id (stored
    # profile lookup key or None), customer_repo (CustomerRepository or None).
    # Returns (UserProfile, []) or (None, [missing required fields]).
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
        activity_level=data.get("activity_level", "moderately_active"),
        goal=data.get("goal", "maintenance"),
        diet=_coarse_diet(diet_preferences, data.get("diet")),
        allergies=data.get("allergies", []) or [],
    )
    return profile, []
