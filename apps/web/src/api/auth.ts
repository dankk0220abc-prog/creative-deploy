const AUTH_SESSION_PATH = "/api/v1/auth/session";
const AUTH_LOGOUT_PATH = "/api/v1/auth/logout";
export const AUTH_EXPIRED_EVENT = "paintpilot-auth-expired";

const uuidPattern =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const timezonePattern = /(Z|[+-]\d{2}:\d{2})$/;

export interface AuthenticatedUser {
  id: string;
  display_name: string;
  email: string | null;
}

export type SessionStatus =
  | { authenticated: false }
  | {
      authenticated: true;
      user: AuthenticatedUser;
      expires_at: string;
    };

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function hasExactKeys(
  value: Record<string, unknown>,
  expected: readonly string[],
): boolean {
  const keys = Object.keys(value);
  return keys.length === expected.length && expected.every((key) => key in value);
}

function isSessionStatus(value: unknown): value is SessionStatus {
  if (!isPlainObject(value) || typeof value.authenticated !== "boolean") {
    return false;
  }
  if (!value.authenticated) {
    return hasExactKeys(value, ["authenticated"]);
  }
  if (
    !hasExactKeys(value, ["authenticated", "user", "expires_at"]) ||
    !isPlainObject(value.user) ||
    !hasExactKeys(value.user, ["id", "display_name", "email"])
  ) {
    return false;
  }
  return (
    typeof value.user.id === "string" &&
    uuidPattern.test(value.user.id) &&
    typeof value.user.display_name === "string" &&
    value.user.display_name.trim() === value.user.display_name &&
    value.user.display_name.length > 0 &&
    (value.user.email === null ||
      (typeof value.user.email === "string" &&
        value.user.email === value.user.email.trim().toLowerCase())) &&
    typeof value.expires_at === "string" &&
    timezonePattern.test(value.expires_at) &&
    Number.isFinite(Date.parse(value.expires_at))
  );
}

function cookieValue(names: readonly string[]): string | null {
  for (const entry of document.cookie.split(";")) {
    const separator = entry.indexOf("=");
    if (separator < 0) {
      continue;
    }
    const name = entry.slice(0, separator).trim();
    if (names.includes(name)) {
      return decodeURIComponent(entry.slice(separator + 1));
    }
  }
  return null;
}

export function csrfToken(): string | null {
  return cookieValue(["__Host-paintpilot_csrf", "paintpilot_csrf"]);
}

export async function fetchWithCsrf(
  input: RequestInfo | URL,
  init: RequestInit = {},
): Promise<Response> {
  const method = (init.method ?? "GET").toUpperCase();
  let headers = init.headers;
  if (!["GET", "HEAD", "OPTIONS", "TRACE"].includes(method)) {
    const token = csrfToken();
    if (token !== null) {
      const csrfHeaders = new Headers(init.headers);
      csrfHeaders.set("X-CSRF-Token", token);
      headers = csrfHeaders;
    }
  }
  const response = await fetch(input, {
    ...init,
    credentials: "same-origin",
    headers,
  });
  if (response.status === 401) {
    window.dispatchEvent(new Event(AUTH_EXPIRED_EVENT));
  }
  return response;
}

export async function getSessionStatus(signal?: AbortSignal): Promise<SessionStatus> {
  const response = await fetch(AUTH_SESSION_PATH, {
    method: "GET",
    credentials: "same-origin",
    headers: { Accept: "application/json" },
    signal,
  });
  if (!response.ok) {
    throw new Error("session_unavailable");
  }
  const payload = (await response.json()) as unknown;
  if (!isSessionStatus(payload)) {
    throw new Error("session_invalid");
  }
  return payload;
}

export async function logout(): Promise<void> {
  const response = await fetchWithCsrf(AUTH_LOGOUT_PATH, { method: "POST" });
  if (response.status !== 204) {
    throw new Error("logout_failed");
  }
}

export function loginUrl(returnTo: string): string {
  const safeReturn = returnTo.startsWith("/paintpilot") || returnTo.startsWith("/arcana")
    ? returnTo
    : "/paintpilot/projects";
  return `/api/v1/auth/login?${new URLSearchParams({ return_to: safeReturn })}`;
}
