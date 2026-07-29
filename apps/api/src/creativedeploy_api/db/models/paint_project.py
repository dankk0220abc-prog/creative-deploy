"""PaintProject persistence model for the first business migration."""

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql.elements import conv

from creativedeploy_api.db.base import Base
from creativedeploy_api.db.models.constants import (
    PLANNING_MODE_DEMO,
    POSTGRESQL_MACHINE_TOKEN_PATTERN,
    TARGET_STYLE_CEL_SHADING,
    WORKFLOW_STATES,
)


def _sql_values(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


class PaintProject(Base):
    """The Phase 1D PaintProject aggregate root persistence boundary."""

    __tablename__ = "paint_projects"
    __table_args__ = (
        CheckConstraint(
            "length(owner_principal_id) >= 1 AND owner_principal_id = btrim(owner_principal_id)",
            name=conv("ck_paint_projects_owner_principal_id_normalized"),
        ),
        CheckConstraint(
            "length(title) >= 1",
            name=conv("ck_paint_projects_title_not_blank"),
        ),
        CheckConstraint(
            "title = btrim(title)",
            name=conv("ck_paint_projects_title_normalized"),
        ),
        CheckConstraint(
            "description IS NULL OR "
            "(length(description) >= 1 AND description = btrim(description))",
            name=conv("ck_paint_projects_description_normalized"),
        ),
        CheckConstraint(
            f"requested_target_style ~ '{POSTGRESQL_MACHINE_TOKEN_PATTERN}'",
            name=conv("ck_paint_projects_requested_target_style_format"),
        ),
        CheckConstraint(
            f"requested_target_style = '{TARGET_STYLE_CEL_SHADING}'",
            name=conv("ck_paint_projects_requested_target_style_allowed"),
        ),
        CheckConstraint(
            f"planning_mode ~ '{POSTGRESQL_MACHINE_TOKEN_PATTERN}'",
            name=conv("ck_paint_projects_planning_mode_format"),
        ),
        CheckConstraint(
            f"planning_mode = '{PLANNING_MODE_DEMO}'",
            name=conv("ck_paint_projects_planning_mode_allowed"),
        ),
        CheckConstraint(
            f"status IN ({_sql_values(WORKFLOW_STATES)})",
            name=conv("ck_paint_projects_status_allowed"),
        ),
        CheckConstraint(
            "updated_at >= created_at",
            name=conv("ck_paint_projects_updated_at_not_before_created_at"),
        ),
        UniqueConstraint(
            "id",
            "owner_principal_id",
            name="uq_paint_projects_id_owner_principal_id",
        ),
        ForeignKeyConstraint(
            ["id", "owner_principal_id", "current_image_asset_id"],
            [
                "image_assets.paint_project_id",
                "image_assets.owner_principal_id",
                "image_assets.id",
            ],
            name="fk_paint_projects_current_image_asset_same_owner_project",
            ondelete="RESTRICT",
            use_alter=True,
        ),
        Index(
            "ix_paint_projects_owner_updated_at_id",
            "owner_principal_id",
            "updated_at",
            "id",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    owner_principal_id: Mapped[str] = mapped_column(String(128), nullable=False)
    title: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    requested_target_style: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=TARGET_STYLE_CEL_SHADING,
        server_default=text(f"'{TARGET_STYLE_CEL_SHADING}'"),
    )
    planning_mode: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=PLANNING_MODE_DEMO,
        server_default=text(f"'{PLANNING_MODE_DEMO}'"),
    )
    status: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="DRAFT",
        server_default=text("'DRAFT'"),
    )
    current_image_asset_id: Mapped[uuid.UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
