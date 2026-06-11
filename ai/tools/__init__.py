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
_SCHEMAS_BY_NAME: dict[str, dict] = {m.SCHEMA["function"]["name"]: m.SCHEMA for m in _MODULES}


def _coerce_scalar(value: Any, prop_schema: dict) -> Any:
    # Groq/Llama tool calls frequently emit numbers (and booleans) as JSON
    # strings, e.g. {"limit": "10"}. Convert such strings to the schema-declared
    # type so tools and the DB receive real numbers. Unparseable values are left
    # as-is (the tool will surface a clean error). Recurses into nested objects.
    if not isinstance(prop_schema, dict):
        return value
    types = prop_schema.get("type")
    types = types if isinstance(types, list) else [types]
    if isinstance(value, str):
        s = value.strip()
        if s == "":
            return value
        if "integer" in types:
            try:
                return int(float(s))
            except (TypeError, ValueError):
                return value
        if "number" in types:
            try:
                return float(s)
            except (TypeError, ValueError):
                return value
        if "boolean" in types:
            low = s.lower()
            if low in ("true", "false"):
                return low == "true"
    if "object" in types and isinstance(value, dict):
        return _coerce_args(value, prop_schema.get("properties") or {})
    return value


def _coerce_args(args: dict, properties: dict) -> dict:
    # Coerce each known property of `args` to its declared schema type (recursing
    # into nested object schemas such as `profile`). Unknown keys pass through.
    if not isinstance(args, dict) or not properties:
        return args
    return {
        key: (_coerce_scalar(val, properties[key]) if key in properties else val)
        for key, val in args.items()
    }


def execute(name: str, args: dict, ctx: ToolContext) -> dict:
    # Inputs: name (tool name), args (tool arguments), ctx (ToolContext).
    # Coerces string-encoded numbers/booleans to their declared types, then
    # dispatches to the tool; returns {error} for unknown tools or exceptions.
    fn = TOOL_FUNCTIONS.get(name)
    if fn is None:
        return {"error": f"Unknown tool: {name}"}
    properties = (
        _SCHEMAS_BY_NAME.get(name, {})
        .get("function", {})
        .get("parameters", {})
        .get("properties", {})
    )
    try:
        return fn(_coerce_args(args or {}, properties), ctx)
    except Exception as exc:  # surface a clean error to the LLM
        return {"error": f"{type(exc).__name__}: {exc}"}
