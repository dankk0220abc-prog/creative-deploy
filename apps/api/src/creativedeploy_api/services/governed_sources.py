"""Shared server-owned ImageSet eligibility facts for governed downstream work."""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field

from creativedeploy_api.db.models import (
    ImageAsset,
    ImageSetReadinessReview,
    RegionSet,
    RegionSetReview,
)
from creativedeploy_api.db.models.image_asset import IMAGE_ROLE_PRIMARY, REQUIRED_IMAGE_ROLES
from creativedeploy_api.services.image_assets import image_set_fingerprint
from creativedeploy_api.storage.images import ImageStorageError, ImageStoragePort


@dataclass(frozen=True, slots=True)
class CurrentImageSet:
    """Current server-owned source facts used for stale and READY checks."""

    fingerprint: str
    status: str
    current_by_role: dict[str, ImageAsset]
    latest_readiness_review: ImageSetReadinessReview | None = None
    object_available_by_role: dict[str, bool] = field(default_factory=dict)

    @property
    def primary(self) -> ImageAsset | None:
        return self.current_by_role.get(IMAGE_ROLE_PRIMARY)


def image_object_is_available(storage: ImageStoragePort, asset: ImageAsset) -> bool:
    """Verify exact immutable bytes without exposing a storage key or local path."""

    try:
        metadata = storage.stat(asset.storage_key)
        if metadata.st_size != asset.byte_size:
            return False
        stream = storage.open_private(asset.storage_key)
        try:
            digest = hashlib.sha256()
            while chunk := stream.read(64 * 1024):
                digest.update(chunk)
            return digest.hexdigest() == asset.sha256
        finally:
            stream.close()
    except (ImageStorageError, FileNotFoundError, OSError):
        return False


def resolve_current_image_set(
    *,
    project_id: uuid.UUID,
    assets: list[ImageAsset],
    readiness_reviews: list[ImageSetReadinessReview],
    storage: ImageStoragePort,
) -> CurrentImageSet:
    """Derive the single governed ImageSet snapshot shared by Regions and Plans."""

    current_by_role = {asset.role: asset for asset in assets}
    object_available = {
        role: image_object_is_available(storage, asset) for role, asset in current_by_role.items()
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
        latest_readiness_review=latest,
        object_available_by_role=object_available,
    )


def effective_region_set_lifecycle(
    region_set: RegionSet,
    *,
    region_sets: list[RegionSet],
    reviews_by_set: dict[uuid.UUID, RegionSetReview],
) -> str:
    """Derive one immutable RegionSet snapshot's current effective lifecycle."""

    later_sets = [item for item in region_sets if item.version > region_set.version]
    if region_set.lifecycle == "draft":
        return "superseded" if later_sets else "draft"
    if region_set.lifecycle == "submitted":
        if any(item.lifecycle == "submitted" for item in later_sets):
            return "superseded"
        review = reviews_by_set.get(region_set.id)
        return region_set.lifecycle if review is None else review.verdict
    return region_set.lifecycle


def region_set_stale_reasons(
    region_set: RegionSet,
    current_image_set: CurrentImageSet,
) -> list[str]:
    """Return stable reasons that one exact RegionSet is no longer usable."""

    reasons: list[str] = []
    if current_image_set.status != "ready":
        reasons.append("image_set_not_ready")
    if region_set.source_image_set_fingerprint != current_image_set.fingerprint:
        reasons.append("image_set_fingerprint_changed")
    current_primary = current_image_set.primary
    if current_primary is None or region_set.source_primary_image_asset_id != current_primary.id:
        reasons.append("primary_front_changed")
    return reasons
