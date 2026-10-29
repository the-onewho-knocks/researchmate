"""backend/app/api/deps.py"""
from functools import lru_cache

from app.core.config import Settings, get_settings
from app.services.cache.result_cache import ResultCache
from app.services.framework.loader import get_framework
from app.services.llm.gemini_client import GeminiClient
from app.services.llm.local_client import LocalClient
from app.services.llm.policy import LLMPolicy
from app.services.llm.rate_limit import GeminiQuota
from app.services.ml.embedder import get_embedder
from app.services.ml.section_classifier import SectionClassifier
from app.services.ml.sentence_roles import SentenceRoleModel
from app.services.orchestrator.pipeline import Services
from app.services.rules.engine import validate_rules
from app.services.upload.storage import UploadStorage


def _read_prompt(path, fallback: str = "") -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return fallback


def build_services(settings: Settings | None = None) -> Services:
    s = settings or get_settings()

    fw = get_framework(str(s.framework_path), str(s.schema_path))
    validate_rules(fw)                       # fail at startup, not on the first upload

    embedder = get_embedder(s)
    prompts = s.prompts_dir

    gemini = GeminiClient(s.gemini_api_key, s.gemini_model, s.llm_timeout_s, s.thinking_budget)
    local = LocalClient(
        s.local_llm_base_url,
        s.local_llm_model,
        s.local_llm_api_key,
        s.local_llm_timeout_s,
        enabled=s.local_llm_enabled,
    )
    quota = GeminiQuota(s.data_dir, s.gemini_rpm, s.gemini_tpm, s.gemini_rpd)
    llm = LLMPolicy(gemini, local, quota, s)

    system_prompt = _read_prompt(prompts / "judge_system.md")
    local_system_prompt = _read_prompt(prompts / "judge_local_system.md", system_prompt)

    return Services(
        settings=s,
        framework=fw,
        llm=llm,
        roles=SentenceRoleModel(embedder, s.models_dir),
        section_clf=SectionClassifier(embedder, s.models_dir),
        storage=UploadStorage(s.data_dir / "uploads", s.ttl_hours),
        cache=ResultCache(s.data_dir, s.ttl_hours),
        system_prompt=system_prompt,
        judge_template=_read_prompt(prompts / "judge_criterion.md"),
        coach_template=_read_prompt(prompts / "coach.md"),
        suggest_template=_read_prompt(prompts / "suggest.md"),
        local_system_prompt=local_system_prompt,
    )


@lru_cache
def get_services() -> Services:
    return build_services()
