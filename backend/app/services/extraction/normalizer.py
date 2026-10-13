"""backend/app/services/extraction/normalizer.py"""
import re
from collections import Counter, defaultdict

from app.schemas.document import Block, ParsedDocument

_WS = re.compile(r"\s+")
_LIGATURES = {"\ufb00": "ff", "\ufb01": "fi", "\ufb02": "fl", "\ufb03": "ffi", "\ufb04": "ffl"}
# "Abstract—Text...", "Index Terms—a, b", "Keywords: a, b"
_RUNIN = re.compile(r"^(abstract|index terms|keywords?)\s*(?:[—–:]|-\s)\s*(.+)$", re.I | re.S)


def clean_text(text: str) -> str:
    for k, v in _LIGATURES.items():
        text = text.replace(k, v)
    return _WS.sub(" ", text.replace("\u00ad", "")).strip()


def join_lines(lines: list[str]) -> str:
    """Join PDF lines into one paragraph and repair end-of-line hyphenation."""
    out = ""
    for ln in lines:
        ln = ln.strip()
        if not ln:
            continue
        if out.endswith("-") and len(out) > 1 and out[-2].isalpha() and ln[:1].islower():
            out = out[:-1] + ln
        else:
            out = (out + " " + ln).strip()
    return out


def normalize(doc: ParsedDocument) -> ParsedDocument:
    blocks: list[Block] = []
    for b in doc.blocks:
        t = clean_text(b.text)
        if t:
            blocks.append(b.model_copy(update={"text": t}))
    blocks = _strip_repeating_edges(blocks, doc.num_pages)
    blocks = _split_run_in_headings(blocks)
    doc.blocks = blocks
    doc.meta["body_size"] = _body_size(blocks)
    return doc


def _key(text: str) -> str:
    return re.sub(r"\d+", "#", text.lower())[:80]


def _is_edge(b: Block) -> bool:
    return b.page is not None and b.ypos is not None and (b.ypos < 0.08 or b.ypos > 0.92)


def _strip_repeating_edges(blocks: list[Block], num_pages: int | None) -> list[Block]:
    """Remove running headers/footers (same text on many pages) and bare page numbers."""
    pages_by_key: dict[str, set[int]] = defaultdict(set)
    for b in blocks:
        if _is_edge(b):
            pages_by_key[_key(b.text)].add(b.page)
    threshold = max(3, int(0.5 * (num_pages or 0)))
    repeating = {k for k, pages in pages_by_key.items() if len(pages) >= threshold}

    out = []
    for b in blocks:
        if _is_edge(b):
            if _key(b.text) in repeating:
                continue
            if re.fullmatch(r"[\d\s\-–]{1,6}", b.text):
                continue
        out.append(b)
    return out


def _split_run_in_headings(blocks: list[Block]) -> list[Block]:
    out: list[Block] = []
    for b in blocks:
        m = _RUNIN.match(b.text) if b.kind == "text" else None
        if not m:
            out.append(b)
            continue
        name = "Abstract" if m.group(1).lower() == "abstract" else "Keywords"
        out.append(
            Block(text=name, page=b.page, size=b.size, bold=True, ypos=b.ypos, kind="heading", level=1)
        )
        out.append(b.model_copy(update={"text": m.group(2).strip()}))
    return out


def _body_size(blocks: list[Block]) -> float | None:
    counts: Counter[float] = Counter()
    for b in blocks:
        if b.kind == "text" and b.size:
            counts[round(b.size, 1)] += len(b.text)
    return counts.most_common(1)[0][0] if counts else None