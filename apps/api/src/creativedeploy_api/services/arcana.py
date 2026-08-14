"""Owner-scoped Arcana Tarot vertical-slice service."""

from __future__ import annotations

import hashlib
import json
import secrets
import uuid
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Final, Literal

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from creativedeploy_api.ai.provider_transport import (
    GovernedMultimodalPrompt,
    ProviderContractError,
    StructuredOutputValidationError,
)
from creativedeploy_api.ai.retrieval import (
    RetrievalContractError,
    RetrievedCitation,
    RetrievedContextBundle,
    RetrievedContextUnit,
    validate_retrieved_citations,
)
from creativedeploy_api.ai.zhipu_provider import (
    ZHIPU_ARCANA_MAX_OUTPUT_TOKENS,
    ZHIPU_GLM_52_MODEL,
    ZhipuChatAdapter,
)
from creativedeploy_api.arcana.catalog import THREE_CARD_SPREAD
from creativedeploy_api.arcana.fixture_interpreter import TarotFixtureInterpreter
from creativedeploy_api.arcana.knowledge import LocalTarotKnowledgeLayer
from creativedeploy_api.arcana.quality import validate_question_aware_readiness
from creativedeploy_api.arcana.question_analysis import analyze_question
from creativedeploy_api.arcana.relationships import (
    RelationshipCard,
    RelationshipSignal,
    assemble_relationship_signals,
)
from creativedeploy_api.core.principal import PrincipalContext, PrincipalType
from creativedeploy_api.db.models.arcana import (
    TarotCardDefinition,
    TarotInterpretationRevision,
    TarotJournalEntry,
    TarotReading,
    TarotReadingCard,
)
from creativedeploy_api.db.models.paint_plan import ProviderPricingSnapshot
from creativedeploy_api.schemas.arcana import (
    ARCANA_LIVE_OUTPUT_CONTRACT,
    TarotCardRead,
    TarotCatalogRead,
    TarotInterpretationDocument,
    TarotInterpretationRead,
    TarotJournalRead,
    TarotJournalUpdate,
    TarotKnowledgeRead,
    TarotLiveInterpretRequest,
    TarotReadingCardRead,
    TarotReadingCreate,
    TarotReadingHistoryRead,
    TarotReadingRead,
    TarotSharePreviewRead,
    TarotSpreadRead,
)
from creativedeploy_api.services.paint_projects import PaintProjectApplicationError
from creativedeploy_api.services.zhipu_invocations import (
    GovernedZhipuInvocationService,
    ZhipuBusinessResourceClaim,
    ZhipuLiveSelection,
)


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


class ArcanaLiveUnavailableError(PaintProjectApplicationError):
    status_code = 409
    error_code = "ARCANA_ZHIPU_LIVE_UNAVAILABLE"
    category = "CONFLICT"
    message = "The governed Zhipu live interpretation path is unavailable."
    allowed_actions = ("use_fixture_interpretation", "review_ai_settings")


def _pydantic_error_path(error: ValidationError) -> str:
    errors = error.errors(include_url=False, include_context=False, include_input=False)
    if not errors:
        return "$"
    path = "$"
    for component in errors[0].get("loc", ()):
        path += f"[{component}]" if isinstance(component, int) else f".{component}"
    return path[:240]


_MISSING_STRUCTURED_VALUE = object()
_ARCANA_EXPECTED_JSON_TYPES = {
    "schema_version": "string",
    "generation_locale": "string",
    "question_restatement": "string",
    "summary": "string",
    "positions": "array<object>",
    "synthesis": "string",
    "relationship_analysis": "array<object>",
    "actionable_reflections": "array<string>",
    "reflection_prompts": "array<string>",
    "knowledge_basis": "array<object>",
    "uncertainty": "string",
}
_ARCANA_ITEM_KEY_ALLOWLIST = {
    "positions": frozenset({"position_key", "card_id", "orientation", "headline", "contribution"}),
    "relationship_analysis": frozenset({"kind", "headline", "content"}),
    "knowledge_basis": frozenset(
        {"card_id", "knowledge_id", "source_id", "source_title", "retrieval_mode"}
    ),
}
ARCANA_LIVE_PROMPT_VERSION: Final = 6


def _structured_json_shape(value: object) -> str:
    if value is _MISSING_STRUCTURED_VALUE:
        return "missing"
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, str):
        return "string"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, Mapping):
        return "object"
    if isinstance(value, list):
        if not value:
            return "array<empty>"
        item_shapes = {_structured_json_shape(item) for item in value}
        if len(item_shapes) != 1:
            return "array<mixed>"
        item_shape = next(iter(item_shapes))
        if item_shape in {"object", "string", "integer", "number", "boolean", "null"}:
            return f"array<{item_shape}>"
        return "array<mixed>"
    return "unknown"


def _pydantic_error_diagnostics(
    error: ValidationError,
    raw: Mapping[str, object],
) -> tuple[str | None, str | None, int | None, tuple[str, ...], str | None]:
    """Describe only the failed JSON shape; never retain output values."""

    errors = error.errors(include_url=False, include_context=False, include_input=False)
    if not errors:
        return None, None, None, (), None
    first = errors[0]
    loc = first.get("loc", ())
    field = loc[0] if isinstance(loc, tuple) and loc and isinstance(loc[0], str) else None
    if field not in _ARCANA_EXPECTED_JSON_TYPES:
        return None, None, None, (), None
    received = raw.get(field, _MISSING_STRUCTURED_VALUE)
    received_count = len(received) if isinstance(received, list) else None
    object_value: Mapping[object, object] | None = None
    if isinstance(received, Mapping):
        object_value = received
    elif isinstance(received, list) and received and isinstance(received[0], Mapping):
        object_value = received[0]
    allowed_keys = _ARCANA_ITEM_KEY_ALLOWLIST.get(field, frozenset())
    received_keys = (
        tuple(sorted(key for key in object_value if isinstance(key, str) and key in allowed_keys))
        if object_value is not None
        else ()
    )
    validator_category = first.get("type")
    return (
        _ARCANA_EXPECTED_JSON_TYPES[field],
        _structured_json_shape(received),
        received_count,
        received_keys,
        validator_category if isinstance(validator_category, str) else None,
    )


def _arcana_live_system_prompt() -> str:
    return (
        "Your first obligation is to ANSWER THE USER'S EXACT QUESTION using only the saved draw "
        "and repository-local retrieved context. Never produce three independent generic card "
        "explanations followed by a generic summary. Build one tarot-reading.v2 argument in this "
        "order: (1) restate the exact question and its domain, intent, and temporal anchor; "
        "(2) give a concise probabilistic thesis that directly answers it; (3) use Past, Present, "
        "and Future as evidence for that thesis; (4) explain cause -> current dynamic -> likely "
        "direction; (5) explain reinforcement, contradiction, or tension between cards; "
        "(6) identify the most important turning point; (7) tie every major conclusion back to "
        "the question; (8) give practical reflection or action; and (9) state uncertainty and "
        "avoid deterministic fortune-telling. Address an explicit time frame, but never invent a "
        "precise date from the cards. For relationship questions discuss openness, reciprocity, "
        "stability, barriers, and dynamics rather than listing traditional meanings. Preserve "
        "each saved card identity, orientation, and position. Every knowledge_basis entry must "
        "use the exact primary card chunk_id as knowledge_id and its exact source_id and "
        "source_title.\n"
        f"{ARCANA_LIVE_OUTPUT_CONTRACT}"
    )


class ArcanaService:
    def __init__(
        self,
        session: AsyncSession,
        interpreter: TarotFixtureInterpreter | None = None,
        *,
        live_service: GovernedZhipuInvocationService | None = None,
    ) -> None:
        self._session = session
        self._interpreter = interpreter or TarotFixtureInterpreter()
        self._knowledge = LocalTarotKnowledgeLayer()
        self._live_service = live_service

    def _retrieval_payload(
        self,
        *,
        reading: TarotReading,
        rows: list[tuple[TarotReadingCard, TarotCardDefinition]],
    ) -> tuple[
        list[dict[str, object]],
        RetrievedContextBundle,
        dict[str, object],
        list[dict[str, object]],
    ]:
        if len(rows) != 3:
            raise ArcanaLifecycleConflictError
        locale: Literal["zh-CN", "en-US"] = (
            "zh-CN" if reading.generation_locale == "zh-CN" else "en-US"
        )
        analysis = analyze_question(reading.question, locale)
        payload_cards: list[dict[str, object]] = []
        retrieved_units: list[RetrievedContextUnit] = []
        relationship_cards: list[RelationshipCard] = []
        for draw, card in rows:
            localized = card.orientation_knowledge[draw.orientation]
            if not isinstance(localized, Mapping):
                raise ArcanaLifecycleConflictError
            context = self._knowledge.context_for(
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
                question_analysis=analysis,
            )
            retrieved_units.extend(context.as_retrieved_units(locale=locale))
            knowledge_context = context.as_payload()
            knowledge_context["primary_knowledge_id"] = context.primary_knowledge_id(locale=locale)
            knowledge_context["position_name"] = (
                draw.position_name_zh if locale == "zh-CN" else draw.position_name_en
            )
            payload_cards.append(knowledge_context)
            relationship_cards.append(
                RelationshipCard(
                    card_id=card.id,
                    card_name=card.name_zh if locale == "zh-CN" else card.name_en,
                    position_key=draw.position_key,
                    orientation=draw.orientation,
                    arcana=card.arcana,
                    suit=card.suit,
                    rank=card.rank,
                    meaning=str(localized[locale]),
                )
            )
        exact_cards = (relationship_cards[0], relationship_cards[1], relationship_cards[2])
        relationships: tuple[RelationshipSignal, ...] = assemble_relationship_signals(
            exact_cards, analysis
        )
        retrieved_units.extend(signal.as_retrieved_unit(locale=locale) for signal in relationships)
        retrieval = RetrievedContextBundle(product_space="arcana", units=retrieved_units)
        validate_question_aware_readiness(
            question=reading.question,
            analysis=analysis,
            cards=payload_cards,
            relationships=relationships,
            retrieval=retrieval,
        )
        return (
            payload_cards,
            retrieval,
            analysis.as_payload(),
            [signal.as_payload() for signal in relationships],
        )

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
                    TarotCardDefinition.arcana,
                    TarotCardDefinition.suit,
                    TarotCardDefinition.number,
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
            (
                await self._session.execute(
                    select(TarotReadingCard, TarotCardDefinition)
                    .join(
                        TarotCardDefinition,
                        TarotCardDefinition.id == TarotReadingCard.card_definition_id,
                    )
                    .where(TarotReadingCard.reading_id == reading.id)
                    .order_by(TarotReadingCard.position_index)
                )
            )
            .tuples()
            .all()
        )
        if len(rows) != 3:
            raise ArcanaLifecycleConflictError
        payload_cards, retrieval, question_analysis, relationship_signals = self._retrieval_payload(
            reading=reading, rows=list(rows)
        )
        payload: dict[str, object] = {
            "question": reading.question,
            "generation_locale": reading.generation_locale,
            "spread_key": reading.spread_key,
            "spread_version": reading.spread_version,
            "cards": payload_cards,
            "question_analysis": question_analysis,
            "relationship_signals": relationship_signals,
        }
        payload["retrieved_context"] = retrieval.model_dump(mode="json")
        input_hash, document = self._interpreter.interpret(payload)
        citations = validate_retrieved_citations(
            [
                RetrievedCitation(
                    source_id=unit.source_id,
                    chunk_id=unit.chunk_id,
                    target_path=f"/positions/{index}",
                )
                for index, unit in enumerate(retrieval.units)
            ],
            retrieval,
            require_at_least_one=True,
        )
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
                retrieved_context_snapshot=[
                    unit.model_dump(mode="json") for unit in retrieval.units
                ],
                citation_snapshot=[item.model_dump(mode="json") for item in citations],
                source_invocation_id=None,
                source_attempt_id=None,
                created_at=now,
            )
        )
        reading.status = "interpreted"
        reading.interpreted_at = now
        reading.updated_at = now
        await self._session.commit()
        return await self._read(reading)

    async def interpret_live(
        self,
        reading_id: uuid.UUID,
        payload: TarotLiveInterpretRequest,
        principal: PrincipalContext,
        *,
        request_id: uuid.UUID,
        idempotency_key: uuid.UUID,
    ) -> TarotReadingRead:
        if self._live_service is None:
            raise ArcanaLiveUnavailableError
        reading = await self._owned(reading_id, principal)
        if reading.status != "drawn":
            raise ArcanaLifecycleConflictError
        existing = await self._session.scalar(
            select(TarotInterpretationRevision).where(
                TarotInterpretationRevision.reading_id == reading.id
            )
        )
        rows = list(
            (
                await self._session.execute(
                    select(TarotReadingCard, TarotCardDefinition)
                    .join(
                        TarotCardDefinition,
                        TarotCardDefinition.id == TarotReadingCard.card_definition_id,
                    )
                    .where(TarotReadingCard.reading_id == reading.id)
                    .order_by(TarotReadingCard.position_index)
                )
            )
            .tuples()
            .all()
        )
        if existing is not None or len(rows) != 3:
            raise ArcanaLifecycleConflictError
        payload_cards, retrieval, question_analysis, relationship_signals = self._retrieval_payload(
            reading=reading, rows=rows
        )
        context = {
            "reading": {
                "question": reading.question,
                "generation_locale": reading.generation_locale,
                "spread_key": reading.spread_key,
                "spread_version": reading.spread_version,
                "cards": payload_cards,
                "question_analysis": question_analysis,
                "relationship_signals": relationship_signals,
            },
            "retrieved_context": retrieval.model_dump(mode="json"),
            "safety_note": self._knowledge.safety_note(
                "zh-CN" if reading.generation_locale == "zh-CN" else "en-US"
            ),
        }
        adapter = ZhipuChatAdapter(ZHIPU_GLM_52_MODEL)
        prompt = GovernedMultimodalPrompt(
            system_prompt=_arcana_live_system_prompt(),
            user_intent=reading.question,
            structured_context=context,
            generation_locale=reading.generation_locale,  # type: ignore[arg-type]
        )
        request = adapter.prepare_request(
            prompt=prompt,
            images=(),
            response_schema=TarotInterpretationDocument.model_json_schema(),
            max_output_tokens=ZHIPU_ARCANA_MAX_OUTPUT_TOKENS,
            timeout_ms=60_000,
        )
        estimate = adapter.estimate_cost(
            prompt=prompt,
            images=(),
            response_schema=TarotInterpretationDocument.model_json_schema(),
            max_output_tokens=ZHIPU_ARCANA_MAX_OUTPUT_TOKENS,
        )
        pricing = await self._session.scalar(
            select(ProviderPricingSnapshot)
            .where(
                ProviderPricingSnapshot.provider_definition_id == payload.provider_definition_id,
                ProviderPricingSnapshot.model_definition_id == payload.model_definition_id,
                ProviderPricingSnapshot.provider_key == "zhipu",
                ProviderPricingSnapshot.model_id == ZHIPU_GLM_52_MODEL,
            )
            .order_by(ProviderPricingSnapshot.effective_at.desc())
            .limit(1)
        )
        if pricing is None:
            raise ArcanaLiveUnavailableError
        expected = {
            draw.card_definition_id: (draw.position_key, draw.orientation) for draw, _card in rows
        }
        units_by_chunk_id = {unit.chunk_id: unit for unit in retrieval.units}
        primary_units_by_card = {
            str(card["card_id"]): units_by_chunk_id[str(card["primary_knowledge_id"])]
            for card in payload_cards
        }

        def validate_output(raw: Mapping[str, object]) -> dict[str, object]:
            try:
                document = TarotInterpretationDocument.model_validate(dict(raw))
            except ValidationError as error:
                (
                    expected_json_type,
                    received_json_type,
                    received_item_count,
                    received_object_keys,
                    validator_error_category,
                ) = _pydantic_error_diagnostics(error, raw)
                raise StructuredOutputValidationError(
                    "SCHEMA_VALIDATION_FAILED",
                    path=_pydantic_error_path(error),
                    expected_json_type=expected_json_type,
                    received_json_type=received_json_type,
                    received_item_count=received_item_count,
                    received_object_keys=received_object_keys,
                    validator_error_category=validator_error_category,
                ) from None
            if document.generation_locale != reading.generation_locale:
                raise StructuredOutputValidationError(
                    "SCHEMA_VALIDATION_FAILED", path="$.generation_locale"
                )
            if {
                item.card_id: (item.position_key, item.orientation) for item in document.positions
            } != expected:
                raise StructuredOutputValidationError(
                    "SCHEMA_VALIDATION_FAILED", path="$.positions"
                )
            if {item.card_id for item in document.knowledge_basis} != set(expected):
                raise StructuredOutputValidationError(
                    "CITATION_VALIDATION_FAILED", path="$.knowledge_basis"
                )
            citations: list[RetrievedCitation] = []
            for index, basis in enumerate(document.knowledge_basis):
                unit = primary_units_by_card.get(basis.card_id)
                if (
                    unit is None
                    or basis.knowledge_id != unit.chunk_id
                    or basis.source_id != unit.source_id
                    or basis.source_title != unit.source_title
                    or basis.retrieval_mode != "repository_local_only"
                ):
                    raise StructuredOutputValidationError(
                        "CITATION_VALIDATION_FAILED",
                        path=f"$.knowledge_basis[{index}]",
                    )
                try:
                    citations.append(
                        RetrievedCitation(
                            source_id=basis.source_id,
                            chunk_id=basis.knowledge_id,
                            target_path=f"/knowledge_basis/{index}",
                        )
                    )
                except ValidationError:
                    raise StructuredOutputValidationError(
                        "CITATION_VALIDATION_FAILED",
                        path=f"$.knowledge_basis[{index}]",
                    ) from None
            try:
                validate_retrieved_citations(citations, retrieval, require_at_least_one=True)
            except RetrievalContractError:
                raise StructuredOutputValidationError(
                    "CITATION_VALIDATION_FAILED", path="$.knowledge_basis"
                ) from None
            return document.model_dump(mode="json")

        await self._session.commit()
        try:
            result = await self._live_service.execute(
                selection=ZhipuLiveSelection(
                    product_space="arcana",
                    invocation_family="arcana_interpretation",
                    project_id=None,
                    provider_definition_id=payload.provider_definition_id,
                    model_definition_id=payload.model_definition_id,
                    credential_id=payload.credential_id,
                    required_capability_keys=("text_generation", "structured_output"),
                    estimate_minor_units=estimate,
                    pricing_snapshot_id=pricing.id,
                ),
                principal=principal,
                request=request,
                retrieval=retrieval,
                output_validator=validate_output,
                idempotency_key=idempotency_key,
                request_id=request_id,
                safe_input_snapshot={
                    "reading_id": str(reading.id),
                    "question_hash": hashlib.sha256(reading.question.encode("utf-8")).hexdigest(),
                    "question_analysis": {
                        "domain": question_analysis["domain"],
                        "intents": question_analysis["intents"],
                        "temporal_frame": question_analysis["temporal_frame"],
                        "has_temporal_anchor": question_analysis["temporal_anchor"] is not None,
                    },
                    "draw": [
                        {
                            "card_id": draw.card_definition_id,
                            "position_key": draw.position_key,
                            "orientation": draw.orientation,
                        }
                        for draw, _card in rows
                    ],
                    "schema_version": "tarot-reading.v2",
                },
                business_claim=ZhipuBusinessResourceClaim(
                    scope_key=f"zhipu_resource:arcana:reading:{reading.id}",
                    principal_id=principal.principal_id,
                    command_type="arcana_interpretation",
                ),
            )
        except (ProviderContractError, RuntimeError) as error:
            raise ArcanaLiveUnavailableError from error
        document = TarotInterpretationDocument.model_validate(result.output)
        citations = [
            RetrievedCitation(
                source_id=basis.source_id,
                chunk_id=basis.knowledge_id,
                target_path=f"/knowledge_basis/{index}",
            )
            for index, basis in enumerate(document.knowledge_basis)
        ]
        validate_retrieved_citations(citations, retrieval, require_at_least_one=True)
        reading = await self._owned(reading_id, principal, for_update=True)
        if reading.status != "drawn":
            raise ArcanaLifecycleConflictError
        now = datetime.now(UTC)
        revision_id = uuid.uuid4()
        input_hash = hashlib.sha256(
            json.dumps(context, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
                "utf-8"
            )
        ).hexdigest()
        self._session.add(
            TarotInterpretationRevision(
                id=revision_id,
                reading_id=reading.id,
                revision=1,
                source="zhipu_live",
                schema_version="tarot-reading.v2",
                provider_key="zhipu",
                model_id=ZHIPU_GLM_52_MODEL,
                adapter_version=adapter.adapter_version,
                prompt_version=ARCANA_LIVE_PROMPT_VERSION,
                input_hash=input_hash,
                document=document.model_dump(mode="json"),
                retrieved_context_snapshot=[
                    unit.model_dump(mode="json") for unit in retrieval.units
                ],
                citation_snapshot=[item.model_dump(mode="json") for item in citations],
                source_invocation_id=result.invocation_id,
                source_attempt_id=result.attempt_id,
                created_at=now,
            )
        )
        reading.status = "interpreted"
        reading.interpreted_at = now
        reading.updated_at = now
        await self._live_service.complete_business_resource_claim(
            claim_id=result.business_claim_id,
            resource_type="tarot_interpretation",
            resource_id=revision_id,
            response_snapshot={
                "phase": "completed",
                "reading_id": str(reading.id),
                "interpretation_revision_id": str(revision_id),
            },
        )
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
                    "retrieved_context": interpretation_row.retrieved_context_snapshot,
                    "citations": interpretation_row.citation_snapshot,
                    "source_invocation_id": interpretation_row.source_invocation_id,
                    "source_attempt_id": interpretation_row.source_attempt_id,
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
