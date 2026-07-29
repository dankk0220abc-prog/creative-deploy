"""ImageAsset upload, immutable replacement, owner access, and compensation service."""

import hashlib
import json
import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from types import MappingProxyType
from typing import BinaryIO

from fastapi import UploadFile
from pydantic import ValidationError
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from creativedeploy_api.core.config import MAX_DATABASE_TRANSACTION_TIMEOUT_MS, Settings
from creativedeploy_api.core.principal import PrincipalContext, PrincipalType
from creativedeploy_api.db.models import (
    CommandIdempotencyRecord,
    ImageAsset,
    StateTransitionEvent,
)
from creativedeploy_api.db.models.constants import IDEMPOTENCY_STATUS_COMPLETED
from creativedeploy_api.db.models.image_asset import IMAGE_ROLE_PRIMARY
from creativedeploy_api.repositories.image_assets import SqlAlchemyImageAssetRepository
from creativedeploy_api.schemas.errors import ErrorCategory
from creativedeploy_api.schemas.image_assets import (
    CreateImageAssetRequest,
    ImageAssetListResponse,
    ImageAssetRead,
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
FIRST_UPLOAD_STATES = ("DRAFT",)
REPLACEMENT_STATES = ("IMAGE_REVIEW_REQUIRED", "IMAGE_VALIDATION_FAILED")


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

    def __init__(self, *, current_state: str, replacement: bool) -> None:
        super().__init__()
        self.current_state = current_state
        self.allowed_actions = (
            ("review_image", "replace_image", "abandon_project")
            if replacement
            else ("view_project", "abandon_project")
        )


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


def image_scope_key(principal_id: str, project_id: uuid.UUID) -> str:
    """Compute the server-owned project upload scope."""
    return f"principal:{principal_id}:project:{project_id}:command:{UPLOAD_COMMAND_TYPE}"


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
        await self._require_owned_project(project_id=project_id, principal=principal)

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
                        replacement = current is not None
                        allowed_states = REPLACEMENT_STATES if replacement else FIRST_UPLOAD_STATES
                        if project.status not in allowed_states:
                            raise ImageWorkflowStateError(
                                current_state=project.status,
                                replacement=replacement,
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
                            role=IMAGE_ROLE_PRIMARY,
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
                        project.current_image_asset_id = asset_id
                        project.status = "IMAGE_UPLOADED"
                        project.updated_at = created_at
                        event = StateTransitionEvent(
                            id=uuid.uuid4(),
                            project_id=project_id,
                            from_state=from_state,
                            to_state="IMAGE_UPLOADED",
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
                                "schema_version": "image_upload_event.v1",
                                "image_asset_id": str(asset_id),
                                "role": payload.role,
                                "version": version,
                            },
                            created_at=created_at,
                        )
                        self._repository.add_asset(asset)
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
