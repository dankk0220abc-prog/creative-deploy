"""add phase3a provider model capability registries

Revision ID: 3a01c7e9b4d2
Revises: 2b1c4d5e6f70
Create Date: 2026-08-05 00:00:00
"""

# ruff: noqa: E501

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "3a01c7e9b4d2"
down_revision: str | Sequence[str] | None = "2b1c4d5e6f70"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "provider_definitions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("provider_key", sa.String(64), nullable=False),
        sa.Column("display_name", sa.String(160), nullable=False),
        sa.Column("adapter_type", sa.String(64), nullable=False),
        sa.Column("base_url_policy", sa.String(32), nullable=False),
        sa.Column("authentication_scheme", sa.String(64), nullable=False),
        sa.Column("model_catalog_mode", sa.String(32), nullable=False),
        sa.Column(
            "allow_custom_model_id", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("catalog_status", sa.String(32), nullable=False),
        sa.Column("catalog_fresh_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("max_timeout_ms", sa.Integer(), nullable=False),
        sa.Column("max_retries", sa.Integer(), nullable=False),
        sa.Column("revision", sa.Integer(), server_default=sa.text("1"), nullable=False),
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
            "status IN ('active','disabled','retired')",
            name=op.f("ck_provider_definitions_status_allowed"),
        ),
        sa.CheckConstraint(
            "base_url_policy IN ('provider_managed','allowlisted_custom','not_applicable')",
            name=op.f("ck_provider_definitions_base_url_policy_allowed"),
        ),
        sa.CheckConstraint(
            "model_catalog_mode IN ('bundled','remote_refresh','user_supplied')",
            name=op.f("ck_provider_definitions_catalog_mode_allowed"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_provider_definitions")),
        sa.UniqueConstraint("provider_key", name="uq_provider_definitions_provider_key"),
    )
    op.create_table(
        "capability_definitions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("capability_key", sa.String(64), nullable=False),
        sa.Column("display_name", sa.String(160), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("revision", sa.Integer(), server_default=sa.text("1"), nullable=False),
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
            "status IN ('active','disabled','retired')",
            name=op.f("ck_capability_definitions_status_allowed"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_capability_definitions")),
        sa.UniqueConstraint("capability_key", name="uq_capability_definitions_capability_key"),
    )
    op.create_table(
        "model_definitions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("provider_definition_id", sa.UUID(), nullable=False),
        sa.Column("provider_key", sa.String(64), nullable=False),
        sa.Column("model_id", sa.String(160), nullable=False),
        sa.Column("display_name", sa.String(160), nullable=False),
        sa.Column("catalog_source", sa.String(64), nullable=False),
        sa.Column("catalog_fresh_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("catalog_status", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("context_window", sa.Integer(), nullable=True),
        sa.Column(
            "supports_structured_output",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("supports_vision", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("pricing_minor_units", sa.BigInteger(), nullable=True),
        sa.Column("pricing_currency", sa.String(32), nullable=True),
        sa.Column("revision", sa.Integer(), server_default=sa.text("1"), nullable=False),
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
            "status IN ('active','disabled','unknown','unsupported','retired')",
            name=op.f("ck_model_definitions_status_allowed"),
        ),
        sa.CheckConstraint(
            "pricing_currency IS NULL OR pricing_currency = 'FIXTURE_CREDITS'",
            name=op.f("ck_model_definitions_fixture_currency_only"),
        ),
        sa.ForeignKeyConstraint(
            ["provider_definition_id"],
            ["provider_definitions.id"],
            name="fk_model_definitions_provider_provider_definitions",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_model_definitions")),
        sa.UniqueConstraint("provider_key", "model_id", name="uq_model_definitions_provider_model"),
    )
    op.create_index(
        "ix_model_definitions_provider_status",
        "model_definitions",
        ["provider_definition_id", "status"],
    )
    for table_name, source_column, source_table, source_constraint in (
        ("provider_capabilities", "provider_definition_id", "provider_definitions", "provider"),
        ("model_capabilities", "model_definition_id", "model_definitions", "model"),
    ):
        op.create_table(
            table_name,
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column(source_column, sa.UUID(), nullable=False),
            sa.Column("capability_definition_id", sa.UUID(), nullable=False),
            sa.Column("source", sa.String(64), nullable=False),
            sa.Column("trust_status", sa.String(32), nullable=False),
            sa.Column("status", sa.String(32), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(
                [source_column],
                [f"{source_table}.id"],
                name=f"fk_{table_name}_{source_constraint}_{source_table}",
                ondelete="RESTRICT",
            ),
            sa.ForeignKeyConstraint(
                ["capability_definition_id"],
                ["capability_definitions.id"],
                name=f"fk_{table_name}_capability_capability_definitions",
                ondelete="RESTRICT",
            ),
            sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{table_name}")),
            sa.UniqueConstraint(
                source_column,
                "capability_definition_id",
                name=f"uq_{table_name}_{source_constraint}_capability",
            ),
        )
        op.create_index(f"ix_{table_name}_capability", table_name, ["capability_definition_id"])


def downgrade() -> None:
    op.execute(
        sa.text("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM provider_capabilities)
               OR EXISTS (SELECT 1 FROM model_capabilities)
               OR EXISTS (SELECT 1 FROM model_definitions)
               OR EXISTS (SELECT 1 FROM capability_definitions)
               OR EXISTS (SELECT 1 FROM provider_definitions)
            THEN
                RAISE EXCEPTION USING ERRCODE = '55000', MESSAGE = 'Phase 3A Migration A downgrade refused: Registry facts exist';
            END IF;
        END
        $$;
    """)
    )
    op.drop_index("ix_model_capabilities_capability", table_name="model_capabilities")
    op.drop_table("model_capabilities")
    op.drop_index("ix_provider_capabilities_capability", table_name="provider_capabilities")
    op.drop_table("provider_capabilities")
    op.drop_index("ix_model_definitions_provider_status", table_name="model_definitions")
    op.drop_table("model_definitions")
    op.drop_table("capability_definitions")
    op.drop_table("provider_definitions")
