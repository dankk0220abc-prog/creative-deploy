"""Authoritative PaintProject state transition audit model."""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql.elements import conv

from creativedeploy_api.db.base import Base
from creativedeploy_api.db.models.constants import (
    ACTOR_TYPES,
    POSTGRESQL_MACHINE_TOKEN_PATTERN,
    WORKFLOW_STATES,
)


def _sql_values(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


class StateTransitionEvent(Base):
    """An immutable audit fact written with a guarded project state change."""

    __tablename__ = "state_transition_events"
    __table_args__ = (
        CheckConstraint(
            f"from_state IS NULL OR from_state IN ({_sql_values(WORKFLOW_STATES)})",
            name=conv("ck_state_transition_events_from_state_allowed"),
        ),
        CheckConstraint(
            f"to_state IN ({_sql_values(WORKFLOW_STATES)})",
            name=conv("ck_state_transition_events_to_state_allowed"),
        ),
        CheckConstraint(
            f"event ~ '{POSTGRESQL_MACHINE_TOKEN_PATTERN}'",
            name=conv("ck_state_transition_events_event_format"),
        ),
        CheckConstraint(
            f"actor_type ~ '{POSTGRESQL_MACHINE_TOKEN_PATTERN}'",
            name=conv("ck_state_transition_events_actor_type_format"),
        ),
        CheckConstraint(
            f"actor_type IN ({_sql_values(ACTOR_TYPES)})",
            name=conv("ck_state_transition_events_actor_type_allowed"),
        ),
        CheckConstraint(
            "length(actor_principal_id) >= 1 AND actor_principal_id = btrim(actor_principal_id)",
            name=conv("ck_state_transition_events_actor_principal_id_normalized"),
        ),
        CheckConstraint(
            "actor_display_name_snapshot IS NULL "
            "OR (length(actor_display_name_snapshot) >= 1 "
            "AND actor_display_name_snapshot = btrim(actor_display_name_snapshot))",
            name=conv("ck_state_transition_events_actor_display_snapshot_normalized"),
        ),
        CheckConstraint(
            "actor_type <> 'user' OR actor_display_name_snapshot IS NOT NULL",
            name=conv("ck_state_transition_events_user_display_name_required"),
        ),
        CheckConstraint(
            f"reason IS NULL OR reason ~ '{POSTGRESQL_MACHINE_TOKEN_PATTERN}'",
            name=conv("ck_state_transition_events_reason_format"),
        ),
        CheckConstraint(
            "event <> 'create_project' OR (reason IS NOT NULL AND reason = 'project_created')",
            name=conv("ck_state_transition_events_create_project_reason"),
        ),
        CheckConstraint(
            "jsonb_typeof(event_metadata) = 'object'",
            name=conv("ck_state_transition_events_event_metadata_is_object"),
        ),
        Index(
            "ix_state_transition_events_project_created_at_id",
            "project_id",
            "created_at",
            "id",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("paint_projects.id", ondelete="RESTRICT"),
        nullable=False,
    )
    from_state: Mapped[str | None] = mapped_column(String(64), nullable=True)
    to_state: Mapped[str] = mapped_column(String(64), nullable=False)
    event: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_type: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_principal_id: Mapped[str] = mapped_column(String(128), nullable=False)
    actor_display_name_snapshot: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
    )
    reason: Mapped[str | None] = mapped_column(String(128), nullable=True)
    correlation_id: Mapped[uuid.UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        nullable=False,
    )
    event_metadata: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
