"""backend/app/services/rules/components/methods.py"""
import re

from ..primitives import EvalContext, RuleResult, rule

_CATEGORIES = {
    "data": r"\b(dataset|data set|corpus|samples?|participants|subjects)\b",
    "parameters": r"\b(hyper-?parameters?|learning rate|epochs?|batch size|threshold|temperature|seed)\b",
    "code": r"\b(github|gitlab|source code|open[- ]source|repository|code is available|supplementary)\b",
    "setup": r"\b(implemented|library|version|setup|configured|split|software|hardware)\b",
}


@rule("methods_reproducibility_cues")
def methods_reproducibility_cues(ctx: EvalContext, p: dict) -> RuleResult:
    text = ctx.section_text()
    found = [name for name, rx in _CATEGORIES.items() if re.search(rx, text, re.I)]
    if len(found) >= 2:
        return RuleResult("pass", "Cues found: " + ", ".join(found), 0.6)
    return RuleResult("fail", None, 0.5, "Few reproducibility cues (data, parameters, code, setup).")
