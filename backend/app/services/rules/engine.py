"""backend/app/services/rules/engine.py"""
from app.core.errors import FrameworkError
from app.schemas.framework import Criterion, Framework

from .components import (  # noqa: F401  (importing registers the rules)
    abstract,
    bibliography,
    conclusion,
    discussion,
    introduction,
    methods,
    related_work,
    results,
    title,
)
from .primitives import RULES, EvalContext, RuleResult


def run_rule(crit: Criterion, ctx: EvalContext) -> RuleResult | None:
    """Run the rule declared in the YAML. Returns None if the criterion has no rule."""
    spec = RULES.get(crit.rule or "")
    if spec is None:
        return None
    if spec.needs_section and not ctx.section_text():
        return RuleResult("needs_review", None, 0.0, f"Section '{ctx.section_key}' was not detected.")
    try:
        return spec.fn(ctx, crit.params)
    except Exception as exc:  # a broken rule must never crash an evaluation
        return RuleResult("needs_review", None, 0.0, f"Rule error: {exc}")


def validate_rules(fw: Framework) -> None:
    """Fail at startup if the YAML references a rule that does not exist."""
    unknown = sorted({c.rule for c in fw.all_criteria() if c.rule and c.rule not in RULES})
    if unknown:
        raise FrameworkError(f"Unknown rules in framework YAML: {unknown}")