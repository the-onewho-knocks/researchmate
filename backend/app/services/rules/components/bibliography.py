"""backend/app/services/rules/components/bibliography.py"""
import re
from datetime import datetime

from ..primitives import (
    EvalContext,
    RuleResult,
    cited_numbers,
    ref_number,
    ref_year,
    rule,
)

_VENUE = re.compile(
    r"journal|proceedings|conference|transactions|trans\.|ieee|acm|springer|elsevier|arxiv|doi"
    r"|letters|review|symposium|workshop|annals|quarterly|international|bmj|lancet|nature|science|vaccine",
    re.I,
)
_AUTHOR_YEAR = re.compile(r"\(([A-Z][A-Za-z\-']+)(?: et al\.| (?:and|&) [A-Z][a-z]+)?,? (?:19|20)\d{2}[a-z]?\)")


def _no_refs(ctx: EvalContext) -> RuleResult:
    if ctx.doc.meta.get("bib_external"):
        return RuleResult("needs_review", None, 0.0, "The bibliography (.bib file) was not uploaded.")
    return RuleResult("needs_review", None, 0.0, "No reference list was detected.")


@rule("citations_match_refs", needs_section=False)
def citations_match_refs(ctx: EvalContext, p: dict) -> RuleResult:
    refs = ctx.refs
    if not refs:
        return _no_refs(ctx)

    body = ctx.body_text
    listed = {n for n in (ref_number(r) for r in refs) if n is not None}

    if len(listed) >= max(3, int(0.6 * len(refs))):          # numeric style [1], [2] ...
        cited = cited_numbers(body)
        missing = sorted(cited - listed)
        uncited = sorted(listed - cited)
        ok = not missing and len(uncited) <= 0.1 * len(listed)
        parts = [f"{len(cited)} cited, {len(listed)} listed"]
        if missing:
            parts.append(f"cited but not listed: {missing[:8]}")
        if uncited:
            parts.append(f"listed but never cited: {uncited[:8]}")
        return RuleResult("pass" if ok else "fail", "; ".join(parts), 0.85)

    surnames = {m.group(1) for m in _AUTHOR_YEAR.finditer(body)}   # author-year style
    if not surnames:
        return RuleResult("needs_review", None, 0.0, "Citation style not recognised for automatic matching.")
    reftext = " ".join(refs).lower()
    missing_names = sorted(s for s in surnames if s.lower() not in reftext)
    if missing_names:
        return RuleResult("fail", f"Cited but not in the list: {missing_names[:8]}", 0.7)
    return RuleResult("pass", f"{len(surnames)} cited authors all appear in the list", 0.7)


@rule("recent_ref_share", needs_section=False)
def recent_ref_share(ctx: EvalContext, p: dict) -> RuleResult:
    refs = ctx.refs
    if not refs:
        return _no_refs(ctx)
    years = [y for y in (ref_year(r) for r in refs) if y]
    if len(years) < max(3, int(0.5 * len(refs))):
        return RuleResult("needs_review", None, 0.0, "Publication years could not be read from the references.")
    window = p.get("years", 5)
    cutoff = datetime.now().year - window
    recent = sum(1 for y in years if y >= cutoff)
    share = recent / len(years)
    ok = share >= p.get("min_share", 0.3)
    return RuleResult(
        "pass" if ok else "fail",
        f"{recent} of {len(years)} references are from the last {window} years ({share:.0%})",
        0.8,
    )


@rule("venue_or_doi_share", needs_section=False)
def venue_or_doi_share(ctx: EvalContext, p: dict) -> RuleResult:
    refs = ctx.refs
    if not refs:
        return _no_refs(ctx)
    hits = sum(1 for r in refs if _VENUE.search(r))
    share = hits / len(refs)
    ok = share >= p.get("min_share", 0.6)
    return RuleResult(
        "pass" if ok else "fail",
        f"{hits} of {len(refs)} references name a journal, conference or DOI ({share:.0%})",
        0.6,
        "Heuristic: based on venue keywords.",
    )
