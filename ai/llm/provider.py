"""Provider-agnostic wrapper around any OpenAI-compatible chat completions API
(Google Gemini, Groq, Cerebras, GitHub Models, OpenRouter, local servers, ...).

The provider is chosen purely through configuration (base_url + api_key +
model), so switching models/providers never requires code changes. The OpenAI
SDK is imported lazily so the module stays cheap to import. Transient failures
(rate limits, timeouts, upstream 5xx) are retried with exponential backoff.
"""
import logging
import time
from typing import Any

from ai.config import settings

# HTTP statuses worth retrying (transient rate-limit / server-side conditions).
_RETRY_STATUS = {408, 409, 429, 500, 502, 503, 504}
# OpenAI SDK exception class names that indicate a transient error.
_RETRY_EXC_NAMES = {
    "RateLimitError",
    "APITimeoutError",
    "APIConnectionError",
    "InternalServerError",
    "APIStatusError",
}

def _status_code(exc: Exception):
    # Best-effort extraction of an HTTP status code from an OpenAI SDK error.
    return getattr(exc, "status_code", None) or getattr(exc, "code", None)

def _is_retryable(exc: Exception) -> bool:
    # Retry on known transient SDK exception types or transient HTTP statuses.
    if type(exc).__name__ in _RETRY_EXC_NAMES:
        return True
    code = _status_code(exc)
    try:
        return int(code) in _RETRY_STATUS
    except (TypeError, ValueError):
        return False

class LLMProvider:
    # Lazily-built OpenAI-compatible client exposing a single chat() method.
    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
    ):
        # Inputs: model/api_key/base_url each override the configured default.
        self.model = model or settings.llm_model
        self._api_key = api_key or settings.llm_api_key
        self._base_url = base_url or settings.llm_base_url
        self._client = None

    def _ensure_client(self):
        # Build the OpenAI-compatible client on first use; raises if no key.
        if self._client is None:
            from openai import OpenAI  # lazy import

            if not self._api_key:
                raise RuntimeError(
                    "LLM API key is not configured (set LLM_API_KEY, "
                    "GEMINI_API_KEY or GROQ_API_KEY)"
                )
            self._client = OpenAI(api_key=self._api_key, base_url=self._base_url)
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
        # Retries transient failures with exponential backoff, then re-raises.
        client = self._ensure_client()
        kwargs: dict = {
            "model": self.model,
            "messages": messages,
            "temperature": settings.llm_temperature if temperature is None else temperature,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = tool_choice

        attempts = 1 + max(0, settings.llm_max_retries)
        for attempt in range(attempts):
            try:
                resp = client.chat.completions.create(**kwargs)
                logging.getLogger("ai.llm").info(
                    "LLM served by model=%s", getattr(resp, "model", "?")
                )
                return resp
            except Exception as exc:
                # On the last attempt, or for non-transient errors, re-raise.
                if attempt == attempts - 1 or not _is_retryable(exc):
                    raise
                time.sleep(settings.llm_retry_base_delay * (2 ** attempt))
