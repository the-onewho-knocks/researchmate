"""backend/app/services/rules/components/abstract.py"""
import re

from ..primitives import EvalContext, RuleResult, find_hit, rule, short, split_sentences

_SELF_REF = [
    r"\b(fig\.?|figs\.?|figure|table|section|sec\.|eq\.|equation)\s*[\d#]",
    r"\bSec\./Fig\.",
    r"\[\d+(?:\s*[,–\-]\s*\d+)*\]",
    r"\bet al\.",
]
_RESULT_CUES = re.compile(
    r"\b(achiev|outperform|improv|reach|reduc|increas|accura|f1|precision|recall|show|demonstrat|found|result)",
    re.I,
)


@rule("abstract_self_contained")
def abstract_self_contained(ctx: EvalContext, p: dict) -> RuleResult:
    hit = find_hit(ctx.section_text(), _SELF_REF)
    if hit:
        return RuleResult("fail", short(hit), 0.85, "Refers to figures, sections, tables or citations.")
    return RuleResult("pass", None, 0.85)


@rule("abstract_results_summary")
def abstract_results_summary(ctx: EvalContext, p: dict) -> RuleResult:
    for s in split_sentences(ctx.section_text()):
        if re.search(r"\d", s) and _RESULT_CUES.search(s):
            return RuleResult("pass", short(s), 0.7)
    return RuleResult("fail", None, 0.5, "No sentence combines results with numbers.")
