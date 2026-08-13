"""Deterministic readiness gate for question-aware Arcana context."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from creativedeploy_api.ai.retrieval import RetrievedContextBundle
from creativedeploy_api.arcana.question_analysis import QuestionAnalysis
from creativedeploy_api.arcana.relationships import RelationshipSignal


class ArcanaQualityReadinessError(ValueError):
    """Layer-1 context is too weak or internally inconsistent for synthesis."""


def validate_question_aware_readiness(
    *,
    question: str,
    analysis: QuestionAnalysis,
    cards: Sequence[Mapping[str, object]],
    relationships: Sequence[RelationshipSignal],
    retrieval: RetrievedContextBundle,
) -> None:
    """Reject generic or uncited context before Fixture or Provider synthesis."""

    if not question.strip() or analysis.question != question.strip():
        raise ArcanaQualityReadinessError("the exact user question is absent from layer-1 context")
    if len(cards) != 3:
        raise ArcanaQualityReadinessError("the saved three-card draw is incomplete")
    sections = [unit.section for unit in retrieval.units]
    if analysis.domain != "general" and not any(
        section == f"question/{analysis.domain}" for section in sections
    ):
        raise ArcanaQualityReadinessError("specific question-domain retrieval is absent")
    positions = {
        section.removeprefix("position/") for section in sections if section.startswith("position/")
    }
    if positions != {"past", "present", "future"}:
        raise ArcanaQualityReadinessError("position-aware knowledge is incomplete")
    if not relationships or not any(
        signal.kind in {"transition", "turning_point"} for signal in relationships
    ):
        raise ArcanaQualityReadinessError("cross-card transition context is absent")
    primary_ids = {
        str(card.get("primary_knowledge_id"))
        for card in cards
        if isinstance(card.get("primary_knowledge_id"), str)
    }
    available = {unit.chunk_id for unit in retrieval.units}
    if len(primary_ids) != 3 or not primary_ids.issubset(available):
        raise ArcanaQualityReadinessError("card knowledge provenance is incomplete")
