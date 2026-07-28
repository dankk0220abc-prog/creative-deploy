export const PAINT_PROJECTS_PATH = "/api/v1/paint-projects";

export const workflowStatuses = [
  "DRAFT",
  "IMAGE_UPLOADED",
  "IMAGE_REVIEW_REQUIRED",
  "IMAGE_VALIDATION_FAILED",
  "IMAGE_VALIDATED",
  "REGION_ANALYSIS_RUNNING",
  "REGION_REVIEW_REQUIRED",
  "REGIONS_CONFIRMED",
  "PLAN_GENERATION_RUNNING",
  "PLAN_REVIEW_REQUIRED",
  "PLAN_APPROVED",
  "COMPLETED",
  "BLOCKED_LOW_CONFIDENCE",
  "FAILED_RETRYABLE",
  "FAILED_FINAL",
  "ABANDONED",
] as const;

export type WorkflowStatus = (typeof workflowStatuses)[number];

export interface PaintProject {
  id: string;
  owner_principal_id: string;
  title: string;
  description: string | null;
  requested_target_style: "cel_shading";
  planning_mode: "planning_only_demo";
  status: WorkflowStatus;
  created_at: string;
  updated_at: string;
}

export interface PaintProjectList {
  items: PaintProject[];
  total: number;
  limit: number;
  offset: number;
}

export interface CreatePaintProjectInput {
  title: string;
  description: string | null;
}

export type PaintProjectApiErrorKind =
  | "aborted"
  | "conflict"
  | "internal"
  | "invalid_response"
  | "network"
  | "not_found"
  | "server"
  | "unavailable"
  | "validation";

interface PaintProjectApiErrorOptions {
  errorCode?: string;
  fieldNames?: Array<"description" | "title">;
  retryable?: boolean;
  status?: number;
}

export class PaintProjectApiError extends Error {
  readonly errorCode: string | null;
  readonly fieldNames: Array<"description" | "title">;
  readonly kind: PaintProjectApiErrorKind;
  readonly retryable: boolean;
  readonly status: number | null;

  constructor(
    kind: PaintProjectApiErrorKind,
    message: string,
    options: PaintProjectApiErrorOptions = {},
  ) {
    super(message);
    this.name = "PaintProjectApiError";
    this.kind = kind;
    this.status = options.status ?? null;
    this.errorCode = options.errorCode ?? null;
    this.retryable = options.retryable ?? false;
    this.fieldNames = options.fieldNames ?? [];
  }
}

const errorCategories = [
  "VALIDATION_ERROR",
  "NOT_FOUND",
  "IDEMPOTENCY_KEY_REUSED",
  "INVALID_STATE_TRANSITION",
  "CONFLICT",
  "DATABASE_UNAVAILABLE",
  "STORAGE_ERROR",
  "PROVIDER_TIMEOUT",
  "PROVIDER_RATE_LIMIT",
  "PROVIDER_RESPONSE_INVALID",
  "RETRIEVAL_ERROR",
  "SCHEMA_VALIDATION_ERROR",
  "INTERNAL_ERROR",
] as const;

type ErrorCategory = (typeof errorCategories)[number];

interface ErrorEnvelope {
  allowed_actions: string[];
  category: ErrorCategory;
  current_state: string | null;
  error_code: string;
  message: string;
  request_id: string;
  retryable: boolean;
  safe_details: Record<string, unknown>;
}

const uuidPattern =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const timezonePattern = /(Z|[+-]\d{2}:\d{2})$/;
const workflowStatusSet = new Set<string>(workflowStatuses);
const errorCategorySet = new Set<string>(errorCategories);
const paintProjectKeys = Object.freeze([
  "id",
  "owner_principal_id",
  "title",
  "description",
  "requested_target_style",
  "planning_mode",
  "status",
  "created_at",
  "updated_at",
] satisfies ReadonlyArray<keyof PaintProject>);
const paintProjectListKeys = Object.freeze([
  "items",
  "total",
  "limit",
  "offset",
] satisfies ReadonlyArray<keyof PaintProjectList>);
const errorEnvelopeKeys = Object.freeze([
  "error_code",
  "category",
  "message",
  "retryable",
  "request_id",
  "current_state",
  "allowed_actions",
  "safe_details",
] satisfies ReadonlyArray<keyof ErrorEnvelope>);

function isPlainObject(value: unknown): value is Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    return false;
  }

  const prototype = Object.getPrototypeOf(value) as unknown;
  return prototype === Object.prototype || prototype === null;
}

function hasExactKeys(
  value: Record<string, unknown>,
  expectedKeys: readonly string[],
): boolean {
  const actualKeys = Object.keys(value);
  return (
    actualKeys.length === expectedKeys.length &&
    expectedKeys.every((key) => Object.prototype.hasOwnProperty.call(value, key))
  );
}

function isFiniteInteger(value: unknown): value is number {
  return typeof value === "number" && Number.isInteger(value) && Number.isFinite(value);
}

function isNormalizedString(value: unknown, min: number, max: number): value is string {
  return (
    typeof value === "string" &&
    value === value.trim() &&
    Array.from(value).length >= min &&
    Array.from(value).length <= max
  );
}

function isTimestamp(value: unknown): value is string {
  return (
    typeof value === "string" &&
    timezonePattern.test(value) &&
    Number.isFinite(Date.parse(value))
  );
}

export function isPaintProjectId(value: string | undefined): value is string {
  return value !== undefined && uuidPattern.test(value);
}

function isPaintProject(value: unknown): value is PaintProject {
  if (!isPlainObject(value) || !hasExactKeys(value, paintProjectKeys)) {
    return false;
  }

  const descriptionIsValid =
    value.description === null || isNormalizedString(value.description, 1, 500);

  return (
    typeof value.id === "string" &&
    isPaintProjectId(value.id) &&
    isNormalizedString(value.owner_principal_id, 1, 128) &&
    isNormalizedString(value.title, 1, 80) &&
    descriptionIsValid &&
    value.requested_target_style === "cel_shading" &&
    value.planning_mode === "planning_only_demo" &&
    typeof value.status === "string" &&
    workflowStatusSet.has(value.status) &&
    isTimestamp(value.created_at) &&
    isTimestamp(value.updated_at) &&
    Date.parse(value.updated_at) >= Date.parse(value.created_at)
  );
}

function isPaintProjectList(value: unknown): value is PaintProjectList {
  if (
    !isPlainObject(value) ||
    !hasExactKeys(value, paintProjectListKeys) ||
    !Array.isArray(value.items)
  ) {
    return false;
  }

  return (
    value.items.every(isPaintProject) &&
    isFiniteInteger(value.total) &&
    value.total >= 0 &&
    isFiniteInteger(value.limit) &&
    value.limit >= 1 &&
    value.limit <= 100 &&
    isFiniteInteger(value.offset) &&
    value.offset >= 0
  );
}

function isErrorEnvelope(value: unknown): value is ErrorEnvelope {
  if (!isPlainObject(value) || !hasExactKeys(value, errorEnvelopeKeys)) {
    return false;
  }

  return (
    typeof value.error_code === "string" &&
    typeof value.category === "string" &&
    errorCategorySet.has(value.category) &&
    typeof value.message === "string" &&
    typeof value.retryable === "boolean" &&
    typeof value.request_id === "string" &&
    isPaintProjectId(value.request_id) &&
    (value.current_state === null || typeof value.current_state === "string") &&
    Array.isArray(value.allowed_actions) &&
    value.allowed_actions.every((item) => typeof item === "string") &&
    isPlainObject(value.safe_details)
  );
}

function extractFieldNames(
  safeDetails: Record<string, unknown>,
): Array<"description" | "title"> {
  if (!Array.isArray(safeDetails.fields)) {
    return [];
  }

  const names = new Set<"description" | "title">();
  for (const item of safeDetails.fields) {
    if (!isPlainObject(item) || typeof item.field !== "string") {
      continue;
    }
    const finalSegment = item.field.split(".").at(-1);
    if (finalSegment === "title" || finalSegment === "description") {
      names.add(finalSegment);
    }
  }
  return [...names];
}

function invalidResponse(status: number | null = null): PaintProjectApiError {
  return new PaintProjectApiError(
    "invalid_response",
    "The project service returned an unreadable response.",
    { status: status ?? undefined },
  );
}

async function readJson(response: Response): Promise<unknown> {
  let body: string;
  try {
    body = await response.text();
  } catch {
    throw invalidResponse(response.status);
  }

  if (body.trim().length === 0) {
    throw invalidResponse(response.status);
  }

  try {
    return JSON.parse(body) as unknown;
  } catch {
    throw invalidResponse(response.status);
  }
}

function errorFromEnvelope(response: Response, envelope: ErrorEnvelope): PaintProjectApiError {
  const options: PaintProjectApiErrorOptions = {
    errorCode: envelope.error_code,
    retryable: envelope.retryable,
    status: response.status,
  };

  switch (response.status) {
    case 404:
      return new PaintProjectApiError(
        "not_found",
        "The project was not found or is not available to this operator.",
        options,
      );
    case 409:
      return new PaintProjectApiError(
        "conflict",
        "This protected create attempt was already used with different project details.",
        options,
      );
    case 422:
      return new PaintProjectApiError(
        "validation",
        "One or more project fields need attention.",
        {
          ...options,
          fieldNames: extractFieldNames(envelope.safe_details),
        },
      );
    case 500:
      return new PaintProjectApiError(
        "internal",
        "The project service could not complete this request.",
        options,
      );
    case 503:
      return new PaintProjectApiError(
        "unavailable",
        "Project data is temporarily unavailable.",
        options,
      );
    default:
      return new PaintProjectApiError(
        "server",
        "The project service returned an unexpected status.",
        options,
      );
  }
}

async function fetchJson(
  input: RequestInfo | URL,
  init: RequestInit,
  expectedStatus: number,
  validate: (value: unknown) => boolean,
): Promise<unknown> {
  let response: Response;
  try {
    response = await fetch(input, init);
  } catch {
    if (init.signal?.aborted) {
      throw new PaintProjectApiError("aborted", "The project request was cancelled.");
    }
    throw new PaintProjectApiError(
      "network",
      "The PaintPilot API could not be reached.",
      { retryable: true },
    );
  }

  if (response.status === 502 || response.status === 504) {
    throw new PaintProjectApiError(
      "network",
      "The PaintPilot API could not be reached through the local web proxy.",
      { retryable: true, status: response.status },
    );
  }

  const payload = await readJson(response);
  if (response.status === expectedStatus) {
    if (!validate(payload)) {
      throw invalidResponse(response.status);
    }
    return payload;
  }

  if (!isErrorEnvelope(payload)) {
    throw invalidResponse(response.status);
  }
  throw errorFromEnvelope(response, payload);
}

export function normalizeCreatePaintProjectInput(
  title: string,
  description: string,
): CreatePaintProjectInput {
  const normalizedDescription = description.trim();
  return {
    title: title.trim(),
    description: normalizedDescription.length === 0 ? null : normalizedDescription,
  };
}

export function createIdempotencyKey(): string {
  const key = globalThis.crypto.randomUUID();
  if (!isPaintProjectId(key)) {
    throw new PaintProjectApiError(
      "internal",
      "A protected create attempt could not be started.",
    );
  }
  return key;
}

export async function createPaintProject(
  input: CreatePaintProjectInput,
  idempotencyKey: string,
  signal?: AbortSignal,
): Promise<PaintProject> {
  if (!isPaintProjectId(idempotencyKey)) {
    throw new PaintProjectApiError(
      "validation",
      "A protected create attempt could not be started.",
    );
  }

  return (await fetchJson(
    PAINT_PROJECTS_PATH,
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
    isPaintProject,
  )) as PaintProject;
}

export async function listPaintProjects(
  options: { limit?: number; offset?: number; signal?: AbortSignal } = {},
): Promise<PaintProjectList> {
  const limit = options.limit ?? 20;
  const offset = options.offset ?? 0;
  const query = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  });

  return (await fetchJson(
    `${PAINT_PROJECTS_PATH}?${query.toString()}`,
    {
      method: "GET",
      headers: { Accept: "application/json" },
      signal: options.signal,
    },
    200,
    isPaintProjectList,
  )) as PaintProjectList;
}

export async function getPaintProject(
  projectId: string,
  signal?: AbortSignal,
): Promise<PaintProject> {
  if (!isPaintProjectId(projectId)) {
    throw new PaintProjectApiError(
      "validation",
      "The project address is not valid.",
    );
  }

  return (await fetchJson(
    `${PAINT_PROJECTS_PATH}/${encodeURIComponent(projectId)}`,
    {
      method: "GET",
      headers: { Accept: "application/json" },
      signal,
    },
    200,
    isPaintProject,
  )) as PaintProject;
}
