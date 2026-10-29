"""backend/app/services/llm/suggest.py"""
"""One batched AI call: a concrete, text-specific fix for each failing criterion."""
import json
import logging
import re

from pydantic import BaseModel

from app.core.errors import LLMError, RateLimitError
from app.schemas.framework import Criterion
from app.schemas.report import Usage
from app.schemas.verdict import Verdict
from app.services.llm.base import LLMClient
from app.services.llm.token_budget import trim_to_tokens
from app.services.report.priority import VALID_LEVELS

log = logging.getLogger(__name__)

SYSTEM = (
    "You are a concise writing coach for authors of scientific papers. "
    "You give one concrete, specific fix per checklist item and never invent facts."
)
_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.I)


class SuggestionSchema(BaseModel):
    """Structured-output schema sent to Gemini."""

    id: str
    suggestion: str
    effort: str


class LocalSuggestionResponse(BaseModel):
    """Same items, wrapped in one object for grammar-constrained local decoding."""

    results: list[SuggestionSchema]


def build_prompt(template: str, items: list[tuple[Verdict, Criterion, str]]) -> tuple[str, list[str]]:
    blocks: list[str] = []
    ids: list[str] = []
    for v, crit, excerpt in items:
        why = v.note or v.evidence or ""
        blocks.append(
            f"[{crit.id}] {crit.name}: {crit.hint}\n"
            f"Status: {v.status}. {why}\n"
            f"EXCERPT:\n{trim_to_tokens(excerpt, 300)}"
        )
        ids.append(crit.id)
    return template.format(items="\n\n".join(blocks), ids=", ".join(ids)), ids


def parse_suggestions(text: str, expected: set[str]) -> dict[str, tuple[str, str | None]]:
    """Lenient parse: bad items are skipped, because every criterion has a static fallback."""
    try:
        data = json.loads(_FENCE.sub("", (text or "").strip()))
    except json.JSONDecodeError:
        return {}
    if isinstance(data, dict):
        for key in ("results", "items", "suggestions"):
            if isinstance(data.get(key), list):
                data = data[key]
                break
    if not isinstance(data, list):
        return {}

    out: dict[str, tuple[str, str | None]] = {}
    for raw in data:
        if not isinstance(raw, dict):
            continue
        cid, sug = raw.get("id"), str(raw.get("suggestion") or "").strip()
        if cid not in expected or not sug:
            continue
        effort = str(raw.get("effort") or "").strip().lower()
        out[cid] = (sug[:400], effort if effort in VALID_LEVELS else None)
    return out


def suggest_fixes(
    client: LLMClient,
    template: str,
    items: list[tuple[Verdict, Criterion, str]],
    usage: Usage,
) -> dict[str, tuple[str, str | None]]:
    if not client.available or not items:
        return {}
    prompt, ids = build_prompt(template, items)
    provider = getattr(client, "name", "gemini")
    is_local = provider == "local"
    schema = LocalSuggestionResponse if is_local else list[SuggestionSchema]
    max_tokens = min(2500, 200 + 110 * len(ids))
    if is_local:
        max_tokens = min(1200, 80 + 90 * len(ids))
    try:
        res = client.generate_json(SYSTEM, prompt, schema, max_tokens)
    except RateLimitError:
        raise
    except LLMError as exc:
        log.warning("Suggestion call failed (%s): %s", provider, exc)
        return {}
    usage.add(res.input_tokens, res.output_tokens, provider)
    return parse_suggestions(res.text, set(ids))
