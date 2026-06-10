"""Tool registry. Each tool module exposes:
  - SCHEMA: a Groq/OpenAI function-tool JSON schema dict
  - run(args, ctx) -> dict
ctx is a ToolContext carrying repos, retriever, web client, and resolved profile.
"""
from dataclasses import dataclass, field
from typing import Any, Callable

from . import (
    recommendation_engine,
    meal_planner,
    meal_search,
    restaurant_search,
    nutrition_knowledge,
    allergy_assistant,
    web_search,
)

_MODULES = [
    recommendation_engine,
    meal_planner,
    meal_search,
    restaurant_search,
    nutrition_knowledge,
    allergy_assistant,
    web_search,
]


@dataclass
class ToolContext:
    # Per-request bundle passed to every tool. Fields: engine, the repositories,
    # retriever, web_client, recommender, resolved profile, explicit_profile,
    # user_id, and citations (accumulated source list).
    engine: Any = None
    meal_repo: Any = None
    ingredient_repo: Any = None
    restaurant_repo: Any = None
    customer_repo: Any = None
    reference_repo: Any = None
    retriever: Any = None
    web_client: Any = None
    recommender: Any = None
    profile: Any = None  # resolved UserProfile or None
    explicit_profile: dict | None = None
    user_id: str | None = None
    citations: list = field(default_factory=list)


TOOL_SCHEMAS: list[dict] = [m.SCHEMA for m in _MODULES]
TOOL_FUNCTIONS: dict[str, Callable] = {m.SCHEMA["function"]["name"]: m.run for m in _MODULES}


def execute(name: str, args: dict, ctx: ToolContext) -> dict:
    # Inputs: name (tool name), args (tool arguments), ctx (ToolContext).
    # Dispatches to the tool; returns {error} for unknown tools or exceptions.
    fn = TOOL_FUNCTIONS.get(name)
    if fn is None:
        return {"error": f"Unknown tool: {name}"}
    try:
        return fn(args or {}, ctx)
    except Exception as exc:  # surface a clean error to the LLM
        return {"error": f"{type(exc).__name__}: {exc}"}
