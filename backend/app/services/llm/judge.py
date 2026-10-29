"""backend/app/services/llm/judge.py"""
import logging
from dataclasses import dataclass

from pydantic import BaseModel

from app.core.config import Settings
from app.core.errors import LLMError, OutputValidationError, RateLimitError
from app.schemas.framework import Component
from app.schemas.report import Usage
from app.schemas.verdict import Verdict
from app.services.framework.compiler import compile_component
from app.services.orchestrator.merger import Pending
from app.services.validation.evidence_verifier import verify_evidence
from app.services.validation.output_validator import JudgeItem, parse_judge_output
from app.services.validation.repair import repair_once

from .base import LLMClient

log = logging.getLogger(__name__)

# Small components share one call to save the repeated role/format overhead.
JUDGE_GROUPS: list[list[str]] = [
    ["title", "abstract"],
    ["related_work"],
    ["introduction"],
    ["methods"],
    ["results"],
    ["discussion", "conclusion"],
    ["bibliography"],
]

EVIDENCE_MAX_WORDS = 15


class JudgeItemSchema(BaseModel):
    """Structured-output schema sent to Gemini."""

    id: str
    met: bool
    why: str
    evidence: str | None = None


class LocalJudgeItemSchema(BaseModel):
    """Local 4B models ramble in free-text fields and then truncate the JSON.

    Asking only for the verdict and the quote keeps output ~3x shorter and removes
    that failure mode. `parse_judge_output` already treats `why` as optional.
    """

    id: str
    met: bool
    evidence: str | None = None


class LocalJudgeResponse(BaseModel):
    """Top-level object: LM Studio's grammar backend is most reliable with one."""

    results: list[LocalJudgeItemSchema]


@dataclass
class GroupInput:
    component: Component
    pendings: list[Pending]
    text: str                      # the context the model sees (also used to verify quotes)


def build_prompt(template: str, items: list[GroupInput]) -> tuple[str, list[str]]:
    blocks: list[str] = []
    ids: list[str] = []
    for it in items:
        only = {p.criterion.id for p in it.pendings}
        blocks.append(compile_component(it.component, only) + "\nTEXT:\n" + it.text)
        ids.extend(c.id for c in it.component.criteria if c.id in only)
    return template.format(blocks="\n\n".join(blocks), ids=", ".join(ids)), ids


def _max_tokens(ids: list[str], is_local: bool) -> int:
    if is_local:
        return min(1200, 40 + 45 * len(ids))
    return min(2000, 150 + 90 * len(ids))


def _trim_quote(text: str | None) -> str | None:
    if not text:
        return None
    words = text.split()
    return " ".join(words[:EVIDENCE_MAX_WORDS]) if len(words) > EVIDENCE_MAX_WORDS else text


def judge_group(
    client: LLMClient,
    system: str,
    template: str,
    items: list[GroupInput],
    usage: Usage,
    settings: Settings,
) -> dict[str, Verdict]:
    """One call for a group of components. Returns verdicts by criterion id.

    Criteria missing from the result map get their fallback verdict from the caller.
    """
    provider = getattr(client, "name", "gemini")
    is_local = provider == "local"
    schema = LocalJudgeResponse if is_local else list[JudgeItemSchema]

    prompt, ids = build_prompt(template, items)
    expected = set(ids)
    max_tokens = _max_tokens(ids, is_local)

    try:
        res = client.generate_json(system, prompt, schema, max_tokens)
    except RateLimitError:
        raise
    except LLMError as exc:
        log.warning("Judge call failed (%s): %s", provider, exc)
        return {}
    usage.add(res.input_tokens, res.output_tokens, provider)

    try:
        parsed = parse_judge_output(res.text, expected)
    except OutputValidationError as exc:
        fixed = repair_once(client, system, prompt, res.text, str(exc), schema, max_tokens, usage)
        if fixed is None:
            return {}
        try:
            parsed = parse_judge_output(fixed, expected)
        except OutputValidationError as exc2:
            log.warning("Judge output invalid after repair (%s): %s", provider, exc2)
            return {}

    return _to_verdicts(parsed, items, provider)


def _to_verdicts(parsed: list[JudgeItem], items: list[GroupInput], provider: str) -> dict[str, Verdict]:
    by_id = {p.id: p for p in parsed}
    out: dict[str, Verdict] = {}
    for it in items:
        for pend in it.pendings:
            crit = pend.criterion
            item = by_id.get(crit.id)
            if item is None:
                continue

            quote = _trim_quote(item.evidence)
            verified = bool(quote) and verify_evidence(quote, it.text)
            evidence = quote if verified else None
            note = (item.why or "").strip()[:200] or None

            if bool(item.met):
                if evidence is None and crit.tier == "B":
                    # "met" without a quote that exists in the text is the hallucination case
                    status, conf = "needs_review", 0.4
                    note = "The AI judged this as met but gave no verifiable quote. Please check it yourself."
                else:
                    status, conf = "pass", (0.8 if evidence else 0.65)
            else:
                status, conf = "fail", 0.7

            if provider == "local" and note is None:
                note = "Judged by the local model."

            out[crit.id] = Verdict(
                id=crit.id,
                component=it.component.key,
                name=crit.name,
                tier=crit.tier,
                status=status,
                evidence=evidence,
                confidence=conf,
                source="llm",
                provider=provider,
                note=note,
            )
    return out
