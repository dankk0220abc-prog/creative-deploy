import type {
  RegionDraftInput,
  RegionSet,
  RegionWorkbench,
} from "../api/regionSets";
import { PROJECT_ID } from "./paintProjectFixtures";

export const REGION_SET_ID = "66666666-6666-4666-8666-666666666666";
export const REGION_ID = "77777777-7777-4777-8777-777777777777";
export const REGION_KEY = "88888888-8888-4888-8888-888888888888";
export const REGION_IMAGE_ID = "99999999-9999-4999-8999-999999999999";
export const REGION_SHA = "a".repeat(64);

export function regionDraftsFixture(): RegionDraftInput[] {
  return [
    {
      stable_region_key: REGION_KEY,
      kind: "paint",
      label: "hair",
      z_index: 0,
      opacity_ppm: 500_000,
      notes: "Human boundary.",
      vertices: [
        { x_ppm: 100_000, y_ppm: 100_000 },
        { x_ppm: 300_000, y_ppm: 100_000 },
        { x_ppm: 300_000, y_ppm: 300_000 },
        { x_ppm: 100_000, y_ppm: 300_000 },
      ],
    },
  ];
}

export function regionSetFixture(
  overrides: Partial<RegionSet> = {},
): RegionSet {
  return {
    id: REGION_SET_ID,
    paint_project_id: PROJECT_ID,
    version: 1,
    lifecycle: "draft",
    effective_lifecycle: "draft",
    source_primary_image_asset_id: REGION_IMAGE_ID,
    source_image_set_fingerprint: REGION_SHA,
    region_count: 1,
    total_vertex_count: 4,
    geometry_fingerprint: REGION_SHA,
    stale: false,
    stale_reasons: [],
    is_current: true,
    latest_review: null,
    created_at: "2026-07-29T02:00:00+00:00",
    source_image_width: 900,
    source_image_height: 768,
    source_content_url: `/api/v1/paint-projects/${PROJECT_ID}/images/${REGION_IMAGE_ID}/content`,
    supersedes_region_set_id: null,
    based_on_region_set_id: null,
    overlap_warnings: [],
    regions: [
      {
        id: REGION_ID,
        stable_region_key: REGION_KEY,
        kind: "paint",
        label: "hair",
        normalized_label: "hair",
        z_index: 0,
        opacity_ppm: 500_000,
        notes: "Human boundary.",
        vertex_count: 4,
        area_twice_ppm_squared: 80_000_000_000,
        bbox_min_x_ppm: 100_000,
        bbox_min_y_ppm: 100_000,
        bbox_max_x_ppm: 300_000,
        bbox_max_y_ppm: 300_000,
        vertices: regionDraftsFixture()[0]!.vertices.map((vertex, sequence) => ({
          sequence,
          ...vertex,
        })),
      },
    ],
    ...overrides,
  };
}

export function regionWorkbenchFixture(
  overrides: Partial<RegionWorkbench> = {},
): RegionWorkbench {
  return {
    paint_project_id: PROJECT_ID,
    access_role: "owner",
    image_set_status: "ready",
    current_image_set_fingerprint: REGION_SHA,
    source_primary_image_asset_id: REGION_IMAGE_ID,
    source_image_width: 900,
    source_image_height: 768,
    source_content_url: `/api/v1/paint-projects/${PROJECT_ID}/images/${REGION_IMAGE_ID}/content`,
    can_create_draft: true,
    current_region_set: null,
    history: [],
    ...overrides,
  };
}
