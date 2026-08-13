"""Environment-backed application settings."""

import os
from functools import lru_cache
from ipaddress import ip_address
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import urlparse

from pydantic import Field, SecretStr, StringConstraints, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import ArgumentError

from creativedeploy_api.core.secret_files import read_secret_file

REPOSITORY_ROOT = Path(__file__).resolve().parents[5]
DEFAULT_ENV_FILE = (
    Path(os.environ.get("CREATIVEDEPLOY_ENV_FILE", REPOSITORY_ROOT / ".env"))
    .expanduser()
    .resolve(strict=False)
)
DEFAULT_IMAGE_STORAGE_ROOT = REPOSITORY_ROOT / ".local" / "private-image-storage"
DEFAULT_S3_STAGING_ROOT = REPOSITORY_ROOT / ".local" / "s3-upload-staging"
DEFAULT_DATABASE_LOCK_TIMEOUT_MS = 2_000
DEFAULT_DATABASE_STATEMENT_TIMEOUT_MS = 5_000
MAX_DATABASE_TRANSACTION_TIMEOUT_MS = 60_000
DEFAULT_OIDC_ID_TOKEN_MAX_AGE_SECONDS = 300
MAX_OIDC_ID_TOKEN_MAX_AGE_SECONDS = 900
DEFAULT_OIDC_CLOCK_SKEW_SECONDS = 30
MAX_OIDC_CLOCK_SKEW_SECONDS = 60
DEFAULT_IMAGE_MAX_BYTES = 20 * 1024 * 1024
DEFAULT_IMAGE_MIN_SIDE_PX = 768
DEFAULT_IMAGE_MAX_SIDE_PX = 8_192
DEFAULT_IMAGE_MAX_PIXELS = 40_000_000
AppEnvironment = Literal["development", "test", "production"]
ImageStorageProvider = Literal["local_filesystem", "s3"]
IdentityProvider = Literal["configured_demo", "oidc"]
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
    database_url_file: Path | None = None
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
    identity_provider: IdentityProvider = "configured_demo"
    oidc_issuer: str | None = None
    oidc_discovery_url: str | None = None
    oidc_backchannel_base_url: str | None = None
    oidc_client_id: str | None = None
    oidc_client_secret: SecretStr | None = None
    oidc_client_secret_file: Path | None = None
    oidc_redirect_uri: str | None = None
    oidc_http_timeout_seconds: float = Field(default=5.0, gt=0, le=30)
    oidc_id_token_max_age_seconds: int = Field(
        default=DEFAULT_OIDC_ID_TOKEN_MAX_AGE_SECONDS,
        ge=60,
        le=MAX_OIDC_ID_TOKEN_MAX_AGE_SECONDS,
    )
    oidc_clock_skew_seconds: int = Field(
        default=DEFAULT_OIDC_CLOCK_SKEW_SECONDS,
        ge=0,
        le=MAX_OIDC_CLOCK_SKEW_SECONDS,
    )
    auth_session_ttl_seconds: int = Field(default=28_800, ge=300, le=86_400)
    oidc_login_ttl_seconds: int = Field(default=300, ge=60, le=600)
    image_storage_provider: ImageStorageProvider = "local_filesystem"
    image_storage_root: Path = DEFAULT_IMAGE_STORAGE_ROOT
    s3_endpoint_url: str | None = None
    s3_region: str | None = None
    s3_bucket: str | None = None
    s3_access_key_id: SecretStr | None = None
    s3_access_key_id_file: Path | None = None
    s3_secret_access_key: SecretStr | None = None
    s3_secret_access_key_file: Path | None = None
    s3_force_path_style: bool = True
    s3_allow_insecure_http: bool = False
    s3_create_bucket: bool = False
    s3_staging_root: Path = DEFAULT_S3_STAGING_ROOT
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
    public_origin: str | None = None
    secure_cookies: bool = False
    require_csrf_origin: bool = False
    structured_logs: bool = False
    paintpilot_demo_read_only: bool = False
    paintpilot_demo_seed_enabled: bool = False
    paintpilot_demo_seed_subject: PrincipalIdSetting | None = None
    paintpilot_demo_seed_display_name: PrincipalDisplayNameSetting | None = None
    paintpilot_demo_seed_email: str | None = None
    phase3a_fixture_enabled: bool = False
    phase3b_paint_plan_enabled: bool = False
    zhipu_live_enabled: bool = False
    credential_fixture_root_key_file: Path | None = None
    staging_run_id: str | None = None

    @model_validator(mode="after")
    def load_mounted_secrets(self) -> "Settings":
        """Resolve supported direct-or-file secrets with an exact one-source rule."""
        secret_pairs = (
            ("DATABASE_URL", "database_url", "database_url_file"),
            ("OIDC_CLIENT_SECRET", "oidc_client_secret", "oidc_client_secret_file"),
            ("S3_ACCESS_KEY_ID", "s3_access_key_id", "s3_access_key_id_file"),
            ("S3_SECRET_ACCESS_KEY", "s3_secret_access_key", "s3_secret_access_key_file"),
        )
        for setting_name, value_field, file_field in secret_pairs:
            direct_value = getattr(self, value_field)
            file_path = getattr(self, file_field)
            if direct_value is not None and file_path is not None:
                raise ValueError(f"Configure exactly one of {setting_name} or {setting_name}_FILE.")
            if file_path is not None:
                object.__setattr__(
                    self,
                    value_field,
                    SecretStr(read_secret_file(file_path, setting_name=setting_name)),
                )
                object.__setattr__(self, file_field, None)
        return self

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
        if self.public_origin is not None:
            if self.public_origin != self.public_origin.strip() or "*" in self.public_origin:
                raise ValueError("PUBLIC_ORIGIN must be one exact normalized origin.")
            origin = urlparse(self.public_origin)
            if (
                origin.scheme not in {"http", "https"}
                or not origin.hostname
                or origin.username is not None
                or origin.password is not None
                or origin.path not in {"", "/"}
                or origin.params
                or origin.query
                or origin.fragment
            ):
                raise ValueError("PUBLIC_ORIGIN must contain only an absolute HTTP(S) origin.")
            origin_host = canonical_trusted_host(origin.hostname)
            if origin_host not in self.trusted_hosts:
                raise ValueError("PUBLIC_ORIGIN host must be present in TRUSTED_HOSTS.")
            default_port = 443 if origin.scheme == "https" else 80
            try:
                origin_port = origin.port
            except ValueError as error:
                raise ValueError("PUBLIC_ORIGIN contains an invalid port.") from error
            authority = origin_host
            if origin_port is not None and origin_port != default_port:
                authority = (
                    f"[{origin_host}]:{origin_port}"
                    if ":" in origin_host
                    else f"{origin_host}:{origin_port}"
                )
            self.public_origin = f"{origin.scheme}://{authority}"
        if self.secure_cookies and (
            self.public_origin is None or not self.public_origin.startswith("https://")
        ):
            raise ValueError("SECURE_COOKIES requires an HTTPS PUBLIC_ORIGIN.")
        if self.require_csrf_origin and self.public_origin is None:
            raise ValueError("REQUIRE_CSRF_ORIGIN requires PUBLIC_ORIGIN.")
        if self.app_env == "production" and self.identity_provider != "oidc":
            raise ValueError("Production requires the OIDC identity provider.")
        if self.app_env == "production" and self.image_storage_provider != "s3":
            raise ValueError("Production requires the S3 private-object storage provider.")
        if self.app_env == "production" and (
            not self.secure_cookies
            or not self.require_csrf_origin
            or self.public_origin is None
            or not self.public_origin.startswith("https://")
        ):
            raise ValueError(
                "Production requires HTTPS PUBLIC_ORIGIN, secure cookies, and exact CSRF origin."
            )
        if self.paintpilot_demo_read_only and self.identity_provider != "oidc":
            raise ValueError("PAINTPILOT_DEMO_READ_ONLY requires the OIDC identity provider.")
        if self.paintpilot_demo_seed_enabled:
            if self.identity_provider != "oidc":
                raise ValueError(
                    "PAINTPILOT_DEMO_SEED_ENABLED requires the OIDC identity provider."
                )
            seed_values = {
                "PAINTPILOT_DEMO_SEED_SUBJECT": self.paintpilot_demo_seed_subject,
                "PAINTPILOT_DEMO_SEED_DISPLAY_NAME": self.paintpilot_demo_seed_display_name,
                "PAINTPILOT_DEMO_SEED_EMAIL": self.paintpilot_demo_seed_email,
            }
            missing_seed_values = [
                name for name, value in seed_values.items() if value is None or not value.strip()
            ]
            if missing_seed_values:
                raise ValueError(
                    "PAINTPILOT_DEMO_SEED_ENABLED requires " + ", ".join(missing_seed_values) + "."
                )
            assert self.paintpilot_demo_seed_email is not None
            if not self.paintpilot_demo_seed_email.endswith(".invalid"):
                raise ValueError("PAINTPILOT_DEMO_SEED_EMAIL must use a reserved .invalid address.")
        if self.phase3a_fixture_enabled:
            if self.app_env not in {"development", "test"}:
                raise ValueError(
                    "PHASE3A_FIXTURE_ENABLED is permitted only in development or test."
                )
            if self.staging_run_id is not None:
                raise ValueError("Phase 3A fixture mode is forbidden in staging-style runs.")
            if self.credential_fixture_root_key_file is None:
                raise ValueError(
                    "CREDENTIAL_FIXTURE_ROOT_KEY_FILE is required when Phase 3A is enabled."
                )
        if self.phase3b_paint_plan_enabled:
            if not self.phase3a_fixture_enabled:
                raise ValueError(
                    "PHASE3B_PAINT_PLAN_ENABLED requires the offline Phase 3A fixture gate."
                )
            if self.app_env not in {"development", "test"} or self.staging_run_id is not None:
                raise ValueError(
                    "Phase 3B Paint Plan mode is permitted only in non-staging development/test."
                )
        if self.zhipu_live_enabled:
            if not self.phase3a_fixture_enabled:
                raise ValueError("ZHIPU_LIVE_ENABLED requires the encrypted credential foundation.")
            if self.app_env not in {"development", "test"} or self.staging_run_id is not None:
                raise ValueError(
                    "Zhipu live validation is permitted only in an explicit local "
                    "development/test run."
                )
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
        if self.identity_provider != "configured_demo":
            raise ValueError("The configured Demo Principal Adapter is not selected.")
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

    def require_demo_seed_identity(self) -> tuple[str, str, str]:
        """Return the explicit synthetic OIDC identity allowed for a one-shot demo seed."""
        if not self.paintpilot_demo_seed_enabled:
            raise ValueError(
                "PAINTPILOT_DEMO_SEED_ENABLED=true is required for the synthetic demo seed."
            )
        if self.identity_provider != "oidc":
            raise ValueError("The synthetic demo seed requires the OIDC identity provider.")
        if (
            self.paintpilot_demo_seed_subject is None
            or self.paintpilot_demo_seed_display_name is None
            or self.paintpilot_demo_seed_email is None
        ):
            raise ValueError("The synthetic demo seed identity is incomplete.")
        return (
            self.paintpilot_demo_seed_subject,
            self.paintpilot_demo_seed_display_name,
            self.paintpilot_demo_seed_email,
        )

    def require_oidc_client(self) -> tuple[str, str, str, str, str]:
        """Return the complete provider-neutral confidential OIDC client configuration."""
        if self.app_env is None:
            raise ValueError("APP_ENV must be explicitly configured.")
        if self.identity_provider != "oidc":
            raise ValueError("The OIDC identity provider is not selected.")
        values = {
            "OIDC_ISSUER": self.oidc_issuer,
            "OIDC_CLIENT_ID": self.oidc_client_id,
            "OIDC_CLIENT_SECRET": (
                None
                if self.oidc_client_secret is None
                else self.oidc_client_secret.get_secret_value()
            ),
            "OIDC_REDIRECT_URI": self.oidc_redirect_uri,
        }
        missing = [name for name, value in values.items() if not value or not value.strip()]
        if missing:
            raise ValueError(f"OIDC configuration is incomplete: {', '.join(missing)}.")
        issuer = values["OIDC_ISSUER"]
        client_id = values["OIDC_CLIENT_ID"]
        client_secret = values["OIDC_CLIENT_SECRET"]
        redirect_uri = values["OIDC_REDIRECT_URI"]
        assert issuer is not None
        assert client_id is not None
        assert client_secret is not None
        assert redirect_uri is not None
        if issuer.endswith("/"):
            raise ValueError("OIDC_ISSUER must not end with a slash.")
        issuer_parts = urlparse(issuer)
        redirect_parts = urlparse(redirect_uri)
        if issuer_parts.scheme not in {"http", "https"} or not issuer_parts.netloc:
            raise ValueError("OIDC_ISSUER must be an absolute HTTP(S) URL.")
        if redirect_parts.scheme not in {"http", "https"} or not redirect_parts.netloc:
            raise ValueError("OIDC_REDIRECT_URI must be an absolute HTTP(S) URL.")
        if self.app_env == "production" and (
            issuer_parts.scheme != "https" or redirect_parts.scheme != "https"
        ):
            raise ValueError("Production OIDC issuer and redirect URI must use HTTPS.")
        if self.public_origin is not None:
            expected_redirect = f"{self.public_origin}/api/v1/auth/callback"
            if redirect_uri != expected_redirect:
                raise ValueError("OIDC_REDIRECT_URI must exactly match PUBLIC_ORIGIN callback.")
        discovery_url = self.oidc_discovery_url or (f"{issuer}/.well-known/openid-configuration")
        discovery_parts = urlparse(discovery_url)
        if discovery_parts.scheme not in {"http", "https"} or not discovery_parts.netloc:
            raise ValueError("OIDC_DISCOVERY_URL must be an absolute HTTP(S) URL.")
        if self.app_env == "production" and discovery_parts.scheme != "https":
            raise ValueError("Production OIDC discovery must use HTTPS.")
        if self.oidc_backchannel_base_url is not None:
            backchannel_parts = urlparse(self.oidc_backchannel_base_url)
            if (
                backchannel_parts.scheme not in {"http", "https"}
                or not backchannel_parts.netloc
                or self.oidc_backchannel_base_url.endswith("/")
            ):
                raise ValueError(
                    "OIDC_BACKCHANNEL_BASE_URL must be an absolute URL without a trailing slash."
                )
            if self.app_env == "production":
                raise ValueError(
                    "Production must use discovery endpoints published by the configured issuer."
                )
        return issuer, discovery_url, client_id, client_secret, redirect_uri

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

    def require_s3_image_storage(
        self,
    ) -> tuple[str, str, str, str, str, Path]:
        """Return complete private S3-compatible configuration or fail closed."""
        if self.app_env is None:
            raise ValueError("APP_ENV must be explicitly configured.")
        if self.image_storage_provider != "s3":
            raise ValueError("The S3 private-object storage provider is not selected.")
        access_key = (
            None if self.s3_access_key_id is None else self.s3_access_key_id.get_secret_value()
        )
        secret_key = (
            None
            if self.s3_secret_access_key is None
            else self.s3_secret_access_key.get_secret_value()
        )
        values = {
            "S3_ENDPOINT_URL": self.s3_endpoint_url,
            "S3_REGION": self.s3_region,
            "S3_BUCKET": self.s3_bucket,
            "S3_ACCESS_KEY_ID": access_key,
            "S3_SECRET_ACCESS_KEY": secret_key,
        }
        missing = [name for name, value in values.items() if not value or not value.strip()]
        if missing:
            raise ValueError(f"S3 configuration is incomplete: {', '.join(missing)}.")
        endpoint = values["S3_ENDPOINT_URL"]
        region = values["S3_REGION"]
        bucket = values["S3_BUCKET"]
        assert endpoint is not None
        assert region is not None
        assert bucket is not None
        assert access_key is not None
        assert secret_key is not None
        endpoint_parts = urlparse(endpoint)
        if endpoint_parts.scheme not in {"http", "https"} or not endpoint_parts.netloc:
            raise ValueError("S3_ENDPOINT_URL must be an absolute HTTP(S) URL.")
        if endpoint_parts.scheme == "http" and not self.s3_allow_insecure_http:
            raise ValueError("Plain HTTP S3 endpoints require S3_ALLOW_INSECURE_HTTP=true.")
        if self.app_env == "production" and (
            endpoint_parts.scheme != "https" or self.s3_allow_insecure_http
        ):
            raise ValueError("Production S3 endpoints must use HTTPS.")
        if self.app_env == "production" and self.s3_create_bucket:
            raise ValueError("Production must not create the S3 bucket at application startup.")
        if not 3 <= len(bucket) <= 63 or bucket.lower() != bucket:
            raise ValueError("S3_BUCKET must be a normalized bucket name.")
        staging_root = self.s3_staging_root.expanduser().resolve(strict=False)
        return endpoint, region, bucket, access_key, secret_key, staging_root


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached process settings without creating mutable global state."""
    return Settings.model_validate({})
