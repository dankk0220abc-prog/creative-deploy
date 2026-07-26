"""Environment-backed application settings."""

from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, SecretStr, StringConstraints
from pydantic_settings import BaseSettings, SettingsConfigDict

REPOSITORY_ROOT = Path(__file__).resolve().parents[5]
DEFAULT_ENV_FILE = REPOSITORY_ROOT / ".env"
DEFAULT_DATABASE_LOCK_TIMEOUT_MS = 2_000
DEFAULT_DATABASE_STATEMENT_TIMEOUT_MS = 5_000
MAX_DATABASE_TRANSACTION_TIMEOUT_MS = 60_000
AppEnvironment = Literal["development", "test", "production"]
PrincipalIdSetting = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=128),
]
PrincipalDisplayNameSetting = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
]


class Settings(BaseSettings):
    """Validated runtime configuration sourced from environment variables."""

    model_config = SettingsConfigDict(
        env_file=DEFAULT_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: AppEnvironment | None = None
    app_name: str = "CreativeDeploy API"
    app_version: str = "0.1.0"
    database_url: SecretStr
    database_health_timeout_seconds: float = Field(default=2.0, gt=0)
    database_lock_timeout_ms: int = Field(
        default=DEFAULT_DATABASE_LOCK_TIMEOUT_MS,
        gt=0,
        le=MAX_DATABASE_TRANSACTION_TIMEOUT_MS,
    )
    database_statement_timeout_ms: int = Field(
        default=DEFAULT_DATABASE_STATEMENT_TIMEOUT_MS,
        gt=0,
        le=MAX_DATABASE_TRANSACTION_TIMEOUT_MS,
    )
    paintpilot_demo_principal_id: PrincipalIdSetting | None = None
    paintpilot_demo_principal_display_name: PrincipalDisplayNameSetting | None = None

    def require_configured_demo_principal(self) -> tuple[str, str]:
        """Return an explicitly configured non-production demo identity or fail closed."""
        if self.app_env is None:
            raise ValueError("APP_ENV must be explicitly configured.")
        if self.app_env == "production":
            raise ValueError("The configured Demo Principal Adapter is unavailable in production.")
        if self.paintpilot_demo_principal_id is None:
            raise ValueError("PAINTPILOT_DEMO_PRINCIPAL_ID must be explicitly configured.")
        if self.paintpilot_demo_principal_display_name is None:
            raise ValueError(
                "PAINTPILOT_DEMO_PRINCIPAL_DISPLAY_NAME must be explicitly configured."
            )
        return (
            self.paintpilot_demo_principal_id,
            self.paintpilot_demo_principal_display_name,
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached process settings without creating mutable global state."""
    return Settings.model_validate({})
