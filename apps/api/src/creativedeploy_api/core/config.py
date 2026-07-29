"""Environment-backed application settings."""

from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, SecretStr, StringConstraints
from pydantic_settings import BaseSettings, SettingsConfigDict

REPOSITORY_ROOT = Path(__file__).resolve().parents[5]
DEFAULT_ENV_FILE = REPOSITORY_ROOT / ".env"
DEFAULT_IMAGE_STORAGE_ROOT = REPOSITORY_ROOT / ".local" / "private-image-storage"
DEFAULT_DATABASE_LOCK_TIMEOUT_MS = 2_000
DEFAULT_DATABASE_STATEMENT_TIMEOUT_MS = 5_000
MAX_DATABASE_TRANSACTION_TIMEOUT_MS = 60_000
DEFAULT_IMAGE_MAX_BYTES = 20 * 1024 * 1024
DEFAULT_IMAGE_MIN_SIDE_PX = 768
DEFAULT_IMAGE_MAX_SIDE_PX = 8_192
DEFAULT_IMAGE_MAX_PIXELS = 40_000_000
AppEnvironment = Literal["development", "test", "production"]
ImageStorageProvider = Literal["local_filesystem"]
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
    image_storage_provider: ImageStorageProvider = "local_filesystem"
    image_storage_root: Path = DEFAULT_IMAGE_STORAGE_ROOT
    image_upload_max_bytes: int = Field(
        default=DEFAULT_IMAGE_MAX_BYTES,
        gt=0,
        le=DEFAULT_IMAGE_MAX_BYTES,
    )
    image_min_side_px: int = Field(
        default=DEFAULT_IMAGE_MIN_SIDE_PX,
        ge=DEFAULT_IMAGE_MIN_SIDE_PX,
        le=DEFAULT_IMAGE_MAX_SIDE_PX,
    )
    image_max_side_px: int = Field(
        default=DEFAULT_IMAGE_MAX_SIDE_PX,
        ge=DEFAULT_IMAGE_MIN_SIDE_PX,
        le=DEFAULT_IMAGE_MAX_SIDE_PX,
    )
    image_max_pixels: int = Field(
        default=DEFAULT_IMAGE_MAX_PIXELS,
        gt=0,
        le=DEFAULT_IMAGE_MAX_PIXELS,
    )

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

    def require_local_image_storage(self) -> Path:
        """Return the private local root only in explicitly non-production runtimes."""
        if self.app_env is None:
            raise ValueError("APP_ENV must be explicitly configured.")
        if self.app_env == "production":
            raise ValueError(
                "LocalFilesystemImageStorageAdapter is NOT_FOR_PRODUCTION_OBJECT_STORAGE."
            )
        if self.image_storage_provider != "local_filesystem":
            raise ValueError("No approved production image storage provider is configured.")
        if self.image_min_side_px > self.image_max_side_px:
            raise ValueError("IMAGE_MIN_SIDE_PX must not exceed IMAGE_MAX_SIDE_PX.")
        return self.image_storage_root.expanduser().resolve(strict=False)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached process settings without creating mutable global state."""
    return Settings.model_validate({})
