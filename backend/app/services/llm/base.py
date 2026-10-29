"""backend/app/services/llm/base.py"""
"""Provider-neutral types shared by every LLM backend.

A client only has to expose `name`, `model`, `available`, `generate_json` and
`generate_text`; `LLMPolicy` decides which client sees which work.
"""
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


@dataclass
class LLMResult:
    text: str
    input_tokens: int
    output_tokens: int


@runtime_checkable
class LLMClient(Protocol):
    name: str
    model: str

    @property
    def available(self) -> bool: ...

    def generate_json(
        self, system: str, prompt: str, schema: Any, max_output_tokens: int = 1200
    ) -> LLMResult: ...

    def generate_text(
        self, system: str, prompt: str, max_output_tokens: int = 400
    ) -> LLMResult: ...
