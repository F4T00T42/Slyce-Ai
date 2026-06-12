"""Offline unit tests for the provider-agnostic LLM wrapper.

These verify the retry/backoff behavior of `ai.llm.provider.LLMProvider`
WITHOUT importing the OpenAI SDK or making any network call: a fake client is
injected directly and the backoff delay is set to zero. They run in a plain
Python environment (only `pydantic` is needed transitively via ai.config).

Run:  python -m unittest discover -s tests -v
"""
import os
import sys
import unittest

# Make the project root importable when run from anywhere.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai.config import settings
from ai.llm.provider import LLMProvider

class RateLimitError(Exception):
    # Class name matches an entry in provider._RETRY_EXC_NAMES, so the provider
    # treats it as a transient (retryable) error.
    pass

class _FakeCompletions:
    def __init__(self, fail_times, exc):
        self._fail_times = fail_times
        self._exc = exc
        self.calls = 0

    def create(self, **kwargs):
        self.calls += 1
        if self.calls <= self._fail_times:
            raise self._exc
        return {"ok": True, "calls": self.calls}

class _FakeChat:
    def __init__(self, completions):
        self.completions = completions

class _FakeClient:
    # Mimics the shape the provider uses: client.chat.completions.create(...).
    def __init__(self, fail_times, exc):
        self.chat = _FakeChat(_FakeCompletions(fail_times, exc))

class RetryTests(unittest.TestCase):
    def setUp(self):
        # Neutralize backoff timing + fix the retry budget for fast, determin
        # istic tests; originals restored in tearDown.
        self._saved = (settings.llm_retry_base_delay, settings.llm_max_retries)
        settings.llm_retry_base_delay = 0.0
        settings.llm_max_retries = 3

    def tearDown(self):
        settings.llm_retry_base_delay, settings.llm_max_retries = self._saved

    def _provider_with(self, fake):
        p = LLMProvider(model="test-model", api_key="x", base_url="http://x")
        p._client = fake  # bypass _ensure_client (no OpenAI import / network)
        return p

    def test_retries_then_succeeds(self):
        # Fails twice, succeeds on the third attempt (within the budget).
        fake = _FakeClient(fail_times=2, exc=RateLimitError("429"))
        p = self._provider_with(fake)
        result = p.chat(messages=[{"role": "user", "content": "hi"}])
        self.assertEqual(result["ok"], True)
        self.assertEqual(fake.chat.completions.calls, 3)

    def test_gives_up_after_budget(self):
        # 1 initial + 3 retries = 4 attempts, all fail -> last exc re-raised.
        fake = _FakeClient(fail_times=99, exc=RateLimitError("429"))
        p = self._provider_with(fake)
        with self.assertRaises(RateLimitError):
            p.chat(messages=[{"role": "user", "content": "hi"}])
        self.assertEqual(fake.chat.completions.calls, 4)

    def test_non_retryable_raises_immediately(self):
        # An unknown, non-transient error is not retried (single attempt).
        class BadRequest(Exception):
            pass

        fake = _FakeClient(fail_times=99, exc=BadRequest("bad"))
        p = self._provider_with(fake)
        with self.assertRaises(BadRequest):
            p.chat(messages=[{"role": "user", "content": "hi"}])
        self.assertEqual(fake.chat.completions.calls, 1)

if __name__ == "__main__":
    unittest.main()
