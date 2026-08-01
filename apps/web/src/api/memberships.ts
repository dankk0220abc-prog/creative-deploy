import { fetchWithCsrf } from "./auth";

export interface MembershipUser {
  id: string;
  display_name: string;
  email: string | null;
}

export interface ProjectMembership {
  user_id: string;
  role: "reviewer";
  display_name: string;
  email: string | null;
  created_at: string;
}

const uuidPattern =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const timestampPattern = /(Z|[+-]\d{2}:\d{2})$/;

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function hasExactKeys(
  value: Record<string, unknown>,
  expected: readonly string[],
): boolean {
  const actual = Object.keys(value);
  return actual.length === expected.length && expected.every((key) => key in value);
}

function isNullableEmail(value: unknown): value is string | null {
  return (
    value === null ||
    (typeof value === "string" &&
      value.length >= 3 &&
      value.length <= 320 &&
      value === value.trim().toLowerCase())
  );
}

function isMembershipUser(value: unknown): value is MembershipUser {
  return (
    isPlainObject(value) &&
    hasExactKeys(value, ["id", "display_name", "email"]) &&
    typeof value.id === "string" &&
    uuidPattern.test(value.id) &&
    typeof value.display_name === "string" &&
    value.display_name.length >= 1 &&
    value.display_name.length <= 200 &&
    value.display_name === value.display_name.trim() &&
    isNullableEmail(value.email)
  );
}

function isMembership(value: unknown): value is ProjectMembership {
  return (
    isPlainObject(value) &&
    hasExactKeys(value, [
      "user_id",
      "role",
      "display_name",
      "email",
      "created_at",
    ]) &&
    typeof value.user_id === "string" &&
    uuidPattern.test(value.user_id) &&
    value.role === "reviewer" &&
    typeof value.display_name === "string" &&
    value.display_name.length >= 1 &&
    value.display_name.length <= 200 &&
    value.display_name === value.display_name.trim() &&
    isNullableEmail(value.email) &&
    typeof value.created_at === "string" &&
    timestampPattern.test(value.created_at) &&
    Number.isFinite(Date.parse(value.created_at))
  );
}

async function parseItems<T>(
  response: Response,
  validateItem: (value: unknown) => value is T,
): Promise<T[]> {
  if (!response.ok) {
    throw new Error(response.status === 404 ? "membership_not_found" : "membership_failed");
  }
  const payload = (await response.json()) as unknown;
  if (
    !isPlainObject(payload) ||
    !hasExactKeys(payload, ["items"]) ||
    !Array.isArray(payload.items) ||
    !payload.items.every(validateItem)
  ) {
    throw new Error("membership_invalid_response");
  }
  return payload.items;
}

function projectMembershipPath(projectId: string): string {
  return `/api/v1/paint-projects/${projectId}`;
}

export async function listProjectMemberships(
  projectId: string,
  signal?: AbortSignal,
): Promise<ProjectMembership[]> {
  const response = await fetchWithCsrf(
    `${projectMembershipPath(projectId)}/memberships`,
    { headers: { Accept: "application/json" }, signal },
  );
  return parseItems(response, isMembership);
}

export async function listAssignableReviewers(
  projectId: string,
  signal?: AbortSignal,
): Promise<MembershipUser[]> {
  const response = await fetchWithCsrf(
    `${projectMembershipPath(projectId)}/assignable-reviewers`,
    { headers: { Accept: "application/json" }, signal },
  );
  return parseItems(response, isMembershipUser);
}

export async function assignProjectReviewer(
  projectId: string,
  userId: string,
): Promise<ProjectMembership> {
  const response = await fetchWithCsrf(
    `${projectMembershipPath(projectId)}/memberships/${userId}`,
    {
      method: "PUT",
      headers: { Accept: "application/json", "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: userId }),
    },
  );
  if (!response.ok) {
    throw new Error(response.status === 404 ? "reviewer_not_found" : "membership_failed");
  }
  const payload = (await response.json()) as unknown;
  if (!isMembership(payload)) {
    throw new Error("membership_invalid_response");
  }
  return payload;
}

export async function removeProjectReviewer(
  projectId: string,
  userId: string,
): Promise<void> {
  const response = await fetchWithCsrf(
    `${projectMembershipPath(projectId)}/memberships/${userId}`,
    { method: "DELETE" },
  );
  if (response.status !== 204) {
    throw new Error(response.status === 404 ? "reviewer_not_found" : "membership_failed");
  }
}
