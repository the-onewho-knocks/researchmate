"""backend/app/services/report/priority.py"""
"""Rank open criteria by impact versus effort. Pure code, no LLM needed."""
from app.schemas.framework import Criterion
from app.schemas.report import ComponentResult, Level, TodoItem

# How much work a fix usually is, by the rule that produced the verdict.
_EFFORT_BY_RULE: dict[str, Level] = {
    "title_compact": "low",
    "word_count_between": "low",
    "abstract_self_contained": "low",
    "abstract_results_summary": "low",
    "any_pattern": "low",
    "no_pattern": "low",
    "intro_novelty_statement": "low",
    "conclusion_item": "low",
    "limitations_stated": "low",
    "open_issues_stated": "low",
    "contrast_with_own_work": "medium",
    "methods_reproducibility_cues": "medium",
    "has_captions": "medium",
    "citations_match_refs": "medium",
    "results_visual_support": "high",
    "recent_ref_share": "high",
    "venue_or_doi_share": "high",
}

# How much a component matters for a reader's first impression.
_IMPACT_BY_COMPONENT: dict[str, Level] = {
    "title": "high",
    "abstract": "high",
    "introduction": "high",
    "related_work": "medium",
    "methods": "medium",
    "results": "medium",
    "discussion": "medium",
    "conclusion": "medium",
    "bibliography": "low",
}

_NUM = {"low": 1, "medium": 2, "high": 3}
VALID_LEVELS = set(_NUM)


def effort_for(crit: Criterion) -> Level:
    if crit.rule and crit.rule in _EFFORT_BY_RULE:
        return _EFFORT_BY_RULE[crit.rule]
    return "medium"          # judgment criteria without a rule


def impact_for(component_key: str) -> Level:
    return _IMPACT_BY_COMPONENT.get(component_key, "medium")


def priority_score(status: str, effort: str, impact: str) -> float:
    """Higher = do it first. Real failures outrank items that only need a manual check."""
    weight = 1.0 if status == "fail" else 0.5
    return round(weight * _NUM[impact] / _NUM[effort], 3)


def default_suggestion(crit: Criterion) -> str:
    return f"Aim for this: {crit.hint}" if crit.hint else f"Revisit: {crit.name}."


def build_todo(
    results: list[ComponentResult],
    crit_by_id: dict[str, Criterion],
    suggestions: dict[str, tuple[str, str | None]] | None = None,
) -> list[TodoItem]:
    """suggestions maps criterion id -> (text, optional effort override from the model)."""
    suggestions = suggestions or {}
    items: list[tuple[float, int, TodoItem]] = []
    order = 0
    for comp in results:
        for v in comp.verdicts:
            order += 1
            if v.status not in ("fail", "needs_review"):
                continue
            crit = crit_by_id[v.id]
            text, eff_override = suggestions.get(v.id, (default_suggestion(crit), None))
            effort: Level = eff_override if eff_override in VALID_LEVELS else effort_for(crit)  # type: ignore[assignment]
            impact = impact_for(comp.key)
            score = priority_score(v.status, effort, impact)
            items.append(
                (
                    score,
                    order,
                    TodoItem(
                        id=v.id,
                        name=v.name,
                        component=comp.key,
                        component_name=comp.name,
                        status=v.status,
                        effort=effort,
                        impact=impact,
                        priority=score,
                        suggestion=text,
                        block=v.block,
                        section=v.section,
                    ),
                )
            )
    items.sort(key=lambda t: (-t[0], t[1]))
    return [t[2] for t in items]
