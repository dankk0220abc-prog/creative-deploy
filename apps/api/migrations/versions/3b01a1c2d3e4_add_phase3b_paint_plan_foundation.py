"""add Phase 3B multimodal provider and Paint Plan foundation

Revision ID: 3b01a1c2d3e4
Revises: 3a04fab2e7a5
Create Date: 2026-08-09 00:00:00
"""

# ruff: noqa: E501

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "3b01a1c2d3e4"
down_revision: str | Sequence[str] | None = "3a04fab2e7a5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OPENAI_PROVIDER_ID = uuid.UUID("3b000000-0000-4000-8000-000000000001")
OPENAI_MODEL_ID = uuid.UUID("3b000000-0000-4000-8000-000000000101")
OPENAI_PRICING_ID = uuid.UUID("3b000000-0000-4000-8000-000000000201")
PAINT_PLAN_PROMPT_ID = uuid.UUID("3b000000-0000-4000-8000-000000000301")
TEXT_CAPABILITY_ID = uuid.UUID("3a000000-0000-4000-8000-000000001001")
VISION_CAPABILITY_ID = uuid.UUID("3a000000-0000-4000-8000-000000001002")
STRUCTURED_CAPABILITY_ID = uuid.UUID("3a000000-0000-4000-8000-000000001003")
FIXED_TIME = datetime(2026, 8, 9, tzinfo=UTC)
PRICING_EFFECTIVE_TIME = datetime(2026, 3, 17, tzinfo=UTC)
PAINT_PLAN_PROMPT_BODY = (
    "Analyze only the governed PaintPilot project images and approved semantic regions. "
    "Return exactly the paint-plan.v1 JSON schema. Produce one instruction for every "
    "paint region, produce no instruction for excluded regions, preserve every supplied "
    "region identifier, and state uncertainty without claiming verified colors, materials, "
    "safety, cost, or real-world results."
)
PAINT_PLAN_PROMPT_HASH = "8f946b8ae444637aa56b8624118f45b539eb314bf5bb6ed9013e7b89b0561de6"

CURRENCY_CHECKS = (
    (
        "model_definitions",
        "ck_model_definitions_fixture_currency_only",
        "pricing_currency IS NULL OR pricing_currency IN ('FIXTURE_CREDITS','USD')",
        "pricing_currency IS NULL OR pricing_currency = 'FIXTURE_CREDITS'",
    ),
    (
        "project_model_policies",
        "ck_project_model_policies_fixture_currency_only",
        "currency IN ('FIXTURE_CREDITS','USD')",
        "currency = 'FIXTURE_CREDITS'",
    ),
    (
        "user_budget_policies",
        "ck_user_budget_policies_fixture_currency_only",
        "currency IN ('FIXTURE_CREDITS','USD')",
        "currency = 'FIXTURE_CREDITS'",
    ),
    (
        "project_budget_policies",
        "ck_project_budget_policies_fixture_currency_only",
        "currency IN ('FIXTURE_CREDITS','USD')",
        "currency = 'FIXTURE_CREDITS'",
    ),
    (
        "user_budget_counters",
        "ck_user_budget_counters_fixture_currency_only",
        "currency IN ('FIXTURE_CREDITS','USD')",
        "currency = 'FIXTURE_CREDITS'",
    ),
    (
        "project_budget_counters",
        "ck_project_budget_counters_fixture_currency_only",
        "currency IN ('FIXTURE_CREDITS','USD')",
        "currency = 'FIXTURE_CREDITS'",
    ),
    (
        "invocation_attempts",
        "ck_invocation_attempts_fixture_currency_only",
        "currency IN ('FIXTURE_CREDITS','USD')",
        "currency = 'FIXTURE_CREDITS'",
    ),
    (
        "budget_reservations",
        "ck_budget_reservations_fixture_currency_only",
        "currency IN ('FIXTURE_CREDITS','USD')",
        "currency = 'FIXTURE_CREDITS'",
    ),
    (
        "ai_cost_ledger",
        "ck_ai_cost_ledger_fixture_currency_only",
        "currency IN ('FIXTURE_CREDITS','USD')",
        "currency = 'FIXTURE_CREDITS'",
    ),
)


def _created_at() -> sa.Column[datetime]:
    return sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        server_default=sa.text("now()"),
        nullable=False,
    )


def _replace_check(table_name: str, constraint_name: str, condition: str) -> None:
    op.drop_constraint(op.f(constraint_name), table_name, type_="check")
    op.create_check_constraint(op.f(constraint_name), table_name, condition)


def _expand_phase3a_contracts() -> None:
    for table_name, constraint_name, expanded, _fixture_only in CURRENCY_CHECKS:
        _replace_check(table_name, constraint_name, expanded)

    _replace_check(
        "invocation_requests",
        "ck_invocation_requests_family_allowed",
        "invocation_family IN ('fixture_credential_validation','fixture_model_catalog','fixture_invocation','paint_plan_generation')",
    )

    op.add_column(
        "invocation_attempts",
        sa.Column(
            "provider_request_id_status",
            sa.String(32),
            server_default=sa.text("'absent'"),
            nullable=False,
        ),
    )
    op.add_column(
        "invocation_attempts",
        sa.Column("provider_request_id", sa.String(200), nullable=True),
    )
    op.create_check_constraint(
        op.f("ck_invocation_attempts_provider_request_id_status_allowed"),
        "invocation_attempts",
        "provider_request_id_status IN ('absent','provided','unavailable')",
    )
    op.create_check_constraint(
        op.f("ck_invocation_attempts_provider_request_id_consistent"),
        "invocation_attempts",
        "(provider_request_id_status = 'provided' "
        "AND provider_request_id IS NOT NULL "
        "AND length(provider_request_id) BETWEEN 1 AND 200 "
        "AND provider_request_id = btrim(provider_request_id) "
        "AND provider_request_id !~ '[[:cntrl:]]') "
        "OR (provider_request_id_status IN ('absent','unavailable') "
        "AND provider_request_id IS NULL)",
    )

    op.add_column(
        "ai_usage_ledger",
        sa.Column(
            "measurement_status",
            sa.String(32),
            server_default=sa.text("'measured'"),
            nullable=False,
        ),
    )
    op.alter_column(
        "ai_usage_ledger",
        "input_units",
        existing_type=sa.BigInteger(),
        nullable=True,
    )
    op.alter_column(
        "ai_usage_ledger",
        "output_units",
        existing_type=sa.BigInteger(),
        nullable=True,
    )
    op.create_check_constraint(
        op.f("ck_ai_usage_ledger_measurement_status_allowed"),
        "ai_usage_ledger",
        "measurement_status IN ('measured','unavailable')",
    )
    op.create_check_constraint(
        op.f("ck_ai_usage_ledger_measurement_consistent"),
        "ai_usage_ledger",
        "(measurement_status = 'measured' "
        "AND input_units IS NOT NULL AND input_units >= 0 "
        "AND output_units IS NOT NULL AND output_units >= 0) "
        "OR (measurement_status = 'unavailable' "
        "AND input_units IS NULL AND output_units IS NULL)",
    )

    op.add_column(
        "ai_cost_ledger",
        sa.Column(
            "measurement_status",
            sa.String(32),
            server_default=sa.text("'measured'"),
            nullable=False,
        ),
    )
    op.alter_column(
        "ai_cost_ledger",
        "amount_minor_units",
        existing_type=sa.BigInteger(),
        nullable=True,
    )
    op.create_check_constraint(
        op.f("ck_ai_cost_ledger_measurement_status_allowed"),
        "ai_cost_ledger",
        "measurement_status IN ('estimated','measured','unavailable')",
    )
    op.create_check_constraint(
        op.f("ck_ai_cost_ledger_measurement_consistent"),
        "ai_cost_ledger",
        "(measurement_status IN ('estimated','measured') "
        "AND amount_minor_units IS NOT NULL AND amount_minor_units >= 0) "
        "OR (measurement_status = 'unavailable' AND amount_minor_units IS NULL)",
    )


def _create_phase3b_tables() -> None:
    op.create_table(
        "provider_pricing_snapshots",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("provider_definition_id", sa.UUID(), nullable=False),
        sa.Column("model_definition_id", sa.UUID(), nullable=False),
        sa.Column("provider_key", sa.String(64), nullable=False),
        sa.Column("model_id", sa.String(160), nullable=False),
        sa.Column("pricing_version", sa.String(64), nullable=False),
        sa.Column("currency", sa.String(32), nullable=False),
        sa.Column("unit_basis", sa.String(32), nullable=False),
        sa.Column("input_minor_units_per_million", sa.BigInteger(), nullable=False),
        sa.Column("output_minor_units_per_million", sa.BigInteger(), nullable=False),
        sa.Column("source_url", sa.String(512), nullable=False),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        _created_at(),
        sa.CheckConstraint(
            "length(provider_key) BETWEEN 1 AND 64 "
            "AND provider_key = btrim(provider_key) "
            "AND provider_key !~ '[<>]' AND provider_key !~ '[[:cntrl:]]'",
            name=op.f("ck_provider_pricing_snapshots_provider_key_safe"),
        ),
        sa.CheckConstraint(
            "length(model_id) BETWEEN 1 AND 160 "
            "AND model_id = btrim(model_id) "
            "AND model_id !~ '[<>]' AND model_id !~ '[[:cntrl:]]'",
            name=op.f("ck_provider_pricing_snapshots_model_id_safe"),
        ),
        sa.CheckConstraint(
            "length(pricing_version) BETWEEN 1 AND 64 "
            "AND pricing_version = btrim(pricing_version) "
            "AND pricing_version !~ '[<>]' AND pricing_version !~ '[[:cntrl:]]'",
            name=op.f("ck_provider_pricing_snapshots_version_safe"),
        ),
        sa.CheckConstraint(
            "currency = 'USD'",
            name=op.f("ck_provider_pricing_snapshots_currency_usd"),
        ),
        sa.CheckConstraint(
            "unit_basis = 'per_million_tokens'",
            name=op.f("ck_provider_pricing_snapshots_unit_basis_allowed"),
        ),
        sa.CheckConstraint(
            "input_minor_units_per_million >= 0 AND output_minor_units_per_million >= 0",
            name=op.f("ck_provider_pricing_snapshots_prices_nonnegative"),
        ),
        sa.CheckConstraint(
            "length(source_url) BETWEEN 1 AND 512 "
            "AND source_url = btrim(source_url) "
            "AND source_url ~ '^https://[^[:space:]<>]+$'",
            name=op.f("ck_provider_pricing_snapshots_source_url_safe"),
        ),
        sa.CheckConstraint(
            "effective_at <= captured_at",
            name=op.f("ck_provider_pricing_snapshots_time_order"),
        ),
        sa.ForeignKeyConstraint(
            ["provider_definition_id"],
            ["provider_definitions.id"],
            name="fk_provider_pricing_snapshots_provider",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["model_definition_id"],
            ["model_definitions.id"],
            name="fk_provider_pricing_snapshots_model",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_provider_pricing_snapshots")),
        sa.UniqueConstraint(
            "provider_definition_id",
            "model_definition_id",
            "pricing_version",
            name="uq_provider_pricing_snapshots_provider_model_version",
        ),
        sa.UniqueConstraint(
            "id",
            "provider_definition_id",
            "model_definition_id",
            name="uq_provider_pricing_snapshots_exact_model",
        ),
    )
    op.create_index(
        "ix_provider_pricing_snapshots_model_effective",
        "provider_pricing_snapshots",
        ["model_definition_id", "effective_at"],
    )

    op.create_table(
        "prompt_template_definitions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("template_key", sa.String(64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("schema_version", sa.String(64), nullable=False),
        sa.Column("template_body", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        _created_at(),
        sa.CheckConstraint(
            "template_key ~ '^[a-z0-9]+(-[a-z0-9]+)*$'",
            name=op.f("ck_prompt_template_definitions_key_format"),
        ),
        sa.CheckConstraint(
            "version >= 1",
            name=op.f("ck_prompt_template_definitions_version_positive"),
        ),
        sa.CheckConstraint(
            "schema_version ~ '^[a-z0-9]+(-[a-z0-9]+)*\\.v[1-9][0-9]*$'",
            name=op.f("ck_prompt_template_definitions_schema_format"),
        ),
        sa.CheckConstraint(
            "length(template_body) BETWEEN 1 AND 12000 AND template_body = btrim(template_body)",
            name=op.f("ck_prompt_template_definitions_body_bounded"),
        ),
        sa.CheckConstraint(
            "content_hash ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_prompt_template_definitions_hash_format"),
        ),
        sa.CheckConstraint(
            "status IN ('active','retired')",
            name=op.f("ck_prompt_template_definitions_status_allowed"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_prompt_template_definitions")),
        sa.UniqueConstraint(
            "template_key",
            "version",
            name="uq_prompt_template_definitions_key_version",
        ),
        sa.UniqueConstraint(
            "id",
            "template_key",
            "version",
            "content_hash",
            "schema_version",
            name="uq_prompt_template_definitions_exact_contract",
        ),
    )

    op.create_table(
        "paint_plans",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("owner_principal_id", sa.String(128), nullable=False),
        sa.Column("paint_project_id", sa.UUID(), nullable=False),
        sa.Column("lineage_id", sa.UUID(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("lineage_revision", sa.Integer(), nullable=False),
        sa.Column("revision_kind", sa.String(32), nullable=False),
        sa.Column("lifecycle", sa.String(32), nullable=False),
        sa.Column("parent_plan_id", sa.UUID(), nullable=True),
        sa.Column("source_readiness_review_id", sa.UUID(), nullable=False),
        sa.Column("source_readiness_review_version", sa.Integer(), nullable=False),
        sa.Column("source_image_set_fingerprint", sa.String(64), nullable=False),
        sa.Column("source_region_set_id", sa.UUID(), nullable=False),
        sa.Column("source_region_set_version", sa.Integer(), nullable=False),
        sa.Column("source_geometry_fingerprint", sa.String(64), nullable=False),
        sa.Column("source_invocation_id", sa.UUID(), nullable=False),
        sa.Column("source_attempt_id", sa.UUID(), nullable=False),
        sa.Column("provider_definition_id", sa.UUID(), nullable=False),
        sa.Column("provider_key_snapshot", sa.String(64), nullable=False),
        sa.Column("provider_revision_snapshot", sa.Integer(), nullable=False),
        sa.Column("model_definition_id", sa.UUID(), nullable=False),
        sa.Column("model_id_snapshot", sa.String(160), nullable=False),
        sa.Column("model_revision_snapshot", sa.Integer(), nullable=False),
        sa.Column("provider_pricing_snapshot_id", sa.UUID(), nullable=True),
        sa.Column("prompt_template_definition_id", sa.UUID(), nullable=False),
        sa.Column("prompt_template_key_snapshot", sa.String(64), nullable=False),
        sa.Column("prompt_template_version_snapshot", sa.Integer(), nullable=False),
        sa.Column("prompt_content_hash", sa.String(64), nullable=False),
        sa.Column("response_schema_version", sa.String(64), nullable=False),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("overall_approach", sa.String(2000), nullable=False),
        sa.Column(
            "safety_notes",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("instruction_count", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("created_by_actor_type", sa.String(32), nullable=False),
        sa.Column("created_by_actor_id", sa.String(128), nullable=False),
        sa.Column("created_by_actor_display_name_snapshot", sa.String(200), nullable=False),
        _created_at(),
        sa.CheckConstraint(
            "version >= 1 AND lineage_revision >= 1",
            name=op.f("ck_paint_plans_revisions_positive"),
        ),
        sa.CheckConstraint(
            "revision_kind IN ('generated', 'edited', 'regenerated')",
            name=op.f("ck_paint_plans_revision_kind_allowed"),
        ),
        sa.CheckConstraint(
            "lifecycle IN ('generated', 'edited', 'under_review', 'approved', 'rejected', 'superseded')",
            name=op.f("ck_paint_plans_lifecycle_allowed"),
        ),
        sa.CheckConstraint(
            "(revision_kind = 'generated' AND lineage_revision = 1 "
            "AND lineage_id = id AND parent_plan_id IS NULL) "
            "OR (revision_kind = 'edited' AND lineage_revision >= 2 "
            "AND lineage_id <> id AND parent_plan_id IS NOT NULL) "
            "OR (revision_kind = 'regenerated' AND lineage_revision = 1 "
            "AND lineage_id = id AND parent_plan_id IS NOT NULL)",
            name=op.f("ck_paint_plans_lineage_consistent"),
        ),
        sa.CheckConstraint(
            "source_readiness_review_version >= 1 AND source_region_set_version >= 1",
            name=op.f("ck_paint_plans_source_versions_positive"),
        ),
        sa.CheckConstraint(
            "source_image_set_fingerprint ~ '^[0-9a-f]{64}$' "
            "AND source_geometry_fingerprint ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_paint_plans_source_fingerprints_format"),
        ),
        sa.CheckConstraint(
            "length(provider_key_snapshot) BETWEEN 1 AND 64 "
            "AND provider_key_snapshot = btrim(provider_key_snapshot) "
            "AND length(model_id_snapshot) BETWEEN 1 AND 160 "
            "AND model_id_snapshot = btrim(model_id_snapshot) "
            "AND provider_key_snapshot !~ '[<>]' AND model_id_snapshot !~ '[<>]' "
            "AND provider_key_snapshot !~ '[[:cntrl:]]' "
            "AND model_id_snapshot !~ '[[:cntrl:]]'",
            name=op.f("ck_paint_plans_model_snapshots_safe"),
        ),
        sa.CheckConstraint(
            "provider_revision_snapshot >= 1 AND model_revision_snapshot >= 1",
            name=op.f("ck_paint_plans_model_revisions_positive"),
        ),
        sa.CheckConstraint(
            "provider_pricing_snapshot_id IS NOT NULL OR provider_key_snapshot = 'fixture_local'",
            name=op.f("ck_paint_plans_pricing_snapshot_required"),
        ),
        sa.CheckConstraint(
            "prompt_template_key_snapshot ~ '^[a-z0-9]+(-[a-z0-9]+)*$' "
            "AND prompt_template_version_snapshot >= 1 "
            "AND prompt_content_hash ~ '^[0-9a-f]{64}$' "
            "AND response_schema_version ~ "
            "'^[a-z0-9]+(-[a-z0-9]+)*\\.v[1-9][0-9]*$'",
            name=op.f("ck_paint_plans_prompt_contract_format"),
        ),
        sa.CheckConstraint(
            "length(title) BETWEEN 1 AND 160 AND title = btrim(title) "
            "AND title !~ '[<>]' AND title !~ '[[:cntrl:]]'",
            name=op.f("ck_paint_plans_title_safe"),
        ),
        sa.CheckConstraint(
            "length(overall_approach) BETWEEN 1 AND 2000 "
            "AND overall_approach = btrim(overall_approach) "
            "AND overall_approach !~ '[<>]' "
            "AND overall_approach !~ '[[:cntrl:]]'",
            name=op.f("ck_paint_plans_overall_approach_safe"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(safety_notes) = 'array' "
            "AND jsonb_array_length(safety_notes) <= 16 "
            "AND octet_length(safety_notes::text) <= 7000 "
            "AND NOT jsonb_path_exists(safety_notes, '$[*] ? (@.type() != \"string\")')",
            name=op.f("ck_paint_plans_safety_notes_bounded"),
        ),
        sa.CheckConstraint(
            "instruction_count BETWEEN 1 AND 128",
            name=op.f("ck_paint_plans_instruction_count_allowed"),
        ),
        sa.CheckConstraint(
            "content_hash ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_paint_plans_content_hash_format"),
        ),
        sa.CheckConstraint(
            "created_by_actor_type IN ('provider','user')",
            name=op.f("ck_paint_plans_actor_type_allowed"),
        ),
        sa.CheckConstraint(
            "length(created_by_actor_id) BETWEEN 1 AND 128 "
            "AND created_by_actor_id = btrim(created_by_actor_id) "
            "AND created_by_actor_id !~ '[[:cntrl:]]' "
            "AND length(created_by_actor_display_name_snapshot) BETWEEN 1 AND 200 "
            "AND created_by_actor_display_name_snapshot = "
            "btrim(created_by_actor_display_name_snapshot) "
            "AND created_by_actor_display_name_snapshot !~ '[[:cntrl:]]'",
            name=op.f("ck_paint_plans_actor_snapshots_safe"),
        ),
        sa.CheckConstraint(
            "(revision_kind = 'edited' AND created_by_actor_type = 'user') "
            "OR (revision_kind IN ('generated','regenerated') "
            "AND created_by_actor_type = 'provider')",
            name=op.f("ck_paint_plans_revision_actor_consistent"),
        ),
        sa.ForeignKeyConstraint(
            ["paint_project_id", "owner_principal_id"],
            ["paint_projects.id", "paint_projects.owner_principal_id"],
            name="fk_paint_plans_project_owner",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_readiness_review_id"],
            ["image_set_readiness_reviews.id"],
            name="fk_paint_plans_source_readiness_review",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["paint_project_id", "owner_principal_id", "source_region_set_id"],
            ["region_sets.paint_project_id", "region_sets.owner_principal_id", "region_sets.id"],
            name="fk_paint_plans_source_region_set_same_project_owner",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_invocation_id"],
            ["invocation_requests.id"],
            name="fk_paint_plans_source_invocation",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_invocation_id", "source_attempt_id"],
            ["invocation_attempts.invocation_id", "invocation_attempts.id"],
            name="fk_paint_plans_source_attempt",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["provider_definition_id"],
            ["provider_definitions.id"],
            name="fk_paint_plans_provider",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["model_definition_id"],
            ["model_definitions.id"],
            name="fk_paint_plans_model",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["provider_pricing_snapshot_id", "provider_definition_id", "model_definition_id"],
            [
                "provider_pricing_snapshots.id",
                "provider_pricing_snapshots.provider_definition_id",
                "provider_pricing_snapshots.model_definition_id",
            ],
            name="fk_paint_plans_pricing_snapshot_exact_model",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            [
                "prompt_template_definition_id",
                "prompt_template_key_snapshot",
                "prompt_template_version_snapshot",
                "prompt_content_hash",
                "response_schema_version",
            ],
            [
                "prompt_template_definitions.id",
                "prompt_template_definitions.template_key",
                "prompt_template_definitions.version",
                "prompt_template_definitions.content_hash",
                "prompt_template_definitions.schema_version",
            ],
            name="fk_paint_plans_prompt_exact_contract",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["paint_project_id", "owner_principal_id", "lineage_id"],
            ["paint_plans.paint_project_id", "paint_plans.owner_principal_id", "paint_plans.id"],
            name="fk_paint_plans_lineage_same_project_owner",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["paint_project_id", "owner_principal_id", "parent_plan_id"],
            ["paint_plans.paint_project_id", "paint_plans.owner_principal_id", "paint_plans.id"],
            name="fk_paint_plans_parent_same_project_owner",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_paint_plans")),
        sa.UniqueConstraint(
            "paint_project_id",
            "owner_principal_id",
            "id",
            name="uq_paint_plans_project_owner_id",
        ),
        sa.UniqueConstraint(
            "paint_project_id",
            "version",
            name="uq_paint_plans_project_version",
        ),
        sa.UniqueConstraint(
            "lineage_id",
            "lineage_revision",
            name="uq_paint_plans_lineage_revision",
        ),
        sa.UniqueConstraint(
            "id",
            "source_region_set_id",
            name="uq_paint_plans_id_region_set",
        ),
        sa.UniqueConstraint(
            "id",
            "version",
            "paint_project_id",
            "owner_principal_id",
            name="uq_paint_plans_exact_revision",
        ),
    )
    op.create_index(
        "ix_paint_plans_owner_project_version",
        "paint_plans",
        ["owner_principal_id", "paint_project_id", "version"],
    )
    op.create_index(
        "ix_paint_plans_lineage_revision",
        "paint_plans",
        ["lineage_id", "lineage_revision"],
    )
    op.create_index(
        "ix_paint_plans_source_invocation",
        "paint_plans",
        ["source_invocation_id"],
    )
    op.create_index(
        "uq_paint_plans_one_current_per_project",
        "paint_plans",
        ["paint_project_id"],
        unique=True,
        postgresql_where=sa.text("lifecycle <> 'superseded'"),
    )
    op.create_index(
        "uq_paint_plans_generated_attempt",
        "paint_plans",
        ["source_attempt_id"],
        unique=True,
        postgresql_where=sa.text("revision_kind IN ('generated','regenerated')"),
    )

    op.create_table(
        "paint_plan_region_instructions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("paint_plan_id", sa.UUID(), nullable=False),
        sa.Column("region_set_id", sa.UUID(), nullable=False),
        sa.Column("region_id", sa.UUID(), nullable=False),
        sa.Column("stable_region_key", sa.UUID(), nullable=False),
        sa.Column("region_label_snapshot", sa.String(80), nullable=False),
        sa.Column("region_kind_snapshot", sa.String(16), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("target_color", sa.String(120), nullable=False),
        sa.Column("preparation", sa.String(600), nullable=False),
        sa.Column("base_coat", sa.String(600), nullable=False),
        sa.Column("layer_strategy", sa.String(1000), nullable=False),
        sa.Column("edge_treatment", sa.String(600), nullable=False),
        sa.Column("lighting_guidance", sa.String(600), nullable=False),
        sa.Column("material_guidance", sa.String(600), nullable=False),
        sa.Column(
            "warnings",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("confidence_ppm", sa.Integer(), nullable=False),
        _created_at(),
        sa.CheckConstraint(
            "region_kind_snapshot = 'paint'",
            name=op.f("ck_paint_plan_region_instructions_kind_paint"),
        ),
        sa.CheckConstraint(
            "sequence BETWEEN 0 AND 127",
            name=op.f("ck_paint_plan_region_instructions_sequence_allowed"),
        ),
        sa.CheckConstraint(
            "length(region_label_snapshot) BETWEEN 1 AND 80 "
            "AND region_label_snapshot = btrim(region_label_snapshot) "
            "AND region_label_snapshot !~ '[<>]' "
            "AND region_label_snapshot !~ '[[:cntrl:]]'",
            name=op.f("ck_paint_plan_region_instructions_label_safe"),
        ),
        sa.CheckConstraint(
            "length(target_color) BETWEEN 1 AND 120 AND target_color = btrim(target_color) "
            "AND length(preparation) BETWEEN 1 AND 600 AND preparation = btrim(preparation) "
            "AND length(base_coat) BETWEEN 1 AND 600 AND base_coat = btrim(base_coat) "
            "AND length(layer_strategy) BETWEEN 1 AND 1000 AND layer_strategy = btrim(layer_strategy) "
            "AND length(edge_treatment) BETWEEN 1 AND 600 AND edge_treatment = btrim(edge_treatment) "
            "AND length(lighting_guidance) BETWEEN 1 AND 600 AND lighting_guidance = btrim(lighting_guidance) "
            "AND length(material_guidance) BETWEEN 1 AND 600 AND material_guidance = btrim(material_guidance) "
            "AND target_color !~ '[<>]' AND preparation !~ '[<>]' "
            "AND base_coat !~ '[<>]' AND layer_strategy !~ '[<>]' "
            "AND edge_treatment !~ '[<>]' AND lighting_guidance !~ '[<>]' "
            "AND material_guidance !~ '[<>]' "
            "AND target_color !~ '[[:cntrl:]]' AND preparation !~ '[[:cntrl:]]' "
            "AND base_coat !~ '[[:cntrl:]]' AND layer_strategy !~ '[[:cntrl:]]' "
            "AND edge_treatment !~ '[[:cntrl:]]' "
            "AND lighting_guidance !~ '[[:cntrl:]]' "
            "AND material_guidance !~ '[[:cntrl:]]'",
            name=op.f("ck_paint_plan_region_instructions_text_safe"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(warnings) = 'array' "
            "AND jsonb_array_length(warnings) <= 8 "
            "AND octet_length(warnings::text) <= 2200 "
            "AND NOT jsonb_path_exists(warnings, '$[*] ? (@.type() != \"string\")')",
            name=op.f("ck_paint_plan_region_instructions_warnings_bounded"),
        ),
        sa.CheckConstraint(
            "confidence_ppm BETWEEN 0 AND 1000000",
            name=op.f("ck_paint_plan_region_instructions_confidence_allowed"),
        ),
        sa.ForeignKeyConstraint(
            ["paint_plan_id", "region_set_id"],
            ["paint_plans.id", "paint_plans.source_region_set_id"],
            name="fk_paint_plan_region_instructions_plan_region_set",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["region_id", "region_set_id"],
            ["regions.id", "regions.region_set_id"],
            name="fk_paint_plan_region_instructions_region_same_set",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_paint_plan_region_instructions")),
        sa.UniqueConstraint(
            "paint_plan_id",
            "region_id",
            name="uq_paint_plan_region_instructions_plan_region",
        ),
        sa.UniqueConstraint(
            "paint_plan_id",
            "stable_region_key",
            name="uq_paint_plan_region_instructions_plan_stable_key",
        ),
        sa.UniqueConstraint(
            "paint_plan_id",
            "sequence",
            name="uq_paint_plan_region_instructions_plan_sequence",
        ),
    )
    op.create_index(
        "ix_paint_plan_region_instructions_plan_sequence",
        "paint_plan_region_instructions",
        ["paint_plan_id", "sequence"],
    )

    op.create_table(
        "paint_plan_review_events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("owner_principal_id", sa.String(128), nullable=False),
        sa.Column("paint_project_id", sa.UUID(), nullable=False),
        sa.Column("paint_plan_id", sa.UUID(), nullable=False),
        sa.Column("paint_plan_version", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("actor_user_id", sa.UUID(), nullable=True),
        sa.Column("actor_principal_id", sa.String(128), nullable=False),
        sa.Column("actor_display_name_snapshot", sa.String(200), nullable=False),
        sa.Column("reason", sa.String(1000), nullable=True),
        _created_at(),
        sa.CheckConstraint(
            "action IN ('submit', 'approve', 'reject')",
            name=op.f("ck_paint_plan_review_events_action_allowed"),
        ),
        sa.CheckConstraint(
            "paint_plan_version >= 1",
            name=op.f("ck_paint_plan_review_events_version_positive"),
        ),
        sa.CheckConstraint(
            "reason IS NULL OR (length(reason) BETWEEN 1 AND 1000 "
            "AND reason = btrim(reason) AND reason !~ '[[:cntrl:]]')",
            name=op.f("ck_paint_plan_review_events_reason_safe"),
        ),
        sa.CheckConstraint(
            "action <> 'reject' OR reason IS NOT NULL",
            name=op.f("ck_paint_plan_review_events_reject_reason_required"),
        ),
        sa.CheckConstraint(
            "length(actor_principal_id) BETWEEN 1 AND 128 "
            "AND actor_principal_id = btrim(actor_principal_id) "
            "AND actor_principal_id !~ '[[:cntrl:]]' "
            "AND length(actor_display_name_snapshot) BETWEEN 1 AND 200 "
            "AND actor_display_name_snapshot = btrim(actor_display_name_snapshot) "
            "AND actor_display_name_snapshot !~ '[[:cntrl:]]'",
            name=op.f("ck_paint_plan_review_events_actor_safe"),
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["user_accounts.id"],
            name="fk_paint_plan_review_events_actor_user",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["paint_plan_id", "paint_plan_version", "paint_project_id", "owner_principal_id"],
            [
                "paint_plans.id",
                "paint_plans.version",
                "paint_plans.paint_project_id",
                "paint_plans.owner_principal_id",
            ],
            name="fk_paint_plan_review_events_exact_revision",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_paint_plan_review_events")),
        sa.UniqueConstraint(
            "paint_plan_id",
            "action",
            name="uq_paint_plan_review_events_plan_action",
        ),
    )
    op.create_index(
        "uq_paint_plan_review_events_decision",
        "paint_plan_review_events",
        ["paint_plan_id"],
        unique=True,
        postgresql_where=sa.text("action IN ('approve','reject')"),
    )
    op.create_index(
        "ix_paint_plan_review_events_owner_project_created",
        "paint_plan_review_events",
        ["owner_principal_id", "paint_project_id", "created_at"],
    )


def _create_phase3b_triggers() -> None:
    op.execute(
        sa.text("""
        CREATE FUNCTION phase3b_reject_immutable_mutation() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION USING ERRCODE = '55000', MESSAGE = TG_TABLE_NAME || ' is immutable';
        END
        $$;
        CREATE TRIGGER provider_pricing_snapshots_immutable
        BEFORE UPDATE OR DELETE ON provider_pricing_snapshots
        FOR EACH ROW EXECUTE FUNCTION phase3b_reject_immutable_mutation();
        CREATE TRIGGER prompt_template_definitions_immutable
        BEFORE UPDATE OR DELETE ON prompt_template_definitions
        FOR EACH ROW EXECUTE FUNCTION phase3b_reject_immutable_mutation();
        CREATE TRIGGER paint_plan_region_instructions_immutable
        BEFORE UPDATE OR DELETE ON paint_plan_region_instructions
        FOR EACH ROW EXECUTE FUNCTION phase3b_reject_immutable_mutation();
        CREATE TRIGGER paint_plan_review_events_immutable
        BEFORE UPDATE OR DELETE ON paint_plan_review_events
        FOR EACH ROW EXECUTE FUNCTION phase3b_reject_immutable_mutation();
    """)
    )
    op.execute(
        sa.text("""
        CREATE FUNCTION phase3b_guard_openai_registry_seed() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF (TG_TABLE_NAME = 'provider_definitions'
                AND OLD.id = '3b000000-0000-4000-8000-000000000001'::uuid)
               OR (TG_TABLE_NAME = 'model_definitions'
                   AND OLD.id = '3b000000-0000-4000-8000-000000000101'::uuid)
               OR (TG_TABLE_NAME = 'provider_capabilities'
                   AND OLD.id IN (
                       '3b000000-0000-4000-8000-000000002001'::uuid,
                       '3b000000-0000-4000-8000-000000002002'::uuid,
                       '3b000000-0000-4000-8000-000000002003'::uuid
                   ))
               OR (TG_TABLE_NAME = 'model_capabilities'
                   AND OLD.id IN (
                       '3b000000-0000-4000-8000-000000003001'::uuid,
                       '3b000000-0000-4000-8000-000000003002'::uuid,
                       '3b000000-0000-4000-8000-000000003003'::uuid
                   )) THEN
                RAISE EXCEPTION USING ERRCODE = '55000', MESSAGE = 'Phase 3B OpenAI registry seed facts are immutable';
            END IF;
            IF TG_OP = 'DELETE' THEN
                RETURN OLD;
            END IF;
            RETURN NEW;
        END
        $$;
        CREATE TRIGGER phase3b_openai_provider_seed_immutable
        BEFORE UPDATE OR DELETE ON provider_definitions
        FOR EACH ROW EXECUTE FUNCTION phase3b_guard_openai_registry_seed();
        CREATE TRIGGER phase3b_openai_model_seed_immutable
        BEFORE UPDATE OR DELETE ON model_definitions
        FOR EACH ROW EXECUTE FUNCTION phase3b_guard_openai_registry_seed();
        CREATE TRIGGER phase3b_openai_provider_capability_seed_immutable
        BEFORE UPDATE OR DELETE ON provider_capabilities
        FOR EACH ROW EXECUTE FUNCTION phase3b_guard_openai_registry_seed();
        CREATE TRIGGER phase3b_openai_model_capability_seed_immutable
        BEFORE UPDATE OR DELETE ON model_capabilities
        FOR EACH ROW EXECUTE FUNCTION phase3b_guard_openai_registry_seed();
    """)
    )
    op.execute(
        sa.text("""
        CREATE FUNCTION phase3b_guard_paint_plan_invocation_payload() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF (OLD.invocation_family = 'paint_plan_generation'
                OR NEW.invocation_family = 'paint_plan_generation')
               AND (NEW.requesting_user_id IS DISTINCT FROM OLD.requesting_user_id
                    OR NEW.product_space IS DISTINCT FROM OLD.product_space
                    OR NEW.project_id IS DISTINCT FROM OLD.project_id
                    OR NEW.project_scope_id IS DISTINCT FROM OLD.project_scope_id
                    OR NEW.invocation_family IS DISTINCT FROM OLD.invocation_family
                    OR NEW.idempotency_key IS DISTINCT FROM OLD.idempotency_key
                    OR NEW.canonicalization_version IS DISTINCT FROM OLD.canonicalization_version
                    OR NEW.canonical_request_payload_hash IS DISTINCT FROM OLD.canonical_request_payload_hash
                    OR NEW.requested_capabilities IS DISTINCT FROM OLD.requested_capabilities
                    OR NEW.requested_provider_definition_id IS DISTINCT FROM OLD.requested_provider_definition_id
                    OR NEW.requested_model_definition_id IS DISTINCT FROM OLD.requested_model_definition_id
                    OR NEW.requested_credential_id IS DISTINCT FROM OLD.requested_credential_id
                    OR NEW.request_id IS DISTINCT FROM OLD.request_id
                    OR NEW.max_attempts IS DISTINCT FROM OLD.max_attempts
                    OR NEW.total_elapsed_time_limit_ms IS DISTINCT FROM OLD.total_elapsed_time_limit_ms
                    OR NEW.confirmation_snapshot IS DISTINCT FROM OLD.confirmation_snapshot
                    OR NEW.budget_snapshot IS DISTINCT FROM OLD.budget_snapshot
                    OR NEW.safe_payload IS DISTINCT FROM OLD.safe_payload
                    OR NEW.created_at IS DISTINCT FROM OLD.created_at) THEN
                RAISE EXCEPTION USING ERRCODE = '55000', MESSAGE = 'Paint Plan invocation provenance is immutable';
            END IF;
            RETURN NEW;
        END
        $$;
        CREATE TRIGGER phase3b_paint_plan_invocation_payload_immutable
        BEFORE UPDATE ON invocation_requests
        FOR EACH ROW EXECUTE FUNCTION phase3b_guard_paint_plan_invocation_payload();
    """)
    )
    op.execute(
        sa.text("""
        CREATE FUNCTION phase3b_guard_paint_plan_mutation() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION USING ERRCODE = '55000', MESSAGE = 'paint_plans cannot be deleted';
            END IF;
            IF (to_jsonb(NEW) - 'lifecycle') IS DISTINCT FROM
               (to_jsonb(OLD) - 'lifecycle') THEN
                RAISE EXCEPTION USING ERRCODE = '55000', MESSAGE = 'Paint Plan provenance, content, revision, and actor facts are immutable';
            END IF;
            IF (OLD.lifecycle IN ('generated','edited')
                AND NEW.lifecycle IN ('under_review','superseded'))
               OR (OLD.lifecycle = 'under_review'
                   AND NEW.lifecycle IN ('approved','rejected','superseded'))
               OR (OLD.lifecycle IN ('approved','rejected')
                   AND NEW.lifecycle = 'superseded') THEN
                RETURN NEW;
            END IF;
            RAISE EXCEPTION USING ERRCODE = '23514', MESSAGE = 'Paint Plan lifecycle transition is not allowed';
        END
        $$;
        CREATE TRIGGER paint_plans_guard_mutation
        BEFORE UPDATE OR DELETE ON paint_plans
        FOR EACH ROW EXECUTE FUNCTION phase3b_guard_paint_plan_mutation();
    """)
    )
    op.execute(
        sa.text("""
        CREATE FUNCTION phase3b_verify_paint_plan_insert() RETURNS trigger
        LANGUAGE plpgsql AS $$
        DECLARE
            parent_version integer;
            parent_lineage_id uuid;
            parent_lineage_revision integer;
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM image_set_readiness_reviews review
                WHERE review.id = NEW.source_readiness_review_id
                  AND review.paint_project_id = NEW.paint_project_id
                  AND review.owner_principal_id = NEW.owner_principal_id
                  AND review.version = NEW.source_readiness_review_version
                  AND review.verdict = 'ready'
                  AND review.image_set_fingerprint = NEW.source_image_set_fingerprint
            ) THEN
                RAISE EXCEPTION USING ERRCODE = '23514', MESSAGE = 'Paint Plan source readiness review is not the exact ready project snapshot';
            END IF;

            IF NOT EXISTS (
                SELECT 1
                FROM region_sets region_set
                JOIN region_set_reviews review
                  ON review.region_set_id = region_set.id
                 AND review.paint_project_id = region_set.paint_project_id
                 AND review.owner_principal_id = region_set.owner_principal_id
                 AND review.verdict = 'approved'
                WHERE region_set.id = NEW.source_region_set_id
                  AND region_set.paint_project_id = NEW.paint_project_id
                  AND region_set.owner_principal_id = NEW.owner_principal_id
                  AND region_set.version = NEW.source_region_set_version
                  AND region_set.lifecycle = 'submitted'
                  AND region_set.geometry_fingerprint = NEW.source_geometry_fingerprint
                  AND region_set.source_image_set_fingerprint = NEW.source_image_set_fingerprint
            ) THEN
                RAISE EXCEPTION USING ERRCODE = '23514', MESSAGE = 'Paint Plan source RegionSet is not the exact approved image-bound snapshot';
            END IF;

            IF NOT EXISTS (
                SELECT 1
                FROM invocation_requests invocation
                JOIN invocation_attempts attempt
                  ON attempt.invocation_id = invocation.id
                 AND attempt.id = NEW.source_attempt_id
                JOIN provider_definitions provider
                  ON provider.id = attempt.provider_definition_id
                JOIN model_definitions model
                  ON model.id = attempt.model_definition_id
                WHERE invocation.id = NEW.source_invocation_id
                  AND invocation.project_id = NEW.paint_project_id
                  AND invocation.invocation_family = 'paint_plan_generation'
                  AND invocation.status = 'succeeded'
                  AND invocation.final_attempt_id = NEW.source_attempt_id
                  AND invocation.safe_payload #>> '{paint_plan_provenance,image_set_fingerprint}' = NEW.source_image_set_fingerprint
                  AND jsonb_typeof(invocation.safe_payload #> '{paint_plan_provenance,image_assets}') = 'array'
                  AND jsonb_array_length(invocation.safe_payload #> '{paint_plan_provenance,image_assets}') BETWEEN 3 AND 4
                  AND NOT EXISTS (
                      SELECT 1
                      FROM jsonb_array_elements(invocation.safe_payload #> '{paint_plan_provenance,image_assets}') image
                      WHERE NOT EXISTS (
                          SELECT 1
                          FROM jsonb_array_elements(invocation.safe_payload -> 'artifacts') artifact
                          WHERE artifact ->> 'id' = image ->> 'id'
                            AND artifact ->> 'revision' = image ->> 'version'
                            AND artifact ->> 'content_hash' = 'sha256:' || (image ->> 'sha256')
                            AND artifact ->> 'media_type' = image ->> 'media_type'
                            AND artifact ->> 'byte_length' = image ->> 'byte_length'
                      )
                  )
                  AND invocation.safe_payload #>> '{paint_plan_provenance,readiness_review_id}' = NEW.source_readiness_review_id::text
                  AND (invocation.safe_payload #>> '{paint_plan_provenance,readiness_review_version}')::integer = NEW.source_readiness_review_version
                  AND invocation.safe_payload #>> '{paint_plan_provenance,region_set_id}' = NEW.source_region_set_id::text
                  AND (invocation.safe_payload #>> '{paint_plan_provenance,region_set_version}')::integer = NEW.source_region_set_version
                  AND invocation.safe_payload #>> '{paint_plan_provenance,region_geometry_fingerprint}' = NEW.source_geometry_fingerprint
                  AND invocation.safe_payload #>> '{paint_plan_provenance,prompt_template_id}' = NEW.prompt_template_definition_id::text
                  AND invocation.safe_payload #>> '{paint_plan_provenance,prompt_template_key}' = NEW.prompt_template_key_snapshot
                  AND (invocation.safe_payload #>> '{paint_plan_provenance,prompt_template_version}')::integer = NEW.prompt_template_version_snapshot
                  AND invocation.safe_payload #>> '{paint_plan_provenance,prompt_content_hash}' = NEW.prompt_content_hash
                  AND invocation.safe_payload #>> '{paint_plan_provenance,response_schema_version}' = NEW.response_schema_version
                  AND attempt.status = 'succeeded'
                  AND attempt.provider_definition_id = NEW.provider_definition_id
                  AND attempt.model_definition_id = NEW.model_definition_id
                  AND attempt.provider_key = NEW.provider_key_snapshot
                  AND attempt.model_id = NEW.model_id_snapshot
                  AND provider.provider_key = NEW.provider_key_snapshot
                  AND provider.revision = NEW.provider_revision_snapshot
                  AND model.provider_definition_id = NEW.provider_definition_id
                  AND model.provider_key = NEW.provider_key_snapshot
                  AND model.model_id = NEW.model_id_snapshot
                  AND model.revision = NEW.model_revision_snapshot
            ) THEN
                RAISE EXCEPTION USING ERRCODE = '23514', MESSAGE = 'Paint Plan source invocation, attempt, provider, and model provenance is inconsistent';
            END IF;

            IF NEW.revision_kind = 'generated' THEN
                IF NEW.version <> 1 OR EXISTS (
                    SELECT 1 FROM paint_plans existing
                    WHERE existing.paint_project_id = NEW.paint_project_id
                ) THEN
                    RAISE EXCEPTION USING ERRCODE = '23514', MESSAGE = 'Generated Paint Plan must be the first project revision';
                END IF;
            ELSE
                SELECT parent.version, parent.lineage_id, parent.lineage_revision
                  INTO parent_version, parent_lineage_id, parent_lineage_revision
                FROM paint_plans parent
                WHERE parent.id = NEW.parent_plan_id
                  AND parent.paint_project_id = NEW.paint_project_id
                  AND parent.owner_principal_id = NEW.owner_principal_id
                  AND parent.lifecycle = 'superseded';
                IF NOT FOUND OR NEW.version <> parent_version + 1 THEN
                    RAISE EXCEPTION USING ERRCODE = '23514', MESSAGE = 'Paint Plan parent must be the immediately previous project revision';
                END IF;
                IF NEW.revision_kind = 'edited'
                   AND (NEW.lineage_id <> parent_lineage_id
                        OR NEW.lineage_revision <> parent_lineage_revision + 1) THEN
                    RAISE EXCEPTION USING ERRCODE = '23514', MESSAGE = 'Edited Paint Plan must advance the same lineage by one revision';
                END IF;
            END IF;
            RETURN NEW;
        END
        $$;
        CREATE TRIGGER paint_plans_verify_provenance
        BEFORE INSERT ON paint_plans
        FOR EACH ROW EXECUTE FUNCTION phase3b_verify_paint_plan_insert();
    """)
    )
    op.execute(
        sa.text("""
        CREATE FUNCTION phase3b_verify_instruction_insert() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM regions region
                WHERE region.id = NEW.region_id
                  AND region.region_set_id = NEW.region_set_id
                  AND region.stable_region_key = NEW.stable_region_key
                  AND region.label = NEW.region_label_snapshot
                  AND region.kind = NEW.region_kind_snapshot
                  AND region.kind = 'paint'
            ) THEN
                RAISE EXCEPTION USING ERRCODE = '23514', MESSAGE = 'Paint Plan instruction must bind one exact paint Region identity';
            END IF;
            RETURN NEW;
        END
        $$;
        CREATE TRIGGER paint_plan_region_instructions_verify_region
        BEFORE INSERT ON paint_plan_region_instructions
        FOR EACH ROW EXECUTE FUNCTION phase3b_verify_instruction_insert();
    """)
    )
    op.execute(
        sa.text("""
        CREATE FUNCTION phase3b_verify_instruction_count() RETURNS trigger
        LANGUAGE plpgsql AS $$
        DECLARE
            target_plan_id uuid;
            expected_count integer;
            target_region_set_id uuid;
            region_count bigint;
            actual_count bigint;
        BEGIN
            IF TG_TABLE_NAME = 'paint_plans' THEN
                target_plan_id := NEW.id;
                expected_count := NEW.instruction_count;
                target_region_set_id := NEW.source_region_set_id;
            ELSE
                target_plan_id := NEW.paint_plan_id;
                SELECT instruction_count, paint_plans.source_region_set_id
                  INTO expected_count, target_region_set_id
                FROM paint_plans WHERE id = target_plan_id;
            END IF;
            SELECT count(*) INTO region_count
            FROM regions
            WHERE region_set_id = target_region_set_id
              AND kind = 'paint';
            SELECT count(*) INTO actual_count
            FROM paint_plan_region_instructions
            WHERE paint_plan_id = target_plan_id;
            IF expected_count IS DISTINCT FROM actual_count
               OR actual_count IS DISTINCT FROM region_count
               OR EXISTS (
                    SELECT 1
                    FROM regions region
                    WHERE region.region_set_id = target_region_set_id
                      AND region.kind = 'paint'
                      AND NOT EXISTS (
                          SELECT 1
                          FROM paint_plan_region_instructions instruction
                          WHERE instruction.paint_plan_id = target_plan_id
                            AND instruction.region_id = region.id
                      )
               ) THEN
                RAISE EXCEPTION USING ERRCODE = '23514', MESSAGE = 'Paint Plan instructions must cover every exact paint Region once';
            END IF;
            RETURN NEW;
        END
        $$;
        CREATE CONSTRAINT TRIGGER paint_plans_verify_instruction_count
        AFTER INSERT ON paint_plans
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION phase3b_verify_instruction_count();
        CREATE CONSTRAINT TRIGGER paint_plan_instructions_verify_count
        AFTER INSERT ON paint_plan_region_instructions
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION phase3b_verify_instruction_count();
    """)
    )
    op.execute(
        sa.text("""
        CREATE FUNCTION phase3b_verify_review_event_insert() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF NEW.action = 'submit' THEN
                IF EXISTS (
                    SELECT 1 FROM paint_plan_review_events event
                    WHERE event.paint_plan_id = NEW.paint_plan_id
                ) THEN
                    RAISE EXCEPTION USING ERRCODE = '23514', MESSAGE = 'Paint Plan revision may be submitted only once and before a decision';
                END IF;
            ELSE
                IF NOT EXISTS (
                    SELECT 1 FROM paint_plan_review_events event
                    WHERE event.paint_plan_id = NEW.paint_plan_id
                      AND event.action = 'submit'
                ) THEN
                    RAISE EXCEPTION USING ERRCODE = '23514', MESSAGE = 'Paint Plan decision requires a prior submit event for the exact revision';
                END IF;
                IF EXISTS (
                    SELECT 1 FROM paint_plan_review_events event
                    WHERE event.paint_plan_id = NEW.paint_plan_id
                      AND event.action IN ('approve','reject')
                ) THEN
                    RAISE EXCEPTION USING ERRCODE = '23514', MESSAGE = 'Paint Plan revision already has a terminal review decision';
                END IF;
            END IF;
            RETURN NEW;
        END
        $$;
        CREATE TRIGGER paint_plan_review_events_verify_sequence
        BEFORE INSERT ON paint_plan_review_events
        FOR EACH ROW EXECUTE FUNCTION phase3b_verify_review_event_insert();
    """)
    )
    op.execute(
        sa.text("""
        CREATE FUNCTION phase3b_verify_review_lifecycle() RETURNS trigger
        LANGUAGE plpgsql AS $$
        DECLARE
            target_plan_id uuid;
            expected_action text;
            expected_lifecycle text;
            actual_lifecycle text;
        BEGIN
            IF TG_TABLE_NAME = 'paint_plans' THEN
                target_plan_id := NEW.id;
                expected_lifecycle := NEW.lifecycle;
                IF NEW.lifecycle = 'superseded' THEN
                    IF NOT EXISTS (
                        SELECT 1 FROM paint_plans child
                        WHERE child.parent_plan_id = target_plan_id
                    ) THEN
                        RAISE EXCEPTION USING ERRCODE = '23514', MESSAGE = 'Superseded Paint Plan requires an immutable child revision';
                    END IF;
                    RETURN NEW;
                END IF;
                expected_action := CASE NEW.lifecycle
                    WHEN 'under_review' THEN 'submit'
                    WHEN 'approved' THEN 'approve'
                    WHEN 'rejected' THEN 'reject'
                    ELSE NULL
                END;
                IF expected_action IS NULL THEN
                    RETURN NEW;
                END IF;
            ELSE
                target_plan_id := NEW.paint_plan_id;
                expected_action := NEW.action;
                expected_lifecycle := CASE NEW.action
                    WHEN 'submit' THEN 'under_review'
                    WHEN 'approve' THEN 'approved'
                    WHEN 'reject' THEN 'rejected'
                END;
            END IF;

            SELECT lifecycle INTO actual_lifecycle
            FROM paint_plans WHERE id = target_plan_id;
            IF actual_lifecycle IS DISTINCT FROM expected_lifecycle
               OR NOT EXISTS (
                    SELECT 1 FROM paint_plan_review_events event
                    WHERE event.paint_plan_id = target_plan_id
                      AND event.action = expected_action
               ) THEN
                RAISE EXCEPTION USING ERRCODE = '23514', MESSAGE = 'Paint Plan review event and lifecycle must describe the same exact revision state';
            END IF;
            RETURN NEW;
        END
        $$;
        CREATE CONSTRAINT TRIGGER paint_plans_verify_review_lifecycle
        AFTER UPDATE OF lifecycle ON paint_plans
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION phase3b_verify_review_lifecycle();
        CREATE CONSTRAINT TRIGGER paint_plan_reviews_verify_lifecycle
        AFTER INSERT ON paint_plan_review_events
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION phase3b_verify_review_lifecycle();
    """)
    )


def _seed_phase3b_registry() -> None:
    connection = op.get_bind()
    connection.execute(
        sa.text("""
            INSERT INTO provider_definitions (
                id, provider_key, display_name, adapter_type, base_url_policy,
                authentication_scheme, model_catalog_mode, allow_custom_model_id,
                enabled, status, catalog_status, catalog_fresh_at, max_timeout_ms,
                max_retries, revision, created_at, updated_at
            ) VALUES (
                :id, 'openai', 'OpenAI', 'openai_responses', 'provider_managed',
                'bearer_api_key', 'bundled', false, false, 'disabled',
                'pinned_disabled', :fixed_time, 120000, 0, 1, :fixed_time, :fixed_time
            )
        """),
        {"id": OPENAI_PROVIDER_ID, "fixed_time": FIXED_TIME},
    )
    connection.execute(
        sa.text("""
            INSERT INTO model_definitions (
                id, provider_definition_id, provider_key, model_id, display_name,
                catalog_source, catalog_fresh_at, catalog_status, status,
                context_window, supports_structured_output, supports_vision,
                pricing_minor_units, pricing_currency, revision, created_at, updated_at
            ) VALUES (
                :id, :provider_id, 'openai', 'gpt-5.4-mini-2026-03-17',
                'GPT-5.4 mini (2026-03-17)', 'phase3b_pinned', :fixed_time,
                'pinned', 'disabled', NULL, true, true, NULL, NULL, 1,
                :fixed_time, :fixed_time
            )
        """),
        {
            "id": OPENAI_MODEL_ID,
            "provider_id": OPENAI_PROVIDER_ID,
            "fixed_time": FIXED_TIME,
        },
    )
    for index, capability_id in enumerate(
        (TEXT_CAPABILITY_ID, VISION_CAPABILITY_ID, STRUCTURED_CAPABILITY_ID),
        start=1,
    ):
        connection.execute(
            sa.text("""
                INSERT INTO provider_capabilities (
                    id, provider_definition_id, capability_definition_id,
                    source, trust_status, status, created_at
                ) VALUES (
                    :id, :provider_id, :capability_id,
                    'phase3b_pinned', 'pinned', 'active', :fixed_time
                )
            """),
            {
                "id": uuid.UUID(f"3b000000-0000-4000-8000-00000000200{index}"),
                "provider_id": OPENAI_PROVIDER_ID,
                "capability_id": capability_id,
                "fixed_time": FIXED_TIME,
            },
        )
        connection.execute(
            sa.text("""
                INSERT INTO model_capabilities (
                    id, model_definition_id, capability_definition_id,
                    source, trust_status, status, created_at
                ) VALUES (
                    :id, :model_id, :capability_id,
                    'phase3b_pinned', 'pinned', 'active', :fixed_time
                )
            """),
            {
                "id": uuid.UUID(f"3b000000-0000-4000-8000-00000000300{index}"),
                "model_id": OPENAI_MODEL_ID,
                "capability_id": capability_id,
                "fixed_time": FIXED_TIME,
            },
        )
    connection.execute(
        sa.text("""
            INSERT INTO provider_pricing_snapshots (
                id, provider_definition_id, model_definition_id, provider_key,
                model_id, pricing_version, currency, unit_basis,
                input_minor_units_per_million, output_minor_units_per_million,
                source_url, effective_at, captured_at, created_at
            ) VALUES (
                :id, :provider_id, :model_id, 'openai',
                'gpt-5.4-mini-2026-03-17', 'openai-2026-03-17-usd', 'USD',
                'per_million_tokens', 75, 450,
                'https://openai.com/api/pricing/', :effective_at, :fixed_time, :fixed_time
            )
        """),
        {
            "id": OPENAI_PRICING_ID,
            "provider_id": OPENAI_PROVIDER_ID,
            "model_id": OPENAI_MODEL_ID,
            "effective_at": PRICING_EFFECTIVE_TIME,
            "fixed_time": FIXED_TIME,
        },
    )
    connection.execute(
        sa.text("""
            INSERT INTO prompt_template_definitions (
                id, template_key, version, schema_version, template_body,
                content_hash, status, created_at
            ) VALUES (
                :id, 'paint-plan', 1, 'paint-plan.v1', :template_body,
                :content_hash, 'active', :fixed_time
            )
        """),
        {
            "id": PAINT_PLAN_PROMPT_ID,
            "template_body": PAINT_PLAN_PROMPT_BODY,
            "content_hash": PAINT_PLAN_PROMPT_HASH,
            "fixed_time": FIXED_TIME,
        },
    )


def upgrade() -> None:
    _expand_phase3a_contracts()
    _create_phase3b_tables()
    _create_phase3b_triggers()
    _seed_phase3b_registry()


def _assert_downgrade_safe() -> None:
    op.execute(
        sa.text("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM paint_plan_review_events)
               OR EXISTS (SELECT 1 FROM paint_plan_region_instructions)
               OR EXISTS (SELECT 1 FROM paint_plans)
            THEN
                RAISE EXCEPTION USING ERRCODE = '55000', MESSAGE = 'Phase 3B downgrade refused: immutable Paint Plan facts exist';
            END IF;

            IF EXISTS (
                SELECT 1 FROM provider_pricing_snapshots
                WHERE id <> '3b000000-0000-4000-8000-000000000201'::uuid
            ) OR EXISTS (
                SELECT 1 FROM prompt_template_definitions
                WHERE id <> '3b000000-0000-4000-8000-000000000301'::uuid
            ) THEN
                RAISE EXCEPTION USING ERRCODE = '55000', MESSAGE = 'Phase 3B downgrade refused: non-seed pricing or prompt facts exist';
            END IF;

            IF EXISTS (SELECT 1 FROM model_definitions WHERE pricing_currency = 'USD')
               OR EXISTS (SELECT 1 FROM project_model_policies WHERE currency = 'USD')
               OR EXISTS (SELECT 1 FROM user_budget_policies WHERE currency = 'USD')
               OR EXISTS (SELECT 1 FROM project_budget_policies WHERE currency = 'USD')
               OR EXISTS (SELECT 1 FROM user_budget_counters WHERE currency = 'USD')
               OR EXISTS (SELECT 1 FROM project_budget_counters WHERE currency = 'USD')
               OR EXISTS (SELECT 1 FROM invocation_attempts WHERE currency = 'USD')
               OR EXISTS (SELECT 1 FROM budget_reservations WHERE currency = 'USD')
               OR EXISTS (SELECT 1 FROM ai_cost_ledger WHERE currency = 'USD')
               OR EXISTS (SELECT 1 FROM invocation_requests WHERE invocation_family = 'paint_plan_generation')
               OR EXISTS (
                    SELECT 1 FROM invocation_attempts
                    WHERE provider_request_id_status <> 'absent'
                       OR provider_request_id IS NOT NULL
               )
               OR EXISTS (
                    SELECT 1 FROM ai_usage_ledger
                    WHERE measurement_status <> 'measured'
                       OR input_units IS NULL OR output_units IS NULL
               )
               OR EXISTS (
                    SELECT 1 FROM ai_cost_ledger
                    WHERE measurement_status <> 'measured'
                       OR amount_minor_units IS NULL
               )
            THEN
                RAISE EXCEPTION USING ERRCODE = '55000', MESSAGE = 'Phase 3B downgrade refused: provider-neutral currency, invocation, request-id, usage, or cost facts cannot be represented by Phase 3A';
            END IF;

            IF EXISTS (
                SELECT 1 FROM model_definitions
                WHERE provider_definition_id = '3b000000-0000-4000-8000-000000000001'::uuid
                  AND id <> '3b000000-0000-4000-8000-000000000101'::uuid
            )
               OR EXISTS (SELECT 1 FROM credential_records WHERE provider_definition_id = '3b000000-0000-4000-8000-000000000001'::uuid)
               OR EXISTS (SELECT 1 FROM user_provider_preferences WHERE default_provider_definition_id = '3b000000-0000-4000-8000-000000000001'::uuid OR default_model_definition_id = '3b000000-0000-4000-8000-000000000101'::uuid)
               OR EXISTS (SELECT 1 FROM project_model_policies WHERE default_provider_definition_id = '3b000000-0000-4000-8000-000000000001'::uuid OR default_model_definition_id = '3b000000-0000-4000-8000-000000000101'::uuid)
               OR EXISTS (SELECT 1 FROM project_model_policy_providers WHERE provider_definition_id = '3b000000-0000-4000-8000-000000000001'::uuid)
               OR EXISTS (SELECT 1 FROM project_model_policy_models WHERE model_definition_id = '3b000000-0000-4000-8000-000000000101'::uuid)
               OR EXISTS (SELECT 1 FROM invocation_requests WHERE requested_provider_definition_id = '3b000000-0000-4000-8000-000000000001'::uuid OR requested_model_definition_id = '3b000000-0000-4000-8000-000000000101'::uuid)
               OR EXISTS (SELECT 1 FROM invocation_attempts WHERE provider_definition_id = '3b000000-0000-4000-8000-000000000001'::uuid OR model_definition_id = '3b000000-0000-4000-8000-000000000101'::uuid)
               OR EXISTS (SELECT 1 FROM ai_usage_ledger WHERE provider_definition_id = '3b000000-0000-4000-8000-000000000001'::uuid OR model_definition_id = '3b000000-0000-4000-8000-000000000101'::uuid)
               OR EXISTS (SELECT 1 FROM ai_cost_ledger WHERE provider_definition_id = '3b000000-0000-4000-8000-000000000001'::uuid OR model_definition_id = '3b000000-0000-4000-8000-000000000101'::uuid)
               OR EXISTS (SELECT 1 FROM ai_audit_events WHERE provider_definition_id = '3b000000-0000-4000-8000-000000000001'::uuid OR model_definition_id = '3b000000-0000-4000-8000-000000000101'::uuid)
               OR EXISTS (
                    SELECT 1 FROM provider_capabilities
                    WHERE provider_definition_id = '3b000000-0000-4000-8000-000000000001'::uuid
                      AND id NOT IN (
                          '3b000000-0000-4000-8000-000000002001'::uuid,
                          '3b000000-0000-4000-8000-000000002002'::uuid,
                          '3b000000-0000-4000-8000-000000002003'::uuid
                      )
               )
               OR EXISTS (
                    SELECT 1 FROM model_capabilities
                    WHERE model_definition_id = '3b000000-0000-4000-8000-000000000101'::uuid
                      AND id NOT IN (
                          '3b000000-0000-4000-8000-000000003001'::uuid,
                          '3b000000-0000-4000-8000-000000003002'::uuid,
                          '3b000000-0000-4000-8000-000000003003'::uuid
                      )
               )
            THEN
                RAISE EXCEPTION USING ERRCODE = '55000', MESSAGE = 'Phase 3B downgrade refused: disabled OpenAI Registry identities are referenced';
            END IF;

            IF EXISTS (
                SELECT 1 FROM provider_definitions
                WHERE id = '3b000000-0000-4000-8000-000000000001'::uuid
                  AND (provider_key <> 'openai'
                       OR adapter_type <> 'openai_responses'
                       OR base_url_policy <> 'provider_managed'
                       OR enabled <> false
                       OR status <> 'disabled')
            ) OR EXISTS (
                SELECT 1 FROM model_definitions
                WHERE id = '3b000000-0000-4000-8000-000000000101'::uuid
                  AND (provider_definition_id <> '3b000000-0000-4000-8000-000000000001'::uuid
                       OR provider_key <> 'openai'
                       OR model_id <> 'gpt-5.4-mini-2026-03-17'
                       OR status <> 'disabled')
            ) THEN
                RAISE EXCEPTION USING ERRCODE = '55000', MESSAGE = 'Phase 3B downgrade refused: disabled OpenAI seed identity was modified';
            END IF;
        END
        $$;
    """)
    )


def _drop_phase3b_tables_and_seeds() -> None:
    for function_name in (
        "phase3b_guard_paint_plan_invocation_payload",
        "phase3b_guard_openai_registry_seed",
        "phase3b_verify_review_lifecycle",
        "phase3b_verify_review_event_insert",
        "phase3b_verify_instruction_count",
        "phase3b_verify_instruction_insert",
        "phase3b_verify_paint_plan_insert",
        "phase3b_guard_paint_plan_mutation",
        "phase3b_reject_immutable_mutation",
    ):
        op.execute(sa.text(f"DROP FUNCTION {function_name}() CASCADE"))

    op.drop_index(
        "ix_paint_plan_review_events_owner_project_created",
        table_name="paint_plan_review_events",
    )
    op.drop_index(
        "uq_paint_plan_review_events_decision",
        table_name="paint_plan_review_events",
    )
    op.drop_table("paint_plan_review_events")
    op.drop_index(
        "ix_paint_plan_region_instructions_plan_sequence",
        table_name="paint_plan_region_instructions",
    )
    op.drop_table("paint_plan_region_instructions")
    op.drop_index("uq_paint_plans_generated_attempt", table_name="paint_plans")
    op.drop_index("uq_paint_plans_one_current_per_project", table_name="paint_plans")
    op.drop_index("ix_paint_plans_source_invocation", table_name="paint_plans")
    op.drop_index("ix_paint_plans_lineage_revision", table_name="paint_plans")
    op.drop_index("ix_paint_plans_owner_project_version", table_name="paint_plans")
    op.drop_table("paint_plans")
    op.drop_table("prompt_template_definitions")
    op.drop_index(
        "ix_provider_pricing_snapshots_model_effective",
        table_name="provider_pricing_snapshots",
    )
    op.drop_table("provider_pricing_snapshots")

    op.execute(
        sa.text(
            "DELETE FROM model_capabilities WHERE id IN "
            "('3b000000-0000-4000-8000-000000003001'::uuid, "
            "'3b000000-0000-4000-8000-000000003002'::uuid, "
            "'3b000000-0000-4000-8000-000000003003'::uuid)"
        )
    )
    op.execute(
        sa.text(
            "DELETE FROM provider_capabilities WHERE id IN "
            "('3b000000-0000-4000-8000-000000002001'::uuid, "
            "'3b000000-0000-4000-8000-000000002002'::uuid, "
            "'3b000000-0000-4000-8000-000000002003'::uuid)"
        )
    )
    op.execute(
        sa.text(
            "DELETE FROM model_definitions WHERE id = '3b000000-0000-4000-8000-000000000101'::uuid"
        )
    )
    op.execute(
        sa.text(
            "DELETE FROM provider_definitions "
            "WHERE id = '3b000000-0000-4000-8000-000000000001'::uuid"
        )
    )


def _restore_phase3a_contracts() -> None:
    op.drop_constraint(
        op.f("ck_invocation_attempts_provider_request_id_consistent"),
        "invocation_attempts",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_invocation_attempts_provider_request_id_status_allowed"),
        "invocation_attempts",
        type_="check",
    )
    op.drop_column("invocation_attempts", "provider_request_id")
    op.drop_column("invocation_attempts", "provider_request_id_status")

    op.drop_constraint(
        op.f("ck_ai_usage_ledger_measurement_consistent"),
        "ai_usage_ledger",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_ai_usage_ledger_measurement_status_allowed"),
        "ai_usage_ledger",
        type_="check",
    )
    op.alter_column(
        "ai_usage_ledger",
        "input_units",
        existing_type=sa.BigInteger(),
        nullable=False,
    )
    op.alter_column(
        "ai_usage_ledger",
        "output_units",
        existing_type=sa.BigInteger(),
        nullable=False,
    )
    op.drop_column("ai_usage_ledger", "measurement_status")

    op.drop_constraint(
        op.f("ck_ai_cost_ledger_measurement_consistent"),
        "ai_cost_ledger",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_ai_cost_ledger_measurement_status_allowed"),
        "ai_cost_ledger",
        type_="check",
    )
    op.alter_column(
        "ai_cost_ledger",
        "amount_minor_units",
        existing_type=sa.BigInteger(),
        nullable=False,
    )
    op.drop_column("ai_cost_ledger", "measurement_status")

    _replace_check(
        "invocation_requests",
        "ck_invocation_requests_family_allowed",
        "invocation_family IN ('fixture_credential_validation','fixture_model_catalog','fixture_invocation')",
    )
    for table_name, constraint_name, _expanded, fixture_only in CURRENCY_CHECKS:
        _replace_check(table_name, constraint_name, fixture_only)


def downgrade() -> None:
    _assert_downgrade_safe()
    _drop_phase3b_tables_and_seeds()
    _restore_phase3a_contracts()
