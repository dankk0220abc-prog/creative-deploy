"""Feature-gated, fixture-only Phase 3A provider foundation routes."""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Header, Path, Query, Response, status

from creativedeploy_api.api.dependencies import (
    AIFoundationServiceDependency,
    PrincipalDependency,
    RequestIdDependency,
)
from creativedeploy_api.schemas.ai_foundation import (
    CancelInvocationRequest,
    CapabilityListResponse,
    CredentialCreateRequest,
    CredentialGrantRead,
    CredentialGrantRequest,
    CredentialListResponse,
    CredentialMutationRequest,
    CredentialRead,
    CredentialReplaceRequest,
    CredentialValidationResponse,
    InvocationCreateRequest,
    InvocationPreviewRead,
    InvocationPreviewRequest,
    InvocationRead,
    ModelListResponse,
    ProjectPolicyRead,
    ProjectPolicyUpdate,
    ProviderListResponse,
    TemporaryCredentialValidationRequest,
    UsageAuditListResponse,
    UserPreferenceRead,
    UserPreferenceUpdate,
)
from creativedeploy_api.schemas.errors import ErrorResponse

router = APIRouter(prefix="/ai", tags=["ai-foundation-fixture"])

ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    404: {"model": ErrorResponse, "description": "Unavailable or inaccessible resource."},
    409: {"model": ErrorResponse, "description": "Policy or revision conflict."},
    422: {"model": ErrorResponse, "description": "Strict request validation failed."},
    429: {"model": ErrorResponse, "description": "Local validation rate limit."},
    500: {"model": ErrorResponse, "description": "Safe internal failure."},
    503: {"model": ErrorResponse, "description": "Database unavailable."},
}


@router.get("/providers", response_model=ProviderListResponse, responses=ERROR_RESPONSES)
async def list_providers(
    service: AIFoundationServiceDependency,
    principal: PrincipalDependency,
) -> ProviderListResponse:
    return await service.list_providers()


@router.get(
    "/providers/{provider_key}/models",
    response_model=ModelListResponse,
    responses=ERROR_RESPONSES,
)
async def list_models(
    service: AIFoundationServiceDependency,
    principal: PrincipalDependency,
    provider_key: Annotated[str, Path(pattern=r"^[a-z0-9_]{1,64}$")],
) -> ModelListResponse:
    return await service.list_models(provider_key)


@router.get("/capabilities", response_model=CapabilityListResponse, responses=ERROR_RESPONSES)
async def list_capabilities(
    service: AIFoundationServiceDependency,
    principal: PrincipalDependency,
) -> CapabilityListResponse:
    return await service.list_capabilities()


@router.post(
    "/credentials/validate",
    response_model=CredentialValidationResponse,
    responses=ERROR_RESPONSES,
)
async def validate_temporary_credential(
    payload: TemporaryCredentialValidationRequest,
    service: AIFoundationServiceDependency,
    principal: PrincipalDependency,
    request_id: RequestIdDependency,
    idempotency_key: Annotated[UUID, Header(alias="Idempotency-Key")],
) -> CredentialValidationResponse:
    return await service.validate_temporary(
        payload=payload,
        principal=principal,
        idempotency_key=idempotency_key,
        request_id=request_id,
    )


@router.get("/credentials", response_model=CredentialListResponse, responses=ERROR_RESPONSES)
async def list_credentials(
    service: AIFoundationServiceDependency,
    principal: PrincipalDependency,
) -> CredentialListResponse:
    return await service.list_credentials(principal)


@router.post(
    "/credentials",
    response_model=CredentialRead,
    status_code=status.HTTP_201_CREATED,
    responses=ERROR_RESPONSES,
)
async def create_credential(
    payload: CredentialCreateRequest,
    service: AIFoundationServiceDependency,
    principal: PrincipalDependency,
    request_id: RequestIdDependency,
    idempotency_key: Annotated[UUID, Header(alias="Idempotency-Key")],
) -> CredentialRead:
    return await service.create_credential(
        payload=payload,
        principal=principal,
        idempotency_key=idempotency_key,
        request_id=request_id,
    )


@router.post(
    "/credentials/{credential_id}/validate",
    response_model=CredentialValidationResponse,
    responses=ERROR_RESPONSES,
)
async def validate_saved_credential(
    service: AIFoundationServiceDependency,
    principal: PrincipalDependency,
    request_id: RequestIdDependency,
    credential_id: Annotated[UUID, Path()],
    idempotency_key: Annotated[UUID, Header(alias="Idempotency-Key")],
) -> CredentialValidationResponse:
    return await service.validate_saved(
        credential_id=credential_id,
        principal=principal,
        idempotency_key=idempotency_key,
        request_id=request_id,
    )


@router.post(
    "/credentials/{credential_id}/revoke",
    response_model=CredentialRead,
    responses=ERROR_RESPONSES,
)
async def revoke_credential(
    payload: CredentialMutationRequest,
    service: AIFoundationServiceDependency,
    principal: PrincipalDependency,
    request_id: RequestIdDependency,
    credential_id: Annotated[UUID, Path()],
    idempotency_key: Annotated[UUID, Header(alias="Idempotency-Key")],
) -> CredentialRead:
    return await service.revoke_credential(
        credential_id=credential_id,
        payload=payload,
        principal=principal,
        idempotency_key=idempotency_key,
        request_id=request_id,
    )


@router.post(
    "/credentials/{credential_id}/replace",
    response_model=CredentialRead,
    status_code=status.HTTP_201_CREATED,
    responses=ERROR_RESPONSES,
)
async def replace_credential(
    payload: CredentialReplaceRequest,
    service: AIFoundationServiceDependency,
    principal: PrincipalDependency,
    request_id: RequestIdDependency,
    credential_id: Annotated[UUID, Path()],
    idempotency_key: Annotated[UUID, Header(alias="Idempotency-Key")],
) -> CredentialRead:
    return await service.replace_credential(
        credential_id=credential_id,
        payload=payload,
        principal=principal,
        idempotency_key=idempotency_key,
        request_id=request_id,
    )


@router.post(
    "/credentials/{credential_id}/grants",
    response_model=CredentialGrantRead,
    status_code=status.HTTP_201_CREATED,
    responses=ERROR_RESPONSES,
)
async def create_credential_grant(
    payload: CredentialGrantRequest,
    service: AIFoundationServiceDependency,
    principal: PrincipalDependency,
    request_id: RequestIdDependency,
    credential_id: Annotated[UUID, Path()],
    idempotency_key: Annotated[UUID, Header(alias="Idempotency-Key")],
) -> CredentialGrantRead:
    return await service.create_grant(
        credential_id=credential_id,
        payload=payload,
        principal=principal,
        idempotency_key=idempotency_key,
        request_id=request_id,
    )


@router.delete(
    "/credentials/{credential_id}/grants/{project_id}",
    response_model=CredentialGrantRead,
    responses=ERROR_RESPONSES,
)
async def revoke_credential_grant(
    payload: CredentialMutationRequest,
    service: AIFoundationServiceDependency,
    principal: PrincipalDependency,
    request_id: RequestIdDependency,
    credential_id: Annotated[UUID, Path()],
    project_id: Annotated[UUID, Path()],
    idempotency_key: Annotated[UUID, Header(alias="Idempotency-Key")],
) -> CredentialGrantRead:
    return await service.revoke_grant(
        credential_id=credential_id,
        project_id=project_id,
        payload=payload,
        principal=principal,
        idempotency_key=idempotency_key,
        request_id=request_id,
    )


@router.get("/preferences", response_model=UserPreferenceRead, responses=ERROR_RESPONSES)
async def get_user_preference(
    service: AIFoundationServiceDependency,
    principal: PrincipalDependency,
) -> UserPreferenceRead:
    return await service.get_user_preference(principal)


@router.patch("/preferences", response_model=UserPreferenceRead, responses=ERROR_RESPONSES)
async def update_user_preference(
    payload: UserPreferenceUpdate,
    service: AIFoundationServiceDependency,
    principal: PrincipalDependency,
    request_id: RequestIdDependency,
    idempotency_key: Annotated[UUID, Header(alias="Idempotency-Key")],
) -> UserPreferenceRead:
    return await service.update_user_preference(
        payload=payload,
        principal=principal,
        idempotency_key=idempotency_key,
        request_id=request_id,
    )


@router.post(
    "/invocations/preview",
    response_model=InvocationPreviewRead,
    responses=ERROR_RESPONSES,
)
async def preview_invocation(
    payload: InvocationPreviewRequest,
    service: AIFoundationServiceDependency,
    principal: PrincipalDependency,
) -> InvocationPreviewRead:
    return await service.preview_invocation(payload=payload, principal=principal)


@router.post(
    "/invocations",
    response_model=InvocationRead,
    status_code=status.HTTP_201_CREATED,
    responses=ERROR_RESPONSES,
)
async def create_invocation(
    payload: InvocationCreateRequest,
    response: Response,
    service: AIFoundationServiceDependency,
    principal: PrincipalDependency,
    request_id: RequestIdDependency,
    idempotency_key: Annotated[UUID, Header(alias="Idempotency-Key")],
) -> InvocationRead:
    result = await service.create_invocation(
        payload=payload,
        principal=principal,
        idempotency_key=idempotency_key,
        request_id=request_id,
    )
    if result.replayed:
        response.headers["Idempotent-Replayed"] = "true"
    return result


@router.get(
    "/invocations/{invocation_id}",
    response_model=InvocationRead,
    responses=ERROR_RESPONSES,
)
async def get_invocation(
    service: AIFoundationServiceDependency,
    principal: PrincipalDependency,
    invocation_id: Annotated[UUID, Path()],
) -> InvocationRead:
    return await service.get_invocation(invocation_id=invocation_id, principal=principal)


@router.post(
    "/invocations/{invocation_id}/cancel",
    response_model=InvocationRead,
    responses=ERROR_RESPONSES,
)
async def cancel_invocation(
    payload: CancelInvocationRequest,
    service: AIFoundationServiceDependency,
    principal: PrincipalDependency,
    request_id: RequestIdDependency,
    invocation_id: Annotated[UUID, Path()],
    idempotency_key: Annotated[UUID, Header(alias="Idempotency-Key")],
) -> InvocationRead:
    del payload
    return await service.cancel_invocation(
        invocation_id=invocation_id,
        principal=principal,
        request_id=request_id,
        idempotency_key=idempotency_key,
    )


@router.get("/audit", response_model=UsageAuditListResponse, responses=ERROR_RESPONSES)
async def list_audit(
    service: AIFoundationServiceDependency,
    principal: PrincipalDependency,
    project_id: Annotated[UUID | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> UsageAuditListResponse:
    return await service.list_audit(
        principal=principal,
        project_id=project_id,
        limit=limit,
        offset=offset,
    )


project_policy_router = APIRouter(
    prefix="/paint-projects/{project_id}/ai-model-policy",
    tags=["ai-foundation-fixture"],
)


@project_policy_router.get("", response_model=ProjectPolicyRead, responses=ERROR_RESPONSES)
async def get_project_policy(
    service: AIFoundationServiceDependency,
    principal: PrincipalDependency,
    project_id: Annotated[UUID, Path()],
) -> ProjectPolicyRead:
    return await service.get_project_policy(project_id=project_id, principal=principal)


@project_policy_router.patch("", response_model=ProjectPolicyRead, responses=ERROR_RESPONSES)
async def update_project_policy(
    payload: ProjectPolicyUpdate,
    service: AIFoundationServiceDependency,
    principal: PrincipalDependency,
    request_id: RequestIdDependency,
    project_id: Annotated[UUID, Path()],
    idempotency_key: Annotated[UUID, Header(alias="Idempotency-Key")],
) -> ProjectPolicyRead:
    return await service.update_project_policy(
        project_id=project_id,
        payload=payload,
        principal=principal,
        idempotency_key=idempotency_key,
        request_id=request_id,
    )


__all__ = ["project_policy_router", "router"]
