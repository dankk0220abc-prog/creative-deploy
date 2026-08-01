"""Liveness and readiness endpoints."""

import asyncio
from typing import Annotated, Literal, Protocol, cast

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncEngine

from creativedeploy_api.core.config import Settings
from creativedeploy_api.schemas.health import (
    DatabaseCheck,
    IdentityCheck,
    ReadinessChecks,
    ReadinessResponse,
    ServiceHealthResponse,
    StorageCheck,
)
from creativedeploy_api.services.database_health import DatabaseHealthService
from creativedeploy_api.services.runtime_health import (
    IdentityHealthService,
    RuntimeDependencyHealthResult,
    StorageHealthService,
)
from creativedeploy_api.storage.images import ImageStoragePort

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


class RuntimeHealthPort(Protocol):
    async def check(self) -> RuntimeDependencyHealthResult: ...


def get_storage_health_service(request: Request) -> StorageHealthService:
    settings = cast(Settings, request.app.state.settings)
    storage = cast(ImageStoragePort, request.app.state.image_storage)
    return StorageHealthService(storage, timeout_seconds=settings.database_health_timeout_seconds)


def get_identity_health_service(request: Request) -> IdentityHealthService:
    settings = cast(Settings, request.app.state.settings)
    return IdentityHealthService(
        request.app.state.oidc_client,
        timeout_seconds=settings.oidc_http_timeout_seconds,
    )


StorageHealthDependency = Annotated[RuntimeHealthPort, Depends(get_storage_health_service)]
IdentityHealthDependency = Annotated[RuntimeHealthPort, Depends(get_identity_health_service)]


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
    storage_health: StorageHealthDependency,
    identity_health: IdentityHealthDependency,
) -> ReadinessResponse | JSONResponse:
    """Return readiness only when PostgreSQL, private storage, and identity are usable."""
    settings = cast(Settings, request.app.state.settings)
    database_result, storage_result, identity_result = await asyncio.gather(
        database_health.check(),
        storage_health.check(),
        identity_health.check(),
    )
    database_check = DatabaseCheck(
        status=database_result.status,
        latency_ms=database_result.latency_ms,
        error_code=database_result.error_code,
    )
    storage_check = StorageCheck(
        status=storage_result.status,
        latency_ms=storage_result.latency_ms,
        error_code=cast(
            Literal["STORAGE_UNAVAILABLE"] | None,
            storage_result.error_code,
        ),
    )
    identity_check = IdentityCheck(
        status=identity_result.status,
        latency_ms=identity_result.latency_ms,
        error_code=cast(
            Literal["IDENTITY_PROVIDER_UNAVAILABLE"] | None,
            identity_result.error_code,
        ),
    )

    checks = ReadinessChecks(
        database=database_check,
        storage=storage_check,
        identity=identity_check,
    )
    if any(
        result.status == "error" for result in (database_result, storage_result, identity_result)
    ):
        response = ReadinessResponse(
            status="degraded",
            service=SERVICE_ID,
            version=settings.app_version,
            checks=checks,
        )
        return JSONResponse(status_code=503, content=response.model_dump(mode="json"))

    return ReadinessResponse(
        status="ok",
        service=SERVICE_ID,
        version=settings.app_version,
        checks=checks,
    )
