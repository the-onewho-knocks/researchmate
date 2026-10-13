"""backend/app/schemas/report.py"""
from pydantic import BaseModel, Field

from app.schemas.verdict import Verdict


class Usage(BaseModel):
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    model: str = ""

    def add(self, input_tokens: int, output_tokens: int) -> None:
        self.calls += 1
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens


class ComponentResult(BaseModel):
    key: str
    name: str
    acronym: str
    score: float | None = None      # % of assessed criteria that passed
    coverage: float = 0.0           # share of criteria that got a pass/fail verdict
    verdicts: list[Verdict]


class EvaluationReport(BaseModel):
    document_id: str = ""
    file_type: str = ""
    framework_version: str = ""
    overall_score: float | None = None
    coverage: float = 0.0
    components: list[ComponentResult]
    limitations: list[str] = Field(default_factory=list)
    sections_detected: list[str] = Field(default_factory=list)
    source_counts: dict[str, int] = Field(default_factory=dict)
    usage: Usage = Field(default_factory=Usage)
    coach_feedback: str | None = None
    cached: bool = False