"""backend/app/services/extraction/latex_extractor.py"""
import re
from pathlib import Path

from pylatexenc.latex2text import LatexNodes2Text

from app.core.errors import CorruptFileError, ExtractionError
from app.schemas.document import Block, ParsedDocument

from .base import Extractor
from .normalizer import clean_text

_L2T = LatexNodes2Text()

_COMMENT = re.compile(r"(?<!\\)%.*")
_SEC = re.compile(r"\\(section|subsection|subsubsection)\*?\s*(?:\[[^\]]*\])?\s*\{")
_CITE = re.compile(
    r"\\(?:cite|citep|citet|citeauthor|citeyear|parencite|textcite|autocite)\*?(?:\[[^\]]*\])*\{([^}]*)\}"
)
_REF = re.compile(r"\\(?:auto|c|C|eq)?ref\{[^}]*\}")
_FIG = re.compile(r"\\begin\{(figure|table)\*?\}(.*?)\\end\{\1\*?\}", re.S)
_BIB = re.compile(r"\\begin\{thebibliography\}\{[^}]*\}(.*?)\\end\{thebibliography\}", re.S)
_ABS = re.compile(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", re.S)
_LEVEL = {"section": 1, "subsection": 2, "subsubsection": 3}
_MARK = "CAPTIONMARK "


def _brace_arg(s: str, i: int) -> tuple[str, int]:
    """s[i] must be '{'. Returns (content, index after the closing brace)."""
    depth = 0
    for j in range(i, len(s)):
        if s[j] == "{" and (j == 0 or s[j - 1] != "\\"):
            depth += 1
        elif s[j] == "}" and (j == 0 or s[j - 1] != "\\"):
            depth -= 1
            if depth == 0:
                return s[i + 1:j], j + 1
    return s[i + 1:], len(s)


def _find_cmd(s: str, cmd: str) -> list[tuple[int, str, int]]:
    out = []
    for m in re.finditer(r"\\" + cmd + r"\*?(?:\[[^\]]*\])?\s*\{", s):
        content, end = _brace_arg(s, m.end() - 1)
        out.append((m.start(), content, end))
    return out


def _to_text(s: str) -> str:
    s = re.sub(r"\\(label|maketitle|centering|noindent|newpage|clearpage)\b(\{[^}]*\})?", "", s)
    try:
        t = _L2T.latex_to_text(s)
    except Exception:
        t = re.sub(r"\\[a-zA-Z]+\*?(\[[^\]]*\])?", " ", s)
        t = re.sub(r"[{}$]", "", t)
    return clean_text(t)


def _paragraphs(chunk: str) -> list[Block]:
    out: list[Block] = []
    for para in re.split(r"\n\s*\n", chunk):
        t = _to_text(para)
        if not t:
            continue
        if t.startswith(_MARK):
            out.append(Block(text=t[len(_MARK):], kind="caption"))
        else:
            out.append(Block(text=t))
    return out


class LatexExtractor(Extractor):
    def extract(self, path: Path) -> ParsedDocument:
        try:
            data = path.read_bytes()
        except OSError as exc:
            raise CorruptFileError(f"Could not read the file: {exc}") from exc
        try:
            raw = data.decode("utf-8")
        except UnicodeDecodeError:
            raw = data.decode("latin-1")

        raw = _COMMENT.sub("", raw)
        pre, body = raw, raw
        m = re.search(r"\\begin\{document\}", raw)
        if m:
            pre = raw[:m.start()]
            body = re.sub(r"\\end\{document\}.*", "", raw[m.end():], flags=re.S)

        # title
        title = None
        for src in (pre, body):
            found = _find_cmd(src, "title")
            if found:
                title = _to_text(found[0][1])
                break

        # abstract
        abstract = None
        am = _ABS.search(body)
        if am:
            abstract = am.group(1)
            body = body[:am.start()] + body[am.end():]

        # embedded bibliography (\bibitem) -> numbered entries
        keynum: dict[str, int] = {}
        bib_entries: list[tuple[int, str]] = []
        bm = _BIB.search(body)
        if bm:
            parts = re.split(r"\\bibitem(?:\[[^\]]*\])?\{([^}]*)\}", bm.group(1))
            for key, text in zip(parts[1::2], parts[2::2]):
                key = key.strip()
                keynum.setdefault(key, len(keynum) + 1)
                bib_entries.append((keynum[key], text))
            body = body[:bm.start()] + body[bm.end():]
        bib_external = (not bm) and bool(
            re.search(r"\\(bibliography|addbibresource|printbibliography)\b", body)
        )

        # citations -> [n, m] so citation checks work like in PDFs
        def _cite(mm: re.Match) -> str:
            nums = set()
            for k in (x.strip() for x in mm.group(1).split(",")):
                if not k:
                    continue
                keynum.setdefault(k, len(keynum) + 1)
                nums.add(keynum[k])
            return "[" + ", ".join(str(n) for n in sorted(nums)) + "]"

        body = _CITE.sub(_cite, body)
        if abstract:
            abstract = _CITE.sub(_cite, abstract)

        # references to figures/sections: keep a visible marker for the abstract check
        body = _REF.sub("Sec./Fig. X", body)
        if abstract:
            abstract = _REF.sub("Sec./Fig. X", abstract)

        # figures and tables -> caption blocks
        counts = {"Figure": 0, "Table": 0}

        def _fig(mm: re.Match) -> str:
            kind = "Figure" if mm.group(1) == "figure" else "Table"
            counts[kind] += 1
            caps = _find_cmd(mm.group(2), "caption")
            cap = _to_text(caps[0][1]) if caps else ""
            return f"\n\n{_MARK}{kind} {counts[kind]}: {cap}\n\n" if cap else "\n\n"

        body = _FIG.sub(_fig, body)

        # assemble blocks
        blocks: list[Block] = []
        if title:
            blocks.append(Block(text=title, kind="title"))
        if abstract is not None:
            blocks.append(Block(text="Abstract", kind="heading", level=1, bold=True))
            blocks.extend(_paragraphs(abstract))

        matches = list(_SEC.finditer(body))
        if not matches:
            blocks.extend(_paragraphs(body))
        else:
            blocks.extend(_paragraphs(body[:matches[0].start()]))
            for n, mm in enumerate(matches):
                head, end = _brace_arg(body, mm.end() - 1)
                nxt = matches[n + 1].start() if n + 1 < len(matches) else len(body)
                blocks.append(
                    Block(text=_to_text(head), kind="heading", level=_LEVEL[mm.group(1)], bold=True)
                )
                blocks.extend(_paragraphs(body[end:nxt]))

        if bib_entries:
            blocks.append(Block(text="References", kind="heading", level=1, bold=True))
            for num, text in bib_entries:
                t = _to_text(text)
                if t:
                    blocks.append(Block(text=f"[{num}] {t}"))

        if not blocks:
            raise ExtractionError("No text could be extracted from the LaTeX source.")

        return ParsedDocument(
            file_type="tex",
            blocks=blocks,
            num_pages=None,   # LaTeX source has no pages
            meta={
                "n_figures": counts["Figure"],
                "n_tables": counts["Table"],
                "bib_external": bib_external,
                "cite_keys": len(keynum),
            },
        )
