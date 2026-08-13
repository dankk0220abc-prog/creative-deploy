import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { i18n } from "../i18n";
import paintPlanCss from "../index.css?raw";
import { PaintPlanWorkspacePage } from "../pages/PaintPlanWorkspacePage";
import {
  deferred,
  errorEnvelope,
  jsonResponse,
  PROJECT_ID,
} from "../test/paintProjectFixtures";
import {
  OPENAI_PROVIDER_ID,
  PAINT_PLAN_ID,
  paintPlanDocumentFixture,
  paintPlanFixture,
  paintPlanPreviewFixture,
  paintPlanWorkbenchFixture,
  SECOND_PAINT_PLAN_ID,
} from "../test/paintPlanFixtures";

function fetchMock(): ReturnType<typeof vi.fn> {
  return vi.mocked(fetch);
}

function renderWorkspace() {
  return render(
    <MemoryRouter
      initialEntries={[`/paintpilot/projects/${PROJECT_ID}/paint-plans`]}
    >
      <Routes>
        <Route
          element={<PaintPlanWorkspacePage />}
          path="paintpilot/projects/:projectId/paint-plans"
        />
      </Routes>
    </MemoryRouter>,
  );
}

function editedPlanFixture(title: string) {
  return paintPlanFixture({
    id: SECOND_PAINT_PLAN_ID,
    lineage_id: PAINT_PLAN_ID,
    version: 2,
    lineage_revision: 2,
    parent_plan_id: PAINT_PLAN_ID,
    revision_kind: "edited",
    lifecycle: "edited",
    effective_lifecycle: "edited",
    document: paintPlanDocumentFixture({ title }),
    created_by_actor_type: "user",
  });
}

function supersededRootFixture() {
  return paintPlanFixture({
    lifecycle: "superseded",
    effective_lifecycle: "superseded",
    is_current: false,
    allowed_actions: [],
  });
}

describe("Paint Plan workbench", () => {
  beforeEach(async () => {
    vi.stubGlobal("fetch", vi.fn());
    await i18n.changeLanguage("en-US");
    document.title = "Test title";
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("keeps a direct load honest while the governed workbench is pending", () => {
    fetchMock().mockReturnValue(new Promise<Response>(() => undefined));

    renderWorkspace();

    expect(
      screen.getByRole("heading", {
        name: "Loading the Paint Plan workbench",
        level: 1,
      }),
    ).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent(
      /Reading the current reference images/i,
    );
    expect(screen.queryByText("Governed fixture paint plan")).not.toBeInTheDocument();
    expect(document.title).toBe("Paint Plan — PaintPilot");
  });

  it("renders the image-first ready source and structured current revision", async () => {
    fetchMock().mockResolvedValue(jsonResponse(paintPlanWorkbenchFixture()));

    renderWorkspace();

    expect(
      await screen.findByRole("heading", { name: "Paint Plan workbench", level: 1 }),
    ).toBeInTheDocument();
    expect(screen.getAllByRole("img")).toHaveLength(4);
    expect(screen.getByText("Ready to use")).toBeInTheDocument();
    expect(screen.getByText("2", { selector: ".paint-plan-region-summary strong" })).toBeInTheDocument();
    expect(
      screen.getByText("Protected trim", {
        selector: ".paint-plan-region-summary p",
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Paint Plan v1", level: 3 }),
    ).toBeInTheDocument();
    expect(screen.getByText("Not submitted for review")).toBeInTheDocument();
    expect(screen.getByText("Confidence 87.5%")).toBeInTheDocument();
    expect(screen.getByText("Knowledge citations")).toBeInTheDocument();
    expect(
      screen.getByText("surface preparation · /instructions/0/preparation"),
    ).toBeInTheDocument();
    expect(
      within(document.querySelector(".paint-plan-document") as HTMLElement).queryByText(
        "Governed fixture paint plan",
      ),
    ).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Edit Paint Plan" })).toBeEnabled();
    expect(
      screen.getByRole("button", { name: "Submit for review" }),
    ).toBeEnabled();
    const technical = Array.from(
      document.querySelectorAll<HTMLDetailsElement>("details.paint-plan-technical"),
    ).find((details) => details.textContent?.includes("Generated Fixture title"));
    expect(technical).toBeDefined();
    if (technical === undefined) {
      throw new Error("plan technical details were not rendered");
    }
    technical.open = true;
    expect(screen.getByText("Generated Fixture title")).toBeInTheDocument();
    expect(screen.getByText("Governed fixture paint plan")).toBeInTheDocument();
    expect(screen.getByText("Generation locale")).toBeInTheDocument();
    expect(screen.getByText("en-US")).toBeInTheDocument();
    expect(screen.getByText("Generation requested by user ID")).toBeInTheDocument();
    expect(screen.getByText("Invocation created")).toBeInTheDocument();
    expect(screen.getByText("240 test credits")).toBeInTheDocument();
    expect(
      screen.getByText("Generation-time source image assets"),
    ).toBeInTheDocument();
  });

  it("shows OpenAI honestly, previews its live block, and never enables generation", async () => {
    const user = userEvent.setup();
    fetchMock()
      .mockResolvedValueOnce(jsonResponse(paintPlanWorkbenchFixture()))
      .mockResolvedValueOnce(
        jsonResponse(
          paintPlanPreviewFixture({
            admissible: false,
            execution_mode: "live_authorization_required",
            provider_key: "openai",
            model_id: "gpt-live-registry-entry",
            estimated_cost_minor_units: 1234,
            currency: "USD",
            estimate_status: "estimated",
            blockers: ["live_execution_authorization_required"],
          }),
        ),
      );
    renderWorkspace();
    await screen.findByRole("heading", { name: "Paint Plan workbench" });

    await user.selectOptions(screen.getByLabelText("Model source"), OPENAI_PROVIDER_ID);

    expect(screen.getByText("Live authorization required", { selector: "strong" })).toBeInTheDocument();
    expect(screen.getByText(/server-side live gate is off/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Regenerate Paint Plan" })).toBeDisabled();

    await user.click(screen.getByRole("button", { name: "Check generation conditions" }));
    expect(await screen.findByText("Needs attention")).toBeInTheDocument();
    expect(screen.getByText("$12.34")).toBeInTheDocument();
    expect(screen.queryByText("$1,234.00")).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/temporary/i)).not.toBeInTheDocument();
    expect(fetchMock().mock.calls[1]?.[0]).toBe(
      `/api/v1/paint-projects/${PROJECT_ID}/paint-plans/preview`,
    );
    const previewBody = String(fetchMock().mock.calls[1]?.[1]?.body);
    expect(previewBody).toContain(OPENAI_PROVIDER_ID);
    expect(previewBody).not.toMatch(/api[_-]?key|secret|authorization/i);
  });

  it("rejects a preview that does not match the currently selected model", async () => {
    const user = userEvent.setup();
    fetchMock()
      .mockResolvedValueOnce(jsonResponse(paintPlanWorkbenchFixture()))
      .mockResolvedValueOnce(
        jsonResponse(paintPlanPreviewFixture({ model_id: "wrong-model" })),
      );
    renderWorkspace();
    await screen.findByRole("heading", { name: "Paint Plan workbench" });

    await user.click(screen.getByRole("button", { name: "Check generation conditions" }));

    expect(
      await screen.findByText("The command did not reach a confirmed result"),
    ).toBeInTheDocument();
    expect(screen.queryByText("Ready to generate")).not.toBeInTheDocument();
    expect(
      screen.getByLabelText(/I understand this will create one local test plan/i),
    ).toBeDisabled();
    expect(
      screen.getByRole("button", { name: "Regenerate Paint Plan" }),
    ).toBeDisabled();
    expect(
      screen.getByRole("button", { name: "View current revision 1" }),
    ).toBeDisabled();
  });

  it("protects an exact edit draft, then clears preview confirmation on refresh", async () => {
    const user = userEvent.setup();
    const refreshedFacts = deferred<Response>();
    fetchMock()
      .mockResolvedValueOnce(jsonResponse(paintPlanWorkbenchFixture()))
      .mockResolvedValueOnce(jsonResponse(paintPlanPreviewFixture()))
      .mockReturnValueOnce(refreshedFacts.promise);
    renderWorkspace();
    await screen.findByRole("heading", { name: "Paint Plan workbench" });
    await user.click(screen.getByRole("button", { name: "Check generation conditions" }));
    await screen.findByText("Ready to generate");
    await user.click(
      screen.getByLabelText(/I understand this will create one local test plan/i),
    );
    expect(
      screen.getByRole("button", { name: "Regenerate Paint Plan" }),
    ).toBeEnabled();
    await user.click(screen.getByRole("button", { name: "Edit Paint Plan" }));
    expect(
      screen.getByRole("button", { name: "Regenerate Paint Plan" }),
    ).toBeDisabled();
    const titleInput = screen.getByLabelText("Plan title");
    expect(titleInput).toHaveFocus();
    await user.clear(titleInput);
    await user.type(titleInput, "Unsaved revision A");

    expect(screen.getByRole("button", { name: "Refresh" })).toBeDisabled();
    expect(
      screen.getByRole("button", { name: "View current revision 1" }),
    ).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.getByRole("button", { name: "Refresh" })).toBeEnabled();
    await user.click(screen.getByRole("button", { name: "Refresh" }));

    expect(screen.queryByText("Ready to generate")).not.toBeInTheDocument();
    expect(
      screen.getByLabelText(/I understand this will create one local test plan/i),
    ).not.toBeChecked();
    expect(screen.queryByDisplayValue("Unsaved revision A")).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Regenerate Paint Plan" }),
    ).toBeDisabled();

    await act(async () => {
      refreshedFacts.resolve(jsonResponse(paintPlanWorkbenchFixture()));
    });
    expect(
      await screen.findByRole("button", { name: "Edit Paint Plan" }),
    ).toBeEnabled();
    expect(screen.queryByLabelText("Plan title")).not.toBeInTheDocument();
  });

  it("checks and generates one local test revision with a protected command", async () => {
    const user = userEvent.setup();
    const generated = paintPlanFixture({
      id: SECOND_PAINT_PLAN_ID,
      lineage_id: SECOND_PAINT_PLAN_ID,
    });
    const emptyWorkbench = paintPlanWorkbenchFixture({
      current_plan: null,
      history: [],
      allowed_actions: ["read_history", "preview", "generate"],
    });
    const refreshed = paintPlanWorkbenchFixture({
      current_plan: generated,
      history: [generated],
      allowed_actions: ["read_history", "preview", "regenerate"],
    });
    fetchMock()
      .mockResolvedValueOnce(jsonResponse(emptyWorkbench))
      .mockResolvedValueOnce(jsonResponse(paintPlanPreviewFixture()))
      .mockResolvedValueOnce(jsonResponse(generated, 201))
      .mockResolvedValueOnce(jsonResponse(refreshed));
    renderWorkspace();
    await screen.findByRole("heading", { name: "Paint Plan workbench" });

    await user.click(
      screen.getByLabelText(/I understand this will create one local test plan/i),
    );
    await user.click(
      screen.getByRole("button", { name: "Generate Paint Plan" }),
    );

    expect(
      await screen.findByText("A new Paint Plan version was saved."),
    ).toBeInTheDocument();
    const generateCall = fetchMock().mock.calls.find(
      ([input]) => String(input).endsWith("/paint-plans/generate"),
    );
    expect(generateCall?.[1]?.headers).toEqual(
      expect.objectContaining({ "Idempotency-Key": expect.any(String) }),
    );
    expect(String(generateCall?.[1]?.body)).toContain('"confirm_generation":true');
    expect(String(generateCall?.[1]?.body)).toContain('"max_attempts":1');
    expect(String(generateCall?.[1]?.body)).toContain('"generation_locale":"en-US"');
    expect(fetchMock().mock.calls[1]?.[0]).toBe(
      `/api/v1/paint-projects/${PROJECT_ID}/paint-plans/preview`,
    );
  });

  it("sends zh-CN and keeps localized result status separate from raw Fixture provenance", async () => {
    await i18n.changeLanguage("zh-CN");
    const localized = paintPlanFixture({
      generation_locale: "zh-CN",
      document: paintPlanDocumentFixture({
        title: "受管 Fixture 涂装方案 1234abcd",
        overall_approach: "从大面积底色逐步推进至边缘细节，并保留排除区域。",
        instructions: paintPlanDocumentFixture().instructions.map((instruction) => ({
          ...instruction,
          target_color: "暖中性灰",
          preparation: "清洁表面，并均匀轻磨以提高附着力。",
          confidence_ppm: 900_000,
        })),
        safety_notes: ["仅使用已批准的图像与 RegionSet 修订。"],
      }),
    });
    fetchMock().mockResolvedValueOnce(
      jsonResponse(
        paintPlanWorkbenchFixture({
          current_plan: localized,
          history: [localized],
        }),
      ),
    );

    const view = renderWorkspace();

    expect(
      await screen.findByRole("heading", { name: "涂装方案 v1", level: 3 }),
    ).toBeInTheDocument();
    expect(screen.getByText("尚未提交审核")).toBeInTheDocument();
    expect(screen.getAllByText("置信度 90%")).toHaveLength(2);
    expect(screen.queryByText("Fixture 置信度 90%")).not.toBeInTheDocument();
    expect(
      within(view.container.querySelector(".paint-plan-document") as HTMLElement).queryByText(
        "受管 Fixture 涂装方案 1234abcd",
      ),
    ).not.toBeInTheDocument();
    const technical = Array.from(
      view.container.querySelectorAll<HTMLDetailsElement>("details.paint-plan-technical"),
    ).find((details) => details.textContent?.includes("Fixture 生成标题"));
    expect(technical).toBeDefined();
    if (technical === undefined) {
      throw new Error("plan technical details were not rendered");
    }
    expect(within(technical).getByText("Fixture 生成标题")).toBeInTheDocument();
    expect(
      within(technical).getByText("受管 Fixture 涂装方案 1234abcd"),
    ).toBeInTheDocument();
    expect(within(technical).getByText("zh-CN")).toBeInTheDocument();
  });

  it("shows busy and uncertain states, then retries with the same idempotency key", async () => {
    const user = userEvent.setup();
    const pendingGeneration = deferred<Response>();
    const generated = paintPlanFixture({
      id: SECOND_PAINT_PLAN_ID,
      lineage_id: SECOND_PAINT_PLAN_ID,
    });
    const emptyWorkbench = paintPlanWorkbenchFixture({
      current_plan: null,
      history: [],
      allowed_actions: ["read_history", "preview", "generate"],
    });
    fetchMock()
      .mockResolvedValueOnce(jsonResponse(emptyWorkbench))
      .mockResolvedValueOnce(jsonResponse(paintPlanPreviewFixture()))
      .mockReturnValueOnce(pendingGeneration.promise)
      .mockResolvedValueOnce(jsonResponse(generated, 201))
      .mockResolvedValueOnce(
        jsonResponse(
          paintPlanWorkbenchFixture({
            current_plan: generated,
            history: [generated],
            allowed_actions: ["read_history", "preview", "regenerate"],
          }),
        ),
      );
    renderWorkspace();
    await screen.findByRole("heading", { name: "Paint Plan workbench" });
    await user.click(screen.getByRole("button", { name: "Check generation conditions" }));
    await screen.findByText("Ready to generate");
    await user.click(
      screen.getByLabelText(/I understand this will create one local test plan/i),
    );
    await user.click(
      screen.getByRole("button", { name: "Generate Paint Plan" }),
    );

    expect(
      screen.getByRole("button", { name: "Generating Paint Plan…" }),
    ).toBeDisabled();
    expect(
      screen.getByText("Generating Paint Plan…", {
        selector: ".paint-plan-command-progress",
      }),
    ).toHaveAttribute("role", "status");
    const firstGenerateCall = fetchMock().mock.calls.find(([input]) =>
      String(input).endsWith("/paint-plans/generate"),
    );
    await act(async () => {
      pendingGeneration.reject(new TypeError("connection ended"));
      await Promise.resolve();
    });

    expect(
      await screen.findByText("The command did not reach a confirmed result"),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Retry safely" }));
    expect(
      await screen.findByText("A new Paint Plan version was saved."),
    ).toBeInTheDocument();
    const generateCalls = fetchMock().mock.calls.filter(([input]) =>
      String(input).endsWith("/paint-plans/generate"),
    );
    expect(generateCalls).toHaveLength(2);
    const firstHeaders = firstGenerateCall?.[1]?.headers as Record<string, string>;
    const retryHeaders = generateCalls[1]?.[1]?.headers as Record<string, string>;
    expect(retryHeaders["Idempotency-Key"]).toBe(firstHeaders["Idempotency-Key"]);
  });

  it("locks an uncertain edit payload and history context, then retries the exact body", async () => {
    const user = userEvent.setup();
    const edited = editedPlanFixture("Network-safe edit");
    const root = supersededRootFixture();
    fetchMock()
      .mockResolvedValueOnce(jsonResponse(paintPlanWorkbenchFixture()))
      .mockRejectedValueOnce(new TypeError("connection ended"))
      .mockResolvedValueOnce(jsonResponse(edited, 201))
      .mockResolvedValueOnce(
        jsonResponse(
          paintPlanWorkbenchFixture({
            current_plan: edited,
            history: [edited, root],
          }),
        ),
      );
    renderWorkspace();
    await screen.findByRole("heading", { name: "Paint Plan workbench" });
    await user.click(screen.getByRole("button", { name: "Edit Paint Plan" }));
    const titleInput = screen.getByLabelText("Plan title");
    await user.clear(titleInput);
    await user.type(titleInput, "Network-safe edit");
    await user.click(
      screen.getByRole("button", { name: "Save changes" }),
    );

    expect(
      await screen.findByText("The command did not reach a confirmed result"),
    ).toBeInTheDocument();
    expect(titleInput).toBeDisabled();
    expect(
      screen.getByRole("button", { name: "View current revision 1" }),
    ).toBeDisabled();
    const firstEditCall = fetchMock().mock.calls.find(([input]) =>
      String(input).endsWith(`/${PAINT_PLAN_ID}/edits`),
    );
    const firstEditBody = JSON.parse(String(firstEditCall?.[1]?.body)) as {
      document: unknown;
    };
    expect(firstEditBody.document).toEqual(edited.document);
    await user.click(screen.getByRole("button", { name: "Retry safely" }));
    const editCalls = fetchMock().mock.calls.filter(([input]) =>
      String(input).endsWith(`/${PAINT_PLAN_ID}/edits`),
    );
    expect(editCalls).toHaveLength(2);
    expect(editCalls[1]?.[1]?.body).toBe(firstEditCall?.[1]?.body);
    expect(editCalls[1]?.[1]?.headers).toEqual(firstEditCall?.[1]?.headers);
    expect(
      await screen.findByText(
        "The exact edited revision was saved; the prior revision remains immutable.",
      ),
    ).toBeInTheDocument();
  });

  it("fails closed on a revision conflict until authoritative facts are refreshed", async () => {
    const user = userEvent.setup();
    fetchMock()
      .mockResolvedValueOnce(jsonResponse(paintPlanWorkbenchFixture()))
      .mockResolvedValueOnce(
        jsonResponse(
          errorEnvelope({
            allowed_actions: ["reload_paint_plan_workbench"],
            category: "CONFLICT",
            current_state: "changed",
            error_code: "PAINT_PLAN_LIFECYCLE_CONFLICT",
          }),
          409,
        ),
      );
    renderWorkspace();
    await screen.findByRole("heading", { name: "Paint Plan workbench" });
    await user.click(screen.getByRole("button", { name: "Edit Paint Plan" }));
    await user.type(screen.getByLabelText("Plan title"), " conflict");
    await user.click(
      screen.getByRole("button", { name: "Save changes" }),
    );

    expect(
      await screen.findByText(/Refresh authoritative facts before issuing another command/i),
    ).toBeInTheDocument();
    expect(screen.queryByLabelText("Plan title")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Edit Paint Plan" })).toBeDisabled();
    expect(
      screen.getByRole("button", { name: "View current revision 1" }),
    ).toBeDisabled();
    expect(
        screen.getAllByRole("button", { name: "Refresh" }).length,
    ).toBeGreaterThan(0);
  });

  it("uses top-level authority to regenerate a stale current plan from ready new sources", async () => {
    const user = userEvent.setup();
    const staleCurrent = paintPlanFixture({
      stale: true,
      stale_reasons: ["region_geometry_changed"],
      effective_lifecycle: "superseded",
      source_geometry_fingerprint: "c".repeat(64),
      allowed_actions: [],
    });
    const regenerated = paintPlanFixture({
      id: SECOND_PAINT_PLAN_ID,
      lineage_id: SECOND_PAINT_PLAN_ID,
      version: 2,
      lineage_revision: 1,
      parent_plan_id: PAINT_PLAN_ID,
      revision_kind: "regenerated",
    });
    const supersededStale = {
      ...staleCurrent,
      lifecycle: "superseded" as const,
      is_current: false,
    };
    fetchMock()
      .mockResolvedValueOnce(
        jsonResponse(
          paintPlanWorkbenchFixture({
            current_plan: staleCurrent,
            history: [staleCurrent],
            allowed_actions: ["read_history", "preview", "regenerate"],
          }),
        ),
      )
      .mockResolvedValueOnce(jsonResponse(paintPlanPreviewFixture()))
      .mockResolvedValueOnce(jsonResponse(regenerated, 201))
      .mockResolvedValueOnce(
        jsonResponse(
          paintPlanWorkbenchFixture({
            current_plan: regenerated,
            history: [regenerated, supersededStale],
          }),
        ),
      );
    renderWorkspace();
    await screen.findByText("This plan no longer matches current sources");

    await user.click(screen.getByRole("button", { name: "Check generation conditions" }));
    await screen.findByText("Ready to generate");
    await user.click(
      screen.getByLabelText(/I understand this will create one local test plan/i),
    );
    await user.click(
      screen.getByRole("button", { name: "Regenerate Paint Plan" }),
    );

    expect(
      await screen.findByText(
        "A regenerated revision was saved and the former current revision remains in history.",
      ),
    ).toBeInTheDocument();
    expect(
      fetchMock().mock.calls.some(([input]) =>
        String(input).endsWith(`/${PAINT_PLAN_ID}/regenerate`),
      ),
    ).toBe(true);
  });

  it("explains non-source server prerequisites when preview authority is withheld", async () => {
    fetchMock().mockResolvedValue(
      jsonResponse(
        paintPlanWorkbenchFixture({
          blockers: ["project_abandoned"],
          allowed_actions: ["read_history"],
        }),
      ),
    );
    renderWorkspace();

    expect(
      await screen.findByText("Generation is not available yet"),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/project is abandoned, so generation commands are unavailable/i),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Check generation conditions" })).toBeDisabled();
  });

  it("maps the server's exact governed-source blocker keys", async () => {
    fetchMock().mockResolvedValue(
      jsonResponse(
        paintPlanWorkbenchFixture({
          blockers: [
            "image_set_incomplete",
            "image_set_not_ready",
            "image_set_stale",
            "primary_front_changed",
          ],
          current_plan: null,
          history: [],
          image_set_status: "incomplete",
          source_ready: false,
          allowed_actions: ["read_history"],
        }),
      ),
    );
    renderWorkspace();

    expect(
      await screen.findAllByText("The current image snapshot is not ready."),
    ).toHaveLength(2);
    expect(
      screen.getByText("The image snapshot changed or is stale."),
    ).toBeInTheDocument();
    expect(
      screen.getByText("The RegionSet snapshot changed or is stale."),
    ).toBeInTheDocument();
  });

  it("exposes only server-allowed reviewer actions and records a reasoned rejection", async () => {
    const user = userEvent.setup();
    const underReview = paintPlanFixture({
      lifecycle: "under_review",
      effective_lifecycle: "under_review",
      allowed_actions: ["approve", "reject"],
      latest_review: {
        id: "30303030-3030-4030-8030-303030303030",
        action: "submit",
        reason: null,
        actor_id: "owner-user",
        actor_display_name_snapshot: "Local Owner",
        created_at: "2026-08-09T08:55:00+00:00",
      },
    });
    const rejected = paintPlanFixture({
      lifecycle: "rejected",
      effective_lifecycle: "rejected",
      allowed_actions: [],
      latest_review: {
        id: "31313131-3131-4131-8131-313131313131",
        action: "reject",
        reason: "Clarify the second region edge treatment.",
        actor_id: "reviewer-user",
        actor_display_name_snapshot: "Review Operator",
        created_at: "2026-08-09T09:00:00+00:00",
      },
    });
    const reviewerWorkbench = paintPlanWorkbenchFixture({
      access_role: "reviewer",
      credentials: [],
      current_plan: underReview,
      history: [underReview],
      allowed_actions: ["read_history"],
    });
    fetchMock()
      .mockResolvedValueOnce(jsonResponse(reviewerWorkbench))
      .mockResolvedValueOnce(jsonResponse(rejected, 201))
      .mockResolvedValueOnce(
        jsonResponse({
          ...reviewerWorkbench,
          current_plan: rejected,
          history: [rejected],
        }),
      );
    renderWorkspace();

    expect(
      await screen.findByRole("button", { name: "Approve Paint Plan" }),
    ).toBeEnabled();
    const rejectButton = screen.getByRole("button", { name: "Return for changes" });
    expect(rejectButton).toBeDisabled();
    expect(screen.queryByRole("button", { name: /generate/i })).not.toBeInTheDocument();

    await user.type(
      screen.getByLabelText(/Review reason/),
      "Clarify the second region edge treatment.",
    );
    await user.click(rejectButton);

    await waitFor(() => {
      expect(fetchMock().mock.calls.some(([input]) =>
        String(input).endsWith(`/${PAINT_PLAN_ID}/reject`),
      )).toBe(true);
    });
    const rejectionCall = fetchMock().mock.calls.find(([input]) =>
      String(input).endsWith(`/${PAINT_PLAN_ID}/reject`),
    );
    expect(String(rejectionCall?.[1]?.body)).toContain(
      "Clarify the second region edge treatment.",
    );
  });

  it("keeps stale and historical long-content revisions read-only at a 390px viewport", async () => {
    Object.defineProperty(window, "innerWidth", { configurable: true, value: 390 });
    window.dispatchEvent(new Event("resize"));
    const historical = paintPlanFixture({
      id: SECOND_PAINT_PLAN_ID,
      lineage_id: SECOND_PAINT_PLAN_ID,
      version: 1,
      lineage_revision: 1,
      parent_plan_id: null,
      revision_kind: "generated",
      lifecycle: "superseded",
      is_current: false,
      effective_lifecycle: "superseded",
      stale: true,
      stale_reasons: ["region_geometry_changed"],
      source_geometry_fingerprint: "c".repeat(64),
      allowed_actions: [],
    });
    const longTitle = "T".repeat(160);
    const longApproach = "A".repeat(2000);
    const longWarning = "W".repeat(240);
    const longSafety = "S".repeat(400);
    const longRegionLabel = "R".repeat(80);
    const staleDocument = paintPlanDocumentFixture({
      title: longTitle,
      overall_approach: longApproach,
      instructions: paintPlanDocumentFixture().instructions.map(
        (instruction, index) =>
          index === 0
            ? {
                ...instruction,
                region_label: longRegionLabel,
                warnings: [longWarning],
              }
            : instruction,
      ),
      safety_notes: [longSafety],
    });
    const stale = paintPlanFixture({
      lineage_id: SECOND_PAINT_PLAN_ID,
      version: 2,
      lineage_revision: 2,
      parent_plan_id: SECOND_PAINT_PLAN_ID,
      revision_kind: "edited",
      lifecycle: "approved",
      effective_lifecycle: "superseded",
      stale: true,
      stale_reasons: ["region_geometry_changed"],
      approval_valid: false,
      source_geometry_fingerprint: "c".repeat(64),
      latest_review: {
        id: "34343434-3434-4434-8434-343434343434",
        action: "approve",
        reason: "Approved before source drift.",
        actor_id: "reviewer-user",
        actor_display_name_snapshot: "Review Operator",
        created_at: "2026-08-09T09:00:00+00:00",
      },
      allowed_actions: [],
      created_by_actor_type: "user",
      document: staleDocument,
    });
    fetchMock()
      .mockResolvedValueOnce(
        jsonResponse(
          paintPlanWorkbenchFixture({
            current_plan: stale,
            history: [stale, historical],
            allowed_actions: ["read_history", "preview", "regenerate"],
          }),
        ),
      )
      .mockResolvedValueOnce(jsonResponse(paintPlanPreviewFixture()));
    const view = renderWorkspace();

    expect(await screen.findByText("This plan no longer matches current sources")).toBeInTheDocument();
    expect(screen.getByText(longTitle)).toBeInTheDocument();
    expect(screen.getByText(longApproach)).toBeInTheDocument();
    expect(screen.getByText(longWarning)).toBeInTheDocument();
    expect(screen.getByText(longSafety)).toBeInTheDocument();
    expect(screen.getByText(longRegionLabel)).toBeInTheDocument();
    expect(screen.getAllByText("Approved").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Superseded").length).toBeGreaterThan(0);
    expect(
      screen.getAllByText("Approved before source drift.").length,
    ).toBeGreaterThan(0);
    expect(screen.getAllByText("Review Operator").length).toBeGreaterThan(0);
    expect(screen.getAllByRole("img")).toHaveLength(4);
    expect(
      screen.getAllByText(
        "Long technical region label that must wrap safely at mobile width",
      ).length,
    ).toBeGreaterThan(0);
    expect(screen.queryByRole("button", { name: "Edit Paint Plan" })).not.toBeInTheDocument();
    const technicalDetails = view.container.querySelectorAll(
      "details.paint-plan-technical",
    );
    expect(technicalDetails.length).toBeGreaterThan(0);
    technicalDetails.forEach((details) => expect(details).not.toHaveAttribute("open"));

    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Check generation conditions" }));
    await screen.findByText("Ready to generate");
    await user.click(
      screen.getByLabelText(/I understand this will create one local test plan/i),
    );
    expect(
      screen.getByRole("button", { name: "Regenerate Paint Plan" }),
    ).toBeEnabled();

    const history = screen.getByRole("heading", {
      name: "Paint Plan history",
    }).closest("section");
    expect(history).not.toBeNull();
    const historicalButton = within(history as HTMLElement).getByRole("button", {
      name: "View historical revision 1",
    });
    await user.click(historicalButton);
    expect(await screen.findByText("Immutable historical revision")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Check generation conditions" })).toBeDisabled();
    expect(
      screen.getByRole("button", { name: "Regenerate Paint Plan" }),
    ).toBeDisabled();
    await waitFor(() =>
      expect(
        screen.getByRole("heading", { name: "Historical Paint Plan revision" }),
      ).toHaveFocus(),
    );
    const returnButton = screen.getByRole("button", {
      name: "Return to current revision",
    });
    expect(returnButton).toBeEnabled();
    await user.click(returnButton);
    await waitFor(() =>
      expect(
        screen.getByRole("heading", { name: "Current Paint Plan revision" }),
      ).toHaveFocus(),
    );
    expect(
      screen.getByRole("button", { name: "Regenerate Paint Plan" }),
    ).toBeEnabled();
  });

  it("keeps the Paint Plan container and authored long values within mobile gutters", () => {
    expect(paintPlanCss).toMatch(
      /\.page--paint-plan\s*\{[^}]*width:\s*min\(calc\(100% - 3rem\),\s*1500px\)[^}]*margin:\s*0 auto[^}]*grid-template-columns:\s*minmax\(0,\s*1fr\)/s,
    );
    expect(paintPlanCss).toMatch(
      /\.page--paint-plan > \*,[\s\S]*?\.paint-plan-instruction\s*\{[^}]*min-width:\s*0[^}]*max-width:\s*100%/,
    );
    expect(paintPlanCss).toMatch(
      /@media \(max-width:\s*720px\)[\s\S]*?\.page--paint-plan\s*\{[^}]*width:\s*min\(calc\(100% - 2rem\),\s*1500px\)/,
    );
    expect(paintPlanCss).toMatch(
      /@media \(max-width:\s*430px\)[\s\S]*?\.paint-plan-generate\s*\{[^}]*width:\s*calc\(100% - 2rem\)[^}]*margin-inline:\s*1rem/,
    );
    expect(paintPlanCss).toMatch(
      /\.paint-plan-document__intro h3,[\s\S]*?max-width:\s*100%[^}]*overflow-wrap:\s*anywhere/,
    );
    expect(paintPlanCss).toMatch(
      /\.paint-plan-output > \.section-heading h2\s*\{[^}]*max-width:\s*100%[^}]*overflow-wrap:\s*anywhere/,
    );
    expect(paintPlanCss).toMatch(
      /@media \(max-width:\s*720px\)[\s\S]*?\.paint-plan-instruction dl\s*\{[^}]*grid-template-columns:\s*minmax\(0,\s*1fr\)/,
    );
    expect(paintPlanCss).toMatch(
      /\.paint-plan-editor legend\s*\{[^}]*max-width:\s*100%[^}]*overflow-wrap:\s*anywhere/,
    );
    expect(paintPlanCss).toMatch(
      /\.paint-plan-image-grid:has\(> figure:nth-child\(3\)\)[^{]*\{[^}]*repeat\(2/,
    );
    expect(paintPlanCss).toMatch(
      /\.page--paint-plan \.button--quiet,[^}]*\{[^}]*color:\s*var\(--text-secondary\)/,
    );
    expect(paintPlanCss).not.toMatch(/\.page--paint-plan[^}]*overflow-x:\s*hidden/);
  });
});
