"""Owner-scoped Arcana Tarot vertical-slice service."""

from __future__ import annotations

import secrets
import uuid
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from creativedeploy_api.arcana.catalog import THREE_CARD_SPREAD
from creativedeploy_api.arcana.fixture_interpreter import TarotFixtureInterpreter
from creativedeploy_api.arcana.knowledge import LocalTarotKnowledgeLayer
from creativedeploy_api.core.principal import PrincipalContext, PrincipalType
from creativedeploy_api.db.models.arcana import (
    TarotCardDefinition,
    TarotInterpretationRevision,
    TarotJournalEntry,
    TarotReading,
    TarotReadingCard,
)
from creativedeploy_api.schemas.arcana import (
    TarotCardRead,
    TarotCatalogRead,
    TarotInterpretationRead,
    TarotJournalRead,
    TarotJournalUpdate,
    TarotKnowledgeRead,
    TarotReadingCardRead,
    TarotReadingCreate,
    TarotReadingHistoryRead,
    TarotReadingRead,
    TarotSharePreviewRead,
    TarotSpreadRead,
)
from creativedeploy_api.services.paint_projects import PaintProjectApplicationError


class ArcanaReadingNotFoundError(PaintProjectApplicationError):
    status_code = 404
    error_code = "ARCANA_READING_NOT_FOUND"
    category = "NOT_FOUND"
    message = "The Tarot reading was not found."
    allowed_actions = ("list_readings", "start_reading")


class ArcanaLifecycleConflictError(PaintProjectApplicationError):
    status_code = 409
    error_code = "ARCANA_LIFECYCLE_CONFLICT"
    category = "CONFLICT"
    message = "The Tarot reading is not in the required lifecycle state."
    allowed_actions = ("reload_reading",)


class ArcanaActorNotAllowedError(PaintProjectApplicationError):
    status_code = 403
    error_code = "ARCANA_ACTOR_NOT_AUTHORIZED"
    category = "CONFLICT"
    message = "Arcana readings require an authenticated human Principal."


class ArcanaService:
    def __init__(
        self, session: AsyncSession, interpreter: TarotFixtureInterpreter | None = None
    ) -> None:
        self._session = session
        self._interpreter = interpreter or TarotFixtureInterpreter()
        self._knowledge = LocalTarotKnowledgeLayer()

    @staticmethod
    def _owner(principal: PrincipalContext) -> str:
        if principal.principal_type is not PrincipalType.HUMAN:
            raise ArcanaActorNotAllowedError
        return principal.principal_id

    @staticmethod
    def _spread() -> TarotSpreadRead:
        return TarotSpreadRead.model_validate(THREE_CARD_SPREAD)

    @staticmethod
    def _card(card: TarotCardDefinition) -> TarotCardRead:
        knowledge: list[TarotKnowledgeRead] = []
        raw_knowledge = card.orientation_knowledge
        for orientation in ("upright", "reversed"):
            localized = raw_knowledge.get(orientation)
            if not isinstance(localized, Mapping):
                continue
            for locale in ("en-US", "zh-CN"):
                content = localized.get(locale)
                if isinstance(content, str):
                    knowledge.append(
                        TarotKnowledgeRead(
                            knowledge_id=f"arcana:{card.id}:{orientation}:{locale}:meaning:v1",
                            orientation=orientation,
                            locale=locale,
                            section="meaning",
                            content=content,
                            source=dict(card.source_metadata),
                        )
                    )
        return TarotCardRead.model_validate(
            {
                "id": card.id,
                "arcana": card.arcana,
                "suit": card.suit,
                "rank": card.rank,
                "number": card.number,
                "name_en": card.name_en,
                "name_zh": card.name_zh,
                "theme": str(card.symbolic_metadata.get("theme", card.id)),
                "knowledge": knowledge,
            }
        )

    async def catalog(self) -> TarotCatalogRead:
        cards = (
            await self._session.scalars(
                select(TarotCardDefinition).order_by(
                    TarotCardDefinition.arcana, TarotCardDefinition.suit, TarotCardDefinition.number
                )
            )
        ).all()
        return TarotCatalogRead(cards=[self._card(card) for card in cards], spread=self._spread())

    async def start(
        self, payload: TarotReadingCreate, principal: PrincipalContext
    ) -> TarotReadingRead:
        now = datetime.now(UTC)
        reading = TarotReading(
            owner_principal_id=self._owner(principal),
            status="draft",
            question=payload.question,
            generation_locale=payload.generation_locale,
            spread_key="past-present-future",
            spread_version=1,
            created_at=now,
            updated_at=now,
        )
        self._session.add(reading)
        await self._session.commit()
        return await self._read(reading)

    async def _owned(
        self, reading_id: uuid.UUID, principal: PrincipalContext, *, for_update: bool = False
    ) -> TarotReading:
        statement = select(TarotReading).where(
            TarotReading.id == reading_id,
            TarotReading.owner_principal_id == self._owner(principal),
        )
        if for_update:
            statement = statement.with_for_update()
        reading = await self._session.scalar(statement)
        if reading is None:
            raise ArcanaReadingNotFoundError
        return reading

    async def draw(
        self, reading_id: uuid.UUID, principal: PrincipalContext, *, test_seed: int | None = None
    ) -> TarotReadingRead:
        reading = await self._owned(reading_id, principal, for_update=True)
        if reading.status != "draft":
            raise ArcanaLifecycleConflictError
        cards = list(
            (
                await self._session.scalars(
                    select(TarotCardDefinition).order_by(TarotCardDefinition.id)
                )
            ).all()
        )
        if len(cards) != 78:
            raise RuntimeError("Arcana deck integrity check failed")
        if test_seed is None:
            random_source: secrets.SystemRandom = secrets.SystemRandom()
        else:
            import random

            random_source = random.Random(test_seed)  # type: ignore[assignment]
        selected = random_source.sample(cards, 3)
        positions = THREE_CARD_SPREAD["positions"]
        assert isinstance(positions, list)
        now = datetime.now(UTC)
        for index, card in enumerate(selected):
            position = positions[index]
            assert isinstance(position, dict)
            self._session.add(
                TarotReadingCard(
                    reading_id=reading.id,
                    card_definition_id=card.id,
                    position_index=index,
                    position_key=str(position["key"]),
                    position_name_en=str(position["name_en"]),
                    position_name_zh=str(position["name_zh"]),
                    orientation="reversed" if random_source.getrandbits(1) else "upright",
                    draw_order=index + 1,
                    drawn_at=now,
                )
            )
        reading.status = "drawn"
        reading.drawn_at = now
        reading.updated_at = now
        await self._session.commit()
        return await self._read(reading)

    async def interpret(
        self, reading_id: uuid.UUID, principal: PrincipalContext
    ) -> TarotReadingRead:
        reading = await self._owned(reading_id, principal, for_update=True)
        if reading.status == "draft":
            raise ArcanaLifecycleConflictError
        existing = await self._session.scalar(
            select(TarotInterpretationRevision)
            .where(TarotInterpretationRevision.reading_id == reading.id)
            .order_by(TarotInterpretationRevision.revision.desc())
        )
        if existing is not None:
            return await self._read(reading)
        rows = (
            await self._session.execute(
                select(TarotReadingCard, TarotCardDefinition)
                .join(
                    TarotCardDefinition,
                    TarotCardDefinition.id == TarotReadingCard.card_definition_id,
                )
                .where(TarotReadingCard.reading_id == reading.id)
                .order_by(TarotReadingCard.position_index)
            )
        ).all()
        if len(rows) != 3:
            raise ArcanaLifecycleConflictError
        payload_cards: list[dict[str, object]] = []
        for draw, card in rows:
            localized = card.orientation_knowledge[draw.orientation]
            locale: Literal["zh-CN", "en-US"] = (
                "zh-CN" if reading.generation_locale == "zh-CN" else "en-US"
            )
            knowledge_context = self._knowledge.context_for(
                card_id=card.id,
                card_name=card.name_zh if locale == "zh-CN" else card.name_en,
                orientation=draw.orientation,
                position_key=draw.position_key,
                meaning=str(localized[locale]),
                arcana=card.arcana,
                suit=card.suit,
                rank=card.rank,
                theme=str(card.symbolic_metadata.get("theme", card.id)),
                locale=locale,
            ).as_payload()
            knowledge_context["position_name"] = (
                draw.position_name_zh if locale == "zh-CN" else draw.position_name_en
            )
            payload_cards.append(knowledge_context)
        payload: dict[str, object] = {
            "question": reading.question,
            "generation_locale": reading.generation_locale,
            "spread_key": reading.spread_key,
            "spread_version": reading.spread_version,
            "cards": payload_cards,
        }
        input_hash, document = self._interpreter.interpret(payload)
        now = datetime.now(UTC)
        self._session.add(
            TarotInterpretationRevision(
                reading_id=reading.id,
                revision=1,
                source="fixture_local",
                schema_version="tarot-reading.v2",
                provider_key=self._interpreter.provider_key,
                model_id=self._interpreter.model_id,
                adapter_version=self._interpreter.adapter_version,
                prompt_version=self._interpreter.prompt_version,
                input_hash=input_hash,
                document=document.model_dump(mode="json"),
                created_at=now,
            )
        )
        reading.status = "interpreted"
        reading.interpreted_at = now
        reading.updated_at = now
        await self._session.commit()
        return await self._read(reading)

    async def save_journal(
        self, reading_id: uuid.UUID, payload: TarotJournalUpdate, principal: PrincipalContext
    ) -> TarotReadingRead:
        reading = await self._owned(reading_id, principal, for_update=True)
        if reading.status not in {"interpreted", "saved"}:
            raise ArcanaLifecycleConflictError
        now = datetime.now(UTC)
        journal = await self._session.scalar(
            select(TarotJournalEntry)
            .where(TarotJournalEntry.reading_id == reading.id)
            .with_for_update()
        )
        if journal is None:
            journal = TarotJournalEntry(
                reading_id=reading.id,
                owner_principal_id=self._owner(principal),
                personal_interpretation=payload.personal_interpretation,
                notes=payload.notes,
                created_at=now,
                updated_at=now,
            )
            self._session.add(journal)
        else:
            journal.personal_interpretation = payload.personal_interpretation
            journal.notes = payload.notes
            journal.updated_at = now
        reading.status = "saved"
        reading.saved_at = reading.saved_at or now
        reading.updated_at = now
        await self._session.commit()
        return await self._read(reading)

    async def get(self, reading_id: uuid.UUID, principal: PrincipalContext) -> TarotReadingRead:
        return await self._read(await self._owned(reading_id, principal))

    async def history(self, principal: PrincipalContext) -> TarotReadingHistoryRead:
        readings = (
            await self._session.scalars(
                select(TarotReading)
                .where(TarotReading.owner_principal_id == self._owner(principal))
                .order_by(TarotReading.created_at.desc())
                .limit(50)
            )
        ).all()
        return TarotReadingHistoryRead(items=[await self._read(reading) for reading in readings])

    async def share_preview(
        self, reading_id: uuid.UUID, principal: PrincipalContext
    ) -> TarotSharePreviewRead:
        reading = await self.get(reading_id, principal)
        if reading.interpretation is None:
            raise ArcanaLifecycleConflictError
        return TarotSharePreviewRead(
            reading_id=reading.id,
            question=reading.question,
            generation_locale=reading.generation_locale,
            cards=reading.cards,
            concise_interpretation=reading.interpretation.document.summary,
        )

    async def _read(self, reading: TarotReading) -> TarotReadingRead:
        rows = (
            await self._session.execute(
                select(TarotReadingCard, TarotCardDefinition)
                .join(
                    TarotCardDefinition,
                    TarotCardDefinition.id == TarotReadingCard.card_definition_id,
                )
                .where(TarotReadingCard.reading_id == reading.id)
                .order_by(TarotReadingCard.position_index)
            )
        ).all()
        cards = [
            TarotReadingCardRead(
                card=self._card(card),
                position_index=draw.position_index,
                position_key=draw.position_key,
                position_name_en=draw.position_name_en,
                position_name_zh=draw.position_name_zh,
                orientation=draw.orientation,
                draw_order=draw.draw_order,
                drawn_at=draw.drawn_at,
            )
            for draw, card in rows
        ]
        interpretation_row = await self._session.scalar(
            select(TarotInterpretationRevision)
            .where(TarotInterpretationRevision.reading_id == reading.id)
            .order_by(TarotInterpretationRevision.revision.desc())
        )
        interpretation = (
            None
            if interpretation_row is None
            else TarotInterpretationRead.model_validate(
                {
                    "revision": interpretation_row.revision,
                    "source": interpretation_row.source,
                    "provider_key": interpretation_row.provider_key,
                    "model_id": interpretation_row.model_id,
                    "adapter_version": interpretation_row.adapter_version,
                    "prompt_version": interpretation_row.prompt_version,
                    "input_hash": interpretation_row.input_hash,
                    "document": interpretation_row.document,
                    "created_at": interpretation_row.created_at,
                }
            )
        )
        journal_row = await self._session.scalar(
            select(TarotJournalEntry).where(TarotJournalEntry.reading_id == reading.id)
        )
        journal = (
            None
            if journal_row is None
            else TarotJournalRead(
                personal_interpretation=journal_row.personal_interpretation,
                notes=journal_row.notes,
                created_at=journal_row.created_at,
                updated_at=journal_row.updated_at,
            )
        )
        return TarotReadingRead.model_validate(
            {
                "id": reading.id,
                "question": reading.question,
                "status": reading.status,
                "generation_locale": reading.generation_locale,
                "spread": self._spread(),
                "cards": cards,
                "interpretation": interpretation,
                "journal": journal,
                "created_at": reading.created_at,
                "updated_at": reading.updated_at,
                "drawn_at": reading.drawn_at,
                "interpreted_at": reading.interpreted_at,
                "saved_at": reading.saved_at,
            }
        )
