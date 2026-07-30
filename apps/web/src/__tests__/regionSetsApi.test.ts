import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  createRegionSetReview,
  forkRegionSetDraft,
  getRegionWorkbench,
  RegionSetApiError,
  saveRegionSet,
  submitRegionSet,
  type RegionDraftInput,
} from "../api/regionSets";
import {
  errorEnvelope,
  jsonResponse,
  PROJECT_ID,
} from "../test/paintProjectFixtures";
import {
  REGION_SET_ID,
  regionDraftsFixture,
  regionSetFixture,
  regionWorkbenchFixture,
} from "../test/regionSetFixtures";

const IDEMPOTENCY_KEY = "55555555-5555-4555-8555-555555555555";

function regions(): RegionDraftInput[] {
  return regionDraftsFixture();
}

function fetchMock(): ReturnType<typeof vi.fn> {
  return vi.mocked(fetch);
}

describe("RegionSet API client", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("accepts only the exact owner-safe workbench contract", async () => {
    const workbench = regionWorkbenchFixture();
    fetchMock().mockResolvedValue(jsonResponse(workbench));

    await expect(getRegionWorkbench(PROJECT_ID)).resolves.toEqual(workbench);
    expect(fetchMock()).toHaveBeenCalledWith(
      `/api/v1/paint-projects/${PROJECT_ID}/region-sets/workbench`,
      expect.objectContaining({ method: "GET" }),
    );
  });

  it("fails closed when storage internals or region response fields drift", async () => {
    fetchMock()
      .mockResolvedValueOnce(
        jsonResponse({
          ...regionWorkbenchFixture(),
          storage_key: "private/path.jpg",
        }),
      )
      .mockResolvedValueOnce(
        jsonResponse(
          regionWorkbenchFixture({
            current_region_set: {
              ...regionSetFixture(),
              regions: [
                {
                  ...regionSetFixture().regions[0]!,
                  vertices: [
                    ...regionSetFixture().regions[0]!.vertices,
                    { sequence: 4, x_ppm: 400_000, y_ppm: 400_000 },
                  ],
                },
              ],
            },
          }),
        ),
      );

    await expect(getRegionWorkbench(PROJECT_ID)).rejects.toMatchObject({
      kind: "invalid_response",
    });
    await expect(getRegionWorkbench(PROJECT_ID)).rejects.toMatchObject({
      kind: "invalid_response",
    });
  });

  it("sends exact protected save and submit payloads", async () => {
    const saved = regionSetFixture();
    fetchMock()
      .mockResolvedValueOnce(jsonResponse(saved, 201))
      .mockResolvedValueOnce(
        jsonResponse(
          regionSetFixture({
            version: 2,
            lifecycle: "submitted",
            effective_lifecycle: "submitted",
          }),
          201,
        ),
      );

    await expect(
      saveRegionSet(
        PROJECT_ID,
        {
          base_region_set_id: null,
          base_version: null,
          regions: regions(),
        },
        IDEMPOTENCY_KEY,
      ),
    ).resolves.toEqual(saved);
    let request = fetchMock().mock.calls[0]?.[1];
    expect(request?.headers).toEqual({
      Accept: "application/json",
      "Content-Type": "application/json",
      "Idempotency-Key": IDEMPOTENCY_KEY,
    });
    expect(JSON.parse(String(request?.body))).toEqual({
      base_region_set_id: null,
      base_version: null,
      regions: regions(),
    });

    await submitRegionSet(PROJECT_ID, REGION_SET_ID, IDEMPOTENCY_KEY);
    request = fetchMock().mock.calls[1]?.[1];
    expect(request?.body).toBe("{}");
  });

  it("forks the exact path source against an explicit current snapshot", async () => {
    const forked = regionSetFixture({
      id: "12121212-1212-4212-8212-121212121212",
      version: 4,
      based_on_region_set_id: REGION_SET_ID,
      supersedes_region_set_id: "34343434-3434-4434-8434-343434343434",
    });
    fetchMock().mockResolvedValue(jsonResponse(forked, 201));

    await expect(
      forkRegionSetDraft(
        PROJECT_ID,
        REGION_SET_ID,
        {
          expected_current_region_set_id:
            "34343434-3434-4434-8434-343434343434",
          expected_current_version: 3,
        },
        IDEMPOTENCY_KEY,
      ),
    ).resolves.toEqual(forked);

    const [url, request] = fetchMock().mock.calls[0]!;
    expect(url).toBe(
      `/api/v1/paint-projects/${PROJECT_ID}/region-sets/${REGION_SET_ID}/drafts`,
    );
    expect(request?.method).toBe("POST");
    expect(JSON.parse(String(request?.body))).toEqual({
      expected_current_region_set_id:
        "34343434-3434-4434-8434-343434343434",
      expected_current_version: 3,
    });
  });

  it("trims a human review reason and rejects a blank changes reason locally", async () => {
    const review = {
      id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
      paint_project_id: PROJECT_ID,
      region_set_id: REGION_SET_ID,
      version: 1,
      verdict: "changes_requested" as const,
      reason: "Adjust edge.",
      actor_type: "user" as const,
      actor_id: "demo-owner",
      actor_display_name_snapshot: "Demo operator",
      created_at: "2026-07-29T03:00:00+00:00",
    };
    fetchMock().mockResolvedValueOnce(jsonResponse(review, 201));

    await expect(
      createRegionSetReview(
        PROJECT_ID,
        REGION_SET_ID,
        { verdict: "changes_requested", reason: "  Adjust edge.  " },
        IDEMPOTENCY_KEY,
      ),
    ).resolves.toEqual(review);
    expect(JSON.parse(String(fetchMock().mock.calls[0]?.[1]?.body))).toEqual({
      verdict: "changes_requested",
      reason: "Adjust edge.",
    });

    await expect(
      createRegionSetReview(
        PROJECT_ID,
        REGION_SET_ID,
        { verdict: "changes_requested", reason: " " },
        IDEMPOTENCY_KEY,
      ),
    ).rejects.toBeInstanceOf(RegionSetApiError);
    expect(fetchMock()).toHaveBeenCalledTimes(1);
  });

  it("classifies a safe stale conflict without exposing server text", async () => {
    fetchMock().mockResolvedValue(
      jsonResponse(
        errorEnvelope({
          error_code: "REGION_SET_STALE",
          category: "CONFLICT",
          message: "PRIVATE implementation details",
        }),
        409,
      ),
    );

    const error = await submitRegionSet(
      PROJECT_ID,
      REGION_SET_ID,
      IDEMPOTENCY_KEY,
    ).catch((caught: unknown) => caught);
    expect(error).toMatchObject({
      kind: "conflict",
      errorCode: "REGION_SET_STALE",
    });
    expect(String(error)).not.toContain("PRIVATE");
  });
});
