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
                "max_calories": {
                    "type": "string",
                    "description": "Optional max calories filter, e.g. \"500\".",
                },
                "min_protein": {
                    "type": "string",
                    "description": "Optional min protein in grams, e.g. \"30\".",
                },
                "meal_id": {
                    "type": "string",
                    "description": "MenuMeals.Id (the meal_id returned by search/recommendations) to analyze in detail.",
                },
                "limit": {
                    "type": "string",
                    "description": "Max number of results to return (default 10).",
                },
            },
        },
    },
}

def _meal_brief(m) -> dict:
    # Input: m (Meal). Returns a compact summary dict (macros, price, allergens).
    return {
        "meal_id": m.meal_id,
        "size_id": m.size_id,
        "size_name": m.size_name,
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
    composition = ctx.ingredient_repo.composition_for_size(meal.size_id)
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
    from ai.tools import coerce_int, coerce_float

    # Numeric args may arrive as strings (the schema declares them as strings
    # for cross-provider compatibility), so coerce them explicitly here.
    max_calories = coerce_float(args.get("max_calories"), None)
    min_protein = coerce_float(args.get("min_protein"), None)
    limit = coerce_int(args.get("limit"), 10)
    meal_id = args.get("meal_id")
    query = (args.get("query") or "").strip()

    # Name-only path: resolve a confident single match so no meal_id is needed.
    if not meal_id and query:
        meals = ctx.meal_repo.search(
            query=query,
            max_calories=max_calories,
            min_protein=min_protein,
            limit=limit,
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
        max_calories=max_calories,
        min_protein=min_protein,
        limit=limit,
    )
    return {"status": "ok", "count": len(meals), "results": [_meal_brief(m) for m in meals]}
