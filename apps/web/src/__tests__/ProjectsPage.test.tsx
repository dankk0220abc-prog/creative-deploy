import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AppRoutes } from "../router/AppRoutes";
import {
  deferred,
  errorEnvelope,
  jsonResponse,
  PROJECT_ID,
  projectFixture,
  SECOND_PROJECT_ID,
} from "../test/paintProjectFixtures";

function fetchMock(): ReturnType<typeof vi.fn> {
  return vi.mocked(fetch);
}

function renderProjects() {
  return render(
    <MemoryRouter initialEntries={["/paintpilot/projects"]}>
      <AppRoutes />
    </MemoryRouter>,
  );
}

describe("Projects workspace", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("announces loading while retaining the page title and create action", () => {
    fetchMock().mockReturnValue(new Promise<Response>(() => undefined));

    renderProjects();

    expect(
      screen.getByRole("heading", { name: "Paint projects", level: 1 }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("status", { name: "Reading from PaintPilot…" }),
    ).toBeInTheDocument();
    expect(
      screen.getAllByRole("link", { name: /create project/i }).length,
    ).toBeGreaterThan(0);
  });

  it("renders an honest empty state instead of sample project cards", async () => {
    fetchMock().mockResolvedValue(
      jsonResponse({ items: [], total: 0, limit: 20, offset: 0 }),
    );

    renderProjects();

    expect(
      await screen.findByRole("heading", { name: "No paint projects yet" }),
    ).toBeInTheDocument();
    expect(screen.queryByText("Demo project")).not.toBeInTheDocument();
    expect(screen.queryByText("Image not added")).not.toBeInTheDocument();
  });

  it("preserves the backend order and renders every approved card fact", async () => {
    const first = projectFixture({
      id: PROJECT_ID,
      title: "Most recently updated",
      description: "<img src=x onerror=alert(1)> is rendered as text",
      updated_at: "2026-07-27T10:00:00+00:00",
    });
    const second = projectFixture({
      id: SECOND_PROJECT_ID,
      title: "Earlier project",
      description: null,
      created_at: "2026-07-26T08:00:00+00:00",
      updated_at: "2026-07-26T09:00:00+00:00",
    });
    fetchMock().mockResolvedValue(
      jsonResponse({ items: [first, second], total: 2, limit: 20, offset: 0 }),
    );

    renderProjects();

    const cards = await screen.findAllByRole("article");
    expect(
      within(cards[0] as HTMLElement).getByRole("heading", {
        name: "Most recently updated",
      }),
    ).toBeInTheDocument();
    expect(
      within(cards[1] as HTMLElement).getByRole("heading", {
        name: "Earlier project",
      }),
    ).toBeInTheDocument();

    const firstCard = cards[0] as HTMLElement;
    expect(within(firstCard).getByText("Cel Shading")).toBeInTheDocument();
    expect(within(firstCard).getByText("Planning only")).toBeInTheDocument();
    expect(within(firstCard).getByText("No active review gate")).toBeInTheDocument();
    expect(
      within(firstCard).getByLabelText("Workflow status: Draft"),
    ).toBeInTheDocument();
    expect(
      within(firstCard).getByText("<img src=x onerror=alert(1)> is rendered as text"),
    ).toBeInTheDocument();
    expect(firstCard.querySelector("img")).toBeNull();
    expect(
      within(cards[1] as HTMLElement).getByText("No description provided."),
    ).toBeInTheDocument();

    expect(screen.getByRole("link", { name: "Open project Most recently updated" }))
      .toHaveAttribute("href", `/paintpilot/projects/${PROJECT_ID}`);
    expect(screen.getByRole("link", { name: "Open project Earlier project" }))
      .toHaveAttribute("href", `/paintpilot/projects/${SECOND_PROJECT_ID}`);
  });

  it("opens a detail route whose data is fetched again through the API client", async () => {
    const user = userEvent.setup();
    const project = projectFixture();
    fetchMock()
      .mockResolvedValueOnce(
        jsonResponse({ items: [project], total: 1, limit: 20, offset: 0 }),
      )
      .mockResolvedValueOnce(jsonResponse(project));

    renderProjects();

    await user.click(
      await screen.findByRole("link", {
        name: `Open project ${project.title}`,
      }),
    );

    expect(
      await screen.findByRole("heading", { name: project.title, level: 1 }),
    ).toBeInTheDocument();
    expect(fetchMock()).toHaveBeenCalledTimes(2);
    expect(fetchMock().mock.calls[1]?.[0]).toBe(
      `/api/v1/paint-projects/${project.id}`,
    );
  });

  it("distinguishes a database 503 from an empty list and retries only on activation", async () => {
    const user = userEvent.setup();
    fetchMock()
      .mockResolvedValueOnce(
        jsonResponse(
          errorEnvelope({
            error_code: "DATABASE_UNAVAILABLE",
            category: "DATABASE_UNAVAILABLE",
            retryable: true,
            allowed_actions: ["retry"],
          }),
          503,
        ),
      )
      .mockResolvedValueOnce(
        jsonResponse({ items: [], total: 0, limit: 20, offset: 0 }),
      );

    renderProjects();

    expect(
      await screen.findByRole("heading", {
        name: "Project data is temporarily unavailable",
      }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: "No paint projects yet" }),
    ).not.toBeInTheDocument();
    expect(fetchMock()).toHaveBeenCalledTimes(1);

    await user.click(screen.getByRole("button", { name: "Retry projects" }));
    expect(
      await screen.findByRole("heading", { name: "No paint projects yet" }),
    ).toBeInTheDocument();
    expect(fetchMock()).toHaveBeenCalledTimes(2);
  });

  it("reports an unreachable API separately from a database response", async () => {
    fetchMock().mockRejectedValue(new TypeError("network down"));

    renderProjects();

    expect(
      await screen.findByRole("heading", {
        name: "The project service could not be reached",
      }),
    ).toBeInTheDocument();
    expect(screen.getByText(/workspace shell is available/i)).toBeInTheDocument();
  });

  it("uses the server envelope to request the next page", async () => {
    const user = userEvent.setup();
    const first = projectFixture();
    const second = projectFixture({
      id: SECOND_PROJECT_ID,
      title: "Page two",
    });
    fetchMock()
      .mockResolvedValueOnce(
        jsonResponse({ items: [first], total: 21, limit: 20, offset: 0 }),
      )
      .mockResolvedValueOnce(
        jsonResponse({ items: [second], total: 21, limit: 20, offset: 20 }),
      );

    renderProjects();

    await user.click(await screen.findByRole("button", { name: "Next" }));
    expect(
      await screen.findByRole("heading", { name: "Page two" }),
    ).toBeInTheDocument();
    expect(fetchMock().mock.calls[1]?.[0]).toBe(
      "/api/v1/paint-projects?limit=20&offset=20",
    );
  });

  it("aborts a pending list request on unmount without committing a late response", async () => {
    const pending = deferred<Response>();
    fetchMock().mockReturnValue(pending.promise);
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => undefined);
    const view = renderProjects();
    const signal = fetchMock().mock.calls[0]?.[1]?.signal;

    view.unmount();

    expect(signal?.aborted).toBe(true);
    await act(async () => {
      pending.resolve(
        jsonResponse({ items: [], total: 0, limit: 20, offset: 0 }),
      );
      await pending.promise;
      await Promise.resolve();
    });
    await waitFor(() => expect(consoleError).not.toHaveBeenCalled());
  });
});
