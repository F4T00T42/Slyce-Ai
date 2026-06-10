"""Tool: search the meal catalog and analyze a meal's nutrition/ingredients.

Covers meal discovery (by name/macros) and meal analysis (ingredient + nutrition
breakdown for a specific meal size). A confident name match auto-analyzes, so
the user never has to supply a meal_id.
"""
SCHEMA = {
    "type": "function",
    "function": {
        "name": "meal_search",
        "description": (
            "Search the app's meal catalog by name/keywords and optional macro "
            "limits, or analyze one meal's ingredients and nutrition. Pass "
            "`meal_id` for an exact analysis, OR just pass the meal name as "
            "`query`: if it resolves to a single meal the tool returns that "
            "meal's full analysis automatically (no id needed); otherwise it "
            "returns the list of matches to choose from. Use for 'find a "
            "high-protein meal', 'what's in the Grilled Greek Chicken', 'show "
            "me salads under 500 calories'."
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
    # Input: m (Meal). Returns a compact summary dict (macros, price, allergens).
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


def _best_name_match(meals: list, query: str):
    # Inputs: meals (search results), query (user text). Returns one confident
    # match (exact case-insensitive name, or the lone result) or None.
    if not meals:
        return None
    q = query.strip().lower()
    exact = [
        m for m in meals
        if m.name.lower() == q or m.name.lower().split(" (")[0] == q
    ]
    if len(exact) == 1:
        return exact[0]
    if len(meals) == 1:
        return meals[0]
    return None


def _analyze(meal, ctx) -> dict:
    # Inputs: meal (Meal), ctx (ToolContext). Returns full nutrition + per-
    # ingredient composition for one meal size.
    composition = ctx.ingredient_repo.composition_for_size(meal.meal_id)
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


def run(args: dict, ctx) -> dict:
    # Inputs: args (query?, meal_id?, max_calories?, min_protein?, limit?=10),
    # ctx (ToolContext). Routes to analyze-by-name, analyze-by-id, or plain search.
    meal_id = args.get("meal_id")
    query = (args.get("query") or "").strip()

    # Name-only path: resolve a confident single match so no meal_id is needed.
    if not meal_id and query:
        meals = ctx.meal_repo.search(
            query=query,
            max_calories=args.get("max_calories"),
            min_protein=args.get("min_protein"),
            limit=int(args.get("limit", 10)),
        )
        match = _best_name_match(meals, query)
        if match is not None:
            return _analyze(match, ctx)
        return {
            "status": "ok",
            "count": len(meals),
            "results": [_meal_brief(m) for m in meals],
        }

    # Explicit id path: analyze that exact meal size.
    if meal_id:
        meals = ctx.meal_repo.get_by_ids([meal_id], with_allergens=True)
        if not meals:
            return {"status": "not_found", "meal_id": meal_id}
        return _analyze(meals[0], ctx)

    # No id and no query: plain catalog search (macro filters only).
    meals = ctx.meal_repo.search(
        query=None,
        max_calories=args.get("max_calories"),
        min_protein=args.get("min_protein"),
        limit=int(args.get("limit", 10)),
    )
    return {"status": "ok", "count": len(meals), "results": [_meal_brief(m) for m in meals]}
