"""Liveness and readiness endpoints."""

from typing import Annotated, cast

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncEngine

from creativedeploy_api.core.config import Settings
from creativedeploy_api.schemas.health import (
    DatabaseCheck,
    ReadinessChecks,
    ReadinessResponse,
    ServiceHealthResponse,
)
from creativedeploy_api.services.database_health import DatabaseHealthService

SERVICE_ID = "creativedeploy-api"

router = APIRouter(prefix="/health", tags=["health"])


def get_database_health_service(request: Request) -> DatabaseHealthService:
    """Build the request-scoped database health service from application state."""
    engine = cast(AsyncEngine, request.app.state.database_engine)
    settings = cast(Settings, request.app.state.settings)
    return DatabaseHealthService(
        engine=engine,
        timeout_seconds=settings.database_health_timeout_seconds,
    )


DatabaseHealthDependency = Annotated[
    DatabaseHealthService,
    Depends(get_database_health_service),
]


@router.get(
    "/live",
    response_model=ServiceHealthResponse,
    responses={200: {"model": ServiceHealthResponse}},
)
async def liveness(request: Request) -> ServiceHealthResponse:
    """Return process liveness without touching the database."""
    settings = cast(Settings, request.app.state.settings)
    return ServiceHealthResponse(
        status="ok",
        service=SERVICE_ID,
        version=settings.app_version,
    )


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    responses={
        200: {"model": ReadinessResponse},
        503: {
            "model": ReadinessResponse,
            "description": "The API is live but PostgreSQL is unavailable.",
        },
    },
)
async def readiness(
    request: Request,
    database_health: DatabaseHealthDependency,
) -> ReadinessResponse | JSONResponse:
    """Return API readiness based on a real PostgreSQL SELECT 1 check."""
    settings = cast(Settings, request.app.state.settings)
    database_result = await database_health.check()
    database_check = DatabaseCheck(
        status=database_result.status,
        latency_ms=database_result.latency_ms,
        error_code=database_result.error_code,
    )

    if database_result.status == "error":
        response = ReadinessResponse(
            status="degraded",
            service=SERVICE_ID,
            version=settings.app_version,
            checks=ReadinessChecks(database=database_check),
        )
        return JSONResponse(status_code=503, content=response.model_dump(mode="json"))

    return ReadinessResponse(
        status="ok",
        service=SERVICE_ID,
        version=settings.app_version,
        checks=ReadinessChecks(database=database_check),
    )
