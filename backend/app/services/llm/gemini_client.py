"""backend/app/services/llm/gemini_client.py"""
"""Gemini provider. Swap the model here and nowhere else."""
import logging
import time

from app.core.errors import LLMError, RateLimitError

from .base import LLMResult

log = logging.getLogger(__name__)

__all__ = ["GeminiClient", "LLMResult"]


def _is_rate_limit(exc: Exception) -> bool:
    code = getattr(exc, "code", None)
    if code == 429 or getattr(exc, "status_code", None) == 429:
        return True
    return "429" in str(exc) or "RESOURCE_EXHAUSTED" in str(exc)


class GeminiClient:
    name = "gemini"

    def __init__(
        self,
        api_key: str,
        model: str,
        timeout_s: int = 60,
        thinking_budget: int | None = 0,
        retries: int = 3,
    ):
        self.api_key = api_key
        self.model = model
        self.timeout_s = timeout_s
        self.thinking_budget = thinking_budget
        self.retries = retries
        self._client = None

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def _get_client(self):
        if self._client is None:
            from google import genai
            from google.genai import types

            self._client = genai.Client(
                api_key=self.api_key,
                http_options=types.HttpOptions(timeout=self.timeout_s * 1000),
            )
        return self._client

    def _call(self, system: str, prompt: str, max_output_tokens: int, schema=None) -> LLMResult:
        if not self.available:
            raise LLMError("GEMINI_API_KEY is not configured.")
        from google.genai import types

        cfg: dict = {
            "system_instruction": system,
            "temperature": 0,
            "max_output_tokens": max_output_tokens,
        }
        if schema is not None:
            cfg["response_mime_type"] = "application/json"
            cfg["response_schema"] = schema
        # Thinking tokens are billed as output. Only 2.5-family models take a budget this way;
        # check the current docs for other model families.
        if self.thinking_budget is not None and "2.5" in self.model:
            cfg["thinking_config"] = types.ThinkingConfig(thinking_budget=self.thinking_budget)

        last: Exception | None = None
        for attempt in range(self.retries):
            try:
                resp = self._get_client().models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config=types.GenerateContentConfig(**cfg),
                )
                usage = getattr(resp, "usage_metadata", None)
                n_in = int(getattr(usage, "prompt_token_count", 0) or 0)
                n_out = int(getattr(usage, "candidates_token_count", 0) or 0)
                n_out += int(getattr(usage, "thoughts_token_count", 0) or 0)
                return LLMResult(resp.text or "", n_in, n_out)
            except Exception as exc:
                last = exc
                if _is_rate_limit(exc):
                    # Retrying immediately only burns more quota; let the policy fall back.
                    log.warning("Gemini rate limit hit: %s", exc)
                    raise RateLimitError(f"Gemini rate limit: {exc}") from exc
                log.warning("Gemini call failed (attempt %d/%d): %s", attempt + 1, self.retries, exc)
                if attempt < self.retries - 1:
                    time.sleep(2**attempt)
        raise LLMError(f"Gemini call failed: {last}")

    def generate_json(self, system: str, prompt: str, schema, max_output_tokens: int = 1200) -> LLMResult:
        return self._call(system, prompt, max_output_tokens, schema=schema)

    def generate_text(self, system: str, prompt: str, max_output_tokens: int = 400) -> LLMResult:
        return self._call(system, prompt, max_output_tokens, schema=None)
