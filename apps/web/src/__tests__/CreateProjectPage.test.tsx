import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AppRoutes } from "../router/AppRoutes";
import {
  deferred,
  errorEnvelope,
  imageSetFixture,
  jsonResponse,
  PROJECT_ID,
  projectFixture,
  REQUEST_ID,
  SECOND_PROJECT_ID,
} from "../test/paintProjectFixtures";

function fetchMock(): ReturnType<typeof vi.fn> {
  return vi.mocked(fetch);
}

function renderCreate() {
  return render(
    <MemoryRouter initialEntries={["/paintpilot/projects/new"]}>
      <AppRoutes />
    </MemoryRouter>,
  );
}

function idempotencyKeyAt(callIndex: number): string | null {
  const init = fetchMock().mock.calls[callIndex]?.[1];
  return new Headers(init?.headers).get("Idempotency-Key");
}

function stubIdempotencyKeys(...keys: string[]) {
  const randomUuid = vi.spyOn(globalThis.crypto, "randomUUID");
  for (const key of keys) {
    randomUuid.mockReturnValueOnce(
      key as `${string}-${string}-${string}-${string}-${string}`,
    );
  }
  return randomUuid;
}

describe("Create PaintProject workflow", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("renders only the approved fields, fixed facts, and capability boundary", () => {
    renderCreate();

    expect(
      screen.getByRole("heading", { name: "Create paint project", level: 1 }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText(/project title/i)).toBeRequired();
    expect(screen.getByLabelText("Short description")).toBeInTheDocument();
    expect(screen.getByText("Cel Shading")).toBeInTheDocument();
    expect(screen.getByText("Planning-only demo")).toBeInTheDocument();
    expect(screen.getByText(/no image upload, analysis/i)).toBeInTheDocument();
    expect(screen.queryByLabelText(/style/i)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/image/i)).not.toBeInTheDocument();
  });

  it("validates required and Unicode code-point limits before making a request", async () => {
    const user = userEvent.setup();
    renderCreate();

    await user.click(screen.getByRole("button", { name: "Create project" }));
    expect(
      screen.getByRole("heading", { name: "Please correct 1 project field" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveFocus();
    expect(fetchMock()).not.toHaveBeenCalled();

    fireEvent.change(screen.getByLabelText(/project title/i), {
      target: { value: "🎨".repeat(81) },
    });
    expect(screen.getByText("81 / 80")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Create project" }));
    expect(
      screen.getAllByText("Project title must contain 80 characters or fewer."),
    ).toHaveLength(2);
    expect(fetchMock()).not.toHaveBeenCalled();

    fireEvent.change(screen.getByLabelText(/project title/i), {
      target: { value: "🎨".repeat(80) },
    });
    fireEvent.change(screen.getByLabelText("Short description"), {
      target: { value: "界".repeat(501) },
    });
    expect(screen.getByText("501 / 500")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Create project" }));
    expect(
      screen.getAllByText("Description must contain 500 characters or fewer."),
    ).toHaveLength(2);
    expect(fetchMock()).not.toHaveBeenCalled();
  });

  it("normalizes values, sends one UUID idempotency key, and re-reads success", async () => {
    const user = userEvent.setup();
    stubIdempotencyKeys(REQUEST_ID);
    const project = projectFixture({
      title: "Trimmed title",
      description: "Trimmed description",
    });
    fetchMock()
      .mockResolvedValueOnce(jsonResponse(project, 201))
      .mockResolvedValueOnce(jsonResponse(project))
      .mockResolvedValueOnce(jsonResponse(imageSetFixture()))
      .mockResolvedValueOnce(jsonResponse({ items: [] }));
    renderCreate();

    await user.type(screen.getByLabelText(/project title/i), "  Trimmed title  ");
    await user.type(
      screen.getByLabelText("Short description"),
      "  Trimmed description  ",
    );
    await user.click(screen.getByRole("button", { name: "Create project" }));

    expect(
      await screen.findByRole("heading", { name: "Trimmed title", level: 1 }),
    ).toHaveFocus();
    expect(screen.getByText(/project created and saved/i)).toBeInTheDocument();
    expect(fetchMock()).toHaveBeenCalledTimes(4);
    expect(fetchMock().mock.calls[0]?.[0]).toBe("/api/v1/paint-projects");
    expect(fetchMock().mock.calls[0]?.[1]?.method).toBe("POST");
    expect(idempotencyKeyAt(0)).toBe(REQUEST_ID);
    expect(JSON.parse(String(fetchMock().mock.calls[0]?.[1]?.body))).toEqual({
      title: "Trimmed title",
      description: "Trimmed description",
    });
    expect(fetchMock().mock.calls[1]?.[0]).toBe(
      `/api/v1/paint-projects/${PROJECT_ID}`,
    );
    expect(fetchMock().mock.calls[2]?.[0]).toBe(
      `/api/v1/paint-projects/${PROJECT_ID}/image-set`,
    );
    expect(fetchMock().mock.calls[3]?.[0]).toBe(
      `/api/v1/paint-projects/${PROJECT_ID}/image-set/readiness-reviews`,
    );
    expect(screen.queryByText(REQUEST_ID)).not.toBeInTheDocument();
  });

  it("reuses the same protected attempt after network and 503 uncertainty", async () => {
    const user = userEvent.setup();
    stubIdempotencyKeys(REQUEST_ID);
    fetchMock()
      .mockRejectedValueOnce(new TypeError("connection ended"))
      .mockResolvedValueOnce(
        jsonResponse(
          errorEnvelope({
            category: "DATABASE_UNAVAILABLE",
            error_code: "DATABASE_UNAVAILABLE",
            retryable: true,
          }),
          503,
        ),
      );
    renderCreate();

    await user.type(screen.getByLabelText(/project title/i), "Retry boundary");
    await user.click(screen.getByRole("button", { name: "Create project" }));
    expect(
      await screen.findByRole("heading", {
        name: "We could not confirm whether the project was created",
      }),
    ).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Retry safely" }));
    expect(
      await screen.findByRole("heading", {
        name: "Project creation is temporarily unavailable",
      }),
    ).toBeInTheDocument();
    expect(fetchMock()).toHaveBeenCalledTimes(2);
    expect(idempotencyKeyAt(0)).toBe(REQUEST_ID);
    expect(idempotencyKeyAt(1)).toBe(REQUEST_ID);
    expect(screen.queryByText(REQUEST_ID)).not.toBeInTheDocument();
  });

  it("starts a new protected attempt after an edit or a 409 conflict", async () => {
    const user = userEvent.setup();
    stubIdempotencyKeys(REQUEST_ID, SECOND_PROJECT_ID, PROJECT_ID);
    fetchMock()
      .mockRejectedValueOnce(new TypeError("connection ended"))
      .mockResolvedValueOnce(
        jsonResponse(
          errorEnvelope({
            category: "IDEMPOTENCY_KEY_REUSED",
            error_code: "IDEMPOTENCY_KEY_REUSED",
          }),
          409,
        ),
      )
      .mockResolvedValueOnce(
        jsonResponse(errorEnvelope({ message: "PRIVATE server trace" }), 500),
      );
    renderCreate();

    const title = screen.getByLabelText(/project title/i);
    await user.type(title, "First values");
    await user.click(screen.getByRole("button", { name: "Create project" }));
    await screen.findByRole("heading", {
      name: "We could not confirm whether the project was created",
    });

    await user.type(title, " changed");
    await user.click(screen.getByRole("button", { name: "Create project" }));
    await screen.findByRole("heading", {
      name: "This protected attempt conflicts with earlier details",
    });
    expect(idempotencyKeyAt(0)).toBe(REQUEST_ID);
    expect(idempotencyKeyAt(1)).toBe(SECOND_PROJECT_ID);

    await user.click(
      screen.getByRole("button", { name: "Start new protected attempt" }),
    );
    expect(
      await screen.findByRole("heading", {
        name: "The project could not be created",
      }),
    ).toBeInTheDocument();
    expect(idempotencyKeyAt(2)).toBe(PROJECT_ID);
    expect(screen.queryByText(/PRIVATE server trace/)).not.toBeInTheDocument();
  });

  it("recovers from a real-shaped 409 with a new key and a successful UI retry", async () => {
    const user = userEvent.setup();
    const conflictSecret = "CONFLICT_SECRET_VALUE";
    const project = projectFixture({ title: "Recovered project" });
    stubIdempotencyKeys(REQUEST_ID, SECOND_PROJECT_ID);
    fetchMock()
      .mockResolvedValueOnce(
        jsonResponse(
          errorEnvelope({
            category: "IDEMPOTENCY_KEY_REUSED",
            error_code: "IDEMPOTENCY_KEY_REUSED",
            message: conflictSecret,
            safe_details: { internal: conflictSecret },
          }),
          409,
        ),
      )
      .mockResolvedValueOnce(jsonResponse(project, 201))
      .mockResolvedValueOnce(jsonResponse(project))
      .mockResolvedValueOnce(jsonResponse(imageSetFixture()))
      .mockResolvedValueOnce(jsonResponse({ items: [] }));
    renderCreate();

    const title = screen.getByLabelText(/project title/i);
    await user.type(title, project.title);
    await user.click(screen.getByRole("button", { name: "Create project" }));

    expect(
      await screen.findByRole("heading", {
        name: "This protected attempt conflicts with earlier details",
      }),
    ).toBeInTheDocument();
    expect(title).toHaveValue(project.title);
    expect(screen.queryByText(conflictSecret)).not.toBeInTheDocument();

    await user.click(
      screen.getByRole("button", { name: "Start new protected attempt" }),
    );

    expect(
      await screen.findByRole("heading", { name: project.title, level: 1 }),
    ).toHaveFocus();
    expect(fetchMock()).toHaveBeenCalledTimes(5);
    expect(idempotencyKeyAt(0)).toBe(REQUEST_ID);
    expect(idempotencyKeyAt(1)).toBe(SECOND_PROJECT_ID);
    expect(idempotencyKeyAt(0)).not.toBe(idempotencyKeyAt(1));
  });

  it("maps safe 422 field locations without rendering the server message", async () => {
    const user = userEvent.setup();
    stubIdempotencyKeys(REQUEST_ID);
    fetchMock().mockResolvedValue(
      jsonResponse(
        errorEnvelope({
          category: "VALIDATION_ERROR",
          error_code: "REQUEST_VALIDATION_FAILED",
          message: "PRIVATE database and stack details",
          safe_details: {
            fields: [
              { field: "body.title", reason: "private reason" },
              { field: "body.description", reason: "private reason" },
            ],
          },
        }),
        422,
      ),
    );
    renderCreate();

    await user.type(screen.getByLabelText(/project title/i), "Server validation");
    await user.click(screen.getByRole("button", { name: "Create project" }));

    expect(
      await screen.findByRole("heading", {
        name: "The service needs corrected project details",
      }),
    ).toBeInTheDocument();
    expect(
      screen.getAllByText("Check the project title and try again."),
    ).toHaveLength(2);
    expect(
      screen.getAllByText("Check the description and try again."),
    ).toHaveLength(2);
    expect(screen.queryByText(/PRIVATE/)).not.toBeInTheDocument();
    expect(screen.getByLabelText(/project title/i)).toHaveAttribute(
      "aria-invalid",
      "true",
    );
  });

  it("blocks rapid duplicate activation while a create request is in flight", async () => {
    const user = userEvent.setup();
    stubIdempotencyKeys(REQUEST_ID);
    const pending = deferred<Response>();
    const project = projectFixture();
    fetchMock()
      .mockReturnValueOnce(pending.promise)
      .mockResolvedValueOnce(jsonResponse(project))
      .mockResolvedValueOnce(jsonResponse(imageSetFixture()))
      .mockResolvedValueOnce(jsonResponse({ items: [] }));
    renderCreate();

    await user.type(screen.getByLabelText(/project title/i), project.title);
    const submit = screen.getByRole("button", { name: "Create project" });
    await user.dblClick(submit);

    expect(fetchMock()).toHaveBeenCalledTimes(1);
    expect(
      screen.getByRole("button", { name: "Creating project…" }),
    ).toBeDisabled();
    expect(
      screen.getByRole("button", { name: "Creating project…" }),
    ).toHaveAttribute("aria-busy", "true");
    expect(screen.getByLabelText(/project title/i)).toBeDisabled();

    await act(async () => {
      pending.resolve(jsonResponse(project, 201));
      await pending.promise;
    });
    expect(
      await screen.findByRole("heading", { name: project.title, level: 1 }),
    ).toBeInTheDocument();
    expect(fetchMock()).toHaveBeenCalledTimes(4);
  });

  it("suppresses five consecutive Enter submissions with the same duplicate guard", async () => {
    const user = userEvent.setup();
    stubIdempotencyKeys(REQUEST_ID);
    fetchMock().mockReturnValue(new Promise<Response>(() => undefined));
    renderCreate();

    const title = screen.getByLabelText(/project title/i);
    await user.type(title, "Keyboard create");
    await user.keyboard("{Enter}{Enter}{Enter}{Enter}{Enter}");

    expect(fetchMock()).toHaveBeenCalledTimes(1);
    expect(idempotencyKeyAt(0)).toBe(REQUEST_ID);
    expect(
      screen.getByRole("button", { name: "Creating project…" }),
    ).toBeDisabled();
  });

  it("confirms dirty cancellation, restores trigger focus, and discards explicitly", async () => {
    const user = userEvent.setup();
    fetchMock().mockResolvedValue(
      jsonResponse({ items: [], total: 0, limit: 20, offset: 0 }),
    );
    renderCreate();

    await user.type(screen.getByLabelText(/project title/i), "Unsaved title");
    const cancel = screen.getByRole("button", { name: "Cancel" });
    await user.click(cancel);

    expect(
      screen.getByRole("alertdialog", { name: "Discard unsaved changes?" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Continue editing" })).toHaveFocus();

    await user.tab({ shift: true });
    expect(screen.getByRole("button", { name: "Discard changes" })).toHaveFocus();
    await user.tab();
    expect(screen.getByRole("button", { name: "Continue editing" })).toHaveFocus();
    await user.keyboard("{Escape}");
    expect(cancel).toHaveFocus();
    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();

    await user.click(cancel);
    await user.click(screen.getByRole("button", { name: "Discard changes" }));
    expect(
      await screen.findByRole("heading", { name: "No paint projects yet" }),
    ).toBeInTheDocument();
  });

  it("aborts an in-flight create on unmount without a late state update", async () => {
    const user = userEvent.setup();
    stubIdempotencyKeys(REQUEST_ID);
    const pending = deferred<Response>();
    fetchMock().mockReturnValue(pending.promise);
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => undefined);
    const view = renderCreate();

    await user.type(screen.getByLabelText(/project title/i), "Unmount safety");
    await user.click(screen.getByRole("button", { name: "Create project" }));
    const signal = fetchMock().mock.calls[0]?.[1]?.signal;
    view.unmount();

    expect(signal?.aborted).toBe(true);
    await act(async () => {
      pending.resolve(jsonResponse(projectFixture(), 201));
      await pending.promise;
      await Promise.resolve();
    });
    await waitFor(() => expect(consoleError).not.toHaveBeenCalled());
  });
});
