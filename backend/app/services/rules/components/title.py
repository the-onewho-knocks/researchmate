"""backend/app/services/rules/components/title.py"""
import re

from ..primitives import EvalContext, RuleResult, rule, word_count

_FILLER = re.compile(
    r"^(?:a|an|the)?\s*(?:study|research|investigation|analysis|review)\s+(?:of|on|about)\b"
    r"|\b(?:a|the)\s+(?:research|study)\s+about\b",
    re.I,
)


@rule("title_compact")
def title_compact(ctx: EvalContext, p: dict) -> RuleResult:
    t = ctx.section_text().strip()
    n = word_count(t)
    lo, hi = p.get("min_words", 4), p.get("max_words", 20)
    if _FILLER.search(t):
        return RuleResult("fail", t, 0.85, "The title starts with filler such as 'a study of'.")
    if not lo <= n <= hi:
        return RuleResult("fail", f"{n} words (target {lo}-{hi})", 0.9)
    return RuleResult("pass", f"{n} words", 0.9)
