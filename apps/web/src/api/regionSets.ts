const uuidPattern =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const sha256Pattern = /^[0-9a-f]{64}$/;
const timezonePattern = /(Z|[+-]\d{2}:\d{2})$/;

export const regionKinds = ["paint", "exclude"] as const;
export const regionLifecycles = [
  "draft",
  "submitted",
  "approved",
  "changes_requested",
  "superseded",
] as const;
export const regionReviewVerdicts = ["approved", "changes_requested"] as const;

export type RegionKind = (typeof regionKinds)[number];
export type RegionLifecycle = (typeof regionLifecycles)[number];
export type RegionReviewVerdict = (typeof regionReviewVerdicts)[number];

export interface RegionVertexInput {
  x_ppm: number;
  y_ppm: number;
}

export interface RegionDraftInput {
  stable_region_key: string;
  kind: RegionKind;
  label: string;
  z_index: number;
  opacity_ppm: number;
  notes: string | null;
  vertices: RegionVertexInput[];
}

export interface RegionVertex extends RegionVertexInput {
  sequence: number;
}

export interface Region {
  id: string;
  stable_region_key: string;
  kind: RegionKind;
  label: string;
  normalized_label: string;
  z_index: number;
  opacity_ppm: number;
  notes: string | null;
  vertex_count: number;
  area_twice_ppm_squared: number;
  bbox_min_x_ppm: number;
  bbox_min_y_ppm: number;
  bbox_max_x_ppm: number;
  bbox_max_y_ppm: number;
  vertices: RegionVertex[];
}

export interface RegionSetReview {
  id: string;
  paint_project_id: string;
  region_set_id: string;
  version: number;
  verdict: RegionReviewVerdict;
  reason: string | null;
  actor_type: "user";
  actor_id: string;
  actor_display_name_snapshot: string;
  created_at: string;
}

export interface RegionSetHistoryItem {
  id: string;
  paint_project_id: string;
  version: number;
  lifecycle: RegionLifecycle;
  effective_lifecycle: RegionLifecycle;
  source_primary_image_asset_id: string;
  source_image_set_fingerprint: string;
  region_count: number;
  total_vertex_count: number;
  geometry_fingerprint: string;
  stale: boolean;
  stale_reasons: string[];
  is_current: boolean;
  latest_review: RegionSetReview | null;
  created_at: string;
}

export interface RegionSet extends RegionSetHistoryItem {
  source_image_width: number;
  source_image_height: number;
  source_content_url: string;
  supersedes_region_set_id: string | null;
  based_on_region_set_id: string | null;
  overlap_warnings: string[];
  regions: Region[];
}

export interface RegionWorkbench {
  paint_project_id: string;
  image_set_status: "incomplete" | "ready" | "stale" | "not_ready";
  current_image_set_fingerprint: string;
  source_primary_image_asset_id: string | null;
  source_image_width: number | null;
  source_image_height: number | null;
  source_content_url: string | null;
  can_create_draft: boolean;
  current_region_set: RegionSet | null;
  history: RegionSetHistoryItem[];
}

export interface SaveRegionSetInput {
  base_region_set_id: string | null;
  base_version: number | null;
  regions: RegionDraftInput[];
}

export interface ForkRegionSetDraftInput {
  expected_current_region_set_id: string;
  expected_current_version: number;
}

export interface CreateRegionSetReviewInput {
  verdict: RegionReviewVerdict;
  reason: string | null;
}

export type RegionSetApiErrorKind =
  | "aborted"
  | "conflict"
  | "internal"
  | "invalid_response"
  | "network"
  | "not_found"
  | "validation";

export class RegionSetApiError extends Error {
  readonly errorCode: string | null;
  readonly kind: RegionSetApiErrorKind;
  readonly retryable: boolean;
  readonly status: number | null;

  constructor(
    kind: RegionSetApiErrorKind,
    message: string,
    options: {
      errorCode?: string;
      retryable?: boolean;
      status?: number;
    } = {},
  ) {
    super(message);
    this.name = "RegionSetApiError";
    this.kind = kind;
    this.errorCode = options.errorCode ?? null;
    this.retryable = options.retryable ?? false;
    this.status = options.status ?? null;
  }
}

const reviewKeys = Object.freeze([
  "id",
  "paint_project_id",
  "region_set_id",
  "version",
  "verdict",
  "reason",
  "actor_type",
  "actor_id",
  "actor_display_name_snapshot",
  "created_at",
] satisfies ReadonlyArray<keyof RegionSetReview>);

const historyKeys = Object.freeze([
  "id",
  "paint_project_id",
  "version",
  "lifecycle",
  "effective_lifecycle",
  "source_primary_image_asset_id",
  "source_image_set_fingerprint",
  "region_count",
  "total_vertex_count",
  "geometry_fingerprint",
  "stale",
  "stale_reasons",
  "is_current",
  "latest_review",
  "created_at",
] satisfies ReadonlyArray<keyof RegionSetHistoryItem>);

const regionKeys = Object.freeze([
  "id",
  "stable_region_key",
  "kind",
  "label",
  "normalized_label",
  "z_index",
  "opacity_ppm",
  "notes",
  "vertex_count",
  "area_twice_ppm_squared",
  "bbox_min_x_ppm",
  "bbox_min_y_ppm",
  "bbox_max_x_ppm",
  "bbox_max_y_ppm",
  "vertices",
] satisfies ReadonlyArray<keyof Region>);

const regionSetKeys = Object.freeze([
  ...historyKeys,
  "source_image_width",
  "source_image_height",
  "source_content_url",
  "supersedes_region_set_id",
  "based_on_region_set_id",
  "overlap_warnings",
  "regions",
] satisfies ReadonlyArray<keyof RegionSet>);

const workbenchKeys = Object.freeze([
  "paint_project_id",
  "image_set_status",
  "current_image_set_fingerprint",
  "source_primary_image_asset_id",
  "source_image_width",
  "source_image_height",
  "source_content_url",
  "can_create_draft",
  "current_region_set",
  "history",
] satisfies ReadonlyArray<keyof RegionWorkbench>);

const errorEnvelopeKeys = Object.freeze([
  "error_code",
  "category",
  "message",
  "retryable",
  "request_id",
  "current_state",
  "allowed_actions",
  "safe_details",
]);

function isPlainObject(value: unknown): value is Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    return false;
  }
  const prototype = Object.getPrototypeOf(value) as unknown;
  return prototype === Object.prototype || prototype === null;
}

function hasExactKeys(
  value: Record<string, unknown>,
  expected: readonly string[],
): boolean {
  const actual = Object.keys(value);
  return (
    actual.length === expected.length &&
    expected.every((key) => Object.prototype.hasOwnProperty.call(value, key))
  );
}

function isEnum<T extends string>(
  value: unknown,
  choices: readonly T[],
): value is T {
  return typeof value === "string" && choices.includes(value as T);
}

function isUuid(value: unknown): value is string {
  return typeof value === "string" && uuidPattern.test(value);
}

function isSha256(value: unknown): value is string {
  return typeof value === "string" && sha256Pattern.test(value);
}

function isTimestamp(value: unknown): value is string {
  return (
    typeof value === "string" &&
    timezonePattern.test(value) &&
    Number.isFinite(Date.parse(value))
  );
}

function isInteger(
  value: unknown,
  minimum: number,
  maximum = Number.MAX_SAFE_INTEGER,
): value is number {
  return (
    typeof value === "number" &&
    Number.isSafeInteger(value) &&
    value >= minimum &&
    value <= maximum
  );
}

function isNullableUuid(value: unknown): value is string | null {
  return value === null || isUuid(value);
}

function isNullableText(
  value: unknown,
  minimum: number,
  maximum: number,
): value is string | null {
  return (
    value === null ||
    (typeof value === "string" &&
      value.length >= minimum &&
      value.length <= maximum)
  );
}

function isReview(value: unknown): value is RegionSetReview {
  return (
    isPlainObject(value) &&
    hasExactKeys(value, reviewKeys) &&
    isUuid(value.id) &&
    isUuid(value.paint_project_id) &&
    isUuid(value.region_set_id) &&
    isInteger(value.version, 1) &&
    isEnum(value.verdict, regionReviewVerdicts) &&
    isNullableText(value.reason, 1, 1000) &&
    (value.verdict !== "changes_requested" || value.reason !== null) &&
    value.actor_type === "user" &&
    typeof value.actor_id === "string" &&
    value.actor_id.length >= 1 &&
    value.actor_id.length <= 128 &&
    typeof value.actor_display_name_snapshot === "string" &&
    value.actor_display_name_snapshot.length >= 1 &&
    value.actor_display_name_snapshot.length <= 200 &&
    isTimestamp(value.created_at)
  );
}

function isHistoryItem(value: unknown): value is RegionSetHistoryItem {
  return (
    isPlainObject(value) &&
    hasExactKeys(value, historyKeys) &&
    isUuid(value.id) &&
    isUuid(value.paint_project_id) &&
    isInteger(value.version, 1) &&
    isEnum(value.lifecycle, regionLifecycles) &&
    isEnum(value.effective_lifecycle, regionLifecycles) &&
    isUuid(value.source_primary_image_asset_id) &&
    isSha256(value.source_image_set_fingerprint) &&
    isInteger(value.region_count, 0, 128) &&
    isInteger(value.total_vertex_count, 0, 8192) &&
    isSha256(value.geometry_fingerprint) &&
    typeof value.stale === "boolean" &&
    Array.isArray(value.stale_reasons) &&
    value.stale_reasons.every((reason) => typeof reason === "string") &&
    typeof value.is_current === "boolean" &&
    (value.latest_review === null || isReview(value.latest_review)) &&
    isTimestamp(value.created_at)
  );
}

function isVertex(value: unknown): value is RegionVertex {
  return (
    isPlainObject(value) &&
    hasExactKeys(value, ["sequence", "x_ppm", "y_ppm"]) &&
    isInteger(value.sequence, 0, 255) &&
    isInteger(value.x_ppm, 0, 1_000_000) &&
    isInteger(value.y_ppm, 0, 1_000_000)
  );
}

function isRegion(value: unknown): value is Region {
  return (
    isPlainObject(value) &&
    hasExactKeys(value, regionKeys) &&
    isUuid(value.id) &&
    isUuid(value.stable_region_key) &&
    isEnum(value.kind, regionKinds) &&
    typeof value.label === "string" &&
    value.label.length >= 1 &&
    value.label.length <= 80 &&
    typeof value.normalized_label === "string" &&
    value.normalized_label.length >= 1 &&
    value.normalized_label.length <= 80 &&
    isInteger(value.z_index, 0, 127) &&
    isInteger(value.opacity_ppm, 100_000, 1_000_000) &&
    isNullableText(value.notes, 1, 1000) &&
    isInteger(value.vertex_count, 3, 256) &&
    isInteger(value.area_twice_ppm_squared, 1) &&
    isInteger(value.bbox_min_x_ppm, 0, 1_000_000) &&
    isInteger(value.bbox_min_y_ppm, 0, 1_000_000) &&
    isInteger(value.bbox_max_x_ppm, 0, 1_000_000) &&
    isInteger(value.bbox_max_y_ppm, 0, 1_000_000) &&
    Array.isArray(value.vertices) &&
    value.vertices.length === value.vertex_count &&
    value.vertices.every(
      (vertex, index) => isVertex(vertex) && vertex.sequence === index,
    )
  );
}

export function isRegionSet(value: unknown): value is RegionSet {
  if (!isPlainObject(value) || !hasExactKeys(value, regionSetKeys)) {
    return false;
  }
  const historyView = Object.fromEntries(
    historyKeys.map((key) => [key, value[key]]),
  );
  return (
    isHistoryItem(historyView) &&
    isInteger(value.source_image_width, 1, 8192) &&
    isInteger(value.source_image_height, 1, 8192) &&
    typeof value.source_content_url === "string" &&
    value.source_content_url ===
      `/api/v1/paint-projects/${value.paint_project_id}/images/${value.source_primary_image_asset_id}/content` &&
    isNullableUuid(value.supersedes_region_set_id) &&
    isNullableUuid(value.based_on_region_set_id) &&
    Array.isArray(value.overlap_warnings) &&
    value.overlap_warnings.every((warning) => typeof warning === "string") &&
    Array.isArray(value.regions) &&
    value.regions.length === value.region_count &&
    value.regions.every(isRegion) &&
    value.regions.reduce((count, region) => count + region.vertex_count, 0) ===
      value.total_vertex_count
  );
}

export function isRegionWorkbench(value: unknown): value is RegionWorkbench {
  return (
    isPlainObject(value) &&
    hasExactKeys(value, workbenchKeys) &&
    isUuid(value.paint_project_id) &&
    isEnum(value.image_set_status, [
      "incomplete",
      "ready",
      "stale",
      "not_ready",
    ] as const) &&
    isSha256(value.current_image_set_fingerprint) &&
    isNullableUuid(value.source_primary_image_asset_id) &&
    (value.source_image_width === null ||
      isInteger(value.source_image_width, 1, 8192)) &&
    (value.source_image_height === null ||
      isInteger(value.source_image_height, 1, 8192)) &&
    (value.source_content_url === null ||
      typeof value.source_content_url === "string") &&
    typeof value.can_create_draft === "boolean" &&
    (value.current_region_set === null || isRegionSet(value.current_region_set)) &&
    Array.isArray(value.history) &&
    value.history.every(isHistoryItem)
  );
}

function isErrorEnvelope(value: unknown): value is {
  error_code: string;
  retryable: boolean;
} {
  return (
    isPlainObject(value) &&
    hasExactKeys(value, errorEnvelopeKeys) &&
    typeof value.error_code === "string" &&
    typeof value.category === "string" &&
    typeof value.message === "string" &&
    typeof value.retryable === "boolean" &&
    isUuid(value.request_id) &&
    (value.current_state === null || typeof value.current_state === "string") &&
    Array.isArray(value.allowed_actions) &&
    value.allowed_actions.every((item) => typeof item === "string") &&
    isPlainObject(value.safe_details)
  );
}

async function readJson(response: Response): Promise<unknown> {
  try {
    return JSON.parse(await response.text()) as unknown;
  } catch {
    throw new RegionSetApiError(
      "invalid_response",
      "The region service returned an unreadable response.",
      { status: response.status },
    );
  }
}

function errorFromResponse(
  response: Response,
  envelope: { error_code: string; retryable: boolean },
): RegionSetApiError {
  const options = {
    errorCode: envelope.error_code,
    retryable: envelope.retryable,
    status: response.status,
  };
  if (response.status === 404) {
    return new RegionSetApiError(
      "not_found",
      "The project or region snapshot is not available to this operator.",
      options,
    );
  }
  if (response.status === 409) {
    return new RegionSetApiError(
      "conflict",
      "The image set, region snapshot, or protected command changed.",
      options,
    );
  }
  if (response.status === 403 || response.status === 422) {
    return new RegionSetApiError(
      "validation",
      "The human annotation command does not meet the current contract.",
      options,
    );
  }
  return new RegionSetApiError(
    "internal",
    "The region service could not complete this request.",
    options,
  );
}

async function requestJson<T>(
  input: RequestInfo | URL,
  init: RequestInit,
  expectedStatus: number,
  validator: (value: unknown) => value is T,
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(input, init);
  } catch {
    if (init.signal?.aborted) {
      throw new RegionSetApiError("aborted", "The region request was cancelled.");
    }
    throw new RegionSetApiError(
      "network",
      "The PaintPilot region API could not be reached.",
      { retryable: true },
    );
  }
  if (response.status === 502 || response.status === 504) {
    throw new RegionSetApiError(
      "network",
      "The PaintPilot region API could not be reached through the local proxy.",
      { retryable: true, status: response.status },
    );
  }
  const payload = await readJson(response);
  if (response.status === expectedStatus) {
    if (!validator(payload)) {
      throw new RegionSetApiError(
        "invalid_response",
        "The region service returned an unexpected response.",
        { status: response.status },
      );
    }
    return payload;
  }
  if (!isErrorEnvelope(payload)) {
    throw new RegionSetApiError(
      "invalid_response",
      "The region service returned an unreadable response.",
      { status: response.status },
    );
  }
  throw errorFromResponse(response, payload);
}

function assertUuid(value: string, message: string): void {
  if (!isUuid(value)) {
    throw new RegionSetApiError("validation", message);
  }
}

export function createRegionIdempotencyKey(): string {
  const key = globalThis.crypto.randomUUID();
  assertUuid(key, "A protected region command could not be started.");
  return key;
}

export async function getRegionWorkbench(
  projectId: string,
  signal?: AbortSignal,
): Promise<RegionWorkbench> {
  assertUuid(projectId, "The project address is invalid.");
  return requestJson(
    `/api/v1/paint-projects/${encodeURIComponent(projectId)}/region-sets/workbench`,
    {
      method: "GET",
      headers: { Accept: "application/json" },
      signal,
    },
    200,
    isRegionWorkbench,
  );
}

export async function getRegionSet(
  projectId: string,
  regionSetId: string,
  signal?: AbortSignal,
): Promise<RegionSet> {
  assertUuid(projectId, "The project address is invalid.");
  assertUuid(regionSetId, "The region snapshot address is invalid.");
  return requestJson(
    `/api/v1/paint-projects/${encodeURIComponent(projectId)}/region-sets/${encodeURIComponent(regionSetId)}`,
    {
      method: "GET",
      headers: { Accept: "application/json" },
      signal,
    },
    200,
    isRegionSet,
  );
}

export async function saveRegionSet(
  projectId: string,
  input: SaveRegionSetInput,
  idempotencyKey: string,
  signal?: AbortSignal,
): Promise<RegionSet> {
  assertUuid(projectId, "The project address is invalid.");
  assertUuid(idempotencyKey, "A protected save could not be started.");
  if (
    (input.base_region_set_id === null) !== (input.base_version === null) ||
    (input.base_region_set_id !== null && !isUuid(input.base_region_set_id))
  ) {
    throw new RegionSetApiError("validation", "The draft base is invalid.");
  }
  return requestJson(
    `/api/v1/paint-projects/${encodeURIComponent(projectId)}/region-sets`,
    {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "Idempotency-Key": idempotencyKey,
      },
      body: JSON.stringify(input),
      signal,
    },
    201,
    isRegionSet,
  );
}

export async function submitRegionSet(
  projectId: string,
  regionSetId: string,
  idempotencyKey: string,
  signal?: AbortSignal,
): Promise<RegionSet> {
  assertUuid(projectId, "The project address is invalid.");
  assertUuid(regionSetId, "The draft address is invalid.");
  assertUuid(idempotencyKey, "A protected submit could not be started.");
  return requestJson(
    `/api/v1/paint-projects/${encodeURIComponent(projectId)}/region-sets/${encodeURIComponent(regionSetId)}/submit`,
    {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "Idempotency-Key": idempotencyKey,
      },
      body: "{}",
      signal,
    },
    201,
    isRegionSet,
  );
}

export async function forkRegionSetDraft(
  projectId: string,
  sourceRegionSetId: string,
  input: ForkRegionSetDraftInput,
  idempotencyKey: string,
  signal?: AbortSignal,
): Promise<RegionSet> {
  assertUuid(projectId, "The project address is invalid.");
  assertUuid(sourceRegionSetId, "The historical snapshot address is invalid.");
  assertUuid(
    input.expected_current_region_set_id,
    "The expected current snapshot address is invalid.",
  );
  if (!isInteger(input.expected_current_version, 1)) {
    throw new RegionSetApiError(
      "validation",
      "The expected current snapshot version is invalid.",
    );
  }
  assertUuid(idempotencyKey, "A protected historical fork could not be started.");
  return requestJson(
    `/api/v1/paint-projects/${encodeURIComponent(projectId)}/region-sets/${encodeURIComponent(sourceRegionSetId)}/drafts`,
    {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "Idempotency-Key": idempotencyKey,
      },
      body: JSON.stringify(input),
      signal,
    },
    201,
    isRegionSet,
  );
}

export async function createRegionSetReview(
  projectId: string,
  regionSetId: string,
  input: CreateRegionSetReviewInput,
  idempotencyKey: string,
  signal?: AbortSignal,
): Promise<RegionSetReview> {
  assertUuid(projectId, "The project address is invalid.");
  assertUuid(regionSetId, "The submitted snapshot address is invalid.");
  assertUuid(idempotencyKey, "A protected review could not be started.");
  const reason = input.reason === null ? null : input.reason.trim();
  if (
    (input.verdict === "changes_requested" && !reason) ||
    (reason !== null && reason.length > 1000)
  ) {
    throw new RegionSetApiError("validation", "The review reason is invalid.");
  }
  return requestJson(
    `/api/v1/paint-projects/${encodeURIComponent(projectId)}/region-sets/${encodeURIComponent(regionSetId)}/reviews`,
    {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "Idempotency-Key": idempotencyKey,
      },
      body: JSON.stringify({ verdict: input.verdict, reason }),
      signal,
    },
    201,
    isReview,
  );
}
