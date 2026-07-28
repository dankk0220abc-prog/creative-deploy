import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  createPaintProject,
  getPaintProject,
  listPaintProjects,
  normalizeCreatePaintProjectInput,
  PAINT_PROJECTS_PATH,
  PaintProjectApiError,
} from "../api/paintProjects";
import {
  errorEnvelope,
  jsonResponse,
  PROJECT_ID,
  projectFixture,
} from "../test/paintProjectFixtures";

const IDEMPOTENCY_KEY = "33333333-3333-4333-8333-333333333333";

function fetchMock(): ReturnType<typeof vi.fn> {
  return vi.mocked(fetch);
}

async function caughtApiError(promise: Promise<unknown>): Promise<PaintProjectApiError> {
  try {
    await promise;
  } catch (error: unknown) {
    expect(error).toBeInstanceOf(PaintProjectApiError);
    return error as PaintProjectApiError;
  }
  throw new Error("Expected the API request to reject.");
}

describe("PaintProject API client", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("normalizes the only two approved create fields", () => {
    expect(
      normalizeCreatePaintProjectInput("  Unicode 工程  ", "   "),
    ).toEqual({
      title: "Unicode 工程",
      description: null,
    });
    expect(
      normalizeCreatePaintProjectInput("Project", "  Planning context  "),
    ).toEqual({
      title: "Project",
      description: "Planning context",
    });
  });

  it("creates with a UUID Idempotency-Key and accepts only HTTP 201", async () => {
    const project = projectFixture();
    fetchMock().mockResolvedValue(jsonResponse(project, 201));

    await expect(
      createPaintProject(
        { title: project.title, description: project.description },
        IDEMPOTENCY_KEY,
      ),
    ).resolves.toEqual(project);

    expect(fetchMock()).toHaveBeenCalledTimes(1);
    const [path, init] = fetchMock().mock.calls[0] ?? [];
    expect(path).toBe(PAINT_PROJECTS_PATH);
    expect(init).toMatchObject({
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "Idempotency-Key": IDEMPOTENCY_KEY,
      },
    });
    expect(JSON.parse(String(init?.body))).toEqual({
      title: project.title,
      description: project.description,
    });
  });

  it("rejects an invalid idempotency key without making a request", async () => {
    const error = await caughtApiError(
      createPaintProject({ title: "Project", description: null }, "not-a-uuid"),
    );

    expect(error.kind).toBe("validation");
    expect(fetchMock()).not.toHaveBeenCalled();
  });

  it("reads the stable list envelope and sends bounded pagination inputs", async () => {
    const project = projectFixture();
    fetchMock().mockResolvedValue(
      jsonResponse({ items: [project], total: 1, limit: 20, offset: 20 }),
    );

    await expect(
      listPaintProjects({ limit: 20, offset: 20 }),
    ).resolves.toEqual({
      items: [project],
      total: 1,
      limit: 20,
      offset: 20,
    });
    expect(fetchMock()).toHaveBeenCalledWith(
      `${PAINT_PROJECTS_PATH}?limit=20&offset=20`,
      expect.objectContaining({ method: "GET" }),
    );
  });

  it("reads a project detail by its validated UUID", async () => {
    const project = projectFixture();
    fetchMock().mockResolvedValue(jsonResponse(project));

    await expect(getPaintProject(PROJECT_ID)).resolves.toEqual(project);
    expect(fetchMock()).toHaveBeenCalledWith(
      `${PAINT_PROJECTS_PATH}/${PROJECT_ID}`,
      expect.objectContaining({ method: "GET" }),
    );
  });

  it("accepts exact create, list, detail, and error contracts through public calls", async () => {
    const project = projectFixture();
    fetchMock()
      .mockResolvedValueOnce(jsonResponse(project, 201))
      .mockResolvedValueOnce(
        jsonResponse({ items: [project], total: 1, limit: 20, offset: 0 }),
      )
      .mockResolvedValueOnce(jsonResponse(project))
      .mockResolvedValueOnce(
        jsonResponse(
          errorEnvelope({
            category: "IDEMPOTENCY_KEY_REUSED",
            error_code: "IDEMPOTENCY_KEY_REUSED",
          }),
          409,
        ),
      );

    await expect(
      createPaintProject(
        { title: project.title, description: project.description },
        IDEMPOTENCY_KEY,
      ),
    ).resolves.toEqual(project);
    await expect(listPaintProjects()).resolves.toEqual({
      items: [project],
      total: 1,
      limit: 20,
      offset: 0,
    });
    await expect(getPaintProject(PROJECT_ID)).resolves.toEqual(project);
    await expect(
      caughtApiError(
        createPaintProject(
          { title: project.title, description: project.description },
          IDEMPOTENCY_KEY,
        ),
      ),
    ).resolves.toMatchObject({ kind: "conflict", status: 409 });
  });

  it("rejects a detail response with a tenth top-level field", async () => {
    fetchMock().mockResolvedValue(
      jsonResponse({ ...projectFixture(), unexpected_field: "not approved" }),
    );

    const error = await caughtApiError(getPaintProject(PROJECT_ID));
    expect(error.kind).toBe("invalid_response");
  });

  it.each([
    "id",
    "owner_principal_id",
    "title",
    "description",
    "requested_target_style",
    "planning_mode",
    "status",
    "created_at",
    "updated_at",
  ])("rejects a Project response missing %s", async (field) => {
    const incompleteProject: Record<string, unknown> = { ...projectFixture() };
    Reflect.deleteProperty(incompleteProject, field);
    fetchMock().mockResolvedValue(jsonResponse(incompleteProject));

    const error = await caughtApiError(getPaintProject(PROJECT_ID));
    expect(error.kind).toBe("invalid_response");
  });

  it("rejects a list envelope with an extra top-level field", async () => {
    fetchMock().mockResolvedValue(
      jsonResponse({
        items: [projectFixture()],
        total: 1,
        limit: 20,
        offset: 0,
        next_page: null,
      }),
    );

    const error = await caughtApiError(listPaintProjects());
    expect(error.kind).toBe("invalid_response");
  });

  it("rejects a list item with an extra field", async () => {
    fetchMock().mockResolvedValue(
      jsonResponse({
        items: [{ ...projectFixture(), internal_note: "not approved" }],
        total: 1,
        limit: 20,
        offset: 0,
      }),
    );

    const error = await caughtApiError(listPaintProjects());
    expect(error.kind).toBe("invalid_response");
  });

  it("does not request a malformed detail UUID", async () => {
    const error = await caughtApiError(getPaintProject("unsafe-id"));
    expect(error.kind).toBe("validation");
    expect(fetchMock()).not.toHaveBeenCalled();
  });

  it.each([
    {
      expectedKind: "not_found",
      expectedRetryable: false,
      status: 404,
      envelope: errorEnvelope({
        error_code: "PAINT_PROJECT_NOT_FOUND",
        category: "NOT_FOUND",
      }),
    },
    {
      expectedKind: "conflict",
      expectedRetryable: false,
      status: 409,
      envelope: errorEnvelope({
        error_code: "IDEMPOTENCY_KEY_REUSED",
        category: "IDEMPOTENCY_KEY_REUSED",
      }),
    },
    {
      expectedKind: "validation",
      expectedRetryable: false,
      status: 422,
      envelope: errorEnvelope({
        error_code: "REQUEST_VALIDATION_FAILED",
        category: "VALIDATION_ERROR",
        safe_details: {
          fields: [
            { field: "title", message: "Untrusted server prose." },
            { field: "body.description", message: "Untrusted server prose." },
          ],
        },
      }),
    },
    {
      expectedKind: "internal",
      expectedRetryable: false,
      status: 500,
      envelope: errorEnvelope(),
    },
    {
      expectedKind: "unavailable",
      expectedRetryable: true,
      status: 503,
      envelope: errorEnvelope({
        error_code: "DATABASE_UNAVAILABLE",
        category: "DATABASE_UNAVAILABLE",
        retryable: true,
        allowed_actions: ["retry"],
      }),
    },
  ])(
    "maps HTTP $status to a controlled $expectedKind error",
    async ({ envelope, expectedKind, expectedRetryable, status }) => {
      fetchMock().mockResolvedValue(jsonResponse(envelope, status));

      const error = await caughtApiError(getPaintProject(PROJECT_ID));
      expect(error).toMatchObject({
        kind: expectedKind,
        retryable: expectedRetryable,
        status,
      });
      if (status === 422) {
        expect(error.fieldNames).toEqual(["title", "description"]);
      }
    },
  );

  it("rejects an error envelope with an extra top-level field", async () => {
    fetchMock().mockResolvedValue(
      jsonResponse({ ...errorEnvelope(), debug: "not approved" }, 500),
    );

    const error = await caughtApiError(getPaintProject(PROJECT_ID));
    expect(error.kind).toBe("invalid_response");
    expect(error.status).toBe(500);
  });

  it("suppresses a synthetic secret stored only in an unapproved error field", async () => {
    const secretText =
      "postgresql://audit:EXTRA_FIELD_SECRET@private.invalid/paintpilot";
    const consoleError = vi
      .spyOn(console, "error")
      .mockImplementation(() => undefined);
    const consoleWarn = vi
      .spyOn(console, "warn")
      .mockImplementation(() => undefined);
    fetchMock().mockResolvedValue(
      jsonResponse(
        {
          ...errorEnvelope(),
          unapproved_diagnostics: secretText,
        },
        500,
      ),
    );

    const error = await caughtApiError(getPaintProject(PROJECT_ID));
    expect(error.kind).toBe("invalid_response");
    expect(error.message).not.toContain("EXTRA_FIELD_SECRET");
    expect(JSON.stringify(error)).not.toContain("private.invalid");
    expect(consoleError).not.toHaveBeenCalled();
    expect(consoleWarn).not.toHaveBeenCalled();
  });

  it("fails safely for non-JSON, empty, and schema-invalid success responses", async () => {
    fetchMock()
      .mockResolvedValueOnce(new Response("<html>failure</html>", { status: 503 }))
      .mockResolvedValueOnce(new Response("", { status: 200 }))
      .mockResolvedValueOnce(jsonResponse({ id: PROJECT_ID }, 200));

    for (let attempt = 0; attempt < 3; attempt += 1) {
      const error = await caughtApiError(getPaintProject(PROJECT_ID));
      expect(error.kind).toBe("invalid_response");
    }
  });

  it.each([
    ["array", []],
    ["null", null],
    ["Date serialization", new Date("2026-07-27T08:10:00Z")],
    ["non-plain Response serialization", new Response("not a project")],
  ])("rejects a %s success body at the JSON boundary", async (_label, payload) => {
    fetchMock().mockResolvedValue(jsonResponse(payload));

    const error = await caughtApiError(getPaintProject(PROJECT_ID));
    expect(error.kind).toBe("invalid_response");
  });

  it("does not copy a server secret, URL, or stack text into a client error", async () => {
    const secretText =
      "postgresql://admin:SECRET_PASSWORD@private-db/paintpilot STACK_TRACE";
    fetchMock().mockResolvedValue(
      jsonResponse(
        errorEnvelope({
          message: secretText,
          safe_details: { internal: secretText },
        }),
        500,
      ),
    );

    const error = await caughtApiError(getPaintProject(PROJECT_ID));
    expect(error.message).not.toContain("SECRET_PASSWORD");
    expect(JSON.stringify(error)).not.toContain("private-db");
    expect(error).not.toHaveProperty("envelope");
  });

  it("classifies a transport failure without exposing the thrown message", async () => {
    fetchMock().mockRejectedValue(
      new TypeError("fetch https://secret.internal failed with token=secret"),
    );

    const error = await caughtApiError(listPaintProjects());
    expect(error.kind).toBe("network");
    expect(error.retryable).toBe(true);
    expect(error.message).not.toContain("secret.internal");
  });

  it.each([502, 504])(
    "maps an intermediary %s without a body to the retryable API-unavailable state",
    async (status) => {
      fetchMock().mockResolvedValue(new Response(null, { status }));

      const error = await caughtApiError(listPaintProjects());
      expect(error).toMatchObject({
        kind: "network",
        retryable: true,
        status,
      });
    },
  );

  it("classifies caller abort separately and forwards the signal", async () => {
    fetchMock().mockImplementation(
      (_input: RequestInfo | URL, init?: RequestInit) =>
        new Promise<Response>((_resolve, reject) => {
          init?.signal?.addEventListener(
            "abort",
            () => reject(new DOMException("Aborted", "AbortError")),
            { once: true },
          );
        }),
    );
    const controller = new AbortController();
    const request = listPaintProjects({ signal: controller.signal });

    controller.abort();

    const error = await caughtApiError(request);
    expect(error.kind).toBe("aborted");
    expect(error.retryable).toBe(false);
  });

  it("rejects a malformed error envelope instead of trusting its message", async () => {
    fetchMock().mockResolvedValue(
      jsonResponse(
        {
          error_code: "DATABASE_UNAVAILABLE",
          category: "DATABASE_UNAVAILABLE",
          message: "unsafe",
          retryable: true,
        },
        503,
      ),
    );

    const error = await caughtApiError(listPaintProjects());
    expect(error.kind).toBe("invalid_response");
  });
});
