"""Focused Arcana deck, schema, fixture, and metadata contracts."""

from creativedeploy_api.arcana.catalog import THREE_CARD_SPREAD, card_seeds
from creativedeploy_api.arcana.fixture_interpreter import TarotFixtureInterpreter
from creativedeploy_api.arcana.knowledge import LocalTarotKnowledgeLayer
from creativedeploy_api.db.base import Base


def _fixture_payload() -> dict[str, object]:
    cards = card_seeds()[:3]
    positions = THREE_CARD_SPREAD["positions"]
    assert isinstance(positions, list)
    knowledge = LocalTarotKnowledgeLayer()
    return {
        "question": "What deserves my attention?",
        "generation_locale": "en-US",
        "spread_key": "past-present-future",
        "spread_version": 1,
        "cards": [
            {
                **knowledge.context_for(
                    card_id=card.card_id,
                    card_name=card.name_en,
                    orientation="upright" if index != 1 else "reversed",
                    position_key=str(positions[index]["key"]),
                    meaning=card.upright_en if index != 1 else card.reversed_en,
                    arcana=card.arcana,
                    suit=card.suit,
                    rank=card.rank,
                    theme=card.theme,
                    locale="en-US",
                ).as_payload(),
                "position_name": positions[index]["name_en"],
            }
            for index, card in enumerate(cards)
        ],
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
    assert len(first.relationship_analysis) == 4
    assert 1 <= len(first.actionable_reflections) <= 3
    assert 2 <= len(first.reflection_prompts) <= 4
    assert {basis.retrieval_mode for basis in first.knowledge_basis} == {"repository_local_only"}
    assert adapter.provider_key == "fixture_local"
    assert "medical, legal, or financial" in first.uncertainty


def test_local_knowledge_layer_covers_suit_rank_position_orientation_and_provenance() -> None:
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
    )
    assert len(context.semantic_facets) == 4
    assert context.provenance["retrieval_mode"] == "repository_local_only"
    assert context.provenance["card_locator"] == "minor-cups-queen"


def test_arcana_models_share_the_single_platform_metadata() -> None:
    assert {
        "tarot_card_definitions",
        "tarot_spread_definitions",
        "tarot_readings",
        "tarot_reading_cards",
        "tarot_interpretation_revisions",
        "tarot_journal_entries",
    }.issubset(Base.metadata.tables)
