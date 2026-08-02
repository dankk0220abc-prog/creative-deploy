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

function installSvgScreenTransform(
  canvas: Element,
  initial: { a: number; d: number; e: number; f: number },
) {
  let transform = initial;
  Object.assign(canvas, {
    createSVGPoint: vi.fn(() => {
      const point = {
        x: 0,
        y: 0,
        matrixTransform: vi.fn(
          (matrix: { a: number; d: number; e: number; f: number }) => ({
            x: point.x * matrix.a + matrix.e,
            y: point.y * matrix.d + matrix.f,
          }),
        ),
      };
      return point;
    }),
    getScreenCTM: vi.fn(() => ({
      inverse: () => transform,
    })),
    releasePointerCapture: vi.fn(),
    setPointerCapture: vi.fn(),
  });
  return {
    set(next: { a: number; d: number; e: number; f: number }) {
      transform = next;
    },
  };
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
    expect(document.title).toBe("Region Annotation — PaintPilot");
    expect(screen.getByRole("link", { name: "Projects" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(screen.getByRole("link", { name: "Create project" })).not.toHaveAttribute(
      "aria-current",
    );
    expect(fetchMock()).toHaveBeenCalledWith(
      `/api/v1/paint-projects/${PROJECT_ID}/region-sets/workbench`,
      expect.objectContaining({ method: "GET" }),
    );
  });

  it("renders stable paint/exclude colors, governed hatch opacity, and clear selection", async () => {
    const user = userEvent.setup();
    const base = regionSetFixture();
    const exclude = {
      ...base.regions[0]!,
      id: "abababab-abab-4bab-8bab-abababababab",
      stable_region_key: "cdcdcdcd-cdcd-4dcd-8dcd-cdcdcdcdcdcd",
      kind: "exclude" as const,
      label: "background",
      normalized_label: "background",
      z_index: 1,
      opacity_ppm: 300_000,
    };
    const current = regionSetFixture({
      region_count: 2,
      total_vertex_count: 8,
      regions: [base.regions[0]!, exclude],
    });
    fetchMock().mockResolvedValue(
      jsonResponse(
        regionWorkbenchFixture({
          current_region_set: current,
          history: [],
        }),
      ),
    );
    renderWorkspace();

    const overlay = await screen.findByRole("img", {
      name: "Private primary image with region overlay",
    });
    const source = overlay.querySelector("image");
    expect(source).not.toBeNull();
    expect(source).toHaveAttribute("href", current.source_content_url);
    const paint = screen.getByLabelText("hair region");
    const excluded = screen.getByLabelText("background region");
    expect(paint).toHaveAttribute("data-region-kind", "paint");
    expect(paint.getAttribute("fill")).not.toContain("url(");
    expect(excluded).toHaveAttribute("data-region-kind", "exclude");
    expect(excluded.getAttribute("fill")).toContain("exclude-pattern");
    expect(overlay).toContainElement(paint);
    expect(paint).toHaveAttribute("stroke", "#ffffff");
    expect(paint).not.toHaveAttribute("vector-effect");
    expect(excluded).toHaveAttribute("stroke", "#102128");
    expect(excluded).toHaveAttribute("fill-opacity", "1");

    const pattern = overlay.querySelector(
      `#exclude-pattern-${exclude.stable_region_key}`,
    );
    expect(pattern?.querySelector("rect")).toHaveAttribute("fill", "#d2a45f");
    expect(pattern?.querySelector("rect")).toHaveAttribute("fill-opacity", "0.3");
    expect(pattern?.querySelector("path")).toHaveAttribute("stroke-opacity", "0.3");

    await user.click(
      screen.getByRole("button", { name: /background.*exclude.*4 vertices/i }),
    );
    expect(excluded).toHaveAttribute("stroke", "#ffffff");
    expect(paint).toHaveAttribute("stroke", "#102128");

    fireEvent.input(screen.getByRole("slider"), { target: { value: "10" } });
    expect(pattern?.querySelector("rect")).toHaveAttribute("fill-opacity", "0.1");
    expect(pattern?.querySelector("path")).toHaveAttribute("stroke-opacity", "0.1");
    expect(excluded).toHaveAttribute("stroke", "#ffffff");

    // Zero is outside the persisted Region contract (10–100%), but the
    // presentation remains defensive if an impossible/stale value reaches it.
    const opacitySlider = screen.getByRole("slider");
    opacitySlider.setAttribute("min", "0");
    fireEvent.input(opacitySlider, { target: { value: "0" } });
    expect(pattern?.querySelector("rect")).toHaveAttribute("fill-opacity", "0");
    expect(pattern?.querySelector("path")).toHaveAttribute("stroke-opacity", "0");
    expect(excluded).toHaveAttribute("stroke", "#ffffff");

    fireEvent.input(screen.getByRole("slider"), { target: { value: "100" } });
    expect(pattern?.querySelector("rect")).toHaveAttribute("fill-opacity", "1");
    expect(pattern?.querySelector("path")).toHaveAttribute("stroke-opacity", "1");
  });

  it("draws and closes a valid polygon with normalized canvas coordinates", async () => {
    const user = userEvent.setup();
    fetchMock().mockResolvedValue(jsonResponse(regionWorkbenchFixture()));
    renderWorkspace();
    const canvas = await screen.findByRole("img", {
      name: "Private primary image with region overlay",
    });
    installSvgScreenTransform(canvas, { a: 2_000, d: 2_000, e: 0, f: 0 });

    await user.click(screen.getByRole("button", { name: "Draw polygon" }));
    fireEvent.pointerDown(canvas, {
      button: 0,
      clientX: 50,
      clientY: 50,
      isPrimary: true,
      pointerType: "mouse",
    });
    fireEvent.pointerDown(canvas, {
      button: 0,
      clientX: 250,
      clientY: 50,
      isPrimary: true,
      pointerType: "mouse",
    });
    fireEvent.pointerDown(canvas, {
      button: 0,
      clientX: 250,
      clientY: 250,
      isPrimary: true,
      pointerType: "mouse",
    });
    fireEvent.pointerDown(canvas, {
      button: 0,
      clientX: 50,
      clientY: 250,
      isPrimary: true,
      pointerType: "mouse",
    });
    await user.click(screen.getByRole("button", { name: "Close polygon" }));

    expect(screen.getByRole("heading", { name: "1 region" })).toBeInTheDocument();
    expect(screen.getByLabelText("Region 1 region")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Save new draft snapshot" })).toBeEnabled();
    expect(screen.getByLabelText("Region 1 region")).toHaveAttribute(
      "points",
      "100000,100000 500000,100000 500000,500000 100000,500000",
    );

    const vertex = screen.getByLabelText("Region 1 vertex 1");
    fireEvent.pointerDown(vertex, { pointerId: 7 });
    fireEvent.pointerMove(canvas, { clientX: 80, clientY: 80, pointerId: 7 });
    fireEvent.pointerUp(canvas, { clientX: 80, clientY: 80, pointerId: 7 });
    await user.click(screen.getByRole("button", { name: "Undo" }));
    await user.click(screen.getByRole("button", { name: "Redo" }));
    expect(screen.getByLabelText("Region 1 region")).toBeInTheDocument();
  });

  it("accepts primary touch points from the image at a 320px canvas", async () => {
    const user = userEvent.setup();
    fetchMock().mockResolvedValue(jsonResponse(regionWorkbenchFixture()));
    renderWorkspace();
    const canvas = await screen.findByRole("img", {
      name: "Private primary image with region overlay",
    });
    const image = canvas.querySelector("image");
    expect(image).not.toBeNull();
    vi.spyOn(canvas, "getBoundingClientRect").mockReturnValue({
      bottom: 320,
      height: 320,
      left: 0,
      right: 320,
      top: 0,
      width: 320,
      x: 0,
      y: 0,
      toJSON: () => ({}),
    });
    installSvgScreenTransform(canvas, { a: 3_125, d: 3_125, e: 0, f: 0 });

    await user.click(screen.getByRole("button", { name: "Draw polygon" }));
    fireEvent.pointerDown(image!, {
      clientX: 32,
      clientY: 32,
      isPrimary: true,
      pointerId: 1,
      pointerType: "touch",
    });
    fireEvent.pointerDown(image!, {
      clientX: 160,
      clientY: 32,
      isPrimary: true,
      pointerId: 2,
      pointerType: "touch",
    });
    fireEvent.pointerDown(image!, {
      clientX: 160,
      clientY: 160,
      isPrimary: true,
      pointerId: 3,
      pointerType: "touch",
    });

    expect(screen.getByRole("button", { name: "Close polygon" })).toBeEnabled();
    expect(screen.getByText("3 points")).toBeInTheDocument();
  });

  it("uses the live SVG screen transform after zoom and resize", async () => {
    const user = userEvent.setup();
    fetchMock().mockResolvedValue(jsonResponse(regionWorkbenchFixture()));
    renderWorkspace();
    const canvas = await screen.findByRole("img", {
      name: "Private primary image with region overlay",
    });
    const image = canvas.querySelector("image");
    expect(image).not.toBeNull();
    const transform = installSvgScreenTransform(canvas, {
      a: 2_000,
      d: 2_000,
      e: 0,
      f: 0,
    });

    await user.click(screen.getByRole("button", { name: "Draw polygon" }));
    fireEvent.pointerDown(canvas, {
      button: 0,
      clientX: 50,
      clientY: 50,
      isPrimary: true,
      pointerType: "mouse",
    });
    fireEvent.wheel(canvas, { deltaY: -100 });
    transform.set({ a: 1_680, d: 1_680, e: 80_000, f: 80_000 });
    fireEvent.pointerDown(image!, {
      button: 0,
      clientX: 100,
      clientY: 50,
      isPrimary: true,
      pointerType: "mouse",
    });
    transform.set({ a: 1_050, d: 1_400, e: 80_000, f: 80_000 });
    fireEvent.pointerDown(image!, {
      button: 0,
      clientX: 200,
      clientY: 200,
      isPrimary: true,
      pointerType: "mouse",
    });
    await user.click(screen.getByRole("button", { name: "Close polygon" }));

    expect(screen.getByLabelText("Region 1 region")).toHaveAttribute(
      "points",
      "100000,100000 248000,164000 290000,360000",
    );
  });

  it("does not add a point from an explicitly interactive SVG overlay", async () => {
    const user = userEvent.setup();
    fetchMock().mockResolvedValue(jsonResponse(regionWorkbenchFixture()));
    renderWorkspace();
    const canvas = await screen.findByRole("img", {
      name: "Private primary image with region overlay",
    });
    installSvgScreenTransform(canvas, { a: 2_000, d: 2_000, e: 0, f: 0 });
    const overlay = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    overlay.setAttribute("data-region-interactive", "true");
    canvas.append(overlay);

    await user.click(screen.getByRole("button", { name: "Draw polygon" }));
    fireEvent.pointerDown(overlay, {
      button: 0,
      clientX: 50,
      clientY: 50,
      isPrimary: true,
      pointerType: "mouse",
    });

    expect(
      screen.queryByRole("group", { name: "Open polygon" }),
    ).not.toBeInTheDocument();
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
    expect(document.title).toBe("Region History — PaintPilot");
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
    expect(document.title).toBe("Region Annotation — PaintPilot");
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
    expect(document.title).toBe("Project Not Found — PaintPilot");
    expect(fetchMock()).not.toHaveBeenCalled();
  });

  it("keeps a safe owner-scoped 404 title after the asynchronous response", async () => {
    fetchMock().mockResolvedValue(
      jsonResponse(
        {
          error_code: "PAINT_PROJECT_NOT_FOUND",
          category: "NOT_FOUND",
          message: "The resource was not found.",
          retryable: false,
          request_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
          current_state: null,
          allowed_actions: [],
          safe_details: {},
        },
        404,
      ),
    );
    renderWorkspace();

    expect(
      await screen.findByRole("heading", {
        name: "This project is unavailable",
        level: 1,
      }),
    ).toBeInTheDocument();
    expect(document.title).toBe("Project Not Found — PaintPilot");
  });
});
