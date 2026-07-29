"""Independent deterministic ImageSet readiness contract tests."""

import hashlib
import io
import json
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from creativedeploy_api.core.config import Settings
from creativedeploy_api.db.models import ImageAsset, ImageSetReadinessReview
from creativedeploy_api.schemas.image_assets import (
    CreateImageAssetRequest,
    CreateReadinessReviewRequest,
)
from creativedeploy_api.services.image_assets import (
    ImageAssetService,
    evaluate_image_asset_mutation,
    image_set_fingerprint,
)
from creativedeploy_api.storage.images import ImageStoragePort

PROJECT_ID = uuid.UUID("11111111-1111-4111-8111-111111111111")
OWNER_ID = "image-set-unit-owner"
NOW = datetime(2026, 7, 29, tzinfo=UTC)
ROLES = (
    "primary_front",
    "reference_back",
    "reference_angle",
    "reference_detail",
)
WORKFLOW_STATES = (
    "DRAFT",
    "IMAGE_UPLOADED",
    "IMAGE_REVIEW_REQUIRED",
    "IMAGE_VALIDATION_FAILED",
    "IMAGE_VALIDATED",
    "REGION_ANALYSIS_RUNNING",
    "REGION_REVIEW_REQUIRED",
    "REGIONS_CONFIRMED",
    "PLAN_GENERATION_RUNNING",
    "PLAN_REVIEW_REQUIRED",
    "PLAN_APPROVED",
    "COMPLETED",
    "BLOCKED_LOW_CONFIDENCE",
    "FAILED_RETRYABLE",
    "FAILED_FINAL",
    "ABANDONED",
)
EXPECTED_MUTATION_STATES = {
    ("primary_front", False): frozenset({"DRAFT"}),
    ("primary_front", True): frozenset({"IMAGE_REVIEW_REQUIRED", "IMAGE_VALIDATION_FAILED"}),
    ("reference_back", False): frozenset(
        {
            "DRAFT",
            "IMAGE_UPLOADED",
            "IMAGE_REVIEW_REQUIRED",
            "IMAGE_VALIDATION_FAILED",
        }
    ),
    ("reference_back", True): frozenset(
        {
            "DRAFT",
            "IMAGE_UPLOADED",
            "IMAGE_REVIEW_REQUIRED",
            "IMAGE_VALIDATION_FAILED",
        }
    ),
    ("reference_angle", False): frozenset(
        {
            "DRAFT",
            "IMAGE_UPLOADED",
            "IMAGE_REVIEW_REQUIRED",
            "IMAGE_VALIDATION_FAILED",
        }
    ),
    ("reference_angle", True): frozenset(
        {
            "DRAFT",
            "IMAGE_UPLOADED",
            "IMAGE_REVIEW_REQUIRED",
            "IMAGE_VALIDATION_FAILED",
        }
    ),
    ("reference_detail", False): frozenset(
        {
            "DRAFT",
            "IMAGE_UPLOADED",
            "IMAGE_REVIEW_REQUIRED",
            "IMAGE_VALIDATION_FAILED",
        }
    ),
    ("reference_detail", True): frozenset(
        {
            "DRAFT",
            "IMAGE_UPLOADED",
            "IMAGE_REVIEW_REQUIRED",
            "IMAGE_VALIDATION_FAILED",
        }
    ),
}


class MemoryStorage:
    """Minimal immutable private-object view used only for readiness facts."""

    def __init__(self, objects: dict[str, bytes]) -> None:
        self.objects = objects

    def stat(self, key: str) -> SimpleNamespace:
        try:
            data = self.objects[key]
        except KeyError as error:
            raise FileNotFoundError(key) from error
        return SimpleNamespace(st_size=len(data))

    def open_private(self, key: str) -> io.BytesIO:
        try:
            return io.BytesIO(self.objects[key])
        except KeyError as error:
            raise FileNotFoundError(key) from error


def _asset(
    role: str,
    data: bytes,
    *,
    sequence: int,
    rights_status: str = "confirmed",
) -> ImageAsset:
    digest = hashlib.sha256(data).hexdigest()
    asset = ImageAsset(
        id=uuid.UUID(f"00000000-0000-4000-8000-{sequence:012d}"),
        paint_project_id=PROJECT_ID,
        owner_principal_id=OWNER_ID,
        role=role,
        version=1,
        supersedes_image_asset_id=None,
        is_current=True,
        lifecycle_status="current",
        storage_provider="local_filesystem",
        storage_key=f"objects/aa/{sequence:032x}.jpg",
        original_filename=f"{role}.jpg",
        declared_content_type="image/jpeg",
        detected_format="jpeg",
        byte_size=len(data),
        width=768,
        height=768,
        pixel_count=768 * 768,
        color_mode="RGB",
        has_alpha=False,
        exif_orientation=None,
        sha256=digest,
        upload_validation_result="accepted",
        upload_validation_details={"fully_decoded": True},
        source_type="user_provided",
        rights_attestation_status=rights_status,
        rights_attestation_version=1,
        intended_usage=["private_project"],
        rights_attested_by_principal_id=(OWNER_ID if rights_status == "confirmed" else None),
        rights_attested_at=NOW if rights_status == "confirmed" else None,
        created_by_actor_type="user",
        created_by_actor_id=OWNER_ID,
        created_by_actor_display_name_snapshot="Image Set Unit Owner",
        created_at=NOW,
    )
    asset._unit_bytes = data  # type: ignore[attr-defined]
    return asset


def _service(
    settings: Settings,
    assets: list[ImageAsset],
    *,
    unavailable_roles: set[str] | None = None,
) -> ImageAssetService:
    unavailable = unavailable_roles or set()
    objects = {
        asset.storage_key: cast(bytes, asset._unit_bytes)  # type: ignore[attr-defined]
        for asset in assets
        if asset.role not in unavailable
    }
    for asset in assets:
        if asset.role not in unavailable:
            data = objects[asset.storage_key]
            asset.byte_size = len(data)
            asset.sha256 = hashlib.sha256(data).hexdigest()
    return ImageAssetService(
        cast(AsyncSession, object()),
        cast(ImageStoragePort, MemoryStorage(objects)),
        settings,
    )


def test_formal_roles_reject_legacy_and_arbitrary_strings() -> None:
    base = {
        "source_type": "user_provided",
        "intended_usage": ["private_project"],
        "rights_attestation_confirmed": True,
        "rights_attestation_version": 1,
    }
    for role in ROLES:
        assert CreateImageAssetRequest.model_validate({**base, "role": role}).role == role
    for role in ("primary_mvp_input", "side", ""):
        with pytest.raises(ValidationError):
            CreateImageAssetRequest.model_validate({**base, "role": role})


@pytest.mark.parametrize(
    ("role", "has_current_asset"),
    EXPECTED_MUTATION_STATES,
)
def test_role_aware_mutation_policy_matches_independent_workflow_matrix(
    role: str,
    has_current_asset: bool,
) -> None:
    expected_states = EXPECTED_MUTATION_STATES[(role, has_current_asset)]
    expected_operation = "replacement" if has_current_asset else "first_upload"
    for state in WORKFLOW_STATES:
        decision = evaluate_image_asset_mutation(
            role=role,
            has_current_asset=has_current_asset,
            project_state=state,
        )
        assert decision.operation == expected_operation
        assert decision.allowed is (state in expected_states)


def test_role_aware_mutation_policy_fails_closed_for_unknown_role_and_state() -> None:
    assert (
        evaluate_image_asset_mutation(
            role="unknown_role",
            has_current_asset=False,
            project_state="DRAFT",
        ).allowed
        is False
    )
    assert (
        evaluate_image_asset_mutation(
            role="reference_back",
            has_current_asset=True,
            project_state="UNKNOWN_STATE",
        ).allowed
        is False
    )


def test_readiness_request_requires_reason_and_rejects_client_snapshot() -> None:
    with pytest.raises(ValidationError):
        CreateReadinessReviewRequest.model_validate({"verdict": "not_ready", "reason": "  "})
    with pytest.raises(ValidationError):
        CreateReadinessReviewRequest.model_validate(
            {
                "verdict": "ready",
                "reason": None,
                "primary_front_image_asset_id": str(uuid.uuid4()),
            }
        )
    request = CreateReadinessReviewRequest.model_validate(
        {"verdict": "not_ready", "reason": "  Needs another angle.  "}
    )
    assert request.reason == "Needs another angle."


def test_required_roles_optional_detail_and_distinct_content_gate(
    test_settings: Settings,
) -> None:
    assets = [
        _asset("primary_front", b"front", sequence=1),
        _asset("reference_back", b"back", sequence=2),
        _asset("reference_angle", b"angle", sequence=3),
    ]
    facts = _service(test_settings, assets)._image_set_facts(
        project_id=PROJECT_ID,
        current_assets=assets,
    )
    assert facts.checklist.required_roles_present is True
    assert facts.checklist.content_distinct is True
    assert facts.checklist.can_mark_ready is True

    missing = _service(test_settings, assets[:2])._image_set_facts(
        project_id=PROJECT_ID,
        current_assets=assets[:2],
    )
    assert "missing_required_roles" in missing.checklist.blockers

    duplicate_assets = [
        _asset("primary_front", b"same", sequence=4),
        _asset("reference_back", b"same", sequence=5),
        _asset("reference_angle", b"other", sequence=6),
    ]
    duplicate = _service(test_settings, duplicate_assets)._image_set_facts(
        project_id=PROJECT_ID,
        current_assets=duplicate_assets,
    )
    assert duplicate.checklist.content_distinct is False
    assert "duplicate_or_missing_required_content" in duplicate.checklist.blockers


def test_rights_and_private_object_availability_fail_closed(
    test_settings: Settings,
) -> None:
    assets = [
        _asset("primary_front", b"front", sequence=7),
        _asset(
            "reference_back",
            b"back",
            sequence=8,
            rights_status="pending",
        ),
        _asset("reference_angle", b"angle", sequence=9),
    ]
    facts = _service(
        test_settings,
        assets,
        unavailable_roles={"reference_angle"},
    )._image_set_facts(project_id=PROJECT_ID, current_assets=assets)
    assert facts.checklist.rights_complete is False
    assert facts.checklist.objects_available is False
    assert facts.checklist.can_mark_ready is False
    assert "rights_attestation_incomplete" in facts.checklist.blockers
    assert "private_object_unavailable" in facts.checklist.blockers


def test_fingerprint_matches_independent_canonical_serialization(
    test_settings: Settings,
) -> None:
    assets = [
        _asset("primary_front", b"front", sequence=10),
        _asset("reference_back", b"back", sequence=11),
        _asset("reference_angle", b"angle", sequence=12),
    ]
    facts = _service(test_settings, assets)._image_set_facts(
        project_id=PROJECT_ID,
        current_assets=assets,
    )
    current = {asset.role: asset for asset in assets}
    roles = []
    for role in ROLES:
        asset = current.get(role)
        roles.append(
            {
                "image_asset_id": None if asset is None else str(asset.id),
                "missing": asset is None,
                "object_available": role in current,
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
    expected = hashlib.sha256(
        json.dumps(
            {
                "paint_project_id": str(PROJECT_ID),
                "roles": roles,
                "version": "paintpilot_image_set_fingerprint.v1",
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    assert facts.fingerprint == expected
    assert facts.fingerprint == image_set_fingerprint(
        project_id=PROJECT_ID,
        current_by_role=current,
        object_available_by_role={role: True for role in current},
    )


def test_ready_review_becomes_stale_after_required_role_change(
    test_settings: Settings,
) -> None:
    assets = [
        _asset("primary_front", b"front", sequence=13),
        _asset("reference_back", b"back", sequence=14),
        _asset("reference_angle", b"angle", sequence=15),
    ]
    service = _service(test_settings, assets)
    facts = service._image_set_facts(
        project_id=PROJECT_ID,
        current_assets=assets,
    )
    review = ImageSetReadinessReview(
        id=uuid.uuid4(),
        owner_principal_id=OWNER_ID,
        paint_project_id=PROJECT_ID,
        version=1,
        verdict="ready",
        reason=None,
        primary_front_image_asset_id=assets[0].id,
        primary_front_role="primary_front",
        reference_back_image_asset_id=assets[1].id,
        reference_back_role="reference_back",
        reference_angle_image_asset_id=assets[2].id,
        reference_angle_role="reference_angle",
        reference_detail_image_asset_id=None,
        reference_detail_role=None,
        image_set_fingerprint=facts.fingerprint,
        actor_type="user",
        actor_id=OWNER_ID,
        actor_display_name_snapshot="Image Set Unit Owner",
        created_at=NOW,
    )
    assert (
        service._image_set_read(
            project_id=PROJECT_ID,
            assets=assets,
            reviews=[review],
        ).status
        == "ready"
    )

    replacement = _asset("reference_angle", b"new-angle", sequence=16)
    changed_assets = [assets[0], assets[1], replacement]
    changed = _service(test_settings, changed_assets)._image_set_read(
        project_id=PROJECT_ID,
        assets=changed_assets,
        reviews=[review],
    )
    assert changed.status == "stale"
    assert changed.stale_reasons == ["reference_angle_changed"]
