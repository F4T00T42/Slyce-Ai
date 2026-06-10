"""Tool: personalized meal recommendations from the app catalog.

Reuses the existing MealRecommender (nutrition targets + filters + scorer).
Diet is a ranking preference, not a hard cut, so this always returns meals.
"""
from ai.tools._profile import get_profile, PROFILE_ARG_SCHEMA

SCHEMA = {
    "type": "function",
    "function": {
        "name": "recommendation_engine",
        "description": (
            "Recommend the best-matching meals from the app's catalog for a "
            "user. Use for 'what should I eat', 'recommend meals', goal-based "
            "suggestions. DEFAULT PATH: pass `user_id` and the system loads that "
            "user's stored, already-translated profile (targets, diet, "
            "allergies) — do NOT ask the user to re-enter stats they've already "
            "saved. Only pass `profile` to OVERRIDE when the user explicitly "
            "states different stats (e.g. for a friend or a hypothetical)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "string",
                    "description": "Preferred input. The system loads this "
                    "user's stored, translated profile; no manual stats needed.",
                },
                "top_n": {"type": "integer", "default": 10},
                "profile": PROFILE_ARG_SCHEMA,
            },
        },
    },
}


def run(args: dict, ctx) -> dict:
    # Inputs: args (user_id?, top_n?=10, profile?), ctx (ToolContext).
    # Resolves the profile then returns ranked catalog recommendations.
    profile, missing = get_profile(args, ctx)
    if profile is None:
        return {
            "status": "need_profile",
            "missing_fields": missing,
            "message": "Need " + ", ".join(missing) + " to compute recommendations.",
        }
    top_n = int(args.get("top_n", 10))
    result = ctx.recommender.recommend(profile, top_n=top_n)
    payload = result.to_dict()
    # Drop verbose scoring breakdowns before returning to the LLM.
    for m in payload["ranked_meals"]:
        m.pop("breakdown", None)
    return {
        "status": "ok",
        "targets": payload["user_targets"],
        "meals_considered": payload["meals_considered"],
        "meals_after_filter": payload["meals_after_filter"],
        "diet_enforced": payload["diet_enforced"],
        "note": payload["note"],
        "recommendations": payload["ranked_meals"],
    }
