"""Tool: web search fallback (Tavily). LAST-RESORT only, per priority policy.

Hard-gated behind user_requested: it refuses unless the user explicitly asked
for (or agreed to) an internet search. The Tavily SDK is imported lazily; a web
client can also be injected via ctx for testing.
"""
from ai.config import settings

SCHEMA = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": (
            "Search the public web for nutrition information. Call this ONLY "
            "when the user has EXPLICITLY asked you to search the internet/web, "
            "OR after you offered to search and the user agreed. NEVER call it "
            "on your own initiative. If the database and knowledge base can't "
            "answer, ask the user first, then call this only once they say yes. "
            "Always tell the user the answer came from the web."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "max_results": {"type": ["integer", "string"], "default": 5},
                "user_requested": {
                    "type": "boolean",
                    "description": "Must be true. Set ONLY when the user "
                    "explicitly asked for a web/internet search or agreed to "
                    "one. If you haven't been asked/granted permission, do not "
                    "call this tool — ask the user first.",
                },
            },
            "required": ["query", "user_requested"],
        },
    },
}

def _client(ctx):
    # Input: ctx (ToolContext). Returns the injected web client or a lazily-built
    # Tavily client; raises if TAVILY_API_KEY is unset.
    if ctx.web_client is not None:
        return ctx.web_client
    from tavily import TavilyClient  # lazy import

    if not settings.tavily_api_key:
        raise RuntimeError("TAVILY_API_KEY is not configured")
    client = TavilyClient(api_key=settings.tavily_api_key)
    ctx.web_client = client
    return client

def run(args: dict, ctx) -> dict:
    # Inputs: args (query, user_requested, max_results?=5), ctx (ToolContext).
    # Refuses unless user_requested is true; otherwise returns web results + cites them.
    if not args.get("user_requested"):
        return {
            "status": "confirmation_required",
            "message": (
                "Do not search the web yet. Ask the user to confirm they want "
                "an internet search, then call this tool again with "
                "user_requested=true."
            ),
        }
    query = args.get("query", "").strip()
    if not query:
        return {"status": "error", "message": "query is required"}
    client = _client(ctx)
    resp = client.search(
        query=query,
        max_results=args.get("max_results", 5),
        search_depth="basic",
    )
    results = []
    for r in (resp.get("results") if isinstance(resp, dict) else []) or []:
        results.append(
            {"title": r.get("title"), "url": r.get("url"), "content": r.get("content")}
        )
        if r.get("url") and r["url"] not in ctx.citations:
            ctx.citations.append(r["url"])
    return {"status": "ok" if results else "no_results", "source": "web", "results": results}
