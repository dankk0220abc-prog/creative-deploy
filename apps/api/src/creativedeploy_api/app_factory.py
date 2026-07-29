"""FastAPI application factory."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from creativedeploy_api.api.error_handlers import register_error_handlers
from creativedeploy_api.api.router import api_router
from creativedeploy_api.core.config import Settings, get_settings
from creativedeploy_api.core.principal import ConfiguredDemoPrincipalAdapter
from creativedeploy_api.db.engine import create_database_engine
from creativedeploy_api.db.session import create_database_session_factory
from creativedeploy_api.storage.images import LocalFilesystemImageStorageAdapter


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create a FastAPI application with explicitly injectable settings."""
    resolved_settings = settings or get_settings()
    principal_adapter = ConfiguredDemoPrincipalAdapter.from_settings(resolved_settings)
    image_storage = LocalFilesystemImageStorageAdapter(
        resolved_settings.require_local_image_storage()
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
    register_error_handlers(app)
    app.include_router(api_router)
    return app
