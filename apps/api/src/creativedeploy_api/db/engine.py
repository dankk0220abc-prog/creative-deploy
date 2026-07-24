"""Asynchronous SQLAlchemy engine construction."""

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from creativedeploy_api.core.config import Settings


def create_database_engine(settings: Settings) -> AsyncEngine:
    """Create the application engine without opening a connection."""
    return create_async_engine(
        settings.database_url.get_secret_value(),
        pool_pre_ping=True,
    )
