"""Immutable, owner-scoped ImageAsset persistence model."""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql.elements import conv

from creativedeploy_api.db.base import Base

IMAGE_ROLE_PRIMARY = "primary_mvp_input"
IMAGE_ROLES = (IMAGE_ROLE_PRIMARY,)
IMAGE_LIFECYCLE_STATUSES = ("current", "superseded")
IMAGE_STORAGE_PROVIDERS = ("local_filesystem",)
IMAGE_FORMATS = ("jpeg", "png", "webp")
IMAGE_UPLOAD_VALIDATION_RESULTS = ("accepted",)
IMAGE_SOURCE_TYPES = ("user_provided", "user_photographed", "user_provided_other")
IMAGE_RIGHTS_STATUSES = ("pending", "confirmed", "rejected")
IMAGE_INTENDED_USAGES = ("private_project", "portfolio_demo", "public_repository")


def _sql_values(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


class ImageAsset(Base):
    """One immutable original image; replacement creates another row."""

    __tablename__ = "image_assets"
    __table_args__ = (
        CheckConstraint(
            f"role IN ({_sql_values(IMAGE_ROLES)})",
            name=conv("ck_image_assets_role_allowed"),
        ),
        CheckConstraint(
            "version >= 1",
            name=conv("ck_image_assets_version_positive"),
        ),
        CheckConstraint(
            f"lifecycle_status IN ({_sql_values(IMAGE_LIFECYCLE_STATUSES)})",
            name=conv("ck_image_assets_lifecycle_status_allowed"),
        ),
        CheckConstraint(
            "(is_current AND lifecycle_status = 'current') "
            "OR (NOT is_current AND lifecycle_status = 'superseded')",
            name=conv("ck_image_assets_current_lifecycle_consistent"),
        ),
        CheckConstraint(
            f"storage_provider IN ({_sql_values(IMAGE_STORAGE_PROVIDERS)})",
            name=conv("ck_image_assets_storage_provider_allowed"),
        ),
        CheckConstraint(
            r"storage_key ~ '^objects/[0-9a-f]{2}/[0-9a-f]{32}\.(jpg|png|webp)$'",
            name=conv("ck_image_assets_storage_key_format"),
        ),
        CheckConstraint(
            "length(original_filename) >= 1 "
            "AND original_filename = btrim(original_filename) "
            "AND original_filename !~ '[\\\\/]' "
            "AND original_filename !~ '[[:cntrl:]]'",
            name=conv("ck_image_assets_original_filename_safe"),
        ),
        CheckConstraint(
            f"detected_format IN ({_sql_values(IMAGE_FORMATS)})",
            name=conv("ck_image_assets_detected_format_allowed"),
        ),
        CheckConstraint(
            "(detected_format = 'jpeg' AND declared_content_type = 'image/jpeg') "
            "OR (detected_format = 'png' AND declared_content_type = 'image/png') "
            "OR (detected_format = 'webp' AND declared_content_type = 'image/webp')",
            name=conv("ck_image_assets_declared_type_matches_format"),
        ),
        CheckConstraint(
            "byte_size BETWEEN 1 AND 20971520",
            name=conv("ck_image_assets_byte_size_allowed"),
        ),
        CheckConstraint(
            "width BETWEEN 768 AND 8192 AND height BETWEEN 768 AND 8192",
            name=conv("ck_image_assets_dimensions_allowed"),
        ),
        CheckConstraint(
            "pixel_count = width * height AND pixel_count <= 40000000",
            name=conv("ck_image_assets_pixel_count_allowed"),
        ),
        CheckConstraint(
            "exif_orientation IS NULL OR exif_orientation BETWEEN 1 AND 8",
            name=conv("ck_image_assets_exif_orientation_allowed"),
        ),
        CheckConstraint(
            "sha256 ~ '^[0-9a-f]{64}$'",
            name=conv("ck_image_assets_sha256_format"),
        ),
        CheckConstraint(
            f"upload_validation_result IN ({_sql_values(IMAGE_UPLOAD_VALIDATION_RESULTS)})",
            name=conv("ck_image_assets_upload_validation_result_allowed"),
        ),
        CheckConstraint(
            "jsonb_typeof(upload_validation_details) = 'object'",
            name=conv("ck_image_assets_upload_validation_details_is_object"),
        ),
        CheckConstraint(
            f"source_type IN ({_sql_values(IMAGE_SOURCE_TYPES)})",
            name=conv("ck_image_assets_source_type_allowed"),
        ),
        CheckConstraint(
            f"rights_attestation_status IN ({_sql_values(IMAGE_RIGHTS_STATUSES)})",
            name=conv("ck_image_assets_rights_status_allowed"),
        ),
        CheckConstraint(
            "rights_attestation_version >= 1",
            name=conv("ck_image_assets_rights_version_positive"),
        ),
        CheckConstraint(
            "jsonb_typeof(intended_usage) = 'array' "
            "AND jsonb_array_length(intended_usage) >= 1 "
            "AND intended_usage <@ "
            """'["private_project","portfolio_demo","public_repository"]'::jsonb""",
            name=conv("ck_image_assets_intended_usage_allowed"),
        ),
        CheckConstraint(
            "rights_attestation_status = 'pending' "
            "OR (rights_attested_by_principal_id IS NOT NULL "
            "AND rights_attested_at IS NOT NULL)",
            name=conv("ck_image_assets_rights_actor_required"),
        ),
        CheckConstraint(
            "created_by_actor_type = 'user'",
            name=conv("ck_image_assets_created_by_actor_type_allowed"),
        ),
        CheckConstraint(
            "length(created_by_actor_id) >= 1 AND created_by_actor_id = btrim(created_by_actor_id)",
            name=conv("ck_image_assets_created_by_actor_id_normalized"),
        ),
        CheckConstraint(
            "length(created_by_actor_display_name_snapshot) >= 1 "
            "AND created_by_actor_display_name_snapshot = "
            "btrim(created_by_actor_display_name_snapshot)",
            name=conv("ck_image_assets_created_by_display_normalized"),
        ),
        ForeignKeyConstraint(
            ["paint_project_id", "owner_principal_id"],
            ["paint_projects.id", "paint_projects.owner_principal_id"],
            name="fk_image_assets_project_owner_paint_projects",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            [
                "supersedes_image_asset_id",
                "paint_project_id",
                "owner_principal_id",
                "role",
            ],
            [
                "image_assets.id",
                "image_assets.paint_project_id",
                "image_assets.owner_principal_id",
                "image_assets.role",
            ],
            name="fk_image_assets_supersedes_same_owner_project_role",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "paint_project_id",
            "owner_principal_id",
            "id",
            name="uq_image_assets_project_owner_id",
        ),
        UniqueConstraint(
            "id",
            "paint_project_id",
            "owner_principal_id",
            "role",
            name="uq_image_assets_id_project_owner_role",
        ),
        UniqueConstraint(
            "paint_project_id",
            "role",
            "version",
            name="uq_image_assets_project_role_version",
        ),
        UniqueConstraint(
            "storage_key",
            name="uq_image_assets_storage_key",
        ),
        Index(
            "uq_image_assets_project_role_current",
            "paint_project_id",
            "role",
            unique=True,
            postgresql_where=text("is_current"),
        ),
        Index(
            "ix_image_assets_owner_project_created_at",
            "owner_principal_id",
            "paint_project_id",
            "created_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    paint_project_id: Mapped[uuid.UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        nullable=False,
    )
    owner_principal_id: Mapped[str] = mapped_column(String(128), nullable=False)
    role: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    supersedes_image_asset_id: Mapped[uuid.UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        nullable=True,
    )
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False)
    lifecycle_status: Mapped[str] = mapped_column(String(32), nullable=False)
    storage_provider: Mapped[str] = mapped_column(String(32), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(128), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    declared_content_type: Mapped[str] = mapped_column(String(64), nullable=False)
    detected_format: Mapped[str] = mapped_column(String(16), nullable=False)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    pixel_count: Mapped[int] = mapped_column(Integer, nullable=False)
    color_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    has_alpha: Mapped[bool] = mapped_column(Boolean, nullable=False)
    exif_orientation: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    upload_validation_result: Mapped[str] = mapped_column(String(64), nullable=False)
    upload_validation_details: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        nullable=False,
    )
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    rights_attestation_status: Mapped[str] = mapped_column(String(32), nullable=False)
    rights_attestation_version: Mapped[int] = mapped_column(Integer, nullable=False)
    intended_usage: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    rights_attested_by_principal_id: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )
    rights_attested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_by_actor_type: Mapped[str] = mapped_column(String(32), nullable=False)
    created_by_actor_id: Mapped[str] = mapped_column(String(128), nullable=False)
    created_by_actor_display_name_snapshot: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
