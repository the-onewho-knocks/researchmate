"""backend/app/services/orchestrator/pipeline.py"""
"""Plain-code pipeline: extract -> sections -> route each criterion -> escalate -> merge.

No agent loop: cost and behaviour are predictable.
"""
import logging
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from app.core.config import Settings
from app.core.logging import log_usage
from app.schemas.framework import Component, Criterion, Framework
from app.schemas.report import ComponentResult, EvaluationReport, Usage
from app.schemas.verdict import Verdict
from app.services.cache.result_cache import ResultCache
from app.services.extraction.factory import get_extractor
from app.services.extraction.normalizer import normalize
from app.services.llm.coach import write_feedback
from app.services.llm.gemini_client import GeminiClient
from app.services.llm.judge import JUDGE_GROUPS, GroupInput, judge_group
from app.services.ml.router import route
from app.services.ml.section_classifier import SectionClassifier
from app.services.ml.sentence_roles import SentenceRoleModel
from app.services.rules.engine import run_rule
from app.services.rules.primitives import EvalContext, RuleResult, short, split_sentences
from app.services.scoring.scoring import score_component, score_overall
from app.services.sections.identifier import identify_sections
from app.services.upload.storage import UploadStorage

from .context_selector import select_context
from .merger import Pending, merge_verdicts

log = logging.getLogger(__name__)


@dataclass
class Services:
    settings: Settings
    framework: Framework
    llm: GeminiClient
    roles: SentenceRoleModel
    section_clf: SectionClassifier
    storage: UploadStorage
    cache: ResultCache
    system_prompt: str
    judge_template: str
    coach_template: str


def _v(
    crit: Criterion,
    comp: Component,
    status: str,
    evidence: str | None = None,
    conf: float = 0.0,
    source: str = "rule",
    note: str | None = None,
) -> Verdict:
    return Verdict(
        id=crit.id,
        component=comp.key,
        name=crit.name,
        tier=crit.tier,
        status=status,
        evidence=evidence,
        confidence=round(conf, 3),
        source=source,
        note=note,
    )


def _from_rule(crit: Criterion, comp: Component, r: RuleResult) -> Verdict:
    return _v(crit, comp, r.status, r.evidence, r.confidence, "rule", r.note)


def _missing_section(crit: Criterion, comp: Component, ctx: EvalContext) -> Verdict:
    return _v(crit, comp, "needs_review", note=f"Section '{ctx.section_key}' was not detected.")


def _decide(
    crit: Criterion, comp: Component, ctx: EvalContext, svc: Services
) -> tuple[Verdict | None, Pending | None]:
    """Return (final verdict, None) or (None, Pending) when the LLM is needed."""
    s = svc.settings

    if crit.tier == "A":
        r = run_rule(crit, ctx)
        if r is None:
            return _v(crit, comp, "needs_review", note="No rule defined for this criterion."), None
        return _from_rule(crit, comp, r), None

    labels = [ctx.section_key, *crit.params.get("also", [])]
    text = ctx.text_multi(labels)

    if crit.tier == "C":
        if not text:
            return _missing_section(crit, comp, ctx), None
        fallback = _v(crit, comp, "needs_review", note=f"Needs your judgment: {crit.hint}")
        return None, Pending(crit, comp.key, fallback)

    # ---- Tier B: ML first (if available), then rules, then escalate
    if not text and crit.rule not in ("limitations_stated", "open_issues_stated"):
        return _missing_section(crit, comp, ctx), None

    if crit.ml_label and svc.roles.available and text:
        sents = split_sentences(text)
        probs = svc.roles.score(crit.ml_label, sents)
        if probs:
            best = max(range(len(probs)), key=probs.__getitem__)
            p = probs[best]
            decision = route(p, s.ml_accept_t, s.ml_reject_t, svc.roles.is_calibrated(crit.ml_label))
            if decision == "accept":
                return _v(crit, comp, "pass", short(sents[best]), p, "ml"), None
            if decision == "reject":
                return _v(crit, comp, "fail", None, 1 - p, "ml", "The classifier found no matching sentence."), None
            # uncertain: fall through to the rules

    r = run_rule(crit, ctx)
    if r is None:
        fallback = _v(crit, comp, "needs_review", note=f"Please check: {crit.hint}")
        return None, Pending(crit, comp.key, fallback)
    if r.status in ("pass", "needs_review"):
        return _from_rule(crit, comp, r), None

    # rule found no cue: cue lists miss paraphrases, so ask the LLM before calling it a fail
    fallback = _v(
        crit, comp, "needs_review",
        note=f"No cue phrase found automatically. Please check: {crit.hint}",
    )
    return None, Pending(crit, comp.key, fallback)


def _escalate(
    svc: Services,
    ctx: EvalContext,
    comp_by_key: dict[str, Component],
    pending: dict[str, list[Pending]],
    usage: Usage,
) -> dict[str, Verdict]:
    out: dict[str, Verdict] = {}
    for plist in pending.values():
        for p in plist:
            out[p.criterion.id] = p.fallback          # default if the LLM cannot answer
    if not out or not svc.llm.available:
        return out

    for group in JUDGE_GROUPS:
        items: list[GroupInput] = []
        for key in group:
            plist = pending.get(key)
            if not plist:
                continue
            comp = comp_by_key[key]
            labels: list[str] = []
            for p in plist:
                for lab in [p.criterion.params.get("section", comp.section), *p.criterion.params.get("also", [])]:
                    if lab not in labels:
                        labels.append(lab)
            text = ctx.text_multi(labels)
            if not text:
                continue
            context = select_context(
                text, [p.criterion for p in plist], svc.roles.embedder,
                max_chars=svc.settings.context_max_chars,
            )
            items.append(GroupInput(comp, plist, context))
        if items:
            out.update(
                judge_group(svc.llm, svc.system_prompt, svc.judge_template, items, usage, svc.settings)
            )
    return out


def evaluate_file(
    path: Path,
    file_type: str,
    svc: Services,
    *,
    coach: bool = False,
    document_id: str = "",
) -> EvaluationReport:
    s = svc.settings
    fw = svc.framework

    doc = normalize(get_extractor(file_type, s.max_pages).extract(path))
    smap = identify_sections(doc, svc.section_clf)
    ctx = EvalContext(doc, smap)
    usage = Usage(model=svc.llm.model if svc.llm.available else "")
    comp_by_key = {c.key: c for c in fw.components}

    decided: dict[str, Verdict] = {}
    pending: dict[str, list[Pending]] = {}
    for comp in fw.components:
        for crit in comp.criteria:
            ctx.section_key = crit.params.get("section", comp.section)
            verdict, pend = _decide(crit, comp, ctx, svc)
            if verdict:
                decided[crit.id] = verdict
            if pend:
                pending.setdefault(comp.key, []).append(pend)

    escalated = _escalate(svc, ctx, comp_by_key, pending, usage)
    verdicts = merge_verdicts(decided, escalated)

    results: list[ComponentResult] = []
    for comp in fw.components:
        vs: list[Verdict] = []
        for crit in comp.criteria:
            vs.append(
                verdicts.get(crit.id)
                or _v(crit, comp, "could_not_assess", note="No verdict was produced.")
            )
        score, coverage = score_component(vs)
        results.append(
            ComponentResult(
                key=comp.key, name=comp.name, acronym=comp.acronym,
                score=score, coverage=coverage, verdicts=vs,
            )
        )
    overall, overall_cov = score_overall(results)

    all_verdicts = [v for r in results for v in r.verdicts]
    counts = Counter(v.source for v in all_verdicts if v.status in ("pass", "fail"))
    source_counts = {
        "rule": counts.get("rule", 0),
        "ml": counts.get("ml", 0),
        "llm": counts.get("llm", 0),
        "unresolved": sum(1 for v in all_verdicts if v.status not in ("pass", "fail")),
    }

    limitations = [
        "Figures are not analysed; only captions and in-text references are checked.",
        "This checks writing quality against the checklist, not the scientific validity of the work.",
    ]
    if not svc.llm.available:
        limitations.append("The AI judge is not configured, so judgment criteria are marked 'needs review'.")
    if smap.low_confidence:
        limitations.append("Section structure was hard to detect; results may be unreliable.")
    if doc.meta.get("bib_external"):
        limitations.append("The bibliography (.bib) was not uploaded, so reference checks were skipped.")
    if file_type == "docx":
        limitations.append("Word files rely on heading styles for structure and have no reliable page count.")
    limitations.extend(smap.notes)

    feedback = write_feedback(svc.llm, svc.coach_template, all_verdicts, usage) if coach else None

    log_usage(
        s.data_dir,
        {
            "document_id": document_id,
            "file_type": file_type,
            "model": usage.model,
            "llm_calls": usage.calls,
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
            **{f"n_{k}": v for k, v in source_counts.items()},
        },
    )

    return EvaluationReport(
        document_id=document_id,
        file_type=file_type,
        framework_version=fw.version,
        overall_score=overall,
        coverage=overall_cov,
        components=results,
        limitations=limitations,
        sections_detected=sorted(smap.spans),
        source_counts=source_counts,
        usage=usage,
        coach_feedback=feedback,
    )