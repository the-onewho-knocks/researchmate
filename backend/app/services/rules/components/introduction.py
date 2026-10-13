"""backend/app/services/rules/components/introduction.py"""
from ..primitives import EvalContext, RuleResult, find_hit, rule, short

_NOVELTY = [
    r"\bnovel\b",
    r"\bnovelty\b",
    r"\bfirst\b",
    r"\bcontributions?\b",
    r"\bwe (propose|present|introduce|develop)\b",
    r"\bnew (approach|method|framework|technique|algorithm)\b",
]


@rule("intro_novelty_statement")
def intro_novelty_statement(ctx: EvalContext, p: dict) -> RuleResult:
    hit = find_hit(ctx.section_text(), _NOVELTY)
    if hit:
        return RuleResult("pass", short(hit), 0.7)
    return RuleResult("fail", None, 0.5, "No novelty or contribution statement found.")