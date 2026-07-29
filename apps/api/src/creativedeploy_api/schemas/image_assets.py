"""Strict request and response schemas for private immutable ImageAssets."""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

ImageRole = Literal["primary_mvp_input"]
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
    """Complete current and immutable history for the one approved image role."""

    model_config = ConfigDict(extra="forbid", strict=True)

    items: list[ImageAssetRead]
