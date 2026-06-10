"""Tool: web search fallback (Tavily). LAST-RESORT only, per priority policy.

The Tavily SDK is imported lazily. The web client is also injected via ctx for
testing / provider swapping.
"""
from ai.config import settings

SCHEMA = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": (
            "Search the public web for nutrition information. Use ONLY as a last "
            "resort when the app database and the nutrition knowledge base cannot "
            "answer. Always tell the user the answer came from the web."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "max_results": {"type": "integer", "default": 5},
            },
            "required": ["query"],
        },
    },
}


def _client(ctx):
    if ctx.web_client is not None:
        return ctx.web_client
    from tavily import TavilyClient  # lazy import

    if not settings.tavily_api_key:
        raise RuntimeError("TAVILY_API_KEY is not configured")
    client = TavilyClient(api_key=settings.tavily_api_key)
    ctx.web_client = client
    return client


def run(args: dict, ctx) -> dict:
    query = args.get("query", "").strip()
    if not query:
        return {"status": "error", "message": "query is required"}
    client = _client(ctx)
    resp = client.search(
        query=query,
        max_results=int(args.get("max_results", 5)),
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
