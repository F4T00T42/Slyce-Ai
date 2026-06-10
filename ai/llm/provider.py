"""Thin wrapper around the Groq chat completions API (OpenAI-compatible,
supports tool calling). The SDK is imported lazily so the module can be
imported without the dependency installed.
"""
from typing import Any

from ai.config import settings


class LLMProvider:
    def __init__(self, model: str | None = None, api_key: str | None = None):
        self.model = model or settings.llm_model
        self._api_key = api_key or settings.groq_api_key
        self._client = None

    def _ensure_client(self):
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
