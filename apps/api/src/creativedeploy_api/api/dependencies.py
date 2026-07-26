"""Explicit FastAPI dependencies for database and Principal boundaries."""

import uuid
from collections.abc import AsyncIterator
from typing import Annotated, cast

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from creativedeploy_api.core.config import Settings
from creativedeploy_api.core.principal import (
    ConfiguredDemoPrincipalAdapter,
    PrincipalContext,
)
from creativedeploy_api.services.paint_projects import PaintProjectService


def get_request_id(request: Request) -> uuid.UUID:
    """Return one generated correlation ID for the lifetime of a request."""
    existing = getattr(request.state, "request_id", None)
    if isinstance(existing, uuid.UUID):
        return existing
    request_id = uuid.uuid4()
    request.state.request_id = request_id
    return request_id


async def get_database_session(request: Request) -> AsyncIterator[AsyncSession]:
    """Yield one AsyncSession and always close it after the request."""
    session_factory = cast(
        async_sessionmaker[AsyncSession],
        request.app.state.database_session_factory,
    )
    async with session_factory() as session:
        yield session


def get_current_principal(request: Request) -> PrincipalContext:
    """Resolve the configured demo operator through the installed adapter."""
    adapter = cast(
        ConfiguredDemoPrincipalAdapter,
        request.app.state.principal_adapter,
    )
    return adapter.resolve()


DatabaseSessionDependency = Annotated[AsyncSession, Depends(get_database_session)]
PrincipalDependency = Annotated[PrincipalContext, Depends(get_current_principal)]
RequestIdDependency = Annotated[uuid.UUID, Depends(get_request_id)]


def get_paint_project_service(
    request: Request,
    session: DatabaseSessionDependency,
) -> PaintProjectService:
    """Build the request-scoped PaintProject service."""
    settings = cast(Settings, request.app.state.settings)
    return PaintProjectService(
        session,
        database_lock_timeout_ms=settings.database_lock_timeout_ms,
        database_statement_timeout_ms=settings.database_statement_timeout_ms,
    )


PaintProjectServiceDependency = Annotated[
    PaintProjectService,
    Depends(get_paint_project_service),
]
