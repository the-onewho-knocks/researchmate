"""backend/app/api/deps.py"""
from functools import lru_cache

from app.core.config import Settings, get_settings
from app.services.cache.result_cache import ResultCache
from app.services.framework.loader import get_framework
from app.services.llm.gemini_client import GeminiClient
from app.services.ml.embedder import get_embedder
from app.services.ml.section_classifier import SectionClassifier
from app.services.ml.sentence_roles import SentenceRoleModel
from app.services.orchestrator.pipeline import Services
from app.services.rules.engine import validate_rules
from app.services.upload.storage import UploadStorage


def build_services(settings: Settings | None = None) -> Services:
    s = settings or get_settings()

    fw = get_framework(str(s.framework_path), str(s.schema_path))
    validate_rules(fw)                       # fail at startup, not on the first upload

    embedder = get_embedder(s)
    prompts = s.prompts_dir

    return Services(
        settings=s,
        framework=fw,
        llm=GeminiClient(s.gemini_api_key, s.gemini_model, s.llm_timeout_s, s.thinking_budget),
        roles=SentenceRoleModel(embedder, s.models_dir),
        section_clf=SectionClassifier(embedder, s.models_dir),
        storage=UploadStorage(s.data_dir / "uploads", s.ttl_hours),
        cache=ResultCache(s.data_dir, s.ttl_hours),
        system_prompt=(prompts / "judge_system.md").read_text(encoding="utf-8"),
        judge_template=(prompts / "judge_criterion.md").read_text(encoding="utf-8"),
        coach_template=(prompts / "coach.md").read_text(encoding="utf-8"),
    )


@lru_cache
def get_services() -> Services:
    return build_services()