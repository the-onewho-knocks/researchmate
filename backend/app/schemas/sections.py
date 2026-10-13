from pydantic import BaseModel, Field

from app.schemas.document import ParsedDocument


class SectionSpan(BaseModel):
    label: str
    start: int                 # first block index (inclusive)
    end: int                   # last block index (exclusive)
    heading: str | None = None
    confidence: float = 0.8
    method: str = "heading"    # structure | layout | heading | fallback


class SectionMap(BaseModel):
    spans: dict[str, SectionSpan] = Field(default_factory=dict)
    low_confidence: bool = False
    notes: list[str] = Field(default_factory=list)

    def has(self, label: str) -> bool:
        return label in self.spans

    def text(self, label: str, doc: ParsedDocument) -> str:
        sp = self.spans.get(label)
        if not sp:
            return ""
        return "\n".join(b.text for b in doc.blocks[sp.start:sp.end])
