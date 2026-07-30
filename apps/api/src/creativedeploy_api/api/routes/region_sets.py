"""Owner-scoped human RegionSet annotation and review routes."""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Header, Path, status

from creativedeploy_api.api.dependencies import (
    PrincipalDependency,
    RegionSetServiceDependency,
)
from creativedeploy_api.schemas.errors import ErrorResponse
from creativedeploy_api.schemas.region_sets import (
    CreateRegionSetReviewRequest,
    ForkRegionSetDraftRequest,
    RegionSetHistoryResponse,
    RegionSetRead,
    RegionSetReviewHistoryResponse,
    RegionSetReviewRead,
    RegionWorkbenchRead,
    SaveRegionSetRequest,
    SubmitRegionSetRequest,
)

router = APIRouter(
    prefix="/paint-projects/{project_id}/region-sets",
    tags=["paint-project-region-sets"],
)

ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    403: {"model": ErrorResponse, "description": "Human actor is required."},
    404: {"model": ErrorResponse, "description": "Missing or inaccessible resource."},
    409: {"model": ErrorResponse, "description": "Version, lifecycle, or source conflict."},
    422: {"model": ErrorResponse, "description": "Strict request or geometry validation failed."},
    500: {"model": ErrorResponse, "description": "Safe internal failure."},
    503: {"model": ErrorResponse, "description": "Database unavailable."},
}


@router.get(
    "/workbench",
    response_model=RegionWorkbenchRead,
    responses=ERROR_RESPONSES,
)
async def get_region_workbench(
    service: RegionSetServiceDependency,
    principal: PrincipalDependency,
    project_id: Annotated[UUID, Path()],
) -> RegionWorkbenchRead:
    """Bootstrap the source image, current snapshot, and immutable history."""
    return await service.get_workbench(project_id=project_id, principal=principal)


@router.post(
    "",
    response_model=RegionSetRead,
    status_code=status.HTTP_201_CREATED,
    responses={201: {"model": RegionSetRead}, **ERROR_RESPONSES},
)
async def save_region_set_draft(
    payload: SaveRegionSetRequest,
    service: RegionSetServiceDependency,
    principal: PrincipalDependency,
    project_id: Annotated[UUID, Path()],
    idempotency_key: Annotated[UUID, Header(alias="Idempotency-Key")],
) -> RegionSetRead:
    """Persist a new immutable human draft snapshot."""
    return await service.save_draft(
        project_id=project_id,
        payload=payload,
        principal=principal,
        idempotency_key=idempotency_key,
    )


@router.get(
    "",
    response_model=RegionSetHistoryResponse,
    responses=ERROR_RESPONSES,
)
async def list_region_set_history(
    service: RegionSetServiceDependency,
    principal: PrincipalDependency,
    project_id: Annotated[UUID, Path()],
) -> RegionSetHistoryResponse:
    """Return newest-first immutable RegionSet history."""
    return await service.list_history(project_id=project_id, principal=principal)


@router.get(
    "/{region_set_id}",
    response_model=RegionSetRead,
    responses=ERROR_RESPONSES,
)
async def get_region_set_detail(
    service: RegionSetServiceDependency,
    principal: PrincipalDependency,
    project_id: Annotated[UUID, Path()],
    region_set_id: Annotated[UUID, Path()],
) -> RegionSetRead:
    """Return one exact owner-scoped snapshot and derived stale state."""
    return await service.get_region_set(
        project_id=project_id,
        region_set_id=region_set_id,
        principal=principal,
    )


@router.post(
    "/{source_region_set_id}/drafts",
    response_model=RegionSetRead,
    status_code=status.HTTP_201_CREATED,
    responses={201: {"model": RegionSetRead}, **ERROR_RESPONSES},
)
async def fork_region_set_draft(
    payload: ForkRegionSetDraftRequest,
    service: RegionSetServiceDependency,
    principal: PrincipalDependency,
    project_id: Annotated[UUID, Path()],
    source_region_set_id: Annotated[UUID, Path()],
    idempotency_key: Annotated[UUID, Header(alias="Idempotency-Key")],
) -> RegionSetRead:
    """Copy one exact historical snapshot into a new current draft."""
    return await service.fork_draft(
        project_id=project_id,
        source_region_set_id=source_region_set_id,
        payload=payload,
        principal=principal,
        idempotency_key=idempotency_key,
    )


@router.post(
    "/{region_set_id}/submit",
    response_model=RegionSetRead,
    status_code=status.HTTP_201_CREATED,
    responses={201: {"model": RegionSetRead}, **ERROR_RESPONSES},
)
async def submit_region_set(
    _payload: SubmitRegionSetRequest,
    service: RegionSetServiceDependency,
    principal: PrincipalDependency,
    project_id: Annotated[UUID, Path()],
    region_set_id: Annotated[UUID, Path()],
    idempotency_key: Annotated[UUID, Header(alias="Idempotency-Key")],
) -> RegionSetRead:
    """Seal a validated draft as a new immutable submitted snapshot."""
    return await service.submit(
        project_id=project_id,
        region_set_id=region_set_id,
        principal=principal,
        idempotency_key=idempotency_key,
    )


@router.post(
    "/{region_set_id}/reviews",
    response_model=RegionSetReviewRead,
    status_code=status.HTTP_201_CREATED,
    responses={201: {"model": RegionSetReviewRead}, **ERROR_RESPONSES},
)
async def review_region_set(
    payload: CreateRegionSetReviewRequest,
    service: RegionSetServiceDependency,
    principal: PrincipalDependency,
    project_id: Annotated[UUID, Path()],
    region_set_id: Annotated[UUID, Path()],
    idempotency_key: Annotated[UUID, Header(alias="Idempotency-Key")],
) -> RegionSetReviewRead:
    """Append one human approval or changes-requested decision."""
    return await service.review(
        project_id=project_id,
        region_set_id=region_set_id,
        payload=payload,
        principal=principal,
        idempotency_key=idempotency_key,
    )


@router.get(
    "/{region_set_id}/reviews",
    response_model=RegionSetReviewHistoryResponse,
    responses=ERROR_RESPONSES,
)
async def list_region_set_review_history(
    service: RegionSetServiceDependency,
    principal: PrincipalDependency,
    project_id: Annotated[UUID, Path()],
    region_set_id: Annotated[UUID, Path()],
) -> RegionSetReviewHistoryResponse:
    """Return append-only review history for one exact RegionSet."""
    return await service.list_review_history(
        project_id=project_id,
        region_set_id=region_set_id,
        principal=principal,
    )
