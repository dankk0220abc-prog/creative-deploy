import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AppRoutes } from "../router/AppRoutes";
import { jsonResponse, PROJECT_ID } from "../test/paintProjectFixtures";
import {
  REGION_SET_ID,
  regionSetFixture,
  regionWorkbenchFixture,
} from "../test/regionSetFixtures";
import type {
  RegionSet,
  RegionSetHistoryItem,
  RegionSetReview,
} from "../api/regionSets";

const HISTORICAL_ID = "11111111-1111-4111-8111-111111111111";
const CURRENT_ID = "33333333-3333-4333-8333-333333333333";
const FORKED_ID = "44444444-4444-4444-8444-444444444444";

function historyItem(
  snapshot: RegionSet,
  overrides: Partial<RegionSetHistoryItem> = {},
): RegionSetHistoryItem {
  return {
    id: snapshot.id,
    paint_project_id: snapshot.paint_project_id,
    version: snapshot.version,
    lifecycle: snapshot.lifecycle,
    effective_lifecycle: snapshot.effective_lifecycle,
    source_primary_image_asset_id: snapshot.source_primary_image_asset_id,
    source_image_set_fingerprint: snapshot.source_image_set_fingerprint,
    region_count: snapshot.region_count,
    total_vertex_count: snapshot.total_vertex_count,
    geometry_fingerprint: snapshot.geometry_fingerprint,
    stale: snapshot.stale,
    stale_reasons: snapshot.stale_reasons,
    is_current: snapshot.is_current,
    latest_review: snapshot.latest_review,
    created_at: snapshot.created_at,
    ...overrides,
  };
}

function snapshotScenario() {
  const historical = regionSetFixture({
    id: HISTORICAL_ID,
    version: 1,
    lifecycle: "draft",
    effective_lifecycle: "superseded",
    is_current: false,
  });
  const current = regionSetFixture({
    id: CURRENT_ID,
    version: 3,
    lifecycle: "submitted",
    effective_lifecycle: "submitted",
    is_current: true,
  });
  const workbench = regionWorkbenchFixture({
    current_region_set: current,
    history: [
      historyItem(current),
      historyItem(historical),
    ],
  });
  return { current, historical, workbench };
}

function approval(regionSetId: string): RegionSetReview {
  return {
    id: "56565656-5656-4656-8656-565656565656",
    paint_project_id: PROJECT_ID,
    region_set_id: regionSetId,
    version: 1,
    verdict: "approved",
    reason: null,
    actor_type: "user",
    actor_id: "demo-owner",
    actor_display_name_snapshot: "Demo operator",
    created_at: "2026-07-29T03:00:00+00:00",
  };
}

function fetchMock(): ReturnType<typeof vi.fn> {
  return vi.mocked(fetch);
}

function renderWorkspace(projectId = PROJECT_ID) {
  return render(
    <MemoryRouter
      initialEntries={[`/paintpilot/projects/${projectId}/regions`]}
    >
      <AppRoutes />
    </MemoryRouter>,
  );
}

describe("Human Region Annotation Workspace", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("loads directly, focuses its heading, and exposes only human tools", async () => {
    fetchMock().mockResolvedValue(jsonResponse(regionWorkbenchFixture()));
    renderWorkspace();

    expect(
      await screen.findByRole("heading", {
        name: "Region annotation workspace",
        level: 1,
      }),
    ).toHaveFocus();
    expect(screen.getByRole("button", { name: "Draw polygon" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Save new draft snapshot" })).toBeEnabled();
    expect(screen.getByText(/Human-authored polygons only/i)).toBeInTheDocument();
    expect(screen.queryByText(/segmentation/i)).not.toBeInTheDocument();
    expect(fetchMock()).toHaveBeenCalledWith(
      `/api/v1/paint-projects/${PROJECT_ID}/region-sets/workbench`,
      expect.objectContaining({ method: "GET" }),
    );
  });

  it("draws and closes a valid polygon with normalized canvas coordinates", async () => {
    const user = userEvent.setup();
    fetchMock().mockResolvedValue(jsonResponse(regionWorkbenchFixture()));
    renderWorkspace();
    const canvas = await screen.findByRole("img", {
      name: "Private primary image with region overlay",
    });
    vi.spyOn(canvas, "getBoundingClientRect").mockReturnValue({
      bottom: 500,
      height: 500,
      left: 0,
      right: 500,
      top: 0,
      width: 500,
      x: 0,
      y: 0,
      toJSON: () => ({}),
    });
    Object.assign(canvas, {
      releasePointerCapture: vi.fn(),
      setPointerCapture: vi.fn(),
    });

    await user.click(screen.getByRole("button", { name: "Draw polygon" }));
    fireEvent.pointerDown(canvas, { clientX: 50, clientY: 50 });
    fireEvent.pointerDown(canvas, { clientX: 250, clientY: 50 });
    fireEvent.pointerDown(canvas, { clientX: 250, clientY: 250 });
    fireEvent.pointerDown(canvas, { clientX: 50, clientY: 250 });
    await user.click(screen.getByRole("button", { name: "Close polygon" }));

    expect(screen.getByRole("heading", { name: "1 regions" })).toBeInTheDocument();
    expect(screen.getByLabelText("Region 1 region")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Save new draft snapshot" })).toBeEnabled();

    const vertex = screen.getByLabelText("Region 1 vertex 1");
    fireEvent.pointerDown(vertex, { pointerId: 7 });
    fireEvent.pointerMove(canvas, { clientX: 80, clientY: 80, pointerId: 7 });
    fireEvent.pointerUp(canvas, { clientX: 80, clientY: 80, pointerId: 7 });
    await user.click(screen.getByRole("button", { name: "Undo" }));
    await user.click(screen.getByRole("button", { name: "Redo" }));
    expect(screen.getByLabelText("Region 1 region")).toBeInTheDocument();
  });

  it("reorders z-index deterministically and renders the exact human review", async () => {
    const user = userEvent.setup();
    const draft = regionSetFixture();
    const secondRegion = {
      ...draft.regions[0]!,
      id: "12121212-1212-4212-8212-121212121212",
      stable_region_key: "34343434-3434-4434-8434-343434343434",
      label: "skin",
      normalized_label: "skin",
      z_index: 1,
    };
    const review = {
      id: "56565656-5656-4656-8656-565656565656",
      paint_project_id: PROJECT_ID,
      region_set_id: REGION_SET_ID,
      version: 1,
      verdict: "changes_requested" as const,
      reason: "Clarify the boundary.",
      actor_type: "user" as const,
      actor_id: "demo-owner",
      actor_display_name_snapshot: "Demo operator",
      created_at: "2026-07-29T03:00:00+00:00",
    };
    const current = regionSetFixture({
      region_count: 2,
      total_vertex_count: 8,
      regions: [...draft.regions, secondRegion],
    });
    fetchMock().mockResolvedValue(
      jsonResponse(
        regionWorkbenchFixture({
          current_region_set: current,
          history: [
            {
              id: current.id,
              paint_project_id: current.paint_project_id,
              version: current.version,
              latest_review: review,
              lifecycle: "submitted",
              effective_lifecycle: "changes_requested",
              source_primary_image_asset_id:
                current.source_primary_image_asset_id,
              source_image_set_fingerprint:
                current.source_image_set_fingerprint,
              region_count: current.region_count,
              total_vertex_count: current.total_vertex_count,
              geometry_fingerprint: current.geometry_fingerprint,
              stale: false,
              stale_reasons: [],
              is_current: true,
              created_at: current.created_at,
            },
          ],
        }),
      ),
    );
    renderWorkspace();

    const list = await screen.findByRole("list", {
      name: "Regions in back-to-front order",
    });
    await user.click(
      screen.getByRole("button", { name: /hair.*paint.*4 vertices/i }),
    );
    await user.click(screen.getByRole("button", { name: "Move forward" }));

    const labels = Array.from(list.querySelectorAll("li strong")).map(
      (element) => element.textContent,
    );
    expect(labels).toEqual(["skin", "hair"]);
    expect(screen.getByRole("button", { name: "Move forward" })).toBeDisabled();
    expect(
      screen.getByText(
        /Review by Demo operator.*Clarify the boundary\./,
      ),
    ).toBeInTheDocument();
  });

  it("targets the exact displayed current snapshot for review after direct load", async () => {
    const user = userEvent.setup();
    const { current, workbench } = snapshotScenario();
    fetchMock().mockImplementation((input, init) => {
      const url = String(input);
      if (url.endsWith(`/region-sets/${current.id}/reviews`) && init?.method === "POST") {
        return Promise.resolve(jsonResponse(approval(current.id), 201));
      }
      return Promise.resolve(jsonResponse(workbench));
    });
    renderWorkspace();

    expect(
      await screen.findByLabelText("Displayed RegionSet status"),
    ).toHaveTextContent(`v3 · ${current.id}`);
    await user.click(
      screen.getByRole("button", { name: "Approve exact snapshot" }),
    );

    const reviewCall = fetchMock().mock.calls.find(
      ([url, request]) =>
        String(url).endsWith(`/region-sets/${current.id}/reviews`) &&
        request?.method === "POST",
    );
    expect(reviewCall?.[0]).toBe(
      `/api/v1/paint-projects/${PROJECT_ID}/region-sets/${current.id}/reviews`,
    );
    expect(JSON.parse(String(reviewCall?.[1]?.body))).toEqual({
      verdict: "approved",
      reason: null,
    });
  });

  it("locks lifecycle commands while viewing history and forks the exact source", async () => {
    const user = userEvent.setup();
    const { current, historical, workbench } = snapshotScenario();
    const forked = regionSetFixture({
      id: FORKED_ID,
      version: 4,
      lifecycle: "draft",
      effective_lifecycle: "draft",
      is_current: true,
      based_on_region_set_id: historical.id,
      supersedes_region_set_id: current.id,
    });
    fetchMock().mockImplementation((input, init) => {
      const url = String(input);
      if (url.endsWith(`/region-sets/${historical.id}`) && init?.method === "GET") {
        return Promise.resolve(jsonResponse(historical));
      }
      if (url.endsWith(`/region-sets/${historical.id}/drafts`)) {
        return Promise.resolve(jsonResponse(forked, 201));
      }
      return Promise.resolve(jsonResponse(workbench));
    });
    renderWorkspace();

    await screen.findByLabelText("Displayed RegionSet status");
    await user.click(
      screen.getByRole("button", { name: /v1.*superseded/i }),
    );
    expect(await screen.findByText(/Historical snapshot · read-only/i)).toBeVisible();
    expect(screen.getByLabelText("Displayed RegionSet status")).toHaveTextContent(
      `v1 · ${historical.id}`,
    );
    expect(
      screen.queryByRole("button", { name: "Save new draft snapshot" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Submit saved draft" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Approve exact snapshot" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Request changes" }),
    ).not.toBeInTheDocument();
    expect(
      fetchMock().mock.calls.filter(([, request]) => request?.method === "POST"),
    ).toHaveLength(0);

    await user.click(
      screen.getByRole("button", {
        name: "Create new draft from this version",
      }),
    );
    const forkCall = fetchMock().mock.calls.find(([url]) =>
      String(url).endsWith(`/region-sets/${historical.id}/drafts`),
    );
    expect(forkCall?.[0]).toBe(
      `/api/v1/paint-projects/${PROJECT_ID}/region-sets/${historical.id}/drafts`,
    );
    expect(JSON.parse(String(forkCall?.[1]?.body))).toEqual({
      expected_current_region_set_id: current.id,
      expected_current_version: current.version,
    });
    expect(await screen.findByLabelText("Displayed RegionSet status")).toHaveTextContent(
      `v4 · ${forked.id}`,
    );
    expect(
      screen.getByRole("button", { name: "Submit saved draft" }),
    ).toBeEnabled();
  });

  it("returns explicitly to current and does not retain a historical handler target", async () => {
    const user = userEvent.setup();
    const { current, historical, workbench } = snapshotScenario();
    fetchMock().mockImplementation((input, init) => {
      const url = String(input);
      if (url.endsWith(`/region-sets/${historical.id}`) && init?.method === "GET") {
        return Promise.resolve(jsonResponse(historical));
      }
      return Promise.resolve(jsonResponse(workbench));
    });
    renderWorkspace();

    await screen.findByLabelText("Displayed RegionSet status");
    await user.click(
      screen.getByRole("button", { name: /v1.*superseded/i }),
    );
    await screen.findByText(/Historical snapshot · read-only/i);
    await user.click(
      screen.getByRole("button", { name: "Return to current version" }),
    );
    expect(screen.getByLabelText("Displayed RegionSet status")).toHaveTextContent(
      `v3 · ${current.id}`,
    );
    expect(
      screen.getByRole("button", { name: "Approve exact snapshot" }),
    ).toBeEnabled();

    await user.click(
      screen.getByRole("button", { name: /v1.*superseded/i }),
    );
    expect(await screen.findByText(/Historical snapshot · read-only/i)).toBeVisible();
    expect(
      screen.queryByRole("button", { name: "Approve exact snapshot" }),
    ).not.toBeInTheDocument();
  });

  it("locks every command while an asynchronously selected detail is unresolved", async () => {
    const user = userEvent.setup();
    const { historical, workbench } = snapshotScenario();
    let resolveDetail: ((response: Response) => void) | undefined;
    const pendingDetail = new Promise<Response>((resolve) => {
      resolveDetail = resolve;
    });
    fetchMock().mockImplementation((input, init) => {
      const url = String(input);
      if (url.endsWith(`/region-sets/${historical.id}`) && init?.method === "GET") {
        return pendingDetail;
      }
      return Promise.resolve(jsonResponse(workbench));
    });
    renderWorkspace();

    await screen.findByLabelText("Displayed RegionSet status");
    await user.click(
      screen.getByRole("button", { name: /v1.*superseded/i }),
    );
    expect(
      await screen.findByRole("heading", { name: "Loading selected snapshot" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Approve exact snapshot" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Submit saved draft" }),
    ).not.toBeInTheDocument();
    expect(
      fetchMock().mock.calls.filter(([, request]) => request?.method === "POST"),
    ).toHaveLength(0);

    resolveDetail?.(jsonResponse(historical));
    expect(await screen.findByText(/Historical snapshot · read-only/i)).toBeVisible();
  });

  it("keeps a stale current submitted snapshot locked", async () => {
    const stale = regionSetFixture({
      id: CURRENT_ID,
      version: 3,
      lifecycle: "submitted",
      effective_lifecycle: "submitted",
      stale: true,
      stale_reasons: ["image_set_fingerprint_changed"],
      is_current: true,
    });
    fetchMock().mockResolvedValue(
      jsonResponse(
        regionWorkbenchFixture({
          current_region_set: stale,
          history: [historyItem(stale)],
        }),
      ),
    );
    renderWorkspace();

    expect(await screen.findByText(/Source image set changed/i)).toBeVisible();
    expect(
      screen.queryByRole("button", { name: "Approve exact snapshot" }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Submit saved draft" }),
    ).toBeDisabled();
  });

  it("rejects an invalid project ID without a region API call", () => {
    renderWorkspace("not-a-uuid");
    expect(
      screen.getByRole("heading", {
        name: "This project ID is not a valid UUID",
        level: 1,
      }),
    ).toHaveFocus();
    expect(fetchMock()).not.toHaveBeenCalled();
  });
});
