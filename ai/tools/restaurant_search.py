"""Tool: discover restaurants and their branches from the app DB."""
SCHEMA = {
    "type": "function",
    "function": {
        "name": "restaurant_search",
        "description": (
            "Find restaurants on the platform by name/keywords and/or city. "
            "Returns restaurants with their branches (area, city, phone). Use "
            "for 'which restaurants are in Cairo', 'find healthy restaurants'."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "city": {"type": "string"},
                "limit": {"type": "integer", "default": 10},
            },
        },
    },
}


def run(args: dict, ctx) -> dict:
    # Inputs: args (query?, city?, limit?=10), ctx (ToolContext).
    results = ctx.restaurant_repo.search(
        query=args.get("query"),
        city=args.get("city"),
        limit=int(args.get("limit", 10)),
    )
    return {"status": "ok", "count": len(results), "restaurants": results}
