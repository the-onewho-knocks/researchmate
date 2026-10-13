"""backend/app/services/rules/components/results.py"""
from ..primitives import EvalContext, RuleResult, find_hit, rule, short

_VISUAL_REF = [
    r"\b(fig\.?|figs\.?|figure|figures|table|tables)\s*[\d#]",
    r"\bSec\./Fig\.",
    r"\b(table|figure)s?\s+[IVXLC]+\b",
]


@rule("has_captions", needs_section=False)
def has_captions(ctx: EvalContext, p: dict) -> RuleResult:
    total = ctx.figure_count + ctx.table_count
    captions = sum(ctx.caption_counts)
    if total == 0:
        return RuleResult("needs_review", None, 0.0, "No figures or tables were detected.")
    if captions >= 1 and captions >= 0.8 * total:
        return RuleResult("pass", f"{captions} of {total} figures/tables have captions", 0.8)
    return RuleResult("fail", f"{captions} of {total} figures/tables have captions", 0.75)


@rule("results_visual_support")
def results_visual_support(ctx: EvalContext, p: dict) -> RuleResult:
    n = ctx.figure_count + ctx.table_count
    if n == 0:
        return RuleResult("fail", "No figures or tables found", 0.8, "Results are not supported visually.")
    hit = find_hit(ctx.section_text(), _VISUAL_REF)
    if hit:
        return RuleResult("pass", short(hit), 0.75, f"{n} figures/tables found. Figure content itself is not analysed.")
    return RuleResult("fail", f"{n} figures/tables exist but the Results text does not refer to them", 0.7)