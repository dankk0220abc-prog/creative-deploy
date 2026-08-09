"""enable deterministic phase3a fixture registry facts

Revision ID: 3a04fab2e7a5
Revises: 3a03e9a1d6f4
Create Date: 2026-08-05 00:03:00
"""

# ruff: noqa: E501

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision: str = "3a04fab2e7a5"
down_revision: str | Sequence[str] | None = "3a03e9a1d6f4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PROVIDER_ID = uuid.UUID("3a000000-0000-4000-8000-000000000001")
TEXT_MODEL_ID = uuid.UUID("3a000000-0000-4000-8000-000000000101")
VISION_MODEL_ID = uuid.UUID("3a000000-0000-4000-8000-000000000102")
TEXT_CAPABILITY_ID = uuid.UUID("3a000000-0000-4000-8000-000000001001")
VISION_CAPABILITY_ID = uuid.UUID("3a000000-0000-4000-8000-000000001002")
STRUCTURED_CAPABILITY_ID = uuid.UUID("3a000000-0000-4000-8000-000000001003")
FIXED_TIME = datetime(2026, 8, 5, tzinfo=UTC)


def upgrade() -> None:
    connection = op.get_bind()
    connection.execute(
        sa.text("""
            INSERT INTO provider_definitions (
                id, provider_key, display_name, adapter_type, base_url_policy,
                authentication_scheme, model_catalog_mode, allow_custom_model_id,
                enabled, status, catalog_status, catalog_fresh_at, max_timeout_ms,
                max_retries, revision, created_at, updated_at
            ) VALUES (
                :id, 'fixture_local', 'Fixture Provider', 'fixture_local',
                'not_applicable', 'fixture_key', 'bundled', false, true, 'active',
                'bundled', :fixed_time, 30000, 2, 1, :fixed_time, :fixed_time
            )
        """),
        {"id": PROVIDER_ID, "fixed_time": FIXED_TIME},
    )
    capability_rows = (
        (TEXT_CAPABILITY_ID, "text_generation", "Text generation"),
        (VISION_CAPABILITY_ID, "vision_understanding", "Vision understanding"),
        (STRUCTURED_CAPABILITY_ID, "structured_output", "Structured output"),
    )
    for capability_id, capability_key, display_name in capability_rows:
        connection.execute(
            sa.text("""
                INSERT INTO capability_definitions (
                    id, capability_key, display_name, enabled, status, revision,
                    created_at, updated_at
                ) VALUES (:id, :key, :name, true, 'active', 1, :fixed_time, :fixed_time)
            """),
            {
                "id": capability_id,
                "key": capability_key,
                "name": display_name,
                "fixed_time": FIXED_TIME,
            },
        )
    model_rows = (
        (TEXT_MODEL_ID, "fixture-text-v1", "Fixture Text v1", False, True, 1),
        (VISION_MODEL_ID, "fixture-vision-v1", "Fixture Vision v1", True, True, 2),
    )
    for (
        model_id,
        model_key,
        display_name,
        supports_vision,
        supports_structured,
        price,
    ) in model_rows:
        connection.execute(
            sa.text("""
                INSERT INTO model_definitions (
                    id, provider_definition_id, provider_key, model_id, display_name,
                    catalog_source, catalog_fresh_at, catalog_status, status,
                    context_window, supports_structured_output, supports_vision,
                    pricing_minor_units, pricing_currency, revision, created_at, updated_at
                ) VALUES (
                    :id, :provider_id, 'fixture_local', :model_id, :display_name,
                    'bundled_fixture', :fixed_time, 'bundled', 'active', 4096,
                    :supports_structured, :supports_vision, :price, 'FIXTURE_CREDITS',
                    1, :fixed_time, :fixed_time
                )
            """),
            {
                "id": model_id,
                "provider_id": PROVIDER_ID,
                "model_id": model_key,
                "display_name": display_name,
                "fixed_time": FIXED_TIME,
                "supports_structured": supports_structured,
                "supports_vision": supports_vision,
                "price": price,
            },
        )
    for index, capability_id in enumerate(
        (TEXT_CAPABILITY_ID, VISION_CAPABILITY_ID, STRUCTURED_CAPABILITY_ID), start=1
    ):
        connection.execute(
            sa.text("""
                INSERT INTO provider_capabilities (
                    id, provider_definition_id, capability_definition_id,
                    source, trust_status, status, created_at
                ) VALUES (:id, :provider_id, :capability_id, 'bundled_fixture', 'trusted_fixture', 'active', :fixed_time)
            """),
            {
                "id": uuid.UUID(f"3a000000-0000-4000-8000-00000000200{index}"),
                "provider_id": PROVIDER_ID,
                "capability_id": capability_id,
                "fixed_time": FIXED_TIME,
            },
        )
    model_capabilities = (
        (TEXT_MODEL_ID, TEXT_CAPABILITY_ID),
        (TEXT_MODEL_ID, STRUCTURED_CAPABILITY_ID),
        (VISION_MODEL_ID, TEXT_CAPABILITY_ID),
        (VISION_MODEL_ID, VISION_CAPABILITY_ID),
        (VISION_MODEL_ID, STRUCTURED_CAPABILITY_ID),
    )
    for index, (model_id, capability_id) in enumerate(model_capabilities, start=1):
        connection.execute(
            sa.text("""
                INSERT INTO model_capabilities (
                    id, model_definition_id, capability_definition_id,
                    source, trust_status, status, created_at
                ) VALUES (:id, :model_id, :capability_id, 'bundled_fixture', 'trusted_fixture', 'active', :fixed_time)
            """),
            {
                "id": uuid.UUID(f"3a000000-0000-4000-8000-00000000300{index}"),
                "model_id": model_id,
                "capability_id": capability_id,
                "fixed_time": FIXED_TIME,
            },
        )


def downgrade() -> None:
    op.execute(
        sa.text("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM credential_records WHERE provider_definition_id = '3a000000-0000-4000-8000-000000000001'::uuid)
               OR EXISTS (SELECT 1 FROM user_provider_preferences WHERE default_provider_definition_id = '3a000000-0000-4000-8000-000000000001'::uuid OR default_model_definition_id IN ('3a000000-0000-4000-8000-000000000101'::uuid, '3a000000-0000-4000-8000-000000000102'::uuid))
               OR EXISTS (SELECT 1 FROM project_model_policy_providers WHERE provider_definition_id = '3a000000-0000-4000-8000-000000000001'::uuid)
               OR EXISTS (SELECT 1 FROM project_model_policy_models WHERE model_definition_id IN ('3a000000-0000-4000-8000-000000000101'::uuid, '3a000000-0000-4000-8000-000000000102'::uuid))
               OR EXISTS (SELECT 1 FROM project_model_policy_capabilities WHERE capability_definition_id IN ('3a000000-0000-4000-8000-000000001001'::uuid, '3a000000-0000-4000-8000-000000001002'::uuid, '3a000000-0000-4000-8000-000000001003'::uuid))
               OR EXISTS (SELECT 1 FROM project_model_policies WHERE default_provider_definition_id = '3a000000-0000-4000-8000-000000000001'::uuid OR default_model_definition_id IN ('3a000000-0000-4000-8000-000000000101'::uuid, '3a000000-0000-4000-8000-000000000102'::uuid))
               OR EXISTS (SELECT 1 FROM invocation_requests WHERE requested_provider_definition_id = '3a000000-0000-4000-8000-000000000001'::uuid OR requested_model_definition_id IN ('3a000000-0000-4000-8000-000000000101'::uuid, '3a000000-0000-4000-8000-000000000102'::uuid))
               OR EXISTS (SELECT 1 FROM invocation_attempts WHERE provider_definition_id = '3a000000-0000-4000-8000-000000000001'::uuid OR model_definition_id IN ('3a000000-0000-4000-8000-000000000101'::uuid, '3a000000-0000-4000-8000-000000000102'::uuid))
               OR EXISTS (SELECT 1 FROM ai_usage_ledger WHERE provider_definition_id = '3a000000-0000-4000-8000-000000000001'::uuid OR model_definition_id IN ('3a000000-0000-4000-8000-000000000101'::uuid, '3a000000-0000-4000-8000-000000000102'::uuid))
               OR EXISTS (SELECT 1 FROM ai_cost_ledger WHERE provider_definition_id = '3a000000-0000-4000-8000-000000000001'::uuid OR model_definition_id IN ('3a000000-0000-4000-8000-000000000101'::uuid, '3a000000-0000-4000-8000-000000000102'::uuid))
               OR EXISTS (SELECT 1 FROM ai_audit_events WHERE provider_definition_id = '3a000000-0000-4000-8000-000000000001'::uuid OR model_definition_id IN ('3a000000-0000-4000-8000-000000000101'::uuid, '3a000000-0000-4000-8000-000000000102'::uuid))
               OR EXISTS (
                    SELECT 1 FROM provider_capabilities
                    WHERE (provider_definition_id = '3a000000-0000-4000-8000-000000000001'::uuid
                           OR capability_definition_id IN ('3a000000-0000-4000-8000-000000001001'::uuid, '3a000000-0000-4000-8000-000000001002'::uuid, '3a000000-0000-4000-8000-000000001003'::uuid))
                      AND NOT (
                           (id = '3a000000-0000-4000-8000-000000002001'::uuid AND provider_definition_id = '3a000000-0000-4000-8000-000000000001'::uuid AND capability_definition_id = '3a000000-0000-4000-8000-000000001001'::uuid)
                        OR (id = '3a000000-0000-4000-8000-000000002002'::uuid AND provider_definition_id = '3a000000-0000-4000-8000-000000000001'::uuid AND capability_definition_id = '3a000000-0000-4000-8000-000000001002'::uuid)
                        OR (id = '3a000000-0000-4000-8000-000000002003'::uuid AND provider_definition_id = '3a000000-0000-4000-8000-000000000001'::uuid AND capability_definition_id = '3a000000-0000-4000-8000-000000001003'::uuid)
                      )
               )
               OR EXISTS (
                    SELECT 1 FROM model_capabilities
                    WHERE (model_definition_id IN ('3a000000-0000-4000-8000-000000000101'::uuid, '3a000000-0000-4000-8000-000000000102'::uuid)
                           OR capability_definition_id IN ('3a000000-0000-4000-8000-000000001001'::uuid, '3a000000-0000-4000-8000-000000001002'::uuid, '3a000000-0000-4000-8000-000000001003'::uuid))
                      AND NOT (
                           (id = '3a000000-0000-4000-8000-000000003001'::uuid AND model_definition_id = '3a000000-0000-4000-8000-000000000101'::uuid AND capability_definition_id = '3a000000-0000-4000-8000-000000001001'::uuid)
                        OR (id = '3a000000-0000-4000-8000-000000003002'::uuid AND model_definition_id = '3a000000-0000-4000-8000-000000000101'::uuid AND capability_definition_id = '3a000000-0000-4000-8000-000000001003'::uuid)
                        OR (id = '3a000000-0000-4000-8000-000000003003'::uuid AND model_definition_id = '3a000000-0000-4000-8000-000000000102'::uuid AND capability_definition_id = '3a000000-0000-4000-8000-000000001001'::uuid)
                        OR (id = '3a000000-0000-4000-8000-000000003004'::uuid AND model_definition_id = '3a000000-0000-4000-8000-000000000102'::uuid AND capability_definition_id = '3a000000-0000-4000-8000-000000001002'::uuid)
                        OR (id = '3a000000-0000-4000-8000-000000003005'::uuid AND model_definition_id = '3a000000-0000-4000-8000-000000000102'::uuid AND capability_definition_id = '3a000000-0000-4000-8000-000000001003'::uuid)
                      )
               )
            THEN
                RAISE EXCEPTION USING ERRCODE = '55000', MESSAGE = 'Phase 3A Migration D downgrade refused: fixture Registry identities are referenced';
            END IF;
        END
        $$;
    """)
    )
    op.execute(
        sa.text(
            "DELETE FROM model_capabilities WHERE model_definition_id IN ('3a000000-0000-4000-8000-000000000101'::uuid, '3a000000-0000-4000-8000-000000000102'::uuid)"
        )
    )
    op.execute(
        sa.text(
            "DELETE FROM provider_capabilities WHERE provider_definition_id = '3a000000-0000-4000-8000-000000000001'::uuid"
        )
    )
    op.execute(
        sa.text(
            "DELETE FROM model_definitions WHERE id IN ('3a000000-0000-4000-8000-000000000101'::uuid, '3a000000-0000-4000-8000-000000000102'::uuid)"
        )
    )
    op.execute(
        sa.text(
            "DELETE FROM capability_definitions WHERE id IN ('3a000000-0000-4000-8000-000000001001'::uuid, '3a000000-0000-4000-8000-000000001002'::uuid, '3a000000-0000-4000-8000-000000001003'::uuid)"
        )
    )
    op.execute(
        sa.text(
            "DELETE FROM provider_definitions WHERE id = '3a000000-0000-4000-8000-000000000001'::uuid"
        )
    )
