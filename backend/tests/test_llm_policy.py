"""backend/tests/test_llm_policy.py"""
import json

from app.core.config import get_settings
from app.schemas.report import Usage
from app.schemas.verdict import Verdict
from app.services.framework.loader import load_framework
from app.services.llm.base import LLMResult
from app.services.llm.judge import GroupInput
from app.services.llm.policy import LLMPolicy
from app.services.llm.rate_limit import GeminiQuota
from app.services.orchestrator.merger import Pending

TEMPLATE = "{blocks}\nids: {ids}"
SUGGEST_TEMPLATE = "{items}\nids: {ids}"
SYSTEM = "system"
LOCAL_SYSTEM = "local system"
CONTEXT = "We propose a label-free detector based on isolation trees."


class FakeClient:
    def __init__(self, name: str, model: str, payload=None, available: bool = True):
        self.name = name
        self.model = model
        self._available = available
        self.payload = payload or self._default_payload
        self.calls: list[str] = []

    @property
    def available(self) -> bool:
        return self._available

    @staticmethod
    def _default_payload(prompt: str) -> str:
        raw = prompt.split("ids: ")[-1]
        ids = [i.strip() for i in raw.split(",") if i.strip()]
        return json.dumps(
            [{"id": i, "met": True, "why": "ok", "evidence": None} for i in ids]
        )

    def generate_json(self, system, prompt, schema, max_output_tokens=1200):
        self.calls.append(prompt)
        return LLMResult(self.payload(prompt), 100, 20)

    def generate_text(self, system, prompt, max_output_tokens=400):
        self.calls.append(prompt)
        return LLMResult("feedback", 10, 5)


def _item(fw, key: str, ids: list[str], text: str = CONTEXT) -> GroupInput:
    comp = next(c for c in fw.components if c.key == key)
    pendings = []
    for cid in ids:
        crit = next(c for c in comp.criteria if c.id == cid)
        fallback = Verdict(
            id=cid, component=key, name=crit.name, tier=crit.tier, status="needs_review"
        )
        pendings.append(Pending(crit, key, fallback))
    return GroupInput(comp, pendings, text)


def _setup(tmp_path, **overrides):
    settings = get_settings().model_copy(update={"data_dir": tmp_path, **overrides})
    fw = load_framework(settings.framework_path, settings.schema_path)
    gemini = FakeClient("gemini", "gemini-2.5-flash")
    local = FakeClient("local", "qwen/qwen3-4b-2507")
    quota = GeminiQuota(tmp_path, rpm=100, tpm=10_000_000, rpd=1000)
    policy = LLMPolicy(gemini, local, quota, settings)
    return policy, gemini, local, settings, fw


def _judge(policy, settings, items):
    usage = Usage()
    out = policy.judge(
        items, SYSTEM, LOCAL_SYSTEM, TEMPLATE, usage, settings
    )
    return out, usage


def test_important_components_go_to_gemini(tmp_path):
    policy, gemini, local, settings, fw = _setup(tmp_path)
    items = [_item(fw, "title", ["SP1"]), _item(fw, "methods", ["B2"])]

    out, usage = _judge(policy, settings, items)

    assert out["SP1"].provider == "gemini"
    assert out["B2"].provider == "local"
    assert len(gemini.calls) == 1 and len(local.calls) == 1
    assert usage.by_provider["gemini"].calls == 1
    assert usage.by_provider["local"].calls == 1


def test_tier_b_prefers_gemini(tmp_path):
    policy, gemini, local, settings, fw = _setup(tmp_path)
    items = [_item(fw, "related_work", ["R2"])]          # tier B, not a headline component

    out, _ = _judge(policy, settings, items)

    assert out["R2"].provider == "gemini"
    assert local.calls == []


def test_tier_c_outside_headline_components_stays_local(tmp_path):
    policy, gemini, local, settings, fw = _setup(tmp_path)
    items = [_item(fw, "results", ["E1"])]               # tier C

    out, _ = _judge(policy, settings, items)

    assert out["E1"].provider == "local"
    assert gemini.calls == []


def test_token_budget_pushes_headline_work_to_local(tmp_path):
    policy, gemini, local, settings, fw = _setup(tmp_path, gemini_max_input_tokens=1)
    items = [_item(fw, "title", ["SP1"])]

    out, _ = _judge(policy, settings, items)

    assert gemini.calls == []
    assert out["SP1"].provider == "local"


def test_without_gemini_everything_runs_locally(tmp_path):
    policy, gemini, local, settings, fw = _setup(tmp_path)
    gemini._available = False
    items = [_item(fw, "abstract", ["T3"]), _item(fw, "discussion", ["F6"])]

    out, _ = _judge(policy, settings, items)

    assert {v.provider for v in out.values()} == {"local"}
    assert gemini.calls == []


def test_local_failure_is_escalated_to_gemini(tmp_path):
    policy, gemini, local, settings, fw = _setup(tmp_path)
    local.payload = lambda prompt: "[]"                  # unusable, also after the repair attempt
    items = [_item(fw, "results", ["E1"])]

    out, _ = _judge(policy, settings, items)

    assert out["E1"].provider == "gemini"
    assert len(local.calls) == 2                         # original + one repair
    assert len(gemini.calls) == 1


def test_open_circuit_breaker_skips_gemini(tmp_path):
    policy, gemini, local, settings, fw = _setup(tmp_path)
    policy.quota.trip(60)
    items = [_item(fw, "title", ["SP1"])]

    out, _ = _judge(policy, settings, items)

    assert policy.gemini_available is False
    assert out["SP1"].provider == "local"
    assert gemini.calls == []


def test_unusable_gemini_answer_reroutes_to_local(tmp_path):
    policy, gemini, local, settings, fw = _setup(tmp_path)
    gemini.payload = lambda prompt: "not json"
    items = [_item(fw, "title", ["SP1"]), _item(fw, "abstract", ["T3"])]

    out, _ = _judge(policy, settings, items)

    assert out["SP1"].provider == "local"
    assert out["T3"].provider == "local"
    assert len(gemini.calls) == 2                      # original + one repair
    assert len(local.calls) == 1


def test_suggest_prefers_gemini_then_local(tmp_path):
    policy, gemini, local, settings, fw = _setup(tmp_path)
    crit = fw.components[0].criteria[0]
    verdict = Verdict(id=crit.id, component="title", name=crit.name, tier=crit.tier, status="fail")
    items = [(verdict, crit, CONTEXT)]

    gemini.payload = lambda prompt: json.dumps(
        [{"id": crit.id, "suggestion": "Add a number.", "effort": "low"}]
    )
    usage = Usage()
    out = policy.suggest(SUGGEST_TEMPLATE, items, usage)

    assert out[crit.id][0] == "Add a number."
    assert len(gemini.calls) == 1 and local.calls == []


def test_call_budget_sends_suggestions_to_local(tmp_path):
    policy, gemini, local, settings, fw = _setup(tmp_path, gemini_max_calls_per_eval=0)
    crit = fw.components[0].criteria[0]
    verdict = Verdict(id=crit.id, component="title", name=crit.name, tier=crit.tier, status="fail")
    items = [(verdict, crit, CONTEXT)]

    local.payload = lambda prompt: json.dumps(
        [{"id": crit.id, "suggestion": "Local fix.", "effort": "low"}]
    )
    usage = Usage()
    out = policy.suggest(SUGGEST_TEMPLATE, items, usage)

    assert out[crit.id][0] == "Local fix."
    assert gemini.calls == []
    assert usage.by_provider["local"].calls == 1


def test_cache_key_covers_both_models_and_routing_version(tmp_path):
    policy, _, _, _, _ = _setup(tmp_path, routing_version="7")

    key = policy.cache_key()

    assert "gemini-2.5-flash" in key
    assert "qwen/qwen3-4b-2507" in key
    assert "r7" in key
