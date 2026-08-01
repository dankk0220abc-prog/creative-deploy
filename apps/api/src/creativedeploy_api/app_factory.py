"""FastAPI application factory."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from creativedeploy_api.api.error_handlers import register_error_handlers
from creativedeploy_api.api.router import api_router
from creativedeploy_api.api.security_middleware import (
    ExactTrustedHostMiddleware,
    PrivateApiNoStoreMiddleware,
)
from creativedeploy_api.auth.oidc import OidcClient
from creativedeploy_api.core.config import Settings, get_settings
from creativedeploy_api.core.principal import ConfiguredDemoPrincipalAdapter
from creativedeploy_api.db.engine import create_database_engine
from creativedeploy_api.db.session import create_database_session_factory
from creativedeploy_api.storage.images import (
    ImageStoragePort,
    LocalFilesystemImageStorageAdapter,
)
from creativedeploy_api.storage.s3 import S3ImageStorageAdapter


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create a FastAPI application with explicitly injectable settings."""
    resolved_settings = settings or get_settings()
    principal_adapter: ConfiguredDemoPrincipalAdapter | None
    oidc_client: OidcClient | None
    if resolved_settings.identity_provider == "configured_demo":
        principal_adapter = ConfiguredDemoPrincipalAdapter.from_settings(resolved_settings)
        oidc_client = None
    else:
        issuer, discovery_url, client_id, client_secret, redirect_uri = (
            resolved_settings.require_oidc_client()
        )
        principal_adapter = None
        oidc_client = OidcClient(
            issuer=issuer,
            discovery_url=discovery_url,
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            timeout_seconds=resolved_settings.oidc_http_timeout_seconds,
            id_token_max_age_seconds=(resolved_settings.oidc_id_token_max_age_seconds),
            clock_skew_seconds=resolved_settings.oidc_clock_skew_seconds,
            backchannel_base_url=resolved_settings.oidc_backchannel_base_url,
        )
    image_storage: ImageStoragePort
    if resolved_settings.image_storage_provider == "local_filesystem":
        image_storage = LocalFilesystemImageStorageAdapter(
            resolved_settings.require_local_image_storage()
        )
    else:
        endpoint, region, bucket, access_key, secret_key, staging_root = (
            resolved_settings.require_s3_image_storage()
        )
        image_storage = S3ImageStorageAdapter(
            endpoint_url=endpoint,
            region=region,
            bucket=bucket,
            access_key_id=access_key,
            secret_access_key=secret_key,
            force_path_style=resolved_settings.s3_force_path_style,
            staging_root=staging_root,
            create_bucket=resolved_settings.s3_create_bucket,
        )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = create_database_engine(resolved_settings)
        app.state.database_engine = engine
        app.state.database_session_factory = create_database_session_factory(engine)
        try:
            yield
        finally:
            await engine.dispose()

    app = FastAPI(
        title=resolved_settings.app_name,
        version=resolved_settings.app_version,
        lifespan=lifespan,
    )
    app.state.settings = resolved_settings
    app.state.image_storage = image_storage
    app.state.principal_adapter = principal_adapter
    app.state.oidc_client = oidc_client
    app.add_middleware(
        ExactTrustedHostMiddleware,
        allowed_hosts=list(resolved_settings.trusted_hosts),
    )
    app.add_middleware(PrivateApiNoStoreMiddleware)
    register_error_handlers(app)
    app.include_router(api_router)
    return app
