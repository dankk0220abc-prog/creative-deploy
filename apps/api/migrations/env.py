"""Alembic environment for the CreativeDeploy async PostgreSQL database."""

import asyncio

from alembic import context
from sqlalchemy import Connection
from sqlalchemy.ext.asyncio import AsyncEngine

from creativedeploy_api.core.config import get_settings
from creativedeploy_api.db.base import Base
from creativedeploy_api.db.engine import create_database_engine
from creativedeploy_api.db.models import REGISTERED_MODELS

OFFLINE_MIGRATIONS_ERROR = (
    "Offline migrations are not supported in the current database foundation."
)
REGISTERED_MODEL_TABLES = tuple(model.__table__.name for model in REGISTERED_MODELS)
target_metadata = Base.metadata


def do_run_migrations(connection: Connection) -> None:
    """Configure Alembic against an established synchronous connection adapter."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        include_schemas=False,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run online migrations through the application's async engine boundary."""
    engine: AsyncEngine = create_database_engine(get_settings())
    try:
        async with engine.connect() as connection:
            await connection.run_sync(do_run_migrations)
    finally:
        await engine.dispose()


def run_migrations() -> None:
    """Run the Alembic CLI environment without enabling offline SQL generation."""
    if context.is_offline_mode():
        raise RuntimeError(OFFLINE_MIGRATIONS_ERROR)
    asyncio.run(run_async_migrations())


def _alembic_runtime_is_configured() -> bool:
    """Return whether Alembic installed its runtime proxy for this module execution."""
    try:
        runtime_config = context.config
    except (AttributeError, NameError):
        return False
    return runtime_config is not None


if _alembic_runtime_is_configured():
    run_migrations()
