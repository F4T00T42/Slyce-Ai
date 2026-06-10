"""FastAPI router for the chat endpoints; wires repositories + orchestrator.

Shared resources (DB engine, recommender, retriever, session store) are built
once. The app DB engine is read-only; the retriever uses Qdrant and the session
store uses its own separate datastore.

Endpoints:
  POST   /chat                      -> send a message, get a reply
  GET    /chat/history/{session_id} -> full transcript for display
  DELETE /chat/history/{session_id} -> clear a conversation
"""
from fastapi import APIRouter, Depends, Query, HTTPException

from ai.config import settings
from ai.api.schemas import (
    ChatRequest,
    ChatResponse,
    HistoryResponse,
    TranscriptMessage,
)
from ai.llm.provider import LLMProvider
from ai.orchestrator import Orchestrator
from ai.sessions.store import build_session_store
from ai.tools import ToolContext
from ai.profile_context import resolve_profile

router = APIRouter(tags=["chat"])

# Process-wide shared resources, populated by init_chat().
_state: dict = {}


def init_chat(engine, recommender) -> None:
    # Inputs: engine (shared read-only SQLAlchemy engine), recommender
    # (MealRecommender). Builds repos, session store, LLM, retriever, orchestrator.
    from db.meal_repository import MealRepository
    from db.ingredient_repository import IngredientRepository
    from db.restaurant_repository import RestaurantRepository
    from db.customer_repository import CustomerRepository
    from db.reference_repository import ReferenceRepository

    _state["engine"] = engine
    _state["recommender"] = recommender
    _state["meal_repo"] = MealRepository(engine)
    _state["ingredient_repo"] = IngredientRepository(engine)
    _state["restaurant_repo"] = RestaurantRepository(engine)
    _state["customer_repo"] = CustomerRepository(engine)
    _state["reference_repo"] = ReferenceRepository(engine)
    # Durable, separate conversation store (SQLite by default, or Postgres).
    _state["sessions"] = build_session_store()
    _state["llm"] = LLMProvider()

    # Retriever is optional: enabled only if RAG deps/collection are reachable.
    retriever = None
    try:
        from ai.rag.retriever import Retriever

        retriever = Retriever()
    except Exception:
        retriever = None
    _state["retriever"] = retriever
    _state["orchestrator"] = Orchestrator(_state["llm"], None)


def _get_state() -> dict:
    # Dependency that returns shared state or errors if init_chat() wasn't run.
    if not _state:
        raise RuntimeError("Chat not initialized; call init_chat() at startup.")
    return _state


@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest, state: dict = Depends(_get_state)) -> ChatResponse:
    # Inputs: req (ChatRequest: message, session_id?, user_id?, profile?),
    # state (shared resources). Resolves profile, runs orchestrator, persists turn.
    explicit = req.profile.model_dump(exclude_none=True) if req.profile else None
    try:
        profile, _missing = resolve_profile(explicit, req.user_id, state["customer_repo"])
    except Exception:
        # Don't fail the whole chat on a transient profile-load error: continue
        # without a stored profile so the assistant can still answer or ask for stats.
        profile = None

    ctx = ToolContext(
        engine=state["engine"],
        meal_repo=state["meal_repo"],
        ingredient_repo=state["ingredient_repo"],
        restaurant_repo=state["restaurant_repo"],
        customer_repo=state["customer_repo"],
        reference_repo=state["reference_repo"],
        retriever=state["retriever"],
        recommender=state["recommender"],
        profile=profile,
        explicit_profile=explicit,
        user_id=req.user_id,
    )

    # Feed only the recent window to the LLM; the full transcript is retained.
    history = state["sessions"].get_context(req.session_id, settings.context_turns)
    try:
        result = state["orchestrator"].handle(req.message, ctx, history=history)
    except Exception:
        raise HTTPException(
            status_code=503,
            detail={
                "status": "assistant_unavailable",
                "message": "The assistant is temporarily unavailable. Please retry.",
            },
    )

    state["sessions"].append(
        req.session_id,
        req.message,
        result["reply"],
        metadata={
            "used_tools": result.get("used_tools", []),
            "citations": result.get("citations", []),
        },
    )

    return ChatResponse(
        reply=result["reply"],
        used_tools=result["used_tools"],
        citations=result["citations"],
        session_id=req.session_id,
    )


@router.get("/chat/history/{session_id}", response_model=HistoryResponse)
def get_history(
    session_id: str,
    limit: int | None = Query(default=None, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    state: dict = Depends(_get_state),
) -> HistoryResponse:
    # Inputs: session_id, limit (page size; None = all), offset (start index),
    # state. Returns the full stored transcript (oldest first) for display.
    rows = state["sessions"].get_transcript(session_id, limit=limit, offset=offset)
    return HistoryResponse(
        session_id=session_id,
        messages=[TranscriptMessage(**r) for r in rows],
        count=len(rows),
    )


@router.delete("/chat/history/{session_id}")
def delete_history(session_id: str, state: dict = Depends(_get_state)) -> dict:
    # Inputs: session_id, state. Clears the conversation ('New chat'/'Delete').
    state["sessions"].reset(session_id)
    return {"status": "deleted", "session_id": session_id}
