"""backend/app/services/sections/layout_heuristics.py"""
"""Heading candidates from layout: numbering, caps, bold, larger font."""
from app.schemas.document import ParsedDocument

from .heading_rules import classify_heading, is_caps_heading, is_numbered_heading


def layout_candidates(doc: ParsedDocument) -> list[tuple[int, float]]:
    """Return (block index, score 0..1) for blocks that look like headings."""
    body = doc.meta.get("body_size")
    out: list[tuple[int, float]] = []
    for i, b in enumerate(doc.blocks):
        if b.kind != "text":
            continue
        text = b.text
        words = len(text.split())
        if words == 0 or words > 12:
            continue

        numbered = is_numbered_heading(text)
        caps = is_caps_heading(text)
        if text.endswith((".", ",", ";")) and not numbered and not caps:
            continue

        score = 0.0
        if numbered:
            score += 0.5
        if caps:
            score += 0.4
        if b.bold:
            score += 0.3
        if b.size and body and b.size >= body * 1.08:
            score += 0.3
        if words <= 6 and classify_heading(text):   # a known section name alone on a line
            score += 0.45

        if score >= 0.4:
            out.append((i, min(score, 1.0)))
    return out
