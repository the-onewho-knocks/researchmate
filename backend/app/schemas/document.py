from typing import Any, Literal

from pydantic import BaseModel, Field


class Block(BaseModel):
    text: str
    page: int | None = None
    size: float | None = None          # dominant font size (pdf/docx)
    bold: bool = False
    ypos: float | None = None          # relative vertical position 0..1 on its page
    kind: Literal["text", "heading", "title", "caption"] = "text"
    level: int | None = None           # heading level when known


class ParsedDocument(BaseModel):
    file_type: Literal["pdf", "docx", "tex"]
    blocks: list[Block]
    num_pages: int | None = None
    meta: dict[str, Any] = Field(default_factory=dict)

    def full_text(self) -> str:
        return "\n".join(b.text for b in self.blocks)
