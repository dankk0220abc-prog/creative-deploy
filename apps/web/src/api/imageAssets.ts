const uuidPattern =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const sha256Pattern = /^[0-9a-f]{64}$/;
const timezonePattern = /(Z|[+-]\d{2}:\d{2})$/;

export const imageRoles = ["primary_mvp_input"] as const;
export const imageSourceTypes = [
  "user_provided",
  "user_photographed",
  "user_provided_other",
] as const;
export const imageIntendedUsages = [
  "private_project",
  "portfolio_demo",
  "public_repository",
] as const;

export type ImageRole = (typeof imageRoles)[number];
export type ImageSourceType = (typeof imageSourceTypes)[number];
export type ImageIntendedUsage = (typeof imageIntendedUsages)[number];

export interface ImageAsset {
  id: string;
  paint_project_id: string;
  role: ImageRole;
  version: number;
  supersedes_image_asset_id: string | null;
  is_current: boolean;
  lifecycle_status: "current" | "superseded";
  original_filename: string;
  declared_content_type: "image/jpeg" | "image/png" | "image/webp";
  detected_format: "jpeg" | "png" | "webp";
  byte_size: number;
  width: number;
  height: number;
  pixel_count: number;
  color_mode: string;
  has_alpha: boolean;
  exif_orientation: number | null;
  sha256: string;
  upload_validation_result: "accepted";
  upload_validation_details: Record<string, unknown>;
  source_type: ImageSourceType;
  rights_attestation_status: "pending" | "confirmed" | "rejected";
  rights_attestation_version: number;
  intended_usage: ImageIntendedUsage[];
  rights_attested_at: string | null;
  created_at: string;
  content_url: string;
}

export interface ImageAssetList {
  items: ImageAsset[];
}

export interface UploadImageInput {
  file: File;
  role: ImageRole;
  sourceType: ImageSourceType;
  intendedUsage: ImageIntendedUsage[];
}

export type ImageAssetApiErrorKind =
  | "aborted"
  | "conflict"
  | "internal"
  | "invalid_response"
  | "network"
  | "not_found"
  | "storage"
  | "validation";

export class ImageAssetApiError extends Error {
  readonly errorCode: string | null;
  readonly kind: ImageAssetApiErrorKind;
  readonly retryable: boolean;
  readonly status: number | null;

  constructor(
    kind: ImageAssetApiErrorKind,
    message: string,
    options: {
      errorCode?: string;
      retryable?: boolean;
      status?: number;
    } = {},
  ) {
    super(message);
    this.name = "ImageAssetApiError";
    this.kind = kind;
    this.errorCode = options.errorCode ?? null;
    this.retryable = options.retryable ?? false;
    this.status = options.status ?? null;
  }
}

const imageAssetKeys = Object.freeze([
  "id",
  "paint_project_id",
  "role",
  "version",
  "supersedes_image_asset_id",
  "is_current",
  "lifecycle_status",
  "original_filename",
  "declared_content_type",
  "detected_format",
  "byte_size",
  "width",
  "height",
  "pixel_count",
  "color_mode",
  "has_alpha",
  "exif_orientation",
  "sha256",
  "upload_validation_result",
  "upload_validation_details",
  "source_type",
  "rights_attestation_status",
  "rights_attestation_version",
  "intended_usage",
  "rights_attested_at",
  "created_at",
  "content_url",
] satisfies ReadonlyArray<keyof ImageAsset>);

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

function isUuid(value: unknown): value is string {
  return typeof value === "string" && uuidPattern.test(value);
}

function isTimestamp(value: unknown): value is string {
  return (
    typeof value === "string" &&
    timezonePattern.test(value) &&
    Number.isFinite(Date.parse(value))
  );
}

function isInteger(value: unknown, minimum: number): value is number {
  return (
    typeof value === "number" &&
    Number.isSafeInteger(value) &&
    value >= minimum
  );
}

function isEnum<T extends string>(
  value: unknown,
  choices: readonly T[],
): value is T {
  return typeof value === "string" && choices.includes(value as T);
}

function isImageAsset(value: unknown): value is ImageAsset {
  if (!isPlainObject(value) || !hasExactKeys(value, imageAssetKeys)) {
    return false;
  }
  const intendedUsage = value.intended_usage;
  return (
    isUuid(value.id) &&
    isUuid(value.paint_project_id) &&
    value.role === "primary_mvp_input" &&
    isInteger(value.version, 1) &&
    (value.supersedes_image_asset_id === null ||
      isUuid(value.supersedes_image_asset_id)) &&
    typeof value.is_current === "boolean" &&
    (value.lifecycle_status === "current" ||
      value.lifecycle_status === "superseded") &&
    value.is_current === (value.lifecycle_status === "current") &&
    typeof value.original_filename === "string" &&
    value.original_filename.length >= 1 &&
    value.original_filename.length <= 255 &&
    isEnum(value.declared_content_type, [
      "image/jpeg",
      "image/png",
      "image/webp",
    ] as const) &&
    isEnum(value.detected_format, ["jpeg", "png", "webp"] as const) &&
    isInteger(value.byte_size, 1) &&
    value.byte_size <= 20 * 1024 * 1024 &&
    isInteger(value.width, 1) &&
    isInteger(value.height, 1) &&
    isInteger(value.pixel_count, 1) &&
    value.pixel_count === value.width * value.height &&
    typeof value.color_mode === "string" &&
    value.color_mode.length >= 1 &&
    value.color_mode.length <= 32 &&
    typeof value.has_alpha === "boolean" &&
    (value.exif_orientation === null ||
      (isInteger(value.exif_orientation, 1) && value.exif_orientation <= 8)) &&
    typeof value.sha256 === "string" &&
    sha256Pattern.test(value.sha256) &&
    value.upload_validation_result === "accepted" &&
    isPlainObject(value.upload_validation_details) &&
    isEnum(value.source_type, imageSourceTypes) &&
    isEnum(value.rights_attestation_status, [
      "pending",
      "confirmed",
      "rejected",
    ] as const) &&
    isInteger(value.rights_attestation_version, 1) &&
    Array.isArray(intendedUsage) &&
    intendedUsage.length >= 1 &&
    intendedUsage.every((usage) => isEnum(usage, imageIntendedUsages)) &&
    new Set(intendedUsage).size === intendedUsage.length &&
    (value.rights_attested_at === null || isTimestamp(value.rights_attested_at)) &&
    isTimestamp(value.created_at) &&
    typeof value.content_url === "string" &&
    value.content_url ===
      `/api/v1/paint-projects/${value.paint_project_id}/images/${value.id}/content`
  );
}

function isImageAssetList(value: unknown): value is ImageAssetList {
  return (
    isPlainObject(value) &&
    hasExactKeys(value, ["items"]) &&
    Array.isArray(value.items) &&
    value.items.every(isImageAsset)
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
  let text: string;
  try {
    text = await response.text();
  } catch {
    throw new ImageAssetApiError(
      "invalid_response",
      "The image service returned an unreadable response.",
      { status: response.status },
    );
  }
  try {
    return JSON.parse(text) as unknown;
  } catch {
    throw new ImageAssetApiError(
      "invalid_response",
      "The image service returned an unreadable response.",
      { status: response.status },
    );
  }
}

function errorFromResponse(
  response: Response,
  envelope: { error_code: string; retryable: boolean },
): ImageAssetApiError {
  const options = {
    errorCode: envelope.error_code,
    retryable: envelope.retryable,
    status: response.status,
  };
  if (response.status === 404) {
    return new ImageAssetApiError(
      "not_found",
      "The project or image is not available to this operator.",
      options,
    );
  }
  if (response.status === 409) {
    return new ImageAssetApiError(
      "conflict",
      "The protected upload conflicts with the saved command or project state.",
      options,
    );
  }
  if (response.status === 413 || response.status === 416 || response.status === 422) {
    return new ImageAssetApiError(
      "validation",
      "The image or rights declaration does not meet the upload contract.",
      options,
    );
  }
  if (response.status === 503) {
    return new ImageAssetApiError(
      "storage",
      "Image data is temporarily unavailable.",
      options,
    );
  }
  return new ImageAssetApiError(
    "internal",
    "The image service could not complete this request.",
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
      throw new ImageAssetApiError("aborted", "The image request was cancelled.");
    }
    throw new ImageAssetApiError(
      "network",
      "The PaintPilot image API could not be reached.",
      { retryable: true },
    );
  }
  if (response.status === 502 || response.status === 504) {
    throw new ImageAssetApiError(
      "network",
      "The PaintPilot image API could not be reached through the local proxy.",
      { retryable: true, status: response.status },
    );
  }
  const payload = await readJson(response);
  if (response.status === expectedStatus) {
    if (!validator(payload)) {
      throw new ImageAssetApiError(
        "invalid_response",
        "The image service returned an unreadable response.",
        { status: response.status },
      );
    }
    return payload;
  }
  if (!isErrorEnvelope(payload)) {
    throw new ImageAssetApiError(
      "invalid_response",
      "The image service returned an unreadable response.",
      { status: response.status },
    );
  }
  throw errorFromResponse(response, payload);
}

export function createImageIdempotencyKey(): string {
  const key = globalThis.crypto.randomUUID();
  if (!isUuid(key)) {
    throw new ImageAssetApiError(
      "internal",
      "A protected upload attempt could not be started.",
    );
  }
  return key;
}

export async function listImageAssets(
  projectId: string,
  signal?: AbortSignal,
): Promise<ImageAssetList> {
  if (!isUuid(projectId)) {
    throw new ImageAssetApiError("validation", "The project address is invalid.");
  }
  return requestJson(
    `/api/v1/paint-projects/${encodeURIComponent(projectId)}/images`,
    {
      method: "GET",
      headers: { Accept: "application/json" },
      signal,
    },
    200,
    isImageAssetList,
  );
}

export async function uploadImageAsset(
  projectId: string,
  input: UploadImageInput,
  idempotencyKey: string,
  signal?: AbortSignal,
): Promise<ImageAsset> {
  if (!isUuid(projectId) || !isUuid(idempotencyKey)) {
    throw new ImageAssetApiError(
      "validation",
      "A protected upload attempt could not be started.",
    );
  }
  const body = new FormData();
  body.append("file", input.file);
  body.append("role", input.role);
  body.append("source_type", input.sourceType);
  for (const usage of input.intendedUsage) {
    body.append("intended_usage", usage);
  }
  body.append("rights_attestation_confirmed", "true");
  body.append("rights_attestation_version", "1");

  return requestJson(
    `/api/v1/paint-projects/${encodeURIComponent(projectId)}/images`,
    {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Idempotency-Key": idempotencyKey,
      },
      body,
      signal,
    },
    201,
    isImageAsset,
  );
}
