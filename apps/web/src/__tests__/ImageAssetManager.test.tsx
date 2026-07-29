import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ImageAssetManager } from "../components/ImageAssetManager";
import type { ImageSet } from "../api/imageAssets";
import {
  ANGLE_IMAGE_ID,
  BACK_IMAGE_ID,
  deferred,
  errorEnvelope,
  IMAGE_ID,
  imageSetFixture,
  jsonResponse,
  PROJECT_ID,
  projectFixture,
  readinessReviewFixture,
  roleImageFixture,
  SECOND_IMAGE_ID,
} from "../test/paintProjectFixtures";

const FIRST_KEY = "99999999-9999-4999-8999-999999999999";
const SECOND_KEY = "aaaaaaaa-1111-4111-8111-111111111111";

function fetchMock(): ReturnType<typeof vi.fn> {
  return vi.mocked(fetch);
}

function completeImageSet(overrides: Partial<ImageSet> = {}): ImageSet {
  const front = roleImageFixture("primary_front", IMAGE_ID);
  const back = roleImageFixture("reference_back", BACK_IMAGE_ID);
  const angle = roleImageFixture("reference_angle", ANGLE_IMAGE_ID);
  return imageSetFixture({
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
        missing: false,
        object_available: true,
        current: back,
        history: [back],
      },
      {
        role: "reference_angle",
        required: true,
        missing: false,
        object_available: true,
        current: angle,
        history: [angle],
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
      required_roles_present: true,
      deterministic_validation_accepted: true,
      rights_complete: true,
      content_distinct: true,
      objects_available: true,
      snapshot_current: false,
      can_mark_ready: true,
      blockers: [],
    },
    ...overrides,
  });
}

function mockWorkbench(imageSet = imageSetFixture(), reviews: unknown[] = []) {
  fetchMock()
    .mockResolvedValueOnce(jsonResponse(imageSet))
    .mockResolvedValueOnce(jsonResponse({ items: reviews }));
}

function renderManager(
  imageSet = imageSetFixture(),
  project = projectFixture({ status: "IMAGE_UPLOADED" }),
  reviews: unknown[] = [],
  onProjectChanged = vi.fn(),
) {
  mockWorkbench(imageSet, reviews);
  return {
    onProjectChanged,
    view: render(
      <ImageAssetManager
        onProjectChanged={onProjectChanged}
        project={project}
      />,
    ),
  };
}

async function completeDeclaration(user: ReturnType<typeof userEvent.setup>) {
  const file = new File(["safe-image"], "reference.png", {
    type: "image/png",
    lastModified: 123,
  });
  await user.upload(screen.getByLabelText("Image file"), file);
  await user.click(
    screen.getByRole("checkbox", {
      name: /I confirm that the source above is accurate/i,
    }),
  );
  return file;
}

describe("ImageSet workbench", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
    let nextKey = 0;
    vi.spyOn(globalThis.crypto, "randomUUID").mockImplementation(() => {
      nextKey += 1;
      return (nextKey === 1 ? FIRST_KEY : SECOND_KEY) as `${string}-${string}-${string}-${string}-${string}`;
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("renders four controlled roles, required markers, and no destructive or AI action", async () => {
    renderManager();

    expect(
      await screen.findByRole("heading", {
        name: "Multi-role image-set workbench",
      }),
    ).toBeInTheDocument();
    expect(screen.getByText("4 formal roles")).toBeInTheDocument();
    for (const heading of [
      "Primary front",
      "Reference back",
      "Reference angle",
      "Reference detail",
    ]) {
      expect(screen.getByRole("heading", { name: heading })).toBeInTheDocument();
    }
    expect(screen.getAllByText("Required role")).toHaveLength(3);
    expect(screen.getByText("Optional role")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /delete/i })).not.toBeInTheDocument();
    expect(screen.queryByText(/AI-detected angle/i)).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /quality score/i }),
    ).not.toBeInTheDocument();
    expect(screen.queryByText(/copyright verified/i)).not.toBeInTheDocument();
  });

  it("locks primary replacement in IMAGE_UPLOADED while keeping reference mutations available", async () => {
    renderManager(
      completeImageSet(),
      projectFixture({ status: "IMAGE_UPLOADED" }),
    );
    const user = userEvent.setup();
    const primaryCard = (
      await screen.findByRole("heading", { name: "Primary front" })
    ).closest("article");
    const backCard = screen
      .getByRole("heading", { name: "Reference back" })
      .closest("article");
    const detailCard = screen
      .getByRole("heading", { name: "Reference detail" })
      .closest("article");

    expect(primaryCard).not.toBeNull();
    expect(backCard).not.toBeNull();
    expect(detailCard).not.toBeNull();
    expect(
      within(primaryCard as HTMLElement).queryByRole("button", {
        name: "Replace safely",
      }),
    ).not.toBeInTheDocument();
    expect(primaryCard).toHaveTextContent(
      "Primary front replacement is available only when image review is required or image validation has failed.",
    );
    expect(
      within(backCard as HTMLElement).getByRole("button", {
        name: "Replace safely",
      }),
    ).toBeEnabled();
    expect(
      within(detailCard as HTMLElement).getByRole("button", {
        name: "Add this role",
      }),
    ).toBeEnabled();
    expect(
      screen.getByRole("heading", {
        name: "Primary front replacement is locked in IMAGE_UPLOADED",
      }),
    ).toBeInTheDocument();

    await user.click(
      within(backCard as HTMLElement).getByRole("button", {
        name: "Replace safely",
      }),
    );
    expect(
      screen.getByRole("heading", { name: "Replace Reference back" }),
    ).toBeInTheDocument();
  });

  it.each(["IMAGE_REVIEW_REQUIRED", "IMAGE_VALIDATION_FAILED"] as const)(
    "allows primary replacement in %s",
    async (status) => {
      renderManager(completeImageSet(), projectFixture({ status }));
      const primaryCard = (
        await screen.findByRole("heading", { name: "Primary front" })
      ).closest("article");
      expect(primaryCard).not.toBeNull();
      expect(
        within(primaryCard as HTMLElement).getByRole("button", {
          name: "Replace safely",
        }),
      ).toBeEnabled();
      expect(
        screen.getByRole("heading", { name: "Replace Primary front" }),
      ).toBeInTheDocument();
    },
  );

  it("allows only the first primary upload in DRAFT", async () => {
    const initial = imageSetFixture();
    const noPrimary = imageSetFixture({
      roles: initial.roles.map((slot) =>
        slot.role === "primary_front"
          ? {
              ...slot,
              missing: true,
              object_available: false,
              current: null,
              history: [],
            }
          : slot,
      ),
    });
    const { unmount } = renderManager(
      noPrimary,
      projectFixture({ status: "DRAFT" }),
    ).view;
    const primaryCard = (
      await screen.findByRole("heading", { name: "Primary front" })
    ).closest("article");
    expect(
      within(primaryCard as HTMLElement).getByRole("button", {
        name: "Add this role",
      }),
    ).toBeEnabled();
    expect(
      screen.getByRole("heading", { name: "Add Primary front" }),
    ).toBeInTheDocument();

    unmount();
    renderManager(completeImageSet(), projectFixture({ status: "DRAFT" }));
    const existingPrimaryCard = (
      await screen.findByRole("heading", { name: "Primary front" })
    ).closest("article");
    expect(
      within(existingPrimaryCard as HTMLElement).queryByRole("button", {
        name: "Replace safely",
      }),
    ).not.toBeInTheDocument();
    expect(existingPrimaryCard).toHaveTextContent(
      "Primary front replacement is available only when image review is required or image validation has failed.",
    );
  });

  it("freezes every image role in IMAGE_VALIDATED", async () => {
    renderManager(
      completeImageSet(),
      projectFixture({ status: "IMAGE_VALIDATED" }),
    );
    await screen.findByRole("heading", { name: "Primary front" });

    expect(
      screen.queryByRole("button", { name: "Replace safely" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Add this role" }),
    ).not.toBeInTheDocument();
    expect(
      screen.getAllByText("All image roles are frozen after image validation."),
    ).toHaveLength(5);
    expect(
      screen.getByRole("heading", {
        name: "Primary front replacement is locked in IMAGE_VALIDATED",
      }),
    ).toBeInTheDocument();
  });

  it("shows deterministic blockers and keeps READY disabled for an incomplete set", async () => {
    renderManager();

    expect(
      await screen.findByText("All required roles present"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Required images have distinct content").closest("li"),
    ).toHaveClass("is-blocked");
    expect(
      screen.getByRole("button", { name: "Confirm READY" }),
    ).toBeDisabled();
    expect(screen.getByText(/human readiness not confirmed/i)).toBeInTheDocument();
    expect(
      screen.queryByText(/Duplicate content detected across required roles/i),
    ).not.toBeInTheDocument();
  });

  it("renders complete checklist, private previews, and enables human READY", async () => {
    renderManager(completeImageSet());

    expect(
      await screen.findByRole("img", {
        name: /Private preview of Primary front/i,
      }),
    ).toHaveAttribute(
      "src",
      `/api/v1/paint-projects/${PROJECT_ID}/images/${IMAGE_ID}/content`,
    );
    expect(screen.getAllByText("Accepted")).toHaveLength(3);
    expect(screen.getAllByText("Attested")).toHaveLength(3);
    expect(
      screen.getByText("Required images have distinct content").closest("li"),
    ).toHaveClass("is-pass");
    expect(
      screen.getByRole("button", { name: "Confirm READY" }),
    ).toBeEnabled();
  });

  it("warns about duplicate required content and blocks READY", async () => {
    renderManager(
      completeImageSet({
        status: "stale",
        stale_reasons: ["reference_back_changed"],
        checklist: {
          required_roles_present: true,
          deterministic_validation_accepted: true,
          rights_complete: true,
          content_distinct: false,
          objects_available: true,
          snapshot_current: false,
          can_mark_ready: false,
          blockers: ["duplicate_or_missing_required_content"],
        },
        latest_review: readinessReviewFixture(),
      }),
      projectFixture({ status: "IMAGE_UPLOADED" }),
      [readinessReviewFixture()],
    );

    expect(
      await screen.findByRole("alert", {
        name: "",
      }),
    ).toHaveTextContent("Duplicate content detected");
    expect(screen.getByText(/image set changed after review/i)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Confirm READY" }),
    ).toBeDisabled();
  });

  it("uploads the selected role with one protected request despite repeated submit", async () => {
    const pending = deferred<Response>();
    renderManager();
    const user = userEvent.setup();
    const backCard = (
      await screen.findByRole("heading", { name: "Reference back" })
    ).closest("article");
    expect(backCard).not.toBeNull();
    await user.click(
      within(backCard as HTMLElement).getByRole("button", {
        name: "Add this role",
      }),
    );
    const file = await completeDeclaration(user);
    fetchMock().mockReturnValueOnce(pending.promise);

    const submit = screen.getByRole("button", {
      name: "Store Reference back",
    });
    const form = submit.closest("form");
    fireEvent.submit(form as HTMLFormElement);
    fireEvent.submit(form as HTMLFormElement);

    await waitFor(() => expect(fetchMock()).toHaveBeenCalledTimes(3));
    const uploadRequest = fetchMock().mock.calls[2]?.[1];
    const body = uploadRequest?.body as FormData;
    expect(body.get("file")).toBe(file);
    expect(body.get("role")).toBe("reference_back");
    expect(uploadRequest?.headers).toEqual({
      Accept: "application/json",
      "Idempotency-Key": FIRST_KEY,
    });
    expect(submit).toBeDisabled();
  });

  it("requires a NOT READY reason and prevents repeated review submit", async () => {
    const pending = deferred<Response>();
    renderManager(completeImageSet());
    const user = userEvent.setup();
    await screen.findByRole("button", { name: "Confirm READY" });
    await user.click(screen.getByRole("radio", { name: "NOT READY" }));
    await user.click(screen.getByRole("button", { name: "Record NOT READY" }));
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Explain why this image set is not ready.",
    );

    await user.type(
      screen.getByLabelText("Reason (required)"),
      "The angle needs a safer replacement.",
    );
    fetchMock().mockReturnValueOnce(pending.promise);
    const submit = screen.getByRole("button", { name: "Record NOT READY" });
    const form = submit.closest("form");
    fireEvent.submit(form as HTMLFormElement);
    fireEvent.submit(form as HTMLFormElement);

    await waitFor(() => expect(fetchMock()).toHaveBeenCalledTimes(3));
    const reviewRequest = fetchMock().mock.calls[2]?.[1];
    expect(reviewRequest?.headers).toEqual({
      Accept: "application/json",
      "Content-Type": "application/json",
      "Idempotency-Key": FIRST_KEY,
    });
    expect(JSON.parse(String(reviewRequest?.body))).toEqual({
      verdict: "not_ready",
      reason: "The angle needs a safer replacement.",
    });
    expect(submit).toBeDisabled();
  });

  it("reuses the same readiness key after a retryable response", async () => {
    const review = readinessReviewFixture({
      verdict: "not_ready",
      reason: "Retry this exact decision.",
    });
    renderManager(completeImageSet());
    fetchMock()
      .mockResolvedValueOnce(
        jsonResponse(
          errorEnvelope({
            category: "DATABASE_UNAVAILABLE",
            error_code: "DATABASE_UNAVAILABLE",
            retryable: true,
          }),
          503,
        ),
      )
      .mockResolvedValueOnce(jsonResponse(review, 201))
      .mockResolvedValueOnce(jsonResponse(completeImageSet()))
      .mockResolvedValueOnce(jsonResponse({ items: [review] }));
    const user = userEvent.setup();
    await screen.findByRole("button", { name: "Confirm READY" });
    await user.click(screen.getByRole("radio", { name: "NOT READY" }));
    await user.type(screen.getByLabelText("Reason (required)"), review.reason ?? "");

    await user.click(screen.getByRole("button", { name: "Record NOT READY" }));
    expect(
      await screen.findByText(/Private image storage is temporarily unavailable/i),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Record NOT READY" }));

    await waitFor(() => expect(fetchMock()).toHaveBeenCalledTimes(6));
    expect(
      (fetchMock().mock.calls[2]?.[1]?.headers as Record<string, string>)[
        "Idempotency-Key"
      ],
    ).toBe(FIRST_KEY);
    expect(
      (fetchMock().mock.calls[3]?.[1]?.headers as Record<string, string>)[
        "Idempotency-Key"
      ],
    ).toBe(FIRST_KEY);
  });

  it("shows retained per-role versions, latest review, history, and reconfirmation", async () => {
    const latest = readinessReviewFixture({
      version: 2,
      id: SECOND_IMAGE_ID,
      image_set_fingerprint: "9".repeat(64),
    });
    const retainedAngle = roleImageFixture("reference_angle", SECOND_IMAGE_ID, {
      is_current: false,
      lifecycle_status: "superseded",
      version: 1,
    });
    const currentAngle = roleImageFixture("reference_angle", ANGLE_IMAGE_ID, {
      version: 2,
      supersedes_image_asset_id: SECOND_IMAGE_ID,
    });
    const base = completeImageSet({
      status: "stale",
      latest_review: latest,
      stale_reasons: ["reference_angle_changed"],
    });
    const stale: ImageSet = {
      ...base,
      roles: base.roles.map((slot) =>
        slot.role === "reference_angle"
          ? {
              ...slot,
              current: currentAngle,
              history: [currentAngle, retainedAngle],
            }
          : slot,
      ),
    };
    renderManager(stale, projectFixture({ status: "IMAGE_UPLOADED" }), [
      latest,
      readinessReviewFixture(),
    ]);
    const user = userEvent.setup();

    expect(
      await screen.findByText("Latest review · version 2"),
    ).toBeInTheDocument();
    await user.click(screen.getByText("Version history (2)"));
    expect(screen.getByText(/v1 · reference_angle.png/i)).toBeInTheDocument();
    await user.click(screen.getByText("Review history (2)"));
    expect(screen.getByText(/v2 · READY/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Confirm READY" })).toBeEnabled();
    expect(screen.queryByRole("button", { name: /delete/i })).not.toBeInTheDocument();
  });
});
