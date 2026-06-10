"""Tool: search the meal catalog and analyze a meal's nutrition/ingredients.

Covers 'meal discovery' (by name/macros) and 'meal analysis' (ingredient and
nutrition breakdown for a specific meal size).
"""
SCHEMA = {
    "type": "function",
    "function": {
        "name": "meal_search",
        "description": (
            "Search the app's meal catalog by name/keywords and optional macro "
            "limits, or analyze a specific meal's ingredients and nutrition when "
            "a meal_id is given. Use for 'find a high-protein meal', 'what's in "
            "the Grilled Greek Chicken', 'show me salads under 500 calories'."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Meal name or keywords"},
                "max_calories": {"type": "number"},
                "min_protein": {"type": "number"},
                "meal_id": {
                    "type": "string",
                    "description": "MealSizes.Id to analyze in detail (ingredients + macros).",
                },
                "limit": {"type": "integer", "default": 10},
            },
        },
    },
}


def _meal_brief(m) -> dict:
    return {
        "meal_id": m.meal_id,
        "name": m.name,
        "calories": round(m.calories, 1),
        "protein_g": round(m.protein, 1),
        "carbs_g": round(m.total_carbohydrate, 1),
        "fat_g": round(m.total_fat, 1),
        "price": m.price,
        "currency": m.currency,
        "allergens": m.tags,
    }


def run(args: dict, ctx) -> dict:
    meal_id = args.get("meal_id")
    if meal_id:
        meals = ctx.meal_repo.get_by_ids([meal_id], with_allergens=True)
        if not meals:
            return {"status": "not_found", "meal_id": meal_id}
        meal = meals[0]
        composition = ctx.ingredient_repo.composition_for_size(meal_id)
        return {
            "status": "ok",
            "meal": {
                **_meal_brief(meal),
                "description": meal.description,
                "sodium_mg": round(meal.sodium_mg, 1),
                "sugar_g": round(meal.sugar_grams, 1),
                "fiber_g": round(meal.dietary_fiber, 1),
                "ingredients": meal.ingredients,
            },
            "composition": composition,
        }

    meals = ctx.meal_repo.search(
        query=args.get("query"),
        max_calories=args.get("max_calories"),
        min_protein=args.get("min_protein"),
        limit=int(args.get("limit", 10)),
    )
    return {"status": "ok", "count": len(meals), "results": [_meal_brief(m) for m in meals]}
