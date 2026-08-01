"""Owner-only reviewer assignment routes with safe project non-disclosure."""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Path, Response, status

from creativedeploy_api.api.dependencies import (
    PrincipalDependency,
    ProjectMembershipServiceDependency,
)
from creativedeploy_api.schemas.auth import (
    AssignableUserListResponse,
    AssignReviewerRequest,
    ProjectMembershipListResponse,
    ProjectMembershipRead,
)
from creativedeploy_api.schemas.errors import ErrorResponse

router = APIRouter(
    prefix="/paint-projects/{project_id}",
    tags=["paint-project-memberships"],
)

ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    404: {"model": ErrorResponse, "description": "Missing project, membership, or user."},
    422: {"model": ErrorResponse, "description": "Strict request validation failed."},
    500: {"model": ErrorResponse, "description": "Safe internal failure."},
    503: {"model": ErrorResponse, "description": "Database unavailable."},
}


@router.get(
    "/memberships",
    response_model=ProjectMembershipListResponse,
    responses=ERROR_RESPONSES,
)
async def list_memberships(
    service: ProjectMembershipServiceDependency,
    principal: PrincipalDependency,
    project_id: Annotated[UUID, Path()],
) -> ProjectMembershipListResponse:
    return await service.list_memberships(project_id=project_id, principal=principal)


@router.get(
    "/assignable-reviewers",
    response_model=AssignableUserListResponse,
    responses=ERROR_RESPONSES,
)
async def list_assignable_reviewers(
    service: ProjectMembershipServiceDependency,
    principal: PrincipalDependency,
    project_id: Annotated[UUID, Path()],
) -> AssignableUserListResponse:
    return await service.list_assignable_users(project_id=project_id, principal=principal)


@router.put(
    "/memberships/{reviewer_user_id}",
    response_model=ProjectMembershipRead,
    responses=ERROR_RESPONSES,
)
async def assign_reviewer(
    payload: AssignReviewerRequest,
    service: ProjectMembershipServiceDependency,
    principal: PrincipalDependency,
    project_id: Annotated[UUID, Path()],
    reviewer_user_id: Annotated[UUID, Path()],
) -> ProjectMembershipRead:
    if payload.user_id != reviewer_user_id:
        # Reuse strict request validation semantics without accepting two identities.
        from creativedeploy_api.services.identity import ReviewerUserNotFoundError

        raise ReviewerUserNotFoundError
    return await service.assign(
        project_id=project_id,
        reviewer_user_id=reviewer_user_id,
        principal=principal,
    )


@router.delete(
    "/memberships/{reviewer_user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=ERROR_RESPONSES,
)
async def remove_reviewer(
    service: ProjectMembershipServiceDependency,
    principal: PrincipalDependency,
    project_id: Annotated[UUID, Path()],
    reviewer_user_id: Annotated[UUID, Path()],
) -> Response:
    await service.remove(
        project_id=project_id,
        reviewer_user_id=reviewer_user_id,
        principal=principal,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
