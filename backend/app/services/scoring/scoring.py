"""backend/app/services/scoring/scoring.py"""
from app.schemas.report import ComponentResult
from app.schemas.verdict import Verdict


def score_component(verdicts: list[Verdict]) -> tuple[float | None, float]:
    """Return (score %, coverage). Only pass/fail verdicts count toward the score;
    coverage shows how many criteria could be assessed at all."""
    if not verdicts:
        return None, 0.0
    assessed = [v for v in verdicts if v.status in ("pass", "fail")]
    coverage = len(assessed) / len(verdicts)
    if not assessed:
        return None, coverage
    passed = sum(1 for v in assessed if v.status == "pass")
    return round(100 * passed / len(assessed), 1), round(coverage, 3)


def score_overall(components: list[ComponentResult]) -> tuple[float | None, float]:
    verdicts = [v for c in components for v in c.verdicts]
    return score_component(verdicts)