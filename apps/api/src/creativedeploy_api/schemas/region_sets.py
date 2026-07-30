"""Strict Phase 1F request and response schemas."""

import unicodedata
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from creativedeploy_api.db.models.region_set import (
    MAX_REGIONS_PER_SET,
    MAX_VERTICES_PER_REGION,
    MAX_VERTICES_PER_SET,
    PPM_MAX,
)

RegionKind = Literal["paint", "exclude"]
StoredRegionSetLifecycle = Literal[
    "draft",
    "submitted",
    "approved",
    "changes_requested",
    "superseded",
]
RegionReviewVerdict = Literal["approved", "changes_requested"]
RequestUUID = Annotated[
    UUID,
    BeforeValidator(lambda value: UUID(value) if isinstance(value, str) else value),
]


def _contains_control(value: str) -> bool:
    return any(unicodedata.category(character) == "Cc" for character in value)


def _normalize_human_text(
    value: str,
    *,
    field_name: str,
    forbid_html: bool,
) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be blank")
    if _contains_control(normalized):
        raise ValueError(f"{field_name} must not contain control characters")
    if forbid_html and ("<" in normalized or ">" in normalized):
        raise ValueError(f"{field_name} must not contain HTML")
    return normalized


class RegionVertexInput(BaseModel):
    """One normalized integer coordinate supplied by the human editor."""

    model_config = ConfigDict(extra="forbid", strict=True)

    x_ppm: Annotated[int, Field(ge=0, le=PPM_MAX)]
    y_ppm: Annotated[int, Field(ge=0, le=PPM_MAX)]


class RegionDraftInput(BaseModel):
    """One human-labelled simple Polygon in an unsaved draft."""

    model_config = ConfigDict(extra="forbid", strict=True)

    stable_region_key: RequestUUID
    kind: RegionKind
    label: Annotated[str, Field(min_length=1, max_length=80)]
    z_index: Annotated[int, Field(ge=0, le=127)]
    opacity_ppm: Annotated[int, Field(ge=100_000, le=PPM_MAX)] = 500_000
    notes: Annotated[str, Field(min_length=1, max_length=1000)] | None = None
    vertices: Annotated[
        list[RegionVertexInput],
        Field(min_length=3, max_length=MAX_VERTICES_PER_REGION),
    ]

    @field_validator("label")
    @classmethod
    def normalize_label(cls, value: str) -> str:
        return _normalize_human_text(value, field_name="label", forbid_html=True)

    @field_validator("notes")
    @classmethod
    def normalize_notes(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _normalize_human_text(value, field_name="notes", forbid_html=True)


class SaveRegionSetRequest(BaseModel):
    """Save a new immutable draft from an exact optimistic base."""

    model_config = ConfigDict(extra="forbid", strict=True)

    base_region_set_id: RequestUUID | None = None
    base_version: Annotated[int, Field(ge=1)] | None = None
    regions: Annotated[list[RegionDraftInput], Field(max_length=MAX_REGIONS_PER_SET)]

    @model_validator(mode="after")
    def validate_snapshot_budget_and_base(self) -> "SaveRegionSetRequest":
        if (self.base_region_set_id is None) != (self.base_version is None):
            raise ValueError("base_region_set_id and base_version must be provided together")
        stable_keys = [region.stable_region_key for region in self.regions]
        if len(stable_keys) != len(set(stable_keys)):
            raise ValueError("stable_region_key must be unique within a snapshot")
        z_indices = [region.z_index for region in self.regions]
        if len(z_indices) != len(set(z_indices)):
            raise ValueError("z_index must be unique within a snapshot")
        if sum(len(region.vertices) for region in self.regions) > MAX_VERTICES_PER_SET:
            raise ValueError("total vertex budget exceeded")
        return self


class ForkRegionSetDraftRequest(BaseModel):
    """Fork an exact immutable source against an expected current snapshot."""

    model_config = ConfigDict(extra="forbid", strict=True)

    expected_current_region_set_id: RequestUUID
    expected_current_version: Annotated[int, Field(ge=1)]


class SubmitRegionSetRequest(BaseModel):
    """An intentionally empty, strict submit command body."""

    model_config = ConfigDict(extra="forbid", strict=True)


class CreateRegionSetReviewRequest(BaseModel):
    """The human-owned fields accepted for one append-only review."""

    model_config = ConfigDict(extra="forbid", strict=True)

    verdict: RegionReviewVerdict
    reason: Annotated[str, Field(min_length=1, max_length=1000)] | None = None

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _normalize_human_text(value, field_name="reason", forbid_html=False)

    @model_validator(mode="after")
    def require_changes_reason(self) -> "CreateRegionSetReviewRequest":
        if self.verdict == "changes_requested" and self.reason is None:
            raise ValueError("changes_requested requires a reason")
        return self


class RegionVertexRead(BaseModel):
    """One persisted sequenced ppm vertex."""

    model_config = ConfigDict(extra="forbid", strict=True)

    sequence: Annotated[int, Field(ge=0, le=MAX_VERTICES_PER_REGION - 1)]
    x_ppm: Annotated[int, Field(ge=0, le=PPM_MAX)]
    y_ppm: Annotated[int, Field(ge=0, le=PPM_MAX)]


class RegionRead(BaseModel):
    """One persisted human Region and deterministic geometry summary."""

    model_config = ConfigDict(extra="forbid", strict=True)

    id: UUID
    stable_region_key: UUID
    kind: RegionKind
    label: Annotated[str, Field(min_length=1, max_length=80)]
    normalized_label: Annotated[str, Field(min_length=1, max_length=80)]
    z_index: Annotated[int, Field(ge=0, le=127)]
    opacity_ppm: Annotated[int, Field(ge=100_000, le=PPM_MAX)]
    notes: Annotated[str, Field(min_length=1, max_length=1000)] | None
    vertex_count: Annotated[int, Field(ge=3, le=MAX_VERTICES_PER_REGION)]
    area_twice_ppm_squared: Annotated[int, Field(gt=0)]
    bbox_min_x_ppm: Annotated[int, Field(ge=0, le=PPM_MAX)]
    bbox_min_y_ppm: Annotated[int, Field(ge=0, le=PPM_MAX)]
    bbox_max_x_ppm: Annotated[int, Field(ge=0, le=PPM_MAX)]
    bbox_max_y_ppm: Annotated[int, Field(ge=0, le=PPM_MAX)]
    vertices: list[RegionVertexRead]


class RegionSetReviewRead(BaseModel):
    """One append-only human decision against an exact submitted snapshot."""

    model_config = ConfigDict(extra="forbid", strict=True)

    id: UUID
    paint_project_id: UUID
    region_set_id: UUID
    version: Annotated[int, Field(ge=1)]
    verdict: RegionReviewVerdict
    reason: Annotated[str, Field(min_length=1, max_length=1000)] | None
    actor_type: Literal["user"]
    actor_id: Annotated[str, Field(min_length=1, max_length=128)]
    actor_display_name_snapshot: Annotated[str, Field(min_length=1, max_length=200)]
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must include a timezone")
        return value


class RegionSetHistoryItem(BaseModel):
    """Compact immutable history information for one RegionSet."""

    model_config = ConfigDict(extra="forbid", strict=True)

    id: UUID
    paint_project_id: UUID
    version: Annotated[int, Field(ge=1)]
    lifecycle: StoredRegionSetLifecycle
    effective_lifecycle: StoredRegionSetLifecycle
    source_primary_image_asset_id: UUID
    source_image_set_fingerprint: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    region_count: Annotated[int, Field(ge=0, le=MAX_REGIONS_PER_SET)]
    total_vertex_count: Annotated[int, Field(ge=0, le=MAX_VERTICES_PER_SET)]
    geometry_fingerprint: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    stale: bool
    stale_reasons: list[str]
    is_current: bool
    latest_review: RegionSetReviewRead | None
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def require_history_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must include a timezone")
        return value


class RegionSetRead(RegionSetHistoryItem):
    """Complete owner-scoped RegionSet detail without storage internals."""

    source_image_width: Annotated[int, Field(ge=1, le=8192)]
    source_image_height: Annotated[int, Field(ge=1, le=8192)]
    source_content_url: str
    supersedes_region_set_id: UUID | None
    based_on_region_set_id: UUID | None
    overlap_warnings: list[str]
    regions: list[RegionRead]


class RegionSetHistoryResponse(BaseModel):
    """Newest-first immutable RegionSet history."""

    model_config = ConfigDict(extra="forbid", strict=True)

    items: list[RegionSetHistoryItem]


class RegionSetReviewHistoryResponse(BaseModel):
    """Newest-first append-only review history for one RegionSet."""

    model_config = ConfigDict(extra="forbid", strict=True)

    items: list[RegionSetReviewRead]


class RegionWorkbenchRead(BaseModel):
    """Bootstrap facts for the human Region Annotation Workspace."""

    model_config = ConfigDict(extra="forbid", strict=True)

    paint_project_id: UUID
    image_set_status: Literal["incomplete", "ready", "stale", "not_ready"]
    current_image_set_fingerprint: Annotated[
        str,
        Field(pattern=r"^[0-9a-f]{64}$"),
    ]
    source_primary_image_asset_id: UUID | None
    source_image_width: Annotated[int, Field(ge=1, le=8192)] | None
    source_image_height: Annotated[int, Field(ge=1, le=8192)] | None
    source_content_url: str | None
    can_create_draft: bool
    current_region_set: RegionSetRead | None
    history: list[RegionSetHistoryItem]
