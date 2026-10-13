"""backend/app/schemas/compare.py"""
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.verdict import Status


class CriterionChange(BaseModel):
    id: str
    name: str
    component: str
    component_name: str
    before: Status
    after: Status
    direction: Literal["improved", "regressed", "changed"]
    evidence_after: str | None = None
    note_after: str | None = None


class ComponentDelta(BaseModel):
    key: str
    name: str
    acronym: str
    before: float | None = None
    after: float | None = None
    delta: float | None = None


class Comparison(BaseModel):
    before_id: str = ""
    after_id: str = ""
    overall_before: float | None = None
    overall_after: float | None = None
    overall_delta: float | None = None
    coverage_before: float = 0.0
    coverage_after: float = 0.0
    improved: int = 0
    regressed: int = 0
    changed: int = 0
    unchanged: int = 0
    still_failing: int = 0
    resolved_ids: list[str] = Field(default_factory=list)
    components: list[ComponentDelta] = Field(default_factory=list)
    changes: list[CriterionChange] = Field(default_factory=list)


class CompareRequest(BaseModel):
    before_id: str
    after_id: str
