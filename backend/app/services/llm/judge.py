"""backend/app/services/llm/judge.py"""
import logging
from dataclasses import dataclass

from pydantic import BaseModel

from app.core.config import Settings
from app.core.errors import LLMError, OutputValidationError
from app.schemas.framework import Component
from app.schemas.report import Usage
from app.schemas.verdict import Verdict
from app.services.framework.compiler import compile_component
from app.services.orchestrator.merger import Pending
from app.services.validation.evidence_verifier import verify_evidence
from app.services.validation.output_validator import JudgeItem, parse_judge_output
from app.services.validation.repair import repair_once

from .gemini_client import GeminiClient

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


class JudgeItemSchema(BaseModel):
    """Structured-output schema sent to Gemini."""

    id: str
    met: bool
    why: str
    evidence: str | None = None


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


def judge_group(
    client: GeminiClient,
    system: str,
    template: str,
    items: list[GroupInput],
    usage: Usage,
    settings: Settings,
) -> dict[str, Verdict]:
    """One Gemini call for a group of components. Returns verdicts by criterion id.

    Criteria missing from the result map get their fallback verdict from the caller.
    """
    prompt, ids = build_prompt(template, items)
    expected = set(ids)
    max_tokens = min(2000, 150 + 90 * len(ids))

    try:
        res = client.generate_json(system, prompt, list[JudgeItemSchema], max_tokens)
    except LLMError as exc:
        log.warning("Judge call failed: %s", exc)
        return {}
    usage.add(res.input_tokens, res.output_tokens)

    try:
        parsed = parse_judge_output(res.text, expected)
    except OutputValidationError as exc:
        fixed = repair_once(client, system, prompt, res.text, str(exc), list[JudgeItemSchema], max_tokens, usage)
        if fixed is None:
            return {}
        try:
            parsed = parse_judge_output(fixed, expected)
        except OutputValidationError as exc2:
            log.warning("Judge output invalid after repair: %s", exc2)
            return {}

    return _to_verdicts(parsed, items)


def _to_verdicts(parsed: list[JudgeItem], items: list[GroupInput]) -> dict[str, Verdict]:
    by_id = {p.id: p for p in parsed}
    out: dict[str, Verdict] = {}
    for it in items:
        for pend in it.pendings:
            crit = pend.criterion
            item = by_id.get(crit.id)
            if item is None:
                continue

            verified = bool(item.evidence) and verify_evidence(item.evidence, it.text)
            evidence = item.evidence if verified else None
            note = (item.why or "").strip()[:200] or None

            if item.met:
                if evidence is None and crit.tier == "B":
                    # "met" without a quote that exists in the text is the hallucination case
                    status, conf = "needs_review", 0.4
                    note = "The AI judged this as met but gave no verifiable quote. Please check it yourself."
                else:
                    status, conf = "pass", (0.8 if evidence else 0.65)
            else:
                status, conf = "fail", 0.7

            out[crit.id] = Verdict(
                id=crit.id,
                component=it.component.key,
                name=crit.name,
                tier=crit.tier,
                status=status,
                evidence=evidence,
                confidence=conf,
                source="llm",
                note=note,
            )
    return out
