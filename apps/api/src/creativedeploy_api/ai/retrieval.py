"""Small provider-neutral retrieval and citation contracts shared by products."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Sequence
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Locale = Literal["zh-CN", "en-US"]


class RetrievalContractError(ValueError):
    """Retrieved context or Provider citations failed the local trust boundary."""


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class RetrievedContextUnit(_StrictModel):
    """One bounded, source-attributed repository-local knowledge chunk."""

    source_id: Annotated[str, Field(min_length=1, max_length=160)]
    source_title: Annotated[str, Field(min_length=1, max_length=300)]
    source_type: Annotated[str, Field(min_length=1, max_length=160)]
    repository_reference: Annotated[str, Field(min_length=1, max_length=512)]
    chunk_id: Annotated[str, Field(min_length=1, max_length=200)]
    section: Annotated[str, Field(min_length=1, max_length=120)]
    content: Annotated[str, Field(min_length=1, max_length=4000)]
    retrieval_rationale: Annotated[str, Field(min_length=1, max_length=500)]
    retrieval_score_ppm: Annotated[int, Field(ge=0, le=1_000_000)] | None = None
    locale: Locale
    corpus_id: Annotated[str, Field(min_length=1, max_length=120)]
    corpus_version: Annotated[str, Field(min_length=1, max_length=80)]

    @model_validator(mode="after")
    def repository_reference_is_local(self) -> RetrievedContextUnit:
        if not self.repository_reference.startswith("repo://"):
            raise ValueError("repository_reference must use the repo:// scheme")
        return self

    @property
    def citation_key(self) -> tuple[str, str]:
        return self.source_id, self.chunk_id


class RetrievedCitation(_StrictModel):
    """A Provider-authored reference to an exact retrieved source chunk."""

    source_id: Annotated[str, Field(min_length=1, max_length=160)]
    chunk_id: Annotated[str, Field(min_length=1, max_length=200)]
    target_path: Annotated[str, Field(min_length=1, max_length=240)]


class RetrievedContextBundle(_StrictModel):
    """Canonical context snapshot supplied to Fixture or live adapters."""

    retrieval_version: Literal["retrieval-context.v1"] = "retrieval-context.v1"
    product_space: Literal["arcana", "paintpilot"]
    units: Annotated[list[RetrievedContextUnit], Field(min_length=1, max_length=24)]

    @model_validator(mode="after")
    def exact_chunk_identities_are_unique(self) -> RetrievedContextBundle:
        keys = [unit.citation_key for unit in self.units]
        if len(keys) != len(set(keys)):
            raise ValueError("retrieved context chunk identities must be unique")
        return self

    def canonical_hash(self) -> str:
        encoded = json.dumps(
            self.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


def validate_retrieved_citations(
    citations: Sequence[RetrievedCitation],
    context: RetrievedContextBundle,
    *,
    require_at_least_one: bool,
) -> tuple[RetrievedCitation, ...]:
    """Reject every unsupported or duplicate Provider citation."""

    if require_at_least_one and not citations:
        raise RetrievalContractError("at least one retrieved citation is required")
    allowed = {unit.citation_key for unit in context.units}
    seen: set[tuple[str, str, str]] = set()
    validated: list[RetrievedCitation] = []
    for citation in citations:
        if (citation.source_id, citation.chunk_id) not in allowed:
            raise RetrievalContractError("citation is outside the retrieved source set")
        identity = (citation.source_id, citation.chunk_id, citation.target_path)
        if identity in seen:
            raise RetrievalContractError("duplicate citation")
        seen.add(identity)
        validated.append(citation)
    return tuple(validated)


def citations_for_source_ids(
    source_ids: Iterable[str],
    context: RetrievedContextBundle,
    *,
    target_path: str,
) -> tuple[RetrievedCitation, ...]:
    """Map source IDs to exact retrieved chunks without inventing a source."""

    requested = list(source_ids)
    if len(requested) != len(set(requested)):
        raise RetrievalContractError("duplicate source ID")
    by_source = {unit.source_id: unit for unit in context.units}
    try:
        citations = [
            RetrievedCitation(
                source_id=source_id,
                chunk_id=by_source[source_id].chunk_id,
                target_path=target_path,
            )
            for source_id in requested
        ]
    except KeyError as error:
        raise RetrievalContractError("citation source was not retrieved") from error
    return validate_retrieved_citations(citations, context, require_at_least_one=True)
