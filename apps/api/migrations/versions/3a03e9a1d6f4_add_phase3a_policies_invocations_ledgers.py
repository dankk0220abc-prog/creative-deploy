"""add phase3a policy budget invocation and ledger foundation

Revision ID: 3a03e9a1d6f4
Revises: 3a02d8f0c5e3
Create Date: 2026-08-05 00:02:00
"""

# ruff: noqa: E501

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "3a03e9a1d6f4"
down_revision: str | Sequence[str] | None = "3a02d8f0c5e3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _created_at() -> sa.Column[sa.DateTime]:
    return sa.Column(
        "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
    )


def _updated_at() -> sa.Column[sa.DateTime]:
    return sa.Column(
        "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
    )


def upgrade() -> None:
    op.execute(
        sa.text("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM paint_projects WHERE id = '00000000-0000-0000-0000-000000000000'::uuid) THEN
                RAISE EXCEPTION USING ERRCODE = '55000', MESSAGE = 'Phase 3A Migration C refused: zero UUID PaintProject exists';
            END IF;
        END
        $$;
    """)
    )
    op.create_check_constraint(
        op.f("ck_paint_projects_id_not_zero_uuid"),
        "paint_projects",
        "id <> '00000000-0000-0000-0000-000000000000'::uuid",
    )

    op.create_table(
        "user_provider_preferences",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("default_provider_definition_id", sa.UUID(), nullable=True),
        sa.Column("default_model_definition_id", sa.UUID(), nullable=True),
        sa.Column("default_credential_id", sa.UUID(), nullable=True),
        sa.Column("timeout_ms", sa.Integer(), server_default=sa.text("30000"), nullable=False),
        sa.Column(
            "streaming_enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column("cost_warning_minor_units", sa.BigInteger(), nullable=True),
        sa.Column("cost_warning_currency", sa.String(32), nullable=True),
        sa.Column("revision", sa.Integer(), server_default=sa.text("1"), nullable=False),
        _updated_at(),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user_accounts.id"],
            name="fk_user_provider_preferences_user",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["default_provider_definition_id"],
            ["provider_definitions.id"],
            name="fk_user_provider_preferences_provider",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["default_model_definition_id"],
            ["model_definitions.id"],
            name="fk_user_provider_preferences_model",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["default_credential_id"],
            ["credential_records.id"],
            name="fk_user_provider_preferences_credential",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_provider_preferences")),
        sa.UniqueConstraint("user_id", name="uq_user_provider_preferences_user"),
    )
    op.create_table(
        "project_model_policies",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("default_provider_definition_id", sa.UUID(), nullable=True),
        sa.Column("default_model_definition_id", sa.UUID(), nullable=True),
        sa.Column("default_credential_id", sa.UUID(), nullable=True),
        sa.Column("per_invocation_limit_minor_units", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(32), nullable=False),
        sa.Column(
            "allow_unknown_cost", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column(
            "unknown_cost_reservation_minor_units",
            sa.BigInteger(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "allow_manual_model_id", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column("allow_fallback", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "require_paid_call_confirmation",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column("updated_by_user_id", sa.UUID(), nullable=False),
        sa.Column("revision", sa.Integer(), server_default=sa.text("1"), nullable=False),
        _updated_at(),
        sa.CheckConstraint(
            "currency = 'FIXTURE_CREDITS'",
            name=op.f("ck_project_model_policies_fixture_currency_only"),
        ),
        sa.CheckConstraint(
            "allow_fallback = false", name=op.f("ck_project_model_policies_fallback_disabled")
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["paint_projects.id"],
            name="fk_project_model_policies_project",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["default_provider_definition_id"],
            ["provider_definitions.id"],
            name="fk_project_model_policies_provider",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["default_model_definition_id"],
            ["model_definitions.id"],
            name="fk_project_model_policies_model",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["default_credential_id"],
            ["credential_records.id"],
            name="fk_project_model_policies_credential",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by_user_id"],
            ["user_accounts.id"],
            name="fk_project_model_policies_updated_by",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_project_model_policies")),
        sa.UniqueConstraint("project_id", name="uq_project_model_policies_project"),
    )
    association_specs = (
        (
            "project_model_policy_providers",
            "provider_definition_id",
            "provider_definitions",
            "provider",
            "providers",
        ),
        (
            "project_model_policy_models",
            "model_definition_id",
            "model_definitions",
            "model",
            "models",
        ),
        (
            "project_model_policy_capabilities",
            "capability_definition_id",
            "capability_definitions",
            "capability",
            "capabilities",
        ),
        (
            "project_model_policy_credentials",
            "credential_record_id",
            "credential_records",
            "credential",
            "credentials",
        ),
    )
    for table_name, target_column, target_table, target_label, short_name in association_specs:
        op.create_table(
            table_name,
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("project_model_policy_id", sa.UUID(), nullable=False),
            sa.Column(target_column, sa.UUID(), nullable=False),
            _created_at(),
            sa.ForeignKeyConstraint(
                ["project_model_policy_id"],
                ["project_model_policies.id"],
                name=f"fk_policy_{short_name}_policy",
                ondelete="RESTRICT",
            ),
            sa.ForeignKeyConstraint(
                [target_column],
                [f"{target_table}.id"],
                name=f"fk_policy_{short_name}_{target_label}",
                ondelete="RESTRICT",
            ),
            sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{table_name}")),
            sa.UniqueConstraint(
                "project_model_policy_id", target_column, name=f"uq_policy_{short_name}_pair"
            ),
        )
        op.create_index(f"ix_policy_{short_name}_{target_label}", table_name, [target_column])

    for table_name, subject_column, subject_table, subject_label in (
        ("user_budget_policies", "user_id", "user_accounts", "user"),
        ("project_budget_policies", "project_id", "paint_projects", "project"),
    ):
        op.create_table(
            table_name,
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column(subject_column, sa.UUID(), nullable=False),
            sa.Column("product_space", sa.String(64), nullable=False),
            sa.Column("currency", sa.String(32), nullable=False),
            sa.Column("enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False),
            sa.Column("per_invocation_limit_minor_units", sa.BigInteger(), nullable=False),
            sa.Column("cumulative_limit_minor_units", sa.BigInteger(), nullable=False),
            sa.Column("window_seconds", sa.Integer(), nullable=False),
            sa.Column(
                "allow_unknown_cost", sa.Boolean(), server_default=sa.text("false"), nullable=False
            ),
            sa.Column(
                "unknown_cost_reservation_minor_units",
                sa.BigInteger(),
                server_default=sa.text("0"),
                nullable=False,
            ),
            sa.Column("revision", sa.Integer(), server_default=sa.text("1"), nullable=False),
            _updated_at(),
            sa.CheckConstraint(
                "currency = 'FIXTURE_CREDITS'", name=op.f(f"ck_{table_name}_fixture_currency_only")
            ),
            sa.ForeignKeyConstraint(
                [subject_column],
                [f"{subject_table}.id"],
                name=f"fk_{table_name}_{subject_label}",
                ondelete="RESTRICT",
            ),
            sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{table_name}")),
            sa.UniqueConstraint(
                subject_column, "product_space", "currency", name=f"uq_{table_name}_scope"
            ),
        )

    for table_name, subject_column, subject_table, subject_label in (
        ("user_budget_counters", "user_id", "user_accounts", "user"),
        ("project_budget_counters", "project_id", "paint_projects", "project"),
    ):
        op.create_table(
            table_name,
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column(subject_column, sa.UUID(), nullable=False),
            sa.Column("product_space", sa.String(64), nullable=False),
            sa.Column("currency", sa.String(32), nullable=False),
            sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
            sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
            sa.Column("limit_minor_units", sa.BigInteger(), nullable=False),
            sa.Column(
                "committed_minor_units",
                sa.BigInteger(),
                server_default=sa.text("0"),
                nullable=False,
            ),
            sa.Column(
                "reserved_minor_units", sa.BigInteger(), server_default=sa.text("0"), nullable=False
            ),
            sa.Column("revision", sa.Integer(), server_default=sa.text("1"), nullable=False),
            sa.CheckConstraint(
                "currency = 'FIXTURE_CREDITS'", name=op.f(f"ck_{table_name}_fixture_currency_only")
            ),
            sa.CheckConstraint(
                "committed_minor_units >= 0 AND reserved_minor_units >= 0 AND limit_minor_units >= 0",
                name=op.f(f"ck_{table_name}_nonnegative"),
            ),
            sa.ForeignKeyConstraint(
                [subject_column],
                [f"{subject_table}.id"],
                name=f"fk_{table_name}_{subject_label}",
                ondelete="RESTRICT",
            ),
            sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{table_name}")),
            sa.UniqueConstraint(
                subject_column,
                "product_space",
                "currency",
                "window_start",
                "window_end",
                name=f"uq_{table_name}_window",
            ),
        )

    op.create_table(
        "invocation_requests",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("requesting_user_id", sa.UUID(), nullable=False),
        sa.Column("product_space", sa.String(64), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=True),
        sa.Column("project_scope_id", sa.UUID(), nullable=False),
        sa.Column("invocation_family", sa.String(64), nullable=False),
        sa.Column("idempotency_key", sa.UUID(), nullable=False),
        sa.Column("canonicalization_version", sa.String(32), nullable=False),
        sa.Column("canonical_request_payload_hash", sa.String(80), nullable=False),
        sa.Column(
            "requested_capabilities", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("requested_provider_definition_id", sa.UUID(), nullable=True),
        sa.Column("requested_model_definition_id", sa.UUID(), nullable=True),
        sa.Column("requested_credential_id", sa.UUID(), nullable=True),
        sa.Column("request_id", sa.UUID(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("total_elapsed_time_limit_ms", sa.Integer(), nullable=False),
        sa.Column("confirmation_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("budget_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("safe_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("final_attempt_id", sa.UUID(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("terminal_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancellation_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("final_error_category", sa.String(64), nullable=True),
        sa.Column("output_reference", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("revision", sa.Integer(), server_default=sa.text("1"), nullable=False),
        _created_at(),
        _updated_at(),
        sa.CheckConstraint(
            "invocation_family IN ('fixture_credential_validation','fixture_model_catalog','fixture_invocation')",
            name=op.f("ck_invocation_requests_family_allowed"),
        ),
        sa.CheckConstraint(
            "canonicalization_version = 'phase3a-v1'",
            name=op.f("ck_invocation_requests_canonicalization_version"),
        ),
        sa.CheckConstraint(
            "canonical_request_payload_hash ~ '^sha256:[0-9a-f]{64}$'",
            name=op.f("ck_invocation_requests_payload_hash"),
        ),
        sa.CheckConstraint(
            "status IN ('pending','admitted','running','succeeded','failed','cancelled','outcome_unknown')",
            name=op.f("ck_invocation_requests_status_allowed"),
        ),
        sa.CheckConstraint(
            "(project_id IS NULL AND project_scope_id = '00000000-0000-0000-0000-000000000000'::uuid) OR (project_id IS NOT NULL AND project_id = project_scope_id AND project_scope_id <> '00000000-0000-0000-0000-000000000000'::uuid)",
            name=op.f("ck_invocation_requests_project_scope"),
        ),
        sa.ForeignKeyConstraint(
            ["requesting_user_id"],
            ["user_accounts.id"],
            name="fk_invocation_requests_user",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["paint_projects.id"],
            name="fk_invocation_requests_project",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["requested_provider_definition_id"],
            ["provider_definitions.id"],
            name=op.f("fk_invreq_requested_provider_definition"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["requested_model_definition_id"],
            ["model_definitions.id"],
            name=op.f("fk_invreq_requested_model_definition"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["requested_credential_id"],
            ["credential_records.id"],
            name=op.f("fk_invreq_requested_credential"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_invocation_requests")),
        sa.UniqueConstraint(
            "requesting_user_id",
            "product_space",
            "project_scope_id",
            "invocation_family",
            "idempotency_key",
            name="uq_invocation_requests_idempotency_scope",
        ),
    )
    op.create_index(
        "ix_invocation_requests_user_created",
        "invocation_requests",
        ["requesting_user_id", "created_at"],
    )
    op.create_index(
        "ix_invocation_requests_project_created",
        "invocation_requests",
        ["project_id", "created_at"],
    )
    op.create_table(
        "invocation_attempts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("invocation_id", sa.UUID(), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("provider_definition_id", sa.UUID(), nullable=False),
        sa.Column("model_definition_id", sa.UUID(), nullable=False),
        sa.Column("provider_key", sa.String(64), nullable=False),
        sa.Column("model_id", sa.String(160), nullable=False),
        sa.Column("adapter_version", sa.String(64), nullable=False),
        sa.Column("capability_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("credential_id", sa.UUID(), nullable=True),
        sa.Column("credential_encryption_version_snapshot", sa.String(64), nullable=True),
        sa.Column(
            "temporary_credential", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column("retry_of_attempt_id", sa.UUID(), nullable=True),
        sa.Column(
            "fallback_decision", sa.String(32), server_default=sa.text("'disabled'"), nullable=False
        ),
        sa.Column("currency", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("terminal_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancellation_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("final_error_category", sa.String(64), nullable=True),
        sa.Column("output_reference", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "safe_provider_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("revision", sa.Integer(), server_default=sa.text("1"), nullable=False),
        _created_at(),
        sa.CheckConstraint(
            "status IN ('created','admitted','running','succeeded','failed','cancelled','outcome_unknown')",
            name=op.f("ck_invocation_attempts_status_allowed"),
        ),
        sa.CheckConstraint(
            "currency = 'FIXTURE_CREDITS'",
            name=op.f("ck_invocation_attempts_fixture_currency_only"),
        ),
        sa.ForeignKeyConstraint(
            ["invocation_id"],
            ["invocation_requests.id"],
            name="fk_invocation_attempts_invocation",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["provider_definition_id"],
            ["provider_definitions.id"],
            name="fk_invocation_attempts_provider",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["model_definition_id"],
            ["model_definitions.id"],
            name="fk_invocation_attempts_model",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["credential_id"],
            ["credential_records.id"],
            name="fk_invocation_attempts_credential",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["retry_of_attempt_id"],
            ["invocation_attempts.id"],
            name=op.f("fk_invocation_attempts_retry_of_attempt_id_invocation_attempts"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_invocation_attempts")),
        sa.UniqueConstraint(
            "invocation_id", "attempt_number", name="uq_invocation_attempts_number"
        ),
        sa.UniqueConstraint("invocation_id", "id", name="uq_invocation_attempts_invocation_id"),
    )
    op.create_index(
        "uq_invocation_attempts_active",
        "invocation_attempts",
        ["invocation_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('created','admitted','running')"),
    )
    op.create_foreign_key(
        "fk_invocation_requests_final_attempt",
        "invocation_requests",
        "invocation_attempts",
        ["id", "final_attempt_id"],
        ["invocation_id", "id"],
        ondelete="RESTRICT",
    )

    op.create_table(
        "budget_reservations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("invocation_id", sa.UUID(), nullable=False),
        sa.Column("attempt_id", sa.UUID(), nullable=False),
        sa.Column("user_counter_id", sa.UUID(), nullable=False),
        sa.Column("project_counter_id", sa.UUID(), nullable=True),
        sa.Column("currency", sa.String(32), nullable=False),
        sa.Column("reserved_amount", sa.BigInteger(), nullable=False),
        sa.Column("state", sa.String(32), nullable=False),
        _created_at(),
        sa.Column("admission_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("dispatch_committed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("settled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revision", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.CheckConstraint(
            "state IN ('reserved','dispatch_committed','settled','released','reconciliation_required')",
            name=op.f("ck_budget_reservations_state_allowed"),
        ),
        sa.CheckConstraint(
            "currency = 'FIXTURE_CREDITS'",
            name=op.f("ck_budget_reservations_fixture_currency_only"),
        ),
        sa.ForeignKeyConstraint(
            ["invocation_id"],
            ["invocation_requests.id"],
            name="fk_budget_reservations_invocation",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["attempt_id"],
            ["invocation_attempts.id"],
            name="fk_budget_reservations_attempt",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["user_counter_id"],
            ["user_budget_counters.id"],
            name="fk_budget_reservations_user_counter",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_counter_id"],
            ["project_budget_counters.id"],
            name="fk_budget_reservations_project_counter",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_budget_reservations")),
        sa.UniqueConstraint("attempt_id", name="uq_budget_reservations_attempt"),
    )
    op.create_table(
        "ai_invocation_events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("invocation_id", sa.UUID(), nullable=False),
        sa.Column("attempt_id", sa.UUID(), nullable=True),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("from_status", sa.String(32), nullable=True),
        sa.Column("to_status", sa.String(32), nullable=False),
        sa.Column("safe_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        _created_at(),
        sa.ForeignKeyConstraint(
            ["invocation_id"],
            ["invocation_requests.id"],
            name="fk_ai_invocation_events_invocation",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["attempt_id"],
            ["invocation_attempts.id"],
            name="fk_ai_invocation_events_attempt",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ai_invocation_events")),
    )
    op.create_index(
        "ix_ai_invocation_events_invocation_created",
        "ai_invocation_events",
        ["invocation_id", "created_at"],
    )
    op.create_table(
        "ai_usage_ledger",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("invocation_id", sa.UUID(), nullable=False),
        sa.Column("attempt_id", sa.UUID(), nullable=False),
        sa.Column("provider_definition_id", sa.UUID(), nullable=False),
        sa.Column("model_definition_id", sa.UUID(), nullable=False),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("canonical_sequence", sa.Integer(), nullable=False),
        sa.Column("input_units", sa.BigInteger(), nullable=False),
        sa.Column("output_units", sa.BigInteger(), nullable=False),
        sa.Column("safe_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        _created_at(),
        sa.ForeignKeyConstraint(
            ["invocation_id"],
            ["invocation_requests.id"],
            name="fk_ai_usage_ledger_invocation",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["attempt_id"],
            ["invocation_attempts.id"],
            name="fk_ai_usage_ledger_attempt",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["provider_definition_id"],
            ["provider_definitions.id"],
            name="fk_ai_usage_ledger_provider",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["model_definition_id"],
            ["model_definitions.id"],
            name="fk_ai_usage_ledger_model",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ai_usage_ledger")),
        sa.UniqueConstraint(
            "attempt_id", "source", "canonical_sequence", name="uq_ai_usage_ledger_dedupe"
        ),
    )
    op.create_table(
        "ai_cost_ledger",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("invocation_id", sa.UUID(), nullable=False),
        sa.Column("attempt_id", sa.UUID(), nullable=False),
        sa.Column("provider_definition_id", sa.UUID(), nullable=False),
        sa.Column("model_definition_id", sa.UUID(), nullable=False),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("canonical_sequence", sa.Integer(), nullable=False),
        sa.Column("amount_minor_units", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(32), nullable=False),
        _created_at(),
        sa.CheckConstraint(
            "currency = 'FIXTURE_CREDITS'", name=op.f("ck_ai_cost_ledger_fixture_currency_only")
        ),
        sa.ForeignKeyConstraint(
            ["invocation_id"],
            ["invocation_requests.id"],
            name="fk_ai_cost_ledger_invocation",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["attempt_id"],
            ["invocation_attempts.id"],
            name="fk_ai_cost_ledger_attempt",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["provider_definition_id"],
            ["provider_definitions.id"],
            name="fk_ai_cost_ledger_provider",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["model_definition_id"],
            ["model_definitions.id"],
            name="fk_ai_cost_ledger_model",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ai_cost_ledger")),
        sa.UniqueConstraint(
            "attempt_id", "source", "canonical_sequence", name="uq_ai_cost_ledger_dedupe"
        ),
    )
    op.create_table(
        "ai_audit_events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("actor_user_id", sa.UUID(), nullable=False),
        sa.Column("product_space", sa.String(64), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=True),
        sa.Column("credential_id", sa.UUID(), nullable=True),
        sa.Column("invocation_id", sa.UUID(), nullable=True),
        sa.Column("attempt_id", sa.UUID(), nullable=True),
        sa.Column("provider_definition_id", sa.UUID(), nullable=True),
        sa.Column("model_definition_id", sa.UUID(), nullable=True),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("outcome", sa.String(32), nullable=False),
        sa.Column("request_id", sa.UUID(), nullable=False),
        sa.Column("safe_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        _created_at(),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["user_accounts.id"],
            name="fk_ai_audit_events_actor",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["paint_projects.id"],
            name="fk_ai_audit_events_project",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["credential_id"],
            ["credential_records.id"],
            name="fk_ai_audit_events_credential",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["invocation_id"],
            ["invocation_requests.id"],
            name="fk_ai_audit_events_invocation",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["attempt_id"],
            ["invocation_attempts.id"],
            name="fk_ai_audit_events_attempt",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["provider_definition_id"],
            ["provider_definitions.id"],
            name="fk_ai_audit_events_provider",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["model_definition_id"],
            ["model_definitions.id"],
            name="fk_ai_audit_events_model",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ai_audit_events")),
    )
    op.create_index(
        "ix_ai_audit_events_actor_created", "ai_audit_events", ["actor_user_id", "created_at"]
    )
    op.create_index(
        "ix_ai_audit_events_project_created", "ai_audit_events", ["project_id", "created_at"]
    )
    op.create_table(
        "ai_command_idempotency_records",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("requesting_user_id", sa.UUID(), nullable=False),
        sa.Column("command_scope", sa.String(256), nullable=False),
        sa.Column("idempotency_key", sa.UUID(), nullable=False),
        sa.Column("payload_hash", sa.String(80), nullable=False),
        sa.Column("response_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("http_status", sa.Integer(), nullable=False),
        _created_at(),
        sa.ForeignKeyConstraint(
            ["requesting_user_id"],
            ["user_accounts.id"],
            name="fk_ai_command_idempotency_user",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ai_command_idempotency_records")),
        sa.UniqueConstraint(
            "requesting_user_id",
            "command_scope",
            "idempotency_key",
            name="uq_ai_command_idempotency_scope",
        ),
    )
    op.execute(
        sa.text("""
        CREATE FUNCTION phase3a_reject_append_only_mutation() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION USING ERRCODE = '55000', MESSAGE = TG_TABLE_NAME || ' is append-only';
        END
        $$;
        CREATE TRIGGER ai_invocation_events_append_only
        BEFORE UPDATE OR DELETE ON ai_invocation_events
        FOR EACH ROW EXECUTE FUNCTION phase3a_reject_append_only_mutation();
        CREATE TRIGGER ai_usage_ledger_append_only
        BEFORE UPDATE OR DELETE ON ai_usage_ledger
        FOR EACH ROW EXECUTE FUNCTION phase3a_reject_append_only_mutation();
        CREATE TRIGGER ai_cost_ledger_append_only
        BEFORE UPDATE OR DELETE ON ai_cost_ledger
        FOR EACH ROW EXECUTE FUNCTION phase3a_reject_append_only_mutation();
        CREATE TRIGGER ai_audit_events_append_only
        BEFORE UPDATE OR DELETE ON ai_audit_events
        FOR EACH ROW EXECUTE FUNCTION phase3a_reject_append_only_mutation();
    """)
    )
    op.execute(
        sa.text("""
        CREATE FUNCTION phase3a_verify_final_attempt() RETURNS trigger
        LANGUAGE plpgsql AS $$
        DECLARE final_status text;
        BEGIN
            IF OLD.final_attempt_id IS NOT NULL AND NEW.final_attempt_id IS DISTINCT FROM OLD.final_attempt_id THEN
                RAISE EXCEPTION USING ERRCODE = '23514', MESSAGE = 'final_attempt_id is write-once';
            END IF;
            IF NEW.final_attempt_id IS NOT NULL THEN
                IF NEW.status NOT IN ('succeeded', 'failed', 'cancelled', 'outcome_unknown') THEN
                    RAISE EXCEPTION USING ERRCODE = '23514', MESSAGE = 'final_attempt_id requires terminal invocation';
                END IF;
                SELECT status INTO final_status FROM invocation_attempts WHERE id = NEW.final_attempt_id AND invocation_id = NEW.id;
                IF final_status IS DISTINCT FROM NEW.status THEN
                    RAISE EXCEPTION USING ERRCODE = '23514', MESSAGE = 'final_attempt_id requires matching terminal same-invocation attempt';
                END IF;
            END IF;
            RETURN NEW;
        END
        $$;
        CREATE CONSTRAINT TRIGGER invocation_final_attempt_write_once
        AFTER UPDATE OF final_attempt_id, status ON invocation_requests
        DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION phase3a_verify_final_attempt();
    """)
    )


def downgrade() -> None:
    protected_tables = (
        "project_model_policy_providers",
        "project_model_policy_models",
        "project_model_policy_capabilities",
        "project_model_policy_credentials",
        "project_model_policies",
        "user_provider_preferences",
        "user_budget_policies",
        "project_budget_policies",
        "user_budget_counters",
        "project_budget_counters",
        "budget_reservations",
        "ai_invocation_events",
        "ai_usage_ledger",
        "ai_cost_ledger",
        "ai_audit_events",
        "ai_command_idempotency_records",
        "invocation_attempts",
        "invocation_requests",
    )
    checks = " OR ".join(f"EXISTS (SELECT 1 FROM {table})" for table in protected_tables)
    op.execute(
        sa.text(f"""
        DO $$
        BEGIN
            IF {checks} THEN
                RAISE EXCEPTION USING ERRCODE = '55000', MESSAGE = 'Phase 3A Migration C downgrade refused: governed policy, budget, invocation, or ledger facts exist';
            END IF;
        END
        $$;
    """)
    )
    op.execute(sa.text("DROP FUNCTION phase3a_verify_final_attempt() CASCADE"))
    op.execute(sa.text("DROP FUNCTION phase3a_reject_append_only_mutation() CASCADE"))
    op.drop_table("ai_command_idempotency_records")
    op.drop_index("ix_ai_audit_events_project_created", table_name="ai_audit_events")
    op.drop_index("ix_ai_audit_events_actor_created", table_name="ai_audit_events")
    op.drop_table("ai_audit_events")
    op.drop_table("ai_cost_ledger")
    op.drop_table("ai_usage_ledger")
    op.drop_index("ix_ai_invocation_events_invocation_created", table_name="ai_invocation_events")
    op.drop_table("ai_invocation_events")
    op.drop_table("budget_reservations")
    op.drop_constraint(
        "fk_invocation_requests_final_attempt", "invocation_requests", type_="foreignkey"
    )
    op.drop_index("uq_invocation_attempts_active", table_name="invocation_attempts")
    op.drop_table("invocation_attempts")
    op.drop_index("ix_invocation_requests_project_created", table_name="invocation_requests")
    op.drop_index("ix_invocation_requests_user_created", table_name="invocation_requests")
    op.drop_table("invocation_requests")
    op.drop_table("project_budget_counters")
    op.drop_table("user_budget_counters")
    op.drop_table("project_budget_policies")
    op.drop_table("user_budget_policies")
    for table_name, target_label, short_name in (
        ("project_model_policy_credentials", "credential", "credentials"),
        ("project_model_policy_capabilities", "capability", "capabilities"),
        ("project_model_policy_models", "model", "models"),
        ("project_model_policy_providers", "provider", "providers"),
    ):
        op.drop_index(f"ix_policy_{short_name}_{target_label}", table_name=table_name)
        op.drop_table(table_name)
    op.drop_table("project_model_policies")
    op.drop_table("user_provider_preferences")
    op.drop_constraint(op.f("ck_paint_projects_id_not_zero_uuid"), "paint_projects", type_="check")
