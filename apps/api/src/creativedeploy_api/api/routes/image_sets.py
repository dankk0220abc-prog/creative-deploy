"""Owner-scoped multi-role ImageSet readiness routes."""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Header, Path, status

from creativedeploy_api.api.dependencies import (
    ImageAssetServiceDependency,
    PrincipalDependency,
)
from creativedeploy_api.schemas.errors import ErrorResponse
from creativedeploy_api.schemas.image_assets import (
    CreateReadinessReviewRequest,
    ImageSetRead,
    ImageSetReadinessReviewRead,
    ReadinessReviewHistoryResponse,
)

router = APIRouter(
    prefix="/paint-projects/{project_id}/image-set",
    tags=["paint-project-image-set"],
)

ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    404: {"model": ErrorResponse, "description": "Missing or inaccessible project."},
    409: {"model": ErrorResponse, "description": "Readiness or idempotency conflict."},
    422: {"model": ErrorResponse, "description": "Strict request validation failed."},
    500: {"model": ErrorResponse, "description": "Safe internal failure."},
    503: {"model": ErrorResponse, "description": "Database unavailable."},
}


@router.get(
    "",
    response_model=ImageSetRead,
    responses=ERROR_RESPONSES,
)
async def get_project_image_set(
    service: ImageAssetServiceDependency,
    principal: PrincipalDependency,
    project_id: Annotated[UUID, Path()],
) -> ImageSetRead:
    """Return the current role set, deterministic checklist, and latest verdict."""
    return await service.get_image_set(project_id=project_id, principal=principal)


@router.post(
    "/readiness-reviews",
    response_model=ImageSetReadinessReviewRead,
    status_code=status.HTTP_201_CREATED,
    responses={201: {"model": ImageSetReadinessReviewRead}, **ERROR_RESPONSES},
)
async def create_project_image_set_readiness_review(
    payload: CreateReadinessReviewRequest,
    service: ImageAssetServiceDependency,
    principal: PrincipalDependency,
    project_id: Annotated[UUID, Path()],
    idempotency_key: Annotated[UUID, Header(alias="Idempotency-Key")],
) -> ImageSetReadinessReviewRead:
    """Create or replay one human verdict against the server-owned snapshot."""
    return await service.create_readiness_review(
        project_id=project_id,
        payload=payload,
        principal=principal,
        idempotency_key=idempotency_key,
    )


@router.get(
    "/readiness-reviews",
    response_model=ReadinessReviewHistoryResponse,
    responses=ERROR_RESPONSES,
)
async def list_project_image_set_readiness_history(
    service: ImageAssetServiceDependency,
    principal: PrincipalDependency,
    project_id: Annotated[UUID, Path()],
) -> ReadinessReviewHistoryResponse:
    """Return newest-first append-only readiness history."""
    return await service.list_readiness_history(
        project_id=project_id,
        principal=principal,
    )
