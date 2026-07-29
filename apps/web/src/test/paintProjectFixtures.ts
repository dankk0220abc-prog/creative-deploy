import type {
  ImageAsset,
  ImageRole,
  ImageSet,
  ImageSetReadinessReview,
} from "../api/imageAssets";
import type { PaintProject } from "../api/paintProjects";

export const PROJECT_ID = "11111111-1111-4111-8111-111111111111";
export const SECOND_PROJECT_ID = "22222222-2222-4222-8222-222222222222";
export const IMAGE_ID = "33333333-3333-4333-8333-333333333333";
export const SECOND_IMAGE_ID = "44444444-4444-4444-8444-444444444444";
export const BACK_IMAGE_ID = "55555555-5555-4555-8555-555555555555";
export const ANGLE_IMAGE_ID = "66666666-6666-4666-8666-666666666666";
export const DETAIL_IMAGE_ID = "77777777-7777-4777-8777-777777777777";
export const REVIEW_ID = "88888888-8888-4888-8888-888888888888";
export const REQUEST_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";

export function projectFixture(
  overrides: Partial<PaintProject> = {},
): PaintProject {
  return {
    id: PROJECT_ID,
    owner_principal_id: "local-demo-owner",
    title: "Cel-shaded garage kit",
    description: "A controlled planning study for a graphic two-shadow finish.",
    requested_target_style: "cel_shading",
    planning_mode: "planning_only_demo",
    status: "DRAFT",
    current_image_asset_id: null,
    created_at: "2026-07-27T08:10:00+00:00",
    updated_at: "2026-07-27T08:10:00+00:00",
    ...overrides,
  };
}

export function imageFixture(overrides: Partial<ImageAsset> = {}): ImageAsset {
  return {
    id: IMAGE_ID,
    paint_project_id: PROJECT_ID,
    role: "primary_front",
    version: 1,
    supersedes_image_asset_id: null,
    is_current: true,
    lifecycle_status: "current",
    original_filename: "garage-reference.png",
    declared_content_type: "image/png",
    detected_format: "png",
    byte_size: 1_048_576,
    width: 1200,
    height: 900,
    pixel_count: 1_080_000,
    color_mode: "RGB",
    has_alpha: false,
    exif_orientation: null,
    sha256: "a".repeat(64),
    upload_validation_result: "accepted",
    upload_validation_details: {
      deterministic_checks: ["signature", "decode", "dimensions"],
      policy_version: "image_upload_validation.v1",
    },
    source_type: "user_provided",
    rights_attestation_status: "confirmed",
    rights_attestation_version: 1,
    intended_usage: ["private_project"],
    rights_attested_at: "2026-07-29T08:10:00+00:00",
    created_at: "2026-07-29T08:10:00+00:00",
    content_url: `/api/v1/paint-projects/${PROJECT_ID}/images/${IMAGE_ID}/content`,
    ...overrides,
  };
}

export function roleImageFixture(
  role: ImageRole,
  id: string,
  overrides: Partial<ImageAsset> = {},
): ImageAsset {
  return imageFixture({
    id,
    role,
    original_filename: `${role}.png`,
    sha256:
      role === "primary_front"
        ? "a".repeat(64)
        : role === "reference_back"
          ? "b".repeat(64)
          : role === "reference_angle"
            ? "c".repeat(64)
            : "d".repeat(64),
    content_url: `/api/v1/paint-projects/${PROJECT_ID}/images/${id}/content`,
    ...overrides,
  });
}

export function readinessReviewFixture(
  overrides: Partial<ImageSetReadinessReview> = {},
): ImageSetReadinessReview {
  return {
    id: REVIEW_ID,
    paint_project_id: PROJECT_ID,
    version: 1,
    verdict: "ready",
    reason: null,
    primary_front_image_asset_id: IMAGE_ID,
    reference_back_image_asset_id: BACK_IMAGE_ID,
    reference_angle_image_asset_id: ANGLE_IMAGE_ID,
    reference_detail_image_asset_id: null,
    image_set_fingerprint: "e".repeat(64),
    actor_type: "user",
    actor_id: "local-demo-owner",
    actor_display_name_snapshot: "Local Demo Owner",
    created_at: "2026-07-29T09:10:00+00:00",
    ...overrides,
  };
}

export function imageSetFixture(overrides: Partial<ImageSet> = {}): ImageSet {
  const front = roleImageFixture("primary_front", IMAGE_ID);
  return {
    paint_project_id: PROJECT_ID,
    image_set_fingerprint: "f".repeat(64),
    roles: [
      {
        role: "primary_front",
        required: true,
        missing: false,
        object_available: true,
        current: front,
        history: [front],
      },
      {
        role: "reference_back",
        required: true,
        missing: true,
        object_available: false,
        current: null,
        history: [],
      },
      {
        role: "reference_angle",
        required: true,
        missing: true,
        object_available: false,
        current: null,
        history: [],
      },
      {
        role: "reference_detail",
        required: false,
        missing: true,
        object_available: false,
        current: null,
        history: [],
      },
    ],
    checklist: {
      required_roles_present: false,
      deterministic_validation_accepted: true,
      rights_complete: true,
      content_distinct: false,
      objects_available: false,
      snapshot_current: false,
      can_mark_ready: false,
      blockers: [
        "missing_required_roles",
        "duplicate_or_missing_required_content",
        "private_object_unavailable",
      ],
    },
    latest_review: null,
    status: "incomplete",
    stale_reasons: [],
    ...overrides,
  };
}

export function errorEnvelope(
  overrides: Partial<{
    allowed_actions: string[];
    category: string;
    current_state: string | null;
    error_code: string;
    message: string;
    request_id: string;
    retryable: boolean;
    safe_details: Record<string, unknown>;
  }> = {},
) {
  return {
    error_code: "INTERNAL_ERROR",
    category: "INTERNAL_ERROR",
    message: "The request could not be completed.",
    retryable: false,
    request_id: REQUEST_ID,
    current_state: null,
    allowed_actions: [],
    safe_details: {},
    ...overrides,
  };
}

export function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

export function deferred<T>() {
  let resolve!: (value: T | PromiseLike<T>) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, reject, resolve };
}
