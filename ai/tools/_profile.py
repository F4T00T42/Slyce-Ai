"""Shared helper for tools that need a resolved UserProfile."""
from ai.profile_context import resolve_profile


def get_profile(args: dict, ctx):
    # Inputs: args (tool args; may carry profile/user_id), ctx (ToolContext).
    # Priority: explicit tool args > ctx.profile > stored profile by user_id.
    # Returns (profile or None, missing_required_fields).
    if ctx.profile is not None and not args.get("profile"):
        return ctx.profile, []
    explicit = args.get("profile") or ctx.explicit_profile
    user_id = args.get("user_id") or ctx.user_id
    return resolve_profile(explicit, user_id, ctx.customer_repo)


# Human-friendly labels for the required fields when asking the user.
_FIELD_LABELS = {"weight": "weight (kg)", "height": "height (cm)", "age": "age"}


def need_profile_response(missing: list) -> dict:
    # Input: missing (list of required field names not on file).
    # Returns a standard 'need_profile' tool result whose message tells the model
    # to ask the user for the missing MEASUREMENTS — never for a user_id/account id
    # (the backend supplies that automatically).
    labels = [_FIELD_LABELS.get(f, f) for f in missing] or [
        "weight (kg)",
        "height (cm)",
        "age",
    ]
    human = ", ".join(labels)
    return {
        "status": "need_profile",
        "missing_fields": missing,
        "message": (
            "This user's saved profile is missing " + human + ", which are "
            "required to calculate nutrition targets. Ask the user to share their "
            + human + ". Do NOT ask for a user_id or any account id — the app "
            "provides that automatically."
        ),
    }


# Reusable JSON schema for an explicit profile argument on profile-aware tools.
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
            "enum": [
                "sedentary", "lightly_active", "moderately_active",
                "very_active", "super_active",
            ],
        },
        "goal": {
            "type": "string",
            "enum": ["fat_loss", "muscle_gain", "maintenance"],
        },
        "diet": {
            "type": "string",
            "enum": ["keto", "low_carb", "high_protein", "mediterranean", "balanced"],
        },
        "allergies": {"type": "array", "items": {"type": "string"}},
    },
}
