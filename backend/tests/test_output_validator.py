"""backend/tests/test_output_validator.py"""
import json

import pytest

from app.core.errors import OutputValidationError
from app.services.validation.output_validator import parse_judge_output

IDS = {"A1", "A2"}


def _items(*ids):
    return [{"id": i, "met": True, "why": "fine", "evidence": None} for i in ids]


def test_valid_array():
    out = parse_judge_output(json.dumps(_items("A1", "A2")), IDS)
    assert {i.id for i in out} == IDS


def test_markdown_fences_are_stripped():
    text = "```json\n" + json.dumps(_items("A1", "A2")) + "\n```"
    assert len(parse_judge_output(text, IDS)) == 2


def test_object_wrapping_the_array():
    text = json.dumps({"results": _items("A1", "A2")})
    assert len(parse_judge_output(text, IDS)) == 2


def test_unknown_ids_are_ignored():
    out = parse_judge_output(json.dumps(_items("A1", "A2", "ZZ")), IDS)
    assert {i.id for i in out} == IDS


def test_missing_ids_raise():
    with pytest.raises(OutputValidationError, match="missing"):
        parse_judge_output(json.dumps(_items("A1")), IDS)


def test_invalid_json_raises():
    with pytest.raises(OutputValidationError):
        parse_judge_output("{oops", IDS)


def test_wrong_shape_raises():
    with pytest.raises(OutputValidationError):
        parse_judge_output(json.dumps([{"id": "A1"}, {"id": "A2"}]), IDS)   # no "met"
    with pytest.raises(OutputValidationError):
        parse_judge_output(json.dumps({"a": 1}), IDS)
