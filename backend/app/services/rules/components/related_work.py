"""backend/app/services/rules/components/related_work.py"""
import re

from ..primitives import EvalContext, RuleResult, rule, short, split_sentences

_OWN = re.compile(r"\b(our|ours|we|this (?:paper|work|study|article)|the present (?:paper|work|study))\b", re.I)
_CONTRAST = re.compile(
    r"\bin contrast\b|\bunlike\b|\bdiffer(?:s|ent)?\b|\bcompared (?:to|with)\b|\bwhereas\b|\bwhile\b"
    r"|\bclosest to\b|\bdistinguish|\bgoes? beyond\b|\bin comparison\b|\bbuilds? on\b|\bextends?\b",
    re.I,
)


@rule("contrast_with_own_work")
def contrast_with_own_work(ctx: EvalContext, p: dict) -> RuleResult:
    """A sentence that mentions the own work AND a contrast cue."""
    for s in split_sentences(ctx.section_text()):
        if _OWN.search(s) and _CONTRAST.search(s):
            return RuleResult("pass", short(s), 0.7)
    return RuleResult("fail", None, 0.5, "No sentence contrasts previous work with the own work.")
