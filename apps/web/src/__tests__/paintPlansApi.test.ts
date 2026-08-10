import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  approvePaintPlan,
  editPaintPlan,
  generatePaintPlan,
  getPaintPlan,
  getPaintPlanHistory,
  getPaintPlanWorkbench,
  PaintPlanApiError,
  type PaintPlanSelectionInput,
  previewPaintPlan,
  regeneratePaintPlan,
  rejectPaintPlan,
  stablePaintPlanIdempotencyKey,
  submitPaintPlan,
} from "../api/paintPlans";
import {
  errorEnvelope,
  jsonResponse,
  PROJECT_ID,
  SECOND_PROJECT_ID,
} from "../test/paintProjectFixtures";
import {
  CREDENTIAL_ID,
  MODEL_ID,
  PAINT_PLAN_ID,
  paintPlanDocumentFixture,
  paintPlanFixture,
  paintPlanPreviewFixture,
  paintPlanWorkbenchFixture,
  PROVIDER_ID,
  REGION_SET_ID,
  SECOND_PAINT_PLAN_ID,
} from "../test/paintPlanFixtures";

function fetchMock(): ReturnType<typeof vi.fn> {
  return vi.mocked(fetch);
}

function record(value: unknown): Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new Error("test fixture is not an object");
  }
  return value as Record<string, unknown>;
}

const protectedKey = "30303030-3030-4030-8030-303030303030";

function expectedSelectionProjection() {
  const plan = paintPlanFixture();
  const workbench = paintPlanWorkbenchFixture();
  if (workbench.region_set === null) {
    throw new Error("test RegionSet fixture is missing");
  }
  return {
    provider_key: "fixture_local" as const,
    model_id: "fixture-vision-structured-v1",
    source_image_assets: plan.source_image_assets,
    region_set: workbench.region_set,
  };
}

function selectionInput(intent: string | null = null): PaintPlanSelectionInput {
  return {
    image_set_fingerprint: "a".repeat(64),
    region_set_id: REGION_SET_ID,
    provider_definition_id: PROVIDER_ID,
    model_definition_id: MODEL_ID,
    credential_id: CREDENTIAL_ID,
    generation_locale: "en-US",
    intent,
  };
}

describe("Paint Plan API strict response boundary", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("accepts the exact recursive workbench contract and forwards AbortSignal", async () => {
    const controller = new AbortController();
    fetchMock().mockResolvedValue(jsonResponse(paintPlanWorkbenchFixture()));

    const result = await getPaintPlanWorkbench(PROJECT_ID, controller.signal);

    expect(result.paint_project_id).toBe(PROJECT_ID);
    expect(result.image_assets).toHaveLength(4);
    expect(fetchMock()).toHaveBeenCalledWith(
      `/api/v1/paint-projects/${PROJECT_ID}/paint-plans/workbench`,
      expect.objectContaining({ method: "GET", signal: controller.signal }),
    );
  });

  it("fails closed when a success response contains an extra key", async () => {
    fetchMock().mockResolvedValue(
      jsonResponse({ ...paintPlanWorkbenchFixture(), unexpected_debug: "private" }),
    );

    await expect(getPaintPlanWorkbench(PROJECT_ID)).rejects.toMatchObject({
      kind: "invalid_response",
    });
  });

  it("fails closed when a required nested key is missing", async () => {
    const missing = structuredClone(paintPlanWorkbenchFixture());
    const currentPlan = record(record(missing).current_plan);
    delete record(currentPlan.document).overall_approach;
    fetchMock().mockResolvedValue(jsonResponse(missing));

    await expect(getPaintPlanWorkbench(PROJECT_ID)).rejects.toMatchObject({
      kind: "invalid_response",
    });
  });

  it("fails closed on schema-version drift", async () => {
    const drifted = structuredClone(paintPlanWorkbenchFixture());
    const currentPlan = record(record(drifted).current_plan);
    record(currentPlan.document).schema_version = "paint-plan.v2";
    fetchMock().mockResolvedValue(jsonResponse(drifted));

    await expect(getPaintPlanWorkbench(PROJECT_ID)).rejects.toMatchObject({
      kind: "invalid_response",
    });
  });

  it("binds every workbench and plan projection to the requested project and plan IDs", async () => {
    fetchMock()
      .mockResolvedValueOnce(
        jsonResponse(
          paintPlanWorkbenchFixture({ paint_project_id: SECOND_PROJECT_ID }),
        ),
      )
      .mockResolvedValueOnce(
        jsonResponse(
          paintPlanWorkbenchFixture({
            current_plan: paintPlanFixture({
              paint_project_id: SECOND_PROJECT_ID,
            }),
            history: [
              paintPlanFixture({ paint_project_id: SECOND_PROJECT_ID }),
            ],
          }),
        ),
      )
      .mockResolvedValueOnce(
        jsonResponse(paintPlanFixture({ id: SECOND_PAINT_PLAN_ID })),
      )
      .mockResolvedValueOnce(
        jsonResponse({
          items: [paintPlanFixture({ paint_project_id: SECOND_PROJECT_ID })],
        }),
      );

    await expect(getPaintPlanWorkbench(PROJECT_ID)).rejects.toMatchObject({
      kind: "invalid_response",
    });
    await expect(getPaintPlanWorkbench(PROJECT_ID)).rejects.toMatchObject({
      kind: "invalid_response",
    });
    await expect(getPaintPlan(PROJECT_ID, PAINT_PLAN_ID)).rejects.toMatchObject({
      kind: "invalid_response",
    });
    await expect(getPaintPlanHistory(PROJECT_ID)).rejects.toMatchObject({
      kind: "invalid_response",
    });
  });

  it("rejects impossible history ordering, current identity, and skipped parents", async () => {
    const root = paintPlanFixture({
      lifecycle: "superseded",
      effective_lifecycle: "superseded",
      is_current: false,
      allowed_actions: [],
    });
    const second = paintPlanFixture({
      id: SECOND_PAINT_PLAN_ID,
      lineage_id: SECOND_PAINT_PLAN_ID,
      version: 2,
      parent_plan_id: PAINT_PLAN_ID,
      revision_kind: "regenerated",
      lifecycle: "superseded",
      effective_lifecycle: "superseded",
      is_current: false,
      allowed_actions: [],
    });
    const thirdId = "45454545-4545-4545-8545-454545454545";
    const skippedParentCurrent = paintPlanFixture({
      id: thirdId,
      lineage_id: thirdId,
      version: 3,
      parent_plan_id: PAINT_PLAN_ID,
      revision_kind: "regenerated",
    });
    const oldCurrent = paintPlanFixture();
    fetchMock()
      .mockResolvedValueOnce(
        jsonResponse({ items: [oldCurrent, second] }),
      )
      .mockResolvedValueOnce(
        jsonResponse({ items: [second, oldCurrent] }),
      )
      .mockResolvedValueOnce(
        jsonResponse({ items: [skippedParentCurrent, second, root] }),
      )
      .mockResolvedValueOnce(
        jsonResponse({ items: [second, root] }),
      );

    await expect(getPaintPlanHistory(PROJECT_ID)).rejects.toMatchObject({
      kind: "invalid_response",
    });
    await expect(getPaintPlanHistory(PROJECT_ID)).rejects.toMatchObject({
      kind: "invalid_response",
    });
    await expect(getPaintPlanHistory(PROJECT_ID)).rejects.toMatchObject({
      kind: "invalid_response",
    });
    await expect(getPaintPlanHistory(PROJECT_ID)).rejects.toMatchObject({
      kind: "invalid_response",
    });
  });

  it("rejects malformed provider relabeling and role-swapped server actions", async () => {
    const relabeled = structuredClone(paintPlanWorkbenchFixture());
    const providers = record(relabeled).providers;
    if (!Array.isArray(providers)) {
      throw new Error("test providers fixture is not an array");
    }
    record(providers[0]).execution_mode = "live_authorization_required";
    const reviewerWithOwnerActions = paintPlanWorkbenchFixture({
      access_role: "reviewer",
      credentials: [],
      allowed_actions: ["read_history"],
    });
    fetchMock()
      .mockResolvedValueOnce(jsonResponse(relabeled))
      .mockResolvedValueOnce(jsonResponse(reviewerWithOwnerActions));

    await expect(getPaintPlanWorkbench(PROJECT_ID)).rejects.toMatchObject({
      kind: "invalid_response",
    });
    await expect(getPaintPlanWorkbench(PROJECT_ID)).rejects.toMatchObject({
      kind: "invalid_response",
    });
  });

  it("rejects duplicate governed image roles, unready status, and fixture upstream claims", async () => {
    const duplicateRole = structuredClone(paintPlanWorkbenchFixture());
    const duplicateAssets = record(duplicateRole).image_assets;
    if (!Array.isArray(duplicateAssets)) {
      throw new Error("test image fixture is not an array");
    }
    record(duplicateAssets[2]).role = "reference_back";
    const falseReady = paintPlanWorkbenchFixture({ image_set_status: "stale" });
    const falseFixtureUpstream = paintPlanFixture({
      provider_request_id_status: "provided",
      provider_request_id: "upstream-request",
    });
    fetchMock()
      .mockResolvedValueOnce(jsonResponse(duplicateRole))
      .mockResolvedValueOnce(jsonResponse(falseReady))
      .mockResolvedValueOnce(jsonResponse(falseFixtureUpstream));

    await expect(getPaintPlanWorkbench(PROJECT_ID)).rejects.toMatchObject({
      kind: "invalid_response",
    });
    await expect(getPaintPlanWorkbench(PROJECT_ID)).rejects.toMatchObject({
      kind: "invalid_response",
    });
    await expect(getPaintPlan(PROJECT_ID, PAINT_PLAN_ID)).rejects.toMatchObject({
      kind: "invalid_response",
    });
  });

  it("rejects lifecycle and latest-review contradictions", async () => {
    const contradictory = paintPlanFixture({
      lifecycle: "approved",
      effective_lifecycle: "approved",
      approval_valid: true,
      allowed_actions: ["edit", "regenerate"],
      latest_review: {
        id: "34343434-3434-4434-8434-343434343434",
        action: "reject",
        reason: "Contradictory rejection",
        actor_id: "reviewer-user",
        actor_display_name_snapshot: "Review Operator",
        created_at: "2026-08-09T09:00:00+00:00",
      },
    });
    fetchMock().mockResolvedValueOnce(jsonResponse(contradictory));

    await expect(getPaintPlan(PROJECT_ID, PAINT_PLAN_ID)).rejects.toMatchObject({
      kind: "invalid_response",
    });
  });

  it("rejects secret or raw-provider material inside an otherwise safe error envelope", async () => {
    fetchMock().mockResolvedValue(
      jsonResponse(
        errorEnvelope({
          category: "INTERNAL_ERROR",
          error_code: "PAINT_PLAN_INTERNAL_ERROR",
          message: "PRIVATE server detail",
          safe_details: { api_key: "must-never-render" },
        }),
        500,
      ),
    );

    const error = await getPaintPlanWorkbench(PROJECT_ID).catch(
      (reason: unknown) => reason,
    );
    expect(error).toBeInstanceOf(PaintPlanApiError);
    expect(error).toMatchObject({ kind: "invalid_response" });
    expect(String(error)).not.toContain("PRIVATE");
    expect(String(error)).not.toContain("must-never-render");
  });

  it("rejects every forbidden secret or raw key even inside a whitelisted blocker envelope", async () => {
    const forbiddenKeys = [
      "access_token",
      "refresh_token",
      "password",
      "credential",
      "cookies",
      "headers",
      "body",
      "response",
      "provider_response",
    ];
    for (const forbiddenKey of forbiddenKeys) {
      fetchMock().mockResolvedValueOnce(
        jsonResponse(
          errorEnvelope({
            category: "CONFLICT",
            error_code: "PAINT_PLAN_SOURCE_NOT_READY",
            safe_details: {
              blockers: ["image_set_not_ready"],
              [forbiddenKey]: "must-not-survive",
            },
          }),
          409,
        ),
      );
      await expect(getPaintPlanWorkbench(PROJECT_ID)).rejects.toMatchObject({
        kind: "invalid_response",
      });
    }
  });

  it("accepts only the exact source and live-execution blocker envelopes", async () => {
    for (const errorCode of [
      "PAINT_PLAN_SOURCE_NOT_READY",
      "LIVE_PROVIDER_EXECUTION_NOT_AUTHORIZED",
    ]) {
      fetchMock().mockResolvedValueOnce(
        jsonResponse(
          errorEnvelope({
            category: "CONFLICT",
            error_code: errorCode,
            safe_details: {
              blockers: [
                errorCode === "PAINT_PLAN_SOURCE_NOT_READY"
                  ? "image_set_not_ready"
                  : "live_execution_authorization_required",
              ],
            },
          }),
          409,
        ),
      );
      const error = await getPaintPlanWorkbench(PROJECT_ID).catch(
        (reason: unknown) => reason,
      );
      expect(error).toMatchObject({
        errorCode,
        kind: "conflict",
        safeDetails: { blockers: expect.any(Array) },
      });
    }
  });

  it("fails closed on contradictory preview admission and accounting states", async () => {
    fetchMock()
      .mockResolvedValueOnce(
        jsonResponse(
          paintPlanPreviewFixture({
            source_ready: false,
            blockers: ["image_set_not_ready"],
          }),
        ),
      )
      .mockResolvedValueOnce(
        jsonResponse(
          paintPlanPreviewFixture({
            estimate_status: "estimated",
            estimated_cost_minor_units: null,
          }),
        ),
      );

    await expect(previewPaintPlan(PROJECT_ID, selectionInput())).rejects.toMatchObject(
      { kind: "invalid_response" },
    );
    await expect(previewPaintPlan(PROJECT_ID, selectionInput())).rejects.toMatchObject(
      { kind: "invalid_response" },
    );
  });

  it("rejects command responses that are structurally valid but describe the wrong outcome", async () => {
    const edited = paintPlanFixture({
      id: SECOND_PAINT_PLAN_ID,
      lineage_id: PAINT_PLAN_ID,
      version: 2,
      lineage_revision: 2,
      parent_plan_id: PAINT_PLAN_ID,
      revision_kind: "edited",
      lifecycle: "edited",
      effective_lifecycle: "edited",
    });
    const jumpedEdit = { ...edited, version: 3 };
    const unchangedSubmit = paintPlanFixture();
    const wrongReasonRejection = paintPlanFixture({
      lifecycle: "rejected",
      effective_lifecycle: "rejected",
      allowed_actions: [],
      latest_review: {
        id: "33333333-3333-4333-8333-333333333333",
        action: "reject",
        reason: "A different reason",
        actor_id: "reviewer-user",
        actor_display_name_snapshot: "Review Operator",
        created_at: "2026-08-09T09:00:00+00:00",
      },
    });
    const jumpedRegeneration = paintPlanFixture({
      id: SECOND_PAINT_PLAN_ID,
      lineage_id: SECOND_PAINT_PLAN_ID,
      version: 3,
      lineage_revision: 1,
      parent_plan_id: PAINT_PLAN_ID,
      revision_kind: "regenerated",
    });
    fetchMock()
      .mockResolvedValueOnce(jsonResponse(edited, 201))
      .mockResolvedValueOnce(jsonResponse(jumpedEdit, 201))
      .mockResolvedValueOnce(jsonResponse(unchangedSubmit, 201))
      .mockResolvedValueOnce(jsonResponse(wrongReasonRejection, 201))
      .mockResolvedValueOnce(jsonResponse(jumpedRegeneration, 201));

    await expect(
      generatePaintPlan(
        PROJECT_ID,
        { ...selectionInput(), confirm_generation: true, max_attempts: 1 },
        expectedSelectionProjection(),
        protectedKey,
      ),
    ).rejects.toMatchObject({ kind: "invalid_response" });
    await expect(
      editPaintPlan(
        PROJECT_ID,
        PAINT_PLAN_ID,
        {
          expected_current_plan_id: PAINT_PLAN_ID,
          expected_current_version: 1,
          document: paintPlanDocumentFixture(),
        },
        paintPlanFixture(),
        protectedKey,
      ),
    ).rejects.toMatchObject({ kind: "invalid_response" });
    await expect(
      submitPaintPlan(
        PROJECT_ID,
        PAINT_PLAN_ID,
        {
          expected_current_plan_id: PAINT_PLAN_ID,
          expected_current_version: 1,
        },
        protectedKey,
      ),
    ).rejects.toMatchObject({ kind: "invalid_response" });
    await expect(
      rejectPaintPlan(
        PROJECT_ID,
        PAINT_PLAN_ID,
        {
          expected_current_plan_id: PAINT_PLAN_ID,
          expected_current_version: 1,
          reason: "Expected reason",
        },
        protectedKey,
      ),
    ).rejects.toMatchObject({ kind: "invalid_response" });
    await expect(
      regeneratePaintPlan(
        PROJECT_ID,
        PAINT_PLAN_ID,
        {
          ...selectionInput(),
          expected_current_plan_id: PAINT_PLAN_ID,
          expected_current_version: 1,
          confirm_generation: true,
          max_attempts: 1,
        },
        expectedSelectionProjection(),
        protectedKey,
      ),
    ).rejects.toMatchObject({ kind: "invalid_response" });
  });

  it("accepts multiline request text while binding normalized review output", async () => {
    const multilineReason = "Clarify the edge\n\tbefore approval.";
    const rejected = paintPlanFixture({
      lifecycle: "rejected",
      effective_lifecycle: "rejected",
      allowed_actions: [],
      latest_review: {
        id: "33333333-3333-4333-8333-333333333333",
        action: "reject",
        reason: "Clarify the edge before approval.",
        actor_id: "reviewer-user",
        actor_display_name_snapshot: "Review Operator",
        created_at: "2026-08-09T09:00:00+00:00",
      },
    });
    fetchMock()
      .mockResolvedValueOnce(jsonResponse(paintPlanPreviewFixture()))
      .mockResolvedValueOnce(jsonResponse(rejected, 201));

    await expect(
      previewPaintPlan(PROJECT_ID, selectionInput("Keep this\n\tintent exact.")),
    ).resolves.toMatchObject({ admissible: true });
    await expect(
      rejectPaintPlan(
        PROJECT_ID,
        PAINT_PLAN_ID,
        {
          expected_current_plan_id: PAINT_PLAN_ID,
          expected_current_version: 1,
          reason: multilineReason,
        },
        protectedKey,
      ),
    ).resolves.toMatchObject({ lifecycle: "rejected" });
    expect(String(fetchMock().mock.calls[1]?.[1]?.body)).toContain("\\n\\t");
  });

  it("accepts only supported generation locales before issuing a request", async () => {
    const invalid = {
      ...selectionInput(),
      generation_locale: "fr-FR",
    } as unknown as PaintPlanSelectionInput;

    await expect(previewPaintPlan(PROJECT_ID, invalid)).rejects.toMatchObject({
      kind: "validation",
    });
    expect(fetchMock()).not.toHaveBeenCalled();

    fetchMock().mockResolvedValueOnce(jsonResponse(paintPlanPreviewFixture()));
    await expect(
      previewPaintPlan(PROJECT_ID, {
        ...selectionInput(),
        generation_locale: "zh-CN",
      }),
    ).resolves.toMatchObject({ admissible: true });
    expect(String(fetchMock().mock.calls[0]?.[1]?.body)).toContain(
      '"generation_locale":"zh-CN"',
    );
  });

  it("accepts an exact edited child with normalized document and inherited provenance", async () => {
    const parent = paintPlanFixture();
    const document = paintPlanDocumentFixture({
      title: "Network-safe\n edit",
    });
    const edited = paintPlanFixture({
      id: SECOND_PAINT_PLAN_ID,
      lineage_id: PAINT_PLAN_ID,
      version: 2,
      lineage_revision: 2,
      parent_plan_id: PAINT_PLAN_ID,
      revision_kind: "edited",
      lifecycle: "edited",
      effective_lifecycle: "edited",
      document: paintPlanDocumentFixture({ title: "Network-safe edit" }),
      created_by_actor_type: "user",
    });
    fetchMock().mockResolvedValueOnce(jsonResponse(edited, 201));

    await expect(
      editPaintPlan(
        PROJECT_ID,
        PAINT_PLAN_ID,
        {
          expected_current_plan_id: PAINT_PLAN_ID,
          expected_current_version: 1,
          document,
        },
        parent,
        protectedKey,
      ),
    ).resolves.toMatchObject({ id: SECOND_PAINT_PLAN_ID });
  });

  it("rejects a generated source swap and an edited document swap", async () => {
    const swappedSource = paintPlanFixture({
      source_region_set_version: 5,
    });
    const parent = paintPlanFixture();
    const requestedDocument = paintPlanDocumentFixture({ title: "Requested edit" });
    const swappedEdit = paintPlanFixture({
      id: SECOND_PAINT_PLAN_ID,
      lineage_id: PAINT_PLAN_ID,
      version: 2,
      lineage_revision: 2,
      parent_plan_id: PAINT_PLAN_ID,
      revision_kind: "edited",
      lifecycle: "edited",
      effective_lifecycle: "edited",
      document: paintPlanDocumentFixture({ title: "Different edit" }),
      created_by_actor_type: "user",
    });
    fetchMock()
      .mockResolvedValueOnce(jsonResponse(swappedSource, 201))
      .mockResolvedValueOnce(jsonResponse(swappedEdit, 201));

    await expect(
      generatePaintPlan(
        PROJECT_ID,
        { ...selectionInput(), confirm_generation: true, max_attempts: 1 },
        expectedSelectionProjection(),
        protectedKey,
      ),
    ).rejects.toMatchObject({ kind: "invalid_response" });
    await expect(
      editPaintPlan(
        PROJECT_ID,
        PAINT_PLAN_ID,
        {
          expected_current_plan_id: PAINT_PLAN_ID,
          expected_current_version: 1,
          document: requestedDocument,
        },
        parent,
        protectedKey,
      ),
    ).rejects.toMatchObject({ kind: "invalid_response" });
  });

  it("accepts dynamic historical and stale idempotency replay projections", async () => {
    const generatedReplay = paintPlanFixture({
      lifecycle: "superseded",
      effective_lifecycle: "superseded",
      is_current: false,
      allowed_actions: [],
    });
    const submittedReplay = paintPlanFixture({
      lifecycle: "superseded",
      effective_lifecycle: "superseded",
      is_current: false,
      allowed_actions: [],
      latest_review: {
        id: "34343434-3434-4434-8434-343434343434",
        action: "submit",
        reason: null,
        actor_id: "owner-user",
        actor_display_name_snapshot: "Local Owner",
        created_at: "2026-08-09T09:00:00+00:00",
      },
    });
    const approvedStaleReplay = paintPlanFixture({
      lifecycle: "approved",
      effective_lifecycle: "superseded",
      stale: true,
      stale_reasons: ["image_set_readiness_review_changed"],
      approval_valid: false,
      allowed_actions: [],
      latest_review: {
        id: "35353535-3535-4535-8535-353535353535",
        action: "approve",
        reason: "Approved before drift",
        actor_id: "reviewer-user",
        actor_display_name_snapshot: "Review Operator",
        created_at: "2026-08-09T09:05:00+00:00",
      },
    });
    fetchMock()
      .mockResolvedValueOnce(jsonResponse(generatedReplay, 201))
      .mockResolvedValueOnce(jsonResponse(submittedReplay, 201))
      .mockResolvedValueOnce(jsonResponse(approvedStaleReplay, 201));

    await expect(
      generatePaintPlan(
        PROJECT_ID,
        { ...selectionInput(), confirm_generation: true, max_attempts: 1 },
        expectedSelectionProjection(),
        protectedKey,
      ),
    ).resolves.toMatchObject({ is_current: false, lifecycle: "superseded" });
    await expect(
      submitPaintPlan(
        PROJECT_ID,
        PAINT_PLAN_ID,
        {
          expected_current_plan_id: PAINT_PLAN_ID,
          expected_current_version: 1,
        },
        protectedKey,
      ),
    ).resolves.toMatchObject({ latest_review: { action: "submit" } });
    await expect(
      approvePaintPlan(
        PROJECT_ID,
        PAINT_PLAN_ID,
        {
          expected_current_plan_id: PAINT_PLAN_ID,
          expected_current_version: 1,
          reason: "Approved before drift",
        },
        protectedKey,
      ),
    ).resolves.toMatchObject({ stale: true, approval_valid: false });
  });

  it("reuses a valid protected command key and rejects malformed reuse", () => {
    expect(stablePaintPlanIdempotencyKey(protectedKey)).toBe(protectedKey);
    expect(() => stablePaintPlanIdempotencyKey("not-a-uuid")).toThrow(
      PaintPlanApiError,
    );
  });

  it("does not send runtime request extras or secret-bearing keys", async () => {
    const input = selectionInput();
    record(input).secret = "must-not-be-sent";

    await expect(previewPaintPlan(PROJECT_ID, input)).rejects.toMatchObject({
      kind: "validation",
    });
    expect(fetchMock()).not.toHaveBeenCalled();
  });
});
