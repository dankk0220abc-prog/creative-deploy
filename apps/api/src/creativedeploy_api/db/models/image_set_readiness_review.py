"""Append-only, owner-scoped human ImageSet readiness review model."""

import uuid
from datetime import datetime

from sqlalchemy import (
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
from creativedeploy_api.db.models.image_asset import (
    IMAGE_ROLE_PRIMARY,
    IMAGE_ROLE_REFERENCE_ANGLE,
    IMAGE_ROLE_REFERENCE_BACK,
    IMAGE_ROLE_REFERENCE_DETAIL,
)

READINESS_VERDICTS = ("ready", "not_ready")


def _asset_role_constraint(asset_column: str, role_column: str, role: str) -> str:
    return (
        f"({asset_column} IS NULL AND {role_column} IS NULL) "
        f"OR ({asset_column} IS NOT NULL AND {role_column} = '{role}')"
    )


def _asset_foreign_key(
    asset_column: str,
    role_column: str,
    constraint_name: str,
) -> ForeignKeyConstraint:
    return ForeignKeyConstraint(
        [asset_column, "paint_project_id", "owner_principal_id", role_column],
        [
            "image_assets.id",
            "image_assets.paint_project_id",
            "image_assets.owner_principal_id",
            "image_assets.role",
        ],
        name=constraint_name,
        ondelete="RESTRICT",
    )


class ImageSetReadinessReview(Base):
    """One immutable human verdict bound to an exact current ImageSet snapshot."""

    __tablename__ = "image_set_readiness_reviews"
    __table_args__ = (
        CheckConstraint(
            "version >= 1",
            name=conv("ck_image_set_readiness_reviews_version_positive"),
        ),
        CheckConstraint(
            "verdict IN ('ready', 'not_ready')",
            name=conv("ck_image_set_readiness_reviews_verdict_allowed"),
        ),
        CheckConstraint(
            "reason IS NULL OR (length(reason) BETWEEN 1 AND 1000 AND reason = btrim(reason))",
            name=conv("ck_image_set_readiness_reviews_reason_normalized"),
        ),
        CheckConstraint(
            "verdict <> 'not_ready' OR reason IS NOT NULL",
            name=conv("ck_image_set_readiness_reviews_not_ready_reason_required"),
        ),
        CheckConstraint(
            "verdict <> 'ready' OR "
            "(primary_front_image_asset_id IS NOT NULL "
            "AND reference_back_image_asset_id IS NOT NULL "
            "AND reference_angle_image_asset_id IS NOT NULL)",
            name=conv("ck_image_set_readiness_reviews_ready_required_assets"),
        ),
        CheckConstraint(
            "image_set_fingerprint ~ '^[0-9a-f]{64}$'",
            name=conv("ck_image_set_readiness_reviews_fingerprint_format"),
        ),
        CheckConstraint(
            "actor_type = 'user'",
            name=conv("ck_image_set_readiness_reviews_actor_type_allowed"),
        ),
        CheckConstraint(
            "length(actor_id) >= 1 AND actor_id = btrim(actor_id)",
            name=conv("ck_image_set_readiness_reviews_actor_id_normalized"),
        ),
        CheckConstraint(
            "length(actor_display_name_snapshot) >= 1 "
            "AND actor_display_name_snapshot = btrim(actor_display_name_snapshot)",
            name=conv("ck_image_set_readiness_reviews_actor_display_normalized"),
        ),
        CheckConstraint(
            _asset_role_constraint(
                "primary_front_image_asset_id",
                "primary_front_role",
                IMAGE_ROLE_PRIMARY,
            ),
            name=conv("ck_image_set_readiness_reviews_primary_front_role"),
        ),
        CheckConstraint(
            _asset_role_constraint(
                "reference_back_image_asset_id",
                "reference_back_role",
                IMAGE_ROLE_REFERENCE_BACK,
            ),
            name=conv("ck_image_set_readiness_reviews_reference_back_role"),
        ),
        CheckConstraint(
            _asset_role_constraint(
                "reference_angle_image_asset_id",
                "reference_angle_role",
                IMAGE_ROLE_REFERENCE_ANGLE,
            ),
            name=conv("ck_image_set_readiness_reviews_reference_angle_role"),
        ),
        CheckConstraint(
            _asset_role_constraint(
                "reference_detail_image_asset_id",
                "reference_detail_role",
                IMAGE_ROLE_REFERENCE_DETAIL,
            ),
            name=conv("ck_image_set_readiness_reviews_reference_detail_role"),
        ),
        ForeignKeyConstraint(
            ["paint_project_id", "owner_principal_id"],
            ["paint_projects.id", "paint_projects.owner_principal_id"],
            name="fk_image_set_readiness_reviews_project_owner_paint_projects",
            ondelete="RESTRICT",
        ),
        _asset_foreign_key(
            "primary_front_image_asset_id",
            "primary_front_role",
            "fk_image_set_readiness_reviews_primary_front_asset",
        ),
        _asset_foreign_key(
            "reference_back_image_asset_id",
            "reference_back_role",
            "fk_image_set_readiness_reviews_reference_back_asset",
        ),
        _asset_foreign_key(
            "reference_angle_image_asset_id",
            "reference_angle_role",
            "fk_image_set_readiness_reviews_reference_angle_asset",
        ),
        _asset_foreign_key(
            "reference_detail_image_asset_id",
            "reference_detail_role",
            "fk_image_set_readiness_reviews_reference_detail_asset",
        ),
        UniqueConstraint(
            "paint_project_id",
            "version",
            name="uq_image_set_readiness_reviews_project_version",
        ),
        Index(
            "ix_image_set_readiness_reviews_owner_project_created_at",
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
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    verdict: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    primary_front_image_asset_id: Mapped[uuid.UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        nullable=True,
    )
    primary_front_role: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reference_back_image_asset_id: Mapped[uuid.UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        nullable=True,
    )
    reference_back_role: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reference_angle_image_asset_id: Mapped[uuid.UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        nullable=True,
    )
    reference_angle_role: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reference_detail_image_asset_id: Mapped[uuid.UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        nullable=True,
    )
    reference_detail_role: Mapped[str | None] = mapped_column(String(64), nullable=True)
    image_set_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
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
