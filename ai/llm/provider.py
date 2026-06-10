"""Thin wrapper around the Groq chat completions API (OpenAI-compatible, tool
calling supported). The SDK is imported lazily so the module imports cheaply.
"""
from typing import Any

from ai.config import settings


class LLMProvider:
    # Lazily-built Groq client exposing a single chat() method.
    def __init__(self, model: str | None = None, api_key: str | None = None):
        # Inputs: model (override default model), api_key (override env key).
        self.model = model or settings.llm_model
        self._api_key = api_key or settings.groq_api_key
        self._client = None

    def _ensure_client(self):
        # Build the Groq client on first use; raises if the key is missing.
        if self._client is None:
            from groq import Groq  # lazy import

            if not self._api_key:
                raise RuntimeError("GROQ_API_KEY is not configured")
            self._client = Groq(api_key=self._api_key)
        return self._client

    def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        tool_choice: str = "auto",
        temperature: float | None = None,
    ) -> Any:
        # Inputs: messages (chat history), tools (tool schemas or None),
        # tool_choice ("auto"/"none"/etc.), temperature (override default).
        client = self._ensure_client()
        kwargs: dict = {
            "model": self.model,
            "messages": messages,
            "temperature": settings.llm_temperature if temperature is None else temperature,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = tool_choice
        return client.chat.completions.create(**kwargs)
