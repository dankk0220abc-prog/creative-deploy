"""Project-scoped governed Paint Plan generation and exact review routes."""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Path, status

from creativedeploy_api.api.dependencies import (
    PaintPlanServiceDependency,
    PrincipalDependency,
    get_request_id,
)
from creativedeploy_api.schemas.errors import ErrorResponse
from creativedeploy_api.schemas.paint_plans import (
    PaintPlanEditRequest,
    PaintPlanGenerateRequest,
    PaintPlanHistoryResponse,
    PaintPlanPreviewRead,
    PaintPlanPreviewRequest,
    PaintPlanRead,
    PaintPlanRegenerateRequest,
    PaintPlanReviewRequest,
    PaintPlanRevisionRequest,
    PaintPlanWorkbenchRead,
)

router = APIRouter(
    prefix="/paint-projects/{project_id}/paint-plans",
    tags=["paint-project-paint-plans"],
)

ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    403: {"model": ErrorResponse, "description": "Actor is not authorized."},
    404: {"model": ErrorResponse, "description": "Missing or inaccessible resource."},
    409: {"model": ErrorResponse, "description": "Readiness, revision, or lifecycle conflict."},
    422: {"model": ErrorResponse, "description": "Strict request validation failed."},
    502: {"model": ErrorResponse, "description": "Provider output failed strict validation."},
    503: {"model": ErrorResponse, "description": "Database unavailable."},
}


@router.get(
    "/workbench",
    response_model=PaintPlanWorkbenchRead,
    responses=ERROR_RESPONSES,
)
async def get_paint_plan_workbench(
    service: PaintPlanServiceDependency,
    principal: PrincipalDependency,
    project_id: Annotated[UUID, Path()],
) -> PaintPlanWorkbenchRead:
    return await service.get_workbench(project_id=project_id, principal=principal)


@router.post(
    "/preview",
    response_model=PaintPlanPreviewRead,
    responses=ERROR_RESPONSES,
)
async def preview_paint_plan_generation(
    payload: PaintPlanPreviewRequest,
    service: PaintPlanServiceDependency,
    principal: PrincipalDependency,
    project_id: Annotated[UUID, Path()],
) -> PaintPlanPreviewRead:
    return await service.preview(
        project_id=project_id,
        payload=payload,
        principal=principal,
    )


@router.post(
    "/generate",
    response_model=PaintPlanRead,
    status_code=status.HTTP_201_CREATED,
    responses={201: {"model": PaintPlanRead}, **ERROR_RESPONSES},
)
async def generate_paint_plan(
    payload: PaintPlanGenerateRequest,
    service: PaintPlanServiceDependency,
    principal: PrincipalDependency,
    project_id: Annotated[UUID, Path()],
    idempotency_key: Annotated[UUID, Header(alias="Idempotency-Key")],
    request_id: Annotated[UUID, Depends(get_request_id)],
) -> PaintPlanRead:
    return await service.generate(
        project_id=project_id,
        payload=payload,
        principal=principal,
        idempotency_key=idempotency_key,
        request_id=request_id,
    )


@router.get(
    "",
    response_model=PaintPlanHistoryResponse,
    responses=ERROR_RESPONSES,
)
async def list_paint_plan_history(
    service: PaintPlanServiceDependency,
    principal: PrincipalDependency,
    project_id: Annotated[UUID, Path()],
) -> PaintPlanHistoryResponse:
    return await service.list_history(project_id=project_id, principal=principal)


@router.get(
    "/{plan_id}",
    response_model=PaintPlanRead,
    responses=ERROR_RESPONSES,
)
async def get_paint_plan(
    service: PaintPlanServiceDependency,
    principal: PrincipalDependency,
    project_id: Annotated[UUID, Path()],
    plan_id: Annotated[UUID, Path()],
) -> PaintPlanRead:
    return await service.get_plan(
        project_id=project_id,
        plan_id=plan_id,
        principal=principal,
    )


@router.post(
    "/{plan_id}/edits",
    response_model=PaintPlanRead,
    status_code=status.HTTP_201_CREATED,
    responses={201: {"model": PaintPlanRead}, **ERROR_RESPONSES},
)
async def edit_paint_plan(
    payload: PaintPlanEditRequest,
    service: PaintPlanServiceDependency,
    principal: PrincipalDependency,
    project_id: Annotated[UUID, Path()],
    plan_id: Annotated[UUID, Path()],
    idempotency_key: Annotated[UUID, Header(alias="Idempotency-Key")],
) -> PaintPlanRead:
    return await service.edit(
        project_id=project_id,
        plan_id=plan_id,
        payload=payload,
        principal=principal,
        idempotency_key=idempotency_key,
    )


@router.post(
    "/{plan_id}/submit",
    response_model=PaintPlanRead,
    status_code=status.HTTP_201_CREATED,
    responses={201: {"model": PaintPlanRead}, **ERROR_RESPONSES},
)
async def submit_paint_plan(
    payload: PaintPlanRevisionRequest,
    service: PaintPlanServiceDependency,
    principal: PrincipalDependency,
    project_id: Annotated[UUID, Path()],
    plan_id: Annotated[UUID, Path()],
    idempotency_key: Annotated[UUID, Header(alias="Idempotency-Key")],
) -> PaintPlanRead:
    return await service.submit(
        project_id=project_id,
        plan_id=plan_id,
        payload=payload,
        principal=principal,
        idempotency_key=idempotency_key,
    )


@router.post(
    "/{plan_id}/approve",
    response_model=PaintPlanRead,
    status_code=status.HTTP_201_CREATED,
    responses={201: {"model": PaintPlanRead}, **ERROR_RESPONSES},
)
async def approve_paint_plan(
    payload: PaintPlanReviewRequest,
    service: PaintPlanServiceDependency,
    principal: PrincipalDependency,
    project_id: Annotated[UUID, Path()],
    plan_id: Annotated[UUID, Path()],
    idempotency_key: Annotated[UUID, Header(alias="Idempotency-Key")],
) -> PaintPlanRead:
    return await service.approve(
        project_id=project_id,
        plan_id=plan_id,
        payload=payload,
        principal=principal,
        idempotency_key=idempotency_key,
    )


@router.post(
    "/{plan_id}/reject",
    response_model=PaintPlanRead,
    status_code=status.HTTP_201_CREATED,
    responses={201: {"model": PaintPlanRead}, **ERROR_RESPONSES},
)
async def reject_paint_plan(
    payload: PaintPlanReviewRequest,
    service: PaintPlanServiceDependency,
    principal: PrincipalDependency,
    project_id: Annotated[UUID, Path()],
    plan_id: Annotated[UUID, Path()],
    idempotency_key: Annotated[UUID, Header(alias="Idempotency-Key")],
) -> PaintPlanRead:
    return await service.reject(
        project_id=project_id,
        plan_id=plan_id,
        payload=payload,
        principal=principal,
        idempotency_key=idempotency_key,
    )


@router.post(
    "/{plan_id}/regenerate",
    response_model=PaintPlanRead,
    status_code=status.HTTP_201_CREATED,
    responses={201: {"model": PaintPlanRead}, **ERROR_RESPONSES},
)
async def regenerate_paint_plan(
    payload: PaintPlanRegenerateRequest,
    service: PaintPlanServiceDependency,
    principal: PrincipalDependency,
    project_id: Annotated[UUID, Path()],
    plan_id: Annotated[UUID, Path()],
    idempotency_key: Annotated[UUID, Header(alias="Idempotency-Key")],
    request_id: Annotated[UUID, Depends(get_request_id)],
) -> PaintPlanRead:
    return await service.regenerate(
        project_id=project_id,
        plan_id=plan_id,
        payload=payload,
        principal=principal,
        idempotency_key=idempotency_key,
        request_id=request_id,
    )
