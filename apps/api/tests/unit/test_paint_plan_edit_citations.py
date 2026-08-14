"""Paint Plan edit citation provenance regressions."""

import pytest

from creativedeploy_api.ai.retrieval import RetrievedCitation, RetrievedContextUnit
from creativedeploy_api.schemas.paint_plans import PaintPlanDocument
from creativedeploy_api.services.paint_plans import (
    PaintPlanCitationInvalidError,
    _validate_edit_citations,
)


def _unit(*, source_id: str, chunk_id: str) -> RetrievedContextUnit:
    return RetrievedContextUnit(
        source_id=source_id,
        source_title=f"Source {source_id}",
        source_type="repository_local_test_knowledge",
        repository_reference=f"repo://tests/knowledge/{source_id}/{chunk_id}",
        chunk_id=chunk_id,
        section=f"Section {chunk_id}",
        content=f"Governed test guidance from {source_id}/{chunk_id}.",
        retrieval_rationale="Exact test evidence for citation provenance validation.",
        retrieval_score_ppm=900_000,
        locale="en-US",
        corpus_id="paint-plan-edit-citation-tests",
        corpus_version="1",
    )


def _document(*citations: RetrievedCitation) -> PaintPlanDocument:
    return PaintPlanDocument.model_construct(knowledge_citations=list(citations))


def _citation(*, source_id: str, chunk_id: str, target_path: str) -> RetrievedCitation:
    return RetrievedCitation(
        source_id=source_id,
        chunk_id=chunk_id,
        target_path=target_path,
    )


def _snapshot() -> list[dict[str, object]]:
    return [
        _unit(source_id="source-a", chunk_id="chunk-a").model_dump(mode="json"),
        _unit(source_id="source-b", chunk_id="chunk-b").model_dump(mode="json"),
    ]


def test_edit_citations_accept_empty_complete_and_legitimate_subset() -> None:
    first = _citation(
        source_id="source-a",
        chunk_id="chunk-a",
        target_path="/safety_notes/0",
    )
    second = _citation(
        source_id="source-b",
        chunk_id="chunk-b",
        target_path="/instructions/0/preparation",
    )

    _validate_edit_citations(_document(), [])
    _validate_edit_citations(_document(first, second), _snapshot())
    _validate_edit_citations(_document(first), _snapshot())


@pytest.mark.parametrize(
    "citation",
    [
        _citation(
            source_id="forged-source",
            chunk_id="forged-chunk",
            target_path="/safety_notes/0",
        ),
        _citation(
            source_id="source-a",
            chunk_id="chunk-b",
            target_path="/safety_notes/0",
        ),
    ],
    ids=("forged-pair", "pair-splicing"),
)
def test_edit_citations_reject_forged_and_pair_spliced_identity(
    citation: RetrievedCitation,
) -> None:
    with pytest.raises(PaintPlanCitationInvalidError):
        _validate_edit_citations(_document(citation), _snapshot())


@pytest.mark.parametrize("snapshot", [[], [{}]], ids=("empty", "malformed"))
def test_edit_citations_fail_closed_when_snapshot_cannot_be_reconstructed(
    snapshot: list[dict[str, object]],
) -> None:
    citation = _citation(
        source_id="source-a",
        chunk_id="chunk-a",
        target_path="/safety_notes/0",
    )

    with pytest.raises(PaintPlanCitationInvalidError):
        _validate_edit_citations(_document(citation), snapshot)
