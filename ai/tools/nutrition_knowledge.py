"""Tool: answer general nutrition questions from the curated knowledge base
(RAG over trusted public-domain sources: NIH/ODS, WHO, CDC, USDA, etc.).
"""
SCHEMA = {
    "type": "function",
    "function": {
        "name": "nutrition_knowledge_search",
        "description": (
            "Retrieve trusted nutrition facts and guidance from the curated "
            "knowledge base. Use for general 'what is / why / how much' nutrition "
            "questions (macros, micronutrients, hydration, fiber, etc.). Prefer "
            "this over web_search."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The nutrition question."},
                "top_k": {"type": ["integer", "string"], "default": 5},
            },
            "required": ["query"],
        },
    },
}


def run(args: dict, ctx) -> dict:
    # Inputs: args (query, top_k?=5), ctx (ToolContext; uses ctx.retriever).
    # Returns scored KB chunks and records their sources in ctx.citations.
    query = args.get("query", "").strip()
    if not query:
        return {"status": "error", "message": "query is required"}
    if ctx.retriever is None:
        return {"status": "unavailable", "message": "Knowledge base is not configured."}
    hits = ctx.retriever.search(query, top_k=args.get("top_k", 5))
    for h in hits:
        src = h.get("source") or h.get("title")
        if src and src not in ctx.citations:
            ctx.citations.append(src)
    return {
        "status": "ok" if hits else "no_results",
        "chunks": hits,
    }
