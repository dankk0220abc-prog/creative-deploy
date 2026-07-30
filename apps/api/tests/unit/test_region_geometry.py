"""Deterministic unit coverage for Phase 1F geometry and strict schemas."""

import hashlib
import json
import uuid
from decimal import Decimal
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from creativedeploy_api.schemas.region_sets import (
    CreateRegionSetReviewRequest,
    RegionDraftInput,
    RegionVertexInput,
    SaveRegionSetRequest,
)
from creativedeploy_api.services.region_geometry import (
    GEOMETRY_FINGERPRINT_VERSION,
    MIN_POLYGON_AREA_TWICE_PPM_SQUARED,
    RegionGeometryValidationError,
    geometry_fingerprint,
    pixel_to_ppm,
    polygon_area_twice,
    ppm_to_pixel,
    validate_region_snapshot,
)
from creativedeploy_api.services.region_sets import (
    CurrentImageSet,
    RegionGeometryApplicationError,
    RegionSetService,
)


def _region(
    *,
    key: uuid.UUID | None = None,
    kind: str = "paint",
    label: str = " Hair ",
    z_index: int = 0,
    points: list[tuple[int, int]] | None = None,
) -> RegionDraftInput:
    return RegionDraftInput.model_validate(
        {
            "stable_region_key": key or uuid.uuid4(),
            "kind": kind,
            "label": label,
            "z_index": z_index,
            "opacity_ppm": 500_000,
            "notes": " Human-authored annotation. ",
            "vertices": [
                {"x_ppm": x_ppm, "y_ppm": y_ppm}
                for x_ppm, y_ppm in (
                    points
                    or [
                        (100_000, 100_000),
                        (500_000, 100_000),
                        (500_000, 500_000),
                        (100_000, 500_000),
                    ]
                )
            ],
        }
    )


def test_coordinate_conversion_is_clamped_and_rounds_half_up() -> None:
    assert pixel_to_ppm(0, 200) == 0
    assert pixel_to_ppm(200, 200) == 1_000_000
    assert pixel_to_ppm(100, 200) == 500_000
    assert pixel_to_ppm(1, 3) == 333_333
    assert pixel_to_ppm(2, 3) == 666_667
    assert pixel_to_ppm(-20, 200) == 0
    assert pixel_to_ppm(220, 200) == 1_000_000
    assert ppm_to_pixel(250_000, 800) == Decimal(200)
    with pytest.raises(ValueError):
        pixel_to_ppm(0, 0)
    with pytest.raises(ValueError):
        ppm_to_pixel(1_000_001, 100)


def test_valid_snapshot_normalizes_labels_sorts_and_warns_on_overlap() -> None:
    first = _region(label="\uff28\uff21\uff29\uff32", z_index=1)
    second = _region(
        kind="exclude",
        label=" background ",
        z_index=0,
        points=[
            (400_000, 400_000),
            (700_000, 400_000),
            (700_000, 700_000),
            (400_000, 700_000),
        ],
    )
    snapshot = validate_region_snapshot([first, second])
    assert [item.source.z_index for item in snapshot.regions] == [0, 1]
    assert snapshot.regions[1].normalized_label == "hair"
    assert snapshot.total_vertex_count == 8
    assert snapshot.overlap_warnings == (
        f"overlap:{second.stable_region_key}:{first.stable_region_key}",
    )
    assert snapshot.regions[0].summary.bbox_min_x_ppm == 400_000


@pytest.mark.parametrize(
    ("points", "code"),
    [
        (
            [
                (100_000, 100_000),
                (500_000, 500_000),
                (100_000, 500_000),
                (500_000, 100_000),
            ],
            "polygon_self_intersection",
        ),
        (
            [
                (100_000, 100_000),
                (500_000, 100_000),
                (500_000, 100_000),
                (100_000, 500_000),
            ],
            "zero_length_edge",
        ),
        (
            [
                (100_000, 100_000),
                (500_000, 100_000),
                (100_000, 500_000),
                (500_000, 100_000),
            ],
            "repeated_vertex",
        ),
        (
            [
                (100_000, 100_000),
                (100_001, 100_000),
                (100_000, 100_001),
            ],
            "polygon_area_too_small",
        ),
    ],
)
def test_invalid_polygon_failure_codes_are_stable(
    points: list[tuple[int, int]],
    code: str,
) -> None:
    with pytest.raises(RegionGeometryValidationError) as captured:
        validate_region_snapshot([_region(points=points)])
    assert captured.value.code == code
    assert captured.value.stable_region_key is not None


def test_area_is_exact_integer_and_threshold_is_centralized() -> None:
    points = ((0, 0), (1_000_000, 0), (1_000_000, 1_000_000), (0, 1_000_000))
    assert polygon_area_twice(points) == 2_000_000_000_000
    assert MIN_POLYGON_AREA_TWICE_PPM_SQUARED == 100_000_000


def test_schema_rejects_unsafe_labels_controls_unknown_fields_and_duplicate_order() -> None:
    with pytest.raises(ValidationError):
        _region(label="<b>hair</b>")
    with pytest.raises(ValidationError):
        _region(label="hair\nface")
    with pytest.raises(ValidationError):
        RegionDraftInput.model_validate(
            {
                **_region().model_dump(mode="python"),
                "kind": "semantic",
            }
        )
    with pytest.raises(ValidationError):
        RegionVertexInput.model_validate({"x_ppm": 1_000_001, "y_ppm": 0})
    first = _region(z_index=0)
    second = _region(z_index=0)
    with pytest.raises(ValidationError):
        SaveRegionSetRequest(base_version=None, base_region_set_id=None, regions=[first, second])
    with pytest.raises(ValidationError):
        SaveRegionSetRequest.model_validate(
            {"base_version": None, "base_region_set_id": None, "regions": [], "owner_id": "x"}
        )


def test_changes_requested_reason_is_required_and_trimmed() -> None:
    request = CreateRegionSetReviewRequest(
        verdict="changes_requested",
        reason=" Adjust the boots boundary. ",
    )
    assert request.reason == "Adjust the boots boundary."
    with pytest.raises(ValidationError):
        CreateRegionSetReviewRequest(verdict="changes_requested", reason=" ")


def test_geometry_fingerprint_expected_is_computed_independently() -> None:
    project_id = uuid.UUID("10000000-0000-4000-8000-000000000001")
    image_asset_id = uuid.UUID("20000000-0000-4000-8000-000000000001")
    stable_key = uuid.UUID("30000000-0000-4000-8000-000000000001")
    region = _region(key=stable_key, label=" Hair ")
    snapshot = validate_region_snapshot([region])
    actual = geometry_fingerprint(
        project_id=project_id,
        source_image_set_fingerprint="a" * 64,
        source_primary_image_asset_id=image_asset_id,
        version=7,
        snapshot=snapshot,
    )
    independently_built = {
        "paint_project_id": str(project_id),
        "regions": [
            {
                "kind": "paint",
                "label": "Hair",
                "normalized_label": "hair",
                "notes": "Human-authored annotation.",
                "opacity_ppm": 500_000,
                "stable_region_key": str(stable_key),
                "vertices": [
                    {"sequence": 0, "x_ppm": 100_000, "y_ppm": 100_000},
                    {"sequence": 1, "x_ppm": 500_000, "y_ppm": 100_000},
                    {"sequence": 2, "x_ppm": 500_000, "y_ppm": 500_000},
                    {"sequence": 3, "x_ppm": 100_000, "y_ppm": 500_000},
                ],
                "z_index": 0,
            }
        ],
        "region_set_version": 7,
        "source_image_set_fingerprint": "a" * 64,
        "source_primary_image_asset_id": str(image_asset_id),
        "version": GEOMETRY_FINGERPRINT_VERSION,
    }
    expected = hashlib.sha256(
        json.dumps(
            independently_built,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    assert actual == expected


def test_snapshot_budgets_fail_closed_at_contract_limits() -> None:
    regions = [_region(z_index=index) for index in range(128)]
    regions.append(
        regions[0].model_copy(update={"stable_region_key": uuid.uuid4(), "z_index": 128})
    )
    with pytest.raises(RegionGeometryValidationError) as region_error:
        validate_region_snapshot(regions)
    assert region_error.value.code == "region_budget_exceeded"

    oversized = _region()
    object.__setattr__(
        oversized,
        "vertices",
        [
            RegionVertexInput(x_ppm=index % 1_000_001, y_ppm=index % 1_000_001)
            for index in range(8193)
        ],
    )
    with pytest.raises(RegionGeometryValidationError) as vertex_error:
        validate_region_snapshot([oversized])
    assert vertex_error.value.code == "total_vertex_budget_exceeded"


def test_effective_lifecycle_and_stale_facts_are_derived_without_mutation() -> None:
    draft = SimpleNamespace(id=uuid.uuid4(), version=1, lifecycle="draft")
    submitted = SimpleNamespace(id=uuid.uuid4(), version=2, lifecycle="submitted")
    review = SimpleNamespace(region_set_id=submitted.id, verdict="approved")
    assert (
        RegionSetService._effective_lifecycle(
            draft,
            region_sets=[submitted, draft],
            reviews_by_set={submitted.id: review},
        )
        == "superseded"
    )
    assert (
        RegionSetService._effective_lifecycle(
            submitted,
            region_sets=[submitted, draft],
            reviews_by_set={submitted.id: review},
        )
        == "approved"
    )
    primary_id = uuid.uuid4()
    region_set = SimpleNamespace(
        source_image_set_fingerprint="a" * 64,
        source_primary_image_asset_id=primary_id,
    )
    current = CurrentImageSet(
        fingerprint="b" * 64,
        status="ready",
        current_by_role={
            "primary_front": SimpleNamespace(id=primary_id),
        },
    )
    assert RegionSetService._stale_reasons(region_set, current) == ["image_set_fingerprint_changed"]
    assert draft.lifecycle == "draft"
    assert submitted.lifecycle == "submitted"


def test_geometry_application_error_exposes_only_stable_safe_details() -> None:
    stable_key = uuid.uuid4()
    error = RegionGeometryApplicationError(
        RegionGeometryValidationError(
            "polygon_self_intersection",
            stable_region_key=stable_key,
        )
    )
    assert dict(error.safe_details) == {
        "geometry_code": "polygon_self_intersection",
        "stable_region_key": str(stable_key),
    }
    assert "coordinates" not in str(error.safe_details)
