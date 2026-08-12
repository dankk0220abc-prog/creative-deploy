import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useLocation, useNavigate } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AppRoutes } from "../router/AppRoutes";
import {
  errorEnvelope,
  imageSetFixture,
  jsonResponse,
  PROJECT_ID,
  projectFixture,
  SECOND_PROJECT_ID,
} from "../test/paintProjectFixtures";

function fetchMock(): ReturnType<typeof vi.fn> {
  return vi.mocked(fetch);
}

function renderRoute(initialEntry: string) {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <AppRoutes />
    </MemoryRouter>,
  );
}

function navigationLink(name: "Create project" | "Projects") {
  return within(
    screen.getByRole("navigation", { name: "PaintPilot navigation" }),
  ).getByRole("link", { name });
}

function HistoryProbe() {
  const location = useLocation();
  const navigate = useNavigate();
  return (
    <div>
      <output aria-label="Current test route">
        {location.pathname}
        {location.search}
      </output>
      <button onClick={() => navigate(-1)} type="button">
        Test back
      </button>
      <button onClick={() => navigate(1)} type="button">
        Test forward
      </button>
      <button onClick={() => navigate("?offset=20")} type="button">
        Test search
      </button>
      <button
        onClick={() => navigate("/paintpilot/unsupported/settings")}
        type="button"
      >
        Test unknown
      </button>
    </div>
  );
}

describe("PaintPilot route tree", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
    window.history.replaceState(null, "", "/");
    document.title = "Test title";
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("renders the CreativeDeploy product chooser at the root", () => {
    renderRoute("/");

    expect(
      screen.getByRole("heading", { name: "Choose your working space", level: 1 }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Arcana/ })).toBeInTheDocument();
    expect(document.title).toBe("Product Spaces — CreativeDeploy");
    expect(fetchMock()).not.toHaveBeenCalled();
  });

  it(
    "redirects /paintpilot to the Projects workspace",
    async () => {
      fetchMock().mockResolvedValue(
        jsonResponse({ items: [], total: 0, limit: 20, offset: 0 }),
      );

      renderRoute("/paintpilot");

      expect(
        await screen.findByRole("heading", { name: "Paint projects", level: 1 }),
      ).toBeInTheDocument();
      expect(document.title).toBe("Projects — PaintPilot");
      expect(fetchMock()).toHaveBeenCalledTimes(1);
    },
  );

  it("renders the list route and marks Projects navigation active", async () => {
    fetchMock().mockResolvedValue(
      jsonResponse({ items: [], total: 0, limit: 20, offset: 0 }),
    );

    renderRoute("/paintpilot/projects");

    expect(
      await screen.findByRole("heading", { name: "No paint projects yet" }),
    ).toBeInTheDocument();
    expect(navigationLink("Projects")).toHaveClass(
      "shell-nav__link--active",
    );
    expect(navigationLink("Projects")).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(navigationLink("Create project")).not.toHaveAttribute("aria-current");
    expect(document.title).toBe("Projects — PaintPilot");
  });

  it("renders the independent create route without loading project data", () => {
    renderRoute("/paintpilot/projects/new");

    expect(
      screen.getByRole("heading", { name: "Create paint project", level: 1 }),
    ).toBeInTheDocument();
    expect(navigationLink("Create project")).toHaveClass(
      "shell-nav__link--active",
    );
    expect(navigationLink("Create project")).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(navigationLink("Projects")).not.toHaveAttribute("aria-current");
    expect(document.title).toBe("Create Project — PaintPilot");
    expect(fetchMock()).not.toHaveBeenCalled();
  });

  it("renders a fail-closed identity-provider error with an explicit retry", () => {
    renderRoute(
      "/paintpilot/login?auth_error=identity_provider_unavailable&return_to=%2Fpaintpilot%2Fprojects",
    );

    expect(
      screen.getByRole("heading", {
        name: "CreativeDeploy could not reach the identity provider",
        level: 1,
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Try sign in again" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/No Demo Principal, request header, email/),
    ).toBeInTheDocument();
    expect(fetchMock()).not.toHaveBeenCalled();
  });

  it("directly loads a valid detail route from the API", async () => {
    fetchMock()
      .mockResolvedValueOnce(jsonResponse(projectFixture()))
      .mockResolvedValueOnce(jsonResponse(imageSetFixture()))
      .mockResolvedValueOnce(jsonResponse({ items: [] }));

    renderRoute(`/paintpilot/projects/${PROJECT_ID}`);

    expect(
      await screen.findByRole("heading", {
        name: "Cel-shaded garage kit",
        level: 1,
      }),
    ).toBeInTheDocument();
    expect(navigationLink("Projects")).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(navigationLink("Create project")).not.toHaveAttribute("aria-current");
    expect(document.title).toBe("Project Details — PaintPilot");
    expect(fetchMock()).toHaveBeenCalledTimes(3);
    expect(fetchMock().mock.calls[1]?.[0]).toBe(
      `/api/v1/paint-projects/${PROJECT_ID}/image-set`,
    );
    expect(fetchMock().mock.calls[2]?.[0]).toBe(
      `/api/v1/paint-projects/${PROJECT_ID}/image-set/readiness-reviews`,
    );
  });

  it("rejects an invalid detail ID without issuing a request", () => {
    renderRoute("/paintpilot/projects/not-a-uuid");

    expect(
      screen.getByRole("heading", {
        name: "This project ID is not a valid UUID",
        level: 1,
      }),
    ).toHaveFocus();
    expect(document.title).toBe("Project Not Found — PaintPilot");
    expect(fetchMock()).not.toHaveBeenCalled();
  });

  it("distinguishes an owner-safe detail 404 from an unknown frontend route", async () => {
    fetchMock().mockResolvedValueOnce(
      jsonResponse(
        errorEnvelope({
          error_code: "PAINT_PROJECT_NOT_FOUND",
          category: "NOT_FOUND",
        }),
        404,
      ),
    );

    const detailRender = renderRoute(`/paintpilot/projects/${PROJECT_ID}`);
    expect(
      await screen.findByRole("heading", {
        name: "This project is unavailable",
        level: 1,
      }),
    ).toHaveFocus();
    expect(document.title).toBe("Project Not Found — PaintPilot");
    detailRender.unmount();

    renderRoute("/paintpilot/unsupported/settings");
    expect(
      screen.getByRole("heading", {
        name: "This PaintPilot page does not exist",
        level: 1,
      }),
    ).toBeInTheDocument();
    expect(navigationLink("Projects")).not.toHaveAttribute("aria-current");
    expect(navigationLink("Create project")).not.toHaveAttribute("aria-current");
    expect(document.title).toBe("Page Not Found — PaintPilot");
  });

  it("moves focus to main when the skip link is activated with Enter", async () => {
    const user = userEvent.setup();
    fetchMock().mockResolvedValue(
      jsonResponse({ items: [], total: 0, limit: 20, offset: 0 }),
    );
    renderRoute("/paintpilot/projects");
    await screen.findByRole("heading", { name: "Paint projects", level: 1 });

    await user.tab();
    const skipLink = screen.getByRole("link", { name: "Skip to main content" });
    expect(skipLink).toHaveFocus();

    await user.keyboard("{Enter}");
    expect(screen.getByRole("main")).toHaveFocus();
    expect(window.location.hash).toBe("#main-content");
  });

  it("focuses the Create h1 after Projects navigation", async () => {
    const user = userEvent.setup();
    fetchMock().mockResolvedValue(
      jsonResponse({ items: [], total: 0, limit: 20, offset: 0 }),
    );
    renderRoute("/paintpilot/projects");
    await screen.findByRole("heading", { name: "No paint projects yet" });

    await user.click(navigationLink("Create project"));

    const heading = screen.getByRole("heading", {
      name: "Create paint project",
      level: 1,
    });
    expect(heading).toHaveFocus();
    expect(document.title).toBe("Create Project — PaintPilot");
  });

  it("focuses the persisted Detail h1 after a successful Create navigation", async () => {
    const user = userEvent.setup();
    const project = projectFixture({ title: "Keyboard detail focus" });
    fetchMock()
      .mockResolvedValueOnce(jsonResponse(project, 201))
      .mockResolvedValueOnce(jsonResponse(project));
    renderRoute("/paintpilot/projects/new");

    await user.type(screen.getByLabelText(/project title/i), project.title);
    await user.click(screen.getByRole("button", { name: "Create project" }));

    const heading = await screen.findByRole("heading", {
      name: project.title,
      level: 1,
    });
    expect(heading).toHaveFocus();
    expect(document.title).toBe("Project Details — PaintPilot");
  });

  it("focuses the Projects h1 and restores its title after Detail navigation", async () => {
    const user = userEvent.setup();
    fetchMock()
      .mockResolvedValueOnce(jsonResponse(projectFixture()))
      .mockResolvedValueOnce(jsonResponse(imageSetFixture()))
      .mockResolvedValueOnce(jsonResponse({ items: [] }))
      .mockResolvedValueOnce(
        jsonResponse({ items: [], total: 0, limit: 20, offset: 0 }),
      );
    renderRoute(`/paintpilot/projects/${PROJECT_ID}`);
    await screen.findByRole("heading", {
      name: "Cel-shaded garage kit",
      level: 1,
    });

    await user.click(screen.getByRole("link", { name: /Back to projects/ }));

    const heading = await screen.findByRole("heading", {
      name: "Paint projects",
      level: 1,
    });
    expect(heading).toHaveFocus();
    expect(document.title).toBe("Projects — PaintPilot");
  });

  it("returns focus to the Projects h1 after pagination changes", async () => {
    const user = userEvent.setup();
    fetchMock()
      .mockResolvedValueOnce(
        jsonResponse({
          items: [projectFixture()],
          total: 21,
          limit: 20,
          offset: 0,
        }),
      )
      .mockResolvedValueOnce(
        jsonResponse({
          items: [projectFixture({ id: SECOND_PROJECT_ID, title: "Page two" })],
          total: 21,
          limit: 20,
          offset: 20,
        }),
      );
    renderRoute("/paintpilot/projects");
    await screen.findByRole("heading", { name: "Your projects" });

    await user.click(screen.getByRole("button", { name: "Next" }));

    await screen.findByText("Page two");
    expect(
      screen.getByRole("heading", { name: "Paint projects", level: 1 }),
    ).toHaveFocus();
    expect(fetchMock()).toHaveBeenLastCalledWith(
      "/api/v1/paint-projects?limit=20&offset=20",
      expect.objectContaining({ method: "GET" }),
    );
  });

  it("focuses the page h1 after an actual search-parameter navigation", async () => {
    const user = userEvent.setup();
    fetchMock().mockResolvedValue(
      jsonResponse({ items: [], total: 0, limit: 20, offset: 0 }),
    );
    render(
      <MemoryRouter initialEntries={["/paintpilot/projects"]}>
        <HistoryProbe />
        <AppRoutes />
      </MemoryRouter>,
    );
    await screen.findByRole("heading", { name: "No paint projects yet" });

    await user.click(screen.getByRole("button", { name: "Test search" }));

    await waitFor(() =>
      expect(screen.getByLabelText("Current test route")).toHaveTextContent(
        "/paintpilot/projects?offset=20",
      ),
    );
    expect(
      screen.getByRole("heading", { name: "Paint projects", level: 1 }),
    ).toHaveFocus();
    expect(document.title).toBe("Projects — PaintPilot");
  });

  it("focuses the unknown-route h1 after frontend navigation", async () => {
    const user = userEvent.setup();
    fetchMock().mockResolvedValue(
      jsonResponse({ items: [], total: 0, limit: 20, offset: 0 }),
    );
    render(
      <MemoryRouter initialEntries={["/paintpilot/projects"]}>
        <HistoryProbe />
        <AppRoutes />
      </MemoryRouter>,
    );
    await screen.findByRole("heading", { name: "No paint projects yet" });

    await user.click(screen.getByRole("button", { name: "Test unknown" }));

    expect(
      screen.getByRole("heading", {
        name: "This PaintPilot page does not exist",
        level: 1,
      }),
    ).toHaveFocus();
    expect(document.title).toBe("Page Not Found — PaintPilot");
  });

  it("preserves browser-like back and forward navigation between business routes", async () => {
    const user = userEvent.setup();
    const consoleError = vi
      .spyOn(console, "error")
      .mockImplementation(() => undefined);
    fetchMock().mockResolvedValue(
      jsonResponse({ items: [], total: 0, limit: 20, offset: 0 }),
    );
    render(
      <MemoryRouter
        initialEntries={["/paintpilot/projects", "/paintpilot/projects/new"]}
        initialIndex={1}
      >
        <HistoryProbe />
        <AppRoutes />
      </MemoryRouter>,
    );

    expect(screen.getByLabelText("Current test route")).toHaveTextContent(
      "/paintpilot/projects/new",
    );
    await user.click(screen.getByRole("button", { name: "Test back" }));
    await waitFor(() =>
      expect(screen.getByLabelText("Current test route")).toHaveTextContent(
        "/paintpilot/projects",
      ),
    );
    expect(
      await screen.findByRole("heading", { name: "No paint projects yet" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Paint projects", level: 1 }),
    ).toHaveFocus();
    expect(document.title).toBe("Projects — PaintPilot");

    await user.click(screen.getByRole("button", { name: "Test forward" }));
    await waitFor(() =>
      expect(screen.getByLabelText("Current test route")).toHaveTextContent(
        "/paintpilot/projects/new",
      ),
    );
    expect(
      screen.getByRole("heading", { name: "Create paint project", level: 1 }),
    ).toHaveFocus();
    expect(document.title).toBe("Create Project — PaintPilot");
    expect(consoleError).not.toHaveBeenCalled();
  });
});
