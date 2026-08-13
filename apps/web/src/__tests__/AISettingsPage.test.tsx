import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { i18n } from "../i18n";
import { AISettingsPage } from "../pages/AISettingsPage";
import { jsonResponse } from "../test/paintProjectFixtures";

const PROVIDER_ID = "5a000000-0000-4000-8000-000000000001";
const MODEL_ID = "5a000000-0000-4000-8000-000000000101";
const OLD_CREDENTIAL_ID = "62426099-53af-41f4-a865-b6de4bee864d";
const NEW_CREDENTIAL_ID = "ec09e045-55e1-4f85-8e2a-bf332d050301";
const now = "2026-08-12T14:00:46Z";

function preference(credentialId: string, revision: number) {
  return {
    enabled: true,
    default_provider_definition_id: PROVIDER_ID,
    default_model_definition_id: MODEL_ID,
    default_credential_id: credentialId,
    timeout_ms: 30_000,
    streaming_enabled: false,
    cost_warning_minor_units: 20,
    currency: "CNY",
    budget_per_invocation_minor_units: 100,
    budget_cumulative_minor_units: 100,
    budget_window_seconds: 86_400,
    revision,
  };
}

function credential(id: string, status: "active" | "revoked") {
  return {
    id,
    alias: status === "active" ? "WP2 replacement" : "WP2 rejected",
    provider_key: "zhipu",
    fingerprint: "redacted-test-fingerprint",
    last_four: null,
    status,
    created_at: now,
    updated_at: now,
    revoked_at: status === "revoked" ? now : null,
    replaced_at: null,
    last_validation_status:
      status === "active" ? "live_validation_not_authorized" : "provider_invalid",
    last_successful_validation_at: null,
    revision: status === "active" ? 4 : 3,
  };
}

describe("AI default route", () => {
  beforeEach(async () => {
    vi.stubGlobal("fetch", vi.fn());
    await i18n.changeLanguage("en-US");
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("submits the active replacement when the persisted default credential was revoked", async () => {
    const submitted: Array<Record<string, unknown>> = [];
    vi.mocked(fetch).mockImplementation(async (input, init) => {
      const path = String(input);
      if (path === "/api/v1/ai/providers") {
        return jsonResponse({
          items: [{
            id: PROVIDER_ID,
            provider_key: "zhipu",
            display_name: "Zhipu BigModel",
            adapter_type: "zhipu_chat_completions",
            enabled: true,
            status: "active",
            catalog_status: "official_pinned",
            catalog_fresh_at: now,
            local_only: false,
            real_model_calls: true,
            real_cost: true,
            capabilities: [],
          }],
        });
      }
      if (path === "/api/v1/ai/capabilities") return jsonResponse({ items: [] });
      if (path === "/api/v1/ai/credentials") {
        return jsonResponse({
          items: [
            credential(NEW_CREDENTIAL_ID, "active"),
            credential(OLD_CREDENTIAL_ID, "revoked"),
          ],
        });
      }
      if (path === "/api/v1/ai/preferences" && init?.method === "PATCH") {
        submitted.push(JSON.parse(String(init.body)) as Record<string, unknown>);
        return jsonResponse(preference(NEW_CREDENTIAL_ID, 2));
      }
      if (path === "/api/v1/ai/preferences") {
        return jsonResponse(
          submitted.length === 0
            ? preference(OLD_CREDENTIAL_ID, 1)
            : preference(NEW_CREDENTIAL_ID, 2),
        );
      }
      if (path === "/api/v1/ai/providers/zhipu/models") {
        return jsonResponse({
          items: [{
            id: MODEL_ID,
            provider_key: "zhipu",
            model_id: "glm-5.2",
            display_name: "GLM-5.2",
            catalog_source: "official_pinned",
            catalog_status: "official_pinned",
            catalog_fresh_at: now,
            status: "active",
            context_window: 128_000,
            pricing_minor_units: 20,
            pricing_currency: "CNY",
            local_only: false,
            capabilities: [],
          }],
        });
      }
      throw new Error(`unexpected request: ${path}`);
    });

    render(
      <MemoryRouter initialEntries={["/paintpilot/settings/ai/models-providers"]}>
        <Routes>
          <Route element={<AISettingsPage />} path="paintpilot/settings/ai/:tab" />
        </Routes>
      </MemoryRouter>,
    );

    const user = userEvent.setup();
    expect(await screen.findByLabelText("Default credential")).toHaveValue(NEW_CREDENTIAL_ID);
    await user.click(screen.getByRole("button", { name: "Save default route" }));

    await waitFor(() => expect(submitted).toHaveLength(1));
    expect(submitted[0]).toMatchObject({
      default_provider_definition_id: PROVIDER_ID,
      default_model_definition_id: MODEL_ID,
      default_credential_id: NEW_CREDENTIAL_ID,
      expected_revision: 1,
    });
    expect(await screen.findByText("Default governed route saved.")).toBeInTheDocument();
  });
});
