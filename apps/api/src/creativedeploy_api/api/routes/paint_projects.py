"""Owner-scoped PaintProject create, list, and detail routes."""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Header, Path, Query, Response, status

from creativedeploy_api.api.dependencies import (
    PaintProjectServiceDependency,
    PrincipalDependency,
    RequestIdDependency,
)
from creativedeploy_api.schemas.errors import ErrorResponse
from creativedeploy_api.schemas.paint_projects import (
    CreatePaintProjectRequest,
    PaintProjectListResponse,
    PaintProjectRead,
)

router = APIRouter(prefix="/paint-projects", tags=["paint-projects"])

ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    422: {"model": ErrorResponse, "description": "Request validation failed."},
    500: {"model": ErrorResponse, "description": "Safe internal failure."},
    503: {"model": ErrorResponse, "description": "Database unavailable."},
}


@router.post(
    "",
    response_model=PaintProjectRead,
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {"model": PaintProjectRead},
        409: {"model": ErrorResponse, "description": "Idempotency-Key conflict."},
        **ERROR_RESPONSES,
    },
)
async def create_paint_project(
    payload: CreatePaintProjectRequest,
    response: Response,
    service: PaintProjectServiceDependency,
    principal: PrincipalDependency,
    request_id: RequestIdDependency,
    idempotency_key: Annotated[UUID, Header(alias="Idempotency-Key")],
) -> PaintProjectRead:
    """Create or safely replay a PaintProject command."""
    result = await service.create_project(
        payload=payload,
        principal=principal,
        idempotency_key=idempotency_key,
        correlation_id=request_id,
    )
    if result.replayed:
        response.headers["Idempotent-Replayed"] = "true"
    return result.project


@router.get(
    "",
    response_model=PaintProjectListResponse,
    responses=ERROR_RESPONSES,
)
async def list_paint_projects(
    service: PaintProjectServiceDependency,
    principal: PrincipalDependency,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> PaintProjectListResponse:
    """List a deterministic page of the current Principal's projects."""
    return await service.list_projects(
        principal=principal,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{project_id}",
    response_model=PaintProjectRead,
    responses={
        404: {"model": ErrorResponse, "description": "Missing or inaccessible project."},
        **ERROR_RESPONSES,
    },
)
async def get_paint_project(
    service: PaintProjectServiceDependency,
    principal: PrincipalDependency,
    project_id: Annotated[UUID, Path()],
) -> PaintProjectRead:
    """Read one project without disclosing another owner's resource."""
    return await service.get_project(
        project_id=project_id,
        principal=principal,
    )
