"""backend/app/services/llm/coach.py"""
from app.core.errors import LLMError
from app.schemas.report import Usage
from app.schemas.verdict import Verdict

from .gemini_client import GeminiClient

SYSTEM = "You are a concise, kind writing coach for student authors."


def write_feedback(client: GeminiClient, template: str, verdicts: list[Verdict], usage: Usage) -> str | None:
    """Optional last step: turn failing items into short, prioritized feedback."""
    if not client.available:
        return None
    items = [v for v in verdicts if v.status in ("fail", "needs_review")]
    if not items:
        return None
    items.sort(key=lambda v: 0 if v.status == "fail" else 1)

    lines = [
        f"- {v.component} / {v.name} [{v.status}]: {v.note or v.evidence or 'no detail'}"
        for v in items[:12]
    ]
    prompt = template.format(items="\n".join(lines))
    try:
        res = client.generate_text(SYSTEM, prompt, max_output_tokens=400)
    except LLMError:
        return None
    usage.add(res.input_tokens, res.output_tokens)
    return res.text.strip() or None