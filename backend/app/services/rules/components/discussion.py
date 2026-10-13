"""backend/app/services/rules/components/discussion.py"""
from ..primitives import EvalContext, RuleResult, find_hit, rule, short

_LIMITATIONS = [
    r"\blimitations?\b",
    r"\blimited (to|by)\b",
    r"\bthreats? to validity\b",
    r"\bbias\b",
    r"\bnot feasible\b",
    r"\bshortcomings?\b",
    r"\bcaveats?\b",
    r"\bwe acknowledge\b",
]
_OPEN_ISSUES = [
    r"\bfuture (work|research|studies|directions)\b",
    r"\bopen (issues|questions|problems)\b",
    r"\bfurther (research|work|investigation|studies)\b",
    r"\bremains? (to be|unclear|open)\b",
    r"\bpromising (direction|step)\b",
]


def _search(ctx: EvalContext, p: dict, cues: list[str]) -> RuleResult:
    """Limitations and open issues may sit in the Discussion or in the Conclusion."""
    labels = [ctx.section_key, *p.get("also", ["conclusion"])]
    present = [l for l in labels if ctx.text(l)]
    if not present:
        return RuleResult("needs_review", None, 0.0, "Discussion and conclusion were not detected.")
    for label in present:
        hit = find_hit(ctx.text(label), cues)
        if hit:
            return RuleResult("pass", short(hit), 0.7, f"Found in {label}.")
    return RuleResult("fail", None, 0.5, "No cue phrase found.")


@rule("limitations_stated", needs_section=False)
def limitations_stated(ctx: EvalContext, p: dict) -> RuleResult:
    return _search(ctx, p, _LIMITATIONS)


@rule("open_issues_stated", needs_section=False)
def open_issues_stated(ctx: EvalContext, p: dict) -> RuleResult:
    return _search(ctx, p, _OPEN_ISSUES)