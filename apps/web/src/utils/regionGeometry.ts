import type { RegionDraftInput, RegionVertexInput } from "../api/regionSets";

const MIN_AREA_TWICE = 100_000_000;
const MAX_TOTAL_VERTICES = 8_192;

function orientation(
  first: RegionVertexInput,
  second: RegionVertexInput,
  third: RegionVertexInput,
): number {
  const value =
    (second.x_ppm - first.x_ppm) * (third.y_ppm - first.y_ppm) -
    (second.y_ppm - first.y_ppm) * (third.x_ppm - first.x_ppm);
  return Math.sign(value);
}

function onSegment(
  first: RegionVertexInput,
  second: RegionVertexInput,
  point: RegionVertexInput,
): boolean {
  return (
    point.x_ppm >= Math.min(first.x_ppm, second.x_ppm) &&
    point.x_ppm <= Math.max(first.x_ppm, second.x_ppm) &&
    point.y_ppm >= Math.min(first.y_ppm, second.y_ppm) &&
    point.y_ppm <= Math.max(first.y_ppm, second.y_ppm) &&
    orientation(first, second, point) === 0
  );
}

function segmentsIntersect(
  first: RegionVertexInput,
  second: RegionVertexInput,
  third: RegionVertexInput,
  fourth: RegionVertexInput,
): boolean {
  const values = [
    orientation(first, second, third),
    orientation(first, second, fourth),
    orientation(third, fourth, first),
    orientation(third, fourth, second),
  ];
  return (
    (values[0] !== values[1] && values[2] !== values[3]) ||
    (values[0] === 0 && onSegment(first, second, third)) ||
    (values[1] === 0 && onSegment(first, second, fourth)) ||
    (values[2] === 0 && onSegment(third, fourth, first)) ||
    (values[3] === 0 && onSegment(third, fourth, second))
  );
}

export function polygonAreaTwice(vertices: RegionVertexInput[]): number {
  return Math.abs(
    vertices.reduce((sum, vertex, index) => {
      const next = vertices[(index + 1) % vertices.length]!;
      return sum + vertex.x_ppm * next.y_ppm - next.x_ppm * vertex.y_ppm;
    }, 0),
  );
}

export function validateRegionDrafts(regions: RegionDraftInput[]): string[] {
  const errors: string[] = [];
  if (regions.length > 128) {
    errors.push("A snapshot can contain at most 128 regions.");
  }
  if (
    regions.reduce((count, region) => count + region.vertices.length, 0) >
    MAX_TOTAL_VERTICES
  ) {
    errors.push("A snapshot can contain at most 8,192 vertices.");
  }
  const stableKeys = new Set<string>();
  const zIndices = new Set<number>();
  for (const region of regions) {
    if (stableKeys.has(region.stable_region_key)) {
      errors.push(`Region “${region.label}” has a duplicate stable key.`);
    }
    stableKeys.add(region.stable_region_key);
    if (zIndices.has(region.z_index)) {
      errors.push(`Region “${region.label}” has a duplicate layer position.`);
    }
    zIndices.add(region.z_index);
    if (!region.label.trim() || region.label.length > 80) {
      errors.push("Every region needs a label of 80 characters or fewer.");
    }
    const vertices = region.vertices;
    if (vertices.length < 3 || vertices.length > 256) {
      errors.push(`Region “${region.label}” needs between 3 and 256 vertices.`);
      continue;
    }
    if (
      vertices.some(
        (vertex) =>
          !Number.isSafeInteger(vertex.x_ppm) ||
          !Number.isSafeInteger(vertex.y_ppm) ||
          vertex.x_ppm < 0 ||
          vertex.x_ppm > 1_000_000 ||
          vertex.y_ppm < 0 ||
          vertex.y_ppm > 1_000_000,
      )
    ) {
      errors.push(`Region “${region.label}” has an out-of-bounds vertex.`);
      continue;
    }
    if (
      vertices.some((vertex, index) => {
        const next = vertices[(index + 1) % vertices.length]!;
        return vertex.x_ppm === next.x_ppm && vertex.y_ppm === next.y_ppm;
      })
    ) {
      errors.push(`Region “${region.label}” has a zero-length edge.`);
      continue;
    }
    let selfIntersects = false;
    for (let first = 0; first < vertices.length && !selfIntersects; first += 1) {
      const firstNext = (first + 1) % vertices.length;
      for (let second = first + 1; second < vertices.length; second += 1) {
        const secondNext = (second + 1) % vertices.length;
        if (
          firstNext === second ||
          secondNext === first ||
          first === second
        ) {
          continue;
        }
        if (
          segmentsIntersect(
            vertices[first]!,
            vertices[firstNext]!,
            vertices[second]!,
            vertices[secondNext]!,
          )
        ) {
          selfIntersects = true;
          break;
        }
      }
    }
    if (selfIntersects) {
      errors.push(`Region “${region.label}” crosses itself.`);
    } else if (polygonAreaTwice(vertices) < MIN_AREA_TWICE) {
      errors.push(`Region “${region.label}” is too small.`);
    }
  }
  return errors;
}

export function persistedRegionsToDrafts(
  regions: Array<{
    stable_region_key: string;
    kind: "paint" | "exclude";
    label: string;
    z_index: number;
    opacity_ppm: number;
    notes: string | null;
    vertices: RegionVertexInput[];
  }>,
): RegionDraftInput[] {
  return regions.map((region) => ({
    stable_region_key: region.stable_region_key,
    kind: region.kind,
    label: region.label,
    z_index: region.z_index,
    opacity_ppm: region.opacity_ppm,
    notes: region.notes,
    vertices: region.vertices.map((vertex) => ({
      x_ppm: vertex.x_ppm,
      y_ppm: vertex.y_ppm,
    })),
  }));
}
