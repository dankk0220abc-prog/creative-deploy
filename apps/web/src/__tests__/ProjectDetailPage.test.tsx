import { act, render, screen, waitFor } from "@testing-library/react";
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
} from "../test/paintProjectFixtures";

function fetchMock(): ReturnType<typeof vi.fn> {
  return vi.mocked(fetch);
}

function renderDetail() {
  return render(
    <MemoryRouter initialEntries={[`/paintpilot/projects/${PROJECT_ID}`]}>
      <AppRoutes />
    </MemoryRouter>,
  );
}

function projectAndEmptyImages(project = projectFixture()) {
  fetchMock()
    .mockResolvedValueOnce(jsonResponse(project))
    .mockResolvedValueOnce(jsonResponse(imageSetFixture()))
    .mockResolvedValueOnce(jsonResponse({ items: [] }));
}

describe("PaintProject detail", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("announces a direct-load request without inventing project facts", () => {
    fetchMock().mockReturnValue(new Promise<Response>(() => undefined));
    renderDetail();

    expect(
      screen.getByRole("heading", { name: "Loading saved project", level: 1 }),
    ).toHaveFocus();
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(document.title).toBe("Project Details — PaintPilot");
    expect(
      screen.getByRole("status", {
        name: "Reading the project from PaintPilot…",
      }),
    ).toBeInTheDocument();
    expect(screen.queryByText("Demo project")).not.toBeInTheDocument();
  });

  it("renders every approved persisted fact and hides the raw owner principal", async () => {
    const project = projectFixture({
      owner_principal_id: "PRIVATE-owner-principal",
      status: "IMAGE_REVIEW_REQUIRED",
    });
    projectAndEmptyImages(project);
    const view = renderDetail();

    expect(
      await screen.findByRole("heading", { name: project.title, level: 1 }),
    ).toHaveFocus();
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(document.title).toBe("Project Details — PaintPilot");
    expect(screen.getByText(project.description ?? "")).toBeInTheDocument();
    expect(
      screen.getByLabelText("Workflow status: Image review required"),
    ).toBeInTheDocument();
    expect(screen.getByText("Cel Shading · Current release")).toBeInTheDocument();
    expect(screen.getByText("Planning-only demo")).toBeInTheDocument();
    expect(screen.getByText("Current configured demo operator")).toBeInTheDocument();
    expect(screen.getByText(project.id)).toBeInTheDocument();
    expect(
      view.container.querySelectorAll(`time[datetime="${project.created_at}"]`),
    ).toHaveLength(2);
    expect(
      screen.getByRole("heading", {
        name: "Multi-role image-set workbench",
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", {
        name: "Human-guided region planning is not implemented yet",
      }),
    ).toBeInTheDocument();
    expect(screen.queryByText("PRIVATE-owner-principal")).not.toBeInTheDocument();
  });

  it("states when the optional description is absent", async () => {
    projectAndEmptyImages(projectFixture({ description: null }));
    renderDetail();

    expect(await screen.findByText("No description provided.")).toBeInTheDocument();
  });

  it("uses the owner-safe 404 state without exposing the server message", async () => {
    fetchMock().mockResolvedValue(
      jsonResponse(
        errorEnvelope({
          category: "NOT_FOUND",
          error_code: "PAINT_PROJECT_NOT_FOUND",
          message: "PRIVATE project or owner details",
        }),
        404,
      ),
    );
    renderDetail();

    expect(
      await screen.findByRole("heading", {
        name: "This project is unavailable",
        level: 1,
      }),
    ).toHaveFocus();
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(document.title).toBe("Project Not Found — PaintPilot");
    expect(screen.getByText(/may not exist or may not belong/i)).toBeInTheDocument();
    expect(screen.queryByText(/PRIVATE/)).not.toBeInTheDocument();
  });

  it("distinguishes a database 503 and retries only after activation", async () => {
    const user = userEvent.setup();
    const project = projectFixture();
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
      .mockResolvedValueOnce(jsonResponse(project))
      .mockResolvedValueOnce(jsonResponse(imageSetFixture()))
      .mockResolvedValueOnce(jsonResponse({ items: [] }));
    renderDetail();

    expect(
      await screen.findByRole("heading", {
        name: "Project data is temporarily unavailable",
        level: 1,
      }),
    ).toHaveFocus();
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(document.title).toBe("Project Details — PaintPilot");
    expect(fetchMock()).toHaveBeenCalledTimes(1);

    await user.click(screen.getByRole("button", { name: "Retry project" }));
    expect(
      await screen.findByRole("heading", { name: project.title, level: 1 }),
    ).toBeInTheDocument();
    expect(fetchMock()).toHaveBeenCalledTimes(4);
  });

  it("distinguishes an unreachable API from a database response", async () => {
    fetchMock().mockRejectedValue(new TypeError("API stopped"));
    renderDetail();

    expect(
      await screen.findByRole("heading", {
        name: "The project service could not be reached",
        level: 1,
      }),
    ).toHaveFocus();
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(screen.getByText(/no in-memory project fallback/i)).toBeInTheDocument();
  });

  it("fails closed for a malformed success response", async () => {
    fetchMock().mockResolvedValue(
      jsonResponse({
        ...projectFixture(),
        owner_principal_id: "",
      }),
    );
    renderDetail();

    expect(
      await screen.findByRole("heading", {
        name: "The project could not be displayed",
        level: 1,
      }),
    ).toHaveFocus();
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(screen.queryByText("Cel-shaded garage kit")).not.toBeInTheDocument();
  });

  it("aborts a pending direct-load request on unmount", async () => {
    const pending = deferred<Response>();
    fetchMock().mockReturnValue(pending.promise);
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => undefined);
    const view = renderDetail();
    const signal = fetchMock().mock.calls[0]?.[1]?.signal;

    view.unmount();

    expect(signal?.aborted).toBe(true);
    await act(async () => {
      pending.resolve(jsonResponse(projectFixture()));
      await pending.promise;
      await Promise.resolve();
    });
    await waitFor(() => expect(consoleError).not.toHaveBeenCalled());
  });
});
