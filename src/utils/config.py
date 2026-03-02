"""Configuration management using Pydantic Settings."""

from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve .env relative to project root (directory containing src/), not CWD.
# config.py lives at src/utils/config.py -> parent.parent = src, parent.parent.parent = project root.
# This ensures the key is loaded whether the process is started from repo root,
# frontend/, or any other directory (e.g. IDE, uvicorn from different cwd).
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_ENV_FILE = _PROJECT_ROOT / ".env"


def _read_env_key(key: str) -> str:
    """Read a single key from .env at project root (no extra deps). Used as fallback if pydantic didn't load it."""
    if not _ENV_FILE.exists():
        return ""
    try:
        for line in _ENV_FILE.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            if k.strip() == key:
                return v.strip().strip('"').strip("'").strip()
    except OSError:
        pass
    return ""


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @model_validator(mode="before")
    @classmethod
    def _inject_openai_key_from_env_file(cls, data: Any) -> Any:
        """Prefer OPENAI_API_KEY from .env when present, so .env wins over stale/empty process env."""
        if not isinstance(data, dict):
            return data
        from_env_file = _read_env_key("OPENAI_API_KEY") if _ENV_FILE.exists() else ""
        # Prefer .env when it has a value so it wins over empty or stale process OPENAI_API_KEY
        if from_env_file:
            data = {**data, "openai_api_key": from_env_file}
        # Prefer .env for use_mock_data so local .env wins over process env (e.g. USE_MOCK_DATA=true in shell)
        use_mock_raw = _read_env_key("USE_MOCK_DATA") if _ENV_FILE.exists() else ""
        if use_mock_raw:
            data = {**data, "use_mock_data": use_mock_raw}
        # Prefer .env for Ghostfolio so evals and local runs always see .env (process env can override and empty the token)
        if _ENV_FILE.exists():
            gf_token = _read_env_key("GHOSTFOLIO_ACCESS_TOKEN")
            if gf_token:
                data = {**data, "ghostfolio_access_token": gf_token}
            gf_url = _read_env_key("GHOSTFOLIO_API_URL")
            if gf_url:
                data = {**data, "ghostfolio_api_url": gf_url}
        return data

    # Environment
    environment: Literal["development", "staging", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    rate_limit_per_minute: int = 100

    # LLM Configuration
    openai_api_key: str = Field(default="", description="OpenAI API key (required)")

    @field_validator("openai_api_key", mode="after")
    @classmethod
    def _strip_openai_key(cls, v: str) -> str:
        """Strip whitespace so key from .env (e.g. trailing newline) is not sent to OpenAI."""
        return (v or "").strip()

    anthropic_api_key: str = Field(default="", description="Anthropic API key (optional fallback)")

    # LangSmith Observability (new format)
    langsmith_tracing: bool = True
    langsmith_endpoint: str = "https://api.smith.langchain.com"
    langsmith_api_key: str = Field(default="", description="LangSmith API key")
    langsmith_project: str = "AgentForge"
    langsmith_workspace_id: str = Field(default="", description="LangSmith workspace ID for org-scoped keys")

    # Ghostfolio Configuration
    ghostfolio_api_url: str = "http://localhost:3333"
    ghostfolio_access_token: str = Field(default="", description="Ghostfolio access token")
    use_mock_data: bool = False

    @field_validator("use_mock_data", mode="before")
    @classmethod
    def _coerce_use_mock_data(cls, v: Any) -> bool:
        """Ensure env string 'false'/'true' is parsed as bool (env vars are strings)."""
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            return v.strip().lower() in ("true", "1", "yes")
        return bool(v)

    # External APIs
    yahoo_finance_enabled: bool = True
    coingecko_api_key: str = Field(default="", description="CoinGecko Pro API key")

    # Cache Configuration
    cache_ttl_seconds: int = 300
    redis_url: str | None = None

    # Security
    secret_key: str = Field(default="change-me-in-production", description="Secret key for sessions")
    cors_origins: str = Field(
        default="http://localhost:3000,http://localhost:5173,http://localhost:8501",
        description="Comma-separated CORS origins. For Railway, add your frontend URL.",
    )
    cors_origin_regex: str | None = Field(
        default="https://.*\\.up\\.railway\\.app",
        description="Regex for dynamic origins (e.g. Railway). Set empty to disable.",
    )

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse CORS origins as a list."""
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.environment == "development"

    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
