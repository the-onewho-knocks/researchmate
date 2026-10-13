"""backend/app/services/validation/output_validator.py"""
import json
import re

from pydantic import BaseModel, ValidationError

from app.core.errors import OutputValidationError

_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.I)


class JudgeItem(BaseModel):
    id: str
    met: bool
    why: str | None = ""
    evidence: str | None = None


def parse_judge_output(text: str, expected_ids: set[str]) -> list[JudgeItem]:
    """Parse and validate the model output. Raises OutputValidationError with a message
    that is fed back to the model for the one repair attempt."""
    cleaned = _FENCE.sub("", (text or "").strip())
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise OutputValidationError(f"not valid JSON ({exc.msg})") from exc

    if isinstance(data, dict):
        for key in ("results", "items", "criteria"):
            if isinstance(data.get(key), list):
                data = data[key]
                break
    if not isinstance(data, list):
        raise OutputValidationError("expected a JSON array with one object per criterion id")

    items: dict[str, JudgeItem] = {}
    for raw in data:
        try:
            item = JudgeItem(**raw)
        except (ValidationError, TypeError) as exc:
            raise OutputValidationError(f"an item has the wrong shape: {exc}") from exc
        if item.id in expected_ids:          # unknown ids are ignored
            items[item.id] = item

    missing = sorted(expected_ids - set(items))
    if missing:
        raise OutputValidationError(f"missing criterion ids: {missing}")
    return list(items.values())