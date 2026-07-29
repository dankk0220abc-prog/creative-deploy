"""add ImageAsset foundation

Revision ID: 5ed9906e7d33
Revises: a10d3d8dab38
Create Date: 2026-07-29 00:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "5ed9906e7d33"
down_revision: str | Sequence[str] | None = "a10d3d8dab38"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create immutable private image assets and the current primary-image reference."""
    op.create_unique_constraint(
        "uq_paint_projects_id_owner_principal_id",
        "paint_projects",
        ["id", "owner_principal_id"],
    )
    op.create_table(
        "image_assets",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("paint_project_id", sa.UUID(), nullable=False),
        sa.Column("owner_principal_id", sa.String(length=128), nullable=False),
        sa.Column("role", sa.String(length=64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("supersedes_image_asset_id", sa.UUID(), nullable=True),
        sa.Column("is_current", sa.Boolean(), nullable=False),
        sa.Column("lifecycle_status", sa.String(length=32), nullable=False),
        sa.Column("storage_provider", sa.String(length=32), nullable=False),
        sa.Column("storage_key", sa.String(length=128), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("declared_content_type", sa.String(length=64), nullable=False),
        sa.Column("detected_format", sa.String(length=16), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("pixel_count", sa.Integer(), nullable=False),
        sa.Column("color_mode", sa.String(length=32), nullable=False),
        sa.Column("has_alpha", sa.Boolean(), nullable=False),
        sa.Column("exif_orientation", sa.Integer(), nullable=True),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("upload_validation_result", sa.String(length=64), nullable=False),
        sa.Column(
            "upload_validation_details",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("rights_attestation_status", sa.String(length=32), nullable=False),
        sa.Column("rights_attestation_version", sa.Integer(), nullable=False),
        sa.Column(
            "intended_usage",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("rights_attested_by_principal_id", sa.String(length=128), nullable=True),
        sa.Column("rights_attested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_actor_type", sa.String(length=32), nullable=False),
        sa.Column("created_by_actor_id", sa.String(length=128), nullable=False),
        sa.Column(
            "created_by_actor_display_name_snapshot",
            sa.String(length=200),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "role IN ('primary_mvp_input')",
            name=op.f("ck_image_assets_role_allowed"),
        ),
        sa.CheckConstraint(
            "version >= 1",
            name=op.f("ck_image_assets_version_positive"),
        ),
        sa.CheckConstraint(
            "lifecycle_status IN ('current', 'superseded')",
            name=op.f("ck_image_assets_lifecycle_status_allowed"),
        ),
        sa.CheckConstraint(
            "(is_current AND lifecycle_status = 'current') "
            "OR (NOT is_current AND lifecycle_status = 'superseded')",
            name=op.f("ck_image_assets_current_lifecycle_consistent"),
        ),
        sa.CheckConstraint(
            "storage_provider IN ('local_filesystem')",
            name=op.f("ck_image_assets_storage_provider_allowed"),
        ),
        sa.CheckConstraint(
            r"storage_key ~ '^objects/[0-9a-f]{2}/[0-9a-f]{32}\.(jpg|png|webp)$'",
            name=op.f("ck_image_assets_storage_key_format"),
        ),
        sa.CheckConstraint(
            "length(original_filename) >= 1 "
            "AND original_filename = btrim(original_filename) "
            "AND original_filename !~ '[\\\\/]' "
            "AND original_filename !~ '[[:cntrl:]]'",
            name=op.f("ck_image_assets_original_filename_safe"),
        ),
        sa.CheckConstraint(
            "detected_format IN ('jpeg', 'png', 'webp')",
            name=op.f("ck_image_assets_detected_format_allowed"),
        ),
        sa.CheckConstraint(
            "(detected_format = 'jpeg' AND declared_content_type = 'image/jpeg') "
            "OR (detected_format = 'png' AND declared_content_type = 'image/png') "
            "OR (detected_format = 'webp' AND declared_content_type = 'image/webp')",
            name=op.f("ck_image_assets_declared_type_matches_format"),
        ),
        sa.CheckConstraint(
            "byte_size BETWEEN 1 AND 20971520",
            name=op.f("ck_image_assets_byte_size_allowed"),
        ),
        sa.CheckConstraint(
            "width BETWEEN 768 AND 8192 AND height BETWEEN 768 AND 8192",
            name=op.f("ck_image_assets_dimensions_allowed"),
        ),
        sa.CheckConstraint(
            "pixel_count = width * height AND pixel_count <= 40000000",
            name=op.f("ck_image_assets_pixel_count_allowed"),
        ),
        sa.CheckConstraint(
            "exif_orientation IS NULL OR exif_orientation BETWEEN 1 AND 8",
            name=op.f("ck_image_assets_exif_orientation_allowed"),
        ),
        sa.CheckConstraint(
            "sha256 ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_image_assets_sha256_format"),
        ),
        sa.CheckConstraint(
            "upload_validation_result IN ('accepted')",
            name=op.f("ck_image_assets_upload_validation_result_allowed"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(upload_validation_details) = 'object'",
            name=op.f("ck_image_assets_upload_validation_details_is_object"),
        ),
        sa.CheckConstraint(
            "source_type IN ('user_provided', 'user_photographed', 'user_provided_other')",
            name=op.f("ck_image_assets_source_type_allowed"),
        ),
        sa.CheckConstraint(
            "rights_attestation_status IN ('pending', 'confirmed', 'rejected')",
            name=op.f("ck_image_assets_rights_status_allowed"),
        ),
        sa.CheckConstraint(
            "rights_attestation_version >= 1",
            name=op.f("ck_image_assets_rights_version_positive"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(intended_usage) = 'array' "
            "AND jsonb_array_length(intended_usage) >= 1 "
            "AND intended_usage <@ "
            """'["private_project","portfolio_demo","public_repository"]'::jsonb""",
            name=op.f("ck_image_assets_intended_usage_allowed"),
        ),
        sa.CheckConstraint(
            "rights_attestation_status = 'pending' "
            "OR (rights_attested_by_principal_id IS NOT NULL "
            "AND rights_attested_at IS NOT NULL)",
            name=op.f("ck_image_assets_rights_actor_required"),
        ),
        sa.CheckConstraint(
            "created_by_actor_type = 'user'",
            name=op.f("ck_image_assets_created_by_actor_type_allowed"),
        ),
        sa.CheckConstraint(
            "length(created_by_actor_id) >= 1 AND created_by_actor_id = btrim(created_by_actor_id)",
            name=op.f("ck_image_assets_created_by_actor_id_normalized"),
        ),
        sa.CheckConstraint(
            "length(created_by_actor_display_name_snapshot) >= 1 "
            "AND created_by_actor_display_name_snapshot = "
            "btrim(created_by_actor_display_name_snapshot)",
            name=op.f("ck_image_assets_created_by_display_normalized"),
        ),
        sa.ForeignKeyConstraint(
            ["paint_project_id", "owner_principal_id"],
            ["paint_projects.id", "paint_projects.owner_principal_id"],
            name="fk_image_assets_project_owner_paint_projects",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_image_assets")),
        sa.UniqueConstraint(
            "paint_project_id",
            "owner_principal_id",
            "id",
            name="uq_image_assets_project_owner_id",
        ),
        sa.UniqueConstraint(
            "id",
            "paint_project_id",
            "owner_principal_id",
            "role",
            name="uq_image_assets_id_project_owner_role",
        ),
        sa.UniqueConstraint(
            "paint_project_id",
            "role",
            "version",
            name="uq_image_assets_project_role_version",
        ),
        sa.UniqueConstraint("storage_key", name="uq_image_assets_storage_key"),
    )
    op.create_index(
        "uq_image_assets_project_role_current",
        "image_assets",
        ["paint_project_id", "role"],
        unique=True,
        postgresql_where=sa.text("is_current"),
    )
    op.create_index(
        "ix_image_assets_owner_project_created_at",
        "image_assets",
        ["owner_principal_id", "paint_project_id", "created_at"],
        unique=False,
    )
    op.add_column(
        "paint_projects",
        sa.Column("current_image_asset_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_paint_projects_current_image_asset_same_owner_project",
        "paint_projects",
        "image_assets",
        ["id", "owner_principal_id", "current_image_asset_id"],
        ["paint_project_id", "owner_principal_id", "id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    """Remove only the Phase 1E-1 ImageAsset foundation."""
    op.drop_constraint(
        "fk_paint_projects_current_image_asset_same_owner_project",
        "paint_projects",
        type_="foreignkey",
    )
    op.drop_column("paint_projects", "current_image_asset_id")
    op.drop_index("ix_image_assets_owner_project_created_at", table_name="image_assets")
    op.drop_index("uq_image_assets_project_role_current", table_name="image_assets")
    op.drop_table("image_assets")
    op.drop_constraint(
        "uq_paint_projects_id_owner_principal_id",
        "paint_projects",
        type_="unique",
    )
