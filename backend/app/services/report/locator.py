"""backend/app/services/report/locator.py"""
"""Map verdict evidence back to the paragraph it came from, for the in-context reading view."""
import re

from app.schemas.document import ParsedDocument
from app.schemas.report import Paragraph
from app.schemas.sections import SectionMap
from app.schemas.verdict import Verdict

_TOKEN = re.compile(r"[a-z0-9]+")
_MAX_PARAGRAPH_CHARS = 3000


def _tokens(s: str) -> list[str]:
    return _TOKEN.findall((s or "").lower())


def block_sections(doc: ParsedDocument, smap: SectionMap) -> list[list[str]]:
    """Section labels for every block. A heading belongs to the section it opens."""
    labels: list[list[str]] = [[] for _ in doc.blocks]
    n = len(doc.blocks)
    for label, sp in smap.spans.items():
        for i in range(sp.start, min(sp.end, n)):
            labels[i].append(label)
        head = sp.start - 1
        if label != "title" and sp.heading and 0 <= head < n and doc.blocks[head].text == sp.heading:
            labels[head].append(label)
    return [sorted(set(x)) for x in labels]


def build_paragraphs(doc: ParsedDocument, smap: SectionMap) -> list[Paragraph]:
    sections = block_sections(doc, smap)
    return [
        Paragraph(i=i, text=b.text[:_MAX_PARAGRAPH_CHARS], kind=b.kind, sections=sections[i])
        for i, b in enumerate(doc.blocks)
    ]


class Locator:
    """Finds the paragraph that contains a verdict's evidence quote."""

    def __init__(self, doc: ParsedDocument, smap: SectionMap):
        self.smap = smap
        self.norm = [" " + " ".join(_tokens(b.text)) + " " for b in doc.blocks]

    def _find(self, evidence: str | None, section: str) -> int | None:
        q = _tokens(evidence or "")
        if len(q) < 3:
            return None
        probe = " " + " ".join(q[:10]) + " "
        sp = self.smap.spans.get(section)
        inside = list(range(sp.start, min(sp.end, len(self.norm)))) if sp else []
        seen = set(inside)
        for i in inside + [i for i in range(len(self.norm)) if i not in seen]:
            if probe in self.norm[i]:
                return i
        return None

    def locate(self, v: Verdict, section: str) -> int | None:
        """Exact paragraph if the evidence is found; section start for failures; otherwise None."""
        exact = self._find(v.evidence, section)
        if exact is not None:
            return exact
        if v.status in ("fail", "needs_review"):
            sp = self.smap.spans.get(section)
            if sp and sp.start < len(self.norm):
                return sp.start
        return None
