"""backend/app/services/sections/identifier.py"""
import re

from app.schemas.document import ParsedDocument
from app.schemas.sections import SectionMap, SectionSpan

from .fallback import fallback_sections
from .heading_rules import classify_heading
from .layout_heuristics import layout_candidates
from .structural_hints import structural_headings, structural_title

CORE = {"introduction", "methods", "results", "conclusion", "references"}
_KEEP_REPEATS = {"references", "appendix"}


def identify_sections(doc: ParsedDocument, classifier=None) -> SectionMap:
    """Map blocks to paper sections.

    A section runs from its heading to the next *recognized* heading, so unknown
    subsection headings stay inside the section they belong to.
    """
    blocks = doc.blocks

    cands: dict[int, float] = {i: 0.95 for i in structural_headings(doc)}
    for i, score in layout_candidates(doc):
        cands.setdefault(i, min(0.85, 0.5 + score / 2))

    found: list[tuple[int, tuple[str, ...], float]] = []
    seen: set[str] = set()
    for i in sorted(cands):
        labels = classify_heading(blocks[i].text)
        if not labels:
            continue
        if any(l in seen for l in labels) and not (set(labels) & _KEEP_REPEATS):
            continue    # a repeated name is most likely a subsection
        seen.update(labels)
        found.append((i, labels, cands[i]))

    smap = SectionMap()
    for n, (i, labels, conf) in enumerate(found):
        end = found[n + 1][0] if n + 1 < len(found) else len(blocks)
        if end - (i + 1) < 1:
            continue
        for lab in labels:
            smap.spans[lab] = SectionSpan(
                label=lab,
                start=i + 1,
                end=end,
                heading=blocks[i].text,
                confidence=conf if len(labels) == 1 else min(conf, 0.8),
                method="structure" if conf >= 0.95 else "layout",
            )

    limit = found[0][0] if found else min(len(blocks), 25)
    _find_references(doc, smap)
    _find_abstract(doc, smap, limit)
    _find_title(doc, smap, limit)

    if len(CORE & set(smap.spans)) < 3:
        smap.low_confidence = True
        smap.notes.append(
            "Few section headings were detected; structure-dependent checks may be unreliable."
        )
        smap = fallback_sections(doc, smap, classifier)
    return smap


def _find_references(doc: ParsedDocument, smap: SectionMap) -> None:
    if smap.has("references"):
        return
    blocks = doc.blocks
    for i, b in enumerate(blocks):
        if re.match(r"^\[1\]\s", b.text) and any("[2]" in x.text[:6] for x in blocks[i:i + 4]):
            smap.spans["references"] = SectionSpan(
                label="references", start=i, end=len(blocks), confidence=0.6, method="fallback"
            )
            for sp in smap.spans.values():     # keep the last body section out of the reference list
                if sp.label != "references" and sp.start < i < sp.end:
                    sp.end = i
            smap.notes.append("Reference list located by its numbering (no 'References' heading).")
            return


def _find_abstract(doc: ParsedDocument, smap: SectionMap, limit: int) -> None:
    if smap.has("abstract"):
        return
    for i in range(min(limit, len(doc.blocks))):
        b = doc.blocks[i]
        if b.kind == "text" and 60 <= len(b.text.split()) <= 450:
            smap.spans["abstract"] = SectionSpan(
                label="abstract", start=i, end=i + 1, confidence=0.5, method="fallback"
            )
            smap.notes.append("Abstract guessed from its position (no 'Abstract' heading found).")
            return


def _find_title(doc: ParsedDocument, smap: SectionMap, limit: int) -> None:
    blocks = doc.blocks
    ti = structural_title(doc)
    if ti is not None:
        smap.spans["title"] = SectionSpan(
            label="title", start=ti, end=ti + 1, confidence=0.95, method="structure"
        )
        return

    head = [(i, b) for i, b in enumerate(blocks[:limit]) if b.kind == "text" and b.page in (None, 1)]
    sized = [(i, b) for i, b in head if b.size]
    if sized:
        biggest = max(b.size for _, b in sized)
        start = next(i for i, b in sized if b.size >= 0.9 * biggest)
        end = start + 1
        while end < limit and blocks[end].kind == "text" and blocks[end].size and blocks[end].size >= 0.9 * biggest:
            end += 1
        smap.spans["title"] = SectionSpan(
            label="title", start=start, end=end, confidence=0.8, method="layout"
        )
        return

    for i, b in head:
        if 2 <= len(b.text.split()) <= 30:
            smap.spans["title"] = SectionSpan(
                label="title", start=i, end=i + 1, confidence=0.5, method="fallback"
            )
            return
