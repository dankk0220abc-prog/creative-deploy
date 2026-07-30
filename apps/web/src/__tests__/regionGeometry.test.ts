import { describe, expect, it } from "vitest";

import type { RegionDraftInput } from "../api/regionSets";
import {
  persistedRegionsToDrafts,
  polygonAreaTwice,
  validateRegionDrafts,
} from "../utils/regionGeometry";

const key = "88888888-8888-4888-8888-888888888888";

function region(vertices: RegionDraftInput["vertices"]): RegionDraftInput {
  return {
    stable_region_key: key,
    kind: "paint",
    label: "shirt",
    z_index: 0,
    opacity_ppm: 500_000,
    notes: null,
    vertices,
  };
}

function polygonVertices(count: number): RegionDraftInput["vertices"] {
  return Array.from({ length: count }, (_, index) => {
    const angle = (Math.PI * 2 * index) / count;
    return {
      x_ppm: Math.round(500_000 + Math.cos(angle) * 300_000),
      y_ppm: Math.round(500_000 + Math.sin(angle) * 300_000),
    };
  });
}

function snapshotWithVertexCounts(counts: number[]): RegionDraftInput[] {
  return counts.map((count, index) => ({
    ...region(polygonVertices(count)),
    stable_region_key: `contract-region-${index}`,
    label: `region ${index}`,
    z_index: index,
  }));
}

describe("client region geometry", () => {
  it("uses exact integer shoelace area for a valid simple polygon", () => {
    const vertices = [
      { x_ppm: 100_000, y_ppm: 100_000 },
      { x_ppm: 300_000, y_ppm: 100_000 },
      { x_ppm: 300_000, y_ppm: 300_000 },
      { x_ppm: 100_000, y_ppm: 300_000 },
    ];
    expect(polygonAreaTwice(vertices)).toBe(80_000_000_000);
    expect(validateRegionDrafts([region(vertices)])).toEqual([]);
  });

  it("rejects a crossing polygon before an API command", () => {
    expect(
      validateRegionDrafts([
        region([
          { x_ppm: 100_000, y_ppm: 100_000 },
          { x_ppm: 300_000, y_ppm: 300_000 },
          { x_ppm: 100_000, y_ppm: 300_000 },
          { x_ppm: 300_000, y_ppm: 100_000 },
        ]),
      ]),
    ).toContain("Region “shirt” crosses itself.");
  });

  it("copies persisted vertices without leaking response-only fields", () => {
    const persistedVertices = [
      { sequence: 0, x_ppm: 100_000, y_ppm: 100_000 },
      { sequence: 1, x_ppm: 300_000, y_ppm: 100_000 },
      { sequence: 2, x_ppm: 200_000, y_ppm: 300_000 },
    ];
    expect(
      persistedRegionsToDrafts([
        {
          ...region([
            { x_ppm: 100_000, y_ppm: 100_000 },
            { x_ppm: 300_000, y_ppm: 100_000 },
            { x_ppm: 200_000, y_ppm: 300_000 },
          ]),
          vertices: persistedVertices,
        },
      ]),
    ).toEqual([
      region([
        { x_ppm: 100_000, y_ppm: 100_000 },
        { x_ppm: 300_000, y_ppm: 100_000 },
        { x_ppm: 200_000, y_ppm: 300_000 },
      ]),
    ]);
  });

  it("accepts the independent 4,097 and 8,192 total-vertex contract edges", () => {
    const total4097 = snapshotWithVertexCounts([
      ...Array.from({ length: 15 }, () => 256),
      254,
      3,
    ]);
    const total8192 = snapshotWithVertexCounts(
      Array.from({ length: 32 }, () => 256),
    );

    expect(total4097.reduce((sum, item) => sum + item.vertices.length, 0)).toBe(
      4097,
    );
    expect(validateRegionDrafts(total4097)).toEqual([]);
    expect(total8192.reduce((sum, item) => sum + item.vertices.length, 0)).toBe(
      8192,
    );
    expect(validateRegionDrafts(total8192)).toEqual([]);
  });

  it("rejects 8,193 total vertices without changing other contract limits", () => {
    const total8193 = snapshotWithVertexCounts([
      ...Array.from({ length: 31 }, () => 256),
      254,
      3,
    ]);
    const tooManyRegions = snapshotWithVertexCounts(
      Array.from({ length: 129 }, () => 3),
    );
    const oversizedPolygon = snapshotWithVertexCounts([257]);

    expect(total8193.reduce((sum, item) => sum + item.vertices.length, 0)).toBe(
      8193,
    );
    expect(validateRegionDrafts(total8193)).toContain(
      "A snapshot can contain at most 8,192 vertices.",
    );
    expect(validateRegionDrafts(tooManyRegions)).toContain(
      "A snapshot can contain at most 128 regions.",
    );
    expect(validateRegionDrafts(oversizedPolygon)).toContain(
      "Region “region 0” needs between 3 and 256 vertices.",
    );
  });
});
