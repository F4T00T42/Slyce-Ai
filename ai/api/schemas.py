"""Pydantic request/response models for the /chat endpoints."""
from typing import Optional

from pydantic import BaseModel, Field


class ProfileInput(BaseModel):
    # Optional per-request profile contract; any subset is accepted. Fields:
    # weight, height, age, gender, activity_level, goal, diet, allergies,
    # diet_preferences. Missing required fields trigger a clarifying question.
    weight: Optional[float] = None
    height: Optional[float] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    activity_level: Optional[str] = None
    goal: Optional[str] = None
    diet: Optional[str] = None
    allergies: Optional[list[str]] = None
    diet_preferences: Optional[list[str]] = None


class ChatRequest(BaseModel):
    # Fields: message (required), session_id?, user_id?, profile? (ProfileInput).
    message: str = Field(..., min_length=1)
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    profile: Optional[ProfileInput] = None


class RecommendRequest(BaseModel):
    # Body for POST /recommend. Fields: user_id? (preferred — loads the stored
    # profile), profile? (manual override for a friend/hypothetical), top_n (max
    # meals, default 10). Provide user_id and/or profile; profile overrides stored.
    user_id: Optional[str] = None
    profile: Optional[ProfileInput] = None
    top_n: int = 10


class ChatResponse(BaseModel):
    # Fields: reply, used_tools, citations, session_id.
    reply: str
    used_tools: list[str] = []
    citations: list[str] = []
    session_id: Optional[str] = None


class TranscriptMessage(BaseModel):
    # One stored transcript turn: role, content, created_at?, metadata?.
    role: str
    content: str
    created_at: Optional[str] = None
    metadata: Optional[dict] = None


class HistoryResponse(BaseModel):
    # Fields: session_id, messages (list of TranscriptMessage), count.
    session_id: str
    messages: list[TranscriptMessage] = []
    count: int = 0
