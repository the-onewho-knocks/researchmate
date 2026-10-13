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
    note: str | None = None