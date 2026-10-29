"""backend/tests/test_local_client.py"""
import httpx
import pytest

from app.core.errors import LLMError, RateLimitError
from app.services.llm.gemini_client import LLMResult as GeminiLLMResult
from app.services.llm.judge import LocalJudgeResponse
from app.services.llm.local_client import LocalClient, to_json_schema


def _client(handler) -> LocalClient:
    client = LocalClient("http://local/v1", "qwen/qwen3-4b-2507", "secret")
    client._client = httpx.Client(transport=httpx.MockTransport(handler))
    return client


def _ok(payload: dict) -> httpx.Response:
    return httpx.Response(200, json=payload)


def test_schema_is_strict_and_nullable_evidence():
    schema = to_json_schema(LocalJudgeResponse)

    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False
    assert schema["required"] == ["results"]

    item = schema["properties"]["results"]["items"]
    assert item["additionalProperties"] is False
    assert set(item["required"]) == {"id", "met", "evidence"}
    assert item["properties"]["evidence"]["type"] == ["string", "null"]
    assert item["properties"]["met"]["type"] == "boolean"


def test_generate_json_maps_usage_and_sends_strict_response_format():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = __import__("json").loads(request.content)
        seen["auth"] = request.headers.get("authorization")
        return _ok(
            {
                "choices": [{"message": {"content": '{"results": []}'}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 321, "completion_tokens": 45},
            }
        )

    result = _client(handler).generate_json("sys", "prompt", LocalJudgeResponse, 300)

    assert isinstance(result, GeminiLLMResult)          # same type as the Gemini client
    assert (result.input_tokens, result.output_tokens) == (321, 45)
    assert seen["auth"] == "Bearer secret"
    assert seen["body"]["max_tokens"] == 300
    assert seen["body"]["temperature"] == 0
    fmt = seen["body"]["response_format"]
    assert fmt["type"] == "json_schema" and fmt["json_schema"]["strict"] is True


def test_bad_api_key_is_reported_clearly():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "invalid_api_key"})

    with pytest.raises(LLMError, match="API key"):
        _client(handler).generate_json("sys", "prompt", LocalJudgeResponse)


def test_unknown_model_is_reported_clearly():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": "model_not_found"})

    with pytest.raises(LLMError, match="not served"):
        _client(handler).generate_json("sys", "prompt", LocalJudgeResponse)


def test_429_raises_rate_limit_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": "busy"})

    with pytest.raises(RateLimitError):
        _client(handler).generate_json("sys", "prompt", LocalJudgeResponse)


def test_disabled_client_is_unavailable():
    client = LocalClient("http://local/v1", "qwen/qwen3-4b-2507", enabled=False)

    assert client.available is False
    with pytest.raises(LLMError):
        client.generate_text("sys", "prompt")
