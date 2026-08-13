"""add Zhipu live-provider registry and shared citation snapshots

Revision ID: 5a01b2c3d4e5
Revises: 4c01a2b3c4d5
Create Date: 2026-08-12 00:00:00
"""

# ruff: noqa: E501

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "5a01b2c3d4e5"
down_revision: str | Sequence[str] | None = "4c01a2b3c4d5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ZHIPU_PROVIDER_ID = uuid.UUID("5a000000-0000-4000-8000-000000000001")
GLM_52_MODEL_ID = uuid.UUID("5a000000-0000-4000-8000-000000000101")
GLM_5V_TURBO_MODEL_ID = uuid.UUID("5a000000-0000-4000-8000-000000000102")
GLM_52_PRICING_ID = uuid.UUID("5a000000-0000-4000-8000-000000000201")
GLM_5V_TURBO_PRICING_ID = uuid.UUID("5a000000-0000-4000-8000-000000000202")
TEXT_CAPABILITY_ID = uuid.UUID("3a000000-0000-4000-8000-000000001001")
VISION_CAPABILITY_ID = uuid.UUID("3a000000-0000-4000-8000-000000001002")
STRUCTURED_CAPABILITY_ID = uuid.UUID("3a000000-0000-4000-8000-000000001003")
FIXED_TIME = datetime(2026, 8, 12, tzinfo=UTC)
PRICING_EFFECTIVE_TIME = datetime(2026, 8, 1, tzinfo=UTC)
PRICING_URL = "https://open.bigmodel.cn/pricing"

CURRENCY_CONSTRAINTS = (
    ("model_definitions", "ck_model_definitions_fixture_currency_only", "pricing_currency"),
    ("project_model_policies", "ck_project_model_policies_fixture_currency_only", "currency"),
    ("user_budget_policies", "ck_user_budget_policies_fixture_currency_only", "currency"),
    ("project_budget_policies", "ck_project_budget_policies_fixture_currency_only", "currency"),
    ("user_budget_counters", "ck_user_budget_counters_fixture_currency_only", "currency"),
    ("project_budget_counters", "ck_project_budget_counters_fixture_currency_only", "currency"),
    ("invocation_attempts", "ck_invocation_attempts_fixture_currency_only", "currency"),
    ("budget_reservations", "ck_budget_reservations_fixture_currency_only", "currency"),
    ("ai_cost_ledger", "ck_ai_cost_ledger_fixture_currency_only", "currency"),
)


def _replace_check(table: str, name: str, condition: str) -> None:
    op.drop_constraint(op.f(name), table, type_="check")
    op.create_check_constraint(op.f(name), table, condition)


def _expand_contracts() -> None:
    for table, name, column in CURRENCY_CONSTRAINTS:
        nullable = " IS NULL OR" if column == "pricing_currency" else ""
        _replace_check(
            table,
            name,
            f"{column}{nullable} {column} IN ('FIXTURE_CREDITS','USD','CNY')"
            if nullable
            else f"{column} IN ('FIXTURE_CREDITS','USD','CNY')",
        )
    op.drop_constraint(
        op.f("ck_provider_pricing_snapshots_currency_usd"),
        "provider_pricing_snapshots",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_provider_pricing_snapshots_currency_allowed"),
        "provider_pricing_snapshots",
        "currency IN ('USD','CNY')",
    )
    _replace_check(
        "invocation_requests",
        "ck_invocation_requests_family_allowed",
        "invocation_family IN ('fixture_credential_validation','fixture_model_catalog',"
        "'fixture_invocation','paint_plan_generation','arcana_interpretation')",
    )
    _replace_check(
        "tarot_interpretation_revisions",
        "ck_tarot_interpretation_revisions_source_allowed",
        "source IN ('fixture_local','zhipu_live','user_edit')",
    )


def _add_citation_snapshots() -> None:
    for table in ("paint_plans", "tarot_interpretation_revisions"):
        op.add_column(
            table,
            sa.Column(
                "retrieved_context_snapshot",
                postgresql.JSONB(astext_type=sa.Text()),
                server_default=sa.text("'[]'::jsonb"),
                nullable=False,
            ),
        )
        op.add_column(
            table,
            sa.Column(
                "citation_snapshot",
                postgresql.JSONB(astext_type=sa.Text()),
                server_default=sa.text("'[]'::jsonb"),
                nullable=False,
            ),
        )
    op.create_check_constraint(
        op.f("ck_paint_plans_retrieved_context_array"),
        "paint_plans",
        "jsonb_typeof(retrieved_context_snapshot) = 'array'",
    )
    op.create_check_constraint(
        op.f("ck_paint_plans_citation_snapshot_array"),
        "paint_plans",
        "jsonb_typeof(citation_snapshot) = 'array'",
    )
    op.create_check_constraint(
        op.f("ck_tarot_interpretation_revisions_retrieved_context_array"),
        "tarot_interpretation_revisions",
        "jsonb_typeof(retrieved_context_snapshot) = 'array'",
    )
    op.create_check_constraint(
        op.f("ck_tarot_interpretation_revisions_citation_snapshot_array"),
        "tarot_interpretation_revisions",
        "jsonb_typeof(citation_snapshot) = 'array'",
    )
    op.add_column(
        "tarot_interpretation_revisions",
        sa.Column("source_invocation_id", sa.UUID(), nullable=True),
    )
    op.add_column(
        "tarot_interpretation_revisions",
        sa.Column("source_attempt_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        op.f("fk_tarot_interp_revisions_source_invocation"),
        "tarot_interpretation_revisions",
        "invocation_requests",
        ["source_invocation_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        op.f("fk_tarot_interp_revisions_source_attempt"),
        "tarot_interpretation_revisions",
        "invocation_attempts",
        ["source_attempt_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_check_constraint(
        op.f("ck_tarot_interpretation_revisions_live_provenance_consistent"),
        "tarot_interpretation_revisions",
        "(source = 'zhipu_live' AND source_invocation_id IS NOT NULL "
        "AND source_attempt_id IS NOT NULL AND jsonb_array_length(retrieved_context_snapshot) > 0 "
        "AND jsonb_array_length(citation_snapshot) > 0) OR "
        "(source <> 'zhipu_live' AND source_invocation_id IS NULL AND source_attempt_id IS NULL)",
    )


def _seed_registry() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text("""
        INSERT INTO provider_definitions (
            id, provider_key, display_name, adapter_type, base_url_policy,
            authentication_scheme, model_catalog_mode, allow_custom_model_id,
            enabled, status, catalog_status, catalog_fresh_at, max_timeout_ms,
            max_retries, revision, created_at, updated_at
        ) VALUES (
            :id, 'zhipu', 'Zhipu BigModel', 'zhipu_chat_completions',
            'provider_managed', 'bearer_api_key', 'bundled', false, true,
            'active', 'official_pinned', :fixed, 120000, 0, 1, :fixed, :fixed
        )
        """),
        {"id": ZHIPU_PROVIDER_ID, "fixed": FIXED_TIME},
    )
    model_rows = (
        (
            GLM_52_MODEL_ID,
            "glm-5.2",
            "GLM-5.2",
            1_000_000,
            True,
            False,
            800,
        ),
        (
            GLM_5V_TURBO_MODEL_ID,
            "glm-5v-turbo",
            "GLM-5V-Turbo",
            None,
            True,
            True,
            700,
        ),
    )
    for model_id, model_name, display, context, structured, vision, price in model_rows:
        bind.execute(
            sa.text("""
            INSERT INTO model_definitions (
                id, provider_definition_id, provider_key, model_id, display_name,
                catalog_source, catalog_fresh_at, catalog_status, status,
                context_window, supports_structured_output, supports_vision,
                pricing_minor_units, pricing_currency, revision, created_at, updated_at
            ) VALUES (
                :id, :provider, 'zhipu', :model, :display, 'official_2026_08_12',
                :fixed, 'official_pinned', 'active', :context, :structured, :vision,
                :price, 'CNY', 1, :fixed, :fixed
            )
            """),
            {
                "id": model_id,
                "provider": ZHIPU_PROVIDER_ID,
                "model": model_name,
                "display": display,
                "fixed": FIXED_TIME,
                "context": context,
                "structured": structured,
                "vision": vision,
                "price": price,
            },
        )
    provider_capabilities = (TEXT_CAPABILITY_ID, VISION_CAPABILITY_ID, STRUCTURED_CAPABILITY_ID)
    for index, capability_id in enumerate(provider_capabilities, start=1):
        bind.execute(
            sa.text("""
            INSERT INTO provider_capabilities (
                id, provider_definition_id, capability_definition_id,
                source, trust_status, status, created_at
            ) VALUES (:id, :provider, :capability, 'official_2026_08_12', 'pinned', 'active', :fixed)
            """),
            {
                "id": uuid.UUID(f"5a000000-0000-4000-8000-00000000100{index}"),
                "provider": ZHIPU_PROVIDER_ID,
                "capability": capability_id,
                "fixed": FIXED_TIME,
            },
        )
    model_capabilities = {
        GLM_52_MODEL_ID: (TEXT_CAPABILITY_ID, STRUCTURED_CAPABILITY_ID),
        GLM_5V_TURBO_MODEL_ID: provider_capabilities,
    }
    sequence = 1
    for model_id, capability_ids in model_capabilities.items():
        for capability_id in capability_ids:
            bind.execute(
                sa.text("""
                INSERT INTO model_capabilities (
                    id, model_definition_id, capability_definition_id,
                    source, trust_status, status, created_at
                ) VALUES (:id, :model, :capability, 'official_2026_08_12', 'pinned', 'active', :fixed)
                """),
                {
                    "id": uuid.UUID(f"5a000000-0000-4000-8000-000000002{sequence:03d}"),
                    "model": model_id,
                    "capability": capability_id,
                    "fixed": FIXED_TIME,
                },
            )
            sequence += 1
    pricing_rows = (
        (GLM_52_PRICING_ID, GLM_52_MODEL_ID, "glm-5.2", "zhipu-2026-08-glm-5.2", 800, 2800),
        (
            GLM_5V_TURBO_PRICING_ID,
            GLM_5V_TURBO_MODEL_ID,
            "glm-5v-turbo",
            "zhipu-2026-08-glm-5v-turbo-conservative-tier",
            700,
            2600,
        ),
    )
    for pricing_id, model_id, model_name, version, input_price, output_price in pricing_rows:
        bind.execute(
            sa.text("""
            INSERT INTO provider_pricing_snapshots (
                id, provider_definition_id, model_definition_id, provider_key,
                model_id, pricing_version, currency, unit_basis,
                input_minor_units_per_million, output_minor_units_per_million,
                source_url, effective_at, captured_at, created_at
            ) VALUES (
                :id, :provider, :model_id, 'zhipu', :model_name, :version, 'CNY',
                'per_million_tokens', :input_price, :output_price, :source_url,
                :effective, :fixed, :fixed
            )
            """),
            {
                "id": pricing_id,
                "provider": ZHIPU_PROVIDER_ID,
                "model_id": model_id,
                "model_name": model_name,
                "version": version,
                "input_price": input_price,
                "output_price": output_price,
                "source_url": PRICING_URL,
                "effective": PRICING_EFFECTIVE_TIME,
                "fixed": FIXED_TIME,
            },
        )
    op.execute(
        sa.text("""
        CREATE FUNCTION wp2_reject_zhipu_seed_mutation() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION USING ERRCODE = '55000', MESSAGE = 'WP2 Zhipu registry seed facts are immutable';
        END
        $$;
        CREATE TRIGGER wp2_zhipu_provider_seed_immutable
        BEFORE UPDATE OR DELETE ON provider_definitions
        FOR EACH ROW WHEN (OLD.id = '5a000000-0000-4000-8000-000000000001'::uuid)
        EXECUTE FUNCTION wp2_reject_zhipu_seed_mutation();
        CREATE TRIGGER wp2_zhipu_model_seed_immutable
        BEFORE UPDATE OR DELETE ON model_definitions
        FOR EACH ROW WHEN (OLD.provider_definition_id = '5a000000-0000-4000-8000-000000000001'::uuid)
        EXECUTE FUNCTION wp2_reject_zhipu_seed_mutation();
        """)
    )


def upgrade() -> None:
    _expand_contracts()
    _add_citation_snapshots()
    _seed_registry()


def downgrade() -> None:
    op.execute(sa.text("DROP TRIGGER wp2_zhipu_model_seed_immutable ON model_definitions"))
    op.execute(sa.text("DROP TRIGGER wp2_zhipu_provider_seed_immutable ON provider_definitions"))
    op.execute(sa.text("DROP FUNCTION wp2_reject_zhipu_seed_mutation()"))
    op.execute(
        sa.text(
            "ALTER TABLE provider_pricing_snapshots DISABLE TRIGGER provider_pricing_snapshots_immutable"
        )
    )
    op.execute(
        sa.text(
            "DELETE FROM provider_pricing_snapshots "
            "WHERE provider_definition_id = CAST(:provider AS uuid)"
        ).bindparams(provider=str(ZHIPU_PROVIDER_ID))
    )
    op.execute(
        sa.text(
            "ALTER TABLE provider_pricing_snapshots ENABLE TRIGGER provider_pricing_snapshots_immutable"
        )
    )
    op.execute(
        sa.text(
            "DELETE FROM model_capabilities WHERE model_definition_id IN "
            "(CAST(:text_model AS uuid), CAST(:vision_model AS uuid))"
        ).bindparams(text_model=str(GLM_52_MODEL_ID), vision_model=str(GLM_5V_TURBO_MODEL_ID))
    )
    op.execute(
        sa.text(
            "DELETE FROM provider_capabilities "
            "WHERE provider_definition_id = CAST(:provider AS uuid)"
        ).bindparams(provider=str(ZHIPU_PROVIDER_ID))
    )
    op.execute(
        sa.text(
            "DELETE FROM model_definitions WHERE provider_definition_id = CAST(:provider AS uuid)"
        ).bindparams(provider=str(ZHIPU_PROVIDER_ID))
    )
    op.execute(
        sa.text("DELETE FROM provider_definitions WHERE id = CAST(:provider AS uuid)").bindparams(
            provider=str(ZHIPU_PROVIDER_ID)
        )
    )
    op.drop_constraint(
        op.f("ck_tarot_interpretation_revisions_live_provenance_consistent"),
        "tarot_interpretation_revisions",
        type_="check",
    )
    op.drop_constraint(
        op.f("fk_tarot_interp_revisions_source_attempt"),
        "tarot_interpretation_revisions",
        type_="foreignkey",
    )
    op.drop_constraint(
        op.f("fk_tarot_interp_revisions_source_invocation"),
        "tarot_interpretation_revisions",
        type_="foreignkey",
    )
    op.drop_column("tarot_interpretation_revisions", "source_attempt_id")
    op.drop_column("tarot_interpretation_revisions", "source_invocation_id")
    for table in ("tarot_interpretation_revisions", "paint_plans"):
        op.drop_constraint(op.f(f"ck_{table}_citation_snapshot_array"), table, type_="check")
        op.drop_constraint(op.f(f"ck_{table}_retrieved_context_array"), table, type_="check")
        op.drop_column(table, "citation_snapshot")
        op.drop_column(table, "retrieved_context_snapshot")
    _replace_check(
        "tarot_interpretation_revisions",
        "ck_tarot_interpretation_revisions_source_allowed",
        "source IN ('fixture_local','user_edit')",
    )
    _replace_check(
        "invocation_requests",
        "ck_invocation_requests_family_allowed",
        "invocation_family IN ('fixture_credential_validation','fixture_model_catalog',"
        "'fixture_invocation','paint_plan_generation')",
    )
    op.drop_constraint(
        op.f("ck_provider_pricing_snapshots_currency_allowed"),
        "provider_pricing_snapshots",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_provider_pricing_snapshots_currency_usd"),
        "provider_pricing_snapshots",
        "currency = 'USD'",
    )
    for table, name, column in CURRENCY_CONSTRAINTS:
        condition = (
            "pricing_currency IS NULL OR pricing_currency IN ('FIXTURE_CREDITS','USD')"
            if column == "pricing_currency"
            else f"{column} IN ('FIXTURE_CREDITS','USD')"
        )
        _replace_check(table, name, condition)
