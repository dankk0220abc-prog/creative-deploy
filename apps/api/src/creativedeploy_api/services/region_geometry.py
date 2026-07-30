"""Deterministic simple-Polygon validation and canonical fingerprinting."""

import hashlib
import json
import unicodedata
import uuid
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from fractions import Fraction

from creativedeploy_api.db.models.region_set import (
    MAX_REGIONS_PER_SET,
    MAX_VERTICES_PER_REGION,
    MAX_VERTICES_PER_SET,
    PPM_MAX,
)
from creativedeploy_api.schemas.region_sets import RegionDraftInput

MIN_POLYGON_AREA_TWICE_PPM_SQUARED = 100_000_000
GEOMETRY_FINGERPRINT_VERSION = "paintpilot_region_geometry_fingerprint.v1"

Point = tuple[int, int]


class RegionGeometryValidationError(ValueError):
    """A safe deterministic geometry failure with one stable public code."""

    def __init__(self, code: str, *, stable_region_key: uuid.UUID | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.stable_region_key = stable_region_key


@dataclass(frozen=True, slots=True)
class GeometrySummary:
    """Deterministic integer summaries for one valid Polygon."""

    area_twice_ppm_squared: int
    bbox_min_x_ppm: int
    bbox_min_y_ppm: int
    bbox_max_x_ppm: int
    bbox_max_y_ppm: int


@dataclass(frozen=True, slots=True)
class ValidatedRegion:
    """One normalized human Region ready for persistence."""

    source: RegionDraftInput
    normalized_label: str
    summary: GeometrySummary


@dataclass(frozen=True, slots=True)
class ValidatedRegionSnapshot:
    """A bounded, canonical RegionSet payload and non-blocking warnings."""

    regions: tuple[ValidatedRegion, ...]
    total_vertex_count: int
    overlap_warnings: tuple[str, ...]


def pixel_to_ppm(pixel: Decimal | int | float, extent: int) -> int:
    """Convert a display pixel coordinate to a clamped deterministic ppm integer."""
    if extent <= 0:
        raise ValueError("extent must be positive")
    value = Decimal(str(pixel))
    converted = int(
        (value * Decimal(PPM_MAX) / Decimal(extent)).quantize(
            Decimal("1"),
            rounding=ROUND_HALF_UP,
        )
    )
    return max(0, min(PPM_MAX, converted))


def ppm_to_pixel(ppm: int, extent: int) -> Decimal:
    """Convert a validated ppm coordinate to an exact display pixel Decimal."""
    if not 0 <= ppm <= PPM_MAX:
        raise ValueError("ppm must be in bounds")
    if extent <= 0:
        raise ValueError("extent must be positive")
    return Decimal(ppm) * Decimal(extent) / Decimal(PPM_MAX)


def normalize_label(label: str) -> str:
    """Create a deterministic search label without changing the display label."""
    normalized = unicodedata.normalize("NFKC", label).casefold().strip()
    normalized = " ".join(normalized.split())
    if not normalized or len(normalized) > 80:
        raise RegionGeometryValidationError("normalized_label_invalid")
    return normalized


def _orientation(a: Point, b: Point, c: Point) -> int:
    value = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
    return (value > 0) - (value < 0)


def _on_segment(a: Point, b: Point, point: Point) -> bool:
    return (
        min(a[0], b[0]) <= point[0] <= max(a[0], b[0])
        and min(a[1], b[1]) <= point[1] <= max(a[1], b[1])
        and _orientation(a, b, point) == 0
    )


def _segments_intersect(a: Point, b: Point, c: Point, d: Point) -> bool:
    orientations = (
        _orientation(a, b, c),
        _orientation(a, b, d),
        _orientation(c, d, a),
        _orientation(c, d, b),
    )
    if orientations[0] != orientations[1] and orientations[2] != orientations[3]:
        return True
    return (
        (orientations[0] == 0 and _on_segment(a, b, c))
        or (orientations[1] == 0 and _on_segment(a, b, d))
        or (orientations[2] == 0 and _on_segment(c, d, a))
        or (orientations[3] == 0 and _on_segment(c, d, b))
    )


def polygon_area_twice(points: tuple[Point, ...]) -> int:
    """Return the absolute exact shoelace double-area."""
    return abs(
        sum(
            point[0] * points[(index + 1) % len(points)][1]
            - points[(index + 1) % len(points)][0] * point[1]
            for index, point in enumerate(points)
        )
    )


def _validate_simple_polygon(points: tuple[Point, ...], key: uuid.UUID) -> GeometrySummary:
    if not 3 <= len(points) <= MAX_VERTICES_PER_REGION:
        raise RegionGeometryValidationError("vertex_count_invalid", stable_region_key=key)
    if any(not 0 <= coordinate <= PPM_MAX for point in points for coordinate in point):
        raise RegionGeometryValidationError("coordinate_out_of_bounds", stable_region_key=key)
    if any(points[index] == points[(index + 1) % len(points)] for index in range(len(points))):
        raise RegionGeometryValidationError("zero_length_edge", stable_region_key=key)
    if len(set(points)) != len(points):
        raise RegionGeometryValidationError("repeated_vertex", stable_region_key=key)

    edge_count = len(points)
    for first_index in range(edge_count):
        first_next = (first_index + 1) % edge_count
        for second_index in range(first_index + 1, edge_count):
            second_next = (second_index + 1) % edge_count
            if (
                first_index == second_index
                or first_next == second_index
                or second_next == first_index
            ):
                continue
            if _segments_intersect(
                points[first_index],
                points[first_next],
                points[second_index],
                points[second_next],
            ):
                raise RegionGeometryValidationError(
                    "polygon_self_intersection",
                    stable_region_key=key,
                )

    area_twice = polygon_area_twice(points)
    if area_twice < MIN_POLYGON_AREA_TWICE_PPM_SQUARED:
        raise RegionGeometryValidationError("polygon_area_too_small", stable_region_key=key)
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return GeometrySummary(
        area_twice_ppm_squared=area_twice,
        bbox_min_x_ppm=min(xs),
        bbox_min_y_ppm=min(ys),
        bbox_max_x_ppm=max(xs),
        bbox_max_y_ppm=max(ys),
    )


def _point_in_polygon(point: Point, polygon: tuple[Point, ...]) -> bool:
    inside = False
    x, y = point
    previous = polygon[-1]
    for current in polygon:
        if _on_segment(previous, current, point):
            return True
        if (current[1] > y) != (previous[1] > y):
            intersection_x = (
                Fraction(
                    (previous[0] - current[0]) * (y - current[1]),
                    previous[1] - current[1],
                )
                + current[0]
            )
            if x < intersection_x:
                inside = not inside
        previous = current
    return inside


def polygons_overlap(first: tuple[Point, ...], second: tuple[Point, ...]) -> bool:
    """Return a deterministic warning fact; overlap is intentionally allowed."""
    for first_index, first_start in enumerate(first):
        first_end = first[(first_index + 1) % len(first)]
        for second_index, second_start in enumerate(second):
            second_end = second[(second_index + 1) % len(second)]
            if _segments_intersect(first_start, first_end, second_start, second_end):
                return True
    return _point_in_polygon(first[0], second) or _point_in_polygon(second[0], first)


def validate_region_snapshot(regions: list[RegionDraftInput]) -> ValidatedRegionSnapshot:
    """Validate budgets, simple geometry, canonical order, and overlap warnings."""
    if len(regions) > MAX_REGIONS_PER_SET:
        raise RegionGeometryValidationError("region_budget_exceeded")
    total_vertices = sum(len(region.vertices) for region in regions)
    if total_vertices > MAX_VERTICES_PER_SET:
        raise RegionGeometryValidationError("total_vertex_budget_exceeded")
    stable_keys = [region.stable_region_key for region in regions]
    if len(stable_keys) != len(set(stable_keys)):
        raise RegionGeometryValidationError("duplicate_stable_region_key")
    z_indices = [region.z_index for region in regions]
    if len(z_indices) != len(set(z_indices)):
        raise RegionGeometryValidationError("duplicate_z_index")

    validated: list[ValidatedRegion] = []
    polygons: dict[uuid.UUID, tuple[Point, ...]] = {}
    for region in sorted(regions, key=lambda item: (item.z_index, str(item.stable_region_key))):
        points = tuple((vertex.x_ppm, vertex.y_ppm) for vertex in region.vertices)
        summary = _validate_simple_polygon(points, region.stable_region_key)
        validated.append(
            ValidatedRegion(
                source=region,
                normalized_label=normalize_label(region.label),
                summary=summary,
            )
        )
        polygons[region.stable_region_key] = points

    warnings: list[str] = []
    for first_index, first in enumerate(validated):
        for second in validated[first_index + 1 :]:
            if polygons_overlap(
                polygons[first.source.stable_region_key],
                polygons[second.source.stable_region_key],
            ):
                warnings.append(
                    f"overlap:{first.source.stable_region_key}:{second.source.stable_region_key}"
                )
    return ValidatedRegionSnapshot(
        regions=tuple(validated),
        total_vertex_count=total_vertices,
        overlap_warnings=tuple(warnings),
    )


def geometry_fingerprint(
    *,
    project_id: uuid.UUID,
    source_image_set_fingerprint: str,
    source_primary_image_asset_id: uuid.UUID,
    version: int,
    snapshot: ValidatedRegionSnapshot,
) -> str:
    """SHA-256 a fixed path-free canonical serialization of the full snapshot."""
    canonical_regions: list[dict[str, object]] = []
    for validated in snapshot.regions:
        region = validated.source
        canonical_regions.append(
            {
                "kind": region.kind,
                "label": region.label,
                "normalized_label": validated.normalized_label,
                "notes": region.notes,
                "opacity_ppm": region.opacity_ppm,
                "stable_region_key": str(region.stable_region_key),
                "vertices": [
                    {
                        "sequence": sequence,
                        "x_ppm": vertex.x_ppm,
                        "y_ppm": vertex.y_ppm,
                    }
                    for sequence, vertex in enumerate(region.vertices)
                ],
                "z_index": region.z_index,
            }
        )
    canonical = {
        "paint_project_id": str(project_id),
        "regions": canonical_regions,
        "region_set_version": version,
        "source_image_set_fingerprint": source_image_set_fingerprint,
        "source_primary_image_asset_id": str(source_primary_image_asset_id),
        "version": GEOMETRY_FINGERPRINT_VERSION,
    }
    encoded = json.dumps(
        canonical,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
