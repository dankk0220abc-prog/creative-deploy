"""Focused Arcana deck, schema, fixture, and metadata contracts."""

from copy import deepcopy

import pytest
from pydantic import ValidationError

from creativedeploy_api.arcana.catalog import THREE_CARD_SPREAD, card_seeds
from creativedeploy_api.arcana.fixture_interpreter import TarotFixtureInterpreter
from creativedeploy_api.arcana.knowledge import LocalTarotKnowledgeLayer
from creativedeploy_api.arcana.question_analysis import analyze_question
from creativedeploy_api.arcana.relationships import (
    RelationshipCard,
    assemble_relationship_signals,
)
from creativedeploy_api.db.base import Base
from creativedeploy_api.schemas.arcana import (
    ARCANA_LIVE_OUTPUT_CONTRACT,
    TarotInterpretationDocument,
)
from creativedeploy_api.services.arcana import (
    ARCANA_LIVE_PROMPT_VERSION,
    _arcana_live_system_prompt,
    _pydantic_error_diagnostics,
)


def _fixture_payload() -> dict[str, object]:
    cards = card_seeds()[:3]
    positions = THREE_CARD_SPREAD["positions"]
    assert isinstance(positions, list)
    knowledge = LocalTarotKnowledgeLayer()
    question = "What deserves my attention?"
    analysis = analyze_question(question, "en-US")
    payload_cards: list[dict[str, object]] = []
    relationship_cards: list[RelationshipCard] = []
    for index, card in enumerate(cards):
        orientation = "upright" if index != 1 else "reversed"
        meaning = card.upright_en if index != 1 else card.reversed_en
        context = knowledge.context_for(
            card_id=card.card_id,
            card_name=card.name_en,
            orientation=orientation,
            position_key=str(positions[index]["key"]),
            meaning=meaning,
            arcana=card.arcana,
            suit=card.suit,
            rank=card.rank,
            theme=card.theme,
            locale="en-US",
            question_analysis=analysis,
        )
        payload_cards.append(
            {
                **context.as_payload(),
                "primary_knowledge_id": context.primary_knowledge_id(locale="en-US"),
                "position_name": positions[index]["name_en"],
            }
        )
        relationship_cards.append(
            RelationshipCard(
                card_id=card.card_id,
                card_name=card.name_en,
                position_key=str(positions[index]["key"]),
                orientation=orientation,
                arcana=card.arcana,
                suit=card.suit,
                rank=card.rank,
                meaning=meaning,
            )
        )
    exact_cards = (relationship_cards[0], relationship_cards[1], relationship_cards[2])
    signals = assemble_relationship_signals(exact_cards, analysis)
    return {
        "question": question,
        "generation_locale": "en-US",
        "spread_key": "past-present-future",
        "spread_version": 1,
        "cards": payload_cards,
        "question_analysis": analysis.as_payload(),
        "relationship_signals": [signal.as_payload() for signal in signals],
    }


def test_arcana_seed_is_one_complete_original_78_card_deck() -> None:
    cards = card_seeds()
    assert len(cards) == 78
    assert len({card.card_id for card in cards}) == 78
    assert sum(card.arcana == "major" for card in cards) == 22
    assert sum(card.arcana == "minor" for card in cards) == 56
    assert {card.suit for card in cards if card.arcana == "minor"} == {
        "wands",
        "cups",
        "swords",
        "pentacles",
    }
    for card in cards:
        assert all(
            value.strip()
            for value in (
                card.name_en,
                card.name_zh,
                card.upright_en,
                card.upright_zh,
                card.reversed_en,
                card.reversed_zh,
                card.theme,
            )
        )


def test_tarot_fixture_interpretation_is_deterministic_and_schema_valid() -> None:
    adapter = TarotFixtureInterpreter()
    first_hash, first = adapter.interpret(_fixture_payload())
    second_hash, second = adapter.interpret(_fixture_payload())

    assert first_hash == second_hash
    assert first == second
    assert first.schema_version == "tarot-reading.v2"
    assert len(first.positions) == 3
    assert 3 <= len(first.relationship_analysis) <= 4
    assert 1 <= len(first.actionable_reflections) <= 3
    assert 2 <= len(first.reflection_prompts) <= 4
    assert {basis.retrieval_mode for basis in first.knowledge_basis} == {"repository_local_only"}
    assert adapter.provider_key == "fixture_local"
    assert "medical, legal, or financial" in first.uncertainty


def _valid_interpretation_payload() -> dict[str, object]:
    _input_hash, document = TarotFixtureInterpreter().interpret(_fixture_payload())
    return document.model_dump(mode="json")


def test_arcana_live_output_contract_names_every_required_top_level_field() -> None:
    prompt = _arcana_live_system_prompt()

    assert ARCANA_LIVE_OUTPUT_CONTRACT in prompt
    for field_name in TarotInterpretationDocument.model_fields:
        assert f"- {field_name}:" in ARCANA_LIVE_OUTPUT_CONTRACT
    assert (
        "- actionable_reflections: array<string>, 1..3 items; each item is a string of "
        "1..400 characters, never an object."
    ) in ARCANA_LIVE_OUTPUT_CONTRACT
    assert "ANSWER THE USER'S EXACT QUESTION" in prompt
    assert "Never produce three independent generic card explanations" in prompt
    assert ARCANA_LIVE_PROMPT_VERSION == 6


def test_exact_fixture_document_passes_the_live_application_schema() -> None:
    payload = _valid_interpretation_payload()

    validated = TarotInterpretationDocument.model_validate(payload)

    assert validated.model_dump(mode="json") == payload


@pytest.mark.parametrize(
    "invalid_value",
    [
        [{"reflection": "This object shape is forbidden."}],
        {"reflection": "The field itself must be an array."},
        [],
        ["one", "two", "three", "four"],
        [""],
        ["x" * 401],
        None,
    ],
)
def test_actionable_reflections_rejects_every_noncontract_shape(invalid_value: object) -> None:
    payload = deepcopy(_valid_interpretation_payload())
    payload["actionable_reflections"] = invalid_value

    with pytest.raises(ValidationError) as captured:
        TarotInterpretationDocument.model_validate(payload)

    assert captured.value.errors(include_url=False, include_input=False)[0]["loc"][0] == (
        "actionable_reflections"
    )


def test_actionable_reflection_shape_diagnostics_never_retain_values_or_unapproved_keys() -> None:
    marker = "private-output-value-must-not-persist"
    payload = deepcopy(_valid_interpretation_payload())
    payload["actionable_reflections"] = [{"reflection": marker}]

    with pytest.raises(ValidationError) as captured:
        TarotInterpretationDocument.model_validate(payload)

    diagnostics = _pydantic_error_diagnostics(captured.value, payload)
    assert diagnostics == ("array<string>", "array<object>", 1, (), "string_type")
    assert marker not in repr(diagnostics)
    assert "reflection" not in repr(diagnostics)


def test_local_knowledge_layer_covers_suit_rank_position_orientation_and_provenance() -> None:
    analysis = analyze_question("What can I learn about my relationship?", "en-US")
    context = LocalTarotKnowledgeLayer().context_for(
        card_id="minor-cups-queen",
        card_name="Queen of Cups",
        orientation="reversed",
        position_key="present",
        meaning="a feeling that needs a boundary",
        arcana="minor",
        suit="cups",
        rank="queen",
        theme="cups:queen",
        locale="en-US",
        question_analysis=analysis,
    )
    assert len(context.semantic_facets) == 4
    assert context.provenance["retrieval_mode"] == "repository_local_only"
    assert context.provenance["card_locator"] == "minor-cups-queen"
    units = context.as_retrieved_units(locale="en-US")
    assert {unit.section for unit in units} == {
        "card/reversed/core",
        "position/present",
        "question/love_relationship",
    }


def test_arcana_models_share_the_single_platform_metadata() -> None:
    assert {
        "tarot_card_definitions",
        "tarot_spread_definitions",
        "tarot_readings",
        "tarot_reading_cards",
        "tarot_interpretation_revisions",
        "tarot_journal_entries",
    }.issubset(Base.metadata.tables)
