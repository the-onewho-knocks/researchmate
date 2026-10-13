"""backend/app/services/sections/fallback.py"""
"""Used only when too few headings were found."""
from collections import Counter
from itertools import groupby

from app.schemas.document import ParsedDocument
from app.schemas.sections import SectionMap, SectionSpan

ORDER = [
    "abstract", "introduction", "related_work", "methods",
    "results", "discussion", "conclusion", "references",
]


def fallback_sections(doc: ParsedDocument, smap: SectionMap, classifier=None) -> SectionMap:
    if classifier is None or not getattr(classifier, "available", False):
        smap.notes.append(
            "No trained section classifier available; unlabeled text is not assigned to sections."
        )
        return smap

    idx = [i for i, b in enumerate(doc.blocks) if b.kind == "text" and len(b.text.split()) >= 8]
    if not idx:
        return smap

    labels = _smooth(classifier.predict([doc.blocks[i].text for i in idx]))
    pos = 0
    for label, group in groupby(labels):
        n = len(list(group))
        start, end = idx[pos], idx[pos + n - 1] + 1
        pos += n
        if label in ORDER and label not in smap.spans and not _overlaps(smap, start, end):
            smap.spans[label] = SectionSpan(
                label=label, start=start, end=end, confidence=0.45, method="fallback"
            )
    smap.notes.append("Some sections were assigned by the ML section classifier (low confidence).")
    return smap


def _smooth(labels: list[str], window: int = 2) -> list[str]:
    out = []
    for i in range(len(labels)):
        win = labels[max(0, i - window): i + window + 1]
        out.append(Counter(win).most_common(1)[0][0])
    return out


def _overlaps(smap: SectionMap, start: int, end: int) -> bool:
    return any(start < sp.end and sp.start < end for sp in smap.spans.values())