"""backend/app/services/framework/compiler.py"""
"""Turn the framework into compact prompt fragments (built once, reused for every call)."""
from app.schemas.framework import Component, Framework


def compile_component(comp: Component, only_ids: set[str] | None = None) -> str:
    lines = [f"## {comp.name} ({comp.acronym})", "Criteria:"]
    for c in comp.criteria:
        if only_ids is not None and c.id not in only_ids:
            continue
        lines.append(f"{c.id} {c.name}: {c.hint}" if c.hint else f"{c.id} {c.name}")
    return "\n".join(lines)


def compile_all(fw: Framework) -> dict[str, str]:
    return {comp.key: compile_component(comp) for comp in fw.components}