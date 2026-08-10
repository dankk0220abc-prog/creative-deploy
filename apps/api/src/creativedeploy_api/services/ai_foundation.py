"""Transactional AI foundation configuration with fixture-only execution."""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TypeVar

from pydantic import BaseModel, ValidationError
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from creativedeploy_api.ai.canonicalization import canonicalize_and_hash
from creativedeploy_api.ai.constants import (
    CANONICALIZATION_VERSION,
    FIXTURE_CURRENCY,
    FIXTURE_PROVIDER_KEY,
    PROJECTLESS_SCOPE_ID,
)
from creativedeploy_api.ai.encryption import (
    CredentialAAD,
    CredentialCipher,
    EncryptedCredentialPayload,
    SecretBytes,
)
from creativedeploy_api.ai.fixture_provider import (
    FixtureProviderAdapter,
    FixtureProviderError,
)
from creativedeploy_api.core.principal import PrincipalContext
from creativedeploy_api.db.models import (
    AIAuditEvent,
    AICommandIdempotencyRecord,
    AICostLedger,
    AIInvocationEvent,
    AIUsageLedger,
    BudgetReservation,
    CredentialProjectGrant,
    CredentialRecord,
    InvocationAttempt,
    InvocationRequest,
    ModelDefinition,
    ProjectBudgetCounter,
    ProjectBudgetPolicy,
    ProjectModelPolicy,
    ProviderDefinition,
    UserBudgetCounter,
    UserBudgetPolicy,
    UserProviderPreference,
)
from creativedeploy_api.repositories.ai_foundation import (
    SqlAlchemyAIFoundationRepository,
)
from creativedeploy_api.repositories.identity import SqlAlchemyIdentityRepository
from creativedeploy_api.schemas.ai_foundation import (
    AttemptRead,
    CapabilityListResponse,
    CapabilityRead,
    CredentialCreateRequest,
    CredentialGrantRead,
    CredentialGrantRequest,
    CredentialListResponse,
    CredentialMutationRequest,
    CredentialRead,
    CredentialReplaceRequest,
    CredentialValidationResponse,
    CredentialValidationStatus,
    Currency,
    FixtureInvocationPayload,
    InvocationCreateRequest,
    InvocationPreviewRead,
    InvocationPreviewRequest,
    InvocationRead,
    ModelListResponse,
    ModelRead,
    ProjectPolicyRead,
    ProjectPolicyUpdate,
    ProviderKey,
    ProviderListResponse,
    ProviderRead,
    TemporaryCredentialValidationRequest,
    UsageAuditListResponse,
    UsageAuditRead,
    UserPreferenceRead,
    UserPreferenceUpdate,
)
from creativedeploy_api.schemas.errors import ErrorCategory
from creativedeploy_api.schemas.paint_plans import PaintPlanDocument
from creativedeploy_api.services.paint_projects import PaintProjectApplicationError

READ_MODEL = TypeVar("READ_MODEL", bound=BaseModel)
RESERVATION_EXPIRY = timedelta(seconds=120)
VALIDATION_WINDOW = timedelta(minutes=1)
VALIDATION_LIMIT = 5
OPENAI_PROVIDER_KEY: ProviderKey = "openai"
USD_CURRENCY: Currency = "USD"
LIVE_VALIDATION_NOT_AUTHORIZED: CredentialValidationStatus = "live_validation_not_authorized"
TERMINAL_INVOCATION_STATES = {
    "succeeded",
    "failed",
    "cancelled",
    "outcome_unknown",
}
ENVELOPE_FIELDS = (
    "encryption_version",
    "data_algorithm",
    "ciphertext",
    "data_nonce",
    "data_authentication_tag",
    "wrapped_dek",
    "wrap_algorithm",
    "wrap_nonce",
    "wrap_authentication_tag",
    "aad_version",
)


def _configuration_currency(provider: ProviderDefinition) -> Currency | None:
    if (
        provider.provider_key == FIXTURE_PROVIDER_KEY
        and provider.adapter_type == "fixture_local"
        and provider.enabled
        and provider.status == "active"
    ):
        return FIXTURE_CURRENCY
    if (
        provider.provider_key == OPENAI_PROVIDER_KEY
        and provider.adapter_type == "openai_responses"
        and provider.base_url_policy == "provider_managed"
        and not provider.enabled
        and provider.status == "disabled"
    ):
        return USD_CURRENCY
    return None


def _model_matches_provider(model: ModelDefinition, provider: ProviderDefinition) -> bool:
    if model.provider_definition_id != provider.id or model.provider_key != provider.provider_key:
        return False
    if provider.provider_key == FIXTURE_PROVIDER_KEY:
        return model.status == "active"
    return provider.provider_key == OPENAI_PROVIDER_KEY and model.status == "disabled"


def _live_validation_blocked_response(*, persisted: bool) -> CredentialValidationResponse:
    return CredentialValidationResponse(
        provider_key=OPENAI_PROVIDER_KEY,
        valid=False,
        validation_status=LIVE_VALIDATION_NOT_AUTHORIZED,
        message_code="LIVE_VALIDATION_NOT_AUTHORIZED",
        fixture=False,
        local_only=False,
        persisted=persisted,
    )


@dataclass(frozen=True, slots=True)
class AdmissionContext:
    provider: ProviderDefinition
    model: ModelDefinition
    credential: CredentialRecord | None
    temporary_secret: SecretBytes | None
    user_counter: UserBudgetCounter
    project_counter: ProjectBudgetCounter | None
    estimate_minor_units: int
    capability_keys: list[str]


def _fixture_estimate(payload: FixtureInvocationPayload) -> int:
    encoded = repr(sorted(payload.model_dump(mode="json").items())).encode("utf-8")
    input_units = max(1, len(encoded) // 8)
    if payload.paint_plan_input is None:
        return input_units + 12
    paint_regions = sum(
        region.kind == "paint" for region in payload.paint_plan_input.region_set.regions
    )
    return input_units + 200 + (paint_regions * 500)


def _validated_paint_plan_output(
    output: Mapping[str, object],
    *,
    safe_payload: Mapping[str, object],
) -> dict[str, object]:
    """Validate and project Provider output before any durable/browser-visible write."""

    contract = safe_payload.get("paint_plan_contract")
    if not isinstance(contract, Mapping):
        raise ValueError("Paint Plan invocation contract is missing")
    paint_regions = contract.get("paint_regions")
    excluded_region_ids = contract.get("excluded_region_ids")
    if not isinstance(paint_regions, list) or not isinstance(excluded_region_ids, list):
        raise ValueError("Paint Plan region contract is invalid")
    expected: set[tuple[str, str, str]] = set()
    for item in paint_regions:
        if not isinstance(item, Mapping):
            raise ValueError("Paint Plan region identity is invalid")
        region_id = item.get("region_id")
        stable_region_key = item.get("stable_region_key")
        region_label = item.get("region_label")
        if not all(
            isinstance(value, str) for value in (region_id, stable_region_key, region_label)
        ):
            raise ValueError("Paint Plan region identity is invalid")
        expected.add((region_id, stable_region_key, region_label))  # type: ignore[arg-type]
    if not expected or not all(isinstance(value, str) for value in excluded_region_ids):
        raise ValueError("Paint Plan region contract is invalid")
    document = PaintPlanDocument.model_validate(output)
    actual = {
        (str(item.region_id), str(item.stable_region_key), item.region_label)
        for item in document.instructions
    }
    actual_ids = {item[0] for item in actual}
    if actual != expected or actual_ids.intersection(excluded_region_ids):
        raise ValueError("Paint Plan output does not match the exact governed RegionSet")
    return document.model_dump(mode="json")


class AIFoundationError(PaintProjectApplicationError):
    """Safe Phase 3A application error."""


class Phase3UnavailableError(AIFoundationError):
    status_code = 404
    error_code = "PHASE3A_FIXTURE_UNAVAILABLE"
    category: ErrorCategory = "NOT_FOUND"
    message = "The fixture provider foundation is not enabled."


class AIIdentityRequiredError(AIFoundationError):
    status_code = 403
    error_code = "INTERNAL_USER_ID_REQUIRED"
    category: ErrorCategory = "CONFLICT"
    message = "This operation requires an authenticated internal user account."


class AIResourceNotFoundError(AIFoundationError):
    status_code = 404
    error_code = "AI_RESOURCE_NOT_FOUND"
    category: ErrorCategory = "NOT_FOUND"
    message = "The requested AI foundation resource was not found."


class AIAuthorizationError(AIFoundationError):
    status_code = 404
    error_code = "AI_RESOURCE_NOT_FOUND"
    category: ErrorCategory = "NOT_FOUND"
    message = "The requested AI foundation resource was not found."


class AIConflictError(AIFoundationError):
    status_code = 409
    error_code = "AI_FOUNDATION_CONFLICT"
    category: ErrorCategory = "CONFLICT"
    message = "The AI foundation resource changed or conflicts with this request."
    allowed_actions = ("reload", "retry_with_current_revision")


class AIIdempotencyConflictError(AIFoundationError):
    status_code = 409
    error_code = "IDEMPOTENCY_KEY_REUSED"
    category: ErrorCategory = "IDEMPOTENCY_KEY_REUSED"
    message = "The Idempotency-Key was already used with a different payload."


class CredentialRejectedError(AIFoundationError):
    status_code = 422
    error_code = "FIXTURE_CREDENTIAL_REJECTED"
    category: ErrorCategory = "VALIDATION_ERROR"
    message = "The local fixture credential format was rejected."


class ValidationRateLimitedError(AIFoundationError):
    status_code = 429
    error_code = "CREDENTIAL_VALIDATION_RATE_LIMITED"
    category: ErrorCategory = "PROVIDER_RATE_LIMIT"
    message = "Credential validation is temporarily rate limited."
    retryable = True
    allowed_actions = ("retry_later",)


class AdmissionRejectedError(AIFoundationError):
    status_code = 409
    error_code = "INVOCATION_ADMISSION_REJECTED"
    category: ErrorCategory = "CONFLICT"
    message = "The fixture invocation did not satisfy current authorization and policy."
    allowed_actions = ("review_policy", "review_grant", "review_budget")


def _user_id(principal: PrincipalContext) -> uuid.UUID:
    if principal.user_id is None:
        raise AIIdentityRequiredError
    return principal.user_id


def _credential_read(record: CredentialRecord) -> CredentialRead:
    return CredentialRead(
        id=record.id,
        alias=record.alias,
        provider_key=record.provider_key,
        fingerprint=record.key_fingerprint,
        last_four=record.last_four,
        status=record.status,  # type: ignore[arg-type]
        created_at=record.created_at,
        updated_at=record.updated_at,
        revoked_at=record.revoked_at,
        replaced_at=record.replaced_at,
        last_validation_status=record.last_validation_status,
        last_successful_validation_at=record.last_successful_validation_at,
        revision=record.revision,
    )


def _grant_read(grant: CredentialProjectGrant) -> CredentialGrantRead:
    return CredentialGrantRead(
        id=grant.id,
        credential_id=grant.credential_id,
        project_id=grant.project_id,
        active=grant.revoked_at is None,
        created_at=grant.created_at,
        revoked_at=grant.revoked_at,
        revision=grant.revision,
    )


def _encrypted_payload(record: CredentialRecord) -> EncryptedCredentialPayload:
    values = [getattr(record, field) for field in ENVELOPE_FIELDS]
    if any(value is None for value in values):
        raise AIConflictError
    return EncryptedCredentialPayload(
        encryption_version=record.encryption_version or "",
        data_algorithm=record.data_algorithm or "",
        ciphertext=record.ciphertext or b"",
        data_nonce=record.data_nonce or b"",
        data_authentication_tag=record.data_authentication_tag or b"",
        wrapped_dek=record.wrapped_dek or b"",
        wrap_algorithm=record.wrap_algorithm or "",
        wrap_nonce=record.wrap_nonce or b"",
        wrap_authentication_tag=record.wrap_authentication_tag or b"",
        aad_version=record.aad_version or "",
    )


def _erase(record: CredentialRecord, *, status: str, now: datetime) -> None:
    record.status = status
    record.revoked_at = now if status == "revoked" else None
    record.replaced_at = now if status == "replaced" else None
    for field in ENVELOPE_FIELDS:
        setattr(record, field, None)
    record.updated_at = now
    record.revision += 1


class AIFoundationService:
    """Provider configuration service whose invocation path remains fixture-only."""

    def __init__(
        self,
        session: AsyncSession,
        cipher: CredentialCipher,
        adapter: FixtureProviderAdapter,
    ) -> None:
        self._session = session
        self._cipher = cipher
        self._adapter = adapter
        self._repository = SqlAlchemyAIFoundationRepository(session)
        self._identity_repository = SqlAlchemyIdentityRepository(session)

    def _audit(
        self,
        *,
        user_id: uuid.UUID,
        request_id: uuid.UUID,
        action: str,
        outcome: str,
        project_id: uuid.UUID | None = None,
        credential_id: uuid.UUID | None = None,
        invocation_id: uuid.UUID | None = None,
        attempt_id: uuid.UUID | None = None,
        provider_id: uuid.UUID | None = None,
        model_id: uuid.UUID | None = None,
        safe_metadata: Mapping[str, object] | None = None,
    ) -> None:
        self._repository.add(
            AIAuditEvent(
                id=uuid.uuid4(),
                actor_user_id=user_id,
                product_space="paintpilot",
                project_id=project_id,
                credential_id=credential_id,
                invocation_id=invocation_id,
                attempt_id=attempt_id,
                provider_definition_id=provider_id,
                model_definition_id=model_id,
                action=action,
                outcome=outcome,
                request_id=request_id,
                safe_metadata=dict(safe_metadata or {}),
                created_at=datetime.now(UTC),
            )
        )

    async def _command_replay(
        self,
        *,
        user_id: uuid.UUID,
        scope: str,
        idempotency_key: uuid.UUID,
        identity_payload: object,
        response_type: type[READ_MODEL],
    ) -> READ_MODEL | None:
        _, payload_hash = canonicalize_and_hash(identity_payload)
        lock_scope = f"{user_id}:{scope}:{idempotency_key}"
        await self._session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:scope, 0))"),
            {"scope": lock_scope},
        )
        existing = (
            await self._session.execute(
                select(AICommandIdempotencyRecord).where(
                    AICommandIdempotencyRecord.requesting_user_id == user_id,
                    AICommandIdempotencyRecord.command_scope == scope,
                    AICommandIdempotencyRecord.idempotency_key == idempotency_key,
                )
            )
        ).scalar_one_or_none()
        if existing is None:
            return None
        if existing.payload_hash != payload_hash:
            raise AIIdempotencyConflictError
        return response_type.model_validate(existing.response_snapshot)

    def _complete_command(
        self,
        *,
        user_id: uuid.UUID,
        scope: str,
        idempotency_key: uuid.UUID,
        identity_payload: object,
        response: BaseModel,
        http_status: int = 200,
    ) -> None:
        _, payload_hash = canonicalize_and_hash(identity_payload)
        self._repository.add(
            AICommandIdempotencyRecord(
                id=uuid.uuid4(),
                requesting_user_id=user_id,
                command_scope=scope,
                idempotency_key=idempotency_key,
                payload_hash=payload_hash,
                response_snapshot=response.model_dump(mode="json"),
                http_status=http_status,
                created_at=datetime.now(UTC),
            )
        )

    async def list_providers(self) -> ProviderListResponse:
        grouped: dict[uuid.UUID, ProviderRead] = {}
        async with self._session.begin():
            for provider, capability, link in await self._repository.list_providers():
                item = grouped.get(provider.id)
                capability_read = CapabilityRead(
                    id=capability.id,
                    capability_key=capability.capability_key,
                    display_name=capability.display_name,
                    status=capability.status,
                    source=link.source,
                    trust_status=link.trust_status,
                )
                if item is None:
                    grouped[provider.id] = ProviderRead(
                        id=provider.id,
                        provider_key=provider.provider_key,
                        display_name=provider.display_name,
                        adapter_type=provider.adapter_type,
                        enabled=provider.enabled,
                        status=provider.status,
                        catalog_status=provider.catalog_status,
                        catalog_fresh_at=provider.catalog_fresh_at,
                        local_only=provider.provider_key == FIXTURE_PROVIDER_KEY,
                        real_model_calls=False,
                        real_cost=False,
                        capabilities=[capability_read],
                    )
                else:
                    item.capabilities.append(capability_read)
        return ProviderListResponse(items=list(grouped.values()))

    async def list_capabilities(self) -> CapabilityListResponse:
        async with self._session.begin():
            capabilities = await self._repository.list_capabilities()
        return CapabilityListResponse(
            items=[
                CapabilityRead(
                    id=item.id,
                    capability_key=item.capability_key,
                    display_name=item.display_name,
                    status=item.status,
                )
                for item in capabilities
            ]
        )

    async def list_models(self, provider_key: str) -> ModelListResponse:
        grouped: dict[uuid.UUID, ModelRead] = {}
        async with self._session.begin():
            rows = await self._repository.list_models(provider_key)
            if not rows:
                raise AIResourceNotFoundError
            for model, capability, link in rows:
                capability_read = CapabilityRead(
                    id=capability.id,
                    capability_key=capability.capability_key,
                    display_name=capability.display_name,
                    status=capability.status,
                    source=link.source,
                    trust_status=link.trust_status,
                )
                item = grouped.get(model.id)
                if item is None:
                    grouped[model.id] = ModelRead(
                        id=model.id,
                        provider_key=model.provider_key,
                        model_id=model.model_id,
                        display_name=model.display_name,
                        catalog_source=model.catalog_source,
                        catalog_status=model.catalog_status,
                        catalog_fresh_at=model.catalog_fresh_at,
                        status=model.status,
                        context_window=model.context_window,
                        pricing_minor_units=model.pricing_minor_units,
                        pricing_currency=model.pricing_currency,  # type: ignore[arg-type]
                        local_only=model.provider_key == FIXTURE_PROVIDER_KEY,
                        capabilities=[capability_read],
                    )
                else:
                    item.capabilities.append(capability_read)
        return ModelListResponse(items=list(grouped.values()))

    async def list_credentials(self, principal: PrincipalContext) -> CredentialListResponse:
        user_id = _user_id(principal)
        async with self._session.begin():
            records = await self._repository.list_credentials(user_id)
        return CredentialListResponse(items=[_credential_read(record) for record in records])

    async def validate_temporary(
        self,
        *,
        payload: TemporaryCredentialValidationRequest,
        principal: PrincipalContext,
        idempotency_key: uuid.UUID,
        request_id: uuid.UUID,
    ) -> CredentialValidationResponse:
        user_id = _user_id(principal)
        if payload.provider_key == OPENAI_PROVIDER_KEY:
            identity: dict[str, object] = {
                "provider_key": OPENAI_PROVIDER_KEY,
                "credential_present": True,
            }
            async with self._session.begin():
                replay = await self._command_replay(
                    user_id=user_id,
                    scope="credential_validate_temporary",
                    idempotency_key=idempotency_key,
                    identity_payload=identity,
                    response_type=CredentialValidationResponse,
                )
                if replay is not None:
                    return replay
                if await self._repository.lock_active_user(user_id) is None:
                    raise AIAuthorizationError
                provider = await self._repository.get_provider(OPENAI_PROVIDER_KEY)
                if provider is None or _configuration_currency(provider) != USD_CURRENCY:
                    raise AIResourceNotFoundError
                response = _live_validation_blocked_response(persisted=False)
                self._audit(
                    user_id=user_id,
                    request_id=request_id,
                    action="credential_validate_temporary",
                    outcome=LIVE_VALIDATION_NOT_AUTHORIZED,
                    provider_id=provider.id,
                    safe_metadata={
                        "credential_present": True,
                        "fixture": False,
                        "live_execution_authorized": False,
                    },
                )
                self._complete_command(
                    user_id=user_id,
                    scope="credential_validate_temporary",
                    idempotency_key=idempotency_key,
                    identity_payload=identity,
                    response=response,
                )
                return response
        plaintext = payload.credential.get_secret_value().encode("utf-8")
        identity = {
            "provider_key": payload.provider_key,
            "credential_fingerprint": self._cipher.fingerprint(plaintext),
        }
        async with self._session.begin():
            replay = await self._command_replay(
                user_id=user_id,
                scope="credential_validate_temporary",
                idempotency_key=idempotency_key,
                identity_payload=identity,
                response_type=CredentialValidationResponse,
            )
            if replay is not None:
                return replay
            if await self._repository.lock_active_user(user_id) is None:
                raise AIAuthorizationError
            count = await self._repository.validation_count_since(
                user_id, datetime.now(UTC) - VALIDATION_WINDOW
            )
            if count >= VALIDATION_LIMIT:
                raise ValidationRateLimitedError
            validation = self._adapter.validate_credential(SecretBytes(plaintext))
            response = CredentialValidationResponse(
                provider_key=FIXTURE_PROVIDER_KEY,
                valid=validation.valid,
                validation_status=validation.status,
                message_code=validation.message_code,
                fixture=True,
                local_only=True,
                persisted=False,
            )
            self._audit(
                user_id=user_id,
                request_id=request_id,
                action="credential_validate_temporary",
                outcome=validation.status,
                safe_metadata={"credential_present": True, "fixture": True},
            )
            self._complete_command(
                user_id=user_id,
                scope="credential_validate_temporary",
                idempotency_key=idempotency_key,
                identity_payload=identity,
                response=response,
            )
            return response

    async def create_credential(
        self,
        *,
        payload: CredentialCreateRequest,
        principal: PrincipalContext,
        idempotency_key: uuid.UUID,
        request_id: uuid.UUID,
    ) -> CredentialRead:
        user_id = _user_id(principal)
        plaintext = payload.credential.get_secret_value().encode("utf-8")
        fingerprint = self._cipher.fingerprint(plaintext)
        identity = {
            "provider_key": payload.provider_key,
            "alias": payload.alias,
            "credential_fingerprint": fingerprint,
            "confirm_save": payload.confirm_save,
        }
        async with self._session.begin():
            replay = await self._command_replay(
                user_id=user_id,
                scope="credential_create",
                idempotency_key=idempotency_key,
                identity_payload=identity,
                response_type=CredentialRead,
            )
            if replay is not None:
                return replay
            if await self._repository.lock_active_user(user_id) is None:
                raise AIAuthorizationError
            provider = await self._repository.get_provider(payload.provider_key)
            expected_currency: Currency = (
                FIXTURE_CURRENCY if payload.provider_key == FIXTURE_PROVIDER_KEY else USD_CURRENCY
            )
            if provider is None or _configuration_currency(provider) != expected_currency:
                raise AIResourceNotFoundError
            now = datetime.now(UTC)
            validation_status: CredentialValidationStatus
            if provider.provider_key == FIXTURE_PROVIDER_KEY:
                validation = self._adapter.validate_credential(SecretBytes(plaintext))
                if not validation.valid:
                    raise CredentialRejectedError
                validation_status = validation.status
                successful_validation_at: datetime | None = now
            else:
                validation_status = LIVE_VALIDATION_NOT_AUTHORIZED
                successful_validation_at = None
            credential_id = uuid.uuid4()
            aad = CredentialAAD(
                credential_id=credential_id,
                owner_user_id=user_id,
                provider_key=provider.provider_key,
            )
            encrypted = self._cipher.encrypt(plaintext, aad=aad)
            record = CredentialRecord(
                id=credential_id,
                owner_user_id=user_id,
                provider_definition_id=provider.id,
                provider_key=provider.provider_key,
                key_fingerprint=fingerprint,
                last_four=plaintext[-4:].decode("utf-8", errors="replace"),
                alias=payload.alias,
                status="active",
                encryption_version=encrypted.encryption_version,
                data_algorithm=encrypted.data_algorithm,
                ciphertext=encrypted.ciphertext,
                data_nonce=encrypted.data_nonce,
                data_authentication_tag=encrypted.data_authentication_tag,
                wrapped_dek=encrypted.wrapped_dek,
                wrap_algorithm=encrypted.wrap_algorithm,
                wrap_nonce=encrypted.wrap_nonce,
                wrap_authentication_tag=encrypted.wrap_authentication_tag,
                aad_version=encrypted.aad_version,
                replaces_credential_id=None,
                last_validation_status=validation_status,
                last_successful_validation_at=successful_validation_at,
                revoked_at=None,
                replaced_at=None,
                revision=1,
                created_at=now,
                updated_at=now,
            )
            self._repository.add(record)
            await self._repository.flush()
            response = _credential_read(record)
            self._audit(
                user_id=user_id,
                request_id=request_id,
                action="credential_create",
                outcome="succeeded",
                credential_id=record.id,
                provider_id=provider.id,
                safe_metadata=(
                    {"alias": record.alias, "fixture": True}
                    if provider.provider_key == FIXTURE_PROVIDER_KEY
                    else {
                        "alias": record.alias,
                        "fixture": False,
                        "live_execution_authorized": False,
                    }
                ),
            )
            self._complete_command(
                user_id=user_id,
                scope="credential_create",
                idempotency_key=idempotency_key,
                identity_payload=identity,
                response=response,
                http_status=201,
            )
            return response

    async def validate_saved(
        self,
        *,
        credential_id: uuid.UUID,
        principal: PrincipalContext,
        idempotency_key: uuid.UUID,
        request_id: uuid.UUID,
    ) -> CredentialValidationResponse:
        user_id = _user_id(principal)
        identity = {"credential_id": str(credential_id)}
        async with self._session.begin():
            replay = await self._command_replay(
                user_id=user_id,
                scope=f"credential_validate_saved:{credential_id}",
                idempotency_key=idempotency_key,
                identity_payload=identity,
                response_type=CredentialValidationResponse,
            )
            if replay is not None:
                return replay
            await self._repository.lock_active_user(user_id)
            record = await self._repository.get_owned_credential(
                credential_id=credential_id, owner_user_id=user_id, for_update=True
            )
            if record is None or record.status != "active":
                raise AIResourceNotFoundError
            if record.provider_key == OPENAI_PROVIDER_KEY:
                provider = await self._repository.get_provider(OPENAI_PROVIDER_KEY)
                if (
                    provider is None
                    or provider.id != record.provider_definition_id
                    or _configuration_currency(provider) != USD_CURRENCY
                ):
                    raise AIResourceNotFoundError
                now = datetime.now(UTC)
                record.last_validation_status = LIVE_VALIDATION_NOT_AUTHORIZED
                record.last_successful_validation_at = None
                record.updated_at = now
                record.revision += 1
                response = _live_validation_blocked_response(persisted=True)
                self._audit(
                    user_id=user_id,
                    request_id=request_id,
                    action="credential_validate_saved",
                    outcome=LIVE_VALIDATION_NOT_AUTHORIZED,
                    credential_id=record.id,
                    provider_id=record.provider_definition_id,
                    safe_metadata={
                        "credential_present": True,
                        "fixture": False,
                        "live_execution_authorized": False,
                    },
                )
                self._complete_command(
                    user_id=user_id,
                    scope=f"credential_validate_saved:{credential_id}",
                    idempotency_key=idempotency_key,
                    identity_payload=identity,
                    response=response,
                )
                return response
            if record.provider_key != FIXTURE_PROVIDER_KEY:
                raise AIResourceNotFoundError
            if (
                await self._repository.validation_count_since(
                    user_id, datetime.now(UTC) - VALIDATION_WINDOW
                )
                >= VALIDATION_LIMIT
            ):
                raise ValidationRateLimitedError
            secret = self._cipher.decrypt(
                _encrypted_payload(record),
                aad=CredentialAAD(
                    credential_id=record.id,
                    owner_user_id=record.owner_user_id,
                    provider_key=record.provider_key,
                    encryption_version=record.encryption_version or "",
                ),
            )
            validation = self._adapter.validate_credential(secret)
            now = datetime.now(UTC)
            record.last_validation_status = validation.status
            record.last_successful_validation_at = now if validation.valid else None
            record.updated_at = now
            record.revision += 1
            response = CredentialValidationResponse(
                provider_key=FIXTURE_PROVIDER_KEY,
                valid=validation.valid,
                validation_status=validation.status,
                message_code=validation.message_code,
                fixture=True,
                local_only=True,
                persisted=True,
            )
            self._audit(
                user_id=user_id,
                request_id=request_id,
                action="credential_validate_saved",
                outcome=validation.status,
                credential_id=record.id,
                provider_id=record.provider_definition_id,
                safe_metadata={"credential_present": True, "fixture": True},
            )
            self._complete_command(
                user_id=user_id,
                scope=f"credential_validate_saved:{credential_id}",
                idempotency_key=idempotency_key,
                identity_payload=identity,
                response=response,
            )
            return response

    async def revoke_credential(
        self,
        *,
        credential_id: uuid.UUID,
        payload: CredentialMutationRequest,
        principal: PrincipalContext,
        idempotency_key: uuid.UUID,
        request_id: uuid.UUID,
    ) -> CredentialRead:
        user_id = _user_id(principal)
        identity = payload.model_dump(mode="json")
        async with self._session.begin():
            replay = await self._command_replay(
                user_id=user_id,
                scope=f"credential_revoke:{credential_id}",
                idempotency_key=idempotency_key,
                identity_payload=identity,
                response_type=CredentialRead,
            )
            if replay is not None:
                return replay
            if await self._repository.lock_active_user(user_id) is None:
                raise AIAuthorizationError
            record = await self._repository.get_owned_credential(
                credential_id=credential_id, owner_user_id=user_id, for_update=True
            )
            if record is None:
                raise AIResourceNotFoundError
            if record.status != "active" or record.revision != payload.expected_revision:
                raise AIConflictError
            grants = await self._repository.lock_credential_grants(record.id)
            now = datetime.now(UTC)
            for grant in grants:
                if grant.revoked_at is None:
                    grant.revoked_at = now
                    grant.revision += 1
            _erase(record, status="revoked", now=now)
            response = _credential_read(record)
            self._audit(
                user_id=user_id,
                request_id=request_id,
                action="credential_revoke",
                outcome="succeeded",
                credential_id=record.id,
                provider_id=record.provider_definition_id,
                safe_metadata={"revoked_grants": sum(g.revoked_at == now for g in grants)},
            )
            self._complete_command(
                user_id=user_id,
                scope=f"credential_revoke:{credential_id}",
                idempotency_key=idempotency_key,
                identity_payload=identity,
                response=response,
            )
            return response

    async def replace_credential(
        self,
        *,
        credential_id: uuid.UUID,
        payload: CredentialReplaceRequest,
        principal: PrincipalContext,
        idempotency_key: uuid.UUID,
        request_id: uuid.UUID,
    ) -> CredentialRead:
        user_id = _user_id(principal)
        plaintext = payload.credential.get_secret_value().encode("utf-8")
        fingerprint = self._cipher.fingerprint(plaintext)
        identity = {
            "alias": payload.alias,
            "credential_fingerprint": fingerprint,
            "expected_revision": payload.expected_revision,
            "confirm_replace": payload.confirm_replace,
        }
        async with self._session.begin():
            replay = await self._command_replay(
                user_id=user_id,
                scope=f"credential_replace:{credential_id}",
                idempotency_key=idempotency_key,
                identity_payload=identity,
                response_type=CredentialRead,
            )
            if replay is not None:
                return replay
            await self._repository.lock_active_user(user_id)
            old = await self._repository.get_owned_credential(
                credential_id=credential_id, owner_user_id=user_id, for_update=True
            )
            if old is None or old.status != "active" or old.revision != payload.expected_revision:
                raise AIConflictError
            provider = await self._repository.get_provider(old.provider_key)
            if (
                provider is None
                or provider.id != old.provider_definition_id
                or _configuration_currency(provider) is None
            ):
                raise AIResourceNotFoundError
            now = datetime.now(UTC)
            validation_status: CredentialValidationStatus
            if old.provider_key == FIXTURE_PROVIDER_KEY:
                validation = self._adapter.validate_credential(SecretBytes(plaintext))
                if not validation.valid:
                    raise CredentialRejectedError
                validation_status = validation.status
                successful_validation_at: datetime | None = now
            elif old.provider_key == OPENAI_PROVIDER_KEY:
                validation_status = LIVE_VALIDATION_NOT_AUTHORIZED
                successful_validation_at = None
            else:
                raise AIResourceNotFoundError
            grants = await self._repository.lock_credential_grants(old.id)
            new_id = uuid.uuid4()
            encrypted = self._cipher.encrypt(
                plaintext,
                aad=CredentialAAD(
                    credential_id=new_id,
                    owner_user_id=user_id,
                    provider_key=old.provider_key,
                ),
            )
            replacement = CredentialRecord(
                id=new_id,
                owner_user_id=user_id,
                provider_definition_id=old.provider_definition_id,
                provider_key=old.provider_key,
                key_fingerprint=fingerprint,
                last_four=plaintext[-4:].decode("utf-8", errors="replace"),
                alias=payload.alias.strip(),
                status="active",
                encryption_version=encrypted.encryption_version,
                data_algorithm=encrypted.data_algorithm,
                ciphertext=encrypted.ciphertext,
                data_nonce=encrypted.data_nonce,
                data_authentication_tag=encrypted.data_authentication_tag,
                wrapped_dek=encrypted.wrapped_dek,
                wrap_algorithm=encrypted.wrap_algorithm,
                wrap_nonce=encrypted.wrap_nonce,
                wrap_authentication_tag=encrypted.wrap_authentication_tag,
                aad_version=encrypted.aad_version,
                replaces_credential_id=old.id,
                last_validation_status=validation_status,
                last_successful_validation_at=successful_validation_at,
                revoked_at=None,
                replaced_at=None,
                revision=1,
                created_at=now,
                updated_at=now,
            )
            self._repository.add(replacement)
            for grant in grants:
                if grant.revoked_at is None:
                    grant.revoked_at = now
                    grant.revision += 1
            _erase(old, status="replaced", now=now)
            await self._repository.flush()
            response = _credential_read(replacement)
            self._audit(
                user_id=user_id,
                request_id=request_id,
                action="credential_replace",
                outcome="succeeded",
                credential_id=replacement.id,
                provider_id=replacement.provider_definition_id,
                safe_metadata=(
                    {
                        "replaces_credential_id": str(old.id),
                        "grants_transferred": False,
                    }
                    if old.provider_key == FIXTURE_PROVIDER_KEY
                    else {
                        "replaces_credential_id": str(old.id),
                        "grants_transferred": False,
                        "fixture": False,
                        "live_execution_authorized": False,
                    }
                ),
            )
            self._complete_command(
                user_id=user_id,
                scope=f"credential_replace:{credential_id}",
                idempotency_key=idempotency_key,
                identity_payload=identity,
                response=response,
                http_status=201,
            )
            return response

    async def create_grant(
        self,
        *,
        credential_id: uuid.UUID,
        payload: CredentialGrantRequest,
        principal: PrincipalContext,
        idempotency_key: uuid.UUID,
        request_id: uuid.UUID,
    ) -> CredentialGrantRead:
        user_id = _user_id(principal)
        identity = payload.model_dump(mode="json")
        async with self._session.begin():
            replay = await self._command_replay(
                user_id=user_id,
                scope=f"credential_grant:{credential_id}:{payload.project_id}",
                idempotency_key=idempotency_key,
                identity_payload=identity,
                response_type=CredentialGrantRead,
            )
            if replay is not None:
                return replay
            await self._repository.lock_active_user(user_id)
            access = await self._identity_repository.resolve_project_access(
                project_id=payload.project_id,
                principal_id=principal.principal_id,
                user_id=user_id,
                for_update=True,
            )
            if access is None or access.project.status == "ABANDONED":
                raise AIAuthorizationError
            credential = await self._repository.get_owned_credential(
                credential_id=credential_id, owner_user_id=user_id, for_update=True
            )
            if (
                credential is None
                or credential.status != "active"
                or credential.revision != payload.expected_credential_revision
            ):
                raise AIConflictError
            existing = await self._repository.get_active_grant(
                credential_id=credential_id, project_id=payload.project_id, for_update=True
            )
            if existing is None:
                existing = CredentialProjectGrant(
                    id=uuid.uuid4(),
                    credential_id=credential_id,
                    project_id=payload.project_id,
                    granted_by_user_id=user_id,
                    created_at=datetime.now(UTC),
                    revoked_at=None,
                    revision=1,
                )
                self._repository.add(existing)
                await self._repository.flush()
            response = _grant_read(existing)
            self._audit(
                user_id=user_id,
                request_id=request_id,
                action="credential_grant_create",
                outcome="succeeded",
                project_id=payload.project_id,
                credential_id=credential_id,
                safe_metadata={"ownership_transferred": False},
            )
            self._complete_command(
                user_id=user_id,
                scope=f"credential_grant:{credential_id}:{payload.project_id}",
                idempotency_key=idempotency_key,
                identity_payload=identity,
                response=response,
                http_status=201,
            )
            return response

    async def revoke_grant(
        self,
        *,
        credential_id: uuid.UUID,
        project_id: uuid.UUID,
        payload: CredentialMutationRequest,
        principal: PrincipalContext,
        idempotency_key: uuid.UUID,
        request_id: uuid.UUID,
    ) -> CredentialGrantRead:
        user_id = _user_id(principal)
        identity = payload.model_dump(mode="json")
        async with self._session.begin():
            replay = await self._command_replay(
                user_id=user_id,
                scope=f"credential_grant_revoke:{credential_id}:{project_id}",
                idempotency_key=idempotency_key,
                identity_payload=identity,
                response_type=CredentialGrantRead,
            )
            if replay is not None:
                return replay
            await self._repository.lock_active_user(user_id)
            access = await self._identity_repository.resolve_project_access(
                project_id=project_id,
                principal_id=principal.principal_id,
                user_id=user_id,
                for_update=True,
            )
            credential = await self._repository.get_owned_credential(
                credential_id=credential_id, owner_user_id=user_id, for_update=True
            )
            if access is None or credential is None:
                raise AIAuthorizationError
            grant = await self._repository.get_active_grant(
                credential_id=credential_id, project_id=project_id, for_update=True
            )
            if grant is None or grant.revision != payload.expected_revision:
                raise AIConflictError
            grant.revoked_at = datetime.now(UTC)
            grant.revision += 1
            response = _grant_read(grant)
            self._audit(
                user_id=user_id,
                request_id=request_id,
                action="credential_grant_revoke",
                outcome="succeeded",
                project_id=project_id,
                credential_id=credential_id,
            )
            self._complete_command(
                user_id=user_id,
                scope=f"credential_grant_revoke:{credential_id}:{project_id}",
                idempotency_key=idempotency_key,
                identity_payload=identity,
                response=response,
            )
            return response

    async def _preference_currency(self, preference: UserProviderPreference) -> Currency:
        if preference.cost_warning_currency in {FIXTURE_CURRENCY, USD_CURRENCY}:
            return preference.cost_warning_currency  # type: ignore[return-value]
        if preference.default_provider_definition_id is not None:
            provider = await self._repository.get_provider_by_id(
                preference.default_provider_definition_id
            )
            if provider is not None:
                currency = _configuration_currency(provider)
                if currency is not None:
                    return currency
        return FIXTURE_CURRENCY

    async def _user_preference_read(self, user_id: uuid.UUID) -> UserPreferenceRead:
        preference = await self._repository.get_preference(user_id)
        if preference is None:
            return UserPreferenceRead(
                enabled=False,
                default_provider_definition_id=None,
                default_model_definition_id=None,
                default_credential_id=None,
                timeout_ms=30_000,
                streaming_enabled=False,
                cost_warning_minor_units=None,
                currency=FIXTURE_CURRENCY,
                budget_per_invocation_minor_units=None,
                budget_cumulative_minor_units=None,
                budget_window_seconds=None,
                revision=0,
            )
        currency = await self._preference_currency(preference)
        budget = await self._repository.get_user_budget_policy(user_id, currency=currency)
        return UserPreferenceRead(
            enabled=preference.enabled,
            default_provider_definition_id=preference.default_provider_definition_id,
            default_model_definition_id=preference.default_model_definition_id,
            default_credential_id=preference.default_credential_id,
            timeout_ms=preference.timeout_ms,
            streaming_enabled=preference.streaming_enabled,
            cost_warning_minor_units=preference.cost_warning_minor_units,
            currency=currency,
            budget_per_invocation_minor_units=(
                budget.per_invocation_limit_minor_units if budget is not None else None
            ),
            budget_cumulative_minor_units=(
                budget.cumulative_limit_minor_units if budget is not None else None
            ),
            budget_window_seconds=budget.window_seconds if budget is not None else None,
            revision=preference.revision,
        )

    async def get_user_preference(self, principal: PrincipalContext) -> UserPreferenceRead:
        user_id = _user_id(principal)
        async with self._session.begin():
            if await self._repository.lock_active_user(user_id) is None:
                raise AIAuthorizationError
            return await self._user_preference_read(user_id)

    async def update_user_preference(
        self,
        *,
        payload: UserPreferenceUpdate,
        principal: PrincipalContext,
        idempotency_key: uuid.UUID,
        request_id: uuid.UUID,
    ) -> UserPreferenceRead:
        user_id = _user_id(principal)
        identity = payload.model_dump(mode="json")
        async with self._session.begin():
            replay = await self._command_replay(
                user_id=user_id,
                scope="user_provider_preference_update",
                idempotency_key=idempotency_key,
                identity_payload=identity,
                response_type=UserPreferenceRead,
            )
            if replay is not None:
                return replay
            if await self._repository.lock_active_user(user_id) is None:
                raise AIAuthorizationError
            references = (
                payload.default_provider_definition_id,
                payload.default_model_definition_id,
                payload.default_credential_id,
            )
            if payload.enabled and any(value is None for value in references):
                raise AdmissionRejectedError
            provider = (
                None
                if payload.default_provider_definition_id is None
                else await self._repository.get_provider_by_id(
                    payload.default_provider_definition_id
                )
            )
            model = (
                None
                if payload.default_model_definition_id is None
                else await self._repository.get_model(payload.default_model_definition_id)
            )
            credential = (
                None
                if payload.default_credential_id is None
                else await self._repository.get_owned_credential(
                    credential_id=payload.default_credential_id,
                    owner_user_id=user_id,
                    for_update=True,
                )
            )
            if payload.default_provider_definition_id is not None and provider is None:
                raise AIResourceNotFoundError
            if payload.default_model_definition_id is not None and model is None:
                raise AIResourceNotFoundError
            if payload.default_credential_id is not None and (
                credential is None or credential.status != "active"
            ):
                raise AIResourceNotFoundError
            referenced_provider_ids = {
                value
                for value in (
                    provider.id if provider is not None else None,
                    model.provider_definition_id if model is not None else None,
                    credential.provider_definition_id if credential is not None else None,
                )
                if value is not None
            }
            if len(referenced_provider_ids) > 1:
                raise AdmissionRejectedError
            configured_provider = provider
            if configured_provider is None and referenced_provider_ids:
                configured_provider = await self._repository.get_provider_by_id(
                    next(iter(referenced_provider_ids))
                )
            if configured_provider is None:
                if referenced_provider_ids or payload.currency != FIXTURE_CURRENCY:
                    raise AdmissionRejectedError
            else:
                configured_currency = _configuration_currency(configured_provider)
                if configured_currency != payload.currency:
                    raise AdmissionRejectedError
                if model is not None and not _model_matches_provider(model, configured_provider):
                    raise AdmissionRejectedError
                if credential is not None and (
                    credential.provider_definition_id != configured_provider.id
                    or credential.provider_key != configured_provider.provider_key
                ):
                    raise AdmissionRejectedError
            preference = await self._repository.get_preference(user_id, for_update=True)
            current_revision = preference.revision if preference is not None else 0
            if current_revision != payload.expected_revision:
                raise AIConflictError
            now = datetime.now(UTC)
            if preference is None:
                preference = UserProviderPreference(
                    id=uuid.uuid4(),
                    user_id=user_id,
                    enabled=payload.enabled,
                    default_provider_definition_id=payload.default_provider_definition_id,
                    default_model_definition_id=payload.default_model_definition_id,
                    default_credential_id=payload.default_credential_id,
                    timeout_ms=payload.timeout_ms,
                    streaming_enabled=False,
                    cost_warning_minor_units=payload.cost_warning_minor_units,
                    cost_warning_currency=(
                        payload.currency if payload.cost_warning_minor_units is not None else None
                    ),
                    revision=1,
                    updated_at=now,
                )
                self._repository.add(preference)
            else:
                preference.enabled = payload.enabled
                preference.default_provider_definition_id = payload.default_provider_definition_id
                preference.default_model_definition_id = payload.default_model_definition_id
                preference.default_credential_id = payload.default_credential_id
                preference.timeout_ms = payload.timeout_ms
                preference.streaming_enabled = False
                preference.cost_warning_minor_units = payload.cost_warning_minor_units
                preference.cost_warning_currency = (
                    payload.currency if payload.cost_warning_minor_units is not None else None
                )
                preference.revision += 1
                preference.updated_at = now
            budget = await self._repository.get_user_budget_policy(
                user_id, currency=payload.currency, for_update=True
            )
            if budget is None:
                budget = UserBudgetPolicy(
                    id=uuid.uuid4(),
                    user_id=user_id,
                    product_space="paintpilot",
                    currency=payload.currency,
                    enabled=payload.enabled,
                    per_invocation_limit_minor_units=(payload.budget_per_invocation_minor_units),
                    cumulative_limit_minor_units=payload.budget_cumulative_minor_units,
                    window_seconds=payload.budget_window_seconds,
                    allow_unknown_cost=False,
                    unknown_cost_reservation_minor_units=0,
                    revision=1,
                    updated_at=now,
                )
                self._repository.add(budget)
            else:
                budget.enabled = payload.enabled
                budget.per_invocation_limit_minor_units = payload.budget_per_invocation_minor_units
                budget.cumulative_limit_minor_units = payload.budget_cumulative_minor_units
                budget.window_seconds = payload.budget_window_seconds
                budget.allow_unknown_cost = False
                budget.unknown_cost_reservation_minor_units = 0
                budget.revision += 1
                budget.updated_at = now
            counter = await self._repository.get_user_counter(
                user_id, now, currency=payload.currency, for_update=True
            )
            if (
                counter is None
                or int((counter.window_end - counter.window_start).total_seconds())
                != payload.budget_window_seconds
            ):
                self._repository.add(
                    UserBudgetCounter(
                        id=uuid.uuid4(),
                        user_id=user_id,
                        product_space="paintpilot",
                        currency=payload.currency,
                        window_start=now,
                        window_end=now + timedelta(seconds=payload.budget_window_seconds),
                        limit_minor_units=payload.budget_cumulative_minor_units,
                        committed_minor_units=0,
                        reserved_minor_units=0,
                        revision=1,
                    )
                )
            elif (
                counter.committed_minor_units + counter.reserved_minor_units
                <= payload.budget_cumulative_minor_units
            ):
                counter.limit_minor_units = payload.budget_cumulative_minor_units
                counter.revision += 1
            await self._repository.flush()
            response = await self._user_preference_read(user_id)
            self._audit(
                user_id=user_id,
                request_id=request_id,
                action="user_provider_preference_update",
                outcome="succeeded",
                credential_id=payload.default_credential_id,
                provider_id=payload.default_provider_definition_id,
                model_id=payload.default_model_definition_id,
                safe_metadata=(
                    {"enabled": payload.enabled, "fixture": True}
                    if payload.currency == FIXTURE_CURRENCY
                    else {
                        "enabled": payload.enabled,
                        "currency": payload.currency,
                        "fixture": False,
                        "live_execution_authorized": False,
                    }
                ),
            )
            self._complete_command(
                user_id=user_id,
                scope="user_provider_preference_update",
                idempotency_key=idempotency_key,
                identity_payload=identity,
                response=response,
            )
            return response

    async def _project_policy_read(self, project_id: uuid.UUID) -> ProjectPolicyRead:
        policy = await self._repository.get_project_policy(project_id)
        if policy is None:
            return ProjectPolicyRead(
                project_id=project_id,
                enabled=False,
                default_provider_definition_id=None,
                default_model_definition_id=None,
                default_credential_id=None,
                provider_allowlist=[],
                model_allowlist=[],
                capability_allowlist=[],
                credential_allowlist=[],
                active_grant_credential_ids=(
                    await self._repository.active_grant_credential_ids(project_id)
                ),
                per_invocation_limit_minor_units=None,
                cumulative_limit_minor_units=None,
                budget_window_seconds=None,
                currency=FIXTURE_CURRENCY,
                allow_unknown_cost=False,
                allow_manual_model_id=False,
                allow_fallback=False,
                require_paid_call_confirmation=True,
                resolved_status="not_configured",
                revision=0,
            )
        budget = await self._repository.get_project_budget_policy(
            project_id, currency=policy.currency
        )
        providers, models, capabilities, credentials = await self._repository.policy_allowlists(
            policy.id
        )
        grants = await self._repository.active_grant_credential_ids(project_id)
        provider = (
            None
            if policy.default_provider_definition_id is None
            else await self._repository.get_provider_by_id(policy.default_provider_definition_id)
        )
        model = (
            None
            if policy.default_model_definition_id is None
            else await self._repository.get_model(policy.default_model_definition_id)
        )
        credential = (
            None
            if policy.default_credential_id is None
            else await self._repository.get_credential_by_id(policy.default_credential_id)
        )
        provider_currency = None if provider is None else _configuration_currency(provider)
        required_live_capability_keys = {
            "vision_understanding",
            "structured_output",
        }
        required_live_capability_ids = (
            set()
            if provider is None or provider.provider_key != OPENAI_PROVIDER_KEY
            else set(
                await self._repository.capability_ids_for_keys(
                    sorted(required_live_capability_keys)
                )
            )
        )
        model_capability_keys = (
            set() if model is None else set(await self._repository.model_capability_keys(model.id))
        )
        live_capabilities_ready = (
            provider is None
            or provider.provider_key != OPENAI_PROVIDER_KEY
            or (
                len(required_live_capability_ids) == len(required_live_capability_keys)
                and required_live_capability_ids.issubset(set(capabilities))
                and required_live_capability_keys.issubset(model_capability_keys)
            )
        )
        configuration_ready = (
            policy.enabled
            and budget is not None
            and budget.enabled
            and provider is not None
            and model is not None
            and credential is not None
            and credential.status == "active"
            and provider_currency == policy.currency
            and _model_matches_provider(model, provider)
            and credential.provider_definition_id == provider.id
            and credential.provider_key == provider.provider_key
            and policy.default_provider_definition_id in providers
            and policy.default_model_definition_id in models
            and policy.default_credential_id in credentials
            and policy.default_credential_id in grants
            and live_capabilities_ready
        )
        resolved_status = "blocked"
        if configuration_ready and provider is not None:
            resolved_status = (
                "live_authorization_required"
                if provider.provider_key == OPENAI_PROVIDER_KEY
                else "ready"
            )
        return ProjectPolicyRead(
            project_id=project_id,
            enabled=policy.enabled,
            default_provider_definition_id=policy.default_provider_definition_id,
            default_model_definition_id=policy.default_model_definition_id,
            default_credential_id=policy.default_credential_id,
            provider_allowlist=sorted(providers),
            model_allowlist=sorted(models),
            capability_allowlist=sorted(capabilities),
            credential_allowlist=sorted(credentials),
            active_grant_credential_ids=grants,
            per_invocation_limit_minor_units=policy.per_invocation_limit_minor_units,
            cumulative_limit_minor_units=(
                budget.cumulative_limit_minor_units if budget is not None else None
            ),
            budget_window_seconds=budget.window_seconds if budget is not None else None,
            currency=policy.currency,  # type: ignore[arg-type]
            allow_unknown_cost=policy.allow_unknown_cost,
            allow_manual_model_id=policy.allow_manual_model_id,
            allow_fallback=policy.allow_fallback,
            require_paid_call_confirmation=policy.require_paid_call_confirmation,
            resolved_status=resolved_status,
            revision=policy.revision,
        )

    async def get_project_policy(
        self, *, project_id: uuid.UUID, principal: PrincipalContext
    ) -> ProjectPolicyRead:
        user_id = _user_id(principal)
        async with self._session.begin():
            if await self._repository.lock_active_user(user_id) is None:
                raise AIAuthorizationError
            access = await self._identity_repository.resolve_project_access(
                project_id=project_id,
                principal_id=principal.principal_id,
                user_id=user_id,
            )
            if access is None or access.project.status == "ABANDONED":
                raise AIAuthorizationError
            return await self._project_policy_read(project_id)

    async def update_project_policy(
        self,
        *,
        project_id: uuid.UUID,
        payload: ProjectPolicyUpdate,
        principal: PrincipalContext,
        idempotency_key: uuid.UUID,
        request_id: uuid.UUID,
    ) -> ProjectPolicyRead:
        user_id = _user_id(principal)
        identity = payload.model_dump(mode="json")
        scope = f"project_model_policy_update:{project_id}"
        async with self._session.begin():
            replay = await self._command_replay(
                user_id=user_id,
                scope=scope,
                idempotency_key=idempotency_key,
                identity_payload=identity,
                response_type=ProjectPolicyRead,
            )
            if replay is not None:
                return replay
            if await self._repository.lock_active_user(user_id) is None:
                raise AIAuthorizationError
            access = await self._identity_repository.resolve_project_access(
                project_id=project_id,
                principal_id=principal.principal_id,
                user_id=user_id,
                for_update=True,
            )
            if access is None or access.role != "owner" or access.project.status == "ABANDONED":
                raise AIAuthorizationError
            referenced_credential_ids = sorted(set(payload.credential_allowlist))
            credentials = await self._repository.lock_owned_credentials(
                credential_ids=referenced_credential_ids,
                owner_user_id=user_id,
            )
            if {credential.id for credential in credentials} != set(
                referenced_credential_ids
            ) or any(credential.status != "active" for credential in credentials):
                raise AdmissionRejectedError
            grants = await self._repository.lock_active_grants_for_credentials(
                credential_ids=referenced_credential_ids,
                project_id=project_id,
            )
            if {grant.credential_id for grant in grants} != set(referenced_credential_ids):
                raise AdmissionRejectedError
            policy = await self._repository.get_project_policy(project_id, for_update=True)
            current_revision = policy.revision if policy is not None else 0
            if current_revision != payload.expected_revision:
                raise AIConflictError
            provider_ids = set(payload.provider_allowlist)
            model_ids = set(payload.model_allowlist)
            capability_ids = set(payload.capability_allowlist)
            credential_ids = set(payload.credential_allowlist)
            if (
                await self._repository.existing_provider_ids(list(provider_ids)) != provider_ids
                or await self._repository.existing_model_ids(list(model_ids)) != model_ids
                or await self._repository.existing_capability_ids(list(capability_ids))
                != capability_ids
                or await self._repository.owned_credential_ids(user_id, list(credential_ids))
                != credential_ids
            ):
                raise AIResourceNotFoundError
            provider_records = {
                provider_id: provider
                for provider_id in sorted(provider_ids)
                if (provider := await self._repository.get_provider_by_id(provider_id)) is not None
            }
            model_records = {
                model_id: model
                for model_id in sorted(model_ids)
                if (model := await self._repository.get_model(model_id)) is not None
            }
            if set(provider_records) != provider_ids or set(model_records) != model_ids:
                raise AdmissionRejectedError
            if any(
                _configuration_currency(provider) != payload.currency
                for provider in provider_records.values()
            ):
                raise AdmissionRejectedError
            if any(
                model.provider_definition_id not in provider_records
                or not _model_matches_provider(
                    model, provider_records[model.provider_definition_id]
                )
                for model in model_records.values()
            ):
                raise AdmissionRejectedError
            if any(
                credential.provider_definition_id not in provider_records
                or credential.provider_key
                != provider_records[credential.provider_definition_id].provider_key
                for credential in credentials
            ):
                raise AdmissionRejectedError
            provider = provider_records[payload.default_provider_definition_id]
            model = model_records[payload.default_model_definition_id]
            default_credential = next(
                (
                    credential
                    for credential in credentials
                    if credential.id == payload.default_credential_id
                ),
                None,
            )
            if (
                not _model_matches_provider(model, provider)
                or default_credential is None
                or default_credential.provider_definition_id != provider.id
                or default_credential.provider_key != provider.provider_key
            ):
                raise AdmissionRejectedError
            now = datetime.now(UTC)
            if policy is None:
                policy = ProjectModelPolicy(
                    id=uuid.uuid4(),
                    project_id=project_id,
                    enabled=payload.enabled,
                    default_provider_definition_id=payload.default_provider_definition_id,
                    default_model_definition_id=payload.default_model_definition_id,
                    default_credential_id=payload.default_credential_id,
                    per_invocation_limit_minor_units=(payload.per_invocation_limit_minor_units),
                    currency=payload.currency,
                    allow_unknown_cost=False,
                    unknown_cost_reservation_minor_units=0,
                    allow_manual_model_id=False,
                    allow_fallback=False,
                    require_paid_call_confirmation=(payload.require_paid_call_confirmation),
                    updated_by_user_id=user_id,
                    revision=1,
                    updated_at=now,
                )
                self._repository.add(policy)
                await self._repository.flush()
            else:
                policy.enabled = payload.enabled
                policy.default_provider_definition_id = payload.default_provider_definition_id
                policy.default_model_definition_id = payload.default_model_definition_id
                policy.default_credential_id = payload.default_credential_id
                policy.per_invocation_limit_minor_units = payload.per_invocation_limit_minor_units
                policy.currency = payload.currency
                policy.allow_unknown_cost = False
                policy.unknown_cost_reservation_minor_units = 0
                policy.allow_manual_model_id = False
                policy.allow_fallback = False
                policy.require_paid_call_confirmation = payload.require_paid_call_confirmation
                policy.updated_by_user_id = user_id
                policy.revision += 1
                policy.updated_at = now
            await self._repository.replace_policy_allowlists(
                policy_id=policy.id,
                providers=list(provider_ids),
                models=list(model_ids),
                capabilities=list(capability_ids),
                credentials=list(credential_ids),
                created_at=now,
            )
            budget = await self._repository.get_project_budget_policy(
                project_id, currency=payload.currency, for_update=True
            )
            if budget is None:
                budget = ProjectBudgetPolicy(
                    id=uuid.uuid4(),
                    project_id=project_id,
                    product_space="paintpilot",
                    currency=payload.currency,
                    enabled=payload.enabled,
                    per_invocation_limit_minor_units=(payload.per_invocation_limit_minor_units),
                    cumulative_limit_minor_units=payload.cumulative_limit_minor_units,
                    window_seconds=payload.budget_window_seconds,
                    allow_unknown_cost=False,
                    unknown_cost_reservation_minor_units=0,
                    revision=1,
                    updated_at=now,
                )
                self._repository.add(budget)
            else:
                budget.enabled = payload.enabled
                budget.per_invocation_limit_minor_units = payload.per_invocation_limit_minor_units
                budget.cumulative_limit_minor_units = payload.cumulative_limit_minor_units
                budget.window_seconds = payload.budget_window_seconds
                budget.allow_unknown_cost = False
                budget.unknown_cost_reservation_minor_units = 0
                budget.revision += 1
                budget.updated_at = now
            counter = await self._repository.get_project_counter(
                project_id, now, currency=payload.currency, for_update=True
            )
            if (
                counter is None
                or int((counter.window_end - counter.window_start).total_seconds())
                != payload.budget_window_seconds
            ):
                self._repository.add(
                    ProjectBudgetCounter(
                        id=uuid.uuid4(),
                        project_id=project_id,
                        product_space="paintpilot",
                        currency=payload.currency,
                        window_start=now,
                        window_end=now + timedelta(seconds=payload.budget_window_seconds),
                        limit_minor_units=payload.cumulative_limit_minor_units,
                        committed_minor_units=0,
                        reserved_minor_units=0,
                        revision=1,
                    )
                )
            elif (
                counter.committed_minor_units + counter.reserved_minor_units
                <= payload.cumulative_limit_minor_units
            ):
                counter.limit_minor_units = payload.cumulative_limit_minor_units
                counter.revision += 1
            await self._repository.flush()
            response = await self._project_policy_read(project_id)
            self._audit(
                user_id=user_id,
                request_id=request_id,
                action="project_model_policy_update",
                outcome="succeeded",
                project_id=project_id,
                credential_id=payload.default_credential_id,
                provider_id=payload.default_provider_definition_id,
                model_id=payload.default_model_definition_id,
                safe_metadata=(
                    {"enabled": payload.enabled, "fixture": True}
                    if payload.currency == FIXTURE_CURRENCY
                    else {
                        "enabled": payload.enabled,
                        "currency": payload.currency,
                        "fixture": False,
                        "live_execution_authorized": False,
                    }
                ),
            )
            self._complete_command(
                user_id=user_id,
                scope=scope,
                idempotency_key=idempotency_key,
                identity_payload=identity,
                response=response,
            )
            return response

    async def _preauthorize_invocation_references(
        self,
        *,
        payload: InvocationCreateRequest,
        principal: PrincipalContext,
    ) -> None:
        """Authorize every client-supplied FK before an Invocation row can exist."""
        user_id = _user_id(principal)
        if await self._repository.lock_active_user(user_id) is None:
            raise AIResourceNotFoundError

        project = None
        if payload.project_id is not None:
            access = await self._identity_repository.resolve_project_access(
                project_id=payload.project_id,
                principal_id=principal.principal_id,
                user_id=user_id,
                for_update=True,
            )
            if access is None or access.project.status == "ABANDONED":
                raise AIResourceNotFoundError
            project = access.project

        credential = None
        if payload.credential_id is not None:
            credential = await self._repository.get_owned_credential(
                credential_id=payload.credential_id,
                owner_user_id=user_id,
                for_update=True,
            )
            if credential is None or credential.status != "active":
                raise AIResourceNotFoundError
        if project is not None:
            if credential is None:
                raise AIResourceNotFoundError
            grant = await self._repository.get_active_grant(
                credential_id=credential.id,
                project_id=project.id,
                for_update=True,
            )
            if grant is None:
                raise AIResourceNotFoundError

        provider = await self._repository.get_provider(FIXTURE_PROVIDER_KEY)
        model = await self._repository.get_model(payload.model_definition_id)
        if (
            provider is None
            or provider.id != payload.provider_definition_id
            or provider.status != "active"
            or not provider.enabled
            or model is None
            or model.provider_definition_id != provider.id
            or model.provider_key != provider.provider_key
            or model.status != "active"
            or (
                credential is not None
                and (
                    credential.provider_definition_id != provider.id
                    or credential.provider_key != provider.provider_key
                )
            )
        ):
            raise AIResourceNotFoundError

    async def _resolve_admission(
        self,
        *,
        payload: InvocationPreviewRequest,
        principal: PrincipalContext,
        for_update: bool,
    ) -> AdmissionContext:
        user_id = _user_id(principal)
        if await self._repository.lock_active_user(user_id) is None:
            raise AIAuthorizationError
        project = None
        if payload.project_id is not None:
            access = await self._identity_repository.resolve_project_access(
                project_id=payload.project_id,
                principal_id=principal.principal_id,
                user_id=user_id,
                for_update=for_update,
            )
            if access is None or access.project.status == "ABANDONED":
                raise AIAuthorizationError
            project = access.project
        credential = None
        temporary_secret = None
        if payload.credential_id is not None:
            credential = await self._repository.get_owned_credential(
                credential_id=payload.credential_id,
                owner_user_id=user_id,
                for_update=for_update,
            )
            if credential is None or credential.status != "active":
                raise AdmissionRejectedError
        else:
            assert payload.temporary_credential is not None
            temporary_secret = SecretBytes(
                payload.temporary_credential.get_secret_value().encode("utf-8")
            )
            if not self._adapter.validate_credential(temporary_secret).valid:
                raise CredentialRejectedError
        grant = None
        if project is not None:
            if credential is None:
                raise AdmissionRejectedError
            grant = await self._repository.get_active_grant(
                credential_id=credential.id,
                project_id=project.id,
                for_update=for_update,
            )
            if grant is None:
                raise AdmissionRejectedError
        preference = await self._repository.get_preference(user_id, for_update=for_update)
        if preference is None or not preference.enabled or preference.streaming_enabled:
            raise AdmissionRejectedError
        project_policy = None
        if project is not None:
            project_policy = await self._repository.get_project_policy(
                project.id, for_update=for_update
            )
            if (
                project_policy is None
                or not project_policy.enabled
                or project_policy.currency != FIXTURE_CURRENCY
            ):
                raise AdmissionRejectedError
        user_budget = await self._repository.get_user_budget_policy(
            user_id, currency=FIXTURE_CURRENCY, for_update=for_update
        )
        project_budget = (
            None
            if project is None
            else await self._repository.get_project_budget_policy(
                project.id, currency=FIXTURE_CURRENCY, for_update=for_update
            )
        )
        if (
            user_budget is None
            or not user_budget.enabled
            or user_budget.currency != FIXTURE_CURRENCY
            or user_budget.allow_unknown_cost
            or (
                project is not None
                and (
                    project_budget is None
                    or not project_budget.enabled
                    or project_budget.currency != FIXTURE_CURRENCY
                    or project_budget.allow_unknown_cost
                )
            )
        ):
            raise AdmissionRejectedError
        now = datetime.now(UTC)
        user_counter = await self._repository.get_user_counter(
            user_id, now, currency=FIXTURE_CURRENCY, for_update=for_update
        )
        project_counter = (
            None
            if project is None
            else await self._repository.get_project_counter(
                project.id, now, currency=FIXTURE_CURRENCY, for_update=for_update
            )
        )
        if user_counter is None or (project is not None and project_counter is None):
            raise AdmissionRejectedError
        if int((user_counter.window_end - user_counter.window_start).total_seconds()) != (
            user_budget.window_seconds
        ):
            raise AdmissionRejectedError
        if (
            project_budget is not None
            and project_counter is not None
            and int((project_counter.window_end - project_counter.window_start).total_seconds())
            != project_budget.window_seconds
        ):
            raise AdmissionRejectedError
        provider = await self._repository.get_provider(FIXTURE_PROVIDER_KEY)
        model = await self._repository.get_model(payload.model_definition_id)
        if (
            provider is None
            or provider.id != payload.provider_definition_id
            or provider.provider_key != FIXTURE_PROVIDER_KEY
            or provider.adapter_type != "fixture_local"
            or not provider.enabled
            or provider.status != "active"
            or model is None
            or model.provider_definition_id != provider.id
            or model.provider_key != provider.provider_key
            or model.status != "active"
            or (
                credential is not None
                and (
                    credential.provider_definition_id != provider.id
                    or credential.provider_key != provider.provider_key
                )
            )
        ):
            raise AdmissionRejectedError
        capability_keys = sorted(set(payload.requested_capabilities))
        if not capability_keys or len(capability_keys) != len(payload.requested_capabilities):
            raise AdmissionRejectedError
        model_capabilities = set(await self._repository.model_capability_keys(model.id))
        if not set(capability_keys).issubset(model_capabilities):
            raise AdmissionRejectedError
        if project_policy is not None:
            providers, models, capabilities, credentials = await self._repository.policy_allowlists(
                project_policy.id
            )
            requested_capability_ids = set(
                await self._repository.capability_ids_for_keys(capability_keys)
            )
            if (
                provider.id not in providers
                or model.id not in models
                or credential is None
                or credential.id not in credentials
                or len(requested_capability_ids) != len(capability_keys)
                or not requested_capability_ids.issubset(set(capabilities))
                or project_policy.allow_fallback
                or project_policy.allow_manual_model_id
                or project_policy.allow_unknown_cost
            ):
                raise AdmissionRejectedError
        estimate = _fixture_estimate(payload.payload)
        per_invocation_limits = [user_budget.per_invocation_limit_minor_units]
        if project_budget is not None:
            per_invocation_limits.append(project_budget.per_invocation_limit_minor_units)
        if project_policy is not None:
            per_invocation_limits.append(project_policy.per_invocation_limit_minor_units)
        if estimate > min(per_invocation_limits):
            raise AdmissionRejectedError
        user_total_after_reservation = (
            user_counter.committed_minor_units + user_counter.reserved_minor_units + estimate
        )
        if user_total_after_reservation > user_budget.cumulative_limit_minor_units:
            raise AdmissionRejectedError
        if project_counter is not None and project_budget is not None:
            project_total_after_reservation = (
                project_counter.committed_minor_units
                + project_counter.reserved_minor_units
                + estimate
            )
            if project_total_after_reservation > project_budget.cumulative_limit_minor_units:
                raise AdmissionRejectedError
        if (
            for_update
            and user_counter.limit_minor_units != user_budget.cumulative_limit_minor_units
        ):
            user_counter.limit_minor_units = user_budget.cumulative_limit_minor_units
            user_counter.revision += 1
        if (
            for_update
            and project_counter is not None
            and project_budget is not None
            and project_counter.limit_minor_units != project_budget.cumulative_limit_minor_units
        ):
            project_counter.limit_minor_units = project_budget.cumulative_limit_minor_units
            project_counter.revision += 1
        return AdmissionContext(
            provider=provider,
            model=model,
            credential=credential,
            temporary_secret=temporary_secret,
            user_counter=user_counter,
            project_counter=project_counter,
            estimate_minor_units=estimate,
            capability_keys=capability_keys,
        )

    async def live_saved_selection_blockers(
        self,
        *,
        user_id: uuid.UUID,
        project_id: uuid.UUID,
        provider_definition_id: uuid.UUID,
        model_definition_id: uuid.UUID,
        credential_id: uuid.UUID,
        required_capability_keys: list[str],
        estimate_minor_units: int,
    ) -> list[str]:
        """Evaluate a saved live selection without reading a credential or dispatching.

        Phase 3B keeps live execution source-disabled.  This read-only admission mirror
        makes every other prerequisite explicit so the UI cannot imply that a missing
        Grant, allowlist, or USD budget would become executable by flipping that gate.
        """

        blockers: list[str] = []
        capability_keys = sorted(set(required_capability_keys))
        now = datetime.now(UTC)
        async with self._session.begin():
            active_user = await self._repository.lock_active_user(user_id)
            provider = await self._repository.get_provider_by_id(provider_definition_id)
            model = await self._repository.get_model(model_definition_id)
            credential = await self._repository.get_owned_credential(
                credential_id=credential_id,
                owner_user_id=user_id,
            )
            grant = await self._repository.get_active_grant(
                credential_id=credential_id,
                project_id=project_id,
            )
            preference = await self._repository.get_preference(user_id)
            policy = await self._repository.get_project_policy(project_id)
            user_budget = await self._repository.get_user_budget_policy(
                user_id,
                currency=USD_CURRENCY,
            )
            project_budget = await self._repository.get_project_budget_policy(
                project_id,
                currency=USD_CURRENCY,
            )
            user_counter = await self._repository.get_user_counter(
                user_id,
                now,
                currency=USD_CURRENCY,
            )
            project_counter = await self._repository.get_project_counter(
                project_id,
                now,
                currency=USD_CURRENCY,
            )
            capability_ids = set(await self._repository.capability_ids_for_keys(capability_keys))
            model_capabilities = (
                set()
                if model is None
                else set(await self._repository.model_capability_keys(model.id))
            )
            providers: list[uuid.UUID] = []
            models: list[uuid.UUID] = []
            capabilities: list[uuid.UUID] = []
            credentials: list[uuid.UUID] = []
            if policy is not None:
                (
                    providers,
                    models,
                    capabilities,
                    credentials,
                ) = await self._repository.policy_allowlists(policy.id)

        if active_user is None:
            blockers.append("user_inactive")
        if (
            provider is None
            or provider.provider_key != OPENAI_PROVIDER_KEY
            or _configuration_currency(provider) != USD_CURRENCY
        ):
            blockers.append("openai_provider_contract_invalid")
        if (
            provider is None
            or model is None
            or model.id != model_definition_id
            or not _model_matches_provider(model, provider)
        ):
            blockers.append("openai_model_contract_invalid")
        if (
            not capability_keys
            or len(capability_ids) != len(capability_keys)
            or not set(capability_keys).issubset(model_capabilities)
        ):
            blockers.append("model_capabilities_missing")
        if credential is None or credential.status != "active":
            blockers.append("credential_not_owned_or_inactive")
        elif (
            provider is None
            or credential.provider_definition_id != provider.id
            or credential.provider_key != provider.provider_key
        ):
            blockers.append("credential_provider_mismatch")
        elif (
            credential.last_validation_status != "provider_valid"
            or credential.last_successful_validation_at is None
        ):
            blockers.append("credential_live_validation_required")
        if grant is None:
            blockers.append("credential_grant_missing")
        if preference is None or not preference.enabled or preference.streaming_enabled:
            blockers.append("user_preference_not_enabled")
        if policy is None or not policy.enabled:
            blockers.append("project_policy_not_configured")
        else:
            if policy.currency != USD_CURRENCY:
                blockers.append("project_policy_currency_mismatch")
            if (
                policy.allow_unknown_cost
                or policy.allow_manual_model_id
                or policy.allow_fallback
                or not policy.require_paid_call_confirmation
            ):
                blockers.append("project_policy_controls_not_strict")
            if provider_definition_id not in providers:
                blockers.append("provider_not_allowlisted")
            if model_definition_id not in models:
                blockers.append("model_not_allowlisted")
            if credential_id not in credentials:
                blockers.append("credential_not_allowlisted")
            if not capability_ids.issubset(set(capabilities)):
                blockers.append("capability_not_allowlisted")
        if (
            user_budget is None
            or not user_budget.enabled
            or user_budget.currency != USD_CURRENCY
            or user_budget.allow_unknown_cost
        ):
            blockers.append("user_budget_not_configured")
        if (
            project_budget is None
            or not project_budget.enabled
            or project_budget.currency != USD_CURRENCY
            or project_budget.allow_unknown_cost
        ):
            blockers.append("project_budget_not_configured")
        if user_counter is None or project_counter is None:
            blockers.append("budget_window_not_active")
        if (
            user_budget is not None
            and project_budget is not None
            and policy is not None
            and estimate_minor_units
            > min(
                user_budget.per_invocation_limit_minor_units,
                project_budget.per_invocation_limit_minor_units,
                policy.per_invocation_limit_minor_units,
            )
        ):
            blockers.append("per_invocation_budget_exceeded")
        if user_budget is not None and user_counter is not None:
            if (
                int((user_counter.window_end - user_counter.window_start).total_seconds())
                != user_budget.window_seconds
                or user_counter.limit_minor_units != user_budget.cumulative_limit_minor_units
            ):
                blockers.append("user_budget_window_mismatch")
            if (
                user_counter.committed_minor_units
                + user_counter.reserved_minor_units
                + estimate_minor_units
                > user_budget.cumulative_limit_minor_units
            ):
                blockers.append("user_cumulative_budget_exceeded")
        if project_budget is not None and project_counter is not None:
            if (
                int((project_counter.window_end - project_counter.window_start).total_seconds())
                != project_budget.window_seconds
                or project_counter.limit_minor_units != project_budget.cumulative_limit_minor_units
            ):
                blockers.append("project_budget_window_mismatch")
            if (
                project_counter.committed_minor_units
                + project_counter.reserved_minor_units
                + estimate_minor_units
                > project_budget.cumulative_limit_minor_units
            ):
                blockers.append("project_cumulative_budget_exceeded")
        return list(dict.fromkeys(blockers))

    @staticmethod
    def _reject_public_paint_plan_invocation(payload: InvocationPreviewRequest) -> None:
        if (
            payload.invocation_family == "paint_plan_generation"
            or payload.payload.paint_plan_input is not None
        ):
            raise AdmissionRejectedError

    @staticmethod
    def _require_internal_paint_plan_invocation(payload: InvocationPreviewRequest) -> None:
        if (
            payload.invocation_family != "paint_plan_generation"
            or payload.payload.paint_plan_input is None
            or payload.payload.prompt_label != "paint-plan.v1"
        ):
            raise AdmissionRejectedError

    async def preview_invocation(
        self, *, payload: InvocationPreviewRequest, principal: PrincipalContext
    ) -> InvocationPreviewRead:
        self._reject_public_paint_plan_invocation(payload)
        return await self._preview_invocation(payload=payload, principal=principal)

    async def preview_paint_plan_invocation(
        self, *, payload: InvocationPreviewRequest, principal: PrincipalContext
    ) -> InvocationPreviewRead:
        self._require_internal_paint_plan_invocation(payload)
        return await self._preview_invocation(payload=payload, principal=principal)

    async def _preview_invocation(
        self, *, payload: InvocationPreviewRequest, principal: PrincipalContext
    ) -> InvocationPreviewRead:
        async with self._session.begin():
            admission = await self._resolve_admission(
                payload=payload, principal=principal, for_update=False
            )
            project_policy = (
                None
                if payload.project_id is None
                else await self._repository.get_project_policy(payload.project_id)
            )
            return InvocationPreviewRead(
                admissible=True,
                provider_key=admission.provider.provider_key,
                model_id=admission.model.model_id,
                credential_alias=(
                    admission.credential.alias
                    if admission.credential is not None
                    else "Temporary fixture credential"
                ),
                required_grant=payload.project_id is not None,
                active_grant=payload.project_id is None or True,
                estimated_cost_minor_units=admission.estimate_minor_units,
                currency=FIXTURE_CURRENCY,
                fixture=True,
                local_only=True,
                fallback_enabled=False,
                confirmation_required=(
                    project_policy.require_paid_call_confirmation
                    if project_policy is not None
                    else True
                ),
            )

    def _invocation_event(
        self,
        *,
        invocation_id: uuid.UUID,
        attempt_id: uuid.UUID | None,
        event_type: str,
        from_status: str | None,
        to_status: str,
        safe_metadata: Mapping[str, object] | None = None,
    ) -> None:
        self._repository.add(
            AIInvocationEvent(
                id=uuid.uuid4(),
                invocation_id=invocation_id,
                attempt_id=attempt_id,
                event_type=event_type,
                from_status=from_status,
                to_status=to_status,
                safe_metadata=dict(safe_metadata or {}),
                created_at=datetime.now(UTC),
            )
        )

    async def _invocation_read(
        self, invocation: InvocationRequest, *, replayed: bool = False
    ) -> InvocationRead:
        attempts = await self._repository.list_attempts(invocation.id)
        return InvocationRead(
            id=invocation.id,
            product_space=invocation.product_space,
            project_id=invocation.project_id,
            invocation_family=invocation.invocation_family,  # type: ignore[arg-type]
            canonicalization_version=CANONICALIZATION_VERSION,
            payload_hash=invocation.canonical_request_payload_hash,
            status=invocation.status,  # type: ignore[arg-type]
            final_attempt_id=invocation.final_attempt_id,
            final_error_category=invocation.final_error_category,
            output=invocation.output_reference,
            currency=FIXTURE_CURRENCY,
            created_at=invocation.created_at,
            updated_at=invocation.updated_at,
            replayed=replayed,
            attempts=[
                AttemptRead(
                    id=attempt.id,
                    attempt_number=attempt.attempt_number,
                    provider_key=attempt.provider_key,
                    model_id=attempt.model_id,
                    status=attempt.status,
                    currency=FIXTURE_CURRENCY,
                    dispatched_at=attempt.dispatched_at,
                    terminal_at=attempt.terminal_at,
                    final_error_category=attempt.final_error_category,
                    provider_request_id_status=attempt.provider_request_id_status,  # type: ignore[arg-type]
                    provider_request_id=attempt.provider_request_id,
                    safe_provider_metadata=attempt.safe_provider_metadata,
                )
                for attempt in attempts
            ],
        )

    async def _create_pending_invocation(
        self,
        *,
        payload: InvocationCreateRequest,
        principal: PrincipalContext,
        idempotency_key: uuid.UUID,
        request_id: uuid.UUID,
    ) -> tuple[InvocationRequest, bool]:
        user_id = _user_id(principal)
        identity = payload.model_dump(mode="json", exclude={"temporary_credential"})
        if payload.temporary_credential is not None:
            identity["temporary_credential_fingerprint"] = self._cipher.fingerprint(
                payload.temporary_credential.get_secret_value().encode("utf-8")
            )
        _, payload_hash = canonicalize_and_hash(identity)
        project_scope_id = payload.project_id or PROJECTLESS_SCOPE_ID
        async with self._session.begin():
            lock_scope = (
                f"invocation:{user_id}:paintpilot:{project_scope_id}:"
                f"{payload.invocation_family}:{idempotency_key}"
            )
            await self._session.execute(
                text("SELECT pg_advisory_xact_lock(hashtextextended(:scope, 0))"),
                {"scope": lock_scope},
            )
            existing = (
                await self._session.execute(
                    select(InvocationRequest).where(
                        InvocationRequest.requesting_user_id == user_id,
                        InvocationRequest.product_space == "paintpilot",
                        InvocationRequest.project_scope_id == project_scope_id,
                        InvocationRequest.invocation_family == payload.invocation_family,
                        InvocationRequest.idempotency_key == idempotency_key,
                    )
                )
            ).scalar_one_or_none()
            if existing is not None:
                if existing.canonical_request_payload_hash != payload_hash:
                    raise AIIdempotencyConflictError
                return existing, True
            await self._preauthorize_invocation_references(
                payload=payload,
                principal=principal,
            )
            now = datetime.now(UTC)
            safe_payload: dict[str, object] = {
                "fixture": True,
                "local_only": True,
                "scenario": payload.payload.scenario,
                "artifacts": [artifact.model_dump(mode="json") for artifact in payload.artifacts],
                "temporary_credential": payload.temporary_credential is not None,
            }
            paint_plan_source = payload.payload.paint_plan_input
            if paint_plan_source is not None:
                safe_payload["paint_plan_provenance"] = {
                    "image_set_fingerprint": paint_plan_source.image_set_fingerprint,
                    "image_assets": [
                        image.model_dump(mode="json") for image in paint_plan_source.image_assets
                    ],
                    "readiness_review_id": str(paint_plan_source.readiness_review_id),
                    "readiness_review_version": paint_plan_source.readiness_review_version,
                    "region_set_id": str(paint_plan_source.region_set.id),
                    "region_set_version": paint_plan_source.region_set.version,
                    "region_geometry_fingerprint": (
                        paint_plan_source.region_set.geometry_fingerprint
                    ),
                    "prompt_template_id": str(paint_plan_source.prompt_template_id),
                    "prompt_template_key": paint_plan_source.prompt_template_key,
                    "prompt_template_version": paint_plan_source.prompt_template_version,
                    "prompt_content_hash": paint_plan_source.prompt_content_hash,
                    "generation_locale": paint_plan_source.generation_locale,
                    "response_schema_version": paint_plan_source.response_schema_version,
                }
                safe_payload["paint_plan_contract"] = {
                    "paint_regions": [
                        {
                            "region_id": str(region.id),
                            "stable_region_key": str(region.stable_region_key),
                            "region_label": region.label,
                        }
                        for region in paint_plan_source.region_set.regions
                        if region.kind == "paint"
                    ],
                    "excluded_region_ids": [
                        str(region.id)
                        for region in paint_plan_source.region_set.regions
                        if region.kind == "exclude"
                    ],
                }
            invocation = InvocationRequest(
                id=uuid.uuid4(),
                requesting_user_id=user_id,
                product_space="paintpilot",
                project_id=payload.project_id,
                project_scope_id=project_scope_id,
                invocation_family=payload.invocation_family,
                idempotency_key=idempotency_key,
                canonicalization_version=CANONICALIZATION_VERSION,
                canonical_request_payload_hash=payload_hash,
                requested_capabilities=sorted(set(payload.requested_capabilities)),
                requested_provider_definition_id=payload.provider_definition_id,
                requested_model_definition_id=payload.model_definition_id,
                requested_credential_id=payload.credential_id,
                request_id=request_id,
                max_attempts=payload.max_attempts,
                total_elapsed_time_limit_ms=payload.total_elapsed_time_limit_ms,
                confirmation_snapshot={"confirm_fixture_use": True},
                budget_snapshot={"currency": FIXTURE_CURRENCY},
                safe_payload=safe_payload,
                status="pending",
                final_attempt_id=None,
                started_at=None,
                terminal_at=None,
                cancellation_requested_at=None,
                final_error_category=None,
                output_reference=None,
                revision=1,
                created_at=now,
                updated_at=now,
            )
            self._repository.add(invocation)
            await self._repository.flush()
            self._invocation_event(
                invocation_id=invocation.id,
                attempt_id=None,
                event_type="request_created",
                from_status=None,
                to_status="pending",
                safe_metadata={"fixture": True},
            )
            self._audit(
                user_id=user_id,
                request_id=request_id,
                action="invocation_create",
                outcome="pending",
                project_id=payload.project_id,
                credential_id=payload.credential_id,
                invocation_id=invocation.id,
                provider_id=payload.provider_definition_id,
                model_id=payload.model_definition_id,
                safe_metadata={"payload_hash": payload_hash, "fixture": True},
            )
            return invocation, False

    async def _admit_attempt(
        self,
        *,
        invocation_id: uuid.UUID,
        payload: InvocationCreateRequest,
        principal: PrincipalContext,
        attempt_number: int,
        retry_of_attempt_id: uuid.UUID | None,
    ) -> tuple[uuid.UUID, uuid.UUID, SecretBytes, AdmissionContext]:
        async with self._session.begin():
            admission = await self._resolve_admission(
                payload=payload, principal=principal, for_update=True
            )
            invocation = await self._repository.get_invocation(invocation_id, for_update=True)
            if (
                invocation is None
                or invocation.requesting_user_id != _user_id(principal)
                or invocation.status not in {"pending", "running"}
                or invocation.cancellation_requested_at is not None
                or attempt_number > invocation.max_attempts
            ):
                raise AIConflictError
            now = datetime.now(UTC)
            if now - invocation.created_at > timedelta(
                milliseconds=invocation.total_elapsed_time_limit_ms
            ):
                invocation.status = "failed"
                invocation.final_error_category = "deadline_exceeded"
                invocation.terminal_at = now
                invocation.updated_at = now
                invocation.revision += 1
                raise AdmissionRejectedError
            attempt = InvocationAttempt(
                id=uuid.uuid4(),
                invocation_id=invocation.id,
                attempt_number=attempt_number,
                provider_definition_id=admission.provider.id,
                model_definition_id=admission.model.id,
                provider_key=admission.provider.provider_key,
                model_id=admission.model.model_id,
                adapter_version=self._adapter.adapter_version,
                capability_snapshot=admission.capability_keys,
                credential_id=(
                    admission.credential.id if admission.credential is not None else None
                ),
                credential_encryption_version_snapshot=(
                    admission.credential.encryption_version
                    if admission.credential is not None
                    else None
                ),
                temporary_credential=admission.credential is None,
                retry_of_attempt_id=retry_of_attempt_id,
                fallback_decision="disabled",
                currency=FIXTURE_CURRENCY,
                status="admitted",
                dispatched_at=None,
                terminal_at=None,
                cancellation_requested_at=None,
                final_error_category=None,
                output_reference=None,
                safe_provider_metadata={"fixture": True, "local_only": True},
                latency_ms=None,
                revision=1,
                created_at=now,
            )
            reservation = BudgetReservation(
                id=uuid.uuid4(),
                invocation_id=invocation.id,
                attempt_id=attempt.id,
                user_counter_id=admission.user_counter.id,
                project_counter_id=(
                    admission.project_counter.id if admission.project_counter is not None else None
                ),
                currency=FIXTURE_CURRENCY,
                reserved_amount=admission.estimate_minor_units,
                state="reserved",
                created_at=now,
                admission_expires_at=now + RESERVATION_EXPIRY,
                dispatch_committed_at=None,
                settled_at=None,
                released_at=None,
                revision=1,
            )
            admission.user_counter.reserved_minor_units += admission.estimate_minor_units
            admission.user_counter.revision += 1
            if admission.project_counter is not None:
                admission.project_counter.reserved_minor_units += admission.estimate_minor_units
                admission.project_counter.revision += 1
            previous = invocation.status
            invocation.status = "admitted"
            invocation.started_at = invocation.started_at or now
            invocation.updated_at = now
            invocation.revision += 1
            self._repository.add(attempt)
            await self._repository.flush()
            self._repository.add(reservation)
            await self._repository.flush()
            self._invocation_event(
                invocation_id=invocation.id,
                attempt_id=attempt.id,
                event_type="attempt_admitted",
                from_status=previous,
                to_status="admitted",
                safe_metadata={
                    "attempt_number": attempt_number,
                    "reserved_minor_units": admission.estimate_minor_units,
                    "currency": FIXTURE_CURRENCY,
                },
            )
            if admission.credential is None:
                if admission.temporary_secret is None:
                    raise AIConflictError
                secret = admission.temporary_secret
            else:
                secret = self._cipher.decrypt(
                    _encrypted_payload(admission.credential),
                    aad=CredentialAAD(
                        credential_id=admission.credential.id,
                        owner_user_id=admission.credential.owner_user_id,
                        provider_key=admission.credential.provider_key,
                        encryption_version=admission.credential.encryption_version or "",
                    ),
                )
            await self._repository.flush()
            return attempt.id, reservation.id, secret, admission

    async def _commit_dispatch(
        self,
        *,
        invocation_id: uuid.UUID,
        attempt_id: uuid.UUID,
        reservation_id: uuid.UUID,
    ) -> bool:
        async with self._session.begin():
            invocation = await self._repository.get_invocation(invocation_id, for_update=True)
            attempt = await self._repository.get_attempt(attempt_id, for_update=True)
            reservation = (
                await self._session.execute(
                    select(BudgetReservation)
                    .where(BudgetReservation.id == reservation_id)
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if invocation is None or attempt is None or reservation is None:
                raise AIConflictError
            if (
                invocation.status != "admitted"
                or invocation.cancellation_requested_at is not None
                or attempt.status != "admitted"
                or reservation.state != "reserved"
                or reservation.admission_expires_at <= datetime.now(UTC)
            ):
                return False
            now = datetime.now(UTC)
            invocation.status = "running"
            invocation.updated_at = now
            invocation.revision += 1
            attempt.status = "running"
            attempt.dispatched_at = now
            attempt.revision += 1
            reservation.state = "dispatch_committed"
            reservation.dispatch_committed_at = now
            reservation.revision += 1
            self._invocation_event(
                invocation_id=invocation.id,
                attempt_id=attempt.id,
                event_type="dispatch_committed",
                from_status="admitted",
                to_status="running",
                safe_metadata={"fixture": True, "local_only": True},
            )
            return True

    async def _terminalize_attempt(
        self,
        *,
        invocation_id: uuid.UUID,
        attempt_id: uuid.UUID,
        reservation_id: uuid.UUID,
        principal: PrincipalContext,
        request_id: uuid.UUID,
        result: object | None,
        error: FixtureProviderError | None,
        can_retry: bool,
    ) -> bool:
        user_id = _user_id(principal)
        async with self._session.begin():
            reservation_snapshot = await self._session.get(BudgetReservation, reservation_id)
            if reservation_snapshot is None:
                raise AIConflictError
            user_counter = await self._repository.get_user_counter_by_id(
                reservation_snapshot.user_counter_id, for_update=True
            )
            project_counter = (
                None
                if reservation_snapshot.project_counter_id is None
                else await self._repository.get_project_counter_by_id(
                    reservation_snapshot.project_counter_id, for_update=True
                )
            )
            invocation = await self._repository.get_invocation(invocation_id, for_update=True)
            attempt = await self._repository.get_attempt(attempt_id, for_update=True)
            reservation = (
                await self._session.execute(
                    select(BudgetReservation)
                    .where(BudgetReservation.id == reservation_id)
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if (
                invocation is None
                or attempt is None
                or reservation is None
                or user_counter is None
                or reservation.state != "dispatch_committed"
                or attempt.status != "running"
            ):
                raise AIConflictError
            now = datetime.now(UTC)
            reserved = reservation.reserved_amount
            if (
                invocation.cancellation_requested_at is not None
                or attempt.cancellation_requested_at is not None
            ):
                from creativedeploy_api.ai.fixture_provider import FixtureInvocationResult

                late_outcome = error.category if error is not None else "succeeded"
                if isinstance(result, FixtureInvocationResult):
                    actual = result.cost_minor_units
                    user_counter.reserved_minor_units -= reserved
                    user_counter.committed_minor_units += actual
                    user_counter.revision += 1
                    if project_counter is not None:
                        project_counter.reserved_minor_units -= reserved
                        project_counter.committed_minor_units += actual
                        project_counter.revision += 1
                    reservation.state = "settled"
                    reservation.settled_at = now
                    reservation.revision += 1
                    self._repository.add_all(
                        [
                            AIUsageLedger(
                                id=uuid.uuid4(),
                                invocation_id=invocation.id,
                                attempt_id=attempt.id,
                                provider_definition_id=attempt.provider_definition_id,
                                model_definition_id=attempt.model_definition_id,
                                source="late_fixture_reconciliation",
                                canonical_sequence=1,
                                input_units=result.input_units,
                                output_units=result.output_units,
                                safe_metadata={"fixture": True, "late_after_cancel": True},
                                created_at=now,
                            ),
                            AICostLedger(
                                id=uuid.uuid4(),
                                invocation_id=invocation.id,
                                attempt_id=attempt.id,
                                provider_definition_id=attempt.provider_definition_id,
                                model_definition_id=attempt.model_definition_id,
                                source="late_fixture_reconciliation",
                                canonical_sequence=1,
                                amount_minor_units=actual,
                                currency=FIXTURE_CURRENCY,
                                created_at=now,
                            ),
                        ]
                    )
                else:
                    reservation.state = "reconciliation_required"
                    reservation.revision += 1
                attempt.status = "cancelled"
                attempt.output_reference = None
                attempt.final_error_category = "cancelled"
                attempt.terminal_at = now
                attempt.revision += 1
                invocation.status = "cancelled"
                invocation.final_attempt_id = None
                invocation.output_reference = None
                invocation.final_error_category = "cancelled"
                invocation.terminal_at = now
                invocation.updated_at = now
                invocation.revision += 1
                self._invocation_event(
                    invocation_id=invocation.id,
                    attempt_id=attempt.id,
                    event_type="late_result_received",
                    from_status="running",
                    to_status="running",
                    safe_metadata={"provider_outcome": late_outcome, "ignored_after_cancel": True},
                )
                self._invocation_event(
                    invocation_id=invocation.id,
                    attempt_id=attempt.id,
                    event_type="attempt_cancelled",
                    from_status="running",
                    to_status="cancelled",
                    safe_metadata={"cancel_won": True},
                )
                self._audit(
                    user_id=user_id,
                    request_id=request_id,
                    action="fixture_invocation_attempt",
                    outcome="cancelled",
                    project_id=invocation.project_id,
                    credential_id=attempt.credential_id,
                    invocation_id=invocation.id,
                    attempt_id=attempt.id,
                    provider_id=attempt.provider_definition_id,
                    model_id=attempt.model_definition_id,
                    safe_metadata={"fixture": True, "cancel_won": True},
                )
                return False
            from creativedeploy_api.ai.fixture_provider import FixtureInvocationResult

            fixture_result: FixtureInvocationResult | None = None
            validated_output: dict[str, object] | None = None
            if error is None:
                if not isinstance(result, FixtureInvocationResult):
                    raise AIConflictError
                fixture_result = result
                validated_output = result.output
                if invocation.invocation_family == "paint_plan_generation":
                    try:
                        validated_output = _validated_paint_plan_output(
                            result.output,
                            safe_payload=invocation.safe_payload,
                        )
                    except (TypeError, ValueError, ValidationError):
                        error = FixtureProviderError("schema_invalid")
                        can_retry = False
            if error is None:
                assert fixture_result is not None
                assert validated_output is not None
                actual = fixture_result.cost_minor_units
                user_counter.reserved_minor_units -= reserved
                user_counter.committed_minor_units += actual
                user_counter.revision += 1
                if project_counter is not None:
                    project_counter.reserved_minor_units -= reserved
                    project_counter.committed_minor_units += actual
                    project_counter.revision += 1
                reservation.state = "settled"
                reservation.settled_at = now
                reservation.revision += 1
                attempt.status = "succeeded"
                attempt.output_reference = validated_output
                attempt.safe_provider_metadata = {
                    "fixture": True,
                    "local_only": True,
                    "input_units": fixture_result.input_units,
                    "output_units": fixture_result.output_units,
                }
                attempt.terminal_at = now
                attempt.revision += 1
                invocation.status = "succeeded"
                invocation.final_attempt_id = attempt.id
                invocation.output_reference = validated_output
                invocation.final_error_category = None
                invocation.terminal_at = now
                invocation.updated_at = now
                invocation.revision += 1
                self._repository.add_all(
                    [
                        AIUsageLedger(
                            id=uuid.uuid4(),
                            invocation_id=invocation.id,
                            attempt_id=attempt.id,
                            provider_definition_id=attempt.provider_definition_id,
                            model_definition_id=attempt.model_definition_id,
                            source="fixture_adapter",
                            canonical_sequence=1,
                            input_units=fixture_result.input_units,
                            output_units=fixture_result.output_units,
                            safe_metadata={"fixture": True},
                            created_at=now,
                        ),
                        AICostLedger(
                            id=uuid.uuid4(),
                            invocation_id=invocation.id,
                            attempt_id=attempt.id,
                            provider_definition_id=attempt.provider_definition_id,
                            model_definition_id=attempt.model_definition_id,
                            source="fixture_adapter",
                            canonical_sequence=1,
                            amount_minor_units=actual,
                            currency=FIXTURE_CURRENCY,
                            created_at=now,
                        ),
                    ]
                )
                self._invocation_event(
                    invocation_id=invocation.id,
                    attempt_id=attempt.id,
                    event_type="attempt_succeeded",
                    from_status="running",
                    to_status="succeeded",
                    safe_metadata={
                        "actual_minor_units": actual,
                        "currency": FIXTURE_CURRENCY,
                    },
                )
                self._audit(
                    user_id=user_id,
                    request_id=request_id,
                    action="fixture_invocation_attempt",
                    outcome="succeeded",
                    project_id=invocation.project_id,
                    credential_id=attempt.credential_id,
                    invocation_id=invocation.id,
                    attempt_id=attempt.id,
                    provider_id=attempt.provider_definition_id,
                    model_id=attempt.model_definition_id,
                    safe_metadata={"fixture": True, "cost_minor_units": actual},
                )
                return False
            category = error.category
            if category == "outcome_unknown":
                reservation.state = "reconciliation_required"
                reservation.revision += 1
                attempt.status = "outcome_unknown"
                invocation.status = "outcome_unknown"
            elif fixture_result is not None:
                actual = fixture_result.cost_minor_units
                user_counter.reserved_minor_units -= reserved
                user_counter.committed_minor_units += actual
                user_counter.revision += 1
                if project_counter is not None:
                    project_counter.reserved_minor_units -= reserved
                    project_counter.committed_minor_units += actual
                    project_counter.revision += 1
                reservation.state = "settled"
                reservation.settled_at = now
                reservation.revision += 1
                self._repository.add_all(
                    [
                        AIUsageLedger(
                            id=uuid.uuid4(),
                            invocation_id=invocation.id,
                            attempt_id=attempt.id,
                            provider_definition_id=attempt.provider_definition_id,
                            model_definition_id=attempt.model_definition_id,
                            source="fixture_adapter_invalid_output",
                            canonical_sequence=1,
                            input_units=fixture_result.input_units,
                            output_units=fixture_result.output_units,
                            safe_metadata={
                                "fixture": True,
                                "output_persisted": False,
                            },
                            created_at=now,
                        ),
                        AICostLedger(
                            id=uuid.uuid4(),
                            invocation_id=invocation.id,
                            attempt_id=attempt.id,
                            provider_definition_id=attempt.provider_definition_id,
                            model_definition_id=attempt.model_definition_id,
                            source="fixture_adapter_invalid_output",
                            canonical_sequence=1,
                            amount_minor_units=actual,
                            currency=FIXTURE_CURRENCY,
                            created_at=now,
                        ),
                    ]
                )
                attempt.status = "failed"
                invocation.status = "failed"
            else:
                user_counter.reserved_minor_units -= reserved
                user_counter.revision += 1
                if project_counter is not None:
                    project_counter.reserved_minor_units -= reserved
                    project_counter.revision += 1
                reservation.state = "released"
                reservation.released_at = now
                reservation.revision += 1
                attempt.status = "failed"
                invocation.status = "running" if can_retry else "failed"
            attempt.output_reference = None
            attempt.final_error_category = category
            attempt.terminal_at = now
            attempt.revision += 1
            invocation.final_error_category = category
            invocation.output_reference = None
            invocation.final_attempt_id = None
            invocation.terminal_at = None if can_retry else now
            invocation.updated_at = now
            invocation.revision += 1
            self._invocation_event(
                invocation_id=invocation.id,
                attempt_id=attempt.id,
                event_type=(
                    "reconciliation_required" if category == "outcome_unknown" else "attempt_failed"
                ),
                from_status="running",
                to_status=invocation.status,
                safe_metadata={"error_category": category, "retry": can_retry},
            )
            self._audit(
                user_id=user_id,
                request_id=request_id,
                action="fixture_invocation_attempt",
                outcome=invocation.status,
                project_id=invocation.project_id,
                credential_id=attempt.credential_id,
                invocation_id=invocation.id,
                attempt_id=attempt.id,
                provider_id=attempt.provider_definition_id,
                model_id=attempt.model_definition_id,
                safe_metadata={"fixture": True, "error_category": category},
            )
            return can_retry

    async def create_invocation(
        self,
        *,
        payload: InvocationCreateRequest,
        principal: PrincipalContext,
        idempotency_key: uuid.UUID,
        request_id: uuid.UUID,
    ) -> InvocationRead:
        self._reject_public_paint_plan_invocation(payload)
        return await self._create_invocation(
            payload=payload,
            principal=principal,
            idempotency_key=idempotency_key,
            request_id=request_id,
        )

    async def create_paint_plan_invocation(
        self,
        *,
        payload: InvocationCreateRequest,
        principal: PrincipalContext,
        idempotency_key: uuid.UUID,
        request_id: uuid.UUID,
    ) -> InvocationRead:
        self._require_internal_paint_plan_invocation(payload)
        return await self._create_invocation(
            payload=payload,
            principal=principal,
            idempotency_key=idempotency_key,
            request_id=request_id,
        )

    async def _create_invocation(
        self,
        *,
        payload: InvocationCreateRequest,
        principal: PrincipalContext,
        idempotency_key: uuid.UUID,
        request_id: uuid.UUID,
    ) -> InvocationRead:
        invocation, replayed = await self._create_pending_invocation(
            payload=payload,
            principal=principal,
            idempotency_key=idempotency_key,
            request_id=request_id,
        )
        if replayed or invocation.status in TERMINAL_INVOCATION_STATES:
            async with self._session.begin():
                current = await self._repository.get_invocation(invocation.id)
                if current is None:
                    raise AIResourceNotFoundError
                return await self._invocation_read(current, replayed=True)
        previous_attempt_id: uuid.UUID | None = None
        for attempt_number in range(1, payload.max_attempts + 1):
            attempt_id, reservation_id, secret, _ = await self._admit_attempt(
                invocation_id=invocation.id,
                payload=payload,
                principal=principal,
                attempt_number=attempt_number,
                retry_of_attempt_id=previous_attempt_id,
            )
            if not await self._commit_dispatch(
                invocation_id=invocation.id,
                attempt_id=attempt_id,
                reservation_id=reservation_id,
            ):
                break
            result = None
            error = None
            try:
                result = self._adapter.invoke(
                    payload.payload.model_dump(mode="json"),
                    secret,
                    scenario=payload.payload.scenario,
                )
            except FixtureProviderError as exc:
                error = exc
            retryable = (
                error is not None
                and error.category in {"provider_unavailable", "rate_limited"}
                and attempt_number < payload.max_attempts
            )
            should_retry = await self._terminalize_attempt(
                invocation_id=invocation.id,
                attempt_id=attempt_id,
                reservation_id=reservation_id,
                principal=principal,
                request_id=request_id,
                result=result,
                error=error,
                can_retry=retryable,
            )
            previous_attempt_id = attempt_id
            if not should_retry:
                break
        async with self._session.begin():
            current = await self._repository.get_invocation(invocation.id)
            if current is None:
                raise AIResourceNotFoundError
            return await self._invocation_read(current)

    async def get_invocation(
        self,
        *,
        invocation_id: uuid.UUID,
        principal: PrincipalContext,
    ) -> InvocationRead:
        user_id = _user_id(principal)
        async with self._session.begin():
            invocation = await self._repository.get_invocation(invocation_id)
            if invocation is None or invocation.requesting_user_id != user_id:
                raise AIAuthorizationError
            if invocation.project_id is not None:
                access = await self._identity_repository.resolve_project_access(
                    project_id=invocation.project_id,
                    principal_id=principal.principal_id,
                    user_id=user_id,
                )
                if access is None:
                    raise AIAuthorizationError
            return await self._invocation_read(invocation)

    async def cancel_invocation(
        self,
        *,
        invocation_id: uuid.UUID,
        principal: PrincipalContext,
        request_id: uuid.UUID,
        idempotency_key: uuid.UUID,
    ) -> InvocationRead:
        user_id = _user_id(principal)
        identity = {"invocation_id": str(invocation_id), "confirm": True}
        scope = f"invocation_cancel:{invocation_id}"
        async with self._session.begin():
            replay = await self._command_replay(
                user_id=user_id,
                scope=scope,
                idempotency_key=idempotency_key,
                identity_payload=identity,
                response_type=InvocationRead,
            )
            if replay is not None:
                return replay
            snapshot = await self._repository.get_invocation(invocation_id)
            if snapshot is None or snapshot.requesting_user_id != user_id:
                raise AIAuthorizationError
            attempts = await self._repository.list_attempts(invocation_id)
            active_attempt = next(
                (
                    item
                    for item in reversed(attempts)
                    if item.status in {"created", "admitted", "running"}
                ),
                None,
            )
            reservation_snapshot = (
                None
                if active_attempt is None
                else await self._repository.get_reservation(active_attempt.id)
            )
            if await self._repository.lock_active_user(user_id) is None:
                raise AIAuthorizationError
            if snapshot.project_id is not None:
                access = await self._identity_repository.resolve_project_access(
                    project_id=snapshot.project_id,
                    principal_id=principal.principal_id,
                    user_id=user_id,
                    for_update=True,
                )
                if access is None:
                    raise AIAuthorizationError
            user_counter = (
                None
                if reservation_snapshot is None
                else await self._repository.get_user_counter_by_id(
                    reservation_snapshot.user_counter_id, for_update=True
                )
            )
            project_counter = (
                None
                if reservation_snapshot is None or reservation_snapshot.project_counter_id is None
                else await self._repository.get_project_counter_by_id(
                    reservation_snapshot.project_counter_id, for_update=True
                )
            )
            invocation = await self._repository.get_invocation(invocation_id, for_update=True)
            if invocation is None:
                raise AIResourceNotFoundError
            if invocation.status in TERMINAL_INVOCATION_STATES:
                response = await self._invocation_read(invocation)
                self._complete_command(
                    user_id=user_id,
                    scope=scope,
                    idempotency_key=idempotency_key,
                    identity_payload=identity,
                    response=response,
                )
                return response
            now = datetime.now(UTC)
            attempt = (
                None
                if active_attempt is None
                else await self._repository.get_attempt(active_attempt.id, for_update=True)
            )
            reservation = (
                None
                if active_attempt is None
                else await self._repository.get_reservation(active_attempt.id, for_update=True)
            )
            invocation.cancellation_requested_at = now
            invocation.updated_at = now
            invocation.revision += 1
            if attempt is not None:
                attempt.cancellation_requested_at = now
                attempt.revision += 1
            if invocation.status in {"pending", "admitted"} and (
                attempt is None or attempt.status != "running"
            ):
                if (
                    reservation is not None
                    and reservation.state == "reserved"
                    and user_counter is not None
                ):
                    user_counter.reserved_minor_units -= reservation.reserved_amount
                    user_counter.revision += 1
                    if project_counter is not None:
                        project_counter.reserved_minor_units -= reservation.reserved_amount
                        project_counter.revision += 1
                    reservation.state = "released"
                    reservation.released_at = now
                    reservation.revision += 1
                if attempt is not None:
                    attempt.status = "cancelled"
                    attempt.terminal_at = now
                    attempt.revision += 1
                invocation.status = "cancelled"
                invocation.terminal_at = now
                self._invocation_event(
                    invocation_id=invocation.id,
                    attempt_id=attempt.id if attempt is not None else None,
                    event_type="cancelled_before_dispatch",
                    from_status=snapshot.status,
                    to_status="cancelled",
                )
            else:
                self._invocation_event(
                    invocation_id=invocation.id,
                    attempt_id=attempt.id if attempt is not None else None,
                    event_type="cancellation_requested_after_dispatch",
                    from_status=invocation.status,
                    to_status=invocation.status,
                    safe_metadata={"mutation_owner": "dispatch"},
                )
            self._audit(
                user_id=user_id,
                request_id=request_id,
                action="invocation_cancel",
                outcome=invocation.status,
                project_id=invocation.project_id,
                invocation_id=invocation.id,
                attempt_id=attempt.id if attempt is not None else None,
                safe_metadata={"cancellation_requested": True},
            )
            await self._repository.flush()
            response = await self._invocation_read(invocation)
            self._complete_command(
                user_id=user_id,
                scope=scope,
                idempotency_key=idempotency_key,
                identity_payload=identity,
                response=response,
            )
            return response

    async def list_audit(
        self,
        *,
        principal: PrincipalContext,
        project_id: uuid.UUID | None,
        limit: int,
        offset: int,
    ) -> UsageAuditListResponse:
        user_id = _user_id(principal)
        async with self._session.begin():
            if project_id is not None:
                access = await self._identity_repository.resolve_project_access(
                    project_id=project_id,
                    principal_id=principal.principal_id,
                    user_id=user_id,
                )
                if access is None:
                    raise AIAuthorizationError
            items, total = await self._repository.list_audit(
                user_id=user_id,
                project_id=project_id,
                limit=limit,
                offset=offset,
            )
            return UsageAuditListResponse(
                items=[
                    UsageAuditRead(
                        id=item.id,
                        created_at=item.created_at,
                        action=item.action,
                        outcome=item.outcome,
                        project_id=item.project_id,
                        credential_id=item.credential_id,
                        invocation_id=item.invocation_id,
                        provider_definition_id=item.provider_definition_id,
                        model_definition_id=item.model_definition_id,
                        safe_metadata=item.safe_metadata,
                    )
                    for item in items
                ],
                total=total,
                limit=limit,
                offset=offset,
            )

    async def recover_expired_admissions(self, *, limit: int = 100) -> int:
        """Release reservations which never reached the dispatch commit point."""
        now = datetime.now(UTC)
        expired_candidates = list(
            (
                await self._session.execute(
                    select(
                        BudgetReservation.id,
                        BudgetReservation.invocation_id,
                        BudgetReservation.attempt_id,
                        BudgetReservation.user_counter_id,
                        BudgetReservation.project_counter_id,
                        InvocationRequest.requesting_user_id,
                        InvocationRequest.project_id,
                    )
                    .join(
                        InvocationRequest,
                        InvocationRequest.id == BudgetReservation.invocation_id,
                    )
                    .where(
                        BudgetReservation.state == "reserved",
                        BudgetReservation.admission_expires_at <= now,
                    )
                    .order_by(BudgetReservation.admission_expires_at)
                    .limit(limit)
                )
            )
            .tuples()
            .all()
        )
        await self._session.rollback()
        recovered = 0
        for (
            reservation_id,
            invocation_id,
            attempt_id,
            user_counter_id,
            project_counter_id,
            requesting_user_id,
            project_id,
        ) in expired_candidates:
            async with self._session.begin():
                await self._repository.lock_user(requesting_user_id)
                if project_id is not None:
                    await self._repository.lock_project(project_id)
                user_counter = (
                    await self._session.execute(
                        select(UserBudgetCounter)
                        .where(UserBudgetCounter.id == user_counter_id)
                        .with_for_update()
                        .execution_options(populate_existing=True)
                    )
                ).scalar_one_or_none()
                project_counter = (
                    None
                    if project_counter_id is None
                    else (
                        await self._session.execute(
                            select(ProjectBudgetCounter)
                            .where(ProjectBudgetCounter.id == project_counter_id)
                            .with_for_update()
                            .execution_options(populate_existing=True)
                        )
                    ).scalar_one_or_none()
                )
                invocation = (
                    await self._session.execute(
                        select(InvocationRequest)
                        .where(InvocationRequest.id == invocation_id)
                        .with_for_update()
                        .execution_options(populate_existing=True)
                    )
                ).scalar_one_or_none()
                attempt = (
                    await self._session.execute(
                        select(InvocationAttempt)
                        .where(InvocationAttempt.id == attempt_id)
                        .with_for_update()
                        .execution_options(populate_existing=True)
                    )
                ).scalar_one_or_none()
                reservation = (
                    await self._session.execute(
                        select(BudgetReservation)
                        .where(BudgetReservation.id == reservation_id)
                        .with_for_update()
                        .execution_options(populate_existing=True)
                    )
                ).scalar_one_or_none()
                if (
                    invocation is None
                    or attempt is None
                    or reservation is None
                    or user_counter is None
                    or reservation.state != "reserved"
                    or reservation.admission_expires_at > now
                ):
                    continue
                relationships_match = (
                    invocation.id == reservation.invocation_id
                    and attempt.invocation_id == invocation.id
                    and attempt.id == reservation.attempt_id
                    and reservation.id == reservation_id
                    and user_counter.id == reservation.user_counter_id
                    and user_counter.user_id == invocation.requesting_user_id
                    and (
                        (
                            reservation.project_counter_id is None
                            and invocation.project_id is None
                            and project_counter is None
                        )
                        or (
                            reservation.project_counter_id is not None
                            and invocation.project_id is not None
                            and project_counter is not None
                            and project_counter.id == reservation.project_counter_id
                            and project_counter.project_id == invocation.project_id
                        )
                    )
                )
                if not relationships_match:
                    continue
                provider_request_id = attempt.safe_provider_metadata.get("provider_request_id")
                dispatch_evidence = (
                    reservation.dispatch_committed_at is not None
                    or attempt.dispatched_at is not None
                    or provider_request_id is not None
                    or await self._repository.attempt_has_dispatch_evidence(
                        invocation_id=invocation.id,
                        attempt_id=attempt.id,
                    )
                )
                clean_orphan = (
                    invocation.status == "admitted"
                    and attempt.status == "admitted"
                    and not dispatch_evidence
                )
                if not clean_orphan:
                    previous_status = invocation.status
                    reservation.state = "reconciliation_required"
                    reservation.revision += 1
                    if invocation.status in {"admitted", "running"} and attempt.status in {
                        "admitted",
                        "running",
                    }:
                        attempt.status = "outcome_unknown"
                        attempt.final_error_category = "dispatch_evidence_present"
                        attempt.terminal_at = now
                        attempt.revision += 1
                        invocation.status = "outcome_unknown"
                        invocation.final_attempt_id = None
                        invocation.final_error_category = "dispatch_evidence_present"
                        invocation.terminal_at = now
                        invocation.updated_at = now
                        invocation.revision += 1
                    self._invocation_event(
                        invocation_id=invocation.id,
                        attempt_id=attempt.id,
                        event_type="recovery_reconciliation_required",
                        from_status=previous_status,
                        to_status=invocation.status,
                        safe_metadata={"reservation_released": False},
                    )
                    continue
                user_counter.reserved_minor_units -= reservation.reserved_amount
                user_counter.revision += 1
                if project_counter is not None:
                    project_counter.reserved_minor_units -= reservation.reserved_amount
                    project_counter.revision += 1
                reservation.state = "released"
                reservation.released_at = now
                reservation.revision += 1
                attempt.status = "failed"
                attempt.final_error_category = "dispatch_not_started"
                attempt.terminal_at = now
                attempt.revision += 1
                invocation.status = "failed"
                invocation.final_attempt_id = None
                invocation.final_error_category = "dispatch_not_started"
                invocation.terminal_at = now
                invocation.updated_at = now
                invocation.revision += 1
                self._invocation_event(
                    invocation_id=invocation.id,
                    attempt_id=attempt.id,
                    event_type="admission_recovered",
                    from_status="admitted",
                    to_status="failed",
                    safe_metadata={"reservation_released": True},
                )
                recovered += 1
        return recovered


__all__ = [
    "AIAuthorizationError",
    "AIConflictError",
    "AIFoundationError",
    "AIFoundationService",
    "AIIdempotencyConflictError",
    "AIResourceNotFoundError",
    "AdmissionRejectedError",
    "CredentialRejectedError",
    "Phase3UnavailableError",
    "ValidationRateLimitedError",
]
