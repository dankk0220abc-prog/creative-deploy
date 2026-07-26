"""Strict request and response schemas for the PaintProject API."""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

WorkflowStatus = Literal[
    "DRAFT",
    "IMAGE_UPLOADED",
    "IMAGE_REVIEW_REQUIRED",
    "IMAGE_VALIDATION_FAILED",
    "IMAGE_VALIDATED",
    "REGION_ANALYSIS_RUNNING",
    "REGION_REVIEW_REQUIRED",
    "REGIONS_CONFIRMED",
    "PLAN_GENERATION_RUNNING",
    "PLAN_REVIEW_REQUIRED",
    "PLAN_APPROVED",
    "COMPLETED",
    "BLOCKED_LOW_CONFIDENCE",
    "FAILED_RETRYABLE",
    "FAILED_FINAL",
    "ABANDONED",
]


class CreatePaintProjectRequest(BaseModel):
    """The only client-owned fields accepted by Create Paint Project."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        str_strip_whitespace=True,
    )

    title: Annotated[str, Field(min_length=1, max_length=80)]
    description: Annotated[str, Field(max_length=500)] | None = None

    @field_validator("description", mode="before")
    @classmethod
    def normalize_empty_description(cls, value: object) -> object:
        """Normalize an empty or whitespace-only description to null."""
        if isinstance(value, str) and not value.strip():
            return None
        return value


class PaintProjectRead(BaseModel):
    """The frozen Phase 1D nine-field physical read contract."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        from_attributes=True,
    )

    id: UUID
    owner_principal_id: Annotated[str, Field(min_length=1, max_length=128)]
    title: Annotated[str, Field(min_length=1, max_length=80)]
    description: Annotated[str, Field(min_length=1, max_length=500)] | None
    requested_target_style: Literal["cel_shading"]
    planning_mode: Literal["planning_only_demo"]
    status: WorkflowStatus
    created_at: datetime
    updated_at: datetime

    @field_validator("owner_principal_id", "title", "description")
    @classmethod
    def require_normalized_text(cls, value: str | None) -> str | None:
        """Reject a replay snapshot that violates stored normalization."""
        if value is not None and value != value.strip():
            raise ValueError("value must be normalized")
        return value

    @field_validator("created_at", "updated_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        """Require the timezone-aware timestamp contract."""
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must include a timezone")
        return value

    @model_validator(mode="after")
    def require_timestamp_order(self) -> "PaintProjectRead":
        """Mirror the database ordering invariant in stored replay validation."""
        if self.updated_at < self.created_at:
            raise ValueError("updated_at must not precede created_at")
        return self


class PaintProjectListResponse(BaseModel):
    """Stable owner-scoped pagination envelope."""

    model_config = ConfigDict(extra="forbid", strict=True)

    items: list[PaintProjectRead]
    total: Annotated[int, Field(ge=0)]
    limit: Annotated[int, Field(ge=1, le=100)]
    offset: Annotated[int, Field(ge=0)]
