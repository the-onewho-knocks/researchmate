"""backend/app/services/validation/repair.py"""
from app.core.errors import LLMError
from app.schemas.report import Usage


def repair_once(client, system: str, prompt: str, bad_output: str, error: str, schema, max_tokens: int, usage: Usage) -> str | None:
    """One bounded retry that shows the model its own error. Returns the new text or None."""
    fix_prompt = (
        f"{prompt}\n\nYour previous answer was invalid ({error}).\n"
        f"Previous answer:\n{(bad_output or '')[:1500]}\n\n"
        "Return the corrected JSON array only."
    )
    try:
        res = client.generate_json(system, fix_prompt, schema, max_tokens)
    except LLMError:
        return None
    usage.add(res.input_tokens, res.output_tokens)
    return res.text
