"""backend/app/services/rules/primitives.py"""
"""Shared helpers, the rule registry, EvalContext and the generic rules."""
from __future__ import annotations

import re
from dataclasses import dataclass
from functools import cached_property, lru_cache
from typing import Callable

from app.schemas.document import ParsedDocument
from app.schemas.sections import SectionMap


# ----------------------------------------------------------------- registry
@dataclass
class RuleResult:
    status: str                      # pass | fail | needs_review
    evidence: str | None = None
    confidence: float = 0.9
    note: str | None = None


RuleFn = Callable[["EvalContext", dict], RuleResult]


@dataclass
class RuleSpec:
    fn: RuleFn
    needs_section: bool = True       # engine returns needs_review if the section is missing


RULES: dict[str, RuleSpec] = {}


def rule(name: str, needs_section: bool = True):
    def deco(fn: RuleFn) -> RuleFn:
        RULES[name] = RuleSpec(fn, needs_section)
        return fn
    return deco


# ------------------------------------------------------------- text helpers
_ABBR = ["e.g.", "i.e.", "et al.", "Fig.", "Figs.", "Eq.", "vs.", "w.r.t.", "cf.", "No.", "approx.", "Sec.", "etc."]


def split_sentences(text: str) -> list[str]:
    t = text
    for a in _ABBR:
        t = t.replace(a, a.replace(".", "\u2024"))
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z\[\(\"\u201c])", t)
    return [p.replace("\u2024", ".").strip() for p in parts if len(p.strip()) > 2]


def word_count(text: str) -> int:
    return len(text.split())


def short(s: str, n: int = 240) -> str:
    s = s.strip()
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


@lru_cache(maxsize=1024)
def _rx(pattern: str) -> re.Pattern:
    return re.compile(pattern, re.I)


def find_hit(text: str, patterns: list[str]) -> str | None:
    """First sentence matching any pattern, or None."""
    rxs = [_rx(p) for p in patterns]
    for s in split_sentences(text):
        if any(r.search(s) for r in rxs):
            return s
    return None


# ---------------------------------------------------------------- citations
_NUM_CITE = re.compile(r"\[(\d+(?:\s*[,–\-]\s*\d+)*)\]")
_YEAR = re.compile(r"(?<![\d–\-])(?:19|20)\d{2}(?!\d|[–\-]\d)")


def cited_numbers(text: str) -> set[int]:
    nums: set[int] = set()
    for m in _NUM_CITE.finditer(text):
        for part in re.split(r"\s*,\s*", m.group(1)):
            if re.search(r"[–\-]", part):
                a, b = (int(x) for x in re.split(r"\s*[–\-]\s*", part))
                if 0 <= b - a <= 50:
                    nums.update(range(a, b + 1))
            else:
                nums.add(int(part))
    return nums


def split_references(block_texts: list[str]) -> list[str]:
    joined = " ".join(block_texts)
    if len(re.findall(r"\[\d+\]\s", joined)) >= 3:
        parts = re.split(r"\s(?=\[\d+\]\s)", " " + joined)
        return [p.strip() for p in parts if len(p.strip()) > 15]
    return [t for t in block_texts if len(t) > 25]


def ref_number(entry: str) -> int | None:
    m = re.match(r"\[(\d+)\]", entry)
    return int(m.group(1)) if m else None


def ref_year(entry: str) -> int | None:
    years = _YEAR.findall(entry)
    return int(years[-1]) if years else None


# ------------------------------------------------------------------ context
_FIG_CAP = re.compile(r"^(?:fig\.?|figure)\s*\d+", re.I)
_TAB_CAP = re.compile(r"^table\s+(?:\d+|[IVXLC]+)\b", re.I)


@dataclass
class EvalContext:
    doc: ParsedDocument
    sections: SectionMap
    section_key: str = ""            # set by the engine/pipeline per criterion

    def text(self, label: str) -> str:
        return self.sections.text(label, self.doc) if self.sections.has(label) else ""

    def text_multi(self, labels: list[str]) -> str:
        return "\n".join(t for t in (self.text(l) for l in labels) if t)

    def section_text(self) -> str:
        return self.text(self.section_key)

    @cached_property
    def body_text(self) -> str:
        """Everything except title, reference list and captions (used for citation checks)."""
        skip: set[int] = set()
        for label in ("references", "title"):
            sp = self.sections.spans.get(label)
            if sp:
                skip.update(range(sp.start, sp.end))
        return "\n".join(
            b.text for i, b in enumerate(self.doc.blocks) if i not in skip and b.kind != "caption"
        )

    @cached_property
    def refs(self) -> list[str]:
        sp = self.sections.spans.get("references")
        if not sp:
            return []
        return split_references([b.text for b in self.doc.blocks[sp.start:sp.end]])

    @cached_property
    def caption_counts(self) -> tuple[int, int]:
        fig = sum(1 for b in self.doc.blocks if _FIG_CAP.match(b.text))
        tab = sum(1 for b in self.doc.blocks if _TAB_CAP.match(b.text))
        return fig, tab

    @property
    def figure_count(self) -> int:
        return max(int(self.doc.meta.get("n_figures") or 0), self.caption_counts[0])

    @property
    def table_count(self) -> int:
        return max(int(self.doc.meta.get("n_tables") or 0), self.caption_counts[1])


# ------------------------------------------------------------ generic rules
@rule("word_count_between")
def _word_count_between(ctx: EvalContext, p: dict) -> RuleResult:
    n = word_count(ctx.section_text())
    lo, hi = p.get("min", 0), p.get("max", 10**9)
    ok = lo <= n <= hi
    return RuleResult("pass" if ok else "fail", f"{n} words (target {lo}-{hi})", 0.95)


@rule("any_pattern")
def _any_pattern(ctx: EvalContext, p: dict) -> RuleResult:
    text = ctx.text_multi([ctx.section_key, *p.get("also", [])])
    hit = find_hit(text, p["patterns"])
    if hit:
        return RuleResult("pass", short(hit), 0.7)
    return RuleResult("fail", None, 0.5, "No cue phrase found.")


@rule("no_pattern")
def _no_pattern(ctx: EvalContext, p: dict) -> RuleResult:
    hit = find_hit(ctx.section_text(), p["patterns"])
    if hit:
        return RuleResult("fail", short(hit), 0.85)
    return RuleResult("pass", None, 0.85)