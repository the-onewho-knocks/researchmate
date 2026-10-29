from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]  # .../backend


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    # LLM
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    thinking_budget: int = 0
    llm_timeout_s: int = 60

    # Local LLM (LM Studio / Ollama / vLLM, OpenAI-compatible)
    local_llm_enabled: bool = False
    local_llm_base_url: str = "http://localhost:1234/v1"
    local_llm_model: str = "qwen/qwen3-4b-2507"
    local_llm_api_key: str = ""
    local_llm_timeout_s: int = 120
    local_llm_context_max_chars: int = 3500

    # Routing: keep Gemini under its quota and let the local model do the bulk
    gemini_max_calls_per_eval: int = 3
    gemini_max_input_tokens: int = 5000
    gemini_token_share: float = 0.30
    gemini_rpm: int = 10
    gemini_tpm: int = 250_000
    gemini_rpd: int = 250
    gemini_circuit_breaker_s: int = 60
    gemini_escalation_max: int = 3
    local_max_groups_per_call: int = 6
    local_max_tokens_per_call: int = 1800
    routing_version: str = "1"

    # upload limits
    max_upload_mb: int = 20
    max_pages: int = 60

    # ML layer
    ml_enabled: bool = True
    ml_accept_t: float = 0.75
    ml_reject_t: float = 0.25
    embed_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    # storage / cache
    data_dir: Path = BASE_DIR / "data"
    ttl_hours: int = 24
    context_max_chars: int = 6000
    prompt_version: str = "1"

    cors_origins: list[str] = ["http://localhost:5173"]

    # paths
    framework_path: Path = BASE_DIR / "config" / "framework" / "strawberry.v1.yaml"
    schema_path: Path = BASE_DIR / "config" / "framework" / "strawberry.schema.json"
    prompts_dir: Path = BASE_DIR / "config" / "prompts"
    models_dir: Path = BASE_DIR / "models"


@lru_cache
def get_settings() -> Settings:
    return Settings()
