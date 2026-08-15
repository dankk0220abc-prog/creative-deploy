"""Provider-neutral retrieval and citation trust-boundary tests."""

import pytest
from pydantic import ValidationError

from creativedeploy_api.ai.retrieval import (
    RetrievalContractError,
    RetrievedCitation,
    RetrievedContextBundle,
    RetrievedContextUnit,
    citations_for_source_ids,
    validate_retrieved_citations,
)


def _unit(source_id: str = "paint-preparation-v1") -> RetrievedContextUnit:
    return RetrievedContextUnit(
        source_id=source_id,
        source_title="Surface preparation",
        source_type="repository_local_practice_note",
        repository_reference="repo://paintpilot/knowledge/surface-preparation",
        chunk_id="surface-preparation",
        section="Preparation",
        content="Clean, abrade, and test compatibility before applying paint.",
        retrieval_rationale="Exact local support for preparation guidance.",
        retrieval_score_ppm=1_000_000,
        locale="en-US",
        corpus_id="paintpilot-practice-notes",
        corpus_version="1",
    )


def _bundle() -> RetrievedContextBundle:
    return RetrievedContextBundle(product_space="paintpilot", units=[_unit()])


def test_bundle_is_canonical_local_and_hash_stable() -> None:
    first = _bundle()
    second = _bundle()
    assert first.canonical_hash() == second.canonical_hash()
    assert first.units[0].repository_reference.startswith("repo://")


def test_bundle_rejects_remote_or_duplicate_chunk_identity() -> None:
    with pytest.raises(ValidationError):
        RetrievedContextUnit(
            **{
                **_unit().model_dump(),
                "repository_reference": "https://example.invalid/source",
            }
        )
    with pytest.raises(ValidationError):
        RetrievedContextBundle(product_space="paintpilot", units=[_unit(), _unit()])


def test_exact_citation_is_accepted_and_hallucinated_source_is_rejected() -> None:
    context = _bundle()
    citation = RetrievedCitation(
        source_id="paint-preparation-v1",
        chunk_id="surface-preparation",
        target_path="instructions[0].preparation",
    )
    assert validate_retrieved_citations([citation], context, require_at_least_one=True) == (
        citation,
    )

    hallucinated = RetrievedCitation(
        source_id="invented-source",
        chunk_id="surface-preparation",
        target_path="instructions[0].preparation",
    )
    with pytest.raises(RetrievalContractError, match="outside"):
        validate_retrieved_citations([hallucinated], context, require_at_least_one=True)


def test_required_empty_and_duplicate_citations_fail_closed() -> None:
    context = _bundle()
    with pytest.raises(RetrievalContractError, match="at least one"):
        validate_retrieved_citations([], context, require_at_least_one=True)
    citation = citations_for_source_ids(
        ["paint-preparation-v1"],
        context,
        target_path="safety_notes[0]",
    )[0]
    with pytest.raises(RetrievalContractError, match="duplicate"):
        validate_retrieved_citations([citation, citation], context, require_at_least_one=True)
