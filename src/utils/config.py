"""Configuration management using Pydantic Settings."""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Environment
    environment: Literal["development", "staging", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    rate_limit_per_minute: int = 100

    # LLM Configuration
    anthropic_api_key: str = Field(default="", description="Anthropic API key for Claude")
    openai_api_key: str = Field(default="", description="OpenAI API key (fallback)")

    # LangSmith Observability
    langchain_api_key: str = Field(default="", description="LangSmith API key")
    langchain_tracing_v2: bool = True
    langchain_project: str = "ghostfolio-agent"

    # Ghostfolio Configuration
    ghostfolio_api_url: str = "http://localhost:3333"
    ghostfolio_access_token: str = Field(default="", description="Ghostfolio access token")
    use_mock_data: bool = False

    # External APIs
    yahoo_finance_enabled: bool = True
    coingecko_api_key: str = Field(default="", description="CoinGecko Pro API key")

    # Cache Configuration
    cache_ttl_seconds: int = 300
    redis_url: str | None = None

    # Security
    secret_key: str = Field(default="change-me-in-production", description="Secret key for sessions")
    cors_origins: str = "http://localhost:3000,http://localhost:8501"

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse CORS origins as a list."""
        return [origin.strip() for origin in self.cors_origins.split(",")]

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
