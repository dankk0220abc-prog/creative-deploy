"""add multi-role ImageSet readiness

Revision ID: d4c8a1f7b2e9
Revises: 5ed9906e7d33
Create Date: 2026-07-29 00:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d4c8a1f7b2e9"
down_revision: str | Sequence[str] | None = "5ed9906e7d33"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Map the sealed primary role and add append-only readiness snapshots."""
    op.drop_constraint(
        "fk_image_assets_supersedes_same_owner_project_role",
        "image_assets",
        type_="foreignkey",
    )
    op.drop_constraint(
        op.f("ck_image_assets_role_allowed"),
        "image_assets",
        type_="check",
    )
    op.execute("UPDATE image_assets SET role = 'primary_front' WHERE role = 'primary_mvp_input'")
    op.create_check_constraint(
        op.f("ck_image_assets_role_allowed"),
        "image_assets",
        "role IN ('primary_front', 'reference_back', 'reference_angle', 'reference_detail')",
    )
    op.create_foreign_key(
        "fk_image_assets_supersedes_same_owner_project_role",
        "image_assets",
        "image_assets",
        [
            "supersedes_image_asset_id",
            "paint_project_id",
            "owner_principal_id",
            "role",
        ],
        ["id", "paint_project_id", "owner_principal_id", "role"],
        ondelete="RESTRICT",
    )

    op.create_table(
        "image_set_readiness_reviews",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("owner_principal_id", sa.String(length=128), nullable=False),
        sa.Column("paint_project_id", sa.UUID(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("verdict", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.String(length=1000), nullable=True),
        sa.Column("primary_front_image_asset_id", sa.UUID(), nullable=True),
        sa.Column("primary_front_role", sa.String(length=64), nullable=True),
        sa.Column("reference_back_image_asset_id", sa.UUID(), nullable=True),
        sa.Column("reference_back_role", sa.String(length=64), nullable=True),
        sa.Column("reference_angle_image_asset_id", sa.UUID(), nullable=True),
        sa.Column("reference_angle_role", sa.String(length=64), nullable=True),
        sa.Column("reference_detail_image_asset_id", sa.UUID(), nullable=True),
        sa.Column("reference_detail_role", sa.String(length=64), nullable=True),
        sa.Column("image_set_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("actor_type", sa.String(length=32), nullable=False),
        sa.Column("actor_id", sa.String(length=128), nullable=False),
        sa.Column(
            "actor_display_name_snapshot",
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
            "version >= 1",
            name=op.f("ck_image_set_readiness_reviews_version_positive"),
        ),
        sa.CheckConstraint(
            "verdict IN ('ready', 'not_ready')",
            name=op.f("ck_image_set_readiness_reviews_verdict_allowed"),
        ),
        sa.CheckConstraint(
            "reason IS NULL OR (length(reason) BETWEEN 1 AND 1000 AND reason = btrim(reason))",
            name=op.f("ck_image_set_readiness_reviews_reason_normalized"),
        ),
        sa.CheckConstraint(
            "verdict <> 'not_ready' OR reason IS NOT NULL",
            name=op.f("ck_image_set_readiness_reviews_not_ready_reason_required"),
        ),
        sa.CheckConstraint(
            "verdict <> 'ready' OR "
            "(primary_front_image_asset_id IS NOT NULL "
            "AND reference_back_image_asset_id IS NOT NULL "
            "AND reference_angle_image_asset_id IS NOT NULL)",
            name=op.f("ck_image_set_readiness_reviews_ready_required_assets"),
        ),
        sa.CheckConstraint(
            "image_set_fingerprint ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_image_set_readiness_reviews_fingerprint_format"),
        ),
        sa.CheckConstraint(
            "actor_type = 'user'",
            name=op.f("ck_image_set_readiness_reviews_actor_type_allowed"),
        ),
        sa.CheckConstraint(
            "length(actor_id) >= 1 AND actor_id = btrim(actor_id)",
            name=op.f("ck_image_set_readiness_reviews_actor_id_normalized"),
        ),
        sa.CheckConstraint(
            "length(actor_display_name_snapshot) >= 1 "
            "AND actor_display_name_snapshot = btrim(actor_display_name_snapshot)",
            name=op.f("ck_image_set_readiness_reviews_actor_display_normalized"),
        ),
        sa.CheckConstraint(
            "(primary_front_image_asset_id IS NULL AND primary_front_role IS NULL) "
            "OR (primary_front_image_asset_id IS NOT NULL "
            "AND primary_front_role = 'primary_front')",
            name=op.f("ck_image_set_readiness_reviews_primary_front_role"),
        ),
        sa.CheckConstraint(
            "(reference_back_image_asset_id IS NULL AND reference_back_role IS NULL) "
            "OR (reference_back_image_asset_id IS NOT NULL "
            "AND reference_back_role = 'reference_back')",
            name=op.f("ck_image_set_readiness_reviews_reference_back_role"),
        ),
        sa.CheckConstraint(
            "(reference_angle_image_asset_id IS NULL AND reference_angle_role IS NULL) "
            "OR (reference_angle_image_asset_id IS NOT NULL "
            "AND reference_angle_role = 'reference_angle')",
            name=op.f("ck_image_set_readiness_reviews_reference_angle_role"),
        ),
        sa.CheckConstraint(
            "(reference_detail_image_asset_id IS NULL AND reference_detail_role IS NULL) "
            "OR (reference_detail_image_asset_id IS NOT NULL "
            "AND reference_detail_role = 'reference_detail')",
            name=op.f("ck_image_set_readiness_reviews_reference_detail_role"),
        ),
        sa.ForeignKeyConstraint(
            [
                "primary_front_image_asset_id",
                "paint_project_id",
                "owner_principal_id",
                "primary_front_role",
            ],
            [
                "image_assets.id",
                "image_assets.paint_project_id",
                "image_assets.owner_principal_id",
                "image_assets.role",
            ],
            name="fk_image_set_readiness_reviews_primary_front_asset",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            [
                "reference_back_image_asset_id",
                "paint_project_id",
                "owner_principal_id",
                "reference_back_role",
            ],
            [
                "image_assets.id",
                "image_assets.paint_project_id",
                "image_assets.owner_principal_id",
                "image_assets.role",
            ],
            name="fk_image_set_readiness_reviews_reference_back_asset",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            [
                "reference_angle_image_asset_id",
                "paint_project_id",
                "owner_principal_id",
                "reference_angle_role",
            ],
            [
                "image_assets.id",
                "image_assets.paint_project_id",
                "image_assets.owner_principal_id",
                "image_assets.role",
            ],
            name="fk_image_set_readiness_reviews_reference_angle_asset",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            [
                "reference_detail_image_asset_id",
                "paint_project_id",
                "owner_principal_id",
                "reference_detail_role",
            ],
            [
                "image_assets.id",
                "image_assets.paint_project_id",
                "image_assets.owner_principal_id",
                "image_assets.role",
            ],
            name="fk_image_set_readiness_reviews_reference_detail_asset",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["paint_project_id", "owner_principal_id"],
            ["paint_projects.id", "paint_projects.owner_principal_id"],
            name="fk_image_set_readiness_reviews_project_owner_paint_projects",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name=op.f("pk_image_set_readiness_reviews"),
        ),
        sa.UniqueConstraint(
            "paint_project_id",
            "version",
            name="uq_image_set_readiness_reviews_project_version",
        ),
    )
    op.create_index(
        "ix_image_set_readiness_reviews_owner_project_created_at",
        "image_set_readiness_reviews",
        ["owner_principal_id", "paint_project_id", "created_at"],
        unique=False,
    )
    op.execute(
        """
        CREATE FUNCTION reject_image_set_readiness_review_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION 'image_set_readiness_reviews are append-only'
                USING ERRCODE = '55000';
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_image_set_readiness_reviews_append_only
        BEFORE UPDATE OR DELETE ON image_set_readiness_reviews
        FOR EACH ROW
        EXECUTE FUNCTION reject_image_set_readiness_review_mutation()
        """
    )


def downgrade() -> None:
    """Roll back only when no Phase 1E-2 facts would be discarded."""
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM image_set_readiness_reviews) THEN
                RAISE EXCEPTION
                    'refusing downgrade: readiness review history would be lost'
                    USING ERRCODE = '55000';
            END IF;
            IF EXISTS (
                SELECT 1 FROM image_assets WHERE role <> 'primary_front'
            ) THEN
                RAISE EXCEPTION
                    'refusing downgrade: multi-role image history would be lost'
                    USING ERRCODE = '55000';
            END IF;
        END;
        $$
        """
    )
    op.execute(
        "DROP TRIGGER trg_image_set_readiness_reviews_append_only ON image_set_readiness_reviews"
    )
    op.execute("DROP FUNCTION reject_image_set_readiness_review_mutation()")
    op.drop_index(
        "ix_image_set_readiness_reviews_owner_project_created_at",
        table_name="image_set_readiness_reviews",
    )
    op.drop_table("image_set_readiness_reviews")

    op.drop_constraint(
        "fk_image_assets_supersedes_same_owner_project_role",
        "image_assets",
        type_="foreignkey",
    )
    op.drop_constraint(
        op.f("ck_image_assets_role_allowed"),
        "image_assets",
        type_="check",
    )
    op.execute("UPDATE image_assets SET role = 'primary_mvp_input' WHERE role = 'primary_front'")
    op.create_check_constraint(
        op.f("ck_image_assets_role_allowed"),
        "image_assets",
        "role IN ('primary_mvp_input')",
    )
    op.create_foreign_key(
        "fk_image_assets_supersedes_same_owner_project_role",
        "image_assets",
        "image_assets",
        [
            "supersedes_image_asset_id",
            "paint_project_id",
            "owner_principal_id",
            "role",
        ],
        ["id", "paint_project_id", "owner_principal_id", "role"],
        ondelete="RESTRICT",
    )
