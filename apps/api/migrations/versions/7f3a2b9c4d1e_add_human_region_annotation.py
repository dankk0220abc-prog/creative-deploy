"""add human governed RegionSet annotation

Revision ID: 7f3a2b9c4d1e
Revises: d4c8a1f7b2e9
Create Date: 2026-07-29 00:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "7f3a2b9c4d1e"
down_revision: str | Sequence[str] | None = "d4c8a1f7b2e9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _create_append_only_trigger(table_name: str) -> None:
    function_name = f"reject_{table_name}_mutation"
    trigger_name = f"trg_{table_name}_append_only"
    op.execute(
        f"""
        CREATE FUNCTION {function_name}()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION '{table_name} are append-only'
                USING ERRCODE = '55000';
        END;
        $$
        """
    )
    op.execute(
        f"""
        CREATE TRIGGER {trigger_name}
        BEFORE UPDATE OR DELETE ON {table_name}
        FOR EACH ROW
        EXECUTE FUNCTION {function_name}()
        """
    )


def _drop_append_only_trigger(table_name: str) -> None:
    op.execute(f"DROP TRIGGER trg_{table_name}_append_only ON {table_name}")
    op.execute(f"DROP FUNCTION reject_{table_name}_mutation()")


def upgrade() -> None:
    """Create immutable human annotation snapshots and append-only reviews."""
    op.create_table(
        "region_sets",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("owner_principal_id", sa.String(length=128), nullable=False),
        sa.Column("paint_project_id", sa.UUID(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("lifecycle", sa.String(length=32), nullable=False),
        sa.Column("source_primary_image_asset_id", sa.UUID(), nullable=False),
        sa.Column(
            "source_primary_image_role",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column(
            "source_image_set_fingerprint",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column("source_image_width", sa.Integer(), nullable=False),
        sa.Column("source_image_height", sa.Integer(), nullable=False),
        sa.Column("supersedes_region_set_id", sa.UUID(), nullable=True),
        sa.Column("based_on_region_set_id", sa.UUID(), nullable=True),
        sa.Column("region_count", sa.Integer(), nullable=False),
        sa.Column("total_vertex_count", sa.Integer(), nullable=False),
        sa.Column("geometry_fingerprint", sa.String(length=64), nullable=False),
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
            "version >= 1",
            name=op.f("ck_region_sets_version_positive"),
        ),
        sa.CheckConstraint(
            "lifecycle IN ('draft','submitted','approved','changes_requested','superseded')",
            name=op.f("ck_region_sets_lifecycle_allowed"),
        ),
        sa.CheckConstraint(
            "source_primary_image_role = 'primary_front'",
            name=op.f("ck_region_sets_source_primary_role"),
        ),
        sa.CheckConstraint(
            "source_image_set_fingerprint ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_region_sets_source_fingerprint_format"),
        ),
        sa.CheckConstraint(
            "source_image_width BETWEEN 1 AND 8192 AND source_image_height BETWEEN 1 AND 8192",
            name=op.f("ck_region_sets_source_dimensions_allowed"),
        ),
        sa.CheckConstraint(
            "region_count BETWEEN 0 AND 128",
            name=op.f("ck_region_sets_region_count_allowed"),
        ),
        sa.CheckConstraint(
            "total_vertex_count BETWEEN 0 AND 8192",
            name=op.f("ck_region_sets_total_vertex_count_allowed"),
        ),
        sa.CheckConstraint(
            "(region_count = 0 AND total_vertex_count = 0) "
            "OR (region_count >= 1 AND total_vertex_count >= region_count * 3)",
            name=op.f("ck_region_sets_counts_consistent"),
        ),
        sa.CheckConstraint(
            "geometry_fingerprint ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_region_sets_geometry_fingerprint_format"),
        ),
        sa.CheckConstraint(
            "created_by_actor_type = 'user'",
            name=op.f("ck_region_sets_created_by_actor_type_allowed"),
        ),
        sa.CheckConstraint(
            "length(created_by_actor_id) >= 1 AND created_by_actor_id = btrim(created_by_actor_id)",
            name=op.f("ck_region_sets_created_by_actor_id_normalized"),
        ),
        sa.CheckConstraint(
            "length(created_by_actor_display_name_snapshot) >= 1 "
            "AND created_by_actor_display_name_snapshot = "
            "btrim(created_by_actor_display_name_snapshot)",
            name=op.f("ck_region_sets_created_by_display_normalized"),
        ),
        sa.ForeignKeyConstraint(
            ["paint_project_id", "owner_principal_id"],
            ["paint_projects.id", "paint_projects.owner_principal_id"],
            name="fk_region_sets_project_owner_paint_projects",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            [
                "source_primary_image_asset_id",
                "paint_project_id",
                "owner_principal_id",
                "source_primary_image_role",
            ],
            [
                "image_assets.id",
                "image_assets.paint_project_id",
                "image_assets.owner_principal_id",
                "image_assets.role",
            ],
            name="fk_region_sets_source_primary_image_asset",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_region_sets")),
        sa.UniqueConstraint(
            "paint_project_id",
            "owner_principal_id",
            "id",
            name="uq_region_sets_project_owner_id",
        ),
        sa.UniqueConstraint(
            "paint_project_id",
            "version",
            name="uq_region_sets_project_version",
        ),
    )
    op.create_foreign_key(
        "fk_region_sets_supersedes_same_owner_project",
        "region_sets",
        "region_sets",
        ["supersedes_region_set_id", "paint_project_id", "owner_principal_id"],
        ["id", "paint_project_id", "owner_principal_id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_region_sets_based_on_same_owner_project",
        "region_sets",
        "region_sets",
        ["based_on_region_set_id", "paint_project_id", "owner_principal_id"],
        ["id", "paint_project_id", "owner_principal_id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_region_sets_owner_project_version",
        "region_sets",
        ["owner_principal_id", "paint_project_id", "version"],
        unique=False,
    )

    op.create_table(
        "regions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("region_set_id", sa.UUID(), nullable=False),
        sa.Column("paint_project_id", sa.UUID(), nullable=False),
        sa.Column("owner_principal_id", sa.String(length=128), nullable=False),
        sa.Column("stable_region_key", sa.UUID(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("label", sa.String(length=80), nullable=False),
        sa.Column("normalized_label", sa.String(length=80), nullable=False),
        sa.Column("z_index", sa.Integer(), nullable=False),
        sa.Column("opacity_ppm", sa.Integer(), nullable=False),
        sa.Column("notes", sa.String(length=1000), nullable=True),
        sa.Column("vertex_count", sa.Integer(), nullable=False),
        sa.Column("area_twice_ppm_squared", sa.BigInteger(), nullable=False),
        sa.Column("bbox_min_x_ppm", sa.Integer(), nullable=False),
        sa.Column("bbox_min_y_ppm", sa.Integer(), nullable=False),
        sa.Column("bbox_max_x_ppm", sa.Integer(), nullable=False),
        sa.Column("bbox_max_y_ppm", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "kind IN ('paint','exclude')",
            name=op.f("ck_regions_kind_allowed"),
        ),
        sa.CheckConstraint(
            "length(label) BETWEEN 1 AND 80 AND label = btrim(label) "
            "AND label !~ '[<>]' AND label !~ '[[:cntrl:]]'",
            name=op.f("ck_regions_label_safe"),
        ),
        sa.CheckConstraint(
            "length(normalized_label) BETWEEN 1 AND 80 "
            "AND normalized_label = btrim(normalized_label) "
            "AND normalized_label !~ '[<>]' "
            "AND normalized_label !~ '[[:cntrl:]]'",
            name=op.f("ck_regions_normalized_label_safe"),
        ),
        sa.CheckConstraint(
            "z_index BETWEEN 0 AND 127",
            name=op.f("ck_regions_z_index_allowed"),
        ),
        sa.CheckConstraint(
            "opacity_ppm BETWEEN 100000 AND 1000000",
            name=op.f("ck_regions_opacity_ppm_allowed"),
        ),
        sa.CheckConstraint(
            "notes IS NULL OR (length(notes) BETWEEN 1 AND 1000 "
            "AND notes = btrim(notes) AND notes !~ '[<>]' "
            "AND notes !~ '[[:cntrl:]]')",
            name=op.f("ck_regions_notes_safe"),
        ),
        sa.CheckConstraint(
            "vertex_count BETWEEN 3 AND 256",
            name=op.f("ck_regions_vertex_count_allowed"),
        ),
        sa.CheckConstraint(
            "area_twice_ppm_squared > 0",
            name=op.f("ck_regions_area_positive"),
        ),
        sa.CheckConstraint(
            "bbox_min_x_ppm BETWEEN 0 AND 1000000 "
            "AND bbox_max_x_ppm BETWEEN 0 AND 1000000 "
            "AND bbox_min_y_ppm BETWEEN 0 AND 1000000 "
            "AND bbox_max_y_ppm BETWEEN 0 AND 1000000 "
            "AND bbox_min_x_ppm < bbox_max_x_ppm "
            "AND bbox_min_y_ppm < bbox_max_y_ppm",
            name=op.f("ck_regions_bbox_allowed"),
        ),
        sa.ForeignKeyConstraint(
            ["region_set_id", "paint_project_id", "owner_principal_id"],
            ["region_sets.id", "region_sets.paint_project_id", "region_sets.owner_principal_id"],
            name="fk_regions_region_set_same_owner_project",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_regions")),
        sa.UniqueConstraint(
            "id",
            "region_set_id",
            name="uq_regions_id_region_set",
        ),
        sa.UniqueConstraint(
            "region_set_id",
            "stable_region_key",
            name="uq_regions_region_set_stable_key",
        ),
        sa.UniqueConstraint(
            "region_set_id",
            "z_index",
            name="uq_regions_region_set_z_index",
        ),
    )
    op.create_index(
        "ix_regions_region_set_z_index",
        "regions",
        ["region_set_id", "z_index"],
        unique=False,
    )

    op.create_table(
        "region_vertices",
        sa.Column("region_id", sa.UUID(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("region_set_id", sa.UUID(), nullable=False),
        sa.Column("x_ppm", sa.Integer(), nullable=False),
        sa.Column("y_ppm", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "sequence BETWEEN 0 AND 255",
            name=op.f("ck_region_vertices_sequence_allowed"),
        ),
        sa.CheckConstraint(
            "x_ppm BETWEEN 0 AND 1000000 AND y_ppm BETWEEN 0 AND 1000000",
            name=op.f("ck_region_vertices_coordinates_allowed"),
        ),
        sa.ForeignKeyConstraint(
            ["region_id", "region_set_id"],
            ["regions.id", "regions.region_set_id"],
            name="fk_region_vertices_region_same_set",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "region_id",
            "sequence",
            name=op.f("pk_region_vertices"),
        ),
    )
    op.create_index(
        "ix_region_vertices_region_set_region_sequence",
        "region_vertices",
        ["region_set_id", "region_id", "sequence"],
        unique=False,
    )

    op.create_table(
        "region_set_reviews",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("owner_principal_id", sa.String(length=128), nullable=False),
        sa.Column("paint_project_id", sa.UUID(), nullable=False),
        sa.Column("region_set_id", sa.UUID(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("verdict", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.String(length=1000), nullable=True),
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
            name=op.f("ck_region_set_reviews_version_positive"),
        ),
        sa.CheckConstraint(
            "verdict IN ('approved','changes_requested')",
            name=op.f("ck_region_set_reviews_verdict_allowed"),
        ),
        sa.CheckConstraint(
            "reason IS NULL OR (length(reason) BETWEEN 1 AND 1000 "
            "AND reason = btrim(reason) AND reason !~ '[[:cntrl:]]')",
            name=op.f("ck_region_set_reviews_reason_normalized"),
        ),
        sa.CheckConstraint(
            "verdict <> 'changes_requested' OR reason IS NOT NULL",
            name=op.f("ck_region_set_reviews_changes_reason_required"),
        ),
        sa.CheckConstraint(
            "actor_type = 'user'",
            name=op.f("ck_region_set_reviews_actor_type_allowed"),
        ),
        sa.CheckConstraint(
            "length(actor_id) >= 1 AND actor_id = btrim(actor_id)",
            name=op.f("ck_region_set_reviews_actor_id_normalized"),
        ),
        sa.CheckConstraint(
            "length(actor_display_name_snapshot) >= 1 "
            "AND actor_display_name_snapshot = btrim(actor_display_name_snapshot)",
            name=op.f("ck_region_set_reviews_actor_display_normalized"),
        ),
        sa.ForeignKeyConstraint(
            ["region_set_id", "paint_project_id", "owner_principal_id"],
            ["region_sets.id", "region_sets.paint_project_id", "region_sets.owner_principal_id"],
            name="fk_region_set_reviews_region_set_same_owner_project",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_region_set_reviews")),
        sa.UniqueConstraint(
            "paint_project_id",
            "version",
            name="uq_region_set_reviews_project_version",
        ),
        sa.UniqueConstraint(
            "region_set_id",
            name="uq_region_set_reviews_region_set",
        ),
    )
    op.create_index(
        "ix_region_set_reviews_owner_project_created_at",
        "region_set_reviews",
        ["owner_principal_id", "paint_project_id", "created_at"],
        unique=False,
    )

    for table_name in ("region_sets", "regions", "region_vertices", "region_set_reviews"):
        _create_append_only_trigger(table_name)


def downgrade() -> None:
    """Roll back only when no Phase 1F facts would be discarded."""
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM region_sets)
               OR EXISTS (SELECT 1 FROM region_set_reviews) THEN
                RAISE EXCEPTION
                    'refusing downgrade: RegionSet history would be lost'
                    USING ERRCODE = '55000';
            END IF;
        END;
        $$
        """
    )
    for table_name in (
        "region_set_reviews",
        "region_vertices",
        "regions",
        "region_sets",
    ):
        _drop_append_only_trigger(table_name)
    op.drop_index(
        "ix_region_set_reviews_owner_project_created_at",
        table_name="region_set_reviews",
    )
    op.drop_table("region_set_reviews")
    op.drop_index(
        "ix_region_vertices_region_set_region_sequence",
        table_name="region_vertices",
    )
    op.drop_table("region_vertices")
    op.drop_index("ix_regions_region_set_z_index", table_name="regions")
    op.drop_table("regions")
    op.drop_index("ix_region_sets_owner_project_version", table_name="region_sets")
    op.drop_table("region_sets")
