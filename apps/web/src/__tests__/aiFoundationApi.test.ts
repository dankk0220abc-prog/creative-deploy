import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  createCredential,
  isZhipuCredentialInputWellFormed,
  listProviders,
  validateTemporaryCredential,
} from "../api/aiFoundation";
import { jsonResponse } from "../test/paintProjectFixtures";

function fetchMock(): ReturnType<typeof vi.fn> {
  return vi.mocked(fetch);
}

function makeFixtureCredential(): string {
  return ["not-a-real-credential", crypto.randomUUID()].join(":");
}

describe("Phase 3A fixture API client", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
    vi.spyOn(Storage.prototype, "setItem");
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("rejects malformed Zhipu token input without normalizing it", () => {
    expect(isZhipuCredentialInputWellFormed("zhipu", "synthetic-zhipu.token_+-~")).toBe(true);
    expect(isZhipuCredentialInputWellFormed("zhipu", "synthetic zhipu token")).toBe(false);
    expect(isZhipuCredentialInputWellFormed("zhipu", "synthetic\tzhipu-token")).toBe(false);
    expect(isZhipuCredentialInputWellFormed("zhipu", "synthetic-zhipu-token\r\n")).toBe(false);
    expect(isZhipuCredentialInputWellFormed("zhipu", "Bearer synthetic-zhipu-token")).toBe(false);
    expect(isZhipuCredentialInputWellFormed("fixture_local", "fixture input unchanged")).toBe(true);
  });

  it("reads explicit local-only provider facts", async () => {
    fetchMock().mockResolvedValue(
      jsonResponse({
        items: [
          {
            id: "3a000000-0000-4000-8000-000000000001",
            provider_key: "fixture_local",
            display_name: "Fixture Provider",
            adapter_type: "fixture_local",
            enabled: true,
            status: "active",
            catalog_status: "bundled",
            catalog_fresh_at: "2026-08-05T00:03:00Z",
            local_only: true,
            real_model_calls: false,
            real_cost: false,
            capabilities: [],
          },
        ],
      }),
    );

    await expect(listProviders()).resolves.toMatchObject([
      {
        provider_key: "fixture_local",
        local_only: true,
        real_model_calls: false,
        real_cost: false,
      },
    ]);
    expect(fetchMock()).toHaveBeenCalledWith(
      "/api/v1/ai/providers",
      expect.objectContaining({ credentials: "same-origin" }),
    );
  });

  it("sends a temporary secret once and never writes it to browser storage", async () => {
    const secret = makeFixtureCredential();
    fetchMock().mockResolvedValue(
      jsonResponse({
        provider_key: "fixture_local",
        valid: true,
        validation_status: "fixture_valid",
        message_code: "FIXTURE_CREDENTIAL_ACCEPTED",
        fixture: true,
        local_only: true,
        persisted: false,
      }),
    );

    await expect(validateTemporaryCredential("fixture_local", secret)).resolves.toMatchObject({
      valid: true,
      persisted: false,
    });
    const [, init] = fetchMock().mock.calls[0] ?? [];
    expect(JSON.parse(String(init?.body))).toEqual({
      provider_key: "fixture_local",
      credential: secret,
    });
    expect(init?.headers).toEqual(
      expect.objectContaining({ "Idempotency-Key": expect.any(String) }),
    );
    expect(Storage.prototype.setItem).not.toHaveBeenCalled();
  });

  it("accepts only a redacted saved-credential response", async () => {
    const secret = makeFixtureCredential();
    fetchMock().mockResolvedValue(
      jsonResponse(
        {
          id: "3a100000-0000-4000-8000-000000000001",
          alias: "Local fixture key",
          provider_key: "fixture_local",
          fingerprint: "fixture-v1:redacted-fingerprint",
          last_four: "cdef",
          status: "active",
          created_at: "2026-08-05T00:03:00Z",
          updated_at: "2026-08-05T00:03:00Z",
          revoked_at: null,
          replaced_at: null,
          last_validation_status: "fixture_valid",
          last_successful_validation_at: "2026-08-05T00:03:00Z",
          revision: 1,
        },
        201,
      ),
    );

    const result = await createCredential("fixture_local", "Local fixture key", secret);
    expect(JSON.stringify(result)).not.toContain(secret);
    expect(result).not.toHaveProperty("credential");
    expect(result).not.toHaveProperty("ciphertext");
    expect(Storage.prototype.setItem).not.toHaveBeenCalled();
  });

  it("maps controlled API failures without exposing server prose", async () => {
    fetchMock().mockResolvedValue(
      jsonResponse(
        {
          error_code: "PHASE3A_FIXTURE_UNAVAILABLE",
          message: "untrusted server prose",
          retryable: false,
        },
        404,
      ),
    );

    await expect(listProviders()).rejects.toEqual(
      expect.objectContaining({
        errorCode: "PHASE3A_FIXTURE_UNAVAILABLE",
        message: "fixture_foundation_request_failed",
        status: 404,
      }),
    );
  });
});
