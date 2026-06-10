"""Tool: allergy assistance.

Given a meal (by id) or a free-text ingredient list, flags which of the
platform's known allergens are present, and checks against the user's declared
allergies. Allergen detection uses ingredient-name matching (the DB has no
explicit food->allergen mapping table).
"""
from ai.tools._profile import get_profile
from db.ingredient_repository import IngredientRepository

SCHEMA = {
    "type": "function",
    "function": {
        "name": "allergy_assistant",
        "description": (
            "Check a meal or a list of ingredients for allergens and compare "
            "against the user's allergies. Use for 'is this safe for my nut "
            "allergy', 'does this contain dairy', 'what allergens are in X'."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "meal_id": {"type": "string", "description": "MealSizes.Id to check."},
                "ingredients": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Free-text ingredient names to check.",
                },
                "user_id": {"type": "string"},
            },
        },
    },
}


def run(args: dict, ctx) -> dict:
    ingredient_names = list(args.get("ingredients") or [])
    meal_name = None
    if args.get("meal_id"):
        meals = ctx.meal_repo.get_by_ids([args["meal_id"]], with_allergens=True)
        if not meals:
            return {"status": "not_found", "meal_id": args["meal_id"]}
        meal_name = meals[0].name
        ingredient_names += meals[0].ingredients

    if not ingredient_names:
        return {"status": "error", "message": "Provide a meal_id or ingredients."}

    detected = IngredientRepository.detect_allergens(ingredient_names)

    # Compare with the user's declared allergies if we can resolve a profile.
    user_allergies = []
    profile, _ = get_profile(args, ctx)
    if profile is not None:
        user_allergies = profile.allergies
    elif ctx.user_id and ctx.customer_repo is not None:
        stored = ctx.customer_repo.get_profile(ctx.user_id) or {}
        user_allergies = stored.get("allergies", [])

    conflicts = sorted(
        {a for a in user_allergies for d in detected if a.lower() == d.lower()}
    )
    return {
        "status": "ok",
        "meal": meal_name,
        "detected_allergens": detected,
        "user_allergies": user_allergies,
        "conflicts": conflicts,
        "safe_for_user": (len(conflicts) == 0) if user_allergies else None,
        "note": "Allergen detection is heuristic (ingredient-name based); verify "
        "with the restaurant for severe allergies.",
    }
