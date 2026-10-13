"""backend/app/services/sections/structural_hints.py"""
"""Native structure: .tex \\section commands and Word heading styles."""
from app.schemas.document import ParsedDocument


def structural_headings(doc: ParsedDocument) -> list[int]:
    return [i for i, b in enumerate(doc.blocks) if b.kind == "heading"]


def structural_title(doc: ParsedDocument) -> int | None:
    for i, b in enumerate(doc.blocks):
        if b.kind == "title":
            return i
    return None
