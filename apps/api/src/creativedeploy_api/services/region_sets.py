"""Phase 1F human RegionSet lifecycle, idempotency, and stale boundary."""

import hashlib
import json
import logging
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from types import MappingProxyType

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from creativedeploy_api.core.config import MAX_DATABASE_TRANSACTION_TIMEOUT_MS, Settings
from creativedeploy_api.core.principal import PrincipalContext, PrincipalType
from creativedeploy_api.db.models import (
    CommandIdempotencyRecord,
    ImageAsset,
    ImageSetReadinessReview,
    Region,
    RegionSet,
    RegionSetReview,
    RegionVertex,
)
from creativedeploy_api.db.models.constants import IDEMPOTENCY_STATUS_COMPLETED
from creativedeploy_api.db.models.image_asset import (
    IMAGE_ROLE_PRIMARY,
    REQUIRED_IMAGE_ROLES,
)
from creativedeploy_api.repositories.identity import SqlAlchemyIdentityRepository
from creativedeploy_api.repositories.region_sets import SqlAlchemyRegionSetRepository
from creativedeploy_api.schemas.errors import ErrorCategory
from creativedeploy_api.schemas.region_sets import (
    CreateRegionSetReviewRequest,
    ForkRegionSetDraftRequest,
    RegionDraftInput,
    RegionRead,
    RegionSetHistoryItem,
    RegionSetHistoryResponse,
    RegionSetRead,
    RegionSetReviewHistoryResponse,
    RegionSetReviewRead,
    RegionVertexInput,
    RegionVertexRead,
    RegionWorkbenchRead,
    SaveRegionSetRequest,
)
from creativedeploy_api.services.image_assets import image_set_fingerprint
from creativedeploy_api.services.paint_projects import (
    IDEMPOTENCY_RETENTION,
    PaintProjectApplicationError,
    PaintProjectNotFoundError,
    StoredIdempotencyResultInvalidError,
)
from creativedeploy_api.services.region_geometry import (
    RegionGeometryValidationError,
    ValidatedRegionSnapshot,
    geometry_fingerprint,
    validate_region_snapshot,
)
from creativedeploy_api.storage.images import ImageStorageError, ImageStoragePort

logger = logging.getLogger(__name__)

SAVE_COMMAND = "save_region_set"
FORK_DRAFT_COMMAND = "fork_region_set_draft"
SUBMIT_COMMAND = "submit_region_set"
REVIEW_COMMAND = "review_region_set"
SAVE_PAYLOAD_VERSION = "paintpilot_save_region_set.v1"
FORK_DRAFT_PAYLOAD_VERSION = "paintpilot_fork_region_set_draft.v1"
SUBMIT_PAYLOAD_VERSION = "paintpilot_submit_region_set.v1"
REVIEW_PAYLOAD_VERSION = "paintpilot_review_region_set.v1"


class RegionSetNotFoundError(PaintProjectApplicationError):
    """A RegionSet is missing or inaccessible within the owner predicate."""

    status_code = 404
    error_code = "REGION_SET_NOT_FOUND"
    category: ErrorCategory = "NOT_FOUND"
    message = "The region set was not found."
    allowed_actions = ("reload_region_history",)


class RegionSetActorNotAllowedError(PaintProjectApplicationError):
    """Only the configured human Principal can author or review annotations."""

    status_code = 403
    error_code = "ACTOR_NOT_AUTHORIZED"
    category: ErrorCategory = "CONFLICT"
    message = "The current Principal cannot perform a human RegionSet command."


class RegionSetIdempotencyKeyReusedError(PaintProjectApplicationError):
    """A RegionSet command key was reused with changed input."""

    status_code = 409
    error_code = "IDEMPOTENCY_KEY_REUSED"
    category: ErrorCategory = "IDEMPOTENCY_KEY_REUSED"
    message = "The Idempotency-Key was already used with different RegionSet data."
    allowed_actions = (
        "retry_with_original_payload",
        "start_new_command_with_new_idempotency_key",
    )


class RegionSetStaleVersionError(PaintProjectApplicationError):
    """An optimistic base is no longer the current editable snapshot."""

    status_code = 409
    error_code = "REGION_SET_STALE_VERSION"
    category: ErrorCategory = "CONFLICT"
    message = "A newer RegionSet snapshot exists."
    allowed_actions = ("reload_region_workbench", "reapply_edits")


class RegionSetLifecycleConflictError(PaintProjectApplicationError):
    """The requested command is not valid for the effective lifecycle."""

    status_code = 409
    error_code = "REGION_SET_LIFECYCLE_CONFLICT"
    category: ErrorCategory = "CONFLICT"
    message = "The RegionSet is not in a lifecycle state that permits this command."
    allowed_actions = ("reload_region_workbench",)


class RegionImageSetNotReadyError(PaintProjectApplicationError):
    """The current source ImageSet is not an exact human READY snapshot."""

    status_code = 409
    error_code = "REGION_IMAGE_SET_NOT_READY"
    category: ErrorCategory = "CONFLICT"
    message = "The current image set is not ready for human region annotation."
    allowed_actions = ("complete_image_set_readiness", "reload_region_workbench")


class RegionSetStaleSourceError(PaintProjectApplicationError):
    """The command targets a snapshot whose source no longer matches."""

    status_code = 409
    error_code = "REGION_SET_STALE"
    category: ErrorCategory = "CONFLICT"
    message = "The RegionSet source image snapshot is stale."
    allowed_actions = ("reload_region_workbench", "create_new_draft")


class RegionSetSubmitValidationError(PaintProjectApplicationError):
    """A draft is structurally valid to save but not complete enough to submit."""

    status_code = 422
    error_code = "REGION_SET_SUBMISSION_INVALID"
    category: ErrorCategory = "VALIDATION_ERROR"
    message = "The RegionSet does not meet the submission requirements."
    allowed_actions = ("edit_regions",)


class RegionGeometryApplicationError(PaintProjectApplicationError):
    """Map deterministic geometry failures without exposing internals."""

    status_code = 422
    error_code = "REGION_GEOMETRY_INVALID"
    category: ErrorCategory = "VALIDATION_ERROR"
    message = "One or more Region polygons are invalid."
    allowed_actions = ("edit_regions",)

    def __init__(self, error: RegionGeometryValidationError) -> None:
        super().__init__()
        details: dict[str, object] = {"geometry_code": error.code}
        if error.stable_region_key is not None:
            details["stable_region_key"] = str(error.stable_region_key)
        self.safe_details: Mapping[str, object] = MappingProxyType(details)


@dataclass(frozen=True, slots=True)
class CurrentImageSet:
    """Current server-owned source facts used for stale and READY checks."""

    fingerprint: str
    status: str
    current_by_role: dict[str, ImageAsset]

    @property
    def primary(self) -> ImageAsset | None:
        return self.current_by_role.get(IMAGE_ROLE_PRIMARY)


def _content_url(project_id: uuid.UUID, image_asset_id: uuid.UUID) -> str:
    return f"/api/v1/paint-projects/{project_id}/images/{image_asset_id}/content"


def _scope_key(principal_id: str, project_id: uuid.UUID, command_type: str) -> str:
    return f"principal:{principal_id}:project:{project_id}:command:{command_type}"


def _hash_canonical(value: dict[str, object]) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _canonical_regions(snapshot: ValidatedRegionSnapshot) -> list[dict[str, object]]:
    return [
        {
            "kind": item.source.kind,
            "label": item.source.label,
            "normalized_label": item.normalized_label,
            "notes": item.source.notes,
            "opacity_ppm": item.source.opacity_ppm,
            "stable_region_key": str(item.source.stable_region_key),
            "vertices": [
                {"x_ppm": vertex.x_ppm, "y_ppm": vertex.y_ppm} for vertex in item.source.vertices
            ],
            "z_index": item.source.z_index,
        }
        for item in snapshot.regions
    ]


def save_payload_hash(
    *,
    payload: SaveRegionSetRequest,
    snapshot: ValidatedRegionSnapshot,
) -> str:
    return _hash_canonical(
        {
            "base_region_set_id": (
                None if payload.base_region_set_id is None else str(payload.base_region_set_id)
            ),
            "base_version": payload.base_version,
            "regions": _canonical_regions(snapshot),
            "version": SAVE_PAYLOAD_VERSION,
        }
    )


def fork_draft_payload_hash(
    *,
    source_region_set_id: uuid.UUID,
    payload: ForkRegionSetDraftRequest,
) -> str:
    return _hash_canonical(
        {
            "expected_current_region_set_id": str(payload.expected_current_region_set_id),
            "expected_current_version": payload.expected_current_version,
            "source_region_set_id": str(source_region_set_id),
            "version": FORK_DRAFT_PAYLOAD_VERSION,
        }
    )


def submit_payload_hash(region_set: RegionSet) -> str:
    return _hash_canonical(
        {
            "geometry_fingerprint": region_set.geometry_fingerprint,
            "region_set_id": str(region_set.id),
            "version": SUBMIT_PAYLOAD_VERSION,
        }
    )


def review_payload_hash(
    region_set: RegionSet,
    payload: CreateRegionSetReviewRequest,
) -> str:
    return _hash_canonical(
        {
            "geometry_fingerprint": region_set.geometry_fingerprint,
            "reason": payload.reason,
            "region_set_id": str(region_set.id),
            "verdict": payload.verdict,
            "version": REVIEW_PAYLOAD_VERSION,
        }
    )


def _review_read(review: RegionSetReview) -> RegionSetReviewRead:
    return RegionSetReviewRead.model_validate(
        {
            "id": review.id,
            "paint_project_id": review.paint_project_id,
            "region_set_id": review.region_set_id,
            "version": review.version,
            "verdict": review.verdict,
            "reason": review.reason,
            "actor_type": review.actor_type,
            "actor_id": review.actor_id,
            "actor_display_name_snapshot": review.actor_display_name_snapshot,
            "created_at": review.created_at,
        }
    )


def _stored_region_set_read(record: CommandIdempotencyRecord) -> RegionSetRead:
    if (
        record.execution_status != IDEMPOTENCY_STATUS_COMPLETED
        or record.resource_type != "region_set"
        or record.http_status != 201
        or record.response_snapshot is None
    ):
        raise StoredIdempotencyResultInvalidError
    try:
        encoded = json.dumps(
            record.response_snapshot,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return RegionSetRead.model_validate_json(encoded)
    except (TypeError, ValueError, ValidationError) as error:
        raise StoredIdempotencyResultInvalidError from error


def _stored_review_read(record: CommandIdempotencyRecord) -> RegionSetReviewRead:
    if (
        record.execution_status != IDEMPOTENCY_STATUS_COMPLETED
        or record.resource_type != "region_set_review"
        or record.http_status != 201
        or record.response_snapshot is None
    ):
        raise StoredIdempotencyResultInvalidError
    try:
        encoded = json.dumps(
            record.response_snapshot,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return RegionSetReviewRead.model_validate_json(encoded)
    except (TypeError, ValueError, ValidationError) as error:
        raise StoredIdempotencyResultInvalidError from error


class RegionSetService:
    """Orchestrate immutable RegionSet commands under one Project row lock."""

    def __init__(
        self,
        session: AsyncSession,
        storage: ImageStoragePort,
        settings: Settings,
        repository: SqlAlchemyRegionSetRepository | None = None,
    ) -> None:
        for name, value in (
            ("database_lock_timeout_ms", settings.database_lock_timeout_ms),
            ("database_statement_timeout_ms", settings.database_statement_timeout_ms),
        ):
            if not 0 < value <= MAX_DATABASE_TRANSACTION_TIMEOUT_MS:
                raise ValueError(f"{name} is outside the approved runtime boundary.")
        self._session = session
        self._storage = storage
        self._repository = repository or SqlAlchemyRegionSetRepository(session)
        self._identity_repository = SqlAlchemyIdentityRepository(session)
        self._lock_timeout_ms = settings.database_lock_timeout_ms
        self._statement_timeout_ms = settings.database_statement_timeout_ms

    def _object_is_available(self, asset: ImageAsset) -> bool:
        try:
            metadata = self._storage.stat(asset.storage_key)
            if metadata.st_size != asset.byte_size:
                return False
            stream = self._storage.open_private(asset.storage_key)
            try:
                digest = hashlib.sha256()
                while chunk := stream.read(64 * 1024):
                    digest.update(chunk)
                return digest.hexdigest() == asset.sha256
            finally:
                stream.close()
        except (ImageStorageError, FileNotFoundError, OSError):
            return False

    def _current_image_set(
        self,
        *,
        project_id: uuid.UUID,
        assets: list[ImageAsset],
        readiness_reviews: list[ImageSetReadinessReview],
    ) -> CurrentImageSet:
        current_by_role = {asset.role: asset for asset in assets}
        object_available = {
            role: self._object_is_available(asset) for role, asset in current_by_role.items()
        }
        fingerprint = image_set_fingerprint(
            project_id=project_id,
            current_by_role=current_by_role,
            object_available_by_role=object_available,
        )
        required_present = all(role in current_by_role for role in REQUIRED_IMAGE_ROLES)
        current_assets = list(current_by_role.values())
        deterministic = bool(current_assets) and all(
            asset.upload_validation_result == "accepted" for asset in current_assets
        )
        rights = bool(current_assets) and all(
            asset.rights_attestation_status == "confirmed"
            and asset.rights_attestation_version >= 1
            and asset.rights_attested_by_principal_id is not None
            and asset.rights_attested_at is not None
            for asset in current_assets
        )
        required_digests = [
            current_by_role[role].sha256 for role in REQUIRED_IMAGE_ROLES if role in current_by_role
        ]
        distinct = required_present and len(set(required_digests)) == len(REQUIRED_IMAGE_ROLES)
        objects = required_present and all(
            object_available.get(role, False) for role in current_by_role
        )
        latest = readiness_reviews[0] if readiness_reviews else None
        if latest is None:
            status = "incomplete"
        elif latest.image_set_fingerprint != fingerprint:
            status = "stale"
        elif latest.verdict == "not_ready":
            status = "not_ready"
        elif required_present and deterministic and rights and distinct and objects:
            status = "ready"
        else:
            status = "stale"
        return CurrentImageSet(
            fingerprint=fingerprint,
            status=status,
            current_by_role=current_by_role,
        )

    @staticmethod
    def _reviews_by_region_set(
        reviews: list[RegionSetReview],
    ) -> dict[uuid.UUID, RegionSetReview]:
        return {review.region_set_id: review for review in reversed(reviews)}

    @staticmethod
    def _effective_lifecycle(
        region_set: RegionSet,
        *,
        region_sets: list[RegionSet],
        reviews_by_set: dict[uuid.UUID, RegionSetReview],
    ) -> str:
        later_sets = [item for item in region_sets if item.version > region_set.version]
        if region_set.lifecycle == "draft":
            return "superseded" if later_sets else "draft"
        if region_set.lifecycle == "submitted":
            if any(item.lifecycle == "submitted" for item in later_sets):
                return "superseded"
            review = reviews_by_set.get(region_set.id)
            return region_set.lifecycle if review is None else review.verdict
        return region_set.lifecycle

    @staticmethod
    def _stale_reasons(
        region_set: RegionSet,
        current_image_set: CurrentImageSet,
    ) -> list[str]:
        reasons: list[str] = []
        if current_image_set.status != "ready":
            reasons.append("image_set_not_ready")
        if region_set.source_image_set_fingerprint != current_image_set.fingerprint:
            reasons.append("image_set_fingerprint_changed")
        current_primary = current_image_set.primary
        if (
            current_primary is None
            or region_set.source_primary_image_asset_id != current_primary.id
        ):
            reasons.append("primary_front_changed")
        return reasons

    def _history_item(
        self,
        region_set: RegionSet,
        *,
        region_sets: list[RegionSet],
        reviews_by_set: dict[uuid.UUID, RegionSetReview],
        current_image_set: CurrentImageSet,
    ) -> RegionSetHistoryItem:
        review = reviews_by_set.get(region_set.id)
        stale_reasons = self._stale_reasons(region_set, current_image_set)
        latest_version = region_sets[0].version if region_sets else region_set.version
        return RegionSetHistoryItem.model_validate(
            {
                "id": region_set.id,
                "paint_project_id": region_set.paint_project_id,
                "version": region_set.version,
                "lifecycle": region_set.lifecycle,
                "effective_lifecycle": self._effective_lifecycle(
                    region_set,
                    region_sets=region_sets,
                    reviews_by_set=reviews_by_set,
                ),
                "source_primary_image_asset_id": region_set.source_primary_image_asset_id,
                "source_image_set_fingerprint": region_set.source_image_set_fingerprint,
                "region_count": region_set.region_count,
                "total_vertex_count": region_set.total_vertex_count,
                "geometry_fingerprint": region_set.geometry_fingerprint,
                "stale": bool(stale_reasons),
                "stale_reasons": stale_reasons,
                "is_current": region_set.version == latest_version,
                "latest_review": None if review is None else _review_read(review),
                "created_at": region_set.created_at,
            }
        )

    @staticmethod
    def _persisted_draft_inputs(
        regions: list[Region],
        vertices: list[RegionVertex],
    ) -> list[RegionDraftInput]:
        vertices_by_region: dict[uuid.UUID, list[RegionVertex]] = {}
        for vertex in vertices:
            vertices_by_region.setdefault(vertex.region_id, []).append(vertex)
        return [
            RegionDraftInput.model_validate(
                {
                    "stable_region_key": region.stable_region_key,
                    "kind": region.kind,
                    "label": region.label,
                    "z_index": region.z_index,
                    "opacity_ppm": region.opacity_ppm,
                    "notes": region.notes,
                    "vertices": [
                        RegionVertexInput(x_ppm=vertex.x_ppm, y_ppm=vertex.y_ppm)
                        for vertex in sorted(
                            vertices_by_region.get(region.id, []),
                            key=lambda item: item.sequence,
                        )
                    ],
                }
            )
            for region in regions
        ]

    def _region_set_read(
        self,
        region_set: RegionSet,
        *,
        regions: list[Region],
        vertices: list[RegionVertex],
        region_sets: list[RegionSet],
        reviews_by_set: dict[uuid.UUID, RegionSetReview],
        current_image_set: CurrentImageSet,
    ) -> RegionSetRead:
        history = self._history_item(
            region_set,
            region_sets=region_sets,
            reviews_by_set=reviews_by_set,
            current_image_set=current_image_set,
        )
        vertices_by_region: dict[uuid.UUID, list[RegionVertex]] = {}
        for vertex in vertices:
            vertices_by_region.setdefault(vertex.region_id, []).append(vertex)
        region_reads = [
            RegionRead.model_validate(
                {
                    "id": region.id,
                    "stable_region_key": region.stable_region_key,
                    "kind": region.kind,
                    "label": region.label,
                    "normalized_label": region.normalized_label,
                    "z_index": region.z_index,
                    "opacity_ppm": region.opacity_ppm,
                    "notes": region.notes,
                    "vertex_count": region.vertex_count,
                    "area_twice_ppm_squared": region.area_twice_ppm_squared,
                    "bbox_min_x_ppm": region.bbox_min_x_ppm,
                    "bbox_min_y_ppm": region.bbox_min_y_ppm,
                    "bbox_max_x_ppm": region.bbox_max_x_ppm,
                    "bbox_max_y_ppm": region.bbox_max_y_ppm,
                    "vertices": [
                        RegionVertexRead(
                            sequence=vertex.sequence,
                            x_ppm=vertex.x_ppm,
                            y_ppm=vertex.y_ppm,
                        )
                        for vertex in sorted(
                            vertices_by_region.get(region.id, []),
                            key=lambda item: item.sequence,
                        )
                    ],
                }
            )
            for region in regions
        ]
        try:
            snapshot = validate_region_snapshot(self._persisted_draft_inputs(regions, vertices))
        except RegionGeometryValidationError as error:
            raise RuntimeError("Persisted RegionSet geometry is invalid.") from error
        return RegionSetRead.model_validate(
            {
                **history.model_dump(mode="python"),
                "source_image_width": region_set.source_image_width,
                "source_image_height": region_set.source_image_height,
                "source_content_url": _content_url(
                    region_set.paint_project_id,
                    region_set.source_primary_image_asset_id,
                ),
                "supersedes_region_set_id": region_set.supersedes_region_set_id,
                "based_on_region_set_id": region_set.based_on_region_set_id,
                "overlap_warnings": list(snapshot.overlap_warnings),
                "regions": region_reads,
            }
        )

    async def _load_project_state(
        self,
        *,
        project_id: uuid.UUID,
        principal: PrincipalContext,
        for_update: bool,
        owner_only: bool = False,
    ) -> tuple[
        CurrentImageSet,
        list[RegionSet],
        list[RegionSetReview],
    ]:
        if principal.user_id is None:
            project = await self._repository.get_owned_project(
                project_id=project_id,
                owner_principal_id=principal.principal_id,
                for_update=for_update,
            )
            if project is None:
                raise PaintProjectNotFoundError
        else:
            access = await self._identity_repository.resolve_project_access(
                project_id=project_id,
                principal_id=principal.principal_id,
                user_id=principal.user_id,
                for_update=for_update,
            )
            if access is None or (owner_only and not access.is_owner):
                raise PaintProjectNotFoundError
            project = access.project
        assets = await self._repository.list_current_assets(
            project_id=project_id,
            owner_principal_id=project.owner_principal_id,
            for_update=for_update,
        )
        readiness = await self._repository.list_readiness_reviews(
            project_id=project_id,
            owner_principal_id=project.owner_principal_id,
        )
        region_sets = await self._repository.list_region_sets(
            project_id=project_id,
            owner_principal_id=project.owner_principal_id,
        )
        reviews = await self._repository.list_reviews(
            project_id=project_id,
            owner_principal_id=project.owner_principal_id,
        )
        return (
            self._current_image_set(
                project_id=project_id,
                assets=assets,
                readiness_reviews=readiness,
            ),
            region_sets,
            reviews,
        )

    async def get_workbench(
        self,
        *,
        project_id: uuid.UUID,
        principal: PrincipalContext,
    ) -> RegionWorkbenchRead:
        async with self._session.begin():
            current_image_set, region_sets, reviews = await self._load_project_state(
                project_id=project_id,
                principal=principal,
                for_update=False,
            )
            access_role = "owner"
            if principal.user_id is not None:
                access = await self._identity_repository.resolve_project_access(
                    project_id=project_id,
                    principal_id=principal.principal_id,
                    user_id=principal.user_id,
                    for_update=False,
                )
                if access is None:
                    raise PaintProjectNotFoundError
                access_role = access.role
            reviews_by_set = self._reviews_by_region_set(reviews)
            history = [
                self._history_item(
                    item,
                    region_sets=region_sets,
                    reviews_by_set=reviews_by_set,
                    current_image_set=current_image_set,
                )
                for item in region_sets
            ]
            current_read: RegionSetRead | None = None
            if region_sets:
                current = region_sets[0]
                regions = await self._repository.list_regions(region_set_id=current.id)
                vertices = await self._repository.list_vertices(region_set_id=current.id)
                current_read = self._region_set_read(
                    current,
                    regions=regions,
                    vertices=vertices,
                    region_sets=region_sets,
                    reviews_by_set=reviews_by_set,
                    current_image_set=current_image_set,
                )
            primary = current_image_set.primary
            can_create = current_image_set.status == "ready"
            if current_read is not None:
                can_create = can_create and current_read.effective_lifecycle in (
                    "draft",
                    "approved",
                    "changes_requested",
                )
        return RegionWorkbenchRead.model_validate(
            {
                "paint_project_id": project_id,
                "access_role": access_role,
                "image_set_status": current_image_set.status,
                "current_image_set_fingerprint": current_image_set.fingerprint,
                "source_primary_image_asset_id": None if primary is None else primary.id,
                "source_image_width": None if primary is None else primary.width,
                "source_image_height": None if primary is None else primary.height,
                "source_content_url": (
                    None if primary is None else _content_url(project_id, primary.id)
                ),
                "can_create_draft": can_create,
                "current_region_set": current_read,
                "history": history,
            }
        )

    async def list_history(
        self,
        *,
        project_id: uuid.UUID,
        principal: PrincipalContext,
    ) -> RegionSetHistoryResponse:
        workbench = await self.get_workbench(project_id=project_id, principal=principal)
        return RegionSetHistoryResponse(items=workbench.history)

    async def get_region_set(
        self,
        *,
        project_id: uuid.UUID,
        region_set_id: uuid.UUID,
        principal: PrincipalContext,
    ) -> RegionSetRead:
        async with self._session.begin():
            current_image_set, region_sets, reviews = await self._load_project_state(
                project_id=project_id,
                principal=principal,
                for_update=False,
            )
            target = next((item for item in region_sets if item.id == region_set_id), None)
            if target is None:
                raise RegionSetNotFoundError
            regions = await self._repository.list_regions(region_set_id=target.id)
            vertices = await self._repository.list_vertices(region_set_id=target.id)
            return self._region_set_read(
                target,
                regions=regions,
                vertices=vertices,
                region_sets=region_sets,
                reviews_by_set=self._reviews_by_region_set(reviews),
                current_image_set=current_image_set,
            )

    @staticmethod
    def _require_human(principal: PrincipalContext) -> None:
        if principal.principal_type is not PrincipalType.HUMAN:
            raise RegionSetActorNotAllowedError

    async def save_draft(
        self,
        *,
        project_id: uuid.UUID,
        payload: SaveRegionSetRequest,
        principal: PrincipalContext,
        idempotency_key: uuid.UUID,
    ) -> RegionSetRead:
        self._require_human(principal)
        try:
            validated = validate_region_snapshot(payload.regions)
        except RegionGeometryValidationError as error:
            raise RegionGeometryApplicationError(error) from error
        command_hash = save_payload_hash(payload=payload, snapshot=validated)
        created_at = datetime.now(UTC)
        async with self._session.begin():
            await self._repository.configure_transaction_timeouts(
                lock_timeout_ms=self._lock_timeout_ms,
                statement_timeout_ms=self._statement_timeout_ms,
            )
            current_image_set, region_sets, reviews = await self._load_project_state(
                project_id=project_id,
                principal=principal,
                for_update=True,
                owner_only=True,
            )
            claim = await self._repository.claim_command(
                record_id=uuid.uuid4(),
                scope_key=_scope_key(principal.principal_id, project_id, SAVE_COMMAND),
                principal_id=principal.principal_id,
                command_type=SAVE_COMMAND,
                idempotency_key=idempotency_key,
                payload_hash=command_hash,
                created_at=created_at,
                expires_at=created_at + IDEMPOTENCY_RETENTION,
            )
            if not claim.acquired:
                existing = claim.existing_record
                if existing is None:
                    raise StoredIdempotencyResultInvalidError
                if existing.payload_hash != command_hash:
                    raise RegionSetIdempotencyKeyReusedError
                return _stored_region_set_read(existing)
            if current_image_set.status != "ready" or current_image_set.primary is None:
                raise RegionImageSetNotReadyError
            reviews_by_set = self._reviews_by_region_set(reviews)
            base: RegionSet | None = None
            if not region_sets:
                if payload.base_region_set_id is not None or payload.base_version is not None:
                    raise RegionSetStaleVersionError
            else:
                base = region_sets[0]
                if payload.base_region_set_id != base.id or payload.base_version != base.version:
                    raise RegionSetStaleVersionError
                effective = self._effective_lifecycle(
                    base,
                    region_sets=region_sets,
                    reviews_by_set=reviews_by_set,
                )
                if effective not in ("draft", "approved", "changes_requested"):
                    raise RegionSetLifecycleConflictError
            version = await self._repository.next_region_set_version(project_id=project_id)
            primary = current_image_set.primary
            if primary is None:
                raise RegionImageSetNotReadyError
            region_set_id = uuid.uuid4()
            fingerprint = geometry_fingerprint(
                project_id=project_id,
                source_image_set_fingerprint=current_image_set.fingerprint,
                source_primary_image_asset_id=primary.id,
                version=version,
                snapshot=validated,
            )
            region_set = RegionSet(
                id=region_set_id,
                owner_principal_id=principal.principal_id,
                paint_project_id=project_id,
                version=version,
                lifecycle="draft",
                source_primary_image_asset_id=primary.id,
                source_primary_image_role=IMAGE_ROLE_PRIMARY,
                source_image_set_fingerprint=current_image_set.fingerprint,
                source_image_width=primary.width,
                source_image_height=primary.height,
                supersedes_region_set_id=(
                    base.id if base is not None and base.lifecycle == "draft" else None
                ),
                based_on_region_set_id=None if base is None else base.id,
                region_count=len(validated.regions),
                total_vertex_count=validated.total_vertex_count,
                geometry_fingerprint=fingerprint,
                created_by_actor_type="user",
                created_by_actor_id=principal.principal_id,
                created_by_actor_display_name_snapshot=principal.display_name,
                created_at=created_at,
            )
            persisted_regions: list[Region] = []
            persisted_vertices: list[RegionVertex] = []
            for item in validated.regions:
                region_id = uuid.uuid4()
                summary = item.summary
                persisted_regions.append(
                    Region(
                        id=region_id,
                        region_set_id=region_set_id,
                        paint_project_id=project_id,
                        owner_principal_id=principal.principal_id,
                        stable_region_key=item.source.stable_region_key,
                        kind=item.source.kind,
                        label=item.source.label,
                        normalized_label=item.normalized_label,
                        z_index=item.source.z_index,
                        opacity_ppm=item.source.opacity_ppm,
                        notes=item.source.notes,
                        vertex_count=len(item.source.vertices),
                        area_twice_ppm_squared=summary.area_twice_ppm_squared,
                        bbox_min_x_ppm=summary.bbox_min_x_ppm,
                        bbox_min_y_ppm=summary.bbox_min_y_ppm,
                        bbox_max_x_ppm=summary.bbox_max_x_ppm,
                        bbox_max_y_ppm=summary.bbox_max_y_ppm,
                        created_at=created_at,
                    )
                )
                persisted_vertices.extend(
                    RegionVertex(
                        region_id=region_id,
                        sequence=sequence,
                        region_set_id=region_set_id,
                        x_ppm=vertex.x_ppm,
                        y_ppm=vertex.y_ppm,
                    )
                    for sequence, vertex in enumerate(item.source.vertices)
                )
            await self._repository.add_snapshot(
                region_set=region_set,
                regions=persisted_regions,
                vertices=persisted_vertices,
            )
            all_sets = [region_set, *region_sets]
            result = self._region_set_read(
                region_set,
                regions=persisted_regions,
                vertices=persisted_vertices,
                region_sets=all_sets,
                reviews_by_set=reviews_by_set,
                current_image_set=current_image_set,
            )
            record_id = claim.acquired_record_id
            if record_id is None:
                raise StoredIdempotencyResultInvalidError
            await self._repository.complete_command(
                record_id=record_id,
                resource_type="region_set",
                resource_id=region_set_id,
                response_snapshot=result.model_dump(mode="json"),
            )
        return result

    async def fork_draft(
        self,
        *,
        project_id: uuid.UUID,
        source_region_set_id: uuid.UUID,
        payload: ForkRegionSetDraftRequest,
        principal: PrincipalContext,
        idempotency_key: uuid.UUID,
    ) -> RegionSetRead:
        self._require_human(principal)
        command_hash = fork_draft_payload_hash(
            source_region_set_id=source_region_set_id,
            payload=payload,
        )
        created_at = datetime.now(UTC)
        async with self._session.begin():
            await self._repository.configure_transaction_timeouts(
                lock_timeout_ms=self._lock_timeout_ms,
                statement_timeout_ms=self._statement_timeout_ms,
            )
            current_image_set, region_sets, reviews = await self._load_project_state(
                project_id=project_id,
                principal=principal,
                for_update=True,
                owner_only=True,
            )
            source = next(
                (item for item in region_sets if item.id == source_region_set_id),
                None,
            )
            if source is None:
                raise RegionSetNotFoundError
            current = region_sets[0]
            claim = await self._repository.claim_command(
                record_id=uuid.uuid4(),
                scope_key=_scope_key(
                    principal.principal_id,
                    project_id,
                    FORK_DRAFT_COMMAND,
                ),
                principal_id=principal.principal_id,
                command_type=FORK_DRAFT_COMMAND,
                idempotency_key=idempotency_key,
                payload_hash=command_hash,
                created_at=created_at,
                expires_at=created_at + IDEMPOTENCY_RETENTION,
            )
            if not claim.acquired:
                existing = claim.existing_record
                if existing is None:
                    raise StoredIdempotencyResultInvalidError
                if existing.payload_hash != command_hash:
                    raise RegionSetIdempotencyKeyReusedError
                return _stored_region_set_read(existing)
            if (
                current.id != payload.expected_current_region_set_id
                or current.version != payload.expected_current_version
            ):
                raise RegionSetStaleVersionError
            if current_image_set.status != "ready" or current_image_set.primary is None:
                raise RegionImageSetNotReadyError
            source_regions = await self._repository.list_regions(region_set_id=source.id)
            source_vertices = await self._repository.list_vertices(region_set_id=source.id)
            version = await self._repository.next_region_set_version(project_id=project_id)
            if version != current.version + 1:
                raise RuntimeError("The current RegionSet version is not the latest version.")
            draft, persisted_regions, persisted_vertices = await self._copy_snapshot(
                project_id=project_id,
                source=source,
                source_regions=source_regions,
                source_vertices=source_vertices,
                principal=principal,
                current_image_set=current_image_set,
                version=version,
                lifecycle="draft",
                supersedes_region_set_id=current.id,
                based_on_region_set_id=source.id,
                created_at=created_at,
            )
            await self._repository.add_snapshot(
                region_set=draft,
                regions=persisted_regions,
                vertices=persisted_vertices,
            )
            all_sets = [draft, *region_sets]
            result = self._region_set_read(
                draft,
                regions=persisted_regions,
                vertices=persisted_vertices,
                region_sets=all_sets,
                reviews_by_set=self._reviews_by_region_set(reviews),
                current_image_set=current_image_set,
            )
            record_id = claim.acquired_record_id
            if record_id is None:
                raise StoredIdempotencyResultInvalidError
            await self._repository.complete_command(
                record_id=record_id,
                resource_type="region_set",
                resource_id=draft.id,
                response_snapshot=result.model_dump(mode="json"),
            )
        return result

    async def _copy_snapshot(
        self,
        *,
        project_id: uuid.UUID,
        source: RegionSet,
        source_regions: list[Region],
        source_vertices: list[RegionVertex],
        principal: PrincipalContext,
        current_image_set: CurrentImageSet,
        version: int,
        lifecycle: str,
        supersedes_region_set_id: uuid.UUID,
        based_on_region_set_id: uuid.UUID,
        created_at: datetime,
    ) -> tuple[RegionSet, list[Region], list[RegionVertex]]:
        inputs = self._persisted_draft_inputs(source_regions, source_vertices)
        try:
            validated = validate_region_snapshot(inputs)
        except RegionGeometryValidationError as error:
            raise RuntimeError("Persisted draft geometry became invalid.") from error
        primary = current_image_set.primary
        if primary is None:
            raise RegionImageSetNotReadyError
        expected_source_fingerprint = geometry_fingerprint(
            project_id=project_id,
            source_image_set_fingerprint=source.source_image_set_fingerprint,
            source_primary_image_asset_id=source.source_primary_image_asset_id,
            version=source.version,
            snapshot=validated,
        )
        if expected_source_fingerprint != source.geometry_fingerprint:
            raise RuntimeError("Persisted RegionSet fingerprint is inconsistent.")
        region_set_id = uuid.uuid4()
        copied_fingerprint = geometry_fingerprint(
            project_id=project_id,
            source_image_set_fingerprint=current_image_set.fingerprint,
            source_primary_image_asset_id=primary.id,
            version=version,
            snapshot=validated,
        )
        copied = RegionSet(
            id=region_set_id,
            owner_principal_id=principal.principal_id,
            paint_project_id=project_id,
            version=version,
            lifecycle=lifecycle,
            source_primary_image_asset_id=primary.id,
            source_primary_image_role=IMAGE_ROLE_PRIMARY,
            source_image_set_fingerprint=current_image_set.fingerprint,
            source_image_width=primary.width,
            source_image_height=primary.height,
            supersedes_region_set_id=supersedes_region_set_id,
            based_on_region_set_id=based_on_region_set_id,
            region_count=len(validated.regions),
            total_vertex_count=validated.total_vertex_count,
            geometry_fingerprint=copied_fingerprint,
            created_by_actor_type="user",
            created_by_actor_id=principal.principal_id,
            created_by_actor_display_name_snapshot=principal.display_name,
            created_at=created_at,
        )
        persisted_regions: list[Region] = []
        persisted_vertices: list[RegionVertex] = []
        for item in validated.regions:
            region_id = uuid.uuid4()
            summary = item.summary
            persisted_regions.append(
                Region(
                    id=region_id,
                    region_set_id=region_set_id,
                    paint_project_id=project_id,
                    owner_principal_id=principal.principal_id,
                    stable_region_key=item.source.stable_region_key,
                    kind=item.source.kind,
                    label=item.source.label,
                    normalized_label=item.normalized_label,
                    z_index=item.source.z_index,
                    opacity_ppm=item.source.opacity_ppm,
                    notes=item.source.notes,
                    vertex_count=len(item.source.vertices),
                    area_twice_ppm_squared=summary.area_twice_ppm_squared,
                    bbox_min_x_ppm=summary.bbox_min_x_ppm,
                    bbox_min_y_ppm=summary.bbox_min_y_ppm,
                    bbox_max_x_ppm=summary.bbox_max_x_ppm,
                    bbox_max_y_ppm=summary.bbox_max_y_ppm,
                    created_at=created_at,
                )
            )
            persisted_vertices.extend(
                RegionVertex(
                    region_id=region_id,
                    sequence=sequence,
                    region_set_id=region_set_id,
                    x_ppm=vertex.x_ppm,
                    y_ppm=vertex.y_ppm,
                )
                for sequence, vertex in enumerate(item.source.vertices)
            )
        return copied, persisted_regions, persisted_vertices

    async def submit(
        self,
        *,
        project_id: uuid.UUID,
        region_set_id: uuid.UUID,
        principal: PrincipalContext,
        idempotency_key: uuid.UUID,
    ) -> RegionSetRead:
        self._require_human(principal)
        created_at = datetime.now(UTC)
        async with self._session.begin():
            await self._repository.configure_transaction_timeouts(
                lock_timeout_ms=self._lock_timeout_ms,
                statement_timeout_ms=self._statement_timeout_ms,
            )
            current_image_set, region_sets, reviews = await self._load_project_state(
                project_id=project_id,
                principal=principal,
                for_update=True,
                owner_only=True,
            )
            source = next((item for item in region_sets if item.id == region_set_id), None)
            if source is None:
                raise RegionSetNotFoundError
            command_hash = submit_payload_hash(source)
            claim = await self._repository.claim_command(
                record_id=uuid.uuid4(),
                scope_key=_scope_key(principal.principal_id, project_id, SUBMIT_COMMAND),
                principal_id=principal.principal_id,
                command_type=SUBMIT_COMMAND,
                idempotency_key=idempotency_key,
                payload_hash=command_hash,
                created_at=created_at,
                expires_at=created_at + IDEMPOTENCY_RETENTION,
            )
            if not claim.acquired:
                existing = claim.existing_record
                if existing is None:
                    raise StoredIdempotencyResultInvalidError
                if existing.payload_hash != command_hash:
                    raise RegionSetIdempotencyKeyReusedError
                return _stored_region_set_read(existing)
            reviews_by_set = self._reviews_by_region_set(reviews)
            if (
                source.version != region_sets[0].version
                or self._effective_lifecycle(
                    source,
                    region_sets=region_sets,
                    reviews_by_set=reviews_by_set,
                )
                != "draft"
            ):
                raise RegionSetLifecycleConflictError
            if self._stale_reasons(source, current_image_set):
                raise RegionSetStaleSourceError
            source_regions = await self._repository.list_regions(region_set_id=source.id)
            source_vertices = await self._repository.list_vertices(region_set_id=source.id)
            if not source_regions or not any(region.kind == "paint" for region in source_regions):
                raise RegionSetSubmitValidationError
            version = await self._repository.next_region_set_version(project_id=project_id)
            submitted, persisted_regions, persisted_vertices = await self._copy_snapshot(
                project_id=project_id,
                source=source,
                source_regions=source_regions,
                source_vertices=source_vertices,
                principal=principal,
                current_image_set=current_image_set,
                version=version,
                lifecycle="submitted",
                supersedes_region_set_id=source.id,
                based_on_region_set_id=source.id,
                created_at=created_at,
            )
            await self._repository.add_snapshot(
                region_set=submitted,
                regions=persisted_regions,
                vertices=persisted_vertices,
            )
            all_sets = [submitted, *region_sets]
            result = self._region_set_read(
                submitted,
                regions=persisted_regions,
                vertices=persisted_vertices,
                region_sets=all_sets,
                reviews_by_set=reviews_by_set,
                current_image_set=current_image_set,
            )
            record_id = claim.acquired_record_id
            if record_id is None:
                raise StoredIdempotencyResultInvalidError
            await self._repository.complete_command(
                record_id=record_id,
                resource_type="region_set",
                resource_id=submitted.id,
                response_snapshot=result.model_dump(mode="json"),
            )
        return result

    async def review(
        self,
        *,
        project_id: uuid.UUID,
        region_set_id: uuid.UUID,
        payload: CreateRegionSetReviewRequest,
        principal: PrincipalContext,
        idempotency_key: uuid.UUID,
    ) -> RegionSetReviewRead:
        self._require_human(principal)
        created_at = datetime.now(UTC)
        async with self._session.begin():
            await self._repository.configure_transaction_timeouts(
                lock_timeout_ms=self._lock_timeout_ms,
                statement_timeout_ms=self._statement_timeout_ms,
            )
            current_image_set, region_sets, reviews = await self._load_project_state(
                project_id=project_id,
                principal=principal,
                for_update=True,
            )
            target = next((item for item in region_sets if item.id == region_set_id), None)
            if target is None:
                raise RegionSetNotFoundError
            command_hash = review_payload_hash(target, payload)
            claim = await self._repository.claim_command(
                record_id=uuid.uuid4(),
                scope_key=_scope_key(principal.principal_id, project_id, REVIEW_COMMAND),
                principal_id=principal.principal_id,
                command_type=REVIEW_COMMAND,
                idempotency_key=idempotency_key,
                payload_hash=command_hash,
                created_at=created_at,
                expires_at=created_at + IDEMPOTENCY_RETENTION,
            )
            if not claim.acquired:
                existing = claim.existing_record
                if existing is None:
                    raise StoredIdempotencyResultInvalidError
                if existing.payload_hash != command_hash:
                    raise RegionSetIdempotencyKeyReusedError
                return _stored_review_read(existing)
            reviews_by_set = self._reviews_by_region_set(reviews)
            if (
                target.version != region_sets[0].version
                or self._effective_lifecycle(
                    target,
                    region_sets=region_sets,
                    reviews_by_set=reviews_by_set,
                )
                != "submitted"
            ):
                raise RegionSetLifecycleConflictError
            if self._stale_reasons(target, current_image_set):
                raise RegionSetStaleSourceError
            if target.id in reviews_by_set:
                raise RegionSetLifecycleConflictError
            review = RegionSetReview(
                id=uuid.uuid4(),
                owner_principal_id=target.owner_principal_id,
                paint_project_id=project_id,
                region_set_id=target.id,
                version=await self._repository.next_review_version(project_id=project_id),
                verdict=payload.verdict,
                reason=payload.reason,
                actor_type="user",
                actor_id=principal.principal_id,
                actor_display_name_snapshot=principal.display_name,
                created_at=created_at,
            )
            self._repository.add_review(review)
            await self._repository.flush()
            result = _review_read(review)
            record_id = claim.acquired_record_id
            if record_id is None:
                raise StoredIdempotencyResultInvalidError
            await self._repository.complete_command(
                record_id=record_id,
                resource_type="region_set_review",
                resource_id=review.id,
                response_snapshot=result.model_dump(mode="json"),
            )
        return result

    async def list_review_history(
        self,
        *,
        project_id: uuid.UUID,
        region_set_id: uuid.UUID,
        principal: PrincipalContext,
    ) -> RegionSetReviewHistoryResponse:
        async with self._session.begin():
            _, region_sets, reviews = await self._load_project_state(
                project_id=project_id,
                principal=principal,
                for_update=False,
            )
            if not any(item.id == region_set_id for item in region_sets):
                raise RegionSetNotFoundError
            return RegionSetReviewHistoryResponse(
                items=[
                    _review_read(review)
                    for review in reviews
                    if review.region_set_id == region_set_id
                ]
            )
