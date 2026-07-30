"""Immutable, owner-scoped human RegionSet persistence models."""

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql.elements import conv

from creativedeploy_api.db.base import Base

REGION_KINDS = ("paint", "exclude")
REGION_SET_LIFECYCLES = (
    "draft",
    "submitted",
    "approved",
    "changes_requested",
    "superseded",
)
REGION_REVIEW_VERDICTS = ("approved", "changes_requested")
MAX_REGIONS_PER_SET = 128
MAX_VERTICES_PER_REGION = 256
MAX_VERTICES_PER_SET = 8192
PPM_MAX = 1_000_000


def _sql_values(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


class RegionSet(Base):
    """One immutable full human annotation snapshot."""

    __tablename__ = "region_sets"
    __table_args__ = (
        CheckConstraint(
            "version >= 1",
            name=conv("ck_region_sets_version_positive"),
        ),
        CheckConstraint(
            f"lifecycle IN ({_sql_values(REGION_SET_LIFECYCLES)})",
            name=conv("ck_region_sets_lifecycle_allowed"),
        ),
        CheckConstraint(
            "source_primary_image_role = 'primary_front'",
            name=conv("ck_region_sets_source_primary_role"),
        ),
        CheckConstraint(
            "source_image_set_fingerprint ~ '^[0-9a-f]{64}$'",
            name=conv("ck_region_sets_source_fingerprint_format"),
        ),
        CheckConstraint(
            "source_image_width BETWEEN 1 AND 8192 AND source_image_height BETWEEN 1 AND 8192",
            name=conv("ck_region_sets_source_dimensions_allowed"),
        ),
        CheckConstraint(
            f"region_count BETWEEN 0 AND {MAX_REGIONS_PER_SET}",
            name=conv("ck_region_sets_region_count_allowed"),
        ),
        CheckConstraint(
            f"total_vertex_count BETWEEN 0 AND {MAX_VERTICES_PER_SET}",
            name=conv("ck_region_sets_total_vertex_count_allowed"),
        ),
        CheckConstraint(
            "(region_count = 0 AND total_vertex_count = 0) "
            "OR (region_count >= 1 AND total_vertex_count >= region_count * 3)",
            name=conv("ck_region_sets_counts_consistent"),
        ),
        CheckConstraint(
            "geometry_fingerprint ~ '^[0-9a-f]{64}$'",
            name=conv("ck_region_sets_geometry_fingerprint_format"),
        ),
        CheckConstraint(
            "created_by_actor_type = 'user'",
            name=conv("ck_region_sets_created_by_actor_type_allowed"),
        ),
        CheckConstraint(
            "length(created_by_actor_id) >= 1 AND created_by_actor_id = btrim(created_by_actor_id)",
            name=conv("ck_region_sets_created_by_actor_id_normalized"),
        ),
        CheckConstraint(
            "length(created_by_actor_display_name_snapshot) >= 1 "
            "AND created_by_actor_display_name_snapshot = "
            "btrim(created_by_actor_display_name_snapshot)",
            name=conv("ck_region_sets_created_by_display_normalized"),
        ),
        ForeignKeyConstraint(
            ["paint_project_id", "owner_principal_id"],
            ["paint_projects.id", "paint_projects.owner_principal_id"],
            name="fk_region_sets_project_owner_paint_projects",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
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
        ForeignKeyConstraint(
            [
                "supersedes_region_set_id",
                "paint_project_id",
                "owner_principal_id",
            ],
            [
                "region_sets.id",
                "region_sets.paint_project_id",
                "region_sets.owner_principal_id",
            ],
            name="fk_region_sets_supersedes_same_owner_project",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            [
                "based_on_region_set_id",
                "paint_project_id",
                "owner_principal_id",
            ],
            [
                "region_sets.id",
                "region_sets.paint_project_id",
                "region_sets.owner_principal_id",
            ],
            name="fk_region_sets_based_on_same_owner_project",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "paint_project_id",
            "owner_principal_id",
            "id",
            name="uq_region_sets_project_owner_id",
        ),
        UniqueConstraint(
            "paint_project_id",
            "version",
            name="uq_region_sets_project_version",
        ),
        Index(
            "ix_region_sets_owner_project_version",
            "owner_principal_id",
            "paint_project_id",
            "version",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    owner_principal_id: Mapped[str] = mapped_column(String(128), nullable=False)
    paint_project_id: Mapped[uuid.UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        nullable=False,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    lifecycle: Mapped[str] = mapped_column(String(32), nullable=False)
    source_primary_image_asset_id: Mapped[uuid.UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        nullable=False,
    )
    source_primary_image_role: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="primary_front",
    )
    source_image_set_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    source_image_width: Mapped[int] = mapped_column(Integer, nullable=False)
    source_image_height: Mapped[int] = mapped_column(Integer, nullable=False)
    supersedes_region_set_id: Mapped[uuid.UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        nullable=True,
    )
    based_on_region_set_id: Mapped[uuid.UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        nullable=True,
    )
    region_count: Mapped[int] = mapped_column(Integer, nullable=False)
    total_vertex_count: Mapped[int] = mapped_column(Integer, nullable=False)
    geometry_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
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


class Region(Base):
    """One immutable human-labelled simple Polygon in a RegionSet."""

    __tablename__ = "regions"
    __table_args__ = (
        CheckConstraint(
            f"kind IN ({_sql_values(REGION_KINDS)})",
            name=conv("ck_regions_kind_allowed"),
        ),
        CheckConstraint(
            "length(label) BETWEEN 1 AND 80 AND label = btrim(label) "
            "AND label !~ '[<>]' AND label !~ '[[:cntrl:]]'",
            name=conv("ck_regions_label_safe"),
        ),
        CheckConstraint(
            "length(normalized_label) BETWEEN 1 AND 80 "
            "AND normalized_label = btrim(normalized_label) "
            "AND normalized_label !~ '[<>]' AND normalized_label !~ '[[:cntrl:]]'",
            name=conv("ck_regions_normalized_label_safe"),
        ),
        CheckConstraint(
            "z_index BETWEEN 0 AND 127",
            name=conv("ck_regions_z_index_allowed"),
        ),
        CheckConstraint(
            "opacity_ppm BETWEEN 100000 AND 1000000",
            name=conv("ck_regions_opacity_ppm_allowed"),
        ),
        CheckConstraint(
            "notes IS NULL OR (length(notes) BETWEEN 1 AND 1000 "
            "AND notes = btrim(notes) AND notes !~ '[<>]' "
            "AND notes !~ '[[:cntrl:]]')",
            name=conv("ck_regions_notes_safe"),
        ),
        CheckConstraint(
            f"vertex_count BETWEEN 3 AND {MAX_VERTICES_PER_REGION}",
            name=conv("ck_regions_vertex_count_allowed"),
        ),
        CheckConstraint(
            "area_twice_ppm_squared > 0",
            name=conv("ck_regions_area_positive"),
        ),
        CheckConstraint(
            f"bbox_min_x_ppm BETWEEN 0 AND {PPM_MAX} "
            f"AND bbox_max_x_ppm BETWEEN 0 AND {PPM_MAX} "
            f"AND bbox_min_y_ppm BETWEEN 0 AND {PPM_MAX} "
            f"AND bbox_max_y_ppm BETWEEN 0 AND {PPM_MAX} "
            "AND bbox_min_x_ppm < bbox_max_x_ppm "
            "AND bbox_min_y_ppm < bbox_max_y_ppm",
            name=conv("ck_regions_bbox_allowed"),
        ),
        ForeignKeyConstraint(
            ["region_set_id", "paint_project_id", "owner_principal_id"],
            ["region_sets.id", "region_sets.paint_project_id", "region_sets.owner_principal_id"],
            name="fk_regions_region_set_same_owner_project",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "id",
            "region_set_id",
            name="uq_regions_id_region_set",
        ),
        UniqueConstraint(
            "region_set_id",
            "stable_region_key",
            name="uq_regions_region_set_stable_key",
        ),
        UniqueConstraint(
            "region_set_id",
            "z_index",
            name="uq_regions_region_set_z_index",
        ),
        Index(
            "ix_regions_region_set_z_index",
            "region_set_id",
            "z_index",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    region_set_id: Mapped[uuid.UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        nullable=False,
    )
    paint_project_id: Mapped[uuid.UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        nullable=False,
    )
    owner_principal_id: Mapped[str] = mapped_column(String(128), nullable=False)
    stable_region_key: Mapped[uuid.UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        nullable=False,
    )
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    label: Mapped[str] = mapped_column(String(80), nullable=False)
    normalized_label: Mapped[str] = mapped_column(String(80), nullable=False)
    z_index: Mapped[int] = mapped_column(Integer, nullable=False)
    opacity_ppm: Mapped[int] = mapped_column(Integer, nullable=False)
    notes: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    vertex_count: Mapped[int] = mapped_column(Integer, nullable=False)
    area_twice_ppm_squared: Mapped[int] = mapped_column(BigInteger, nullable=False)
    bbox_min_x_ppm: Mapped[int] = mapped_column(Integer, nullable=False)
    bbox_min_y_ppm: Mapped[int] = mapped_column(Integer, nullable=False)
    bbox_max_x_ppm: Mapped[int] = mapped_column(Integer, nullable=False)
    bbox_max_y_ppm: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )


class RegionVertex(Base):
    """One sequenced ppm vertex owned by exactly one immutable Region."""

    __tablename__ = "region_vertices"
    __table_args__ = (
        CheckConstraint(
            f"sequence BETWEEN 0 AND {MAX_VERTICES_PER_REGION - 1}",
            name=conv("ck_region_vertices_sequence_allowed"),
        ),
        CheckConstraint(
            f"x_ppm BETWEEN 0 AND {PPM_MAX} AND y_ppm BETWEEN 0 AND {PPM_MAX}",
            name=conv("ck_region_vertices_coordinates_allowed"),
        ),
        ForeignKeyConstraint(
            ["region_id", "region_set_id"],
            ["regions.id", "regions.region_set_id"],
            name="fk_region_vertices_region_same_set",
            ondelete="RESTRICT",
        ),
        Index(
            "ix_region_vertices_region_set_region_sequence",
            "region_set_id",
            "region_id",
            "sequence",
        ),
    )

    region_id: Mapped[uuid.UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
    )
    sequence: Mapped[int] = mapped_column(Integer, primary_key=True)
    region_set_id: Mapped[uuid.UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        nullable=False,
    )
    x_ppm: Mapped[int] = mapped_column(Integer, nullable=False)
    y_ppm: Mapped[int] = mapped_column(Integer, nullable=False)


class RegionSetReview(Base):
    """One append-only human review of an exact submitted RegionSet."""

    __tablename__ = "region_set_reviews"
    __table_args__ = (
        CheckConstraint(
            "version >= 1",
            name=conv("ck_region_set_reviews_version_positive"),
        ),
        CheckConstraint(
            f"verdict IN ({_sql_values(REGION_REVIEW_VERDICTS)})",
            name=conv("ck_region_set_reviews_verdict_allowed"),
        ),
        CheckConstraint(
            "reason IS NULL OR (length(reason) BETWEEN 1 AND 1000 "
            "AND reason = btrim(reason) AND reason !~ '[[:cntrl:]]')",
            name=conv("ck_region_set_reviews_reason_normalized"),
        ),
        CheckConstraint(
            "verdict <> 'changes_requested' OR reason IS NOT NULL",
            name=conv("ck_region_set_reviews_changes_reason_required"),
        ),
        CheckConstraint(
            "actor_type = 'user'",
            name=conv("ck_region_set_reviews_actor_type_allowed"),
        ),
        CheckConstraint(
            "length(actor_id) >= 1 AND actor_id = btrim(actor_id)",
            name=conv("ck_region_set_reviews_actor_id_normalized"),
        ),
        CheckConstraint(
            "length(actor_display_name_snapshot) >= 1 "
            "AND actor_display_name_snapshot = btrim(actor_display_name_snapshot)",
            name=conv("ck_region_set_reviews_actor_display_normalized"),
        ),
        ForeignKeyConstraint(
            ["region_set_id", "paint_project_id", "owner_principal_id"],
            ["region_sets.id", "region_sets.paint_project_id", "region_sets.owner_principal_id"],
            name="fk_region_set_reviews_region_set_same_owner_project",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "paint_project_id",
            "version",
            name="uq_region_set_reviews_project_version",
        ),
        UniqueConstraint(
            "region_set_id",
            name="uq_region_set_reviews_region_set",
        ),
        Index(
            "ix_region_set_reviews_owner_project_created_at",
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
    owner_principal_id: Mapped[str] = mapped_column(String(128), nullable=False)
    paint_project_id: Mapped[uuid.UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        nullable=False,
    )
    region_set_id: Mapped[uuid.UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        nullable=False,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    verdict: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    actor_type: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(128), nullable=False)
    actor_display_name_snapshot: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
