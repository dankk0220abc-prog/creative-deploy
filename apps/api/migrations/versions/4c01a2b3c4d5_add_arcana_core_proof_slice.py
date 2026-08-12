"""add Arcana Tarot core proof slice

Revision ID: 4c01a2b3c4d5
Revises: 3b01a1c2d3e4
Create Date: 2026-08-11 00:00:00
"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from creativedeploy_api.arcana.catalog import THREE_CARD_SPREAD, card_seeds

revision: str = "4c01a2b3c4d5"
down_revision: str | Sequence[str] | None = "3b01a1c2d3e4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _created_at() -> sa.Column[object]:
    return sa.Column(
        "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
    )


def upgrade() -> None:
    card_table = op.create_table(
        "tarot_card_definitions",
        sa.Column("id", sa.String(64), nullable=False),
        sa.Column("arcana", sa.String(16), nullable=False),
        sa.Column("suit", sa.String(16), nullable=True),
        sa.Column("rank", sa.String(24), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("name_en", sa.String(80), nullable=False),
        sa.Column("name_zh", sa.String(80), nullable=False),
        sa.Column("orientation_knowledge", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("symbolic_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("source_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.CheckConstraint(
            "arcana IN ('major','minor')", name=op.f("ck_tarot_card_definitions_arcana_allowed")
        ),
        sa.CheckConstraint(
            "orientation_knowledge IS NOT NULL",
            name=op.f("ck_tarot_card_definitions_knowledge_present"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tarot_card_definitions")),
    )
    spread_table = op.create_table(
        "tarot_spread_definitions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("spread_key", sa.String(64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("name_en", sa.String(100), nullable=False),
        sa.Column("name_zh", sa.String(100), nullable=False),
        sa.Column("positions", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tarot_spread_definitions")),
        sa.UniqueConstraint(
            "spread_key", "version", name="uq_tarot_spread_definitions_key_version"
        ),
    )
    op.bulk_insert(
        card_table,
        [
            {
                "id": card.card_id,
                "arcana": card.arcana,
                "suit": card.suit,
                "rank": card.rank,
                "number": card.number,
                "name_en": card.name_en,
                "name_zh": card.name_zh,
                "orientation_knowledge": {
                    "upright": {"en-US": card.upright_en, "zh-CN": card.upright_zh},
                    "reversed": {"en-US": card.reversed_en, "zh-CN": card.reversed_zh},
                },
                "symbolic_metadata": {"theme": card.theme},
                "source_metadata": {
                    "source_type": "original_synthesis",
                    "source_name": "CreativeDeploy Arcana Core v1",
                    "public_domain_artwork": False,
                    "copyrighted_commercial_artwork": False,
                },
            }
            for card in card_seeds()
        ],
    )
    op.bulk_insert(
        spread_table,
        [
            {
                "id": uuid.UUID("4c000000-0000-4000-8000-000000000001"),
                "spread_key": THREE_CARD_SPREAD["key"],
                "version": THREE_CARD_SPREAD["version"],
                "name_en": THREE_CARD_SPREAD["name_en"],
                "name_zh": THREE_CARD_SPREAD["name_zh"],
                "positions": THREE_CARD_SPREAD["positions"],
            }
        ],
    )

    op.create_table(
        "tarot_readings",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("owner_principal_id", sa.String(128), nullable=False),
        sa.Column("status", sa.String(24), server_default=sa.text("'draft'"), nullable=False),
        sa.Column("question", sa.String(500), nullable=False),
        sa.Column("generation_locale", sa.String(8), nullable=False),
        sa.Column("spread_key", sa.String(64), nullable=False),
        sa.Column("spread_version", sa.Integer(), nullable=False),
        _created_at(),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("drawn_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("interpreted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("saved_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('draft','drawn','interpreted','saved')",
            name=op.f("ck_tarot_readings_status_allowed"),
        ),
        sa.CheckConstraint(
            "generation_locale IN ('zh-CN','en-US')", name=op.f("ck_tarot_readings_locale_allowed")
        ),
        sa.CheckConstraint(
            "length(question) BETWEEN 1 AND 500", name=op.f("ck_tarot_readings_question_length")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tarot_readings")),
    )
    op.create_index(
        "ix_tarot_readings_owner_created",
        "tarot_readings",
        ["owner_principal_id", "created_at"],
        unique=False,
    )
    op.create_table(
        "tarot_reading_cards",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("reading_id", sa.UUID(), nullable=False),
        sa.Column("card_definition_id", sa.String(64), nullable=False),
        sa.Column("position_index", sa.Integer(), nullable=False),
        sa.Column("position_key", sa.String(32), nullable=False),
        sa.Column("position_name_en", sa.String(60), nullable=False),
        sa.Column("position_name_zh", sa.String(60), nullable=False),
        sa.Column("orientation", sa.String(16), nullable=False),
        sa.Column("draw_order", sa.Integer(), nullable=False),
        sa.Column(
            "drawn_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.CheckConstraint(
            "orientation IN ('upright','reversed')",
            name=op.f("ck_tarot_reading_cards_orientation_allowed"),
        ),
        sa.CheckConstraint(
            "position_index BETWEEN 0 AND 2 AND draw_order BETWEEN 1 AND 3",
            name=op.f("ck_tarot_reading_cards_three_positions"),
        ),
        sa.ForeignKeyConstraint(
            ["reading_id"],
            ["tarot_readings.id"],
            name=op.f("fk_tarot_reading_cards_reading_id_tarot_readings"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["card_definition_id"],
            ["tarot_card_definitions.id"],
            name="fk_tarot_reading_cards_card_definition",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tarot_reading_cards")),
        sa.UniqueConstraint(
            "reading_id", "card_definition_id", name="uq_tarot_reading_cards_reading_card"
        ),
        sa.UniqueConstraint(
            "reading_id", "position_index", name="uq_tarot_reading_cards_reading_position"
        ),
    )
    op.create_table(
        "tarot_interpretation_revisions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("reading_id", sa.UUID(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(24), nullable=False),
        sa.Column("schema_version", sa.String(40), nullable=False),
        sa.Column("provider_key", sa.String(64), nullable=False),
        sa.Column("model_id", sa.String(160), nullable=False),
        sa.Column("adapter_version", sa.String(64), nullable=False),
        sa.Column("prompt_version", sa.Integer(), nullable=False),
        sa.Column("input_hash", sa.String(64), nullable=False),
        sa.Column("document", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        _created_at(),
        sa.CheckConstraint(
            "source IN ('fixture_local','user_edit')",
            name=op.f("ck_tarot_interpretation_revisions_source_allowed"),
        ),
        sa.ForeignKeyConstraint(
            ["reading_id"],
            ["tarot_readings.id"],
            name=op.f("fk_tarot_interpretation_revisions_reading_id_tarot_readings"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tarot_interpretation_revisions")),
        sa.UniqueConstraint(
            "reading_id", "revision", name="uq_tarot_interpretation_revisions_reading_revision"
        ),
    )
    op.create_index(
        "ix_tarot_interpretation_revisions_reading",
        "tarot_interpretation_revisions",
        ["reading_id"],
        unique=False,
    )
    op.create_table(
        "tarot_journal_entries",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("reading_id", sa.UUID(), nullable=False),
        sa.Column("owner_principal_id", sa.String(128), nullable=False),
        sa.Column(
            "personal_interpretation", sa.Text(), server_default=sa.text("''"), nullable=False
        ),
        sa.Column("notes", sa.Text(), server_default=sa.text("''"), nullable=False),
        _created_at(),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["reading_id"],
            ["tarot_readings.id"],
            name=op.f("fk_tarot_journal_entries_reading_id_tarot_readings"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tarot_journal_entries")),
        sa.UniqueConstraint("reading_id", name="uq_tarot_journal_entries_reading"),
    )


def downgrade() -> None:
    op.drop_table("tarot_journal_entries")
    op.drop_index(
        "ix_tarot_interpretation_revisions_reading", table_name="tarot_interpretation_revisions"
    )
    op.drop_table("tarot_interpretation_revisions")
    op.drop_table("tarot_reading_cards")
    op.drop_index("ix_tarot_readings_owner_created", table_name="tarot_readings")
    op.drop_table("tarot_readings")
    op.drop_table("tarot_spread_definitions")
    op.drop_table("tarot_card_definitions")
