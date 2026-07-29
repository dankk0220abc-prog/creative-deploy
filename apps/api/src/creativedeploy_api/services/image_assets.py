"""ImageAsset upload, immutable replacement, owner access, and compensation service."""

import hashlib
import json
import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from types import MappingProxyType
from typing import BinaryIO, Literal

from fastapi import UploadFile
from pydantic import ValidationError
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from creativedeploy_api.core.config import MAX_DATABASE_TRANSACTION_TIMEOUT_MS, Settings
from creativedeploy_api.core.principal import PrincipalContext, PrincipalType
from creativedeploy_api.db.models import (
    CommandIdempotencyRecord,
    ImageAsset,
    ImageSetReadinessReview,
    StateTransitionEvent,
)
from creativedeploy_api.db.models.constants import IDEMPOTENCY_STATUS_COMPLETED
from creativedeploy_api.db.models.image_asset import (
    IMAGE_ROLE_PRIMARY,
    IMAGE_ROLE_REFERENCE_ANGLE,
    IMAGE_ROLE_REFERENCE_BACK,
    IMAGE_ROLE_REFERENCE_DETAIL,
    IMAGE_ROLES,
    REQUIRED_IMAGE_ROLES,
)
from creativedeploy_api.repositories.image_assets import SqlAlchemyImageAssetRepository
from creativedeploy_api.schemas.errors import ErrorCategory
from creativedeploy_api.schemas.image_assets import (
    CreateImageAssetRequest,
    CreateReadinessReviewRequest,
    ImageAssetListResponse,
    ImageAssetRead,
    ImageRoleSlotRead,
    ImageSetRead,
    ImageSetReadinessChecklist,
    ImageSetReadinessReviewRead,
    ReadinessReviewHistoryResponse,
)
from creativedeploy_api.services.image_validation import (
    DeterministicImageValidationError,
    ImageValidationLimits,
    safe_original_filename,
    validate_image_file,
)
from creativedeploy_api.services.paint_projects import (
    IDEMPOTENCY_RETENTION,
    PaintProjectApplicationError,
    PaintProjectNotFoundError,
    StoredIdempotencyResultInvalidError,
)
from creativedeploy_api.storage.images import (
    ImageStorageError,
    ImageStoragePort,
    ImageUploadTooLargeError,
    StorageObjectAlreadyExistsError,
    StoragePublishReceipt,
)

logger = logging.getLogger(__name__)

UPLOAD_COMMAND_TYPE = "upload_image"
UPLOAD_PAYLOAD_VERSION = "upload_image.v1"
READINESS_COMMAND_TYPE = "review_image_set_readiness"
READINESS_PAYLOAD_VERSION = "image_set_readiness_review.v1"
PRIMARY_FIRST_UPLOAD_STATES = frozenset({"DRAFT"})
PRIMARY_REPLACEMENT_STATES = frozenset(
    {
        "IMAGE_REVIEW_REQUIRED",
        "IMAGE_VALIDATION_FAILED",
    }
)
REFERENCE_MUTATION_STATES = frozenset(
    {
        "DRAFT",
        "IMAGE_UPLOADED",
        "IMAGE_REVIEW_REQUIRED",
        "IMAGE_VALIDATION_FAILED",
    }
)
REFERENCE_IMAGE_ROLES = frozenset(
    {
        IMAGE_ROLE_REFERENCE_BACK,
        IMAGE_ROLE_REFERENCE_ANGLE,
        IMAGE_ROLE_REFERENCE_DETAIL,
    }
)

ImageAssetMutationOperation = Literal["first_upload", "replacement"]


class ImageAssetNotFoundError(PaintProjectApplicationError):
    """An image is missing or inaccessible in the owner/project scope."""

    status_code = 404
    error_code = "IMAGE_ASSET_NOT_FOUND"
    category: ErrorCategory = "NOT_FOUND"
    message = "The image asset was not found."
    allowed_actions = ("list_project_images",)


class ImageUploadValidationError(PaintProjectApplicationError):
    """Deterministic file validation rejected the upload safely."""

    status_code = 422
    error_code = "IMAGE_UPLOAD_REJECTED"
    category: ErrorCategory = "VALIDATION_ERROR"
    message = "The image did not satisfy the upload contract."
    allowed_actions = ("choose_another_file", "correct_upload_metadata")

    def __init__(self, error: DeterministicImageValidationError) -> None:
        super().__init__()
        self.error_code = error.code.upper()
        self.message = error.safe_message
        self.safe_details = MappingProxyType({"reason": error.code})


class ImageUploadTooLargeApplicationError(PaintProjectApplicationError):
    """Streaming stopped as soon as the configured byte limit was crossed."""

    status_code = 413
    error_code = "REJECTED_TOO_LARGE"
    category: ErrorCategory = "VALIDATION_ERROR"
    message = "The image is larger than the allowed upload limit."
    allowed_actions = ("choose_smaller_file",)


class ImageIdempotencyKeyReusedError(PaintProjectApplicationError):
    """An upload key was reused with different bytes or attestation."""

    status_code = 409
    error_code = "IDEMPOTENCY_KEY_REUSED"
    category: ErrorCategory = "IDEMPOTENCY_KEY_REUSED"
    message = "The Idempotency-Key was already used with different image data."
    allowed_actions = (
        "retry_with_original_payload",
        "start_new_command_with_new_idempotency_key",
    )


class ReadinessIdempotencyKeyReusedError(PaintProjectApplicationError):
    """A readiness key was reused with a changed verdict, reason, or ImageSet."""

    status_code = 409
    error_code = "IDEMPOTENCY_KEY_REUSED"
    category: ErrorCategory = "IDEMPOTENCY_KEY_REUSED"
    message = "The Idempotency-Key was already used for a different readiness review."
    allowed_actions = (
        "retry_with_original_payload",
        "start_new_command_with_new_idempotency_key",
    )


class ImageSetReadyPrerequisitesError(PaintProjectApplicationError):
    """The server-owned deterministic checklist does not permit READY."""

    status_code = 409
    error_code = "IMAGE_SET_READY_PREREQUISITES_NOT_MET"
    category: ErrorCategory = "CONFLICT"
    message = "The image set does not satisfy every deterministic READY prerequisite."
    allowed_actions = ("review_image_set", "resolve_readiness_blockers")

    def __init__(self, blockers: list[str]) -> None:
        super().__init__()
        self.safe_details = MappingProxyType({"blockers": list(blockers)})


class ImageStorageApplicationError(PaintProjectApplicationError):
    """A private object could not be stored or read."""

    status_code = 503
    error_code = "IMAGE_STORAGE_UNAVAILABLE"
    category: ErrorCategory = "STORAGE_ERROR"
    message = "Private image storage is temporarily unavailable."
    retryable = True
    allowed_actions = ("retry",)


class ImageStorageCollisionApplicationError(ImageStorageApplicationError):
    """A random private key collided without changing the existing object."""

    error_code = "IMAGE_STORAGE_COLLISION"
    message = "Private image storage could not allocate a new immutable object."


class ImageWorkflowStateError(PaintProjectApplicationError):
    """The formal state machine does not permit this upload or replacement."""

    status_code = 409
    error_code = "INVALID_STATE_TRANSITION"
    category: ErrorCategory = "INVALID_STATE_TRANSITION"
    message = "The project state does not allow this image operation."

    def __init__(
        self,
        *,
        current_state: str,
        operation: ImageAssetMutationOperation,
    ) -> None:
        super().__init__()
        self.current_state = current_state
        self.allowed_actions = ("view_project", "abandon_project")
        self.safe_details = MappingProxyType({"operation": operation})


class ImagePrincipalTypeNotAllowedError(PaintProjectApplicationError):
    """Image attestation requires an identified human Principal."""

    status_code = 403
    error_code = "ACTOR_NOT_AUTHORIZED"
    category: ErrorCategory = "CONFLICT"
    message = "The current Principal cannot attest image rights."


class ImageIntegrityError(PaintProjectApplicationError):
    """The private object's stored bytes no longer match its immutable metadata."""

    status_code = 503
    error_code = "IMAGE_INTEGRITY_CHECK_FAILED"
    category: ErrorCategory = "STORAGE_ERROR"
    message = "The private image could not be read safely."


class ImageRangeNotSupportedError(PaintProjectApplicationError):
    """Private preview does not support unauthenticated cache/range semantics."""

    status_code = 416
    error_code = "IMAGE_RANGE_NOT_SUPPORTED"
    category: ErrorCategory = "VALIDATION_ERROR"
    message = "Range requests are not supported for private image previews."
    allowed_actions = ("request_complete_private_content",)


class MultipartImageContractError(PaintProjectApplicationError):
    """The multipart field set was not the exact approved contract."""

    status_code = 422
    error_code = "REQUEST_VALIDATION_FAILED"
    category: ErrorCategory = "VALIDATION_ERROR"
    message = "The multipart image request is invalid."
    allowed_actions = ("correct_request",)


@dataclass(frozen=True, slots=True)
class UploadImageAssetResult:
    """Application result with explicit idempotent replay evidence."""

    image: ImageAssetRead
    replayed: bool
    http_status: int = 201


@dataclass(frozen=True, slots=True)
class PrivateImageContent:
    """Authorized stream metadata without a local path."""

    stream: BinaryIO
    content_type: str
    filename: str
    byte_size: int


@dataclass(frozen=True, slots=True)
class ImageSetFacts:
    """One deterministic server-owned view of current role and storage facts."""

    fingerprint: str
    current_by_role: dict[str, ImageAsset]
    object_available_by_role: dict[str, bool]
    checklist: ImageSetReadinessChecklist


@dataclass(frozen=True, slots=True)
class ImageAssetMutationDecision:
    """Pure role/current/workflow authorization result."""

    allowed: bool
    operation: ImageAssetMutationOperation


def evaluate_image_asset_mutation(
    *,
    role: str,
    has_current_asset: bool,
    project_state: str,
) -> ImageAssetMutationDecision:
    """Evaluate the sealed role-aware upload/replacement workflow policy."""
    operation: ImageAssetMutationOperation = "replacement" if has_current_asset else "first_upload"
    if role == IMAGE_ROLE_PRIMARY:
        allowed_states = (
            PRIMARY_REPLACEMENT_STATES if has_current_asset else PRIMARY_FIRST_UPLOAD_STATES
        )
    elif role in REFERENCE_IMAGE_ROLES:
        allowed_states = REFERENCE_MUTATION_STATES
    else:
        return ImageAssetMutationDecision(allowed=False, operation=operation)
    return ImageAssetMutationDecision(
        allowed=project_state in allowed_states,
        operation=operation,
    )


def image_scope_key(principal_id: str, project_id: uuid.UUID) -> str:
    """Compute the server-owned project upload scope."""
    return f"principal:{principal_id}:project:{project_id}:command:{UPLOAD_COMMAND_TYPE}"


def readiness_scope_key(principal_id: str, project_id: uuid.UUID) -> str:
    """Compute the server-owned Project-scoped readiness command scope."""
    return f"principal:{principal_id}:project:{project_id}:command:{READINESS_COMMAND_TYPE}"


def image_payload_hash(
    *,
    declared_content_type: str,
    payload: CreateImageAssetRequest,
    file_sha256: str,
    original_filename: str,
) -> str:
    """Hash the normalized upload command, including bytes and attestation."""
    canonical = {
        "declared_content_type": declared_content_type,
        "file_sha256": file_sha256,
        "intended_usage": payload.intended_usage,
        "original_filename": original_filename,
        "rights_attestation_confirmed": payload.rights_attestation_confirmed,
        "rights_attestation_version": payload.rights_attestation_version,
        "role": payload.role,
        "source_type": payload.source_type,
        "version": UPLOAD_PAYLOAD_VERSION,
    }
    encoded = json.dumps(
        canonical,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def image_set_fingerprint(
    *,
    project_id: uuid.UUID,
    current_by_role: dict[str, ImageAsset],
    object_available_by_role: dict[str, bool],
) -> str:
    """Hash a canonical, path-free snapshot in the frozen formal role order."""
    roles: list[dict[str, object]] = []
    for role in IMAGE_ROLES:
        asset = current_by_role.get(role)
        roles.append(
            {
                "image_asset_id": None if asset is None else str(asset.id),
                "missing": asset is None,
                "object_available": object_available_by_role.get(role, False),
                "rights_attestation_status": (
                    None if asset is None else asset.rights_attestation_status
                ),
                "rights_attestation_version": (
                    None if asset is None else asset.rights_attestation_version
                ),
                "role": role,
                "sha256": None if asset is None else asset.sha256,
                "upload_validation_result": (
                    None if asset is None else asset.upload_validation_result
                ),
            }
        )
    canonical = {
        "paint_project_id": str(project_id),
        "roles": roles,
        "version": "paintpilot_image_set_fingerprint.v1",
    }
    encoded = json.dumps(
        canonical,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def readiness_payload_hash(
    *,
    payload: CreateReadinessReviewRequest,
    fingerprint: str,
) -> str:
    """Hash only normalized human input plus the server-owned current fingerprint."""
    canonical = {
        "image_set_fingerprint": fingerprint,
        "reason": payload.reason,
        "verdict": payload.verdict,
        "version": READINESS_PAYLOAD_VERSION,
    }
    encoded = json.dumps(
        canonical,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _content_url(project_id: uuid.UUID, image_asset_id: uuid.UUID) -> str:
    return f"/api/v1/paint-projects/{project_id}/images/{image_asset_id}/content"


def _image_read(asset: ImageAsset) -> ImageAssetRead:
    return ImageAssetRead.model_validate(
        {
            "id": asset.id,
            "paint_project_id": asset.paint_project_id,
            "role": asset.role,
            "version": asset.version,
            "supersedes_image_asset_id": asset.supersedes_image_asset_id,
            "is_current": asset.is_current,
            "lifecycle_status": asset.lifecycle_status,
            "original_filename": asset.original_filename,
            "declared_content_type": asset.declared_content_type,
            "detected_format": asset.detected_format,
            "byte_size": asset.byte_size,
            "width": asset.width,
            "height": asset.height,
            "pixel_count": asset.pixel_count,
            "color_mode": asset.color_mode,
            "has_alpha": asset.has_alpha,
            "exif_orientation": asset.exif_orientation,
            "sha256": asset.sha256,
            "upload_validation_result": asset.upload_validation_result,
            "upload_validation_details": asset.upload_validation_details,
            "source_type": asset.source_type,
            "rights_attestation_status": asset.rights_attestation_status,
            "rights_attestation_version": asset.rights_attestation_version,
            "intended_usage": asset.intended_usage,
            "rights_attested_at": asset.rights_attested_at,
            "created_at": asset.created_at,
            "content_url": _content_url(asset.paint_project_id, asset.id),
        }
    )


def _review_read(review: ImageSetReadinessReview) -> ImageSetReadinessReviewRead:
    return ImageSetReadinessReviewRead.model_validate(
        {
            "id": review.id,
            "paint_project_id": review.paint_project_id,
            "version": review.version,
            "verdict": review.verdict,
            "reason": review.reason,
            "primary_front_image_asset_id": review.primary_front_image_asset_id,
            "reference_back_image_asset_id": review.reference_back_image_asset_id,
            "reference_angle_image_asset_id": review.reference_angle_image_asset_id,
            "reference_detail_image_asset_id": review.reference_detail_image_asset_id,
            "image_set_fingerprint": review.image_set_fingerprint,
            "actor_type": review.actor_type,
            "actor_id": review.actor_id,
            "actor_display_name_snapshot": review.actor_display_name_snapshot,
            "created_at": review.created_at,
        }
    )


def _stored_image_read(record: CommandIdempotencyRecord) -> ImageAssetRead:
    if (
        record.execution_status != IDEMPOTENCY_STATUS_COMPLETED
        or record.resource_type != "image_asset"
        or record.http_status != 201
        or record.response_snapshot is None
    ):
        raise StoredIdempotencyResultInvalidError
    try:
        encoded_snapshot = json.dumps(
            record.response_snapshot,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return ImageAssetRead.model_validate_json(encoded_snapshot)
    except (TypeError, ValueError, ValidationError) as error:
        raise StoredIdempotencyResultInvalidError from error


def _stored_review_read(
    record: CommandIdempotencyRecord,
) -> ImageSetReadinessReviewRead:
    if (
        record.execution_status != IDEMPOTENCY_STATUS_COMPLETED
        or record.resource_type != "image_set_readiness_review"
        or record.http_status != 201
        or record.response_snapshot is None
    ):
        raise StoredIdempotencyResultInvalidError
    try:
        encoded_snapshot = json.dumps(
            record.response_snapshot,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return ImageSetReadinessReviewRead.model_validate_json(encoded_snapshot)
    except (TypeError, ValueError, ValidationError) as error:
        raise StoredIdempotencyResultInvalidError from error


def _database_sqlstate(error: DBAPIError) -> str | None:
    original = error.orig
    for attribute in ("sqlstate", "pgcode"):
        value = getattr(original, attribute, None)
        if isinstance(value, str):
            return value
    return None


class ImageAssetService:
    """Orchestrate private storage and PostgreSQL as one compensated command."""

    def __init__(
        self,
        session: AsyncSession,
        storage: ImageStoragePort,
        settings: Settings,
        repository: SqlAlchemyImageAssetRepository | None = None,
    ) -> None:
        for name, value in (
            ("database_lock_timeout_ms", settings.database_lock_timeout_ms),
            ("database_statement_timeout_ms", settings.database_statement_timeout_ms),
        ):
            if not 0 < value <= MAX_DATABASE_TRANSACTION_TIMEOUT_MS:
                raise ValueError(f"{name} is outside the approved runtime boundary.")
        self._session = session
        self._storage = storage
        self._repository = repository or SqlAlchemyImageAssetRepository(session)
        self._lock_timeout_ms = settings.database_lock_timeout_ms
        self._statement_timeout_ms = settings.database_statement_timeout_ms
        self._limits = ImageValidationLimits(
            max_bytes=settings.image_upload_max_bytes,
            min_side_px=settings.image_min_side_px,
            max_side_px=settings.image_max_side_px,
            max_pixels=settings.image_max_pixels,
        )

    def _object_is_available(self, asset: ImageAsset) -> bool:
        """Verify immutable private object size and SHA without exposing its path."""
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

    def _image_set_facts(
        self,
        *,
        project_id: uuid.UUID,
        current_assets: list[ImageAsset],
    ) -> ImageSetFacts:
        """Compute the complete deterministic non-AI readiness facts."""
        current_by_role = {asset.role: asset for asset in current_assets}
        object_available_by_role = {
            role: self._object_is_available(asset) for role, asset in current_by_role.items()
        }
        required_present = all(role in current_by_role for role in REQUIRED_IMAGE_ROLES)
        all_current = list(current_by_role.values())
        deterministic_accepted = bool(all_current) and all(
            asset.upload_validation_result == "accepted" for asset in all_current
        )
        rights_complete = bool(all_current) and all(
            asset.rights_attestation_status == "confirmed"
            and asset.rights_attestation_version >= 1
            and asset.rights_attested_by_principal_id is not None
            and asset.rights_attested_at is not None
            for asset in all_current
        )
        required_sha256 = [
            current_by_role[role].sha256 for role in REQUIRED_IMAGE_ROLES if role in current_by_role
        ]
        content_distinct = required_present and len(set(required_sha256)) == len(
            REQUIRED_IMAGE_ROLES
        )
        objects_available = required_present and all(
            object_available_by_role.get(role, False) for role in current_by_role
        )
        blockers: list[str] = []
        if not required_present:
            blockers.append("missing_required_roles")
        if not deterministic_accepted:
            blockers.append("deterministic_validation_not_accepted")
        if not rights_complete:
            blockers.append("rights_attestation_incomplete")
        if not content_distinct:
            blockers.append("duplicate_or_missing_required_content")
        if not objects_available:
            blockers.append("private_object_unavailable")
        checklist = ImageSetReadinessChecklist(
            required_roles_present=required_present,
            deterministic_validation_accepted=deterministic_accepted,
            rights_complete=rights_complete,
            content_distinct=content_distinct,
            objects_available=objects_available,
            snapshot_current=False,
            can_mark_ready=not blockers,
            blockers=blockers,
        )
        return ImageSetFacts(
            fingerprint=image_set_fingerprint(
                project_id=project_id,
                current_by_role=current_by_role,
                object_available_by_role=object_available_by_role,
            ),
            current_by_role=current_by_role,
            object_available_by_role=object_available_by_role,
            checklist=checklist,
        )

    def _image_set_read(
        self,
        *,
        project_id: uuid.UUID,
        assets: list[ImageAsset],
        reviews: list[ImageSetReadinessReview],
    ) -> ImageSetRead:
        """Build the strict ImageSet response from database and private-object facts."""
        current_assets = [asset for asset in assets if asset.is_current]
        facts = self._image_set_facts(
            project_id=project_id,
            current_assets=current_assets,
        )
        latest = reviews[0] if reviews else None
        snapshot_current = latest is not None and latest.image_set_fingerprint == facts.fingerprint
        checklist = facts.checklist.model_copy(update={"snapshot_current": snapshot_current})
        stale_reasons: list[str] = []
        if latest is None:
            status = "incomplete"
        elif not snapshot_current or (latest.verdict == "ready" and not checklist.can_mark_ready):
            status = "stale"
            snapshot_fields = {
                IMAGE_ROLE_PRIMARY: latest.primary_front_image_asset_id,
                IMAGE_ROLE_REFERENCE_BACK: latest.reference_back_image_asset_id,
                IMAGE_ROLE_REFERENCE_ANGLE: latest.reference_angle_image_asset_id,
                IMAGE_ROLE_REFERENCE_DETAIL: latest.reference_detail_image_asset_id,
            }
            for role in IMAGE_ROLES:
                current = facts.current_by_role.get(role)
                current_id = None if current is None else current.id
                if snapshot_fields[role] != current_id:
                    stale_reasons.append(f"{role}_changed")
            if not stale_reasons:
                if not checklist.objects_available:
                    stale_reasons.append("private_object_unavailable")
                elif not checklist.rights_complete:
                    stale_reasons.append("rights_attestation_changed")
                elif not checklist.deterministic_validation_accepted:
                    stale_reasons.append("deterministic_validation_changed")
                else:
                    stale_reasons.append("image_set_fingerprint_changed")
        elif latest.verdict == "ready":
            status = "ready"
        else:
            status = "not_ready"

        history_by_role = {
            role: [asset for asset in assets if asset.role == role] for role in IMAGE_ROLES
        }
        roles = [
            ImageRoleSlotRead(
                role=role,  # type: ignore[arg-type]
                required=role in REQUIRED_IMAGE_ROLES,
                missing=role not in facts.current_by_role,
                object_available=facts.object_available_by_role.get(role, False),
                current=(
                    None
                    if role not in facts.current_by_role
                    else _image_read(facts.current_by_role[role])
                ),
                history=[_image_read(asset) for asset in history_by_role[role]],
            )
            for role in IMAGE_ROLES
        ]
        return ImageSetRead(
            paint_project_id=project_id,
            image_set_fingerprint=facts.fingerprint,
            roles=roles,
            checklist=checklist,
            latest_review=None if latest is None else _review_read(latest),
            status=status,  # type: ignore[arg-type]
            stale_reasons=stale_reasons,
        )

    async def _require_owned_project(
        self,
        *,
        project_id: uuid.UUID,
        principal: PrincipalContext,
    ) -> None:
        async with self._session.begin():
            project = await self._repository.get_owned_project(
                project_id=project_id,
                owner_principal_id=principal.principal_id,
            )
            if project is None:
                raise PaintProjectNotFoundError

    async def _preflight_image_mutation(
        self,
        *,
        project_id: uuid.UUID,
        role: str,
        principal: PrincipalContext,
        idempotency_key: uuid.UUID,
    ) -> None:
        """Reject a known-new unauthorized command before staging file bytes."""
        async with self._session.begin():
            await self._repository.configure_transaction_timeouts(
                lock_timeout_ms=self._lock_timeout_ms,
                statement_timeout_ms=self._statement_timeout_ms,
            )
            project = await self._repository.get_owned_project(
                project_id=project_id,
                owner_principal_id=principal.principal_id,
                for_update=True,
            )
            if project is None:
                raise PaintProjectNotFoundError
            existing = await self._repository.get_upload_command(
                scope_key=image_scope_key(principal.principal_id, project_id),
                idempotency_key=idempotency_key,
            )
            if existing is not None:
                return
            current = await self._repository.get_current_for_update(
                project_id=project_id,
                role=role,
            )
            decision = evaluate_image_asset_mutation(
                role=role,
                has_current_asset=current is not None,
                project_state=project.status,
            )
            if not decision.allowed:
                raise ImageWorkflowStateError(
                    current_state=project.status,
                    operation=decision.operation,
                )

    async def _compensate(
        self,
        receipt: StoragePublishReceipt,
        *,
        request_id: uuid.UUID,
    ) -> None:
        key_digest = hashlib.sha256(receipt.key.encode()).hexdigest()
        try:
            async with self._session.begin():
                referenced_keys = await self._repository.referenced_storage_keys()
        except BaseException:
            logger.error(
                "ImageAsset compensation refused because references could not be verified",
                extra={
                    "request_id": str(request_id),
                    "storage_key_sha256": key_digest,
                    "compensation_status": "reference_verification_failed",
                    "orphan_detection_required": True,
                },
            )
            return
        try:
            self._storage.delete_uncommitted(
                receipt,
                referenced_keys=referenced_keys,
            )
        except (ImageStorageError, OSError):
            logger.error(
                "ImageAsset compensation refused or failed",
                extra={
                    "request_id": str(request_id),
                    "storage_key_sha256": key_digest,
                    "compensation_status": "object_not_deleted",
                    "orphan_detection_required": True,
                },
            )
            return
        logger.info(
            "ImageAsset uncommitted object compensation completed",
            extra={
                "request_id": str(request_id),
                "storage_key_sha256": key_digest,
                "compensation_status": "deleted_exact_receipt_object",
                "orphan_detection_required": False,
            },
        )

    async def upload_image(
        self,
        *,
        project_id: uuid.UUID,
        payload: CreateImageAssetRequest,
        upload: UploadFile,
        principal: PrincipalContext,
        idempotency_key: uuid.UUID,
        correlation_id: uuid.UUID,
    ) -> UploadImageAssetResult:
        """Validate, store, persist, replace, compensate, or replay one image command."""
        if principal.principal_type is not PrincipalType.HUMAN:
            raise ImagePrincipalTypeNotAllowedError
        await self._preflight_image_mutation(
            project_id=project_id,
            role=payload.role,
            principal=principal,
            idempotency_key=idempotency_key,
        )

        staged = None
        stored: StoragePublishReceipt | None = None
        try:
            try:
                staged = await self._storage.stage_upload(
                    upload,
                    max_bytes=self._limits.max_bytes,
                )
            except ImageUploadTooLargeError as error:
                raise ImageUploadTooLargeApplicationError from error
            except (ImageStorageError, OSError) as error:
                raise ImageStorageApplicationError from error

            try:
                validated = validate_image_file(
                    staged.path,
                    declared_content_type=upload.content_type or "",
                    byte_size=staged.byte_size,
                    limits=self._limits,
                )
            except DeterministicImageValidationError as error:
                raise ImageUploadValidationError(error) from error

            original_filename = safe_original_filename(upload.filename)
            declared_content_type = upload.content_type or ""
            command_hash = image_payload_hash(
                declared_content_type=declared_content_type,
                payload=payload,
                file_sha256=staged.sha256,
                original_filename=original_filename,
            )
            created_at = datetime.now(UTC)
            result: UploadImageAssetResult
            try:
                async with self._session.begin():
                    await self._repository.configure_transaction_timeouts(
                        lock_timeout_ms=self._lock_timeout_ms,
                        statement_timeout_ms=self._statement_timeout_ms,
                    )
                    claim = await self._repository.claim_upload_command(
                        record_id=uuid.uuid4(),
                        scope_key=image_scope_key(principal.principal_id, project_id),
                        principal_id=principal.principal_id,
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
                            raise ImageIdempotencyKeyReusedError
                        result = UploadImageAssetResult(
                            image=_stored_image_read(existing),
                            replayed=True,
                        )
                    else:
                        project = await self._repository.get_owned_project(
                            project_id=project_id,
                            owner_principal_id=principal.principal_id,
                            for_update=True,
                        )
                        if project is None:
                            raise PaintProjectNotFoundError
                        current = await self._repository.get_current_for_update(
                            project_id=project_id,
                            role=payload.role,
                        )
                        decision = evaluate_image_asset_mutation(
                            role=payload.role,
                            has_current_asset=current is not None,
                            project_state=project.status,
                        )
                        if not decision.allowed:
                            raise ImageWorkflowStateError(
                                current_state=project.status,
                                operation=decision.operation,
                            )

                        try:
                            stored = self._storage.put_from_temp(
                                staged,
                                detected_format=validated.detected_format,
                            )
                        except StorageObjectAlreadyExistsError as error:
                            logger.warning(
                                "ImageAsset immutable storage key collision",
                                extra={
                                    "request_id": str(correlation_id),
                                    "compensation_status": "not_authorized_without_receipt",
                                },
                            )
                            raise ImageStorageCollisionApplicationError from error
                        except (ImageStorageError, OSError) as error:
                            raise ImageStorageApplicationError from error

                        if current is not None:
                            await self._repository.supersede(current.id)
                        asset_id = uuid.uuid4()
                        version = 1 if current is None else current.version + 1
                        from_state = project.status
                        asset = ImageAsset(
                            id=asset_id,
                            paint_project_id=project_id,
                            owner_principal_id=principal.principal_id,
                            role=payload.role,
                            version=version,
                            supersedes_image_asset_id=None if current is None else current.id,
                            is_current=True,
                            lifecycle_status="current",
                            storage_provider="local_filesystem",
                            storage_key=stored.key,
                            original_filename=original_filename,
                            declared_content_type=declared_content_type,
                            detected_format=validated.detected_format,
                            byte_size=staged.byte_size,
                            width=validated.width,
                            height=validated.height,
                            pixel_count=validated.pixel_count,
                            color_mode=validated.color_mode,
                            has_alpha=validated.has_alpha,
                            exif_orientation=validated.exif_orientation,
                            sha256=staged.sha256,
                            upload_validation_result="accepted",
                            upload_validation_details=validated.validation_details,
                            source_type=payload.source_type,
                            rights_attestation_status="confirmed",
                            rights_attestation_version=payload.rights_attestation_version,
                            intended_usage=payload.intended_usage,
                            rights_attested_by_principal_id=principal.principal_id,
                            rights_attested_at=created_at,
                            created_by_actor_type="user",
                            created_by_actor_id=principal.principal_id,
                            created_by_actor_display_name_snapshot=principal.display_name,
                            created_at=created_at,
                        )
                        previous_state = project.status
                        if payload.role == IMAGE_ROLE_PRIMARY:
                            project.current_image_asset_id = asset_id
                            if project.status in (
                                "DRAFT",
                                "IMAGE_REVIEW_REQUIRED",
                                "IMAGE_VALIDATION_FAILED",
                            ):
                                project.status = "IMAGE_UPLOADED"
                        project.updated_at = created_at
                        self._repository.add_asset(asset)
                        if project.status != previous_state:
                            event = StateTransitionEvent(
                                id=uuid.uuid4(),
                                project_id=project_id,
                                from_state=from_state,
                                to_state=project.status,
                                event="upload_image",
                                actor_type="user",
                                actor_principal_id=principal.principal_id,
                                actor_display_name_snapshot=principal.display_name,
                                reason=(
                                    "image_uploaded"
                                    if current is None
                                    else "replacement_image_uploaded"
                                ),
                                correlation_id=correlation_id,
                                event_metadata={
                                    "schema_version": "image_upload_event.v2",
                                    "image_asset_id": str(asset_id),
                                    "role": payload.role,
                                    "version": version,
                                },
                                created_at=created_at,
                            )
                            self._repository.add_event(event)
                        await self._repository.flush()
                        image_read = _image_read(asset)
                        acquired_record_id = claim.acquired_record_id
                        if acquired_record_id is None:
                            raise StoredIdempotencyResultInvalidError
                        await self._repository.complete_upload_command(
                            record_id=acquired_record_id,
                            image_asset_id=asset_id,
                            response_snapshot=image_read.model_dump(mode="json"),
                        )
                        result = UploadImageAssetResult(image=image_read, replayed=False)
            except DBAPIError as error:
                if stored is not None:
                    await self._compensate(stored, request_id=correlation_id)
                    stored = None
                sqlstate = _database_sqlstate(error)
                logger.warning(
                    "ImageAsset database transaction failed",
                    extra={
                        "request_id": str(correlation_id),
                        "database_sqlstate": sqlstate,
                    },
                )
                raise
            except BaseException:
                if stored is not None:
                    await self._compensate(stored, request_id=correlation_id)
                    stored = None
                raise

            logger.info(
                "ImageAsset upload command completed",
                extra={
                    "request_id": str(correlation_id),
                    "principal_id": principal.principal_id,
                    "project_id": str(project_id),
                    "image_asset_id": str(result.image.id),
                    "idempotent_replayed": result.replayed,
                },
            )
            return result
        finally:
            if staged is not None:
                try:
                    self._storage.delete_staged(staged)
                except (ImageStorageError, OSError):
                    logger.warning(
                        "ImageAsset staging cleanup failed",
                        extra={"request_id": str(correlation_id)},
                    )

    async def list_images(
        self,
        *,
        project_id: uuid.UUID,
        principal: PrincipalContext,
    ) -> ImageAssetListResponse:
        """List only the current owner's project image history."""
        async with self._session.begin():
            project = await self._repository.get_owned_project(
                project_id=project_id,
                owner_principal_id=principal.principal_id,
            )
            if project is None:
                raise PaintProjectNotFoundError
            assets = await self._repository.list_owned_assets(
                project_id=project_id,
                owner_principal_id=principal.principal_id,
            )
        return ImageAssetListResponse(items=[_image_read(asset) for asset in assets])

    async def get_image_set(
        self,
        *,
        project_id: uuid.UUID,
        principal: PrincipalContext,
    ) -> ImageSetRead:
        """Read one complete owner-scoped ImageSet and deterministic readiness state."""
        async with self._session.begin():
            project = await self._repository.get_owned_project(
                project_id=project_id,
                owner_principal_id=principal.principal_id,
            )
            if project is None:
                raise PaintProjectNotFoundError
            assets = await self._repository.list_owned_assets(
                project_id=project_id,
                owner_principal_id=principal.principal_id,
            )
            reviews = await self._repository.list_readiness_reviews(
                project_id=project_id,
                owner_principal_id=principal.principal_id,
            )
        return self._image_set_read(
            project_id=project_id,
            assets=assets,
            reviews=reviews,
        )

    async def create_readiness_review(
        self,
        *,
        project_id: uuid.UUID,
        payload: CreateReadinessReviewRequest,
        principal: PrincipalContext,
        idempotency_key: uuid.UUID,
    ) -> ImageSetReadinessReviewRead:
        """Create or replay one human verdict against the locked current ImageSet."""
        if principal.principal_type is not PrincipalType.HUMAN:
            raise ImagePrincipalTypeNotAllowedError
        created_at = datetime.now(UTC)
        async with self._session.begin():
            await self._repository.configure_transaction_timeouts(
                lock_timeout_ms=self._lock_timeout_ms,
                statement_timeout_ms=self._statement_timeout_ms,
            )
            project = await self._repository.get_owned_project(
                project_id=project_id,
                owner_principal_id=principal.principal_id,
                for_update=True,
            )
            if project is None:
                raise PaintProjectNotFoundError
            current_assets = await self._repository.list_current_for_update(
                project_id=project_id,
                owner_principal_id=principal.principal_id,
            )
            facts = self._image_set_facts(
                project_id=project_id,
                current_assets=current_assets,
            )
            command_hash = readiness_payload_hash(
                payload=payload,
                fingerprint=facts.fingerprint,
            )
            claim = await self._repository.claim_readiness_command(
                record_id=uuid.uuid4(),
                scope_key=readiness_scope_key(principal.principal_id, project_id),
                principal_id=principal.principal_id,
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
                    raise ReadinessIdempotencyKeyReusedError
                result = _stored_review_read(existing)
            else:
                if payload.verdict == "ready" and not facts.checklist.can_mark_ready:
                    raise ImageSetReadyPrerequisitesError(facts.checklist.blockers)
                version = await self._repository.next_readiness_version(project_id=project_id)
                review_id = uuid.uuid4()
                review = ImageSetReadinessReview(
                    id=review_id,
                    owner_principal_id=principal.principal_id,
                    paint_project_id=project_id,
                    version=version,
                    verdict=payload.verdict,
                    reason=payload.reason,
                    primary_front_image_asset_id=(
                        facts.current_by_role[IMAGE_ROLE_PRIMARY].id
                        if IMAGE_ROLE_PRIMARY in facts.current_by_role
                        else None
                    ),
                    primary_front_role=(
                        IMAGE_ROLE_PRIMARY if IMAGE_ROLE_PRIMARY in facts.current_by_role else None
                    ),
                    reference_back_image_asset_id=(
                        facts.current_by_role[IMAGE_ROLE_REFERENCE_BACK].id
                        if IMAGE_ROLE_REFERENCE_BACK in facts.current_by_role
                        else None
                    ),
                    reference_back_role=(
                        IMAGE_ROLE_REFERENCE_BACK
                        if IMAGE_ROLE_REFERENCE_BACK in facts.current_by_role
                        else None
                    ),
                    reference_angle_image_asset_id=(
                        facts.current_by_role[IMAGE_ROLE_REFERENCE_ANGLE].id
                        if IMAGE_ROLE_REFERENCE_ANGLE in facts.current_by_role
                        else None
                    ),
                    reference_angle_role=(
                        IMAGE_ROLE_REFERENCE_ANGLE
                        if IMAGE_ROLE_REFERENCE_ANGLE in facts.current_by_role
                        else None
                    ),
                    reference_detail_image_asset_id=(
                        facts.current_by_role[IMAGE_ROLE_REFERENCE_DETAIL].id
                        if IMAGE_ROLE_REFERENCE_DETAIL in facts.current_by_role
                        else None
                    ),
                    reference_detail_role=(
                        IMAGE_ROLE_REFERENCE_DETAIL
                        if IMAGE_ROLE_REFERENCE_DETAIL in facts.current_by_role
                        else None
                    ),
                    image_set_fingerprint=facts.fingerprint,
                    actor_type="user",
                    actor_id=principal.principal_id,
                    actor_display_name_snapshot=principal.display_name,
                    created_at=created_at,
                )
                self._repository.add_readiness_review(review)
                await self._repository.flush()
                result = _review_read(review)
                acquired_record_id = claim.acquired_record_id
                if acquired_record_id is None:
                    raise StoredIdempotencyResultInvalidError
                await self._repository.complete_readiness_command(
                    record_id=acquired_record_id,
                    review_id=review_id,
                    response_snapshot=result.model_dump(mode="json"),
                )
        logger.info(
            "ImageSet readiness review command completed",
            extra={
                "principal_id": principal.principal_id,
                "project_id": str(project_id),
                "readiness_review_id": str(result.id),
                "image_set_fingerprint": result.image_set_fingerprint,
            },
        )
        return result

    async def list_readiness_history(
        self,
        *,
        project_id: uuid.UUID,
        principal: PrincipalContext,
    ) -> ReadinessReviewHistoryResponse:
        """Read immutable readiness history without disclosing other owners."""
        async with self._session.begin():
            project = await self._repository.get_owned_project(
                project_id=project_id,
                owner_principal_id=principal.principal_id,
            )
            if project is None:
                raise PaintProjectNotFoundError
            reviews = await self._repository.list_readiness_reviews(
                project_id=project_id,
                owner_principal_id=principal.principal_id,
            )
        return ReadinessReviewHistoryResponse(items=[_review_read(review) for review in reviews])

    async def get_image(
        self,
        *,
        project_id: uuid.UUID,
        image_asset_id: uuid.UUID,
        principal: PrincipalContext,
    ) -> ImageAssetRead:
        """Read one owner-scoped immutable asset."""
        async with self._session.begin():
            asset = await self._repository.get_owned_asset(
                project_id=project_id,
                image_asset_id=image_asset_id,
                owner_principal_id=principal.principal_id,
            )
            if asset is None:
                raise ImageAssetNotFoundError
            return _image_read(asset)

    async def open_image_content(
        self,
        *,
        project_id: uuid.UUID,
        image_asset_id: uuid.UUID,
        principal: PrincipalContext,
    ) -> PrivateImageContent:
        """Authorize first, then verify and open the private immutable bytes."""
        async with self._session.begin():
            asset = await self._repository.get_owned_asset(
                project_id=project_id,
                image_asset_id=image_asset_id,
                owner_principal_id=principal.principal_id,
            )
            if asset is None:
                raise ImageAssetNotFoundError
            storage_key = asset.storage_key
            expected_size = asset.byte_size
            expected_sha256 = asset.sha256
            content_type = asset.declared_content_type
            detected_format = asset.detected_format

        try:
            metadata = self._storage.stat(storage_key)
            if metadata.st_size != expected_size:
                raise ImageIntegrityError
            stream = self._storage.open_private(storage_key)
            digest = hashlib.sha256()
            while chunk := stream.read(64 * 1024):
                digest.update(chunk)
            if digest.hexdigest() != expected_sha256:
                stream.close()
                raise ImageIntegrityError
            stream.seek(0)
        except ImageIntegrityError:
            raise
        except (ImageStorageError, FileNotFoundError, OSError) as error:
            raise ImageStorageApplicationError from error
        extension = {"jpeg": "jpg", "png": "png", "webp": "webp"}[detected_format]
        return PrivateImageContent(
            stream=stream,
            content_type=content_type,
            filename=f"paintpilot-image.{extension}",
            byte_size=expected_size,
        )

    async def detect_orphans(self) -> tuple[str, ...]:
        """Run the explicit read-only orphan scanner against database references."""
        async with self._session.begin():
            referenced = await self._repository.referenced_storage_keys()
        return self._storage.scan_orphans(referenced_keys=referenced)
