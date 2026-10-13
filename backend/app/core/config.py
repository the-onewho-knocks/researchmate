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
