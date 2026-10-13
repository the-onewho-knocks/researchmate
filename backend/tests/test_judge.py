"""backend/tests/test_judge.py"""
import json

from app.core.config import get_settings
from app.core.errors import LLMError
from app.schemas.report import Usage
from app.schemas.verdict import Verdict
from app.services.llm.gemini_client import LLMResult
from app.services.llm.judge import GroupInput, build_prompt, judge_group
from app.services.orchestrator.merger import Pending
from app.services.framework.loader import load_framework

TEMPLATE = "{blocks}\nids: {ids}"
CONTEXT = (
    "We propose a label-free detector based on isolation trees. "
    "It needs no failure examples for training."
)


class FakeClient:
    available = True
    model = "fake"

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    def generate_json(self, system, prompt, schema, max_output_tokens=1200):
        self.calls += 1
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return LLMResult(item, 10, 5)


def _group():
    s = get_settings()
    fw = load_framework(s.framework_path, s.schema_path)
    comp = next(c for c in fw.components if c.key == "abstract")
    pendings = []
    for cid in ("T3", "T4"):                        # T3 = tier C, T4 = tier B
        crit = next(c for c in comp.criteria if c.id == cid)
        fb = Verdict(id=cid, component="abstract", name=crit.name, tier=crit.tier, status="needs_review")
        pendings.append(Pending(crit, "abstract", fb))
    return [GroupInput(comp, pendings, CONTEXT)]


def _run(client):
    usage = Usage()
    out = judge_group(client, "system", TEMPLATE, _group(), usage, get_settings())
    return out, usage


def _payload(t3_met=True, t3_ev=None, t4_met=True, t4_ev=None):
    return json.dumps([
        {"id": "T3", "met": t3_met, "why": "ok", "evidence": t3_ev},
        {"id": "T4", "met": t4_met, "why": "ok", "evidence": t4_ev},
    ])


def test_prompt_contains_only_pending_criteria():
    prompt, ids = build_prompt(TEMPLATE, _group())
    assert ids == ["T3", "T4"]
    assert "T3" in prompt and "T4" in prompt and "T1 " not in prompt
    assert CONTEXT in prompt


def test_valid_output_becomes_verdicts():
    client = FakeClient([_payload(True, "We propose a label-free detector based on isolation trees", False, None)])
    out, usage = _run(client)
    assert out["T3"].status == "pass" and out["T3"].source == "llm"
    assert out["T3"].evidence is not None
    assert out["T4"].status == "fail"
    assert usage.calls == 1 and usage.input_tokens == 10


def test_tier_b_met_without_verifiable_quote_needs_review():
    client = FakeClient([_payload(True, None, True, "a sentence that is not in the text at all")])
    out, _ = _run(client)
    assert out["T4"].status == "needs_review"
    assert out["T4"].evidence is None
    assert out["T3"].status == "pass" and out["T3"].confidence < 0.7      # tier C: accepted, lower confidence


def test_invalid_json_is_repaired_once():
    client = FakeClient(["not json at all", _payload(True, None, False, None)])
    out, usage = _run(client)
    assert set(out) == {"T3", "T4"}
    assert client.calls == 2 and usage.calls == 2


def test_still_invalid_after_repair_returns_nothing():
    client = FakeClient(["bad", "still bad"])
    out, _ = _run(client)
    assert out == {}


def test_llm_failure_returns_nothing():
    out, usage = _run(FakeClient([LLMError("boom")]))
    assert out == {} and usage.calls == 0
