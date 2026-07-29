import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ImageAssetManager } from "../components/ImageAssetManager";
import {
  deferred,
  errorEnvelope,
  IMAGE_ID,
  imageFixture,
  jsonResponse,
  PROJECT_ID,
  projectFixture,
  SECOND_IMAGE_ID,
} from "../test/paintProjectFixtures";

const FIRST_KEY = "55555555-5555-4555-8555-555555555555";
const SECOND_KEY = "66666666-6666-4666-8666-666666666666";

function fetchMock(): ReturnType<typeof vi.fn> {
  return vi.mocked(fetch);
}

function renderManager(
  project = projectFixture(),
  onProjectChanged = vi.fn(),
) {
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

describe("ImageAsset manager", () => {
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

  it("shows a single empty formal slot and the complete first-upload declaration", async () => {
    fetchMock().mockResolvedValue(jsonResponse({ items: [] }));
    renderManager();

    expect(
      await screen.findByRole("heading", { name: "No image has been stored" }),
    ).toBeInTheDocument();
    expect(screen.getByText("1 formal slot")).toBeInTheDocument();
    expect(screen.getByLabelText("Image file")).toHaveAttribute(
      "accept",
      expect.stringContaining("image/webp"),
    );
    expect(screen.getByLabelText("Image source")).toBeInTheDocument();
    expect(
      screen.getByRole("checkbox", { name: "Private project planning" }),
    ).toBeChecked();
    expect(
      screen.getByRole("checkbox", { name: "Portfolio demonstration" }),
    ).not.toBeChecked();
    expect(
      screen.getByRole("button", { name: "Store primary image" }),
    ).toBeEnabled();
    expect(screen.queryByRole("button", { name: /delete/i })).not.toBeInTheDocument();
  });

  it("requires a file, intended use, and explicit user attestation", async () => {
    const user = userEvent.setup();
    fetchMock().mockResolvedValue(jsonResponse({ items: [] }));
    renderManager();
    await screen.findByRole("heading", { name: "No image has been stored" });

    await user.click(screen.getByRole("button", { name: "Store primary image" }));
    expect(
      screen.getByRole("alert", { name: "" }),
    ).toHaveTextContent("Choose one JPEG, PNG, or WebP image.");

    await user.upload(
      screen.getByLabelText("Image file"),
      new File(["safe"], "reference.png", { type: "image/png" }),
    );
    await user.click(
      screen.getByRole("checkbox", { name: "Private project planning" }),
    );
    await user.click(screen.getByRole("button", { name: "Store primary image" }));
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Choose at least one intended use.",
    );

    await user.click(
      screen.getByRole("checkbox", { name: "Private project planning" }),
    );
    await user.click(screen.getByRole("button", { name: "Store primary image" }));
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Confirm the source, rights, and intended-use declaration.",
    );
    expect(fetchMock()).toHaveBeenCalledTimes(1);
  });

  it("renders an authorized private preview and immutable metadata", async () => {
    const image = imageFixture();
    fetchMock().mockResolvedValue(jsonResponse({ items: [image] }));
    renderManager(
      projectFixture({
        current_image_asset_id: IMAGE_ID,
        status: "IMAGE_UPLOADED",
      }),
    );

    const preview = await screen.findByRole("img", {
      name: `Private preview of ${image.original_filename}`,
    });
    expect(preview).toHaveAttribute("src", image.content_url);
    expect(screen.getByText("1200 × 900 px")).toBeInTheDocument();
    expect(screen.getByText("User attestation confirmed")).toBeInTheDocument();
    expect(screen.getByText("Upload checks")).toBeInTheDocument();
    expect(
      screen.getByRole("heading", {
        name: "Image upload is not available in IMAGE_UPLOADED",
      }),
    ).toBeInTheDocument();
  });

  it("offers replacement only in a formal replacement state and promises retention", async () => {
    const image = imageFixture();
    fetchMock().mockResolvedValue(jsonResponse({ items: [image] }));
    renderManager(
      projectFixture({
        current_image_asset_id: IMAGE_ID,
        status: "IMAGE_REVIEW_REQUIRED",
      }),
    );

    expect(
      await screen.findByRole("heading", {
        name: "Upload a replacement original",
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/previous original remains in immutable history/i),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Store replacement" }),
    ).toBeEnabled();
  });

  it("shows retained versions without any destructive action", async () => {
    const current = imageFixture({
      id: SECOND_IMAGE_ID,
      version: 2,
      supersedes_image_asset_id: IMAGE_ID,
      content_url: `/api/v1/paint-projects/${PROJECT_ID}/images/${SECOND_IMAGE_ID}/content`,
    });
    const retained = imageFixture({
      is_current: false,
      lifecycle_status: "superseded",
    });
    fetchMock().mockResolvedValue(jsonResponse({ items: [current, retained] }));
    const user = userEvent.setup();
    renderManager(
      projectFixture({
        current_image_asset_id: SECOND_IMAGE_ID,
        status: "IMAGE_UPLOADED",
      }),
    );

    await user.click(
      await screen.findByText("Retained image history (1)"),
    );
    expect(
      screen.getByLabelText("Retained primary image, version 1"),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Open private original" }),
    ).toHaveAttribute("href", retained.content_url);
    expect(screen.queryByRole("button", { name: /delete/i })).not.toBeInTheDocument();
  });

  it("prevents repeated submit while one upload is in flight", async () => {
    const uploadPending = deferred<Response>();
    fetchMock()
      .mockResolvedValueOnce(jsonResponse({ items: [] }))
      .mockReturnValueOnce(uploadPending.promise);
    const user = userEvent.setup();
    const { view } = renderManager();
    await screen.findByRole("heading", { name: "No image has been stored" });
    await completeDeclaration(user);

    const form = view.container.querySelector("form");
    expect(form).not.toBeNull();
    fireEvent.submit(form as HTMLFormElement);
    fireEvent.submit(form as HTMLFormElement);

    expect(
      await screen.findByRole("progressbar", {
        name: "Uploading and checking image",
      }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button")).toBeDisabled();
    expect(fetchMock()).toHaveBeenCalledTimes(2);

    uploadPending.resolve(jsonResponse(imageFixture(), 201));
  });

  it("reuses the same idempotency key after a retryable connection loss", async () => {
    const image = imageFixture();
    fetchMock()
      .mockResolvedValueOnce(jsonResponse({ items: [] }))
      .mockRejectedValueOnce(new TypeError("connection lost"))
      .mockResolvedValueOnce(jsonResponse(image, 201))
      .mockResolvedValueOnce(jsonResponse({ items: [image] }));
    const user = userEvent.setup();
    const onProjectChanged = vi.fn();
    renderManager(projectFixture(), onProjectChanged);
    await screen.findByRole("heading", { name: "No image has been stored" });
    await completeDeclaration(user);

    await user.click(screen.getByRole("button", { name: "Store primary image" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Retry keeps the same protected upload attempt.",
    );
    await user.click(screen.getByRole("button", { name: "Store primary image" }));

    await waitFor(() => expect(onProjectChanged).toHaveBeenCalledTimes(1));
    const firstHeaders = fetchMock().mock.calls[1]?.[1]?.headers as Record<
      string,
      string
    >;
    const retryHeaders = fetchMock().mock.calls[2]?.[1]?.headers as Record<
      string,
      string
    >;
    expect(firstHeaders["Idempotency-Key"]).toBe(FIRST_KEY);
    expect(retryHeaders["Idempotency-Key"]).toBe(FIRST_KEY);
  });

  it("starts a new protected command after upload inputs change", async () => {
    fetchMock()
      .mockResolvedValueOnce(jsonResponse({ items: [] }))
      .mockRejectedValueOnce(new TypeError("connection lost"))
      .mockResolvedValueOnce(jsonResponse(imageFixture(), 201))
      .mockResolvedValueOnce(jsonResponse({ items: [imageFixture()] }));
    const user = userEvent.setup();
    renderManager();
    await screen.findByRole("heading", { name: "No image has been stored" });
    await completeDeclaration(user);

    await user.click(screen.getByRole("button", { name: "Store primary image" }));
    await screen.findByRole("alert");
    await user.selectOptions(screen.getByLabelText("Image source"), "user_photographed");
    await user.click(screen.getByRole("button", { name: "Store primary image" }));

    const retryHeaders = fetchMock().mock.calls[2]?.[1]?.headers as Record<
      string,
      string
    >;
    expect(retryHeaders["Idempotency-Key"]).toBe(SECOND_KEY);
  });

  it("recovers an owner-scoped list error only after explicit retry", async () => {
    fetchMock()
      .mockResolvedValueOnce(
        jsonResponse(
          errorEnvelope({
            category: "STORAGE_ERROR",
            error_code: "IMAGE_STORAGE_UNAVAILABLE",
            retryable: true,
          }),
          503,
        ),
      )
      .mockResolvedValueOnce(jsonResponse({ items: [] }));
    const user = userEvent.setup();
    renderManager();

    expect(
      await screen.findByRole("heading", {
        name: "The image records could not be loaded",
      }),
    ).toBeInTheDocument();
    expect(fetchMock()).toHaveBeenCalledTimes(1);
    await user.click(screen.getByRole("button", { name: "Retry image history" }));
    expect(
      await screen.findByRole("heading", { name: "No image has been stored" }),
    ).toBeInTheDocument();
    expect(fetchMock()).toHaveBeenCalledTimes(2);
  });
});
