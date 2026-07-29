"""Strict request and response schemas for private immutable ImageAssets."""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ImageRole = Literal[
    "primary_front",
    "reference_back",
    "reference_angle",
    "reference_detail",
]
ImageSourceType = Literal[
    "user_provided",
    "user_photographed",
    "user_provided_other",
]
ImageIntendedUsage = Literal[
    "private_project",
    "portfolio_demo",
    "public_repository",
]


class CreateImageAssetRequest(BaseModel):
    """The controlled non-file fields accepted from one multipart upload."""

    model_config = ConfigDict(extra="forbid", strict=True)

    role: ImageRole
    source_type: ImageSourceType
    intended_usage: Annotated[list[ImageIntendedUsage], Field(min_length=1, max_length=3)]
    rights_attestation_confirmed: Literal[True]
    rights_attestation_version: Literal[1]

    @field_validator("intended_usage")
    @classmethod
    def require_unique_usage(
        cls,
        value: list[ImageIntendedUsage],
    ) -> list[ImageIntendedUsage]:
        """Reject duplicate declarations and canonicalize their order."""
        if len(value) != len(set(value)):
            raise ValueError("intended usages must be unique")
        return sorted(value)


class ImageAssetRead(BaseModel):
    """Owner-scoped metadata that never exposes the private storage key or path."""

    model_config = ConfigDict(extra="forbid", strict=True)

    id: UUID
    paint_project_id: UUID
    role: ImageRole
    version: Annotated[int, Field(ge=1)]
    supersedes_image_asset_id: UUID | None
    is_current: bool
    lifecycle_status: Literal["current", "superseded"]
    original_filename: Annotated[str, Field(min_length=1, max_length=255)]
    declared_content_type: Literal["image/jpeg", "image/png", "image/webp"]
    detected_format: Literal["jpeg", "png", "webp"]
    byte_size: Annotated[int, Field(ge=1, le=20 * 1024 * 1024)]
    width: Annotated[int, Field(ge=1)]
    height: Annotated[int, Field(ge=1)]
    pixel_count: Annotated[int, Field(ge=1)]
    color_mode: Annotated[str, Field(min_length=1, max_length=32)]
    has_alpha: bool
    exif_orientation: Annotated[int, Field(ge=1, le=8)] | None
    sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    upload_validation_result: Literal["accepted"]
    upload_validation_details: dict[str, object]
    source_type: ImageSourceType
    rights_attestation_status: Literal["pending", "confirmed", "rejected"]
    rights_attestation_version: Annotated[int, Field(ge=1)]
    intended_usage: list[ImageIntendedUsage]
    rights_attested_at: datetime | None
    created_at: datetime
    content_url: str

    @field_validator("created_at", "rights_attested_at")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        """Require timezone-aware audit timestamps."""
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("timestamp must include a timezone")
        return value


class ImageAssetListResponse(BaseModel):
    """Complete current and immutable history for all approved image roles."""

    model_config = ConfigDict(extra="forbid", strict=True)

    items: list[ImageAssetRead]


ReadinessVerdict = Literal["ready", "not_ready"]
ImageSetStatus = Literal["incomplete", "ready", "stale", "not_ready"]


class CreateReadinessReviewRequest(BaseModel):
    """The only client-owned facts accepted for a human readiness verdict."""

    model_config = ConfigDict(extra="forbid", strict=True)

    verdict: ReadinessVerdict
    reason: Annotated[str, Field(min_length=1, max_length=1000)] | None = None

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str | None) -> str | None:
        """Normalize optional human text without accepting whitespace-only reasons."""
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("reason must not be blank")
        return normalized

    @model_validator(mode="after")
    def require_not_ready_reason(self) -> "CreateReadinessReviewRequest":
        """A negative human verdict must explain why it was selected."""
        if self.verdict == "not_ready" and self.reason is None:
            raise ValueError("not_ready requires a reason")
        return self


class ImageSetReadinessReviewRead(BaseModel):
    """One immutable human verdict and its exact server-owned asset snapshot."""

    model_config = ConfigDict(extra="forbid", strict=True)

    id: UUID
    paint_project_id: UUID
    version: Annotated[int, Field(ge=1)]
    verdict: ReadinessVerdict
    reason: Annotated[str, Field(min_length=1, max_length=1000)] | None
    primary_front_image_asset_id: UUID | None
    reference_back_image_asset_id: UUID | None
    reference_angle_image_asset_id: UUID | None
    reference_detail_image_asset_id: UUID | None
    image_set_fingerprint: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    actor_type: Literal["user"]
    actor_id: Annotated[str, Field(min_length=1, max_length=128)]
    actor_display_name_snapshot: Annotated[str, Field(min_length=1, max_length=200)]
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def require_review_timezone(cls, value: datetime) -> datetime:
        """Require a timezone-aware append-only review timestamp."""
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must include a timezone")
        return value


class ImageRoleSlotRead(BaseModel):
    """One formal role with current metadata, retained history, and object state."""

    model_config = ConfigDict(extra="forbid", strict=True)

    role: ImageRole
    required: bool
    missing: bool
    object_available: bool
    current: ImageAssetRead | None
    history: list[ImageAssetRead]


class ImageSetReadinessChecklist(BaseModel):
    """Deterministic non-AI facts used before a human READY decision."""

    model_config = ConfigDict(extra="forbid", strict=True)

    required_roles_present: bool
    deterministic_validation_accepted: bool
    rights_complete: bool
    content_distinct: bool
    objects_available: bool
    snapshot_current: bool
    can_mark_ready: bool
    blockers: list[str]


class ImageSetRead(BaseModel):
    """The owner-scoped current ImageSet, readiness facts, and latest review."""

    model_config = ConfigDict(extra="forbid", strict=True)

    paint_project_id: UUID
    image_set_fingerprint: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    roles: list[ImageRoleSlotRead]
    checklist: ImageSetReadinessChecklist
    latest_review: ImageSetReadinessReviewRead | None
    status: ImageSetStatus
    stale_reasons: list[str]


class ReadinessReviewHistoryResponse(BaseModel):
    """Newest-first immutable readiness review history."""

    model_config = ConfigDict(extra="forbid", strict=True)

    items: list[ImageSetReadinessReviewRead]
