"""backend/app/schemas/framework.py"""
from typing import Any, Literal

from pydantic import BaseModel, Field


class Criterion(BaseModel):
    id: str
    name: str
    tier: Literal["A", "B", "C"]
    hint: str = ""
    rule: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)
    ml_label: str | None = None


class Component(BaseModel):
    key: str
    name: str
    acronym: str
    section: str
    criteria: list[Criterion]


class Framework(BaseModel):
    version: str
    components: list[Component]

    def all_criteria(self) -> list[Criterion]:
        return [c for comp in self.components for c in comp.criteria]