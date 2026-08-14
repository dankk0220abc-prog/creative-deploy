"""Governed multimodal Paint Plan generation, revision, and exact review flow."""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Literal, cast

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from creativedeploy_api.ai.constants import (
    FIXTURE_CURRENCY,
    FIXTURE_PROVIDER_KEY,
)
from creativedeploy_api.ai.provider_transport import (
    OPENAI_INPUT_CENTS_PER_MILLION,
    OPENAI_OUTPUT_CENTS_PER_MILLION,
    GovernedMultimodalPrompt,
    OpenAIResponsesAdapter,
    PreparedImageAttachment,
    ProviderContractError,
    StructuredOutputValidationError,
    assert_live_provider_execution_authorized,
    structured_json_shape,
)
from creativedeploy_api.ai.retrieval import (
    RetrievalContractError,
    RetrievedContextBundle,
    RetrievedContextUnit,
    validate_retrieved_citations,
)
from creativedeploy_api.ai.zhipu_provider import (
    ZHIPU_GLM_5V_HIGH_INPUT_FEN_PER_MILLION,
    ZHIPU_GLM_5V_HIGH_OUTPUT_FEN_PER_MILLION,
    ZHIPU_GLM_5V_TURBO_MODEL,
    ZhipuChatAdapter,
)
from creativedeploy_api.core.config import Settings
from creativedeploy_api.core.principal import PrincipalContext
from creativedeploy_api.db.models import (
    CommandIdempotencyRecord,
    ImageAsset,
    PaintPlan,
    PaintPlanRegionInstruction,
    PaintPlanReviewEvent,
    PromptTemplateDefinition,
    Region,
    RegionSet,
    RegionSetReview,
    RegionVertex,
)
from creativedeploy_api.db.models.constants import IDEMPOTENCY_STATUS_COMPLETED
from creativedeploy_api.paintpilot.knowledge import LocalPaintPilotKnowledgeLayer
from creativedeploy_api.repositories.identity import (
    ProjectAccess,
    SqlAlchemyIdentityRepository,
)
from creativedeploy_api.repositories.paint_plans import SqlAlchemyPaintPlanRepository
from creativedeploy_api.repositories.region_sets import SqlAlchemyRegionSetRepository
from creativedeploy_api.schemas.ai_foundation import (
    ArtifactIdentity,
    FixtureInvocationPayload,
    InvocationCreateRequest,
    InvocationPreviewRequest,
)
from creativedeploy_api.schemas.errors import ErrorCategory
from creativedeploy_api.schemas.paint_plans import (
    PAINT_PLAN_PROMPT_KEY,
    PAINT_PLAN_PROMPT_VERSION,
    PAINT_PLAN_REQUIRED_ROOT_KEYS,
    PAINT_PLAN_ROOT_KEYS,
    PAINT_PLAN_SCHEMA_VERSION,
    PaintPlanCredentialChoiceRead,
    PaintPlanDocument,
    PaintPlanEditRequest,
    PaintPlanFixtureSource,
    PaintPlanGenerateRequest,
    PaintPlanHistoryResponse,
    PaintPlanImageAssetRead,
    PaintPlanModelChoiceRead,
    PaintPlanPreviewRead,
    PaintPlanPreviewRequest,
    PaintPlanProviderChoiceRead,
    PaintPlanRead,
    PaintPlanRegenerateRequest,
    PaintPlanRegionSetRead,
    PaintPlanReviewEventRead,
    PaintPlanReviewRequest,
    PaintPlanRevisionRequest,
    PaintPlanWorkbenchRead,
    ProviderExecutionMode,
    paint_plan_live_output_contract,
)
from creativedeploy_api.services.ai_foundation import AIFoundationService
from creativedeploy_api.services.governed_sources import (
    CurrentImageSet,
    effective_region_set_lifecycle,
    region_set_stale_reasons,
    resolve_current_image_set,
)
from creativedeploy_api.services.paint_projects import (
    IDEMPOTENCY_RETENTION,
    PaintProjectApplicationError,
    PaintProjectNotFoundError,
)
from creativedeploy_api.services.zhipu_invocations import (
    GovernedZhipuInvocationService,
    ZhipuLiveSelection,
)
from creativedeploy_api.storage.images import ImageStoragePort


class PaintPlanNotFoundError(PaintProjectApplicationError):
    status_code = 404
    error_code = "PAINT_PLAN_NOT_FOUND"
    category: ErrorCategory = "NOT_FOUND"
    message = "The Paint Plan revision was not found."
    allowed_actions = ("reload_paint_plan_workbench",)


class PaintPlanSourceNotReadyError(PaintProjectApplicationError):
    status_code = 409
    error_code = "PAINT_PLAN_SOURCE_NOT_READY"
    category: ErrorCategory = "CONFLICT"
    message = "The governed image and RegionSet source is not ready."
    allowed_actions = ("complete_image_and_region_readiness", "reload_paint_plan_workbench")

    def __init__(self, blockers: list[str]) -> None:
        super().__init__()
        self.safe_details: Mapping[str, object] = MappingProxyType({"blockers": list(blockers)})


class PaintPlanLifecycleConflictError(PaintProjectApplicationError):
    status_code = 409
    error_code = "PAINT_PLAN_LIFECYCLE_CONFLICT"
    category: ErrorCategory = "CONFLICT"
    message = "The exact Paint Plan revision does not permit this command."
    allowed_actions = ("reload_paint_plan_workbench",)


class PaintPlanIdempotencyConflictError(PaintProjectApplicationError):
    status_code = 409
    error_code = "IDEMPOTENCY_KEY_REUSED"
    category: ErrorCategory = "IDEMPOTENCY_KEY_REUSED"
    message = "The Idempotency-Key was already used with different Paint Plan data."
    allowed_actions = ("retry_with_original_payload", "use_new_idempotency_key")


class PaintPlanCitationInvalidError(PaintProjectApplicationError):
    status_code = 409
    error_code = "PAINT_PLAN_CITATION_INVALID"
    category: ErrorCategory = "CONFLICT"
    message = "The edited Paint Plan citations are not supported by its retrieval snapshot."
    allowed_actions = ("use_retrieved_citations", "remove_unsupported_citations")


class PaintPlanOutputInvalidError(PaintProjectApplicationError):
    status_code = 502
    error_code = "PAINT_PLAN_OUTPUT_INVALID"
    category: ErrorCategory = "PROVIDER_RESPONSE_INVALID"
    message = "The Provider output did not satisfy the exact Paint Plan contract."
    allowed_actions = ("inspect_invocation_audit", "retry_with_new_idempotency_key")


class PaintPlanLiveExecutionBlockedError(PaintProjectApplicationError):
    status_code = 409
    error_code = "LIVE_PROVIDER_EXECUTION_NOT_AUTHORIZED"
    category: ErrorCategory = "CONFLICT"
    message = "Live Provider execution is not authorized in this phase."
    allowed_actions = ("select_fixture_provider",)

    def __init__(self, blockers: list[str] | None = None) -> None:
        super().__init__()
        self.safe_details: Mapping[str, object] = MappingProxyType(
            {"blockers": list(dict.fromkeys(blockers or []))}
        )


@dataclass(frozen=True, slots=True)
class PaintPlanSourceSnapshot:
    access: ProjectAccess
    image_set: CurrentImageSet
    region_set: RegionSet | None
    regions: list[Region]
    region_read: PaintPlanRegionSetRead | None
    image_reads: list[PaintPlanImageAssetRead]
    prompt: PromptTemplateDefinition | None
    blockers: list[str]

    @property
    def ready(self) -> bool:
        return not self.blockers


def _content_url(project_id: uuid.UUID, image_asset_id: uuid.UUID) -> str:
    return f"/api/v1/paint-projects/{project_id}/images/{image_asset_id}/content"


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _content_hash(document: PaintPlanDocument) -> str:
    return hashlib.sha256(_canonical_json(document.model_dump(mode="json"))).hexdigest()


def _payload_hash(value: object) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


def _scope_key(principal_id: str, project_id: uuid.UUID, command: str) -> str:
    return f"principal:{principal_id}:project:{project_id}:command:{command}"


def _latest_reviews_by_region_set(
    reviews: list[RegionSetReview],
) -> dict[uuid.UUID, RegionSetReview]:
    result: dict[uuid.UUID, RegionSetReview] = {}
    for review in reviews:
        result.setdefault(review.region_set_id, review)
    return result


def _latest_plan_reviews(
    reviews: list[PaintPlanReviewEvent],
) -> dict[uuid.UUID, PaintPlanReviewEvent]:
    result: dict[uuid.UUID, PaintPlanReviewEvent] = {}
    for review in reviews:
        result.setdefault(review.paint_plan_id, review)
    return result


def _validate_document_regions(
    document: PaintPlanDocument,
    regions: list[Region],
) -> None:
    paint_regions = {item.id: item for item in regions if item.kind == "paint"}
    excluded_ids = {item.id for item in regions if item.kind == "exclude"}
    instruction_ids = {item.region_id for item in document.instructions}
    if instruction_ids & excluded_ids or instruction_ids != set(paint_regions):
        raise PaintPlanOutputInvalidError
    for instruction in document.instructions:
        source = paint_regions.get(instruction.region_id)
        if (
            source is None
            or instruction.stable_region_key != source.stable_region_key
            or instruction.region_label != source.label
        ):
            raise PaintPlanOutputInvalidError


def _validate_edit_citations(
    document: PaintPlanDocument,
    retrieved_context_snapshot: list[dict[str, object]],
) -> None:
    if not document.knowledge_citations:
        return
    try:
        retrieval = RetrievedContextBundle(
            product_space="paintpilot",
            units=[
                RetrievedContextUnit.model_validate(item) for item in retrieved_context_snapshot
            ],
        )
        validate_retrieved_citations(
            document.knowledge_citations,
            retrieval,
            require_at_least_one=True,
        )
    except (RetrievalContractError, ValidationError):
        raise PaintPlanCitationInvalidError from None


_MISSING_PAINT_PLAN_VALUE = object()
_PAINT_PLAN_EXPECTED_JSON_TYPES = {
    ("schema_version",): "string",
    ("title",): "string",
    ("overall_approach",): "string",
    ("instructions",): "array<object>",
    ("instructions", "region_id"): "string",
    ("instructions", "stable_region_key"): "string",
    ("instructions", "region_label"): "string",
    ("instructions", "target_color"): "string",
    ("instructions", "preparation"): "string",
    ("instructions", "base_coat"): "string",
    ("instructions", "layer_strategy"): "string",
    ("instructions", "edge_treatment"): "string",
    ("instructions", "lighting_guidance"): "string",
    ("instructions", "material_guidance"): "string",
    ("instructions", "warnings"): "array<string>",
    ("instructions", "confidence_ppm"): "integer",
    ("safety_notes",): "array<string>",
    ("knowledge_citations",): "array<object>",
    ("knowledge_citations", "source_id"): "string",
    ("knowledge_citations", "chunk_id"): "string",
    ("knowledge_citations", "target_path"): "string",
}
_PAINT_PLAN_SAFE_UNEXPECTED_ROOT_KEYS = frozenset(
    {
        "approach",
        "citations",
        "data",
        "document",
        "output",
        "overall_strategy",
        "paint_plan",
        "plan",
        "regions",
        "response",
        "result",
        "steps",
        "summary",
        "version",
    }
)


def _pydantic_error_path(error: ValidationError) -> str:
    errors = error.errors(include_url=False, include_context=False, include_input=False)
    if not errors:
        return "$"
    path = "$"
    for component in errors[0].get("loc", ()):
        path += f"[{component}]" if isinstance(component, int) else f".{component}"
    return path[:240]


def _value_at_error_path(raw: Mapping[str, object], loc: tuple[object, ...]) -> object:
    value: object = raw
    for component in loc:
        if isinstance(component, str) and isinstance(value, Mapping):
            value = value.get(component, _MISSING_PAINT_PLAN_VALUE)
        elif isinstance(component, int) and isinstance(value, list) and component < len(value):
            value = value[component]
        else:
            return _MISSING_PAINT_PLAN_VALUE
    return value


def _paint_plan_pydantic_diagnostics(
    error: ValidationError,
    raw: Mapping[str, object],
) -> tuple[
    str | None,
    str | None,
    int | None,
    tuple[str, ...],
    tuple[str, ...],
    tuple[str, ...],
    str | None,
]:
    """Describe only schema structure and allowlisted names, never output values."""

    errors = error.errors(include_url=False, include_context=False, include_input=False)
    if not errors:
        return None, None, None, (), (), (), None
    first = errors[0]
    raw_loc = first.get("loc", ())
    loc = raw_loc if isinstance(raw_loc, tuple) else ()
    field_path = tuple(component for component in loc if isinstance(component, str))
    received = _value_at_error_path(raw, loc)
    received_count = len(received) if isinstance(received, list) else None
    received_root_keys = tuple(key for key in PAINT_PLAN_ROOT_KEYS if key in raw)
    missing_required_keys = tuple(key for key in PAINT_PLAN_REQUIRED_ROOT_KEYS if key not in raw)
    unexpected_object_keys = tuple(
        sorted(
            key
            for key in raw
            if isinstance(key, str)
            and key not in PAINT_PLAN_ROOT_KEYS
            and key in _PAINT_PLAN_SAFE_UNEXPECTED_ROOT_KEYS
        )
    )
    validator_category = first.get("type")
    return (
        _PAINT_PLAN_EXPECTED_JSON_TYPES.get(field_path),
        structured_json_shape(received, missing=_MISSING_PAINT_PLAN_VALUE),
        received_count,
        received_root_keys,
        missing_required_keys,
        unexpected_object_keys,
        validator_category if isinstance(validator_category, str) else None,
    )


def _validate_live_paint_plan_output(
    raw: Mapping[str, object],
    *,
    regions: list[Region],
    retrieval: RetrievedContextBundle,
) -> dict[str, object]:
    try:
        document = PaintPlanDocument.model_validate(dict(raw))
    except ValidationError as error:
        (
            expected_json_type,
            received_json_type,
            received_item_count,
            received_object_keys,
            missing_required_keys,
            unexpected_object_keys,
            validator_error_category,
        ) = _paint_plan_pydantic_diagnostics(error, raw)
        raise StructuredOutputValidationError(
            "SCHEMA_VALIDATION_FAILED",
            path=_pydantic_error_path(error),
            expected_root_json_type="object",
            received_root_json_type="object",
            expected_json_type=expected_json_type,
            received_json_type=received_json_type,
            received_item_count=received_item_count,
            received_object_keys=received_object_keys,
            missing_required_keys=missing_required_keys,
            unexpected_object_keys=unexpected_object_keys,
            validator_error_category=validator_error_category,
        ) from None
    try:
        _validate_document_regions(document, regions)
    except PaintPlanOutputInvalidError:
        raise StructuredOutputValidationError(
            "SCHEMA_VALIDATION_FAILED",
            path="$.instructions",
            expected_root_json_type="object",
            received_root_json_type="object",
            expected_json_type="array<object>",
            received_json_type="array<object>",
            received_item_count=len(document.instructions),
            received_object_keys=tuple(key for key in PAINT_PLAN_ROOT_KEYS if key in raw),
            validator_error_category="governed_region_identity_mismatch",
        ) from None
    try:
        validate_retrieved_citations(
            document.knowledge_citations,
            retrieval,
            require_at_least_one=True,
        )
    except RetrievalContractError:
        raise StructuredOutputValidationError(
            "CITATION_VALIDATION_FAILED",
            path="$.knowledge_citations",
            expected_root_json_type="object",
            received_root_json_type="object",
            expected_json_type="array<object>",
            received_json_type="array<object>",
            received_item_count=len(document.knowledge_citations),
            received_object_keys=tuple(key for key in PAINT_PLAN_ROOT_KEYS if key in raw),
            validator_error_category="retrieved_citation_mismatch",
        ) from None
    return document.model_dump(mode="json")


def _zhipu_live_system_prompt(fixture_source: PaintPlanFixtureSource) -> str:
    return (
        f"{fixture_source.prompt_template_body} Use only the supplied repository-local "
        "practice notes for general preparation, layering, compatibility, and safety claims. "
        "Include exact knowledge_citations using only retrieved source_id and chunk_id values; "
        "target_path must identify the supported plan field.\n"
        f"{paint_plan_live_output_contract()}"
    )


class PaintPlanService:
    """Project-scoped orchestration over governed sources and Phase 3A ledgers."""

    def __init__(
        self,
        session: AsyncSession,
        storage: ImageStoragePort,
        settings: Settings,
        ai_service: AIFoundationService,
        *,
        live_service: GovernedZhipuInvocationService | None = None,
    ) -> None:
        self._session = session
        self._storage = storage
        self._settings = settings
        self._ai_service = ai_service
        self._live_service = live_service
        self._knowledge = LocalPaintPilotKnowledgeLayer()
        self._identity_repository = SqlAlchemyIdentityRepository(session)
        self._region_repository = SqlAlchemyRegionSetRepository(session)
        self._repository = SqlAlchemyPaintPlanRepository(session)

    async def _resolve_access(
        self,
        *,
        project_id: uuid.UUID,
        principal: PrincipalContext,
        for_update: bool,
    ) -> ProjectAccess:
        if principal.user_id is None:
            project = await self._region_repository.get_owned_project(
                project_id=project_id,
                owner_principal_id=principal.principal_id,
                for_update=for_update,
            )
            if project is None:
                raise PaintProjectNotFoundError
            return ProjectAccess(project=project, role="owner")
        access = await self._identity_repository.resolve_project_access(
            project_id=project_id,
            principal_id=principal.principal_id,
            user_id=principal.user_id,
            for_update=for_update,
        )
        if access is None:
            raise PaintProjectNotFoundError
        return access

    @staticmethod
    def _image_read(project_id: uuid.UUID, asset: ImageAsset) -> PaintPlanImageAssetRead:
        return PaintPlanImageAssetRead.model_validate(
            {
                "id": asset.id,
                "role": asset.role,
                "version": asset.version,
                "content_url": _content_url(project_id, asset.id),
                "sha256": asset.sha256,
                "media_type": asset.declared_content_type,
                "byte_length": asset.byte_size,
                "width": asset.width,
                "height": asset.height,
                "upload_validation_result": asset.upload_validation_result,
                "rights_attestation_status": asset.rights_attestation_status,
                "rights_attestation_version": asset.rights_attestation_version,
                "intended_usage": list(asset.intended_usage),
            }
        )

    @staticmethod
    def _region_read(
        region_set: RegionSet,
        regions: list[Region],
        vertices: list[RegionVertex],
        *,
        effective_lifecycle: str,
        stale: bool,
    ) -> PaintPlanRegionSetRead:
        vertices_by_region: dict[uuid.UUID, list[tuple[int, int]]] = {}
        for vertex in vertices:
            vertices_by_region.setdefault(vertex.region_id, []).append((vertex.x_ppm, vertex.y_ppm))
        return PaintPlanRegionSetRead.model_validate(
            {
                "id": region_set.id,
                "version": region_set.version,
                "geometry_fingerprint": region_set.geometry_fingerprint,
                "effective_lifecycle": effective_lifecycle,
                "stale": stale,
                "regions": [
                    {
                        "id": region.id,
                        "stable_region_key": region.stable_region_key,
                        "kind": region.kind,
                        "label": region.label,
                        "normalized_label": region.normalized_label,
                        "z_index": region.z_index,
                        "opacity_ppm": region.opacity_ppm,
                        "notes": region.notes,
                        "bbox_min_x_ppm": region.bbox_min_x_ppm,
                        "bbox_min_y_ppm": region.bbox_min_y_ppm,
                        "bbox_max_x_ppm": region.bbox_max_x_ppm,
                        "bbox_max_y_ppm": region.bbox_max_y_ppm,
                        "vertices": vertices_by_region.get(region.id, []),
                    }
                    for region in regions
                ],
            }
        )

    async def _load_source(
        self,
        *,
        project_id: uuid.UUID,
        principal: PrincipalContext,
        region_set_id: uuid.UUID | None,
        expected_image_set_fingerprint: str | None,
        for_update: bool,
    ) -> PaintPlanSourceSnapshot:
        access = await self._resolve_access(
            project_id=project_id,
            principal=principal,
            for_update=for_update,
        )
        owner = access.project.owner_principal_id
        assets = await self._region_repository.list_current_assets(
            project_id=project_id,
            owner_principal_id=owner,
            for_update=for_update,
        )
        readiness = await self._region_repository.list_readiness_reviews(
            project_id=project_id,
            owner_principal_id=owner,
        )
        region_sets = await self._region_repository.list_region_sets(
            project_id=project_id,
            owner_principal_id=owner,
        )
        region_reviews = await self._region_repository.list_reviews(
            project_id=project_id,
            owner_principal_id=owner,
        )
        image_set = resolve_current_image_set(
            project_id=project_id,
            assets=assets,
            readiness_reviews=readiness,
            storage=self._storage,
        )
        selected = next(
            (item for item in region_sets if region_set_id is None or item.id == region_set_id),
            None,
        )
        blockers: list[str] = []
        if image_set.status != "ready":
            blockers.append(f"image_set_{image_set.status}")
        if image_set.latest_readiness_review is None:
            blockers.append("readiness_review_missing")
        if (
            expected_image_set_fingerprint is not None
            and expected_image_set_fingerprint != image_set.fingerprint
        ):
            blockers.append("image_set_fingerprint_changed")
        regions: list[Region] = []
        region_read = None
        if selected is None:
            blockers.append("region_set_missing")
        else:
            if not region_sets or selected.id != region_sets[0].id:
                blockers.append("region_set_not_current")
            reviews_by_set = _latest_reviews_by_region_set(region_reviews)
            effective = effective_region_set_lifecycle(
                selected,
                region_sets=region_sets,
                reviews_by_set=reviews_by_set,
            )
            stale_reasons = region_set_stale_reasons(selected, image_set)
            if effective != "approved":
                blockers.append("region_set_not_approved")
            blockers.extend(reason for reason in stale_reasons if reason not in blockers)
            regions = await self._region_repository.list_regions(region_set_id=selected.id)
            vertices = await self._region_repository.list_vertices(region_set_id=selected.id)
            if not any(region.kind == "paint" for region in regions):
                blockers.append("paint_regions_missing")
            region_read = self._region_read(
                selected,
                regions,
                vertices,
                effective_lifecycle=effective,
                stale=bool(stale_reasons),
            )
        prompt = await self._repository.get_prompt(
            template_key=PAINT_PLAN_PROMPT_KEY,
            version=PAINT_PLAN_PROMPT_VERSION,
        )
        if prompt is None:
            blockers.append("prompt_template_unavailable")
        return PaintPlanSourceSnapshot(
            access=access,
            image_set=image_set,
            region_set=selected,
            regions=regions,
            region_read=region_read,
            image_reads=[self._image_read(project_id, item) for item in assets],
            prompt=prompt,
            blockers=list(dict.fromkeys(blockers)),
        )

    @staticmethod
    def _plan_stale_reasons(
        plan: PaintPlan,
        source: PaintPlanSourceSnapshot,
    ) -> list[str]:
        reasons: list[str] = []
        if source.image_set.status != "ready":
            reasons.append("image_set_not_ready")
        if plan.source_image_set_fingerprint != source.image_set.fingerprint:
            reasons.append("image_set_fingerprint_changed")
        latest_readiness = source.image_set.latest_readiness_review
        if (
            latest_readiness is None
            or plan.source_readiness_review_id != latest_readiness.id
            or plan.source_readiness_review_version != latest_readiness.version
        ):
            reasons.append("image_set_readiness_review_changed")
        if source.region_set is None or plan.source_region_set_id != source.region_set.id:
            reasons.append("region_set_changed")
        elif plan.source_geometry_fingerprint != source.region_set.geometry_fingerprint:
            reasons.append("region_geometry_changed")
        return reasons

    async def _plan_read(
        self,
        plan: PaintPlan,
        *,
        source: PaintPlanSourceSnapshot,
        current_plan_id: uuid.UUID | None,
        latest_review: PaintPlanReviewEvent | None,
    ) -> PaintPlanRead:
        instructions = await self._repository.list_instructions(plan_id=plan.id)
        invocation, attempt, usage, cost = await self._repository.get_attempt_accounting(
            invocation_id=plan.source_invocation_id,
            attempt_id=plan.source_attempt_id,
        )
        if invocation is None:
            raise PaintPlanLifecycleConflictError
        provenance = invocation.safe_payload.get("paint_plan_provenance")
        raw_image_assets = (
            None if not isinstance(provenance, Mapping) else provenance.get("image_assets")
        )
        if not isinstance(raw_image_assets, list):
            raise PaintPlanLifecycleConflictError
        raw_generation_locale = (
            "en-US"
            if not isinstance(provenance, Mapping) or provenance.get("generation_locale") is None
            else provenance.get("generation_locale")
        )
        if raw_generation_locale not in {"zh-CN", "en-US"}:
            raise PaintPlanLifecycleConflictError
        generation_locale = cast(Literal["zh-CN", "en-US"], raw_generation_locale)
        try:
            source_image_assets = [
                PaintPlanImageAssetRead.model_validate_json(
                    json.dumps(item, ensure_ascii=False, separators=(",", ":"))
                )
                for item in raw_image_assets
            ]
        except (TypeError, ValueError, ValidationError) as error:
            raise PaintPlanLifecycleConflictError from error
        if any(
            item.content_url != _content_url(plan.paint_project_id, item.id)
            for item in source_image_assets
        ):
            raise PaintPlanLifecycleConflictError
        document = PaintPlanDocument.model_validate(
            {
                "schema_version": plan.response_schema_version,
                "title": plan.title,
                "overall_approach": plan.overall_approach,
                "instructions": [
                    {
                        "region_id": item.region_id,
                        "stable_region_key": item.stable_region_key,
                        "region_label": item.region_label_snapshot,
                        "target_color": item.target_color,
                        "preparation": item.preparation,
                        "base_coat": item.base_coat,
                        "layer_strategy": item.layer_strategy,
                        "edge_treatment": item.edge_treatment,
                        "lighting_guidance": item.lighting_guidance,
                        "material_guidance": item.material_guidance,
                        "warnings": list(item.warnings),
                        "confidence_ppm": item.confidence_ppm,
                    }
                    for item in instructions
                ],
                "safety_notes": list(plan.safety_notes),
                "knowledge_citations": list(plan.citation_snapshot),
            }
        )
        stale_reasons = self._plan_stale_reasons(plan, source)
        is_current = plan.id == current_plan_id and plan.lifecycle != "superseded"
        stale = bool(stale_reasons)
        effective_lifecycle = "superseded" if (not is_current or stale) else plan.lifecycle
        approval_valid = effective_lifecycle == "approved" and not stale
        allowed_actions: list[str] = []
        if source.access.is_owner and is_current and not stale:
            if plan.lifecycle in {"generated", "edited", "approved", "rejected"}:
                allowed_actions.extend(("edit", "regenerate"))
            if plan.lifecycle in {"generated", "edited"}:
                allowed_actions.append("submit")
        if (
            source.access.role == "reviewer"
            and is_current
            and not stale
            and plan.lifecycle == "under_review"
        ):
            allowed_actions.extend(("approve", "reject"))
        review_read = (
            None
            if latest_review is None
            else PaintPlanReviewEventRead(
                id=latest_review.id,
                action=latest_review.action,  # type: ignore[arg-type]
                reason=latest_review.reason,
                actor_id=latest_review.actor_principal_id,
                actor_display_name_snapshot=latest_review.actor_display_name_snapshot,
                created_at=latest_review.created_at,
            )
        )
        provider_request_id_status = cast(
            Literal["absent", "provided", "unavailable"],
            "absent" if attempt is None else attempt.provider_request_id_status,
        )
        usage_measurement_status = cast(
            Literal["measured", "unavailable"],
            "unavailable" if usage is None else usage.measurement_status,
        )
        cost_measurement_status = cast(
            Literal["estimated", "measured", "unavailable"],
            "unavailable" if cost is None else cost.measurement_status,
        )
        cost_currency = cast(
            Literal["FIXTURE_CREDITS", "USD", "CNY"],
            (
                "FIXTURE_CREDITS"
                if plan.provider_key_snapshot == FIXTURE_PROVIDER_KEY
                else "CNY"
                if plan.provider_key_snapshot == "zhipu"
                else "USD"
            )
            if cost is None
            else cost.currency,
        )
        return PaintPlanRead(
            id=plan.id,
            lineage_id=plan.lineage_id,
            paint_project_id=plan.paint_project_id,
            version=plan.version,
            lineage_revision=plan.lineage_revision,
            parent_plan_id=plan.parent_plan_id,
            revision_kind=plan.revision_kind,  # type: ignore[arg-type]
            lifecycle=plan.lifecycle,  # type: ignore[arg-type]
            effective_lifecycle=effective_lifecycle,  # type: ignore[arg-type]
            is_current=is_current,
            stale=stale,
            stale_reasons=stale_reasons,
            approval_valid=approval_valid,
            source_invocation_id=plan.source_invocation_id,
            source_attempt_id=plan.source_attempt_id,
            requested_by_user_id=invocation.requesting_user_id,
            invocation_created_at=invocation.created_at,
            source_image_set_fingerprint=plan.source_image_set_fingerprint,
            source_image_assets=source_image_assets,
            source_readiness_review_id=plan.source_readiness_review_id,
            source_readiness_review_version=plan.source_readiness_review_version,
            source_region_set_id=plan.source_region_set_id,
            source_region_set_version=plan.source_region_set_version,
            source_geometry_fingerprint=plan.source_geometry_fingerprint,
            provider_definition_id=plan.provider_definition_id,
            provider_key=plan.provider_key_snapshot,
            provider_revision_snapshot=plan.provider_revision_snapshot,
            model_definition_id=plan.model_definition_id,
            model_id=plan.model_id_snapshot,
            model_revision_snapshot=plan.model_revision_snapshot,
            provider_pricing_snapshot_id=plan.provider_pricing_snapshot_id,
            prompt_template_id=plan.prompt_template_definition_id,
            prompt_template_key=plan.prompt_template_key_snapshot,  # type: ignore[arg-type]
            prompt_version=plan.prompt_template_version_snapshot,
            prompt_hash=plan.prompt_content_hash,
            generation_locale=generation_locale,
            schema_version=plan.response_schema_version,  # type: ignore[arg-type]
            content_hash=plan.content_hash,
            document=document,
            retrieved_context=[
                RetrievedContextUnit.model_validate(item)
                for item in plan.retrieved_context_snapshot
            ],
            provider_request_id_status=provider_request_id_status,
            provider_request_id=None if attempt is None else attempt.provider_request_id,
            usage_measurement_status=usage_measurement_status,
            input_units=None if usage is None else usage.input_units,
            output_units=None if usage is None else usage.output_units,
            cost_measurement_status=cost_measurement_status,
            cost_minor_units=None if cost is None else cost.amount_minor_units,
            cost_currency=cost_currency,
            latest_review=review_read,
            allowed_actions=allowed_actions,
            created_by_actor_type=plan.created_by_actor_type,  # type: ignore[arg-type]
            created_by_actor_id=plan.created_by_actor_id,
            created_by_actor_display_name_snapshot=(plan.created_by_actor_display_name_snapshot),
            created_at=plan.created_at,
        )

    async def _plans_read(
        self,
        *,
        source: PaintPlanSourceSnapshot,
    ) -> list[PaintPlanRead]:
        plans = await self._repository.list_plans(
            project_id=source.access.project.id,
            owner_principal_id=source.access.project.owner_principal_id,
        )
        reviews = await self._repository.list_reviews(
            project_id=source.access.project.id,
            owner_principal_id=source.access.project.owner_principal_id,
        )
        latest_reviews = _latest_plan_reviews(reviews)
        current = next((item for item in plans if item.lifecycle != "superseded"), None)
        return [
            await self._plan_read(
                item,
                source=source,
                current_plan_id=None if current is None else current.id,
                latest_review=latest_reviews.get(item.id),
            )
            for item in plans
        ]

    async def get_workbench(
        self,
        *,
        project_id: uuid.UUID,
        principal: PrincipalContext,
    ) -> PaintPlanWorkbenchRead:
        async with self._session.begin():
            source = await self._load_source(
                project_id=project_id,
                principal=principal,
                region_set_id=None,
                expected_image_set_fingerprint=None,
                for_update=False,
            )
            provider_models = await self._repository.list_provider_models()
            grouped: dict[uuid.UUID, PaintPlanProviderChoiceRead] = {}
            for provider, model in provider_models:
                if provider.provider_key not in {"fixture_local", "openai", "zhipu"}:
                    continue
                mode: ProviderExecutionMode = (
                    "fixture_available"
                    if provider.provider_key == FIXTURE_PROVIDER_KEY
                    else "live_authorization_required"
                )
                pricing = (
                    None
                    if provider.provider_key == FIXTURE_PROVIDER_KEY
                    else await self._repository.get_pricing(model_definition_id=model.id)
                )
                currency = model.pricing_currency if pricing is None else pricing.currency
                if currency not in {"FIXTURE_CREDITS", "USD", "CNY"}:
                    continue
                model_read = PaintPlanModelChoiceRead(
                    id=model.id,
                    model_id=model.model_id,
                    display_name=model.display_name,
                    execution_mode=mode,
                    currency=currency,  # type: ignore[arg-type]
                    supports_vision=model.supports_vision,
                    supports_structured_output=model.supports_structured_output,
                )
                existing = grouped.get(provider.id)
                if existing is None:
                    grouped[provider.id] = PaintPlanProviderChoiceRead(
                        id=provider.id,
                        provider_key=provider.provider_key,  # type: ignore[arg-type]
                        display_name=provider.display_name,
                        execution_mode=mode,
                        models=[model_read],
                    )
                else:
                    existing.models.append(model_read)
            credentials: list[PaintPlanCredentialChoiceRead] = []
            if principal.user_id is not None and source.access.is_owner:
                for credential, grant in await self._repository.list_owned_credentials_with_grants(
                    owner_user_id=principal.user_id,
                    project_id=project_id,
                ):
                    if credential.provider_key not in {"fixture_local", "openai", "zhipu"}:
                        continue
                    credentials.append(
                        PaintPlanCredentialChoiceRead(
                            id=credential.id,
                            alias=credential.alias,
                            provider_key=credential.provider_key,  # type: ignore[arg-type]
                            active_grant=grant is not None,
                            status=credential.status,
                        )
                    )
            plans = await self._plans_read(source=source)
        current = next((item for item in plans if item.is_current), None)
        allowed_actions = ["read_history"]
        blockers = list(source.blockers)
        if source.access.project.status == "ABANDONED":
            blockers.append("project_abandoned")
        if principal.user_id is None:
            blockers.append("authenticated_user_required")
        if (
            source.access.is_owner
            and source.ready
            and principal.user_id is not None
            and source.access.project.status != "ABANDONED"
        ):
            allowed_actions.append("preview")
            allowed_actions.append("generate" if current is None else "regenerate")
        return PaintPlanWorkbenchRead(
            paint_project_id=project_id,
            access_role=source.access.role,  # type: ignore[arg-type]
            image_set_status=source.image_set.status,
            image_set_fingerprint=source.image_set.fingerprint,
            readiness_review_id=(
                None
                if source.image_set.latest_readiness_review is None
                else source.image_set.latest_readiness_review.id
            ),
            image_assets=source.image_reads,
            region_set=source.region_read,
            source_ready=source.ready,
            blockers=list(dict.fromkeys(blockers)),
            providers=list(grouped.values()),
            credentials=credentials,
            current_plan=current,
            history=plans,
            allowed_actions=allowed_actions,
        )

    def _fixture_source(
        self,
        source: PaintPlanSourceSnapshot,
        *,
        generation_locale: Literal["zh-CN", "en-US"],
        intent: str | None,
        regeneration_of_plan_id: uuid.UUID | None,
    ) -> PaintPlanFixtureSource:
        if (
            not source.ready
            or source.region_read is None
            or source.image_set.latest_readiness_review is None
            or source.prompt is None
        ):
            raise PaintPlanSourceNotReadyError(source.blockers)
        readiness_review = source.image_set.latest_readiness_review
        return PaintPlanFixtureSource(
            image_set_fingerprint=source.image_set.fingerprint,
            readiness_review_id=readiness_review.id,
            readiness_review_version=readiness_review.version,
            image_assets=source.image_reads,
            region_set=source.region_read,
            prompt_template_id=source.prompt.id,
            prompt_template_key=source.prompt.template_key,  # type: ignore[arg-type]
            prompt_template_version=source.prompt.version,  # type: ignore[arg-type]
            prompt_template_body=source.prompt.template_body,
            prompt_content_hash=source.prompt.content_hash,
            response_schema_version=source.prompt.schema_version,  # type: ignore[arg-type]
            generation_locale=generation_locale,
            intent=intent,
            regeneration_of_plan_id=regeneration_of_plan_id,
        )

    def _invocation_preview_request(
        self,
        *,
        source: PaintPlanSourceSnapshot,
        payload: PaintPlanPreviewRequest | PaintPlanGenerateRequest | PaintPlanRegenerateRequest,
        regeneration_of_plan_id: uuid.UUID | None,
    ) -> InvocationPreviewRequest:
        fixture_source = self._fixture_source(
            source,
            generation_locale=payload.generation_locale,
            intent=payload.intent,
            regeneration_of_plan_id=regeneration_of_plan_id,
        )
        assert source.region_set is not None
        assert source.region_read is not None
        artifacts = [
            ArtifactIdentity(
                id=item.id,
                revision=item.version,
                content_hash=f"sha256:{item.sha256}",
                media_type=item.media_type,
                byte_length=item.byte_length,
            )
            for item in source.image_reads
        ]
        region_bytes = _canonical_json(source.region_read.model_dump(mode="json"))
        artifacts.append(
            ArtifactIdentity(
                id=source.region_set.id,
                revision=source.region_set.version,
                content_hash=f"sha256:{source.region_set.geometry_fingerprint}",
                media_type="application/vnd.creativedeploy.region-set+json",
                byte_length=len(region_bytes),
            )
        )
        return InvocationPreviewRequest(
            product_space="paintpilot",
            project_id=source.access.project.id,
            invocation_family="paint_plan_generation",
            provider_definition_id=payload.provider_definition_id,
            model_definition_id=payload.model_definition_id,
            credential_id=payload.credential_id,
            temporary_credential=None,
            requested_capabilities=["vision_understanding", "structured_output"],
            artifacts=artifacts,
            payload=FixtureInvocationPayload(
                prompt_label="paint-plan.v1",
                fixture_input="governed-server-snapshot",
                scenario="success",
                paint_plan_input=fixture_source,
            ),
            confirm_fixture_use=True,
        )

    async def _live_selection_readiness(
        self,
        *,
        source: PaintPlanSourceSnapshot,
        payload: PaintPlanPreviewRequest | PaintPlanGenerateRequest | PaintPlanRegenerateRequest,
        principal: PrincipalContext,
        regeneration_of_plan_id: uuid.UUID | None,
        provider_key: Literal["openai", "zhipu"],
    ) -> tuple[int | None, list[str]]:
        if not source.ready:
            return None, ["cost_estimate_unavailable"]
        fixture_source = self._fixture_source(
            source,
            generation_locale=payload.generation_locale,
            intent=payload.intent,
            regeneration_of_plan_id=regeneration_of_plan_id,
        )
        retrieval = self._knowledge.retrieve(locale=fixture_source.generation_locale)
        prompt = GovernedMultimodalPrompt(
            system_prompt=(
                _zhipu_live_system_prompt(fixture_source)
                if provider_key == "zhipu"
                else fixture_source.prompt_template_body
            ),
            user_intent=fixture_source.intent,
            structured_context={
                "paint_plan_source": fixture_source.model_dump(
                    mode="json",
                    exclude={"prompt_template_body", "intent"},
                ),
                "retrieved_context": retrieval.model_dump(mode="json"),
            },
            generation_locale=fixture_source.generation_locale,
        )
        blockers: list[str] = []
        try:
            if provider_key == "openai":
                estimate_minor_units = (
                    OpenAIResponsesAdapter()
                    .estimate_cost_from_dimensions(
                        prompt=prompt,
                        image_dimensions=[(item.width, item.height) for item in source.image_reads],
                        response_schema=PaintPlanDocument.model_json_schema(),
                        max_output_tokens=4096,
                    )
                    .amount_minor_units_upper_bound
                )
            else:
                estimate_minor_units = ZhipuChatAdapter(
                    ZHIPU_GLM_5V_TURBO_MODEL
                ).estimate_cost_from_metadata(
                    prompt=prompt,
                    image_byte_lengths=[item.byte_length for item in source.image_reads],
                    response_schema=PaintPlanDocument.model_json_schema(),
                    max_output_tokens=4096,
                )
        except ProviderContractError:
            estimate_minor_units = None
            blockers.extend(("provider_request_invalid", "cost_estimate_unavailable"))
        if principal.user_id is None:
            blockers.append("authenticated_user_required")
        else:
            blockers.extend(
                await self._ai_service.live_saved_selection_blockers(
                    user_id=principal.user_id,
                    project_id=source.access.project.id,
                    provider_definition_id=payload.provider_definition_id,
                    model_definition_id=payload.model_definition_id,
                    credential_id=payload.credential_id,
                    required_capability_keys=[
                        "vision_understanding",
                        "structured_output",
                    ],
                    estimate_minor_units=(
                        0 if estimate_minor_units is None else estimate_minor_units
                    ),
                )
            )
        return estimate_minor_units, blockers

    def _prepared_live_images(
        self, source: PaintPlanSourceSnapshot
    ) -> tuple[PreparedImageAttachment, ...]:
        prepared: list[PreparedImageAttachment] = []
        for read in source.image_reads:
            asset = next(
                (
                    item
                    for item in source.image_set.current_by_role.values()
                    if item.id == read.id and item.role == read.role
                ),
                None,
            )
            if asset is None:
                raise PaintPlanSourceNotReadyError(["image_identity_changed"])
            stream = self._storage.open_private(asset.storage_key)
            try:
                content = stream.read(read.byte_length + 1)
            finally:
                stream.close()
            prepared.append(
                PreparedImageAttachment(
                    image_asset_id=str(read.id),
                    role=read.role,
                    sha256=read.sha256,
                    media_type=read.media_type,
                    width=read.width,
                    height=read.height,
                    content=content,
                )
            )
        for image in prepared:
            image.validate()
        return tuple(prepared)

    async def _generate_zhipu_live(
        self,
        *,
        source: PaintPlanSourceSnapshot,
        selection: PaintPlanGenerateRequest | PaintPlanRegenerateRequest,
        principal: PrincipalContext,
        idempotency_key: uuid.UUID,
        request_id: uuid.UUID,
        regeneration_of_plan_id: uuid.UUID | None,
    ) -> tuple[PaintPlanDocument, uuid.UUID, uuid.UUID, uuid.UUID, list[RetrievedContextUnit]]:
        if self._live_service is None:
            raise PaintPlanLiveExecutionBlockedError(["zhipu_live_service_unavailable"])
        fixture_source = self._fixture_source(
            source,
            generation_locale=selection.generation_locale,
            intent=selection.intent,
            regeneration_of_plan_id=regeneration_of_plan_id,
        )
        retrieval = self._knowledge.retrieve(locale=fixture_source.generation_locale)
        prompt = GovernedMultimodalPrompt(
            system_prompt=_zhipu_live_system_prompt(fixture_source),
            user_intent=fixture_source.intent,
            structured_context={
                "paint_plan_source": fixture_source.model_dump(
                    mode="json", exclude={"prompt_template_body", "intent"}
                ),
                "retrieved_context": retrieval.model_dump(mode="json"),
            },
            generation_locale=fixture_source.generation_locale,
        )
        images = self._prepared_live_images(source)
        adapter = ZhipuChatAdapter(ZHIPU_GLM_5V_TURBO_MODEL)
        request = adapter.prepare_request(
            prompt=prompt,
            images=images,
            response_schema=PaintPlanDocument.model_json_schema(),
            max_output_tokens=4_096,
            timeout_ms=60_000,
        )
        estimate = adapter.estimate_cost(
            prompt=prompt,
            images=images,
            response_schema=PaintPlanDocument.model_json_schema(),
            max_output_tokens=4_096,
        )
        async with self._session.begin():
            pricing = await self._repository.get_pricing(
                model_definition_id=selection.model_definition_id
            )
        if (
            pricing is None
            or pricing.provider_definition_id != selection.provider_definition_id
            or pricing.provider_key != "zhipu"
            or pricing.model_id != ZHIPU_GLM_5V_TURBO_MODEL
            or pricing.currency != "CNY"
            or pricing.input_minor_units_per_million != ZHIPU_GLM_5V_HIGH_INPUT_FEN_PER_MILLION
            or pricing.output_minor_units_per_million != ZHIPU_GLM_5V_HIGH_OUTPUT_FEN_PER_MILLION
        ):
            raise PaintPlanLiveExecutionBlockedError(["pricing_snapshot_invalid"])

        def validate_output(raw: Mapping[str, object]) -> dict[str, object]:
            return _validate_live_paint_plan_output(
                raw,
                regions=source.regions,
                retrieval=retrieval,
            )

        readiness_review = source.image_set.latest_readiness_review
        assert readiness_review is not None
        assert source.region_read is not None
        safe_input_snapshot = {
            "artifacts": [
                {
                    "id": str(item.id),
                    "revision": item.version,
                    "content_hash": f"sha256:{item.sha256}",
                    "media_type": item.media_type,
                    "byte_length": item.byte_length,
                }
                for item in source.image_reads
            ],
            "paint_plan_provenance": {
                "image_set_fingerprint": fixture_source.image_set_fingerprint,
                "image_assets": [
                    image.model_dump(mode="json") for image in fixture_source.image_assets
                ],
                "readiness_review_id": str(readiness_review.id),
                "readiness_review_version": readiness_review.version,
                "region_set_id": str(source.region_read.id),
                "region_set_version": source.region_read.version,
                "region_geometry_fingerprint": source.region_read.geometry_fingerprint,
                "prompt_template_id": str(fixture_source.prompt_template_id),
                "prompt_template_key": fixture_source.prompt_template_key,
                "prompt_template_version": fixture_source.prompt_template_version,
                "prompt_content_hash": fixture_source.prompt_content_hash,
                "generation_locale": fixture_source.generation_locale,
                "response_schema_version": fixture_source.response_schema_version,
            },
            "paint_plan_contract": {
                "paint_regions": [
                    {
                        "region_id": str(region.id),
                        "stable_region_key": str(region.stable_region_key),
                        "region_label": region.label,
                    }
                    for region in source.regions
                    if region.kind == "paint"
                ],
                "excluded_region_ids": [
                    str(region.id) for region in source.regions if region.kind == "exclude"
                ],
            },
        }
        try:
            result = await self._live_service.execute(
                selection=ZhipuLiveSelection(
                    product_space="paintpilot",
                    invocation_family="paint_plan_generation",
                    project_id=source.access.project.id,
                    provider_definition_id=selection.provider_definition_id,
                    model_definition_id=selection.model_definition_id,
                    credential_id=selection.credential_id,
                    required_capability_keys=(
                        "vision_understanding",
                        "structured_output",
                    ),
                    estimate_minor_units=estimate,
                    pricing_snapshot_id=pricing.id,
                ),
                principal=principal,
                request=request,
                retrieval=retrieval,
                output_validator=validate_output,
                idempotency_key=idempotency_key,
                request_id=request_id,
                safe_input_snapshot=safe_input_snapshot,
            )
        except (ProviderContractError, RuntimeError) as error:
            raise PaintPlanOutputInvalidError from error
        return (
            PaintPlanDocument.model_validate(result.output),
            result.invocation_id,
            result.attempt_id,
            result.pricing_snapshot_id,
            list(retrieval.units),
        )

    async def preview(
        self,
        *,
        project_id: uuid.UUID,
        payload: PaintPlanPreviewRequest,
        principal: PrincipalContext,
    ) -> PaintPlanPreviewRead:
        async with self._session.begin():
            source = await self._load_source(
                project_id=project_id,
                principal=principal,
                region_set_id=payload.region_set_id,
                expected_image_set_fingerprint=payload.image_set_fingerprint,
                for_update=False,
            )
            provider = await self._repository.get_provider(payload.provider_definition_id)
            model = await self._repository.get_model(payload.model_definition_id)
            provider_key = None if provider is None else provider.provider_key
            provider_enabled = False if provider is None else provider.enabled
            provider_status = None if provider is None else provider.status
            model_id = None if model is None else model.model_id
            model_provider_definition_id = None if model is None else model.provider_definition_id
            pricing = (
                None
                if model is None
                else await self._repository.get_pricing(model_definition_id=model.id)
            )
        blockers = list(source.blockers)
        if source.access.project.status == "ABANDONED":
            blockers.append("project_abandoned")
        if not source.access.is_owner:
            blockers.append("owner_required")
        if principal.user_id is None:
            blockers.append("authenticated_user_required")
        if (
            provider is None
            or model is None
            or model_provider_definition_id != payload.provider_definition_id
        ):
            blockers.append("provider_model_not_found")
            return PaintPlanPreviewRead(
                admissible=False,
                execution_mode="live_authorization_required",
                provider_key="openai",
                model_id="unavailable",
                source_ready=source.ready,
                estimated_cost_minor_units=None,
                currency="USD",
                estimate_status="unavailable",
                live_execution_authorized=False,
                blockers=list(dict.fromkeys(blockers)),
            )
        assert model_id is not None
        if provider_key == "openai":
            estimate_minor_units, admission_blockers = await self._live_selection_readiness(
                source=source,
                payload=payload,
                principal=principal,
                regeneration_of_plan_id=None,
                provider_key="openai",
            )
            blockers.extend(admission_blockers)
            if (
                pricing is None
                or pricing.provider_definition_id != payload.provider_definition_id
                or pricing.model_definition_id != payload.model_definition_id
                or pricing.provider_key != "openai"
                or pricing.model_id != model_id
                or pricing.currency != "USD"
                or pricing.unit_basis != "per_million_tokens"
                or pricing.input_minor_units_per_million != OPENAI_INPUT_CENTS_PER_MILLION
                or pricing.output_minor_units_per_million != OPENAI_OUTPUT_CENTS_PER_MILLION
            ):
                blockers.append("pricing_snapshot_invalid")
                estimate_minor_units = None
            blockers.append("live_execution_authorization_required")
            if not provider_enabled or provider_status != "active":
                blockers.append("provider_disabled")
            return PaintPlanPreviewRead(
                admissible=False,
                execution_mode="live_authorization_required",
                provider_key="openai",
                model_id=model_id,
                source_ready=source.ready,
                estimated_cost_minor_units=estimate_minor_units,
                currency="USD",
                estimate_status=("unavailable" if estimate_minor_units is None else "estimated"),
                live_execution_authorized=False,
                blockers=list(dict.fromkeys(blockers)),
            )
        if provider_key == "zhipu":
            estimate_minor_units, admission_blockers = await self._live_selection_readiness(
                source=source,
                payload=payload,
                principal=principal,
                regeneration_of_plan_id=None,
                provider_key="zhipu",
            )
            blockers.extend(admission_blockers)
            if (
                pricing is None
                or pricing.provider_definition_id != payload.provider_definition_id
                or pricing.model_definition_id != payload.model_definition_id
                or pricing.provider_key != "zhipu"
                or pricing.model_id != model_id
                or pricing.currency != "CNY"
                or pricing.unit_basis != "per_million_tokens"
                or pricing.input_minor_units_per_million != ZHIPU_GLM_5V_HIGH_INPUT_FEN_PER_MILLION
                or pricing.output_minor_units_per_million
                != ZHIPU_GLM_5V_HIGH_OUTPUT_FEN_PER_MILLION
            ):
                blockers.append("pricing_snapshot_invalid")
                estimate_minor_units = None
            if not self._settings.zhipu_live_enabled:
                blockers.append("live_execution_authorization_required")
            if not provider_enabled or provider_status != "active":
                blockers.append("provider_disabled")
            return PaintPlanPreviewRead(
                admissible=not blockers and self._settings.zhipu_live_enabled,
                execution_mode="live_authorization_required",
                provider_key="zhipu",
                model_id=model_id,
                source_ready=source.ready,
                estimated_cost_minor_units=estimate_minor_units,
                currency="CNY",
                estimate_status="unavailable" if estimate_minor_units is None else "estimated",
                live_execution_authorized=self._settings.zhipu_live_enabled,
                blockers=list(dict.fromkeys(blockers)),
            )
        if provider_key != FIXTURE_PROVIDER_KEY:
            blockers.append("provider_unsupported")
            return PaintPlanPreviewRead(
                admissible=False,
                execution_mode="live_authorization_required",
                provider_key="openai",
                model_id=model_id,
                source_ready=source.ready,
                estimated_cost_minor_units=None,
                currency="USD",
                estimate_status="unavailable",
                live_execution_authorized=False,
                blockers=list(dict.fromkeys(blockers)),
            )
        if blockers:
            return PaintPlanPreviewRead(
                admissible=False,
                execution_mode="fixture_available",
                provider_key="fixture_local",
                model_id=model_id,
                source_ready=source.ready,
                estimated_cost_minor_units=None,
                currency="FIXTURE_CREDITS",
                estimate_status="unavailable",
                live_execution_authorized=False,
                blockers=list(dict.fromkeys(blockers)),
            )
        try:
            preview = await self._ai_service.preview_paint_plan_invocation(
                payload=self._invocation_preview_request(
                    source=source,
                    payload=payload,
                    regeneration_of_plan_id=None,
                ),
                principal=principal,
            )
        except PaintProjectApplicationError as error:
            blockers.append(error.error_code.lower())
            return PaintPlanPreviewRead(
                admissible=False,
                execution_mode="fixture_available",
                provider_key="fixture_local",
                model_id=model_id,
                source_ready=True,
                estimated_cost_minor_units=None,
                currency="FIXTURE_CREDITS",
                estimate_status="unavailable",
                live_execution_authorized=False,
                blockers=blockers,
            )
        return PaintPlanPreviewRead(
            admissible=preview.admissible,
            execution_mode="fixture_available",
            provider_key="fixture_local",
            model_id=preview.model_id,
            source_ready=True,
            estimated_cost_minor_units=preview.estimated_cost_minor_units,
            currency=FIXTURE_CURRENCY,
            estimate_status="estimated",
            live_execution_authorized=False,
            blockers=[],
        )

    async def _persist_generated(
        self,
        *,
        project_id: uuid.UUID,
        principal: PrincipalContext,
        selection: PaintPlanGenerateRequest | PaintPlanRegenerateRequest,
        document: PaintPlanDocument,
        invocation_id: uuid.UUID,
        attempt_id: uuid.UUID,
        parent_plan_id: uuid.UUID | None,
        revision_kind: str,
        command: str,
        idempotency_key: uuid.UUID,
        identity: object,
        retrieved_context: list[RetrievedContextUnit] | None = None,
        provider_pricing_snapshot_id: uuid.UUID | None = None,
    ) -> PaintPlanRead:
        async with self._session.begin():
            source = await self._load_source(
                project_id=project_id,
                principal=principal,
                region_set_id=selection.region_set_id,
                expected_image_set_fingerprint=selection.image_set_fingerprint,
                for_update=True,
            )
            claim_id, replay = await self._claim_mutation(
                project_id=project_id,
                principal=principal,
                source=source,
                command=command,
                idempotency_key=idempotency_key,
                identity=identity,
            )
            if replay is not None:
                return replay
            existing = await self._repository.get_plan_by_invocation(
                source_invocation_id=invocation_id
            )
            if existing is not None:
                plan_reads = await self._plans_read(source=source)
                response = next(item for item in plan_reads if item.id == existing.id)
                assert claim_id is not None
                await self._repository.complete_command(
                    record_id=claim_id,
                    resource_id=existing.id,
                    response_snapshot=response.model_dump(mode="json"),
                )
                return response
            if not source.ready or source.region_set is None or source.prompt is None:
                raise PaintPlanSourceNotReadyError(source.blockers)
            _validate_document_regions(document, source.regions)
            plan_rows = await self._repository.list_plans(
                project_id=project_id,
                owner_principal_id=source.access.project.owner_principal_id,
                for_update=True,
            )
            current = next((item for item in plan_rows if item.lifecycle != "superseded"), None)
            parent = None
            if parent_plan_id is None:
                if current is not None:
                    raise PaintPlanLifecycleConflictError
            else:
                parent = next((item for item in plan_rows if item.id == parent_plan_id), None)
                if parent is None or current is None or current.id != parent.id:
                    raise PaintPlanLifecycleConflictError
                parent.lifecycle = "superseded"
                await self._repository.flush()
            provider = await self._repository.get_provider(selection.provider_definition_id)
            model = await self._repository.get_model(selection.model_definition_id)
            if (
                provider is None
                or model is None
                or provider.provider_key not in {FIXTURE_PROVIDER_KEY, "zhipu"}
                or model.provider_definition_id != provider.id
            ):
                raise PaintPlanLifecycleConflictError
            now = datetime.now(UTC)
            plan_id = uuid.uuid4()
            readiness_review = source.image_set.latest_readiness_review
            assert readiness_review is not None
            plan = PaintPlan(
                id=plan_id,
                owner_principal_id=source.access.project.owner_principal_id,
                paint_project_id=project_id,
                lineage_id=plan_id,
                version=await self._repository.next_project_version(project_id=project_id),
                lineage_revision=1,
                revision_kind=revision_kind,
                lifecycle="generated",
                parent_plan_id=None if parent is None else parent.id,
                source_readiness_review_id=readiness_review.id,
                source_readiness_review_version=readiness_review.version,
                source_image_set_fingerprint=source.image_set.fingerprint,
                source_region_set_id=source.region_set.id,
                source_region_set_version=source.region_set.version,
                source_geometry_fingerprint=source.region_set.geometry_fingerprint,
                source_invocation_id=invocation_id,
                source_attempt_id=attempt_id,
                provider_definition_id=provider.id,
                provider_key_snapshot=provider.provider_key,
                provider_revision_snapshot=provider.revision,
                model_definition_id=model.id,
                model_id_snapshot=model.model_id,
                model_revision_snapshot=model.revision,
                provider_pricing_snapshot_id=provider_pricing_snapshot_id,
                prompt_template_definition_id=source.prompt.id,
                prompt_template_key_snapshot=source.prompt.template_key,
                prompt_template_version_snapshot=source.prompt.version,
                prompt_content_hash=source.prompt.content_hash,
                response_schema_version=PAINT_PLAN_SCHEMA_VERSION,
                title=document.title,
                overall_approach=document.overall_approach,
                safety_notes=document.safety_notes,
                retrieved_context_snapshot=[
                    item.model_dump(mode="json") for item in (retrieved_context or [])
                ],
                citation_snapshot=[
                    item.model_dump(mode="json") for item in document.knowledge_citations
                ],
                instruction_count=len(document.instructions),
                content_hash=_content_hash(document),
                created_by_actor_type="provider",
                created_by_actor_id=provider.provider_key,
                created_by_actor_display_name_snapshot=provider.display_name,
                created_at=now,
            )
            instructions = [
                PaintPlanRegionInstruction(
                    id=uuid.uuid4(),
                    paint_plan_id=plan_id,
                    region_set_id=source.region_set.id,
                    region_id=item.region_id,
                    stable_region_key=item.stable_region_key,
                    region_label_snapshot=item.region_label,
                    region_kind_snapshot="paint",
                    sequence=index,
                    target_color=item.target_color,
                    preparation=item.preparation,
                    base_coat=item.base_coat,
                    layer_strategy=item.layer_strategy,
                    edge_treatment=item.edge_treatment,
                    lighting_guidance=item.lighting_guidance,
                    material_guidance=item.material_guidance,
                    warnings=item.warnings,
                    confidence_ppm=item.confidence_ppm,
                    created_at=now,
                )
                for index, item in enumerate(document.instructions)
            ]
            await self._repository.add_plan(plan=plan, instructions=instructions)
            response = await self._plan_read(
                plan,
                source=source,
                current_plan_id=plan.id,
                latest_review=None,
            )
            assert claim_id is not None
            await self._repository.complete_command(
                record_id=claim_id,
                resource_id=plan.id,
                response_snapshot=response.model_dump(mode="json"),
            )
            return response

    async def generate(
        self,
        *,
        project_id: uuid.UUID,
        payload: PaintPlanGenerateRequest,
        principal: PrincipalContext,
        idempotency_key: uuid.UUID,
        request_id: uuid.UUID,
    ) -> PaintPlanRead:
        identity = payload.model_dump(mode="json")
        async with self._session.begin():
            replay_access = await self._resolve_access(
                project_id=project_id,
                principal=principal,
                for_update=False,
            )
            if (
                not replay_access.is_owner
                or principal.user_id is None
                or replay_access.project.status == "ABANDONED"
            ):
                raise PaintProjectNotFoundError
            replay = await self._completed_mutation_replay(
                project_id=project_id,
                principal=principal,
                command="generate_paint_plan",
                idempotency_key=idempotency_key,
                identity=identity,
            )
            if replay is not None:
                return replay
            source = await self._load_source(
                project_id=project_id,
                principal=principal,
                region_set_id=payload.region_set_id,
                expected_image_set_fingerprint=payload.image_set_fingerprint,
                for_update=False,
            )
            provider = await self._repository.get_provider(payload.provider_definition_id)
        if (
            not source.access.is_owner
            or principal.user_id is None
            or source.access.project.status == "ABANDONED"
        ):
            raise PaintProjectNotFoundError
        if not source.ready:
            raise PaintPlanSourceNotReadyError(source.blockers)
        if provider is None:
            raise PaintPlanLifecycleConflictError
        if provider.provider_key == "zhipu":
            (
                document,
                invocation_id,
                attempt_id,
                pricing_id,
                retrieved_context,
            ) = await self._generate_zhipu_live(
                source=source,
                selection=payload,
                principal=principal,
                idempotency_key=idempotency_key,
                request_id=request_id,
                regeneration_of_plan_id=None,
            )
            return await self._persist_generated(
                project_id=project_id,
                principal=principal,
                selection=payload,
                document=document,
                invocation_id=invocation_id,
                attempt_id=attempt_id,
                parent_plan_id=None,
                revision_kind="generated",
                command="generate_paint_plan",
                idempotency_key=idempotency_key,
                identity=identity,
                retrieved_context=retrieved_context,
                provider_pricing_snapshot_id=pricing_id,
            )
        if provider.provider_key != FIXTURE_PROVIDER_KEY:
            blockers: list[str] = ["live_execution_authorization_required"]
            if provider.provider_key == "openai":
                _, readiness_blockers = await self._live_selection_readiness(
                    source=source,
                    payload=payload,
                    principal=principal,
                    regeneration_of_plan_id=None,
                    provider_key="openai",
                )
                blockers.extend(readiness_blockers)
                if not provider.enabled or provider.status != "active":
                    blockers.append("provider_disabled")
            else:
                blockers.append("provider_unsupported")
            try:
                assert_live_provider_execution_authorized()
            except RuntimeError as error:
                raise PaintPlanLiveExecutionBlockedError(blockers) from error
            raise PaintPlanLiveExecutionBlockedError(blockers)
        preview_request = self._invocation_preview_request(
            source=source,
            payload=payload,
            regeneration_of_plan_id=None,
        )
        invocation = await self._ai_service.create_paint_plan_invocation(
            payload=InvocationCreateRequest(
                **preview_request.model_dump(mode="python"),
                max_attempts=payload.max_attempts,
                total_elapsed_time_limit_ms=30_000,
            ),
            principal=principal,
            idempotency_key=idempotency_key,
            request_id=request_id,
        )
        if invocation.output is None or invocation.final_attempt_id is None:
            raise PaintPlanOutputInvalidError
        try:
            document = PaintPlanDocument.model_validate(invocation.output)
            _validate_document_regions(document, source.regions)
        except (ValidationError, PaintPlanOutputInvalidError) as error:
            raise PaintPlanOutputInvalidError from error
        return await self._persist_generated(
            project_id=project_id,
            principal=principal,
            selection=payload,
            document=document,
            invocation_id=invocation.id,
            attempt_id=invocation.final_attempt_id,
            parent_plan_id=None,
            revision_kind="generated",
            command="generate_paint_plan",
            idempotency_key=idempotency_key,
            identity=identity,
        )

    async def regenerate(
        self,
        *,
        project_id: uuid.UUID,
        plan_id: uuid.UUID,
        payload: PaintPlanRegenerateRequest,
        principal: PrincipalContext,
        idempotency_key: uuid.UUID,
        request_id: uuid.UUID,
    ) -> PaintPlanRead:
        if payload.expected_current_plan_id != plan_id:
            raise PaintPlanLifecycleConflictError
        identity = payload.model_dump(mode="json")
        async with self._session.begin():
            replay_access = await self._resolve_access(
                project_id=project_id,
                principal=principal,
                for_update=False,
            )
            if (
                not replay_access.is_owner
                or principal.user_id is None
                or replay_access.project.status == "ABANDONED"
            ):
                raise PaintProjectNotFoundError
            replay = await self._completed_mutation_replay(
                project_id=project_id,
                principal=principal,
                command="regenerate_paint_plan",
                idempotency_key=idempotency_key,
                identity=identity,
            )
            if replay is not None:
                return replay
            source = await self._load_source(
                project_id=project_id,
                principal=principal,
                region_set_id=payload.region_set_id,
                expected_image_set_fingerprint=payload.image_set_fingerprint,
                for_update=False,
            )
            current = await self._repository.get_plan(
                project_id=project_id,
                owner_principal_id=source.access.project.owner_principal_id,
                plan_id=plan_id,
            )
            provider = await self._repository.get_provider(payload.provider_definition_id)
        if (
            not source.access.is_owner
            or principal.user_id is None
            or source.access.project.status == "ABANDONED"
            or current is None
            or current.version != payload.expected_current_version
            or current.lifecycle == "superseded"
        ):
            raise PaintPlanLifecycleConflictError
        if not source.ready:
            raise PaintPlanSourceNotReadyError(source.blockers)
        if provider is not None and provider.provider_key == "zhipu":
            (
                document,
                invocation_id,
                attempt_id,
                pricing_id,
                retrieved_context,
            ) = await self._generate_zhipu_live(
                source=source,
                selection=payload,
                principal=principal,
                idempotency_key=idempotency_key,
                request_id=request_id,
                regeneration_of_plan_id=plan_id,
            )
            return await self._persist_generated(
                project_id=project_id,
                principal=principal,
                selection=payload,
                document=document,
                invocation_id=invocation_id,
                attempt_id=attempt_id,
                parent_plan_id=plan_id,
                revision_kind="regenerated",
                command="regenerate_paint_plan",
                idempotency_key=idempotency_key,
                identity=identity,
                retrieved_context=retrieved_context,
                provider_pricing_snapshot_id=pricing_id,
            )
        if provider is None or provider.provider_key != FIXTURE_PROVIDER_KEY:
            blockers: list[str] = ["live_execution_authorization_required"]
            if provider is not None and provider.provider_key == "openai":
                _, readiness_blockers = await self._live_selection_readiness(
                    source=source,
                    payload=payload,
                    principal=principal,
                    regeneration_of_plan_id=plan_id,
                    provider_key="openai",
                )
                blockers.extend(readiness_blockers)
                if not provider.enabled or provider.status != "active":
                    blockers.append("provider_disabled")
            elif provider is None:
                blockers.append("provider_model_not_found")
            else:
                blockers.append("provider_unsupported")
            try:
                assert_live_provider_execution_authorized()
            except RuntimeError as error:
                raise PaintPlanLiveExecutionBlockedError(blockers) from error
            raise PaintPlanLiveExecutionBlockedError(blockers)
        preview_request = self._invocation_preview_request(
            source=source,
            payload=payload,
            regeneration_of_plan_id=plan_id,
        )
        invocation = await self._ai_service.create_paint_plan_invocation(
            payload=InvocationCreateRequest(
                **preview_request.model_dump(mode="python"),
                max_attempts=payload.max_attempts,
                total_elapsed_time_limit_ms=30_000,
            ),
            principal=principal,
            idempotency_key=idempotency_key,
            request_id=request_id,
        )
        if invocation.output is None or invocation.final_attempt_id is None:
            raise PaintPlanOutputInvalidError
        try:
            document = PaintPlanDocument.model_validate(invocation.output)
            _validate_document_regions(document, source.regions)
        except (ValidationError, PaintPlanOutputInvalidError) as error:
            raise PaintPlanOutputInvalidError from error
        return await self._persist_generated(
            project_id=project_id,
            principal=principal,
            selection=payload,
            document=document,
            invocation_id=invocation.id,
            attempt_id=invocation.final_attempt_id,
            parent_plan_id=plan_id,
            revision_kind="regenerated",
            command="regenerate_paint_plan",
            idempotency_key=idempotency_key,
            identity=identity,
        )

    @staticmethod
    def _command_replay_resource_id(
        existing: CommandIdempotencyRecord,
        *,
        identity: object,
    ) -> uuid.UUID:
        if existing.payload_hash != _payload_hash(identity):
            raise PaintPlanIdempotencyConflictError
        if (
            existing.execution_status != IDEMPOTENCY_STATUS_COMPLETED
            or existing.resource_type != "paint_plan"
            or existing.resource_id is None
            or existing.http_status != 201
            or existing.response_snapshot is None
        ):
            raise PaintPlanLifecycleConflictError
        try:
            encoded = json.dumps(
                existing.response_snapshot,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            snapshot = PaintPlanRead.model_validate_json(encoded)
        except (TypeError, ValueError, ValidationError) as error:
            raise PaintPlanLifecycleConflictError from error
        if snapshot.id != existing.resource_id:
            raise PaintPlanLifecycleConflictError
        return existing.resource_id

    async def _replayed_plan_read(
        self,
        existing: CommandIdempotencyRecord,
        *,
        identity: object,
        source: PaintPlanSourceSnapshot,
    ) -> PaintPlanRead:
        resource_id = self._command_replay_resource_id(existing, identity=identity)
        plan_reads = await self._plans_read(source=source)
        replay = next((item for item in plan_reads if item.id == resource_id), None)
        if replay is None:
            raise PaintPlanLifecycleConflictError
        return replay

    async def _completed_mutation_replay(
        self,
        *,
        project_id: uuid.UUID,
        principal: PrincipalContext,
        command: str,
        idempotency_key: uuid.UUID,
        identity: object,
    ) -> PaintPlanRead | None:
        existing = await self._repository.get_command(
            scope_key=_scope_key(principal.principal_id, project_id, command),
            idempotency_key=idempotency_key,
        )
        if existing is None:
            return None
        source = await self._load_source(
            project_id=project_id,
            principal=principal,
            region_set_id=None,
            expected_image_set_fingerprint=None,
            for_update=False,
        )
        return await self._replayed_plan_read(
            existing,
            identity=identity,
            source=source,
        )

    async def _claim_mutation(
        self,
        *,
        project_id: uuid.UUID,
        principal: PrincipalContext,
        source: PaintPlanSourceSnapshot,
        command: str,
        idempotency_key: uuid.UUID,
        identity: object,
    ) -> tuple[uuid.UUID | None, PaintPlanRead | None]:
        now = datetime.now(UTC)
        claim = await self._repository.claim_command(
            record_id=uuid.uuid4(),
            scope_key=_scope_key(principal.principal_id, project_id, command),
            principal_id=principal.principal_id,
            command_type=command,
            idempotency_key=idempotency_key,
            payload_hash=_payload_hash(identity),
            created_at=now,
            expires_at=now + IDEMPOTENCY_RETENTION,
        )
        if claim.acquired_record_id is not None:
            return claim.acquired_record_id, None
        assert claim.existing_record is not None
        return None, await self._replayed_plan_read(
            claim.existing_record,
            identity=identity,
            source=source,
        )

    async def edit(
        self,
        *,
        project_id: uuid.UUID,
        plan_id: uuid.UUID,
        payload: PaintPlanEditRequest,
        principal: PrincipalContext,
        idempotency_key: uuid.UUID,
    ) -> PaintPlanRead:
        if payload.expected_current_plan_id != plan_id:
            raise PaintPlanLifecycleConflictError
        identity = payload.model_dump(mode="json")
        async with self._session.begin():
            source = await self._load_source(
                project_id=project_id,
                principal=principal,
                region_set_id=None,
                expected_image_set_fingerprint=None,
                for_update=True,
            )
            if not source.access.is_owner:
                raise PaintProjectNotFoundError
            if source.access.project.status == "ABANDONED":
                raise PaintPlanLifecycleConflictError
            claim_id, replay = await self._claim_mutation(
                project_id=project_id,
                principal=principal,
                source=source,
                command="edit_paint_plan",
                idempotency_key=idempotency_key,
                identity=identity,
            )
            if replay is not None:
                return replay
            current = await self._repository.get_plan(
                project_id=project_id,
                owner_principal_id=source.access.project.owner_principal_id,
                plan_id=plan_id,
                for_update=True,
            )
            if (
                current is None
                or current.version != payload.expected_current_version
                or current.lifecycle == "superseded"
                or self._plan_stale_reasons(current, source)
            ):
                raise PaintPlanLifecycleConflictError
            _validate_document_regions(payload.document, source.regions)
            _validate_edit_citations(payload.document, current.retrieved_context_snapshot)
            current.lifecycle = "superseded"
            await self._repository.flush()
            now = datetime.now(UTC)
            new_id = uuid.uuid4()
            edited = PaintPlan(
                id=new_id,
                owner_principal_id=current.owner_principal_id,
                paint_project_id=current.paint_project_id,
                lineage_id=current.lineage_id,
                version=await self._repository.next_project_version(project_id=project_id),
                lineage_revision=current.lineage_revision + 1,
                revision_kind="edited",
                lifecycle="edited",
                parent_plan_id=current.id,
                source_readiness_review_id=current.source_readiness_review_id,
                source_readiness_review_version=current.source_readiness_review_version,
                source_image_set_fingerprint=current.source_image_set_fingerprint,
                source_region_set_id=current.source_region_set_id,
                source_region_set_version=current.source_region_set_version,
                source_geometry_fingerprint=current.source_geometry_fingerprint,
                source_invocation_id=current.source_invocation_id,
                source_attempt_id=current.source_attempt_id,
                provider_definition_id=current.provider_definition_id,
                provider_key_snapshot=current.provider_key_snapshot,
                provider_revision_snapshot=current.provider_revision_snapshot,
                model_definition_id=current.model_definition_id,
                model_id_snapshot=current.model_id_snapshot,
                model_revision_snapshot=current.model_revision_snapshot,
                provider_pricing_snapshot_id=current.provider_pricing_snapshot_id,
                prompt_template_definition_id=current.prompt_template_definition_id,
                prompt_template_key_snapshot=current.prompt_template_key_snapshot,
                prompt_template_version_snapshot=current.prompt_template_version_snapshot,
                prompt_content_hash=current.prompt_content_hash,
                response_schema_version=current.response_schema_version,
                title=payload.document.title,
                overall_approach=payload.document.overall_approach,
                safety_notes=payload.document.safety_notes,
                retrieved_context_snapshot=list(current.retrieved_context_snapshot),
                citation_snapshot=[
                    item.model_dump(mode="json") for item in payload.document.knowledge_citations
                ],
                instruction_count=len(payload.document.instructions),
                content_hash=_content_hash(payload.document),
                created_by_actor_type="user",
                created_by_actor_id=principal.principal_id,
                created_by_actor_display_name_snapshot=principal.display_name,
                created_at=now,
            )
            instructions = [
                PaintPlanRegionInstruction(
                    id=uuid.uuid4(),
                    paint_plan_id=new_id,
                    region_set_id=current.source_region_set_id,
                    region_id=item.region_id,
                    stable_region_key=item.stable_region_key,
                    region_label_snapshot=item.region_label,
                    region_kind_snapshot="paint",
                    sequence=index,
                    target_color=item.target_color,
                    preparation=item.preparation,
                    base_coat=item.base_coat,
                    layer_strategy=item.layer_strategy,
                    edge_treatment=item.edge_treatment,
                    lighting_guidance=item.lighting_guidance,
                    material_guidance=item.material_guidance,
                    warnings=item.warnings,
                    confidence_ppm=item.confidence_ppm,
                    created_at=now,
                )
                for index, item in enumerate(payload.document.instructions)
            ]
            await self._repository.add_plan(plan=edited, instructions=instructions)
            response = await self._plan_read(
                edited,
                source=source,
                current_plan_id=edited.id,
                latest_review=None,
            )
            assert claim_id is not None
            await self._repository.complete_command(
                record_id=claim_id,
                resource_id=edited.id,
                response_snapshot=response.model_dump(mode="json"),
            )
            return response

    async def _transition(
        self,
        *,
        project_id: uuid.UUID,
        plan_id: uuid.UUID,
        payload: PaintPlanRevisionRequest | PaintPlanReviewRequest,
        principal: PrincipalContext,
        idempotency_key: uuid.UUID,
        action: str,
    ) -> PaintPlanRead:
        if payload.expected_current_plan_id != plan_id:
            raise PaintPlanLifecycleConflictError
        reason = payload.reason if isinstance(payload, PaintPlanReviewRequest) else None
        if action == "reject" and reason is None:
            raise PaintPlanLifecycleConflictError
        identity = {**payload.model_dump(mode="json"), "action": action}
        async with self._session.begin():
            source = await self._load_source(
                project_id=project_id,
                principal=principal,
                region_set_id=None,
                expected_image_set_fingerprint=None,
                for_update=True,
            )
            owner_command = action == "submit"
            if owner_command != source.access.is_owner:
                raise PaintProjectNotFoundError
            if source.access.project.status == "ABANDONED":
                raise PaintPlanLifecycleConflictError
            claim_id, replay = await self._claim_mutation(
                project_id=project_id,
                principal=principal,
                source=source,
                command=f"{action}_paint_plan",
                idempotency_key=idempotency_key,
                identity=identity,
            )
            if replay is not None:
                return replay
            plan = await self._repository.get_plan(
                project_id=project_id,
                owner_principal_id=source.access.project.owner_principal_id,
                plan_id=plan_id,
                for_update=True,
            )
            if (
                plan is None
                or plan.version != payload.expected_current_version
                or plan.lifecycle == "superseded"
                or self._plan_stale_reasons(plan, source)
            ):
                raise PaintPlanLifecycleConflictError
            allowed_lifecycles = {"generated", "edited"} if action == "submit" else {"under_review"}
            if plan.lifecycle not in allowed_lifecycles:
                raise PaintPlanLifecycleConflictError
            plan.lifecycle = {
                "submit": "under_review",
                "approve": "approved",
                "reject": "rejected",
            }[action]
            review = PaintPlanReviewEvent(
                id=uuid.uuid4(),
                owner_principal_id=plan.owner_principal_id,
                paint_project_id=project_id,
                paint_plan_id=plan.id,
                paint_plan_version=plan.version,
                action=action,
                actor_user_id=principal.user_id,
                actor_principal_id=principal.principal_id,
                actor_display_name_snapshot=principal.display_name,
                reason=reason,
                created_at=datetime.now(UTC),
            )
            self._repository.add_review(review)
            await self._repository.flush()
            response = await self._plan_read(
                plan,
                source=source,
                current_plan_id=plan.id,
                latest_review=review,
            )
            assert claim_id is not None
            await self._repository.complete_command(
                record_id=claim_id,
                resource_id=plan.id,
                response_snapshot=response.model_dump(mode="json"),
            )
            return response

    async def submit(
        self,
        *,
        project_id: uuid.UUID,
        plan_id: uuid.UUID,
        payload: PaintPlanRevisionRequest,
        principal: PrincipalContext,
        idempotency_key: uuid.UUID,
    ) -> PaintPlanRead:
        return await self._transition(
            project_id=project_id,
            plan_id=plan_id,
            payload=payload,
            principal=principal,
            idempotency_key=idempotency_key,
            action="submit",
        )

    async def approve(
        self,
        *,
        project_id: uuid.UUID,
        plan_id: uuid.UUID,
        payload: PaintPlanReviewRequest,
        principal: PrincipalContext,
        idempotency_key: uuid.UUID,
    ) -> PaintPlanRead:
        return await self._transition(
            project_id=project_id,
            plan_id=plan_id,
            payload=payload,
            principal=principal,
            idempotency_key=idempotency_key,
            action="approve",
        )

    async def reject(
        self,
        *,
        project_id: uuid.UUID,
        plan_id: uuid.UUID,
        payload: PaintPlanReviewRequest,
        principal: PrincipalContext,
        idempotency_key: uuid.UUID,
    ) -> PaintPlanRead:
        return await self._transition(
            project_id=project_id,
            plan_id=plan_id,
            payload=payload,
            principal=principal,
            idempotency_key=idempotency_key,
            action="reject",
        )

    async def list_history(
        self,
        *,
        project_id: uuid.UUID,
        principal: PrincipalContext,
    ) -> PaintPlanHistoryResponse:
        async with self._session.begin():
            source = await self._load_source(
                project_id=project_id,
                principal=principal,
                region_set_id=None,
                expected_image_set_fingerprint=None,
                for_update=False,
            )
            plans = await self._plans_read(source=source)
        return PaintPlanHistoryResponse(items=plans)

    async def get_plan(
        self,
        *,
        project_id: uuid.UUID,
        plan_id: uuid.UUID,
        principal: PrincipalContext,
    ) -> PaintPlanRead:
        history = await self.list_history(project_id=project_id, principal=principal)
        plan = next((item for item in history.items if item.id == plan_id), None)
        if plan is None:
            raise PaintPlanNotFoundError
        return plan
