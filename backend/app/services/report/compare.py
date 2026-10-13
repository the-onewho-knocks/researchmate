"""backend/app/services/report/compare.py"""
from app.schemas.compare import ComponentDelta, Comparison, CriterionChange
from app.schemas.report import EvaluationReport


def _delta(before: float | None, after: float | None) -> float | None:
    if before is None or after is None:
        return None
    return round(after - before, 1)


def compare_reports(before: EvaluationReport, after: EvaluationReport) -> Comparison:
    """What changed between two drafts. Only pass/fail flips count as improved or regressed;
    moves involving 'needs review' are reported as 'changed'."""
    old = {v.id: v for c in before.components for v in c.verdicts}

    changes: list[CriterionChange] = []
    total = 0
    still_failing = 0
    for comp in after.components:
        for v in comp.verdicts:
            total += 1
            if v.status == "fail":
                still_failing += 1
            prev = old.get(v.id)
            if prev is None or prev.status == v.status:
                continue
            if v.status == "pass":
                direction = "improved"
            elif prev.status == "pass":
                direction = "regressed"
            else:
                direction = "changed"
            changes.append(
                CriterionChange(
                    id=v.id,
                    name=v.name,
                    component=comp.key,
                    component_name=comp.name,
                    before=prev.status,
                    after=v.status,
                    direction=direction,
                    evidence_after=v.evidence,
                    note_after=v.note,
                )
            )

    before_scores = {c.key: c.score for c in before.components}
    deltas = [
        ComponentDelta(
            key=c.key,
            name=c.name,
            acronym=c.acronym,
            before=before_scores.get(c.key),
            after=c.score,
            delta=_delta(before_scores.get(c.key), c.score),
        )
        for c in after.components
    ]

    n = lambda d: sum(1 for c in changes if c.direction == d)  # noqa: E731
    return Comparison(
        before_id=before.document_id,
        after_id=after.document_id,
        overall_before=before.overall_score,
        overall_after=after.overall_score,
        overall_delta=_delta(before.overall_score, after.overall_score),
        coverage_before=before.coverage,
        coverage_after=after.coverage,
        improved=n("improved"),
        regressed=n("regressed"),
        changed=n("changed"),
        unchanged=total - len(changes),
        still_failing=still_failing,
        resolved_ids=[c.id for c in changes if c.direction == "improved"],
        components=deltas,
        changes=changes,
    )
