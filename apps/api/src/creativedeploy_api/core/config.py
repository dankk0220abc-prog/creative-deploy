"""Environment-backed application settings."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

REPOSITORY_ROOT = Path(__file__).resolve().parents[5]
DEFAULT_ENV_FILE = REPOSITORY_ROOT / ".env"


class Settings(BaseSettings):
    """Validated runtime configuration sourced from environment variables."""

    model_config = SettingsConfigDict(
        env_file=DEFAULT_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: str = "development"
    app_name: str = "CreativeDeploy API"
    app_version: str = "0.1.0"
    database_url: SecretStr
    database_health_timeout_seconds: float = Field(default=2.0, gt=0)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached process settings without creating mutable global state."""
    return Settings.model_validate({})
