"""backend/app/services/rules/components/conclusion.py"""
from ..primitives import EvalContext, RuleResult, find_hit, rule, short

_CUES = {
    "research_summary": [
        r"\bin this (paper|work|study|article)\b",
        r"\bwe (proposed|presented|introduced|developed|derived|investigated|showed)\b",
        r"\bthis (paper|work|study) (proposed|presented|introduced|investigated)\b",
    ],
    "insights": [
        r"\bwe conclude\b",
        r"\bour (results|findings|evaluation|experiments)\b",
        r"\b(findings|insights|results) (show|indicate|suggest|demonstrate)\b",
        r"\bdemonstrate[sd]?\b",
        r"\bshow(s|ed)? that\b",
        r"\binsights?\b",
    ],
    "new_research": [
        r"\bfuture (work|research|studies|directions)\b",
        r"\bopen (issues|questions|problems)\b",
        r"\bfurther (research|work|investigation|studies)\b",
        r"\bwill (extend|investigate|explore|address)\b",
        r"\bpromising (direction|step)\b",
    ],
}


@rule("conclusion_item")
def conclusion_item(ctx: EvalContext, p: dict) -> RuleResult:
    item = p.get("item", "")
    cues = _CUES.get(item)
    if cues is None:
        return RuleResult("needs_review", None, 0.0, f"Unknown conclusion item '{item}'.")
    hit = find_hit(ctx.section_text(), cues)
    if hit:
        return RuleResult("pass", short(hit), 0.7)
    return RuleResult("fail", None, 0.5, "No cue phrase found.")
