import type {
  PaintPlan,
  PaintPlanDocument,
  PaintPlanImageAsset,
  PaintPlanPreview,
  PaintPlanWorkbench,
} from "../api/paintPlans";
import {
  ANGLE_IMAGE_ID,
  BACK_IMAGE_ID,
  DETAIL_IMAGE_ID,
  IMAGE_ID,
  PROJECT_ID,
  REVIEW_ID,
} from "./paintProjectFixtures";

export const PAINT_PLAN_ID = "12121212-1212-4212-8212-121212121212";
export const SECOND_PAINT_PLAN_ID = "13131313-1313-4313-8313-131313131313";
export const REGION_SET_ID = "14141414-1414-4414-8414-141414141414";
export const PAINT_REGION_ID = "15151515-1515-4515-8515-151515151515";
export const SECOND_PAINT_REGION_ID = "16161616-1616-4616-8616-161616161616";
export const EXCLUDE_REGION_ID = "17171717-1717-4717-8717-171717171717";
export const PROVIDER_ID = "18181818-1818-4818-8818-181818181818";
export const OPENAI_PROVIDER_ID = "19191919-1919-4919-8919-191919191919";
export const MODEL_ID = "20202020-2020-4020-8020-202020202020";
export const OPENAI_MODEL_ID = "21212121-2121-4121-8121-212121212121";
export const CREDENTIAL_ID = "23232323-2323-4323-8323-232323232323";
export const OPENAI_CREDENTIAL_ID = "24242424-2424-4424-8424-242424242424";

const sha = (character: string) => character.repeat(64);

function paintPlanImageAssetFixture(
  id: string,
  role: PaintPlanImageAsset["role"],
  hash: string,
): PaintPlanImageAsset {
  return {
    id,
    role,
    version: 1,
    content_url: `/api/v1/paint-projects/${PROJECT_ID}/images/${id}/content`,
    sha256: sha(hash),
    media_type: "image/png",
    byte_length: 320_000,
    width: 1200,
    height: 900,
    upload_validation_result: "accepted",
    rights_attestation_status: "confirmed",
    rights_attestation_version: 1,
    intended_usage: ["private_project"],
  };
}

export function paintPlanDocumentFixture(
  overrides: Partial<PaintPlanDocument> = {},
): PaintPlanDocument {
  return {
    schema_version: "paint-plan.v1",
    title: "Governed fixture paint plan",
    overall_approach:
      "Preserve the approved silhouettes, work from the prepared base to controlled shadow layers, and inspect every transition under neutral light.",
    instructions: [
      {
        region_id: PAINT_REGION_ID,
        stable_region_key: "25252525-2525-4525-8525-252525252525",
        region_label: "Main body panel",
        target_color: "Warm copper red",
        preparation: "Degrease the surface and key the existing finish evenly.",
        base_coat: "Apply one opaque neutral base coat.",
        layer_strategy: "Build two controlled cel-shaded layers without soft gradients.",
        edge_treatment: "Keep the perimeter crisp and mask adjacent excluded trim.",
        lighting_guidance: "Check the highlight break under a neutral overhead source.",
        material_guidance: "Use a matte-compatible coating system and observe cure times.",
        warnings: ["Confirm coating compatibility on a hidden area."],
        confidence_ppm: 875_000,
      },
      {
        region_id: SECOND_PAINT_REGION_ID,
        stable_region_key: "26262626-2626-4626-8626-262626262626",
        region_label: "Long technical region label that must wrap safely at mobile width",
        target_color: "Deep graphite shadow",
        preparation: "Clean and lightly abrade the bounded region.",
        base_coat: "Carry the neutral base through the exact polygon edge.",
        layer_strategy: "Use one flat shadow layer with a deliberate hard transition.",
        edge_treatment: "Remove masking before the coating fully cures.",
        lighting_guidance: "Compare the shape under side and front reference views.",
        material_guidance: "Maintain the same sheen as the main body panel.",
        warnings: [],
        confidence_ppm: 720_000,
      },
    ],
    safety_notes: ["Use ventilation and the coating maker's protective equipment."],
    knowledge_citations: [
      {
        source_id: "paintpilot-practice-notes",
        chunk_id: "paintpilot:surface-preparation",
        target_path: "/instructions/0/preparation",
      },
    ],
    ...overrides,
  };
}

export function paintPlanFixture(overrides: Partial<PaintPlan> = {}): PaintPlan {
  return {
    id: PAINT_PLAN_ID,
    lineage_id: PAINT_PLAN_ID,
    paint_project_id: PROJECT_ID,
    version: 1,
    lineage_revision: 1,
    parent_plan_id: null,
    revision_kind: "generated",
    lifecycle: "generated",
    effective_lifecycle: "generated",
    is_current: true,
    stale: false,
    stale_reasons: [],
    approval_valid: false,
    source_invocation_id: "27272727-2727-4727-8727-272727272727",
    source_attempt_id: "31313131-3131-4131-8131-313131313131",
    source_image_set_fingerprint: sha("a"),
    source_image_assets: [
      paintPlanImageAssetFixture(IMAGE_ID, "primary_front", "1"),
      paintPlanImageAssetFixture(BACK_IMAGE_ID, "reference_back", "2"),
      paintPlanImageAssetFixture(ANGLE_IMAGE_ID, "reference_angle", "3"),
      paintPlanImageAssetFixture(DETAIL_IMAGE_ID, "reference_detail", "4"),
    ],
    source_readiness_review_id: REVIEW_ID,
    source_readiness_review_version: 2,
    source_region_set_id: REGION_SET_ID,
    source_region_set_version: 4,
    source_geometry_fingerprint: sha("b"),
    provider_definition_id: PROVIDER_ID,
    provider_key: "fixture_local",
    provider_revision_snapshot: 1,
    model_definition_id: MODEL_ID,
    model_id: "fixture-vision-structured-v1",
    model_revision_snapshot: 1,
    provider_pricing_snapshot_id: null,
    prompt_template_id: "28282828-2828-4828-8828-282828282828",
    prompt_template_key: "paint-plan",
    prompt_version: 1,
    prompt_hash: sha("c"),
    generation_locale: "en-US",
    schema_version: "paint-plan.v1",
    content_hash: sha("d"),
    document: paintPlanDocumentFixture(),
    retrieved_context: [
      {
        source_id: "paintpilot-practice-notes",
        source_title: "PaintPilot repository-local practice notes",
        source_type: "repository_local_corpus",
        repository_reference: "repo://paintpilot/knowledge/practice-notes",
        chunk_id: "paintpilot:surface-preparation",
        section: "surface preparation",
        content: "Test compatibility before applying a coating system.",
        retrieval_rationale: "Preparation guidance requested by the governed plan.",
        retrieval_score_ppm: 1_000_000,
        locale: "en-US",
        corpus_id: "paintpilot-practice-notes",
        corpus_version: "1",
      },
    ],
    provider_request_id_status: "absent",
    provider_request_id: null,
    usage_measurement_status: "unavailable",
    input_units: null,
    output_units: null,
    cost_measurement_status: "measured",
    cost_minor_units: 240,
    cost_currency: "FIXTURE_CREDITS",
    latest_review: null,
    allowed_actions: ["edit", "regenerate", "submit"],
    requested_by_user_id: "32323232-3232-4232-8232-323232323232",
    invocation_created_at: "2026-08-09T08:09:30+00:00",
    created_by_actor_type: "provider",
    created_by_actor_id: "local-owner",
    created_by_actor_display_name_snapshot: "Local Owner",
    created_at: "2026-08-09T08:10:00+00:00",
    ...overrides,
  };
}

export function paintPlanPreviewFixture(
  overrides: Partial<PaintPlanPreview> = {},
): PaintPlanPreview {
  return {
    admissible: true,
    execution_mode: "fixture_available",
    provider_key: "fixture_local",
    model_id: "fixture-vision-structured-v1",
    source_ready: true,
    estimated_cost_minor_units: 240,
    currency: "FIXTURE_CREDITS",
    estimate_status: "estimated",
    live_execution_authorized: false,
    blockers: [],
    ...overrides,
  };
}

export function paintPlanWorkbenchFixture(
  overrides: Partial<PaintPlanWorkbench> = {},
): PaintPlanWorkbench {
  const currentPlan = paintPlanFixture();
  return {
    paint_project_id: PROJECT_ID,
    access_role: "owner",
    image_set_status: "ready",
    image_set_fingerprint: sha("a"),
    readiness_review_id: REVIEW_ID,
    image_assets: [
      paintPlanImageAssetFixture(IMAGE_ID, "primary_front", "1"),
      paintPlanImageAssetFixture(BACK_IMAGE_ID, "reference_back", "2"),
      paintPlanImageAssetFixture(ANGLE_IMAGE_ID, "reference_angle", "3"),
      paintPlanImageAssetFixture(DETAIL_IMAGE_ID, "reference_detail", "4"),
    ],
    region_set: {
      id: REGION_SET_ID,
      version: 4,
      geometry_fingerprint: sha("b"),
      effective_lifecycle: "approved",
      stale: false,
      regions: [
        {
          id: PAINT_REGION_ID,
          stable_region_key: "25252525-2525-4525-8525-252525252525",
          kind: "paint",
          label: "Main body panel",
          normalized_label: "main body panel",
          z_index: 0,
          opacity_ppm: 700_000,
          notes: null,
          bbox_min_x_ppm: 10_000,
          bbox_min_y_ppm: 10_000,
          bbox_max_x_ppm: 500_000,
          bbox_max_y_ppm: 500_000,
          vertices: [
            [10_000, 10_000],
            [500_000, 10_000],
            [500_000, 500_000],
          ],
        },
        {
          id: SECOND_PAINT_REGION_ID,
          stable_region_key: "26262626-2626-4626-8626-262626262626",
          kind: "paint",
          label: "Long technical region label that must wrap safely at mobile width",
          normalized_label: "long technical region label",
          z_index: 1,
          opacity_ppm: 650_000,
          notes: null,
          bbox_min_x_ppm: 500_000,
          bbox_min_y_ppm: 10_000,
          bbox_max_x_ppm: 900_000,
          bbox_max_y_ppm: 500_000,
          vertices: [
            [500_000, 10_000],
            [900_000, 10_000],
            [900_000, 500_000],
          ],
        },
        {
          id: EXCLUDE_REGION_ID,
          stable_region_key: "29292929-2929-4929-8929-292929292929",
          kind: "exclude",
          label: "Protected trim",
          normalized_label: "protected trim",
          z_index: 2,
          opacity_ppm: 500_000,
          notes: "Do not paint",
          bbox_min_x_ppm: 0,
          bbox_min_y_ppm: 500_000,
          bbox_max_x_ppm: 1_000_000,
          bbox_max_y_ppm: 900_000,
          vertices: [
            [0, 500_000],
            [1_000_000, 500_000],
            [1_000_000, 900_000],
          ],
        },
      ],
    },
    source_ready: true,
    blockers: [],
    providers: [
      {
        id: PROVIDER_ID,
        provider_key: "fixture_local",
        display_name: "Bundled fixture provider",
        execution_mode: "fixture_available",
        models: [
          {
            id: MODEL_ID,
            model_id: "fixture-vision-structured-v1",
            display_name: "Fixture Vision Structured",
            execution_mode: "fixture_available",
            currency: "FIXTURE_CREDITS",
            supports_vision: true,
            supports_structured_output: true,
          },
        ],
      },
      {
        id: OPENAI_PROVIDER_ID,
        provider_key: "openai",
        display_name: "OpenAI",
        execution_mode: "live_authorization_required",
        models: [
          {
            id: OPENAI_MODEL_ID,
            model_id: "gpt-live-registry-entry",
            display_name: "OpenAI multimodal registry entry",
            execution_mode: "live_authorization_required",
            currency: "USD",
            supports_vision: true,
            supports_structured_output: true,
          },
        ],
      },
    ],
    credentials: [
      {
        id: CREDENTIAL_ID,
        alias: "Local fixture credential",
        provider_key: "fixture_local",
        active_grant: true,
        status: "active",
      },
      {
        id: OPENAI_CREDENTIAL_ID,
        alias: "Saved OpenAI record",
        provider_key: "openai",
        active_grant: true,
        status: "active",
      },
    ],
    current_plan: currentPlan,
    history: [currentPlan],
    allowed_actions: ["read_history", "preview", "regenerate"],
    ...overrides,
  };
}
