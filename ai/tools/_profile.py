"""Shared helper for tools that need a resolved profile."""
from ai.profile_context import resolve_profile


def get_profile(args: dict, ctx):
    """Resolve a profile using (in priority) tool args > ctx.profile > stored.

    Returns (profile, missing_fields). If the tool call carried explicit profile
    fields, they override everything.
    """
    if ctx.profile is not None and not args.get("profile"):
        return ctx.profile, []
    explicit = args.get("profile") or ctx.explicit_profile
    user_id = args.get("user_id") or ctx.user_id
    return resolve_profile(explicit, user_id, ctx.customer_repo)


PROFILE_ARG_SCHEMA = {
    "type": "object",
    "description": "Explicit profile fields. Provide when the user describes "
    "stats directly (e.g. their own or a friend's).",
    "properties": {
        "weight": {"type": "number", "description": "kg"},
        "height": {"type": "number", "description": "cm"},
        "age": {"type": "integer"},
        "gender": {"type": "string", "enum": ["male", "female"]},
        "activity_level": {
            "type": "string",
            "enum": ["sedentary", "light", "moderate", "active", "very_active"],
        },
        "goal": {
            "type": "string",
            "enum": ["fat_loss", "muscle_gain", "maintenance"],
        },
        "diet": {"type": "string", "enum": ["keto", "high_protein", "balanced"]},
        "allergies": {"type": "array", "items": {"type": "string"}},
    },
}
