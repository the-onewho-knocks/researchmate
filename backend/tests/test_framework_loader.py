"""backend/tests/test_framework_loader.py"""
import pytest

from app.core.config import get_settings
from app.core.errors import FrameworkError
from app.services.framework.compiler import compile_component
from app.services.framework.loader import load_framework
from app.services.rules.engine import validate_rules


def _load():
    s = get_settings()
    return load_framework(s.framework_path, s.schema_path)


def test_framework_has_nine_components_with_unique_ids():
    fw = _load()
    assert [c.acronym for c in fw.components] == [
        "SPICE", "The-5-S", "RICK", "WHWN", "BURNS", "ELVIRA", "REFLOW", "RIB", "YEAR",
    ]
    ids = [c.id for c in fw.all_criteria()]
    assert len(ids) == len(set(ids))


def test_every_rule_in_the_yaml_exists():
    validate_rules(_load())     # raises FrameworkError if a rule is unknown


def test_unknown_rule_is_detected():
    fw = _load()
    fw.components[0].criteria[3].rule = "does_not_exist"
    with pytest.raises(FrameworkError):
        validate_rules(fw)


def test_invalid_yaml_is_rejected(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text('version: "1"\n', encoding="utf-8")        # no components
    with pytest.raises(FrameworkError):
        load_framework(bad, get_settings().schema_path)


def test_tier_a_criteria_need_a_rule(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        'version: "1"\ncomponents:\n- {key: t, name: T, acronym: T, section: title, '
        'criteria: [{id: X1, name: Foo, tier: A}]}\n',
        encoding="utf-8",
    )
    with pytest.raises(FrameworkError):
        load_framework(bad, get_settings().schema_path)


def test_compiler_outputs_compact_block():
    comp = _load().components[1]
    text = compile_component(comp)
    assert text.startswith("## Abstract (The-5-S)")
    assert "T1 Short" in text and "T5 " in text
    only = compile_component(comp, {"T3"})
    assert "T3" in only and "T1" not in only
