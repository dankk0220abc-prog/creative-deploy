"""Strict AI foundation configuration requests and safe response contracts."""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    SecretStr,
    field_validator,
    model_validator,
)

from creativedeploy_api.schemas.paint_plans import PaintPlanFixtureSource

FixtureCurrency = Literal["FIXTURE_CREDITS"]
Currency = Literal["FIXTURE_CREDITS", "USD"]
ProviderKey = Literal["fixture_local", "openai"]
CredentialSecret = Annotated[SecretStr, Field(min_length=1, max_length=4096)]
CredentialValidationStatus = Literal[
    "fixture_valid",
    "fixture_invalid",
    "live_validation_not_authorized",
]
RequestUUID = Annotated[
    UUID,
    BeforeValidator(lambda value: UUID(value) if isinstance(value, str) else value),
]
InvocationFamily = Literal[
    "fixture_credential_validation",
    "fixture_model_catalog",
    "fixture_invocation",
    "paint_plan_generation",
]
InvocationStatus = Literal[
    "pending",
    "admitted",
    "running",
    "succeeded",
    "failed",
    "cancelled",
    "outcome_unknown",
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class CapabilityRead(StrictModel):
    id: UUID
    capability_key: str
    display_name: str
    status: str
    source: str | None = None
    trust_status: str | None = None


class ProviderRead(StrictModel):
    id: UUID
    provider_key: str
    display_name: str
    adapter_type: str
    enabled: bool
    status: str
    catalog_status: str
    catalog_fresh_at: datetime | None
    local_only: bool
    real_model_calls: bool
    real_cost: bool
    capabilities: list[CapabilityRead]


class ProviderListResponse(StrictModel):
    items: list[ProviderRead]


class ModelRead(StrictModel):
    id: UUID
    provider_key: str
    model_id: str
    display_name: str
    catalog_source: str
    catalog_status: str
    catalog_fresh_at: datetime | None
    status: str
    context_window: int | None
    pricing_minor_units: int | None
    pricing_currency: Currency | None
    local_only: bool
    capabilities: list[CapabilityRead]


class ModelListResponse(StrictModel):
    items: list[ModelRead]


class CapabilityListResponse(StrictModel):
    items: list[CapabilityRead]


class CredentialRead(StrictModel):
    id: UUID
    alias: str
    provider_key: str
    fingerprint: str
    last_four: str | None
    status: Literal["active", "revoked", "replaced"]
    created_at: datetime
    updated_at: datetime
    revoked_at: datetime | None
    replaced_at: datetime | None
    last_validation_status: str | None
    last_successful_validation_at: datetime | None
    revision: int


class CredentialListResponse(StrictModel):
    items: list[CredentialRead]


class TemporaryCredentialValidationRequest(StrictModel):
    provider_key: ProviderKey
    credential: CredentialSecret


class CredentialCreateRequest(StrictModel):
    provider_key: ProviderKey
    alias: Annotated[str, Field(min_length=1, max_length=120)]
    credential: CredentialSecret
    confirm_save: Literal[True]

    @field_validator("alias")
    @classmethod
    def normalize_alias(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("alias must not be blank")
        return normalized


class CredentialReplaceRequest(StrictModel):
    alias: Annotated[str, Field(min_length=1, max_length=120)]
    credential: CredentialSecret
    expected_revision: Annotated[int, Field(ge=1)]
    confirm_replace: Literal[True]


class CredentialMutationRequest(StrictModel):
    expected_revision: Annotated[int, Field(ge=1)]
    confirm: Literal[True]


class CredentialValidationResponse(StrictModel):
    provider_key: ProviderKey
    valid: bool
    validation_status: CredentialValidationStatus
    message_code: str
    fixture: bool
    local_only: bool
    persisted: bool


class CredentialGrantRequest(StrictModel):
    project_id: RequestUUID
    expected_credential_revision: Annotated[int, Field(ge=1)]


class CredentialGrantRead(StrictModel):
    id: UUID
    credential_id: UUID
    project_id: UUID
    active: bool
    created_at: datetime
    revoked_at: datetime | None
    revision: int


class UserPreferenceUpdate(StrictModel):
    enabled: bool
    default_provider_definition_id: RequestUUID | None
    default_model_definition_id: RequestUUID | None
    default_credential_id: RequestUUID | None
    timeout_ms: Annotated[int, Field(ge=1, le=120_000)]
    streaming_enabled: Literal[False]
    cost_warning_minor_units: Annotated[int, Field(ge=0)] | None
    currency: Currency = "FIXTURE_CREDITS"
    budget_per_invocation_minor_units: Annotated[int, Field(ge=1)]
    budget_cumulative_minor_units: Annotated[int, Field(ge=1)]
    budget_window_seconds: Annotated[int, Field(ge=60, le=2_592_000)]
    expected_revision: Annotated[int, Field(ge=0)]


class UserPreferenceRead(StrictModel):
    enabled: bool
    default_provider_definition_id: UUID | None
    default_model_definition_id: UUID | None
    default_credential_id: UUID | None
    timeout_ms: int
    streaming_enabled: bool
    cost_warning_minor_units: int | None
    currency: Currency
    budget_per_invocation_minor_units: int | None
    budget_cumulative_minor_units: int | None
    budget_window_seconds: int | None
    revision: int


class ProjectPolicyUpdate(StrictModel):
    enabled: bool
    default_provider_definition_id: RequestUUID
    default_model_definition_id: RequestUUID
    default_credential_id: RequestUUID
    provider_allowlist: list[RequestUUID]
    model_allowlist: list[RequestUUID]
    capability_allowlist: list[RequestUUID]
    credential_allowlist: list[RequestUUID]
    per_invocation_limit_minor_units: Annotated[int, Field(ge=1)]
    cumulative_limit_minor_units: Annotated[int, Field(ge=1)]
    budget_window_seconds: Annotated[int, Field(ge=60, le=2_592_000)]
    currency: Currency = "FIXTURE_CREDITS"
    allow_unknown_cost: Literal[False]
    allow_manual_model_id: Literal[False]
    allow_fallback: Literal[False]
    require_paid_call_confirmation: bool
    expected_revision: Annotated[int, Field(ge=0)]

    @model_validator(mode="after")
    def defaults_must_be_allowlisted(self) -> "ProjectPolicyUpdate":
        if self.default_provider_definition_id not in self.provider_allowlist:
            raise ValueError("default provider must be allowlisted")
        if self.default_model_definition_id not in self.model_allowlist:
            raise ValueError("default model must be allowlisted")
        if self.default_credential_id not in self.credential_allowlist:
            raise ValueError("default credential must be allowlisted")
        return self


class ProjectPolicyRead(StrictModel):
    project_id: UUID
    enabled: bool
    default_provider_definition_id: UUID | None
    default_model_definition_id: UUID | None
    default_credential_id: UUID | None
    provider_allowlist: list[UUID]
    model_allowlist: list[UUID]
    capability_allowlist: list[UUID]
    credential_allowlist: list[UUID]
    active_grant_credential_ids: list[UUID]
    per_invocation_limit_minor_units: int | None
    cumulative_limit_minor_units: int | None
    budget_window_seconds: int | None
    currency: Currency
    allow_unknown_cost: bool
    allow_manual_model_id: bool
    allow_fallback: bool
    require_paid_call_confirmation: bool
    resolved_status: str
    revision: int


class FixtureInvocationPayload(StrictModel):
    prompt_label: Annotated[str, Field(min_length=1, max_length=160)]
    fixture_input: Annotated[str, Field(min_length=1, max_length=2_000)]
    scenario: Literal[
        "success",
        "authentication_failed",
        "invalid_request",
        "provider_unavailable",
        "rate_limited",
        "outcome_unknown",
    ] = "success"
    paint_plan_input: PaintPlanFixtureSource | None = None

    @model_validator(mode="after")
    def governed_paint_plan_marker_matches_payload(self) -> "FixtureInvocationPayload":
        is_paint_plan = self.prompt_label == "paint-plan.v1"
        if is_paint_plan != (self.paint_plan_input is not None):
            raise ValueError("paint-plan.v1 requires exactly one governed paint_plan_input")
        if is_paint_plan and self.fixture_input != "governed-server-snapshot":
            raise ValueError("paint-plan.v1 fixture input must be server-governed")
        return self


class ArtifactIdentity(StrictModel):
    id: RequestUUID
    revision: Annotated[int, Field(ge=1)]
    content_hash: Annotated[str, Field(pattern=r"^sha256:[0-9a-f]{64}$")]
    media_type: Annotated[str, Field(min_length=3, max_length=160)]
    byte_length: Annotated[int, Field(ge=0, le=100_000_000)]


class InvocationPreviewRequest(StrictModel):
    product_space: Literal["paintpilot"]
    project_id: RequestUUID | None
    invocation_family: InvocationFamily
    provider_definition_id: RequestUUID
    model_definition_id: RequestUUID
    credential_id: RequestUUID | None = None
    temporary_credential: SecretStr | None = None
    requested_capabilities: list[str]
    artifacts: list[ArtifactIdentity] = Field(default_factory=list, max_length=16)
    payload: FixtureInvocationPayload
    confirm_fixture_use: Literal[True]

    @model_validator(mode="after")
    def exactly_one_credential_source(self) -> "InvocationPreviewRequest":
        if (self.credential_id is None) == (self.temporary_credential is None):
            raise ValueError("exactly one saved or temporary credential is required")
        if self.project_id is not None and self.temporary_credential is not None:
            raise ValueError("project-scoped invocation requires a saved credential")
        return self


class InvocationPreviewRead(StrictModel):
    admissible: bool
    provider_key: str
    model_id: str
    credential_alias: str
    required_grant: bool
    active_grant: bool
    estimated_cost_minor_units: int
    currency: FixtureCurrency
    fixture: Literal[True]
    local_only: Literal[True]
    fallback_enabled: Literal[False]
    confirmation_required: bool


class InvocationCreateRequest(InvocationPreviewRequest):
    max_attempts: Annotated[int, Field(ge=1, le=3)] = 1
    total_elapsed_time_limit_ms: Annotated[int, Field(ge=1, le=120_000)] = 30_000


class AttemptRead(StrictModel):
    id: UUID
    attempt_number: int
    provider_key: str
    model_id: str
    status: str
    currency: FixtureCurrency
    dispatched_at: datetime | None
    terminal_at: datetime | None
    final_error_category: str | None
    provider_request_id_status: Literal["absent", "provided", "unavailable"]
    provider_request_id: str | None
    safe_provider_metadata: dict[str, object]


class InvocationRead(StrictModel):
    id: UUID
    product_space: str
    project_id: UUID | None
    invocation_family: InvocationFamily
    canonicalization_version: Literal["phase3a-v1"]
    payload_hash: str
    status: InvocationStatus
    final_attempt_id: UUID | None
    final_error_category: str | None
    output: dict[str, object] | None
    currency: FixtureCurrency
    created_at: datetime
    updated_at: datetime
    replayed: bool = False
    attempts: list[AttemptRead]


class CancelInvocationRequest(StrictModel):
    confirm: Literal[True]


class UsageAuditRead(StrictModel):
    id: UUID
    created_at: datetime
    action: str
    outcome: str
    project_id: UUID | None
    credential_id: UUID | None
    invocation_id: UUID | None
    provider_definition_id: UUID | None
    model_definition_id: UUID | None
    safe_metadata: dict[str, object]


class UsageAuditListResponse(StrictModel):
    items: list[UsageAuditRead]
    total: int
    limit: int
    offset: int
