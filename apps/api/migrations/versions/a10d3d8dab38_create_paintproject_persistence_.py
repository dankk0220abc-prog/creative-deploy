"""create PaintProject persistence foundation

Revision ID: a10d3d8dab38
Revises:
Create Date: 2026-07-26 02:27:43.623748

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a10d3d8dab38"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "paint_projects",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("owner_principal_id", sa.String(length=128), nullable=False),
        sa.Column("title", sa.String(length=80), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column(
            "requested_target_style",
            sa.String(length=32),
            server_default=sa.text("'cel_shading'"),
            nullable=False,
        ),
        sa.Column(
            "planning_mode",
            sa.String(length=32),
            server_default=sa.text("'planning_only_demo'"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=64),
            server_default=sa.text("'DRAFT'"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "length(owner_principal_id) >= 1 AND owner_principal_id = btrim(owner_principal_id)",
            name=op.f("ck_paint_projects_owner_principal_id_normalized"),
        ),
        sa.CheckConstraint(
            "length(title) >= 1",
            name=op.f("ck_paint_projects_title_not_blank"),
        ),
        sa.CheckConstraint(
            "title = btrim(title)",
            name=op.f("ck_paint_projects_title_normalized"),
        ),
        sa.CheckConstraint(
            "description IS NULL OR "
            "(length(description) >= 1 AND description = btrim(description))",
            name=op.f("ck_paint_projects_description_normalized"),
        ),
        sa.CheckConstraint(
            r"requested_target_style ~ '^[a-z][a-z0-9]*(_[a-z0-9]+)*$'",
            name=op.f("ck_paint_projects_requested_target_style_format"),
        ),
        sa.CheckConstraint(
            "requested_target_style = 'cel_shading'",
            name=op.f("ck_paint_projects_requested_target_style_allowed"),
        ),
        sa.CheckConstraint(
            r"planning_mode ~ '^[a-z][a-z0-9]*(_[a-z0-9]+)*$'",
            name=op.f("ck_paint_projects_planning_mode_format"),
        ),
        sa.CheckConstraint(
            "planning_mode = 'planning_only_demo'",
            name=op.f("ck_paint_projects_planning_mode_allowed"),
        ),
        sa.CheckConstraint(
            "status IN ("
            "'DRAFT', 'IMAGE_UPLOADED', 'IMAGE_REVIEW_REQUIRED', "
            "'IMAGE_VALIDATION_FAILED', 'IMAGE_VALIDATED', "
            "'REGION_ANALYSIS_RUNNING', 'REGION_REVIEW_REQUIRED', "
            "'REGIONS_CONFIRMED', 'PLAN_GENERATION_RUNNING', "
            "'PLAN_REVIEW_REQUIRED', 'PLAN_APPROVED', 'COMPLETED', "
            "'BLOCKED_LOW_CONFIDENCE', 'FAILED_RETRYABLE', "
            "'FAILED_FINAL', 'ABANDONED'"
            ")",
            name=op.f("ck_paint_projects_status_allowed"),
        ),
        sa.CheckConstraint(
            "updated_at >= created_at",
            name=op.f("ck_paint_projects_updated_at_not_before_created_at"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_paint_projects")),
    )
    op.create_index(
        "ix_paint_projects_owner_updated_at_id",
        "paint_projects",
        ["owner_principal_id", "updated_at", "id"],
        unique=False,
    )
    op.create_table(
        "state_transition_events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("from_state", sa.String(length=64), nullable=True),
        sa.Column("to_state", sa.String(length=64), nullable=False),
        sa.Column("event", sa.String(length=64), nullable=False),
        sa.Column("actor_type", sa.String(length=32), nullable=False),
        sa.Column("actor_principal_id", sa.String(length=128), nullable=False),
        sa.Column(
            "actor_display_name_snapshot",
            sa.String(length=200),
            nullable=True,
        ),
        sa.Column("reason", sa.String(length=128), nullable=True),
        sa.Column("correlation_id", sa.UUID(), nullable=False),
        sa.Column(
            "event_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "from_state IS NULL OR from_state IN ("
            "'DRAFT', 'IMAGE_UPLOADED', 'IMAGE_REVIEW_REQUIRED', "
            "'IMAGE_VALIDATION_FAILED', 'IMAGE_VALIDATED', "
            "'REGION_ANALYSIS_RUNNING', 'REGION_REVIEW_REQUIRED', "
            "'REGIONS_CONFIRMED', 'PLAN_GENERATION_RUNNING', "
            "'PLAN_REVIEW_REQUIRED', 'PLAN_APPROVED', 'COMPLETED', "
            "'BLOCKED_LOW_CONFIDENCE', 'FAILED_RETRYABLE', "
            "'FAILED_FINAL', 'ABANDONED'"
            ")",
            name=op.f("ck_state_transition_events_from_state_allowed"),
        ),
        sa.CheckConstraint(
            "to_state IN ("
            "'DRAFT', 'IMAGE_UPLOADED', 'IMAGE_REVIEW_REQUIRED', "
            "'IMAGE_VALIDATION_FAILED', 'IMAGE_VALIDATED', "
            "'REGION_ANALYSIS_RUNNING', 'REGION_REVIEW_REQUIRED', "
            "'REGIONS_CONFIRMED', 'PLAN_GENERATION_RUNNING', "
            "'PLAN_REVIEW_REQUIRED', 'PLAN_APPROVED', 'COMPLETED', "
            "'BLOCKED_LOW_CONFIDENCE', 'FAILED_RETRYABLE', "
            "'FAILED_FINAL', 'ABANDONED'"
            ")",
            name=op.f("ck_state_transition_events_to_state_allowed"),
        ),
        sa.CheckConstraint(
            r"event ~ '^[a-z][a-z0-9]*(_[a-z0-9]+)*$'",
            name=op.f("ck_state_transition_events_event_format"),
        ),
        sa.CheckConstraint(
            r"actor_type ~ '^[a-z][a-z0-9]*(_[a-z0-9]+)*$'",
            name=op.f("ck_state_transition_events_actor_type_format"),
        ),
        sa.CheckConstraint(
            "actor_type IN ('user', 'api', 'worker', 'system')",
            name=op.f("ck_state_transition_events_actor_type_allowed"),
        ),
        sa.CheckConstraint(
            "length(actor_principal_id) >= 1 AND actor_principal_id = btrim(actor_principal_id)",
            name=op.f("ck_state_transition_events_actor_principal_id_normalized"),
        ),
        sa.CheckConstraint(
            "actor_display_name_snapshot IS NULL "
            "OR (length(actor_display_name_snapshot) >= 1 "
            "AND actor_display_name_snapshot = btrim(actor_display_name_snapshot))",
            name=op.f("ck_state_transition_events_actor_display_snapshot_normalized"),
        ),
        sa.CheckConstraint(
            "actor_type <> 'user' OR actor_display_name_snapshot IS NOT NULL",
            name=op.f("ck_state_transition_events_user_display_name_required"),
        ),
        sa.CheckConstraint(
            r"reason IS NULL OR reason ~ '^[a-z][a-z0-9]*(_[a-z0-9]+)*$'",
            name=op.f("ck_state_transition_events_reason_format"),
        ),
        sa.CheckConstraint(
            "event <> 'create_project' OR (reason IS NOT NULL AND reason = 'project_created')",
            name=op.f("ck_state_transition_events_create_project_reason"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(event_metadata) = 'object'",
            name=op.f("ck_state_transition_events_event_metadata_is_object"),
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["paint_projects.id"],
            name=op.f("fk_state_transition_events_project_id_paint_projects"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_state_transition_events")),
    )
    op.create_index(
        "ix_state_transition_events_project_created_at_id",
        "state_transition_events",
        ["project_id", "created_at", "id"],
        unique=False,
    )
    op.create_table(
        "command_idempotency_records",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("scope_key", sa.String(length=512), nullable=False),
        sa.Column("principal_id", sa.String(length=128), nullable=False),
        sa.Column("command_type", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.UUID(), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("execution_status", sa.String(length=32), nullable=False),
        sa.Column("resource_type", sa.String(length=64), nullable=True),
        sa.Column("resource_id", sa.UUID(), nullable=True),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column(
            "response_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "length(scope_key) >= 1 AND scope_key = btrim(scope_key)",
            name=op.f("ck_command_idempotency_records_scope_key_normalized"),
        ),
        sa.CheckConstraint(
            "length(principal_id) >= 1 AND principal_id = btrim(principal_id)",
            name=op.f("ck_command_idempotency_records_principal_id_normalized"),
        ),
        sa.CheckConstraint(
            r"command_type ~ '^[a-z][a-z0-9]*(_[a-z0-9]+)*$'",
            name=op.f("ck_command_idempotency_records_command_type_format"),
        ),
        sa.CheckConstraint(
            "payload_hash ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_command_idempotency_records_payload_hash_format"),
        ),
        sa.CheckConstraint(
            r"execution_status ~ '^[a-z][a-z0-9]*(_[a-z0-9]+)*$'",
            name=op.f("ck_command_idempotency_records_execution_status_format"),
        ),
        sa.CheckConstraint(
            "execution_status IN ('in_progress', 'completed')",
            name=op.f("ck_command_idempotency_records_execution_status_allowed"),
        ),
        sa.CheckConstraint(
            "resource_type IS NULL "
            r"OR resource_type ~ '^[a-z][a-z0-9]*(_[a-z0-9]+)*$'",
            name=op.f("ck_command_idempotency_records_resource_type_format"),
        ),
        sa.CheckConstraint(
            "http_status IS NULL OR http_status BETWEEN 100 AND 599",
            name=op.f("ck_command_idempotency_records_http_status_valid"),
        ),
        sa.CheckConstraint(
            "response_snapshot IS NULL OR jsonb_typeof(response_snapshot) = 'object'",
            name=op.f("ck_command_idempotency_records_response_snapshot_is_object"),
        ),
        sa.CheckConstraint(
            "execution_status <> 'completed' "
            "OR (resource_type IS NOT NULL "
            "AND resource_id IS NOT NULL "
            "AND http_status IS NOT NULL "
            "AND response_snapshot IS NOT NULL)",
            name=op.f("ck_command_idempotency_records_result_matches_execution_status"),
        ),
        sa.CheckConstraint(
            "expires_at > created_at",
            name=op.f("ck_command_idempotency_records_expiry_after_creation"),
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name=op.f("pk_command_idempotency_records"),
        ),
        sa.UniqueConstraint(
            "scope_key",
            "idempotency_key",
            name="uq_command_idempotency_records_scope_key_idempotency_key",
        ),
    )
    op.create_index(
        "ix_command_idempotency_records_expires_at",
        "command_idempotency_records",
        ["expires_at"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "ix_command_idempotency_records_expires_at",
        table_name="command_idempotency_records",
    )
    op.drop_table("command_idempotency_records")
    op.drop_index(
        "ix_state_transition_events_project_created_at_id",
        table_name="state_transition_events",
    )
    op.drop_table("state_transition_events")
    op.drop_index(
        "ix_paint_projects_owner_updated_at_id",
        table_name="paint_projects",
    )
    op.drop_table("paint_projects")
