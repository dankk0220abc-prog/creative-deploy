"""Question relevance, provenance, relationship, and quality-gate regressions."""

# ruff: noqa: RUF001

from __future__ import annotations

import json
from pathlib import Path

import pytest

from creativedeploy_api.ai.retrieval import RetrievedContextBundle
from creativedeploy_api.arcana.catalog import card_seeds
from creativedeploy_api.arcana.fixture_interpreter import TarotFixtureInterpreter
from creativedeploy_api.arcana.knowledge import LocalTarotKnowledgeLayer
from creativedeploy_api.arcana.quality import (
    ArcanaQualityReadinessError,
    validate_question_aware_readiness,
)
from creativedeploy_api.arcana.question_analysis import analyze_question
from creativedeploy_api.arcana.relationships import (
    RelationshipCard,
    RelationshipSignal,
    assemble_relationship_signals,
)


def _september_love_context() -> tuple[
    dict[str, object], RetrievedContextBundle, tuple[RelationshipSignal, ...]
]:
    question = "我九月份会有正缘吗"
    locale = "zh-CN"
    analysis = analyze_question(question, locale)
    by_id = {card.card_id: card for card in card_seeds()}
    selected = (
        (by_id["minor-wands-nine"], "past", "过去", "reversed"),
        (by_id["minor-swords-three"], "present", "现在", "upright"),
        (by_id["minor-pentacles-ten"], "future", "未来", "upright"),
    )
    knowledge = LocalTarotKnowledgeLayer()
    payload_cards: list[dict[str, object]] = []
    relationship_cards: list[RelationshipCard] = []
    units = []
    for card, position_key, position_name, orientation in selected:
        meaning = card.reversed_zh if orientation == "reversed" else card.upright_zh
        context = knowledge.context_for(
            card_id=card.card_id,
            card_name=card.name_zh,
            orientation=orientation,
            position_key=position_key,
            meaning=meaning,
            arcana=card.arcana,
            suit=card.suit,
            rank=card.rank,
            theme=card.theme,
            locale=locale,
            question_analysis=analysis,
        )
        units.extend(context.as_retrieved_units(locale=locale))
        payload_cards.append(
            {
                **context.as_payload(),
                "primary_knowledge_id": context.primary_knowledge_id(locale=locale),
                "position_name": position_name,
            }
        )
        relationship_cards.append(
            RelationshipCard(
                card_id=card.card_id,
                card_name=card.name_zh,
                position_key=position_key,
                orientation=orientation,
                arcana=card.arcana,
                suit=card.suit,
                rank=card.rank,
                meaning=meaning,
            )
        )
    exact_cards = (relationship_cards[0], relationship_cards[1], relationship_cards[2])
    signals = assemble_relationship_signals(exact_cards, analysis)
    units.extend(signal.as_retrieved_unit(locale=locale) for signal in signals)
    retrieval = RetrievedContextBundle(product_space="arcana", units=units)
    payload: dict[str, object] = {
        "question": question,
        "generation_locale": locale,
        "spread_key": "past-present-future",
        "spread_version": 1,
        "cards": payload_cards,
        "question_analysis": analysis.as_payload(),
        "relationship_signals": [signal.as_payload() for signal in signals],
        "retrieved_context": retrieval.model_dump(mode="json"),
    }
    return payload, retrieval, signals


@pytest.mark.parametrize(
    ("question", "locale", "domain", "required_intent"),
    [
        ("我九月份会有正缘吗", "zh-CN", "love_relationship", "timing"),
        ("我应该如何处理目前的工作阻碍？", "zh-CN", "career_work", "obstacle"),
        ("这笔投资的财务风险是什么？", "zh-CN", "money_finance", "self_reflection"),
        ("我在这段经历中需要怎样成长？", "zh-CN", "self_growth", "self_reflection"),
        ("两个方案之间我应该如何选择？", "zh-CN", "decision", "advice"),
        ("我和家人的沟通障碍是什么？", "zh-CN", "family_social", "obstacle"),
        ("Will I find a stable relationship in September?", "en-US", "love_relationship", "timing"),
        ("What should I do about this career decision?", "en-US", "career_work", "advice"),
        ("这件事意味着什么？", "zh-CN", "general", "self_reflection"),
    ],
)
def test_question_analysis_routes_bilingual_domain_intent_and_safe_general_fallback(
    question: str, locale: str, domain: str, required_intent: str
) -> None:
    analysis = analyze_question(question, locale)  # type: ignore[arg-type]

    assert analysis.domain == domain
    assert required_intent in analysis.intents


def test_september_love_context_is_position_domain_time_and_relationship_aware() -> None:
    payload, retrieval, signals = _september_love_context()
    analysis_payload = payload["question_analysis"]
    assert isinstance(analysis_payload, dict)

    assert analysis_payload["domain"] == "love_relationship"
    assert {"outcome_tendency", "timing"}.issubset(set(analysis_payload["intents"]))
    assert analysis_payload["temporal_anchor"] == "九月份"
    sections = {unit.section for unit in retrieval.units}
    assert {"position/past", "position/present", "position/future"}.issubset(sections)
    assert "question/love_relationship" in sections
    assert any(unit.section.startswith("relationship/") for unit in retrieval.units)
    assert any(signal.kind in {"transition", "turning_point"} for signal in signals)
    assert len(retrieval.units) <= 24


def test_september_love_fixture_answers_the_question_as_a_conditional_causal_thesis() -> None:
    payload, retrieval, signals = _september_love_context()
    cards = payload["cards"]
    analysis_payload = payload["question_analysis"]
    assert isinstance(cards, list)
    assert isinstance(analysis_payload, dict)
    analysis = analyze_question(str(payload["question"]), "zh-CN")
    validate_question_aware_readiness(
        question=str(payload["question"]),
        analysis=analysis,
        cards=cards,
        relationships=signals,  # type: ignore[arg-type]
        retrieval=retrieval,
    )

    _input_hash, document = TarotFixtureInterpreter().interpret(payload)

    assert "我九月份会有正缘吗" in document.question_restatement
    assert "感情与关系" in document.question_restatement
    assert "love_relationship" not in document.question_restatement
    assert "outcome_tendency" not in document.question_restatement
    assert "我九月份会有正缘吗" in document.summary
    assert "九月份" in document.summary
    assert "不保证" in document.summary
    assert all(name in document.synthesis for name in ("权杖九", "宝剑三", "星币十"))
    assert "因果" in document.synthesis
    assert "条件和方向" in document.synthesis
    assert len(document.relationship_analysis) >= 3
    available_ids = {unit.chunk_id for unit in retrieval.units}
    assert {basis.knowledge_id for basis in document.knowledge_basis}.issubset(available_ids)


def test_reversed_future_love_card_produces_a_barrier_aware_direct_answer() -> None:
    payload, _retrieval, _signals = _september_love_context()
    cards = payload["cards"]
    assert isinstance(cards, list)
    future = cards[2]
    assert isinstance(future, dict)
    future.update(
        {
            "name": "审判",
            "card_id": "major-20-judgement",
            "orientation": "reversed",
            "meaning": "自我怀疑、逃避召唤或迟迟不愿作出回应",
            "question_context": (
                "自我评判或回避可能延迟识别可发展关系的能力；这是阻碍信号，不是承诺。"
            ),
        }
    )

    _input_hash, document = TarotFixtureInterpreter().interpret(payload)

    assert "没有足够牌面依据" in document.summary
    assert "延迟或阻碍信号" in document.summary
    assert "值得观察" not in document.summary


def test_exact_september_cards_use_card_specific_relationship_lenses() -> None:
    payload, _retrieval, _signals = _september_love_context()
    cards = payload["cards"]
    assert isinstance(cards, list)
    contexts = [str(card["question_context"]) for card in cards if isinstance(card, dict)]

    assert any("防御性疲惫" in context for context in contexts)
    assert any("尚未消化的伤痛" in context for context in contexts)
    assert any("长期价值" in context and "现实稳定性" in context for context in contexts)


def test_unlisted_love_cards_get_natural_card_specific_fallbacks_without_raw_enums() -> None:
    analysis = analyze_question("我九月份会有正缘吗", "zh-CN")
    by_id = {card.card_id: card for card in card_seeds()}
    selected = (
        (by_id["minor-swords-queen"], "past", "upright"),
        (by_id["minor-pentacles-six"], "present", "upright"),
        (by_id["minor-wands-knight"], "future", "upright"),
    )
    knowledge = LocalTarotKnowledgeLayer()
    relationship_cards = []
    contexts = []
    for card, position_key, orientation in selected:
        meaning = card.upright_zh
        context = knowledge.context_for(
            card_id=card.card_id,
            card_name=card.name_zh,
            orientation=orientation,
            position_key=position_key,
            meaning=meaning,
            arcana=card.arcana,
            suit=card.suit,
            rank=card.rank,
            theme=card.theme,
            locale="zh-CN",
            question_analysis=analysis,
        )
        contexts.append(context.question_context)
        relationship_cards.append(
            RelationshipCard(
                card_id=card.card_id,
                card_name=card.name_zh,
                position_key=position_key,
                orientation=orientation,
                arcana=card.arcana,
                suit=card.suit,
                rank=card.rank,
                meaning=meaning,
            )
        )

    assert "诚实沟通、事实判断与关系边界" in contexts[0]
    assert "核对给予与接受是否平衡" in contexts[1]
    assert "主动追求可能带来速度，也要核验持续性" in contexts[2]
    assert not any(raw in " ".join(contexts) for raw in ("past", "present", "future"))
    exact_cards = (relationship_cards[0], relationship_cards[1], relationship_cards[2])
    signals = assemble_relationship_signals(exact_cards, analysis)
    combined_signals = " ".join(signal.content for signal in signals)
    assert "风元素" in combined_signals
    assert "土元素" in combined_signals
    assert "三张牌均为正位" in combined_signals
    assert "air" not in combined_signals
    assert "upright" not in combined_signals


def test_quality_gate_rejects_missing_specific_domain_units_and_relationships() -> None:
    payload, retrieval, signals = _september_love_context()
    cards = payload["cards"]
    assert isinstance(cards, list)
    analysis = analyze_question(str(payload["question"]), "zh-CN")
    without_domain = RetrievedContextBundle(
        product_space="arcana",
        units=[unit for unit in retrieval.units if not unit.section.startswith("question/")],
    )

    with pytest.raises(ArcanaQualityReadinessError, match="question-domain"):
        validate_question_aware_readiness(
            question=str(payload["question"]),
            analysis=analysis,
            cards=cards,
            relationships=signals,  # type: ignore[arg-type]
            retrieval=without_domain,
        )
    with pytest.raises(ArcanaQualityReadinessError, match="transition"):
        validate_question_aware_readiness(
            question=str(payload["question"]),
            analysis=analysis,
            cards=cards,
            relationships=(),
            retrieval=retrieval,
        )


def test_arcana_v2_source_manifest_is_license_first_and_excludes_unlicensed_ingestion() -> None:
    manifest_path = Path(__file__).parents[2] / "src/creativedeploy_api/arcana/source_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    by_id = {source["source_id"]: source for source in manifest["sources"]}

    assert manifest["corpus_version"] == "arcana-local-knowledge-v2"
    assert "MIT" in by_id["arcanite-architecture-reference-2026"]["license_status"]
    assert "MIT" in by_id["metabismuth-tarot-json-identity-reference"]["license_status"]
    assert "Public domain" in by_id["waite-pictorial-key-1910-derived-v2"]["license_status"]
    assert "reference-only" in by_id["ekelen-tarot-api-reference-only"]["license_status"]
    assert "No data" in by_id["ekelen-tarot-api-reference-only"]["derived_data_note"]
