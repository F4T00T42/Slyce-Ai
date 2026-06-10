"""Tool: personalized meal recommendations from the app catalog.

Reuses the existing MealRecommender (nutrition targets + filters + scorer).
"""
from ai.tools._profile import get_profile, PROFILE_ARG_SCHEMA

SCHEMA = {
    "type": "function",
    "function": {
        "name": "recommendation_engine",
        "description": (
            "Recommend the best-matching meals from the app's catalog for a "
            "user's nutrition profile and goal. Use for 'what should I eat', "
            "'recommend meals', goal-based suggestions. Requires weight, height "
            "and age (from the stored profile or provided explicitly)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "profile": PROFILE_ARG_SCHEMA,
                "user_id": {"type": "string"},
                "top_n": {"type": "integer", "default": 5},
            },
        },
    },
}


def run(args: dict, ctx) -> dict:
    profile, missing = get_profile(args, ctx)
    if profile is None:
        return {
            "status": "need_profile",
            "missing_fields": missing,
            "message": "Need " + ", ".join(missing) + " to compute recommendations.",
        }
    top_n = int(args.get("top_n", 5))
    result = ctx.recommender.recommend(profile, top_n=top_n)
    payload = result.to_dict()
    # Trim verbose breakdowns for the LLM.
    for m in payload["ranked_meals"]:
        m.pop("breakdown", None)
    return {
        "status": "ok",
        "targets": payload["user_targets"],
        "meals_considered": payload["meals_considered"],
        "meals_after_filter": payload["meals_after_filter"],
        "recommendations": payload["ranked_meals"],
    }
