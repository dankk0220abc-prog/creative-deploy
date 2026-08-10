import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Link, MemoryRouter } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../api/paintPlans", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api/paintPlans")>();
  return { ...actual, phase3bPaintPlanEnabled: true };
});

vi.mock("../api/aiFoundation", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api/aiFoundation")>();
  return { ...actual, phase3aFixtureEnabled: true };
});

import { AppRoutes } from "../router/AppRoutes";
import {
  imageSetFixture,
  jsonResponse,
  PROJECT_ID,
  projectFixture,
  SECOND_PROJECT_ID,
} from "../test/paintProjectFixtures";
import {
  paintPlanPreviewFixture,
  paintPlanWorkbenchFixture,
} from "../test/paintPlanFixtures";

function fetchMock(): ReturnType<typeof vi.fn> {
  return vi.mocked(fetch);
}

function renderRoute(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AppRoutes />
    </MemoryRouter>,
  );
}

function workbenchForProject(projectId: string) {
  const workbench = paintPlanWorkbenchFixture({
    current_plan: null,
    history: [],
    allowed_actions: ["read_history", "preview", "generate"],
  });
  return {
    ...workbench,
    paint_project_id: projectId,
    image_assets: workbench.image_assets.map((asset) => ({
      ...asset,
      content_url: `/api/v1/paint-projects/${projectId}/images/${asset.id}/content`,
    })),
  };
}

describe("Phase 3B project routes", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
    document.title = "Test title";
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("loads the flagged Paint Plan route with Projects active, exact title, and h1 focus", async () => {
    fetchMock().mockResolvedValue(jsonResponse(paintPlanWorkbenchFixture()));

    renderRoute(`/paintpilot/projects/${PROJECT_ID}/paint-plans`);

    const heading = await screen.findByRole("heading", {
      name: "Paint Plan workbench",
      level: 1,
    });
    expect(heading).toHaveFocus();
    expect(document.title).toBe("Paint Plan — PaintPilot");
    const navigation = screen.getByRole("navigation", {
      name: "PaintPilot navigation",
    });
    expect(within(navigation).getByRole("link", { name: "Projects" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(
      within(navigation).getByRole("link", { name: "AI settings" }),
    ).not.toHaveAttribute("aria-current");
  });

  it("adds one sequenced Paint Plan entry and keeps AI policy as a technical setting", async () => {
    fetchMock()
      .mockResolvedValueOnce(jsonResponse(projectFixture()))
      .mockResolvedValueOnce(jsonResponse(imageSetFixture()))
      .mockResolvedValueOnce(jsonResponse({ items: [] }));

    renderRoute(`/paintpilot/projects/${PROJECT_ID}`);

    await screen.findByRole("heading", {
      name: "Cel-shaded garage kit",
      level: 1,
    });
    const localNavigation = screen.getByRole("navigation", {
      name: "Project workspace sections",
    });
    const paintPlanLink = within(localNavigation).getByRole("link", {
      name: /04\s*Paint Plan/,
    });
    expect(paintPlanLink).toHaveAttribute(
      "href",
      `/paintpilot/projects/${PROJECT_ID}/paint-plans`,
    );
    expect(
      screen.getByRole("heading", {
        name: "Build and review the structured Paint Plan",
      }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open Paint Plan" })).toHaveAttribute(
      "href",
      `/paintpilot/projects/${PROJECT_ID}/paint-plans`,
    );
    expect(
      screen.getByRole("link", { name: "Technical AI settings" }),
    ).toHaveAttribute(
      "href",
      `/paintpilot/projects/${PROJECT_ID}/ai-model-policy`,
    );
    expect(
      screen.queryByRole("heading", { name: "Set the project AI model policy" }),
    ).not.toBeInTheDocument();
  });

  it("remounts project-bound preview, draft, and retry state when the route project changes", async () => {
    const user = userEvent.setup();
    fetchMock()
      .mockResolvedValueOnce(jsonResponse(paintPlanWorkbenchFixture()))
      .mockResolvedValueOnce(jsonResponse(paintPlanPreviewFixture()))
      .mockRejectedValueOnce(new TypeError("connection ended"))
      .mockResolvedValueOnce(jsonResponse(workbenchForProject(SECOND_PROJECT_ID)));
    render(
      <MemoryRouter
        initialEntries={[`/paintpilot/projects/${PROJECT_ID}/paint-plans`]}
      >
        <Link to={`/paintpilot/projects/${SECOND_PROJECT_ID}/paint-plans`}>
          Switch project
        </Link>
        <AppRoutes />
      </MemoryRouter>,
    );
    await screen.findByRole("heading", { name: "Paint Plan workbench" });
    await user.click(screen.getByRole("button", { name: "Check generation conditions" }));
    await screen.findByText("Ready to generate");
    await user.click(
      screen.getByLabelText(/I understand this will create one local test plan/i),
    );
    await user.click(screen.getByRole("button", { name: "Edit Paint Plan" }));
    await user.type(screen.getByLabelText("Plan title"), " project A draft");
    await user.click(
      screen.getByRole("button", { name: "Save changes" }),
    );
    expect(await screen.findByRole("button", { name: "Retry safely" })).toBeEnabled();

    await user.click(screen.getByRole("link", { name: "Switch project" }));

    await screen.findByRole("heading", { name: "Paint Plan workbench" });
    expect(
      screen.getByRole("link", { name: "Back to project" }),
    ).toHaveAttribute("href", `/paintpilot/projects/${SECOND_PROJECT_ID}`);
    expect(screen.queryByText("Ready to generate")).not.toBeInTheDocument();
    expect(
      screen.getByLabelText(/I understand this will create one local test plan/i),
    ).not.toBeChecked();
    expect(screen.queryByDisplayValue(/project A draft/)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Retry safely" })).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Generate Paint Plan" }),
    ).toBeDisabled();
  });
});
