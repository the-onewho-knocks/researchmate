"""backend/app/services/orchestrator/merger.py"""
from dataclasses import dataclass

from app.schemas.framework import Criterion
from app.schemas.verdict import Verdict


@dataclass
class Pending:
    """A criterion that needs the LLM, plus the verdict to use if the LLM cannot answer."""

    criterion: Criterion
    component_key: str
    fallback: Verdict


def merge_verdicts(*maps: dict[str, Verdict]) -> dict[str, Verdict]:
    """Later maps override earlier ones: pass rule/ml verdicts first, LLM verdicts last."""
    out: dict[str, Verdict] = {}
    for m in maps:
        out.update(m)
    return out
