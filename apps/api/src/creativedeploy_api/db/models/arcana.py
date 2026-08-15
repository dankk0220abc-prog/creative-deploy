"""Persistent Arcana Tarot reading, draw, interpretation, and journal facts."""

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql.elements import conv

from creativedeploy_api.db.base import Base


class TarotCardDefinition(Base):
    __tablename__ = "tarot_card_definitions"
    __table_args__ = (
        CheckConstraint(
            "arcana IN ('major','minor')", name=conv("ck_tarot_card_definitions_arcana_allowed")
        ),
        CheckConstraint(
            "orientation_knowledge IS NOT NULL",
            name=conv("ck_tarot_card_definitions_knowledge_present"),
        ),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    arcana: Mapped[str] = mapped_column(String(16), nullable=False)
    suit: Mapped[str | None] = mapped_column(String(16), nullable=True)
    rank: Mapped[str] = mapped_column(String(24), nullable=False)
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    name_en: Mapped[str] = mapped_column(String(80), nullable=False)
    name_zh: Mapped[str] = mapped_column(String(80), nullable=False)
    orientation_knowledge: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    symbolic_metadata: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    source_metadata: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)


class TarotSpreadDefinition(Base):
    __tablename__ = "tarot_spread_definitions"
    __table_args__ = (
        UniqueConstraint("spread_key", "version", name="uq_tarot_spread_definitions_key_version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    spread_key: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    name_en: Mapped[str] = mapped_column(String(100), nullable=False)
    name_zh: Mapped[str] = mapped_column(String(100), nullable=False)
    positions: Mapped[list[dict[str, object]]] = mapped_column(JSONB, nullable=False)


class TarotReading(Base):
    __tablename__ = "tarot_readings"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft','drawn','interpreted','saved')",
            name=conv("ck_tarot_readings_status_allowed"),
        ),
        CheckConstraint(
            "generation_locale IN ('zh-CN','en-US')", name=conv("ck_tarot_readings_locale_allowed")
        ),
        CheckConstraint(
            "length(question) BETWEEN 1 AND 500", name=conv("ck_tarot_readings_question_length")
        ),
        Index("ix_tarot_readings_owner_created", "owner_principal_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    owner_principal_id: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, server_default=text("'draft'"))
    question: Mapped[str] = mapped_column(String(500), nullable=False)
    generation_locale: Mapped[str] = mapped_column(String(8), nullable=False)
    spread_key: Mapped[str] = mapped_column(String(64), nullable=False)
    spread_version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    drawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    interpreted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    saved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class TarotReadingCard(Base):
    __tablename__ = "tarot_reading_cards"
    __table_args__ = (
        CheckConstraint(
            "orientation IN ('upright','reversed')",
            name=conv("ck_tarot_reading_cards_orientation_allowed"),
        ),
        CheckConstraint(
            "position_index BETWEEN 0 AND 2 AND draw_order BETWEEN 1 AND 3",
            name=conv("ck_tarot_reading_cards_three_positions"),
        ),
        UniqueConstraint(
            "reading_id", "position_index", name="uq_tarot_reading_cards_reading_position"
        ),
        UniqueConstraint(
            "reading_id", "card_definition_id", name="uq_tarot_reading_cards_reading_card"
        ),
        ForeignKeyConstraint(
            ["card_definition_id"],
            ["tarot_card_definitions.id"],
            name="fk_tarot_reading_cards_card_definition",
            ondelete="RESTRICT",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    reading_id: Mapped[uuid.UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("tarot_readings.id", ondelete="RESTRICT"),
        nullable=False,
    )
    card_definition_id: Mapped[str] = mapped_column(String(64), nullable=False)
    position_index: Mapped[int] = mapped_column(Integer, nullable=False)
    position_key: Mapped[str] = mapped_column(String(32), nullable=False)
    position_name_en: Mapped[str] = mapped_column(String(60), nullable=False)
    position_name_zh: Mapped[str] = mapped_column(String(60), nullable=False)
    orientation: Mapped[str] = mapped_column(String(16), nullable=False)
    draw_order: Mapped[int] = mapped_column(Integer, nullable=False)
    drawn_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class TarotInterpretationRevision(Base):
    __tablename__ = "tarot_interpretation_revisions"
    __table_args__ = (
        CheckConstraint(
            "source IN ('fixture_local','zhipu_live','user_edit')",
            name=conv("ck_tarot_interpretation_revisions_source_allowed"),
        ),
        CheckConstraint(
            "jsonb_typeof(retrieved_context_snapshot) = 'array'",
            name=conv("ck_tarot_interpretation_revisions_retrieved_context_array"),
        ),
        CheckConstraint(
            "jsonb_typeof(citation_snapshot) = 'array'",
            name=conv("ck_tarot_interpretation_revisions_citation_snapshot_array"),
        ),
        CheckConstraint(
            "(source = 'zhipu_live' AND source_invocation_id IS NOT NULL "
            "AND source_attempt_id IS NOT NULL "
            "AND jsonb_array_length(retrieved_context_snapshot) > 0 "
            "AND jsonb_array_length(citation_snapshot) > 0) OR "
            "(source <> 'zhipu_live' AND source_invocation_id IS NULL "
            "AND source_attempt_id IS NULL)",
            name=conv("ck_tarot_interpretation_revisions_live_provenance_consistent"),
        ),
        UniqueConstraint(
            "reading_id", "revision", name="uq_tarot_interpretation_revisions_reading_revision"
        ),
        Index("ix_tarot_interpretation_revisions_reading", "reading_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    reading_id: Mapped[uuid.UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("tarot_readings.id", ondelete="RESTRICT"),
        nullable=False,
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    source: Mapped[str] = mapped_column(String(24), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(40), nullable=False)
    provider_key: Mapped[str] = mapped_column(String(64), nullable=False)
    model_id: Mapped[str] = mapped_column(String(160), nullable=False)
    adapter_version: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt_version: Mapped[int] = mapped_column(Integer, nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    document: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    retrieved_context_snapshot: Mapped[list[dict[str, object]]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    citation_snapshot: Mapped[list[dict[str, object]]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    source_invocation_id: Mapped[uuid.UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "invocation_requests.id",
            name="fk_tarot_interp_revisions_source_invocation",
            ondelete="RESTRICT",
        ),
        nullable=True,
    )
    source_attempt_id: Mapped[uuid.UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "invocation_attempts.id",
            name="fk_tarot_interp_revisions_source_attempt",
            ondelete="RESTRICT",
        ),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class TarotJournalEntry(Base):
    __tablename__ = "tarot_journal_entries"
    __table_args__ = (UniqueConstraint("reading_id", name="uq_tarot_journal_entries_reading"),)

    id: Mapped[uuid.UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    reading_id: Mapped[uuid.UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("tarot_readings.id", ondelete="RESTRICT"),
        nullable=False,
    )
    owner_principal_id: Mapped[str] = mapped_column(String(128), nullable=False)
    personal_interpretation: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("''")
    )
    notes: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
