"""Transactional Zhipu live admission, dispatch, accounting, and audit coordinator."""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from creativedeploy_api.ai.canonicalization import canonicalize_and_hash
from creativedeploy_api.ai.constants import CANONICALIZATION_VERSION, PROJECTLESS_SCOPE_ID
from creativedeploy_api.ai.encryption import CredentialAAD, CredentialCipher
from creativedeploy_api.ai.provider_transport import (
    NormalizedProviderResult,
    NormalizedProviderUsage,
    PreparedProviderRequest,
    ProviderContractError,
    StructuredOutputValidationError,
)
from creativedeploy_api.ai.retrieval import RetrievedContextBundle
from creativedeploy_api.ai.zhipu_provider import (
    ZHIPU_GLM_5V_HIGH_INPUT_FEN_PER_MILLION,
    ZHIPU_GLM_5V_HIGH_OUTPUT_FEN_PER_MILLION,
    ZHIPU_GLM_5V_TURBO_MODEL,
    ZHIPU_GLM_52_INPUT_FEN_PER_MILLION,
    ZHIPU_GLM_52_MODEL,
    ZHIPU_GLM_52_OUTPUT_FEN_PER_MILLION,
    ZHIPU_PROVIDER_KEY,
    ZhipuChatAdapter,
    ZhipuHTTPTransport,
    assert_zhipu_live_execution_authorized,
)
from creativedeploy_api.core.principal import PrincipalContext
from creativedeploy_api.db.models import (
    AIAuditEvent,
    AICostLedger,
    AIInvocationEvent,
    AIUsageLedger,
    BudgetReservation,
    CommandIdempotencyRecord,
    InvocationAttempt,
    InvocationRequest,
)
from creativedeploy_api.db.models.paint_plan import ProviderPricingSnapshot
from creativedeploy_api.repositories.ai_foundation import SqlAlchemyAIFoundationRepository
from creativedeploy_api.repositories.identity import SqlAlchemyIdentityRepository
from creativedeploy_api.services.ai_foundation import _encrypted_payload

CNY_CURRENCY = "CNY"
WP2_GOVERNED_LEDGER_CAP_FEN = 150
RESERVATION_EXPIRY = timedelta(seconds=120)
BUSINESS_CLAIM_RETENTION = timedelta(days=3650)
BUSINESS_CLAIM_IDEMPOTENCY_KEY = uuid.UUID("87da477f-718f-4df6-a892-637fb40fd0f0")
OutputValidator = Callable[[Mapping[str, object]], dict[str, object]]


def _provider_diagnostic_metadata(error: ProviderContractError | None) -> dict[str, object]:
    """Return only the provider-contract fields approved for durable metadata."""

    if error is None:
        return {}
    metadata: dict[str, object] = {}
    if error.upstream_http_status is not None:
        metadata["upstream_http_status"] = error.upstream_http_status
    if error.provider_error_code is not None:
        metadata["provider_error_code"] = error.provider_error_code
    if error.provider_error_message is not None:
        metadata["provider_error_message"] = error.provider_error_message
    metadata["provider_request_id_status"] = error.provider_request_id_status
    if error.provider_request_id is not None:
        metadata["provider_request_id"] = error.provider_request_id
    if error.finish_reason is not None:
        metadata["finish_reason"] = error.finish_reason
    if error.usage_measurement_status == "measured":
        if error.input_units is not None:
            metadata["prompt_tokens"] = error.input_units
        if error.output_units is not None:
            metadata["completion_tokens"] = error.output_units
    if error.reasoning_tokens is not None:
        metadata["reasoning_tokens"] = error.reasoning_tokens
    if error.output_content_bytes is not None:
        metadata["output_content_bytes"] = error.output_content_bytes
    if error.output_content_characters is not None:
        metadata["output_content_characters"] = error.output_content_characters
    metadata["json_parse_status"] = error.json_parse_status
    metadata["schema_validation_status"] = error.schema_validation_status
    metadata["citation_validation_status"] = error.citation_validation_status
    if error.structured_failure_category is not None:
        metadata["structured_failure_category"] = error.structured_failure_category
    if error.structured_error_path is not None:
        metadata["structured_error_path"] = error.structured_error_path
    if error.structured_expected_root_json_type is not None:
        metadata["structured_expected_root_json_type"] = error.structured_expected_root_json_type
    if error.structured_received_root_json_type is not None:
        metadata["structured_received_root_json_type"] = error.structured_received_root_json_type
    if error.structured_expected_json_type is not None:
        metadata["structured_expected_json_type"] = error.structured_expected_json_type
    if error.structured_received_json_type is not None:
        metadata["structured_received_json_type"] = error.structured_received_json_type
    if error.structured_received_item_count is not None:
        metadata["structured_received_item_count"] = error.structured_received_item_count
    if error.structured_received_object_keys:
        metadata["structured_received_object_keys"] = list(error.structured_received_object_keys)
    if error.structured_missing_required_keys:
        metadata["structured_missing_required_keys"] = list(error.structured_missing_required_keys)
    if error.structured_unexpected_object_keys:
        metadata["structured_unexpected_object_keys"] = list(
            error.structured_unexpected_object_keys
        )
    if error.structured_validator_error_category is not None:
        metadata["structured_validator_error_category"] = error.structured_validator_error_category
    return metadata


def _normalized_completion_metadata(
    normalized: NormalizedProviderResult | None,
    *,
    validated: bool,
) -> dict[str, object]:
    if normalized is None:
        return {}
    metadata: dict[str, object] = {
        "provider_request_id_status": normalized.provider_request_id_status,
        "json_parse_status": normalized.json_parse_status,
        "schema_validation_status": "validated" if validated else "not_attempted",
        "citation_validation_status": "validated" if validated else "not_attempted",
    }
    if normalized.provider_request_id is not None:
        metadata["provider_request_id"] = normalized.provider_request_id
    if normalized.finish_reason is not None:
        metadata["finish_reason"] = normalized.finish_reason
    if normalized.usage.measurement_status == "measured":
        if normalized.usage.input_units is not None:
            metadata["prompt_tokens"] = normalized.usage.input_units
        if normalized.usage.output_units is not None:
            metadata["completion_tokens"] = normalized.usage.output_units
    if normalized.usage.reasoning_tokens is not None:
        metadata["reasoning_tokens"] = normalized.usage.reasoning_tokens
    if normalized.output_content_bytes is not None:
        metadata["output_content_bytes"] = normalized.output_content_bytes
    if normalized.output_content_characters is not None:
        metadata["output_content_characters"] = normalized.output_content_characters
    return metadata


def _safe_request_configuration(request: PreparedProviderRequest) -> dict[str, object]:
    body = request.body
    metadata: dict[str, object] = {
        "max_tokens": body.get("max_tokens"),
        "response_format": body.get("response_format"),
        "thinking": body.get("thinking"),
        "reasoning_effort": body.get("reasoning_effort"),
        "do_sample": body.get("do_sample"),
    }
    return {key: value for key, value in metadata.items() if value is not None}


class ZhipuLiveAdmissionError(RuntimeError):
    """A safe, pre-dispatch live-admission failure."""


class ZhipuBusinessResourceConflictError(ZhipuLiveAdmissionError):
    """The same durable business resource is already claimed."""


@dataclass(frozen=True, slots=True)
class ZhipuLiveSelection:
    product_space: Literal["arcana", "paintpilot"]
    invocation_family: Literal["arcana_interpretation", "paint_plan_generation"]
    project_id: uuid.UUID | None
    provider_definition_id: uuid.UUID
    model_definition_id: uuid.UUID
    credential_id: uuid.UUID
    required_capability_keys: tuple[str, ...]
    estimate_minor_units: int
    pricing_snapshot_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class ZhipuBusinessResourceClaim:
    scope_key: str
    principal_id: str
    command_type: str


@dataclass(frozen=True, slots=True)
class GovernedZhipuResult:
    invocation_id: uuid.UUID
    attempt_id: uuid.UUID
    provider_definition_id: uuid.UUID
    model_definition_id: uuid.UUID
    pricing_snapshot_id: uuid.UUID
    business_claim_id: uuid.UUID
    output: dict[str, object]
    provider_request_id_status: Literal["provided", "unavailable"]
    provider_request_id: str | None
    input_units: int | None
    output_units: int | None
    cost_minor_units: int | None
    currency: Literal["CNY"] = "CNY"


@dataclass(frozen=True, slots=True)
class ZhipuUsageReconciliationResult:
    invocation_id: uuid.UUID
    attempt_id: uuid.UUID
    reservation_before_minor_units: int
    measured_cost_minor_units: int
    committed_after_minor_units: int
    reserved_after_minor_units: int
    reservation_state: Literal["settled"] = "settled"


class ZhipuUsageReconciliationService:
    """Settle one immutable Zhipu Attempt from its existing measured usage ledger."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repository = SqlAlchemyAIFoundationRepository(session)

    async def reconcile(
        self,
        *,
        invocation_id: uuid.UUID,
        attempt_id: uuid.UUID,
    ) -> ZhipuUsageReconciliationResult:
        async with self._session.begin():
            actor_user_id = await self._session.scalar(
                select(InvocationRequest.requesting_user_id).where(
                    InvocationRequest.id == invocation_id
                )
            )
            if actor_user_id is None or await self._repository.lock_user(actor_user_id) is None:
                raise ZhipuLiveAdmissionError("reconciliation actor state rejected")
            invocation = await self._repository.get_invocation(invocation_id, for_update=True)
            attempt = await self._repository.get_attempt(attempt_id, for_update=True)
            reservation = await self._repository.get_reservation(attempt_id, for_update=True)
            usage = await self._session.scalar(
                select(AIUsageLedger)
                .where(
                    AIUsageLedger.invocation_id == invocation_id,
                    AIUsageLedger.attempt_id == attempt_id,
                    AIUsageLedger.source == "zhipu_adapter",
                    AIUsageLedger.canonical_sequence == 1,
                )
                .with_for_update()
            )
            existing_cost = await self._session.scalar(
                select(AICostLedger).where(
                    AICostLedger.invocation_id == invocation_id,
                    AICostLedger.attempt_id == attempt_id,
                    AICostLedger.source == "zhipu_usage_reconciliation",
                    AICostLedger.canonical_sequence == 2,
                )
            )
            if (
                invocation is None
                or attempt is None
                or reservation is None
                or attempt.invocation_id != invocation.id
                or reservation.invocation_id != invocation.id
                or invocation.requesting_user_id is None
                or invocation.status != "failed"
                or attempt.status != "failed"
                or invocation.final_error_category != "schema_invalid"
                or attempt.final_error_category != "schema_invalid"
                or attempt.provider_key != ZHIPU_PROVIDER_KEY
                or attempt.model_id != ZHIPU_GLM_52_MODEL
                or reservation.currency != CNY_CURRENCY
                or usage is None
                or usage.measurement_status != "measured"
                or usage.input_units is None
                or usage.output_units is None
            ):
                raise ZhipuLiveAdmissionError("measured Zhipu reconciliation facts rejected")
            user_counter = await self._repository.get_user_counter_by_id(
                reservation.user_counter_id, for_update=True
            )
            project_counter = (
                None
                if reservation.project_counter_id is None
                else await self._repository.get_project_counter_by_id(
                    reservation.project_counter_id, for_update=True
                )
            )
            pricing_snapshot_id = invocation.budget_snapshot.get("pricing_snapshot_id")
            try:
                pricing_id = uuid.UUID(str(pricing_snapshot_id))
            except (TypeError, ValueError):
                raise ZhipuLiveAdmissionError("pricing snapshot identity rejected") from None
            pricing = await self._session.get(ProviderPricingSnapshot, pricing_id)
            if (
                user_counter is None
                or pricing is None
                or pricing.provider_definition_id != attempt.provider_definition_id
                or pricing.model_definition_id != attempt.model_definition_id
                or pricing.provider_key != ZHIPU_PROVIDER_KEY
                or pricing.model_id != ZHIPU_GLM_52_MODEL
                or pricing.currency != CNY_CURRENCY
                or pricing.unit_basis != "per_million_tokens"
                or pricing.input_minor_units_per_million != ZHIPU_GLM_52_INPUT_FEN_PER_MILLION
                or pricing.output_minor_units_per_million != ZHIPU_GLM_52_OUTPUT_FEN_PER_MILLION
            ):
                raise ZhipuLiveAdmissionError("pricing or counter reconciliation facts rejected")
            raw_reasoning_tokens = usage.safe_metadata.get("reasoning_tokens")
            reasoning_tokens = (
                raw_reasoning_tokens if isinstance(raw_reasoning_tokens, int) else None
            )
            measured = ZhipuChatAdapter(ZHIPU_GLM_52_MODEL).measured_cost(
                NormalizedProviderUsage(
                    measurement_status="measured",
                    input_units=usage.input_units,
                    output_units=usage.output_units,
                    reasoning_tokens=reasoning_tokens,
                )
            )
            if measured is None or measured > reservation.reserved_amount:
                raise ZhipuLiveAdmissionError("measured cost exceeds reserved governance amount")
            if existing_cost is not None:
                if (
                    reservation.state != "settled"
                    or existing_cost.measurement_status != "measured"
                    or existing_cost.amount_minor_units != measured
                ):
                    raise ZhipuLiveAdmissionError("reconciliation replay facts drifted")
                return ZhipuUsageReconciliationResult(
                    invocation_id=invocation.id,
                    attempt_id=attempt.id,
                    reservation_before_minor_units=reservation.reserved_amount,
                    measured_cost_minor_units=measured,
                    committed_after_minor_units=user_counter.committed_minor_units,
                    reserved_after_minor_units=user_counter.reserved_minor_units,
                )
            if (
                reservation.state != "reconciliation_required"
                or user_counter.reserved_minor_units < reservation.reserved_amount
                or (
                    project_counter is not None
                    and project_counter.reserved_minor_units < reservation.reserved_amount
                )
            ):
                raise ZhipuLiveAdmissionError("reconciliation reservation state rejected")
            now = datetime.now(UTC)
            user_counter.reserved_minor_units -= reservation.reserved_amount
            user_counter.committed_minor_units += measured
            user_counter.revision += 1
            if project_counter is not None:
                project_counter.reserved_minor_units -= reservation.reserved_amount
                project_counter.committed_minor_units += measured
                project_counter.revision += 1
            reservation.state = "settled"
            reservation.settled_at = now
            reservation.revision += 1
            self._session.add_all(
                (
                    AICostLedger(
                        id=uuid.uuid4(),
                        invocation_id=invocation.id,
                        attempt_id=attempt.id,
                        provider_definition_id=attempt.provider_definition_id,
                        model_definition_id=attempt.model_definition_id,
                        source="zhipu_usage_reconciliation",
                        canonical_sequence=2,
                        measurement_status="measured",
                        amount_minor_units=measured,
                        currency=CNY_CURRENCY,
                        created_at=now,
                    ),
                    AIInvocationEvent(
                        id=uuid.uuid4(),
                        invocation_id=invocation.id,
                        attempt_id=attempt.id,
                        event_type="usage_cost_reconciled",
                        from_status="failed",
                        to_status="failed",
                        safe_metadata={
                            "currency": CNY_CURRENCY,
                            "measured_cost_minor_units": measured,
                            "reservation_released_minor_units": reservation.reserved_amount,
                            "terminal_evidence_preserved": True,
                        },
                        created_at=now,
                    ),
                    AIAuditEvent(
                        id=uuid.uuid4(),
                        actor_user_id=invocation.requesting_user_id,
                        product_space=invocation.product_space,
                        project_id=invocation.project_id,
                        credential_id=attempt.credential_id,
                        invocation_id=invocation.id,
                        attempt_id=attempt.id,
                        provider_definition_id=attempt.provider_definition_id,
                        model_definition_id=attempt.model_definition_id,
                        action="zhipu_usage_reconciliation",
                        outcome="settled",
                        request_id=invocation.request_id,
                        safe_metadata={
                            "currency": CNY_CURRENCY,
                            "measured_cost_minor_units": measured,
                            "input_units": usage.input_units,
                            "output_units": usage.output_units,
                        },
                        created_at=now,
                    ),
                )
            )
            return ZhipuUsageReconciliationResult(
                invocation_id=invocation.id,
                attempt_id=attempt.id,
                reservation_before_minor_units=reservation.reserved_amount,
                measured_cost_minor_units=measured,
                committed_after_minor_units=user_counter.committed_minor_units,
                reserved_after_minor_units=user_counter.reserved_minor_units,
            )


class GovernedZhipuInvocationService:
    """Reuse the existing Provider ledger while keeping network work outside DB locks."""

    def __init__(
        self,
        session: AsyncSession,
        cipher: CredentialCipher,
        *,
        live_gate_enabled: bool,
        transport: ZhipuHTTPTransport | None = None,
    ) -> None:
        self._session = session
        self._cipher = cipher
        self._live_gate_enabled = live_gate_enabled
        self._transport = transport or ZhipuHTTPTransport()
        self._repository = SqlAlchemyAIFoundationRepository(session)
        self._identity = SqlAlchemyIdentityRepository(session)

    async def _admit(
        self,
        *,
        selection: ZhipuLiveSelection,
        principal: PrincipalContext,
        request: PreparedProviderRequest,
        retrieval: RetrievedContextBundle,
        idempotency_key: uuid.UUID,
        request_id: uuid.UUID,
        safe_input_snapshot: Mapping[str, object],
    ) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
        assert_zhipu_live_execution_authorized(self._live_gate_enabled)
        if principal.user_id is None or selection.estimate_minor_units < 1:
            raise ZhipuLiveAdmissionError("authenticated budgeted user required")
        if selection.estimate_minor_units > WP2_GOVERNED_LEDGER_CAP_FEN:
            raise ZhipuLiveAdmissionError("WP2 governed ledger cap would be exceeded")
        if request.provider_key != ZHIPU_PROVIDER_KEY or request.model_id not in {
            ZHIPU_GLM_52_MODEL,
            ZHIPU_GLM_5V_TURBO_MODEL,
        }:
            raise ZhipuLiveAdmissionError("request is outside the pinned Zhipu contract")
        identity = {
            "selection": {
                "product_space": selection.product_space,
                "invocation_family": selection.invocation_family,
                "project_id": None if selection.project_id is None else str(selection.project_id),
                "provider_definition_id": str(selection.provider_definition_id),
                "model_definition_id": str(selection.model_definition_id),
                "credential_id": str(selection.credential_id),
                "pricing_snapshot_id": str(selection.pricing_snapshot_id),
            },
            "request_model": request.model_id,
            "adapter_version": request.adapter_version,
            "retrieval_hash": retrieval.canonical_hash(),
            "safe_input_snapshot": dict(safe_input_snapshot),
        }
        _, payload_hash = canonicalize_and_hash(identity)
        project_scope_id = selection.project_id or PROJECTLESS_SCOPE_ID
        user_id = principal.user_id
        async with self._session.begin():
            existing = await self._session.scalar(
                select(InvocationRequest).where(
                    InvocationRequest.requesting_user_id == user_id,
                    InvocationRequest.product_space == selection.product_space,
                    InvocationRequest.project_scope_id == project_scope_id,
                    InvocationRequest.invocation_family == selection.invocation_family,
                    InvocationRequest.idempotency_key == idempotency_key,
                )
            )
            if existing is not None:
                raise ZhipuLiveAdmissionError("live invocation key was already consumed")
            active_user = await self._repository.lock_active_user(user_id)
            provider = await self._repository.get_provider_by_id(selection.provider_definition_id)
            model = await self._repository.get_model(selection.model_definition_id)
            credential = await self._repository.get_owned_credential(
                credential_id=selection.credential_id,
                owner_user_id=user_id,
                for_update=True,
            )
            preference = await self._repository.get_preference(user_id, for_update=True)
            user_budget = await self._repository.get_user_budget_policy(
                user_id, currency=CNY_CURRENCY, for_update=True
            )
            now = datetime.now(UTC)
            user_counter = await self._repository.get_user_counter(
                user_id, now, currency=CNY_CURRENCY, for_update=True
            )
            pricing = await self._session.get(
                ProviderPricingSnapshot, selection.pricing_snapshot_id
            )
            expected_input_rate = (
                ZHIPU_GLM_52_INPUT_FEN_PER_MILLION
                if request.model_id == ZHIPU_GLM_52_MODEL
                else ZHIPU_GLM_5V_HIGH_INPUT_FEN_PER_MILLION
            )
            expected_output_rate = (
                ZHIPU_GLM_52_OUTPUT_FEN_PER_MILLION
                if request.model_id == ZHIPU_GLM_52_MODEL
                else ZHIPU_GLM_5V_HIGH_OUTPUT_FEN_PER_MILLION
            )
            capability_keys = sorted(set(selection.required_capability_keys))
            model_capabilities = (
                set()
                if model is None
                else set(await self._repository.model_capability_keys(model.id))
            )
            if (
                active_user is None
                or provider is None
                or provider.provider_key != ZHIPU_PROVIDER_KEY
                or provider.adapter_type != "zhipu_chat_completions"
                or provider.base_url_policy != "provider_managed"
                or not provider.enabled
                or provider.status != "active"
                or model is None
                or model.provider_definition_id != provider.id
                or model.provider_key != ZHIPU_PROVIDER_KEY
                or model.model_id != request.model_id
                or model.status != "active"
                or credential is None
                or credential.status != "active"
                or credential.provider_definition_id != provider.id
                or credential.provider_key != ZHIPU_PROVIDER_KEY
                or credential.last_validation_status == "provider_invalid"
                or preference is None
                or not preference.enabled
                or preference.streaming_enabled
                or preference.default_provider_definition_id != provider.id
                or preference.default_model_definition_id != model.id
                or preference.default_credential_id != credential.id
                or preference.cost_warning_currency != CNY_CURRENCY
                or user_budget is None
                or not user_budget.enabled
                or user_budget.currency != CNY_CURRENCY
                or user_budget.allow_unknown_cost
                or user_counter is None
                or not capability_keys
                or not set(capability_keys).issubset(model_capabilities)
                or pricing is None
                or pricing.provider_definition_id != provider.id
                or pricing.model_definition_id != model.id
                or pricing.provider_key != ZHIPU_PROVIDER_KEY
                or pricing.model_id != model.model_id
                or pricing.currency != CNY_CURRENCY
                or pricing.unit_basis != "per_million_tokens"
                or pricing.input_minor_units_per_million != expected_input_rate
                or pricing.output_minor_units_per_million != expected_output_rate
            ):
                raise ZhipuLiveAdmissionError("live user/provider/model/credential policy rejected")
            if selection.estimate_minor_units > user_budget.per_invocation_limit_minor_units:
                raise ZhipuLiveAdmissionError("user per-invocation budget rejected")
            if (
                user_counter.committed_minor_units
                + user_counter.reserved_minor_units
                + selection.estimate_minor_units
                > min(
                    user_budget.cumulative_limit_minor_units,
                    WP2_GOVERNED_LEDGER_CAP_FEN,
                )
            ):
                raise ZhipuLiveAdmissionError("user cumulative budget rejected")
            committed = await self._session.scalar(
                select(func.coalesce(func.sum(AICostLedger.amount_minor_units), 0))
                .join(
                    InvocationRequest,
                    InvocationRequest.id == AICostLedger.invocation_id,
                )
                .where(
                    InvocationRequest.requesting_user_id == user_id,
                    AICostLedger.currency == CNY_CURRENCY,
                    AICostLedger.amount_minor_units.is_not(None),
                )
            )
            if int(committed or 0) + selection.estimate_minor_units > WP2_GOVERNED_LEDGER_CAP_FEN:
                raise ZhipuLiveAdmissionError("WP2 governed ledger cap rejected")
            project_counter = None
            if selection.project_id is not None:
                access = await self._identity.resolve_project_access(
                    project_id=selection.project_id,
                    principal_id=principal.principal_id,
                    user_id=user_id,
                    for_update=True,
                )
                grant = await self._repository.get_active_grant(
                    credential_id=credential.id,
                    project_id=selection.project_id,
                    for_update=True,
                )
                policy = await self._repository.get_project_policy(
                    selection.project_id, for_update=True
                )
                project_budget = await self._repository.get_project_budget_policy(
                    selection.project_id, currency=CNY_CURRENCY, for_update=True
                )
                project_counter = await self._repository.get_project_counter(
                    selection.project_id, now, currency=CNY_CURRENCY, for_update=True
                )
                allowlists = (
                    ([], [], [], [])
                    if policy is None
                    else await self._repository.policy_allowlists(policy.id)
                )
                providers, models, capabilities, credentials = map(set, allowlists)
                capability_ids = set(
                    await self._repository.capability_ids_for_keys(capability_keys)
                )
                if (
                    access is None
                    or not access.is_owner
                    or access.project.status == "ABANDONED"
                    or grant is None
                    or policy is None
                    or not policy.enabled
                    or policy.currency != CNY_CURRENCY
                    or policy.allow_unknown_cost
                    or policy.allow_manual_model_id
                    or policy.allow_fallback
                    or not policy.require_paid_call_confirmation
                    or provider.id not in providers
                    or model.id not in models
                    or credential.id not in credentials
                    or not capability_ids.issubset(capabilities)
                    or project_budget is None
                    or not project_budget.enabled
                    or project_budget.currency != CNY_CURRENCY
                    or project_budget.allow_unknown_cost
                    or project_counter is None
                    or selection.estimate_minor_units
                    > min(
                        policy.per_invocation_limit_minor_units,
                        project_budget.per_invocation_limit_minor_units,
                    )
                    or project_counter.committed_minor_units
                    + project_counter.reserved_minor_units
                    + selection.estimate_minor_units
                    > project_budget.cumulative_limit_minor_units
                ):
                    raise ZhipuLiveAdmissionError("project live policy rejected")
            invocation = InvocationRequest(
                id=uuid.uuid4(),
                requesting_user_id=user_id,
                product_space=selection.product_space,
                project_id=selection.project_id,
                project_scope_id=project_scope_id,
                invocation_family=selection.invocation_family,
                idempotency_key=idempotency_key,
                canonicalization_version=CANONICALIZATION_VERSION,
                canonical_request_payload_hash=payload_hash,
                requested_capabilities=capability_keys,
                requested_provider_definition_id=provider.id,
                requested_model_definition_id=model.id,
                requested_credential_id=credential.id,
                request_id=request_id,
                max_attempts=1,
                total_elapsed_time_limit_ms=request.timeout_ms,
                confirmation_snapshot={"confirm_paid_call": True, "fallback": False},
                budget_snapshot={
                    "currency": CNY_CURRENCY,
                    "reserved_minor_units": selection.estimate_minor_units,
                    "pricing_snapshot_id": str(pricing.id),
                    "wp2_governed_ledger_cap_minor_units": WP2_GOVERNED_LEDGER_CAP_FEN,
                },
                safe_payload={
                    **dict(safe_input_snapshot),
                    "fixture": False,
                    "live_gate": True,
                    "model_id": model.model_id,
                    "adapter_version": request.adapter_version,
                    "endpoint_policy": "zhipu_official_fixed_chat_completions",
                    "request_body_hash": canonicalize_and_hash(dict(request.body))[1],
                    "request_configuration": _safe_request_configuration(request),
                    "retrieval": retrieval.model_dump(mode="json"),
                    "retrieval_hash": retrieval.canonical_hash(),
                },
                status="admitted",
                final_attempt_id=None,
                started_at=now,
                terminal_at=None,
                cancellation_requested_at=None,
                final_error_category=None,
                output_reference=None,
                revision=1,
                created_at=now,
                updated_at=now,
            )
            attempt = InvocationAttempt(
                id=uuid.uuid4(),
                invocation_id=invocation.id,
                attempt_number=1,
                provider_definition_id=provider.id,
                model_definition_id=model.id,
                provider_key=provider.provider_key,
                model_id=model.model_id,
                adapter_version=request.adapter_version,
                capability_snapshot=capability_keys,
                credential_id=credential.id,
                credential_encryption_version_snapshot=credential.encryption_version,
                temporary_credential=False,
                retry_of_attempt_id=None,
                fallback_decision="disabled",
                currency=CNY_CURRENCY,
                status="admitted",
                dispatched_at=None,
                terminal_at=None,
                cancellation_requested_at=None,
                final_error_category=None,
                output_reference=None,
                safe_provider_metadata={
                    "fixture": False,
                    "egress": "fixed",
                    "live_gate": True,
                },
                provider_request_id_status="absent",
                provider_request_id=None,
                latency_ms=None,
                revision=1,
                created_at=now,
            )
            reservation = BudgetReservation(
                id=uuid.uuid4(),
                invocation_id=invocation.id,
                attempt_id=attempt.id,
                user_counter_id=user_counter.id,
                project_counter_id=None if project_counter is None else project_counter.id,
                currency=CNY_CURRENCY,
                reserved_amount=selection.estimate_minor_units,
                state="reserved",
                created_at=now,
                admission_expires_at=now + RESERVATION_EXPIRY,
                dispatch_committed_at=None,
                settled_at=None,
                released_at=None,
                revision=1,
            )
            user_counter.reserved_minor_units += selection.estimate_minor_units
            user_counter.revision += 1
            if project_counter is not None:
                project_counter.reserved_minor_units += selection.estimate_minor_units
                project_counter.revision += 1
            self._session.add(invocation)
            await self._session.flush()
            self._session.add(attempt)
            await self._session.flush()
            self._session.add(reservation)
            self._session.add_all(
                (
                    AIInvocationEvent(
                        id=uuid.uuid4(),
                        invocation_id=invocation.id,
                        attempt_id=None,
                        event_type="request_created",
                        from_status=None,
                        to_status="admitted",
                        safe_metadata={"fixture": False, "live_gate": True},
                        created_at=now,
                    ),
                )
            )
            return invocation.id, attempt.id, reservation.id

    async def _release_admitted_attempt(
        self,
        *,
        invocation_id: uuid.UUID,
        attempt_id: uuid.UUID,
        reservation_id: uuid.UUID,
        claim_id: uuid.UUID | None,
        error_category: str,
    ) -> None:
        """Release only a claim/admission that never crossed the dispatch marker."""

        async with self._session.begin():
            invocation = await self._repository.get_invocation(invocation_id, for_update=True)
            attempt = await self._repository.get_attempt(attempt_id, for_update=True)
            reservation = await self._repository.get_reservation(attempt_id, for_update=True)
            if (
                invocation is None
                or attempt is None
                or reservation is None
                or reservation.id != reservation_id
                or invocation.status != "admitted"
                or attempt.status != "admitted"
                or reservation.state != "reserved"
            ):
                raise ZhipuLiveAdmissionError("pre-dispatch admission state changed")
            user_counter = await self._repository.get_user_counter_by_id(
                reservation.user_counter_id, for_update=True
            )
            project_counter = (
                None
                if reservation.project_counter_id is None
                else await self._repository.get_project_counter_by_id(
                    reservation.project_counter_id, for_update=True
                )
            )
            if user_counter is None:
                raise ZhipuLiveAdmissionError("pre-dispatch accounting state changed")
            now = datetime.now(UTC)
            user_counter.reserved_minor_units -= reservation.reserved_amount
            user_counter.revision += 1
            if project_counter is not None:
                project_counter.reserved_minor_units -= reservation.reserved_amount
                project_counter.revision += 1
            reservation.state = "released"
            reservation.released_at = now
            reservation.revision += 1
            attempt.status = "failed"
            attempt.final_error_category = error_category
            attempt.terminal_at = now
            attempt.revision += 1
            invocation.status = "failed"
            invocation.final_error_category = error_category
            invocation.terminal_at = now
            invocation.updated_at = now
            invocation.revision += 1
            if claim_id is not None:
                await self._session.execute(
                    delete(CommandIdempotencyRecord).where(
                        CommandIdempotencyRecord.id == claim_id,
                        CommandIdempotencyRecord.execution_status == "in_progress",
                    )
                )
            self._session.add(
                AIInvocationEvent(
                    id=uuid.uuid4(),
                    invocation_id=invocation.id,
                    attempt_id=attempt.id,
                    event_type="attempt_failed",
                    from_status="admitted",
                    to_status="failed",
                    safe_metadata={
                        "error_category": error_category,
                        "dispatch_certainty": "not_dispatched",
                    },
                    created_at=now,
                )
            )

    async def _claim_business_resource(
        self,
        *,
        claim: ZhipuBusinessResourceClaim,
        invocation_id: uuid.UUID,
    ) -> uuid.UUID:
        now = datetime.now(UTC)
        claim_id = uuid.uuid4()
        _, prefixed_hash = canonicalize_and_hash(
            {
                "scope_key": claim.scope_key,
                "principal_id": claim.principal_id,
                "command_type": claim.command_type,
            }
        )
        record = CommandIdempotencyRecord(
            id=claim_id,
            scope_key=claim.scope_key,
            principal_id=claim.principal_id,
            command_type=claim.command_type,
            idempotency_key=BUSINESS_CLAIM_IDEMPOTENCY_KEY,
            payload_hash=prefixed_hash.removeprefix("sha256:"),
            execution_status="in_progress",
            resource_type=None,
            resource_id=None,
            http_status=None,
            response_snapshot={
                "phase": "claimed",
                "invocation_id": str(invocation_id),
            },
            created_at=now,
            expires_at=now + BUSINESS_CLAIM_RETENTION,
        )
        try:
            async with self._session.begin():
                self._session.add(record)
                await self._session.flush()
        except IntegrityError as error:
            raise ZhipuBusinessResourceConflictError(
                "business resource is already claimed"
            ) from error
        return claim_id

    async def _commit_dispatch(
        self,
        *,
        selection: ZhipuLiveSelection,
        principal: PrincipalContext,
        request_id: uuid.UUID,
        invocation_id: uuid.UUID,
        attempt_id: uuid.UUID,
        reservation_id: uuid.UUID,
        claim_id: uuid.UUID,
    ) -> object:
        assert principal.user_id is not None
        async with self._session.begin():
            actor = await self._repository.lock_user(principal.user_id)
            claim = await self._session.get(
                CommandIdempotencyRecord, claim_id, with_for_update=True
            )
            invocation = await self._repository.get_invocation(invocation_id, for_update=True)
            attempt = await self._repository.get_attempt(attempt_id, for_update=True)
            reservation = await self._repository.get_reservation(attempt_id, for_update=True)
            credential = await self._repository.get_owned_credential(
                credential_id=selection.credential_id,
                owner_user_id=principal.user_id,
                for_update=True,
            )
            if (
                actor is None
                or claim is None
                or claim.execution_status != "in_progress"
                or invocation is None
                or attempt is None
                or reservation is None
                or credential is None
                or reservation.id != reservation_id
                or invocation.status != "admitted"
                or attempt.status != "admitted"
                or attempt.dispatched_at is not None
                or reservation.state != "reserved"
                or reservation.dispatch_committed_at is not None
            ):
                raise ZhipuLiveAdmissionError("dispatch boundary state changed")
            now = datetime.now(UTC)
            invocation.status = "running"
            invocation.started_at = now
            invocation.updated_at = now
            invocation.revision += 1
            attempt.status = "running"
            attempt.dispatched_at = now
            attempt.revision += 1
            reservation.state = "dispatch_committed"
            reservation.dispatch_committed_at = now
            reservation.revision += 1
            claim.response_snapshot = {
                "phase": "dispatch_committed",
                "invocation_id": str(invocation.id),
                "attempt_id": str(attempt.id),
            }
            self._session.add_all(
                (
                    AIInvocationEvent(
                        id=uuid.uuid4(),
                        invocation_id=invocation.id,
                        attempt_id=attempt.id,
                        event_type="dispatch_committed",
                        from_status="admitted",
                        to_status="running",
                        safe_metadata={
                            "currency": CNY_CURRENCY,
                            "reserved_minor_units": reservation.reserved_amount,
                            "fallback": False,
                            "business_resource_claimed": True,
                        },
                        created_at=now,
                    ),
                    AIAuditEvent(
                        id=uuid.uuid4(),
                        actor_user_id=principal.user_id,
                        product_space=selection.product_space,
                        project_id=selection.project_id,
                        credential_id=credential.id,
                        invocation_id=invocation.id,
                        attempt_id=attempt.id,
                        provider_definition_id=attempt.provider_definition_id,
                        model_definition_id=attempt.model_definition_id,
                        action="zhipu_live_dispatch",
                        outcome="running",
                        request_id=request_id,
                        safe_metadata={
                            "model_id": attempt.model_id,
                            "live_gate": True,
                            "credential_plaintext": False,
                            "business_resource_claimed": True,
                        },
                        created_at=now,
                    ),
                )
            )
            return self._cipher.decrypt(
                _encrypted_payload(credential),
                aad=CredentialAAD(
                    credential_id=credential.id,
                    owner_user_id=credential.owner_user_id,
                    provider_key=credential.provider_key,
                    encryption_version=credential.encryption_version or "",
                ),
            )

    async def complete_business_resource_claim(
        self,
        *,
        claim_id: uuid.UUID,
        resource_type: str,
        resource_id: uuid.UUID,
        response_snapshot: Mapping[str, object],
    ) -> None:
        """Complete a dispatch claim inside the caller's business-persistence transaction."""

        claim = await self._session.get(CommandIdempotencyRecord, claim_id, with_for_update=True)
        if claim is None or claim.execution_status != "in_progress":
            raise ZhipuLiveAdmissionError("business resource claim state changed")
        claim.execution_status = "completed"
        claim.resource_type = resource_type
        claim.resource_id = resource_id
        claim.http_status = 200
        claim.response_snapshot = dict(response_snapshot)

    async def _release_terminal_business_claim(self, claim_id: uuid.UUID) -> None:
        async with self._session.begin():
            await self._session.execute(
                delete(CommandIdempotencyRecord).where(
                    CommandIdempotencyRecord.id == claim_id,
                    CommandIdempotencyRecord.execution_status == "in_progress",
                )
            )

    async def _terminalize(
        self,
        *,
        selection: ZhipuLiveSelection,
        principal: PrincipalContext,
        request_id: uuid.UUID,
        invocation_id: uuid.UUID,
        attempt_id: uuid.UUID,
        reservation_id: uuid.UUID,
        business_claim_id: uuid.UUID,
        adapter: ZhipuChatAdapter,
        normalized: NormalizedProviderResult | None,
        validated_output: dict[str, object] | None,
        error: ProviderContractError | None,
        latency_ms: int,
    ) -> GovernedZhipuResult | None:
        assert principal.user_id is not None
        async with self._session.begin():
            actor = await self._repository.lock_user(principal.user_id)
            invocation = await self._repository.get_invocation(invocation_id, for_update=True)
            attempt = await self._repository.get_attempt(attempt_id, for_update=True)
            reservation = await self._repository.get_reservation(attempt_id, for_update=True)
            if (
                actor is None
                or invocation is None
                or attempt is None
                or reservation is None
                or reservation.id != reservation_id
                or reservation.state != "dispatch_committed"
                or attempt.status != "running"
            ):
                raise ZhipuLiveAdmissionError("live attempt state changed")
            user_counter = await self._repository.get_user_counter_by_id(
                reservation.user_counter_id, for_update=True
            )
            project_counter = (
                None
                if reservation.project_counter_id is None
                else await self._repository.get_project_counter_by_id(
                    reservation.project_counter_id, for_update=True
                )
            )
            credential = await self._repository.get_owned_credential(
                credential_id=selection.credential_id,
                owner_user_id=principal.user_id,
                for_update=True,
            )
            if user_counter is None or credential is None:
                raise ZhipuLiveAdmissionError("live accounting state changed")
            now = datetime.now(UTC)
            usage = None if normalized is None else normalized.usage
            if (
                usage is None
                and error is not None
                and error.usage_measurement_status == "measured"
                and error.input_units is not None
                and error.output_units is not None
            ):
                usage = NormalizedProviderUsage(
                    measurement_status="measured",
                    input_units=error.input_units,
                    output_units=error.output_units,
                    reasoning_tokens=error.reasoning_tokens,
                )
            measured_cost = None if usage is None else adapter.measured_cost(usage)
            if error is not None:
                request_status = error.provider_request_id_status
                provider_request_id = error.provider_request_id
                usage_status = error.usage_measurement_status
                input_units = error.input_units
                output_units = error.output_units
            elif normalized is not None:
                request_status = normalized.provider_request_id_status
                provider_request_id = normalized.provider_request_id
                usage_status = normalized.usage.measurement_status
                input_units = normalized.usage.input_units
                output_units = normalized.usage.output_units
            else:
                raise ZhipuLiveAdmissionError("live terminal result missing")
            if error is None:
                credential.last_validation_status = "provider_valid"
                credential.last_successful_validation_at = now
                credential.updated_at = now
                credential.revision += 1
            elif error.category == "authentication_failed":
                credential.last_validation_status = "provider_invalid"
                credential.last_successful_validation_at = None
                credential.updated_at = now
                credential.revision += 1
            accounting_reconciliation_required = (
                measured_cost is not None and measured_cost > reservation.reserved_amount
            )
            if measured_cost is not None and not accounting_reconciliation_required:
                actual = measured_cost
                user_counter.reserved_minor_units -= reservation.reserved_amount
                user_counter.committed_minor_units += actual
                user_counter.revision += 1
                if project_counter is not None:
                    project_counter.reserved_minor_units -= reservation.reserved_amount
                    project_counter.committed_minor_units += actual
                    project_counter.revision += 1
                reservation.state = "settled"
                reservation.settled_at = now
            elif accounting_reconciliation_required:
                # Preserve admitted occupancy and measured ledger evidence; a
                # normal overage commit is deliberately forbidden.
                reservation.state = "reconciliation_required"
            elif error is not None and error.dispatch_certainty == "not_dispatched":
                user_counter.reserved_minor_units -= reservation.reserved_amount
                user_counter.revision += 1
                if project_counter is not None:
                    project_counter.reserved_minor_units -= reservation.reserved_amount
                    project_counter.revision += 1
                reservation.state = "released"
                reservation.released_at = now
            else:
                reservation.state = "reconciliation_required"
            reservation.revision += 1
            succeeded = error is None and validated_output is not None
            terminal_status = (
                "succeeded"
                if succeeded
                else "outcome_unknown"
                if error is not None and error.category == "outcome_unknown"
                else "failed"
            )
            error_category = (
                None if succeeded else (error.category if error is not None else "schema_invalid")
            )
            diagnostic_metadata = (
                _provider_diagnostic_metadata(error)
                if error is not None
                else _normalized_completion_metadata(normalized, validated=succeeded)
            )
            attempt.status = terminal_status
            attempt.output_reference = validated_output if succeeded else None
            attempt.final_error_category = error_category
            attempt.provider_request_id_status = request_status
            attempt.provider_request_id = provider_request_id
            attempt.safe_provider_metadata = {
                "fixture": False,
                "model_id": adapter.model_id,
                "usage_measurement_status": usage_status,
                "cost_measurement_status": "measured"
                if measured_cost is not None
                else "unavailable",
                "output_persisted": succeeded,
                "accounting_state": reservation.state,
                "measured_cost_over_reservation": accounting_reconciliation_required,
                **diagnostic_metadata,
            }
            attempt.latency_ms = latency_ms
            attempt.terminal_at = now
            attempt.revision += 1
            invocation.status = terminal_status
            invocation.final_attempt_id = attempt.id if succeeded else None
            invocation.output_reference = validated_output if succeeded else None
            invocation.final_error_category = error_category
            invocation.terminal_at = now
            invocation.updated_at = now
            invocation.revision += 1
            self._session.add(
                AIUsageLedger(
                    id=uuid.uuid4(),
                    invocation_id=invocation.id,
                    attempt_id=attempt.id,
                    provider_definition_id=attempt.provider_definition_id,
                    model_definition_id=attempt.model_definition_id,
                    source="zhipu_adapter",
                    canonical_sequence=1,
                    measurement_status=usage_status,
                    input_units=input_units,
                    output_units=output_units,
                    safe_metadata={
                        "fixture": False,
                        **(
                            {"reasoning_tokens": usage.reasoning_tokens}
                            if usage is not None and usage.reasoning_tokens is not None
                            else {}
                        ),
                    },
                    created_at=now,
                )
            )
            self._session.add(
                AICostLedger(
                    id=uuid.uuid4(),
                    invocation_id=invocation.id,
                    attempt_id=attempt.id,
                    provider_definition_id=attempt.provider_definition_id,
                    model_definition_id=attempt.model_definition_id,
                    source="zhipu_adapter",
                    canonical_sequence=1,
                    measurement_status="measured" if measured_cost is not None else "unavailable",
                    amount_minor_units=measured_cost,
                    currency=CNY_CURRENCY,
                    created_at=now,
                )
            )
            self._session.add_all(
                (
                    AIInvocationEvent(
                        id=uuid.uuid4(),
                        invocation_id=invocation.id,
                        attempt_id=attempt.id,
                        event_type=(
                            "attempt_succeeded"
                            if succeeded
                            else "reconciliation_required"
                            if terminal_status == "outcome_unknown"
                            or accounting_reconciliation_required
                            else "attempt_failed"
                        ),
                        from_status="running",
                        to_status=terminal_status,
                        safe_metadata={
                            "error_category": error_category,
                            "retry": False,
                            "currency": CNY_CURRENCY,
                            "accounting_state": reservation.state,
                            "measured_cost_over_reservation": (accounting_reconciliation_required),
                            **diagnostic_metadata,
                        },
                        created_at=now,
                    ),
                    AIAuditEvent(
                        id=uuid.uuid4(),
                        actor_user_id=principal.user_id,
                        product_space=selection.product_space,
                        project_id=selection.project_id,
                        credential_id=selection.credential_id,
                        invocation_id=invocation.id,
                        attempt_id=attempt.id,
                        provider_definition_id=attempt.provider_definition_id,
                        model_definition_id=attempt.model_definition_id,
                        action="zhipu_live_attempt",
                        outcome=terminal_status,
                        request_id=request_id,
                        safe_metadata={
                            "error_category": error_category,
                            "retry": False,
                            "cost_minor_units": measured_cost,
                            "currency": CNY_CURRENCY,
                            "accounting_state": reservation.state,
                            "measured_cost_over_reservation": (accounting_reconciliation_required),
                            **diagnostic_metadata,
                        },
                        created_at=now,
                    ),
                )
            )
            if not succeeded:
                return None
            assert validated_output is not None
            return GovernedZhipuResult(
                invocation_id=invocation.id,
                attempt_id=attempt.id,
                provider_definition_id=attempt.provider_definition_id,
                model_definition_id=attempt.model_definition_id,
                pricing_snapshot_id=selection.pricing_snapshot_id,
                business_claim_id=business_claim_id,
                output=validated_output,
                provider_request_id_status=request_status,  # type: ignore[arg-type]
                provider_request_id=provider_request_id,
                input_units=input_units,
                output_units=output_units,
                cost_minor_units=measured_cost,
            )

    async def execute(
        self,
        *,
        selection: ZhipuLiveSelection,
        principal: PrincipalContext,
        request: PreparedProviderRequest,
        retrieval: RetrievedContextBundle,
        output_validator: OutputValidator,
        idempotency_key: uuid.UUID,
        request_id: uuid.UUID,
        safe_input_snapshot: Mapping[str, object],
        business_claim: ZhipuBusinessResourceClaim,
    ) -> GovernedZhipuResult:
        adapter = ZhipuChatAdapter(request.model_id)  # type: ignore[arg-type]
        invocation_id, attempt_id, reservation_id = await self._admit(
            selection=selection,
            principal=principal,
            request=request,
            retrieval=retrieval,
            idempotency_key=idempotency_key,
            request_id=request_id,
            safe_input_snapshot=safe_input_snapshot,
        )
        try:
            business_claim_id = await self._claim_business_resource(
                claim=business_claim,
                invocation_id=invocation_id,
            )
        except ZhipuBusinessResourceConflictError:
            await self._release_admitted_attempt(
                invocation_id=invocation_id,
                attempt_id=attempt_id,
                reservation_id=reservation_id,
                claim_id=None,
                error_category="business_resource_claim_conflict",
            )
            raise
        try:
            secret = await self._commit_dispatch(
                selection=selection,
                principal=principal,
                request_id=request_id,
                invocation_id=invocation_id,
                attempt_id=attempt_id,
                reservation_id=reservation_id,
                claim_id=business_claim_id,
            )
        except Exception:
            await self._release_admitted_attempt(
                invocation_id=invocation_id,
                attempt_id=attempt_id,
                reservation_id=reservation_id,
                claim_id=business_claim_id,
                error_category="dispatch_boundary_rejected",
            )
            raise
        started = time.monotonic()
        normalized: NormalizedProviderResult | None = None
        validated_output: dict[str, object] | None = None
        error: ProviderContractError | None = None
        try:
            wire = await self._transport.execute(
                request,
                secret,  # type: ignore[arg-type]
                live_gate_enabled=self._live_gate_enabled,
            )
            normalized = adapter.normalize_response(wire)
            try:
                validated_output = output_validator(normalized.output)
            except StructuredOutputValidationError as validation_error:
                error = ProviderContractError(
                    "schema_invalid",
                    dispatch_certainty="dispatched",
                    provider_request_id_status=normalized.provider_request_id_status,
                    provider_request_id=normalized.provider_request_id,
                    usage_measurement_status=normalized.usage.measurement_status,
                    input_units=normalized.usage.input_units,
                    output_units=normalized.usage.output_units,
                    finish_reason=normalized.finish_reason,
                    reasoning_tokens=normalized.usage.reasoning_tokens,
                    output_content_bytes=normalized.output_content_bytes,
                    output_content_characters=normalized.output_content_characters,
                    json_parse_status=normalized.json_parse_status,
                    schema_validation_status="failed",
                    citation_validation_status=(
                        "failed"
                        if validation_error.category == "CITATION_VALIDATION_FAILED"
                        else "not_attempted"
                    ),
                    structured_failure_category=validation_error.category,
                    structured_error_path=validation_error.path,
                    structured_expected_root_json_type=(validation_error.expected_root_json_type),
                    structured_received_root_json_type=(validation_error.received_root_json_type),
                    structured_expected_json_type=validation_error.expected_json_type,
                    structured_received_json_type=validation_error.received_json_type,
                    structured_received_item_count=validation_error.received_item_count,
                    structured_received_object_keys=validation_error.received_object_keys,
                    structured_missing_required_keys=validation_error.missing_required_keys,
                    structured_unexpected_object_keys=validation_error.unexpected_object_keys,
                    structured_validator_error_category=(validation_error.validator_error_category),
                )
            except (TypeError, ValueError) as validation_error:
                del validation_error
                error = ProviderContractError(
                    "schema_invalid",
                    dispatch_certainty="dispatched",
                    provider_request_id_status=normalized.provider_request_id_status,
                    provider_request_id=normalized.provider_request_id,
                    usage_measurement_status=normalized.usage.measurement_status,
                    input_units=normalized.usage.input_units,
                    output_units=normalized.usage.output_units,
                    finish_reason=normalized.finish_reason,
                    reasoning_tokens=normalized.usage.reasoning_tokens,
                    output_content_bytes=normalized.output_content_bytes,
                    output_content_characters=normalized.output_content_characters,
                    json_parse_status=normalized.json_parse_status,
                    schema_validation_status="failed",
                    structured_failure_category="SCHEMA_VALIDATION_FAILED",
                    structured_error_path="$",
                )
        except ProviderContractError as provider_error:
            error = provider_error
        finally:
            del secret
        latency_ms = max(0, round((time.monotonic() - started) * 1000))
        result = await self._terminalize(
            selection=selection,
            principal=principal,
            request_id=request_id,
            invocation_id=invocation_id,
            attempt_id=attempt_id,
            reservation_id=reservation_id,
            business_claim_id=business_claim_id,
            adapter=adapter,
            normalized=normalized,
            validated_output=validated_output,
            error=error,
            latency_ms=latency_ms,
        )
        if error is not None:
            if error.category != "outcome_unknown":
                await self._release_terminal_business_claim(business_claim_id)
            raise error
        if result is None:
            raise ProviderContractError("schema_invalid", dispatch_certainty="dispatched")
        return result
