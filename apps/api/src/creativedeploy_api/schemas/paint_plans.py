"""Strict Phase 3B governed Paint Plan request and response contracts."""

from __future__ import annotations

import hashlib
import json
import unicodedata
from datetime import datetime
from typing import Annotated, Final, Literal
from uuid import UUID

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, field_validator, model_validator

from creativedeploy_api.ai.retrieval import RetrievedCitation, RetrievedContextUnit

PAINT_PLAN_SCHEMA_VERSION = "paint-plan.v1"
PAINT_PLAN_PROMPT_KEY = "paint-plan"
PAINT_PLAN_PROMPT_VERSION = 1
PAINT_PLAN_LIVE_PROMPT_VERSION: Final = 2
MAX_PLAN_INSTRUCTIONS = 128
MAX_PLAN_WARNINGS = 8
MAX_PLAN_SAFETY_NOTES = 16

RequestUUID = Annotated[
    UUID,
    BeforeValidator(lambda value: UUID(value) if isinstance(value, str) else value),
]
ProviderExecutionMode = Literal["fixture_available", "live_authorization_required"]
GenerationLocale = Literal["zh-CN", "en-US"]
PlanRevisionKind = Literal["generated", "edited", "regenerated"]
PlanLifecycle = Literal[
    "generated",
    "edited",
    "under_review",
    "approved",
    "rejected",
    "superseded",
]


def _normalize_text(value: str, *, field_name: str, forbid_html: bool = True) -> str:
    normalized = " ".join(value.strip().split())
    if not normalized:
        raise ValueError(f"{field_name} must not be blank")
    if any(unicodedata.category(character) == "Cc" for character in normalized):
        raise ValueError(f"{field_name} must not contain control characters")
    if forbid_html and ("<" in normalized or ">" in normalized):
        raise ValueError(f"{field_name} must not contain HTML")
    return normalized


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class PaintPlanRegionInstruction(StrictModel):
    """One typed instruction bound to one exact paint Region."""

    region_id: RequestUUID
    stable_region_key: RequestUUID
    region_label: Annotated[str, Field(min_length=1, max_length=80)]
    target_color: Annotated[str, Field(min_length=1, max_length=120)]
    preparation: Annotated[str, Field(min_length=1, max_length=600)]
    base_coat: Annotated[str, Field(min_length=1, max_length=600)]
    layer_strategy: Annotated[str, Field(min_length=1, max_length=1000)]
    edge_treatment: Annotated[str, Field(min_length=1, max_length=600)]
    lighting_guidance: Annotated[str, Field(min_length=1, max_length=600)]
    material_guidance: Annotated[str, Field(min_length=1, max_length=600)]
    warnings: Annotated[
        list[Annotated[str, Field(min_length=1, max_length=240)]],
        Field(max_length=MAX_PLAN_WARNINGS),
    ]
    confidence_ppm: Annotated[int, Field(ge=0, le=1_000_000)]

    @field_validator(
        "region_label",
        "target_color",
        "preparation",
        "base_coat",
        "layer_strategy",
        "edge_treatment",
        "lighting_guidance",
        "material_guidance",
    )
    @classmethod
    def normalize_fields(cls, value: str, info: object) -> str:
        field_name = getattr(info, "field_name", "instruction")
        return _normalize_text(value, field_name=field_name)

    @field_validator("warnings")
    @classmethod
    def normalize_warnings(cls, values: list[str]) -> list[str]:
        normalized = [_normalize_text(value, field_name="warning") for value in values]
        if len(normalized) != len(set(normalized)):
            raise ValueError("warnings must be unique")
        return normalized


class PaintPlanDocument(StrictModel):
    """Provider/user-authored structured content before persistence projection."""

    schema_version: Literal["paint-plan.v1"]
    title: Annotated[str, Field(min_length=1, max_length=160)]
    overall_approach: Annotated[str, Field(min_length=1, max_length=2000)]
    instructions: Annotated[
        list[PaintPlanRegionInstruction],
        Field(min_length=1, max_length=MAX_PLAN_INSTRUCTIONS),
    ]
    safety_notes: Annotated[
        list[Annotated[str, Field(min_length=1, max_length=400)]],
        Field(max_length=MAX_PLAN_SAFETY_NOTES),
    ]
    knowledge_citations: Annotated[list[RetrievedCitation], Field(max_length=24)] = Field(
        default_factory=list
    )

    @field_validator("title", "overall_approach")
    @classmethod
    def normalize_copy(cls, value: str, info: object) -> str:
        return _normalize_text(value, field_name=getattr(info, "field_name", "plan"))

    @field_validator("safety_notes")
    @classmethod
    def normalize_safety_notes(cls, values: list[str]) -> list[str]:
        normalized = [_normalize_text(value, field_name="safety note") for value in values]
        if len(normalized) != len(set(normalized)):
            raise ValueError("safety notes must be unique")
        return normalized

    @model_validator(mode="after")
    def exact_instruction_identities(self) -> PaintPlanDocument:
        region_ids = [item.region_id for item in self.instructions]
        stable_keys = [item.stable_region_key for item in self.instructions]
        if len(region_ids) != len(set(region_ids)):
            raise ValueError("instruction region_id must be unique")
        if len(stable_keys) != len(set(stable_keys)):
            raise ValueError("instruction stable_region_key must be unique")
        return self


PAINT_PLAN_REQUIRED_ROOT_KEYS: Final = (
    "schema_version",
    "title",
    "overall_approach",
    "instructions",
    "safety_notes",
)
PAINT_PLAN_OPTIONAL_ROOT_KEYS: Final = ("knowledge_citations",)
PAINT_PLAN_ROOT_KEYS: Final = PAINT_PLAN_REQUIRED_ROOT_KEYS + PAINT_PLAN_OPTIONAL_ROOT_KEYS
PAINT_PLAN_INSTRUCTION_KEYS: Final = (
    "region_id",
    "stable_region_key",
    "region_label",
    "target_color",
    "preparation",
    "base_coat",
    "layer_strategy",
    "edge_treatment",
    "lighting_guidance",
    "material_guidance",
    "warnings",
    "confidence_ppm",
)
PAINT_PLAN_CITATION_KEYS: Final = ("source_id", "chunk_id", "target_path")


def paint_plan_live_output_template() -> dict[str, object]:
    """Compact direct-root shape hint; authoritative validation remains Pydantic."""

    return {
        "schema_version": "paint-plan.v1",
        "title": "string (1..160 characters)",
        "overall_approach": "string (1..2000 characters)",
        "instructions": [
            {
                "region_id": "copy the exact governed paint-region UUID",
                "stable_region_key": "copy its exact governed stable-region UUID",
                "region_label": "copy its exact governed label",
                "target_color": "string (1..120 characters)",
                "preparation": "string (1..600 characters)",
                "base_coat": "string (1..600 characters)",
                "layer_strategy": "string (1..1000 characters)",
                "edge_treatment": "string (1..600 characters)",
                "lighting_guidance": "string (1..600 characters)",
                "material_guidance": "string (1..600 characters)",
                "warnings": ["string (1..240 characters; 0..8 unique items)"],
                "confidence_ppm": 0,
            }
        ],
        "safety_notes": ["string (1..400 characters; 0..16 unique items)"],
        "knowledge_citations": [
            {
                "source_id": "copy an exact retrieved source_id",
                "chunk_id": "copy its exact retrieved chunk_id",
                "target_path": "/JSON/pointer/to/supported/plan/field",
            }
        ],
    }


def paint_plan_live_output_contract() -> str:
    template = json.dumps(
        paint_plan_live_output_template(),
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return (
        f"PaintPilot live output contract v{PAINT_PLAN_LIVE_PROMPT_VERSION}. The response root "
        "must be this direct JSON object. Do not wrap it in paint_plan, plan, document, data, "
        "result, response, or output. Do not rename, omit, or add fields. Replace the descriptive "
        f"template values while preserving its exact object/list shape:\n{template}\n"
        "Produce 1..128 instructions: exactly one for every governed kind=paint region and none "
        "for kind=exclude. Copy region_id, stable_region_key, and region_label exactly. "
        "confidence_ppm is an integer from 0 through 1000000. Every object forbids extra keys. "
        "For live output, knowledge_citations must contain 1..24 entries and may use only exact "
        "retrieved source_id/chunk_id pairs; target_path identifies the supported plan field."
    )


class PaintPlanSelectionRequest(StrictModel):
    """Exact governed source and model selection shared by preview/generation."""

    image_set_fingerprint: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    region_set_id: RequestUUID
    provider_definition_id: RequestUUID
    model_definition_id: RequestUUID
    credential_id: RequestUUID
    generation_locale: GenerationLocale = "en-US"
    intent: Annotated[str, Field(min_length=1, max_length=1200)] | None = None

    @field_validator("intent")
    @classmethod
    def normalize_intent(cls, value: str | None) -> str | None:
        return None if value is None else _normalize_text(value, field_name="intent")


class PaintPlanPreviewRequest(PaintPlanSelectionRequest):
    pass


class PaintPlanGenerateRequest(PaintPlanSelectionRequest):
    confirm_generation: Literal[True]
    max_attempts: Annotated[int, Field(ge=1, le=3)] = 1


class PaintPlanEditRequest(StrictModel):
    expected_current_plan_id: RequestUUID
    expected_current_version: Annotated[int, Field(ge=1)]
    document: PaintPlanDocument


class PaintPlanRevisionRequest(StrictModel):
    expected_current_plan_id: RequestUUID
    expected_current_version: Annotated[int, Field(ge=1)]


class PaintPlanReviewRequest(PaintPlanRevisionRequest):
    reason: Annotated[str, Field(min_length=1, max_length=1000)] | None = None

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str | None) -> str | None:
        return (
            None
            if value is None
            else _normalize_text(
                value,
                field_name="reason",
                forbid_html=False,
            )
        )


class PaintPlanRegenerateRequest(PaintPlanSelectionRequest, PaintPlanRevisionRequest):
    confirm_generation: Literal[True]
    max_attempts: Annotated[int, Field(ge=1, le=3)] = 1


class PaintPlanImageAssetRead(StrictModel):
    id: UUID
    role: str
    version: Annotated[int, Field(ge=1)]
    content_url: str
    sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    media_type: Literal["image/jpeg", "image/png", "image/webp"]
    byte_length: Annotated[int, Field(ge=1, le=20_971_520)]
    width: Annotated[int, Field(ge=1, le=8192)]
    height: Annotated[int, Field(ge=1, le=8192)]
    upload_validation_result: str
    rights_attestation_status: str
    rights_attestation_version: Annotated[int, Field(ge=1)]
    intended_usage: list[str]


class PaintPlanRegionSourceRead(StrictModel):
    id: UUID
    stable_region_key: UUID
    kind: Literal["paint", "exclude"]
    label: Annotated[str, Field(min_length=1, max_length=80)]
    normalized_label: Annotated[str, Field(min_length=1, max_length=80)]
    z_index: Annotated[int, Field(ge=0, le=127)]
    opacity_ppm: Annotated[int, Field(ge=100_000, le=1_000_000)]
    notes: Annotated[str, Field(min_length=1, max_length=1000)] | None
    bbox_min_x_ppm: Annotated[int, Field(ge=0, le=1_000_000)]
    bbox_min_y_ppm: Annotated[int, Field(ge=0, le=1_000_000)]
    bbox_max_x_ppm: Annotated[int, Field(ge=0, le=1_000_000)]
    bbox_max_y_ppm: Annotated[int, Field(ge=0, le=1_000_000)]
    vertices: Annotated[
        list[
            tuple[
                Annotated[int, Field(ge=0, le=1_000_000)],
                Annotated[int, Field(ge=0, le=1_000_000)],
            ]
        ],
        Field(min_length=3, max_length=256),
    ]


class PaintPlanRegionSetRead(StrictModel):
    id: UUID
    version: Annotated[int, Field(ge=1)]
    geometry_fingerprint: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    effective_lifecycle: str
    stale: bool
    regions: list[PaintPlanRegionSourceRead]


class PaintPlanFixtureSource(StrictModel):
    """Server-owned canonical source consumed by the deterministic fixture."""

    image_set_fingerprint: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    readiness_review_id: UUID
    readiness_review_version: Annotated[int, Field(ge=1)]
    image_assets: Annotated[
        list[PaintPlanImageAssetRead],
        Field(min_length=3, max_length=4),
    ]
    region_set: PaintPlanRegionSetRead
    prompt_template_id: UUID
    prompt_template_key: Literal["paint-plan"]
    prompt_template_version: Literal[1]
    prompt_template_body: Annotated[str, Field(min_length=1, max_length=12000)]
    prompt_content_hash: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    response_schema_version: Literal["paint-plan.v1"]
    generation_locale: GenerationLocale = "en-US"
    intent: Annotated[str, Field(min_length=1, max_length=1200)] | None = None
    regeneration_of_plan_id: UUID | None = None

    @model_validator(mode="after")
    def prompt_body_matches_hash(self) -> PaintPlanFixtureSource:
        if (
            hashlib.sha256(self.prompt_template_body.encode("utf-8")).hexdigest()
            != self.prompt_content_hash
        ):
            raise ValueError("prompt_template_body must match prompt_content_hash")
        return self


class PaintPlanModelChoiceRead(StrictModel):
    id: UUID
    model_id: str
    display_name: str
    execution_mode: ProviderExecutionMode
    currency: Literal["FIXTURE_CREDITS", "USD", "CNY"]
    supports_vision: bool
    supports_structured_output: bool


class PaintPlanProviderChoiceRead(StrictModel):
    id: UUID
    provider_key: Literal["fixture_local", "openai", "zhipu"]
    display_name: str
    execution_mode: ProviderExecutionMode
    models: list[PaintPlanModelChoiceRead]


class PaintPlanCredentialChoiceRead(StrictModel):
    id: UUID
    alias: str
    provider_key: Literal["fixture_local", "openai", "zhipu"]
    active_grant: bool
    status: str


class PaintPlanPreviewRead(StrictModel):
    admissible: bool
    execution_mode: ProviderExecutionMode
    provider_key: Literal["fixture_local", "openai", "zhipu"]
    model_id: str
    source_ready: bool
    estimated_cost_minor_units: int | None
    currency: Literal["FIXTURE_CREDITS", "USD", "CNY"]
    estimate_status: Literal["estimated", "unavailable"]
    live_execution_authorized: bool
    blockers: list[str]


class PaintPlanReviewEventRead(StrictModel):
    id: UUID
    action: Literal["submit", "approve", "reject"]
    reason: str | None
    actor_id: str
    actor_display_name_snapshot: str
    created_at: datetime


class PaintPlanRead(StrictModel):
    id: UUID
    lineage_id: UUID
    paint_project_id: UUID
    version: Annotated[int, Field(ge=1)]
    lineage_revision: Annotated[int, Field(ge=1)]
    parent_plan_id: UUID | None
    revision_kind: PlanRevisionKind
    lifecycle: PlanLifecycle
    effective_lifecycle: PlanLifecycle
    is_current: bool
    stale: bool
    stale_reasons: list[str]
    approval_valid: bool
    source_invocation_id: UUID
    source_attempt_id: UUID
    requested_by_user_id: UUID
    invocation_created_at: datetime
    source_image_set_fingerprint: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    source_image_assets: Annotated[
        list[PaintPlanImageAssetRead],
        Field(min_length=3, max_length=4),
    ]
    source_readiness_review_id: UUID
    source_readiness_review_version: Annotated[int, Field(ge=1)]
    source_region_set_id: UUID
    source_region_set_version: Annotated[int, Field(ge=1)]
    source_geometry_fingerprint: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    provider_definition_id: UUID
    provider_key: str
    provider_revision_snapshot: Annotated[int, Field(ge=1)]
    model_definition_id: UUID
    model_id: str
    model_revision_snapshot: Annotated[int, Field(ge=1)]
    provider_pricing_snapshot_id: UUID | None
    prompt_template_id: UUID
    prompt_template_key: Literal["paint-plan"]
    prompt_version: Annotated[int, Field(ge=1)]
    prompt_hash: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    generation_locale: GenerationLocale
    schema_version: Literal["paint-plan.v1"]
    content_hash: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    document: PaintPlanDocument
    retrieved_context: list[RetrievedContextUnit] = Field(default_factory=list)
    provider_request_id_status: Literal["absent", "provided", "unavailable"]
    provider_request_id: Annotated[str, Field(min_length=1, max_length=200)] | None
    usage_measurement_status: Literal["measured", "unavailable"]
    input_units: Annotated[int, Field(ge=0)] | None
    output_units: Annotated[int, Field(ge=0)] | None
    cost_measurement_status: Literal["estimated", "measured", "unavailable"]
    cost_minor_units: Annotated[int, Field(ge=0)] | None
    cost_currency: Literal["FIXTURE_CREDITS", "USD", "CNY"]
    latest_review: PaintPlanReviewEventRead | None
    allowed_actions: list[str]
    created_by_actor_type: Literal["provider", "user"]
    created_by_actor_id: str
    created_by_actor_display_name_snapshot: str
    created_at: datetime

    @model_validator(mode="after")
    def accounting_fields_are_consistent(self) -> PaintPlanRead:
        if (self.provider_request_id_status == "provided") != (
            self.provider_request_id is not None
        ):
            raise ValueError("provider request id status and value must agree")
        if self.usage_measurement_status == "measured":
            if self.input_units is None or self.output_units is None:
                raise ValueError("measured usage requires input and output units")
        elif self.input_units is not None or self.output_units is not None:
            raise ValueError("unavailable usage must not contain units")
        if (self.cost_measurement_status == "unavailable") != (self.cost_minor_units is None):
            raise ValueError("cost measurement status and amount must agree")
        return self


class PaintPlanHistoryResponse(StrictModel):
    items: list[PaintPlanRead]


class PaintPlanWorkbenchRead(StrictModel):
    paint_project_id: UUID
    access_role: Literal["owner", "reviewer"]
    image_set_status: str
    image_set_fingerprint: str | None
    readiness_review_id: UUID | None
    image_assets: list[PaintPlanImageAssetRead]
    region_set: PaintPlanRegionSetRead | None
    source_ready: bool
    blockers: list[str]
    providers: list[PaintPlanProviderChoiceRead]
    credentials: list[PaintPlanCredentialChoiceRead]
    current_plan: PaintPlanRead | None
    history: list[PaintPlanRead]
    allowed_actions: list[str]
