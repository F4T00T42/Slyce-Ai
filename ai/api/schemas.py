"""Request/response models for the /chat endpoint."""
from typing import Optional

from pydantic import BaseModel, Field


class ProfileInput(BaseModel):
    """Optional profile contract the backend may pass per request. Any subset
    is accepted; missing required fields trigger a clarifying question.
    """

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
    message: str = Field(..., min_length=1)
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    profile: Optional[ProfileInput] = None


class ChatResponse(BaseModel):
    reply: str
    used_tools: list[str] = []
    citations: list[str] = []
    session_id: Optional[str] = None


class TranscriptMessage(BaseModel):
    role: str
    content: str
    created_at: Optional[str] = None
    metadata: Optional[dict] = None


class HistoryResponse(BaseModel):
    session_id: str
    messages: list[TranscriptMessage] = []
    count: int = 0
