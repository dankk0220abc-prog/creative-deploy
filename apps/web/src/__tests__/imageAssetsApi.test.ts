import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  createReadinessReview,
  getImageSet,
  ImageAssetApiError,
  listImageAssets,
  listReadinessReviews,
  uploadImageAsset,
} from "../api/imageAssets";
import {
  errorEnvelope,
  IMAGE_ID,
  imageFixture,
  imageSetFixture,
  jsonResponse,
  PROJECT_ID,
  readinessReviewFixture,
} from "../test/paintProjectFixtures";

const IDEMPOTENCY_KEY = "55555555-5555-4555-8555-555555555555";

function fetchMock(): ReturnType<typeof vi.fn> {
  return vi.mocked(fetch);
}

describe("ImageAsset API client", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("accepts only the exact owner-safe list contract", async () => {
    const image = imageFixture();
    fetchMock().mockResolvedValue(jsonResponse({ items: [image] }));

    await expect(listImageAssets(PROJECT_ID)).resolves.toEqual({
      items: [image],
    });
    expect(fetchMock()).toHaveBeenCalledWith(
      `/api/v1/paint-projects/${PROJECT_ID}/images`,
      expect.objectContaining({ method: "GET" }),
    );
  });

  it("fails closed when an image response contains storage internals", async () => {
    fetchMock().mockResolvedValue(
      jsonResponse({
        items: [{ ...imageFixture(), storage_key: "private/path.png" }],
      }),
    );

    await expect(listImageAssets(PROJECT_ID)).rejects.toMatchObject({
      kind: "invalid_response",
    });
  });

  it("builds the exact multipart declaration without setting Content-Type", async () => {
    const image = imageFixture();
    fetchMock().mockResolvedValue(jsonResponse(image, 201));
    const file = new File(["image"], "reference.png", { type: "image/png" });

    await expect(
      uploadImageAsset(
        PROJECT_ID,
        {
          file,
          role: "primary_front",
          sourceType: "user_photographed",
          intendedUsage: ["private_project", "portfolio_demo"],
        },
        IDEMPOTENCY_KEY,
      ),
    ).resolves.toEqual(image);

    const request = fetchMock().mock.calls[0]?.[1];
    const body = request?.body;
    expect(request?.headers).toEqual({
      Accept: "application/json",
      "Idempotency-Key": IDEMPOTENCY_KEY,
    });
    expect(body).toBeInstanceOf(FormData);
    expect((body as FormData).get("file")).toBe(file);
    expect((body as FormData).get("role")).toBe("primary_front");
    expect((body as FormData).get("source_type")).toBe("user_photographed");
    expect((body as FormData).getAll("intended_usage")).toEqual([
      "private_project",
      "portfolio_demo",
    ]);
    expect((body as FormData).get("rights_attestation_confirmed")).toBe("true");
    expect((body as FormData).get("rights_attestation_version")).toBe("1");
  });

  it("classifies retryable private-storage failures without exposing server text", async () => {
    fetchMock().mockResolvedValue(
      jsonResponse(
        errorEnvelope({
          category: "STORAGE_ERROR",
          error_code: "IMAGE_STORAGE_UNAVAILABLE",
          message: "PRIVATE /var/image/path",
          retryable: true,
        }),
        503,
      ),
    );

    const error = await listImageAssets(PROJECT_ID).catch(
      (caught: unknown) => caught,
    );
    expect(error).toBeInstanceOf(ImageAssetApiError);
    expect(error).toMatchObject({
      kind: "storage",
      retryable: true,
      status: 503,
    });
    expect(String(error)).not.toContain("PRIVATE");
  });

  it("rejects a cross-project content URL in an otherwise valid payload", async () => {
    fetchMock().mockResolvedValue(
      jsonResponse({
        items: [
          imageFixture({
            content_url: `/api/v1/paint-projects/22222222-2222-4222-8222-222222222222/images/${IMAGE_ID}/content`,
          }),
        ],
      }),
    );

    await expect(listImageAssets(PROJECT_ID)).rejects.toMatchObject({
      kind: "invalid_response",
    });
  });

  it("validates the exact four-role image-set response", async () => {
    const imageSet = imageSetFixture();
    fetchMock().mockResolvedValue(jsonResponse(imageSet));

    await expect(getImageSet(PROJECT_ID)).resolves.toEqual(imageSet);
    expect(fetchMock()).toHaveBeenCalledWith(
      `/api/v1/paint-projects/${PROJECT_ID}/image-set`,
      expect.objectContaining({ method: "GET" }),
    );
  });

  it("fails closed when role order or readiness fields drift", async () => {
    const imageSet = imageSetFixture();
    fetchMock()
      .mockResolvedValueOnce(
        jsonResponse({
          ...imageSet,
          roles: [...imageSet.roles].reverse(),
        }),
      )
      .mockResolvedValueOnce(
        jsonResponse({
          ...imageSet,
          checklist: { ...imageSet.checklist, quality_score: 0.99 },
        }),
      );

    await expect(getImageSet(PROJECT_ID)).rejects.toMatchObject({
      kind: "invalid_response",
    });
    await expect(getImageSet(PROJECT_ID)).rejects.toMatchObject({
      kind: "invalid_response",
    });
  });

  it("creates a protected readiness review with strict JSON and reads history", async () => {
    const review = readinessReviewFixture({
      verdict: "not_ready",
      reason: "Needs another view.",
    });
    fetchMock()
      .mockResolvedValueOnce(jsonResponse(review, 201))
      .mockResolvedValueOnce(jsonResponse({ items: [review] }));

    await expect(
      createReadinessReview(
        PROJECT_ID,
        { verdict: "not_ready", reason: "  Needs another view.  " },
        IDEMPOTENCY_KEY,
      ),
    ).resolves.toEqual(review);
    const request = fetchMock().mock.calls[0]?.[1];
    expect(request?.headers).toEqual({
      Accept: "application/json",
      "Content-Type": "application/json",
      "Idempotency-Key": IDEMPOTENCY_KEY,
    });
    expect(JSON.parse(String(request?.body))).toEqual({
      verdict: "not_ready",
      reason: "Needs another view.",
    });

    await expect(listReadinessReviews(PROJECT_ID)).resolves.toEqual({
      items: [review],
    });
  });

  it("rejects an empty NOT READY reason before sending a request", async () => {
    await expect(
      createReadinessReview(
        PROJECT_ID,
        { verdict: "not_ready", reason: " " },
        IDEMPOTENCY_KEY,
      ),
    ).rejects.toMatchObject({ kind: "validation" });
    expect(fetchMock()).not.toHaveBeenCalled();
  });
});
