"""backend/app/services/sections/heading_rules.py"""
"""Heading synonyms and numbering patterns. Pure functions, no I/O."""
import re

_NUM_PREFIX = re.compile(r"^\s*(?:(?:\d+(?:\.\d+)*|[IVXLC]+|[A-Z])[.)]?\s+)")
_SMALLCAPS = re.compile(r"\b([A-Z]) ([A-Z]{2,})\b")          # "R ELATED W ORK"
_NUMBERED = re.compile(r"^\s*(?:\d+(?:\.\d+)*\.?|[IVXLC]+\.)\s+\S")

SECTION_PATTERNS: dict[str, str] = {
    "abstract": r"abstract|summary",
    "keywords": r"keywords?|index terms",
    "introduction": r"introduction|introductory remarks|motivation|background and motivation",
    "related_work": (
        r"related (work|works|research|literature)|literature (review|survey)"
        r"|state[ -]of[ -]the[ -]art( review)?|previous work|prior work|background( and related work)?"
    ),
    "methods": (
        r"methods?|methodology|materials and methods"
        r"|(proposed |our )?(approach|method|methodology|framework|system)"
        r"|(system|method) (design|overview|description)"
    ),
    "results": (
        r"results?|experiments?|experimental (results|evaluation|setup|study|analysis)"
        r"|evaluation|findings|results and analysis"
    ),
    "discussion": r"discussions?|analysis( and discussion)?|general discussion",
    "conclusion": (
        r"conclusions?|concluding remarks|conclusions? and (future work|outlook|limitations)"
        r"|summary and conclusions?|future work"
    ),
    "references": r"references|bibliography|literature cited|works cited",
    "acknowledgments": r"acknowledg(e)?ments?",
    "appendix": r"appendix( [a-z0-9]+)?|appendices|supplementary (material|information)",
}

_COMPILED = {label: re.compile(p) for label, p in SECTION_PATTERNS.items()}
_MULTI = re.compile(r"results?\s*(and|&)\s*(discussions?|analysis)|findings and discussion")


def fix_smallcaps(text: str) -> str:
    return _SMALLCAPS.sub(r"\1\2", text)


def normalize_heading(text: str) -> str:
    t = fix_smallcaps(text.strip())
    t = _NUM_PREFIX.sub("", t, count=1)
    t = re.sub(r"[\s:.\-–—]+$", "", t)
    return re.sub(r"\s+", " ", t).lower()


def classify_heading(text: str) -> tuple[str, ...]:
    """Return the section label(s) a heading maps to, or () if it is not a known heading."""
    n = normalize_heading(text)
    if not n or len(n.split()) > 8:
        return ()
    if _MULTI.fullmatch(n):
        return ("results", "discussion")
    for label, pattern in _COMPILED.items():
        if pattern.fullmatch(n):
            return (label,)
    return ()


def is_numbered_heading(text: str) -> bool:
    return (
        bool(_NUMBERED.match(text))
        and len(text.split()) <= 12
        and not text.rstrip().endswith((",", ";"))
    )


def is_caps_heading(text: str) -> bool:
    letters = [c for c in text if c.isalpha()]
    return len(letters) >= 4 and text.upper() == text and len(text.split()) <= 6