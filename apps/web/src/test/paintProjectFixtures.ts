import type { PaintProject } from "../api/paintProjects";

export const PROJECT_ID = "11111111-1111-4111-8111-111111111111";
export const SECOND_PROJECT_ID = "22222222-2222-4222-8222-222222222222";
export const REQUEST_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";

export function projectFixture(
  overrides: Partial<PaintProject> = {},
): PaintProject {
  return {
    id: PROJECT_ID,
    owner_principal_id: "local-demo-owner",
    title: "Cel-shaded garage kit",
    description: "A controlled planning study for a graphic two-shadow finish.",
    requested_target_style: "cel_shading",
    planning_mode: "planning_only_demo",
    status: "DRAFT",
    created_at: "2026-07-27T08:10:00+00:00",
    updated_at: "2026-07-27T08:10:00+00:00",
    ...overrides,
  };
}

export function errorEnvelope(
  overrides: Partial<{
    allowed_actions: string[];
    category: string;
    current_state: string | null;
    error_code: string;
    message: string;
    request_id: string;
    retryable: boolean;
    safe_details: Record<string, unknown>;
  }> = {},
) {
  return {
    error_code: "INTERNAL_ERROR",
    category: "INTERNAL_ERROR",
    message: "The request could not be completed.",
    retryable: false,
    request_id: REQUEST_ID,
    current_state: null,
    allowed_actions: [],
    safe_details: {},
    ...overrides,
  };
}

export function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

export function deferred<T>() {
  let resolve!: (value: T | PromiseLike<T>) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, reject, resolve };
}
