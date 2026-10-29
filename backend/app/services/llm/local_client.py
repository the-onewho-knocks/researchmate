"""backend/app/services/llm/local_client.py"""
"""Local OpenAI-compatible client (LM Studio / Ollama / vLLM).

Qwen has no Gemini-style `response_schema`, so we send a strict JSON Schema via
`response_format`. LM Studio compiles it into a grammar, which makes malformed
JSON (and runaway prose) far less likely than a prompt-only request.
"""
import logging
import time
import typing

import httpx
from pydantic import BaseModel

from app.core.errors import LLMError, RateLimitError

from .base import LLMResult

log = logging.getLogger(__name__)

# Cached health probe: `available` is read on every pipeline step.
_PROBE_TTL_S = 30.0


def _resolve_refs(node, defs: dict):
    if isinstance(node, dict):
        ref = node.get("$ref")
        if isinstance(ref, str):
            return _resolve_refs(defs.get(ref.split("/")[-1], {}), defs)
        return {k: _resolve_refs(v, defs) for k, v in node.items() if k != "$defs"}
    if isinstance(node, list):
        return [_resolve_refs(v, defs) for v in node]
    return node


def _normalize(node: dict) -> dict:
    """Turn pydantic's JSON Schema into the strict subset grammar backends accept."""
    # Optional fields arrive as anyOf[X, null]; encode that as type: [X, "null"].
    if "anyOf" in node:
        options = node["anyOf"]
        non_null = [o for o in options if o.get("type") != "null"]
        if len(non_null) == 1:
            inner = _normalize(non_null[0])
            if len(non_null) != len(options) and isinstance(inner.get("type"), str):
                inner["type"] = [inner["type"], "null"]
            return inner

    out = {k: v for k, v in node.items() if k not in ("title", "default")}
    if "properties" in out:
        out["properties"] = {k: _normalize(v) for k, v in out["properties"].items()}
        out["additionalProperties"] = False
        out["required"] = list(out["properties"])       # strict mode wants every key
    if "items" in out:
        out["items"] = _normalize(out["items"])
    return out


def to_json_schema(schema) -> dict:
    """Accept a pydantic model, `list[Model]`, or a ready-made schema dict."""
    origin = typing.get_origin(schema)
    if origin is list:
        (inner,) = typing.get_args(schema)
        return {"type": "array", "items": to_json_schema(inner)}
    if isinstance(schema, type) and issubclass(schema, BaseModel):
        raw = schema.model_json_schema()
        return _normalize(_resolve_refs(raw, raw.get("$defs", {})))
    if isinstance(schema, dict):
        return _normalize(_resolve_refs(schema, schema.get("$defs", {})))
    raise TypeError(f"Unsupported schema type: {schema!r}")


class LocalClient:
    """Qwen served by LM Studio (or any OpenAI-compatible endpoint)."""

    name = "local"

    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str = "",
        timeout_s: int = 120,
        retries: int = 2,
        enabled: bool = True,
    ):
        self.base_url = (base_url or "").rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout_s = timeout_s
        self.retries = retries
        self.enabled = enabled
        self._client: httpx.Client | None = None
        self._probe: tuple[float, bool] | None = None

    @property
    def available(self) -> bool:
        if not self.enabled or not self.base_url:
            return False
        now = time.time()
        if self._probe is not None and now - self._probe[0] < _PROBE_TTL_S:
            return self._probe[1]
        ok = self._check()
        self._probe = (now, ok)
        return ok

    def _check(self) -> bool:
        try:
            resp = httpx.get(f"{self.base_url}/models", headers=self._headers(), timeout=2.0)
            return resp.status_code == 200
        except Exception:
            return False

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _get_client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(timeout=self.timeout_s)
        return self._client

    def _post(self, body: dict) -> LLMResult:
        if not self.enabled or not self.base_url:
            raise LLMError("The local LLM is not configured.")

        last: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                resp = self._get_client().post(
                    f"{self.base_url}/chat/completions", json=body, headers=self._headers()
                )
                if resp.status_code == 401:
                    raise LLMError("LM Studio rejected the API key (check LOCAL_LLM_API_KEY).")
                if resp.status_code == 404:
                    raise LLMError(
                        f"Local model '{self.model}' is not served at {self.base_url} "
                        "(check LOCAL_LLM_MODEL)."
                    )
                if resp.status_code == 429:
                    raise RateLimitError("The local LLM is busy.")
                resp.raise_for_status()
                data = resp.json()
                choice = (data.get("choices") or [{}])[0]
                usage = data.get("usage") or {}
                return LLMResult(
                    (choice.get("message") or {}).get("content") or "",
                    int(usage.get("prompt_tokens", 0) or 0),
                    int(usage.get("completion_tokens", 0) or 0),
                )
            except (LLMError, RateLimitError):
                raise
            except Exception as exc:
                last = exc
                log.warning("Local LLM call failed (attempt %d/%d): %s", attempt + 1, self.retries + 1, exc)
                if attempt < self.retries:
                    time.sleep(2**attempt)
        raise LLMError(f"Local LLM call failed: {last}")

    def generate_json(
        self, system: str, prompt: str, schema, max_output_tokens: int = 1200
    ) -> LLMResult:
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0,
            "top_p": 0.8,
            "seed": 0,
            "max_tokens": max_output_tokens,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "response",
                    "strict": True,
                    "schema": to_json_schema(schema),
                },
            },
        }
        return self._post(body)

    def generate_text(self, system: str, prompt: str, max_output_tokens: int = 400) -> LLMResult:
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0,
            "top_p": 0.8,
            "seed": 0,
            "max_tokens": max_output_tokens,
        }
        return self._post(body)
