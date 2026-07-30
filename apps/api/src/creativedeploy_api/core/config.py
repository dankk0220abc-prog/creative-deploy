"""Environment-backed application settings."""

import os
from functools import lru_cache
from ipaddress import ip_address
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, SecretStr, StringConstraints, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import ArgumentError

REPOSITORY_ROOT = Path(__file__).resolve().parents[5]
DEFAULT_ENV_FILE = (
    Path(os.environ.get("CREATIVEDEPLOY_ENV_FILE", REPOSITORY_ROOT / ".env"))
    .expanduser()
    .resolve(strict=False)
)
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
PostgresComponentSetting = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=128),
]
TrustedHostSetting = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=253),
]
POSTGRES_COMPONENT_NAMES = (
    "POSTGRES_HOST",
    "POSTGRES_PORT",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "POSTGRES_DB",
)
DATABASE_DRIVER = "postgresql+psycopg"


def canonical_trusted_host(value: str) -> str:
    """Return one exact, port-free host allowlist entry."""
    candidate = value.strip()
    if not candidate or "*" in candidate:
        raise ValueError("TRUSTED_HOSTS entries must be non-empty exact hosts without wildcards.")
    if any(character.isspace() for character in candidate):
        raise ValueError("TRUSTED_HOSTS entries must not contain whitespace.")
    if candidate.startswith("["):
        if not candidate.endswith("]"):
            raise ValueError("TRUSTED_HOSTS contains an invalid bracketed IPv6 host.")
        candidate = candidate[1:-1]
    elif candidate.count(":") == 1:
        raise ValueError("TRUSTED_HOSTS entries must not include ports.")

    try:
        return ip_address(candidate).compressed.lower()
    except ValueError:
        pass

    if ":" in candidate:
        raise ValueError("TRUSTED_HOSTS contains an invalid IPv6 host.")
    dns_name = candidate.removesuffix(".")
    if not dns_name:
        raise ValueError("TRUSTED_HOSTS contains an invalid host.")
    try:
        ascii_name = dns_name.encode("idna").decode("ascii").lower()
    except UnicodeError as error:
        raise ValueError("TRUSTED_HOSTS contains an invalid DNS host.") from error
    if len(ascii_name) > 253:
        raise ValueError("TRUSTED_HOSTS contains an overlong DNS host.")
    labels = ascii_name.split(".")
    if any(
        not label
        or len(label) > 63
        or label.startswith("-")
        or label.endswith("-")
        or not all(character.isalnum() or character == "-" for character in label)
        for label in labels
    ):
        raise ValueError("TRUSTED_HOSTS contains an invalid DNS host.")
    return ascii_name


def _validated_database_url(secret: SecretStr) -> URL:
    raw_url = secret.get_secret_value()
    if not raw_url or raw_url != raw_url.strip():
        raise ValueError("DATABASE_URL must be a non-empty value without surrounding whitespace.")
    try:
        database_url = make_url(raw_url)
    except ArgumentError as error:
        raise ValueError("DATABASE_URL must be a valid PostgreSQL SQLAlchemy URL.") from error
    if database_url.drivername != DATABASE_DRIVER:
        raise ValueError(f"DATABASE_URL must use the {DATABASE_DRIVER} scheme.")
    if not database_url.host or not database_url.database:
        raise ValueError("DATABASE_URL must include an explicit host and database name.")
    return database_url


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
    database_url: SecretStr | None = None
    postgres_host: PostgresComponentSetting | None = None
    postgres_port: int | None = Field(default=None, ge=1, le=65_535)
    postgres_user: PostgresComponentSetting | None = None
    postgres_password: SecretStr | None = None
    postgres_db: PostgresComponentSetting | None = None
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
    trusted_hosts: list[TrustedHostSetting] = Field(
        default_factory=lambda: ["localhost", "127.0.0.1", "testserver"]
    )

    @model_validator(mode="after")
    def resolve_database_configuration(self) -> "Settings":
        """Use one local PostgreSQL source and reject partial or drifted input."""
        supplied_database_url = self.database_url
        if supplied_database_url is not None:
            explicit_database_url = _validated_database_url(supplied_database_url)
        else:
            explicit_database_url = None
        if self.app_env == "production" and explicit_database_url is None:
            raise ValueError("Production requires an explicitly provided DATABASE_URL.")

        local_components = (
            self.postgres_host,
            self.postgres_port,
            self.postgres_user,
            self.postgres_password,
            self.postgres_db,
        )
        configured_components = sum(value is not None for value in local_components)
        if configured_components not in (0, len(local_components)):
            raise ValueError(f"{', '.join(POSTGRES_COMPONENT_NAMES)} must be configured together.")
        if (
            self.postgres_password is not None
            and not self.postgres_password.get_secret_value().strip()
        ):
            raise ValueError("POSTGRES_PASSWORD must not be empty or whitespace.")
        if configured_components == len(local_components):
            assert self.postgres_host is not None
            assert self.postgres_port is not None
            assert self.postgres_user is not None
            assert self.postgres_password is not None
            assert self.postgres_db is not None
            derived_url = URL.create(
                drivername=DATABASE_DRIVER,
                username=self.postgres_user,
                password=self.postgres_password.get_secret_value(),
                host=self.postgres_host,
                port=self.postgres_port,
                database=self.postgres_db,
            )
            if explicit_database_url is not None and explicit_database_url != derived_url:
                raise ValueError(
                    "DATABASE_URL conflicts with the local POSTGRES_* configuration. "
                    "Remove DATABASE_URL or make it exactly match the derived local URL."
                )
            if explicit_database_url is None:
                self.database_url = SecretStr(derived_url.render_as_string(hide_password=False))
        if self.database_url is None:
            raise ValueError(
                "Configure DATABASE_URL, or configure the complete local POSTGRES_* set."
            )
        if not self.trusted_hosts:
            raise ValueError("TRUSTED_HOSTS must contain at least one exact host.")
        normalized_hosts = [canonical_trusted_host(host) for host in self.trusted_hosts]
        if len(set(normalized_hosts)) != len(normalized_hosts):
            raise ValueError("TRUSTED_HOSTS must not contain duplicate normalized hosts.")
        self.trusted_hosts = normalized_hosts
        return self

    @property
    def database_configuration_source(self) -> Literal["database_url", "local_postgres"]:
        """Describe the selected non-secret settings source."""
        return "local_postgres" if self.postgres_user is not None else "database_url"

    def require_database_url(self) -> SecretStr:
        """Return the database URL after source reconciliation."""
        if self.database_url is None:
            raise ValueError("Database configuration was not resolved.")
        return self.database_url

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
