"""Application configuration loaded from environment variables.

All settings come from the environment (or a local `.env` file). Secrets are
never hardcoded. See `.env.example` for the full list.
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # App
    app_name: str = "tourist-safety"
    env: str = "local"
    log_level: str = "INFO"
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # Postgres
    postgres_user: str = "tourist"
    postgres_password: str = "tourist"
    postgres_db: str = "tourist_safety"
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0

    # LLM (provider-agnostic; Groq by default). Used from M4 onward.
    llm_provider: str = "groq"
    llm_base_url: str = "https://api.groq.com/openai/v1"
    llm_api_key: str = ""
    llm_model: str = "llama-3.3-70b-versatile"
    llm_dry_run: bool = True

    # DPDP retention
    location_retention_days: int = Field(default=30, ge=1)

    # ML — area-risk model artifact path (joblib bundle).
    risk_model_path: str = "models/area_risk_model.joblib"

    @property
    def database_url(self) -> str:
        """SQLAlchemy URL using the psycopg (v3) driver."""
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def redis_url(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    @property
    def llm_enabled(self) -> bool:
        """LLM is live only when not in dry-run and a key is present."""
        return bool(self.llm_api_key) and not self.llm_dry_run


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()
