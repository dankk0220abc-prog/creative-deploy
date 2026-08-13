"""Strict Arcana request, response, and structured interpretation contracts."""

from datetime import datetime
from typing import Annotated, Final, Literal
from uuid import UUID

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, field_validator

from creativedeploy_api.ai.retrieval import RetrievedCitation, RetrievedContextUnit


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


Locale = Literal["zh-CN", "en-US"]
Orientation = Literal["upright", "reversed"]
ReadingStatus = Literal["draft", "drawn", "interpreted", "saved"]
RequestUUID = Annotated[
    UUID,
    BeforeValidator(lambda value: UUID(value) if isinstance(value, str) else value),
]


def _clean(value: str) -> str:
    normalized = " ".join(value.strip().split())
    if not normalized or "<" in normalized or ">" in normalized:
        raise ValueError("text must be non-empty plain text")
    return normalized


class TarotKnowledgeRead(StrictModel):
    knowledge_id: str
    orientation: Orientation
    locale: Locale
    section: Literal["meaning", "element", "number", "court_role", "position", "spread_rule"]
    content: str
    source: dict[str, object]


class TarotCardRead(StrictModel):
    id: str
    arcana: Literal["major", "minor"]
    suit: str | None
    rank: str
    number: int
    name_en: str
    name_zh: str
    theme: str
    knowledge: list[TarotKnowledgeRead]


class TarotSpreadPositionRead(StrictModel):
    key: Literal["past", "present", "future"]
    name_en: str
    name_zh: str


class TarotSpreadRead(StrictModel):
    key: Literal["past-present-future"]
    version: Literal[1]
    name_en: str
    name_zh: str
    positions: list[TarotSpreadPositionRead]


class TarotCatalogRead(StrictModel):
    deck_key: Literal["arcana-core-78"] = "arcana-core-78"
    deck_version: Literal[1] = 1
    cards: list[TarotCardRead]
    spread: TarotSpreadRead


class TarotReadingCreate(StrictModel):
    question: Annotated[str, Field(min_length=1, max_length=500)]
    generation_locale: Locale

    @field_validator("question")
    @classmethod
    def normalize_question(cls, value: str) -> str:
        return _clean(value)


class TarotLiveInterpretRequest(StrictModel):
    provider_definition_id: RequestUUID
    model_definition_id: RequestUUID
    credential_id: RequestUUID
    confirm_paid_live_call: Literal[True]


class TarotReadingCardRead(StrictModel):
    card: TarotCardRead
    position_index: Annotated[int, Field(ge=0, le=2)]
    position_key: Literal["past", "present", "future"]
    position_name_en: str
    position_name_zh: str
    orientation: Orientation
    draw_order: Annotated[int, Field(ge=1, le=3)]
    drawn_at: datetime


class TarotPositionInterpretation(StrictModel):
    position_key: Literal["past", "present", "future"]
    card_id: str
    orientation: Orientation
    headline: Annotated[str, Field(min_length=1, max_length=160)]
    contribution: Annotated[str, Field(min_length=1, max_length=800)]


class TarotRelationshipInsight(StrictModel):
    kind: Literal["relationship", "trend", "tension", "turning_point"]
    headline: Annotated[str, Field(min_length=1, max_length=120)]
    content: Annotated[str, Field(min_length=1, max_length=600)]


class TarotKnowledgeBasis(StrictModel):
    card_id: str
    knowledge_id: str
    source_id: str
    source_title: str
    retrieval_mode: Literal["repository_local_only"]


class TarotInterpretationDocument(StrictModel):
    schema_version: Literal["tarot-reading.v2"]
    generation_locale: Locale
    question_restatement: Annotated[str, Field(min_length=1, max_length=700)]
    summary: Annotated[str, Field(min_length=1, max_length=1200)]
    positions: Annotated[list[TarotPositionInterpretation], Field(min_length=3, max_length=3)]
    synthesis: Annotated[str, Field(min_length=1, max_length=1600)]
    relationship_analysis: Annotated[
        list[TarotRelationshipInsight], Field(min_length=3, max_length=4)
    ]
    actionable_reflections: Annotated[
        list[Annotated[str, Field(min_length=1, max_length=400)]], Field(min_length=1, max_length=3)
    ]
    reflection_prompts: Annotated[
        list[Annotated[str, Field(min_length=1, max_length=400)]], Field(min_length=2, max_length=4)
    ]
    knowledge_basis: Annotated[list[TarotKnowledgeBasis], Field(min_length=3, max_length=3)]
    uncertainty: Annotated[str, Field(min_length=1, max_length=500)]


ARCANA_LIVE_OUTPUT_CONTRACT: Final = (
    "Required top-level JSON contract; every field is required, null is forbidden, and extra "
    "keys are forbidden at every object level:\n"
    "- schema_version: string literal 'tarot-reading.v2'.\n"
    "- generation_locale: string equal to the input locale ('zh-CN' or 'en-US').\n"
    "- question_restatement: string, 1..700 characters.\n"
    "- summary: string, 1..1200 characters.\n"
    "- positions: array<object>, exactly 3 items; each object requires only position_key "
    "('past'|'present'|'future'), card_id (string), orientation ('upright'|'reversed'), "
    "headline (string, 1..160), and contribution (string, 1..800).\n"
    "- synthesis: string, 1..1600 characters.\n"
    "- relationship_analysis: array<object>, 3..4 items; each object requires only kind "
    "('relationship'|'trend'|'tension'|'turning_point'), headline (string, 1..120), and "
    "content (string, 1..600).\n"
    "- actionable_reflections: array<string>, 1..3 items; each item is a string of 1..400 "
    "characters, never an object.\n"
    "- reflection_prompts: array<string>, 2..4 items; each item is a string of 1..400 "
    "characters, never an object.\n"
    "- knowledge_basis: array<object>, exactly 3 items; each object requires only card_id, "
    "knowledge_id, source_id, source_title (all strings), and retrieval_mode (string literal "
    "'repository_local_only').\n"
    "- uncertainty: string, 1..500 characters."
)


class TarotInterpretationRead(StrictModel):
    revision: int
    source: Literal["fixture_local", "zhipu_live", "user_edit"]
    provider_key: str
    model_id: str
    adapter_version: str
    prompt_version: int
    input_hash: str
    document: TarotInterpretationDocument
    retrieved_context: list[RetrievedContextUnit] = Field(default_factory=list)
    citations: list[RetrievedCitation] = Field(default_factory=list)
    source_invocation_id: UUID | None = None
    source_attempt_id: UUID | None = None
    created_at: datetime


class TarotJournalUpdate(StrictModel):
    personal_interpretation: Annotated[str, Field(max_length=4000)] = ""
    notes: Annotated[str, Field(max_length=8000)] = ""

    @field_validator("personal_interpretation", "notes")
    @classmethod
    def normalize_user_text(cls, value: str) -> str:
        return value.strip()


class TarotJournalRead(StrictModel):
    personal_interpretation: str
    notes: str
    created_at: datetime
    updated_at: datetime


class TarotReadingRead(StrictModel):
    id: UUID
    question: str
    status: ReadingStatus
    generation_locale: Locale
    spread: TarotSpreadRead
    cards: list[TarotReadingCardRead]
    interpretation: TarotInterpretationRead | None
    journal: TarotJournalRead | None
    created_at: datetime
    updated_at: datetime
    drawn_at: datetime | None
    interpreted_at: datetime | None
    saved_at: datetime | None


class TarotReadingHistoryRead(StrictModel):
    items: list[TarotReadingRead]


class TarotSharePreviewRead(StrictModel):
    reading_id: UUID
    question: str
    generation_locale: Locale
    cards: list[TarotReadingCardRead]
    concise_interpretation: str
    private_local_preview: Literal[True] = True
