"""FastAPI application factory."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from creativedeploy_api.api.router import api_router
from creativedeploy_api.core.config import Settings, get_settings
from creativedeploy_api.db.engine import create_database_engine


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create a FastAPI application with explicitly injectable settings."""
    resolved_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = create_database_engine(resolved_settings)
        app.state.database_engine = engine
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
    app.include_router(api_router)
    return app
