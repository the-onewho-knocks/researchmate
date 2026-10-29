"""backend/app/schemas/verdict.py"""
from typing import Literal

from pydantic import BaseModel

Status = Literal["pass", "fail", "needs_review", "could_not_assess"]
Source = Literal["rule", "ml", "llm"]


class Verdict(BaseModel):
    id: str
    component: str
    name: str
    tier: Literal["A", "B", "C"]
    status: Status
    evidence: str | None = None
    confidence: float = 0.0
    source: Source = "rule"
    provider: str | None = None        # which LLM backend judged it ("gemini" / "local")
    note: str | None = None
    section: str | None = None        # section label the criterion is checked in
    block: int | None = None          # paragraph index to jump to (evidence match, or section start for failures)
    suggestion: str | None = None     # one concrete fix (set for fail / needs_review)
