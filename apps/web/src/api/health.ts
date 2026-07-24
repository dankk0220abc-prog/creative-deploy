export type ApiStatus = "ok" | "degraded";
export type DatabaseStatus = "ok" | "error";

export interface DatabaseCheck {
  status: DatabaseStatus;
  latency_ms: number | null;
  error_code: "DATABASE_UNAVAILABLE" | null;
}

export interface ReadinessResponse {
  status: ApiStatus;
  service: string;
  version: string;
  checks: {
    database: DatabaseCheck;
  };
}

export interface ReadinessResult {
  data: ReadinessResponse;
  httpStatus: 200 | 503;
}

export type HealthApiErrorKind =
  | "caller_aborted"
  | "network_or_invalid_response"
  | "timeout";

export class HealthApiError extends Error {
  readonly kind: HealthApiErrorKind;

  constructor(kind: HealthApiErrorKind, message: string) {
    super(message);
    this.name = "HealthApiError";
    this.kind = kind;
  }
}

const READINESS_PATH = "/api/v1/health/ready";
const REQUEST_TIMEOUT_MS = 5_000;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isDatabaseCheck(value: unknown): value is DatabaseCheck {
  if (!isRecord(value)) {
    return false;
  }

  const validLatency =
    value.latency_ms === null ||
    (typeof value.latency_ms === "number" &&
      Number.isFinite(value.latency_ms) &&
      value.latency_ms >= 0);
  const validErrorCode =
    value.error_code === null || value.error_code === "DATABASE_UNAVAILABLE";

  return (
    (value.status === "ok" || value.status === "error") &&
    validLatency &&
    validErrorCode
  );
}

function isReadinessResponse(value: unknown): value is ReadinessResponse {
  if (!isRecord(value) || !isRecord(value.checks)) {
    return false;
  }

  return (
    (value.status === "ok" || value.status === "degraded") &&
    typeof value.service === "string" &&
    typeof value.version === "string" &&
    isDatabaseCheck(value.checks.database)
  );
}

export async function fetchReadiness(signal?: AbortSignal): Promise<ReadinessResult> {
  const requestController = new AbortController();
  let abortSource: "caller" | "timeout" | null = null;

  const forwardAbort = () => {
    abortSource ??= "caller";
    requestController.abort();
  };
  const timeoutId = window.setTimeout(() => {
    abortSource ??= "timeout";
    requestController.abort();
  }, REQUEST_TIMEOUT_MS);

  if (signal?.aborted) {
    forwardAbort();
  } else {
    signal?.addEventListener("abort", forwardAbort, { once: true });
  }

  const throwIfAborted = () => {
    if (abortSource === "caller") {
      throw new HealthApiError("caller_aborted", "The health request was cancelled.");
    }
    if (abortSource === "timeout") {
      throw new HealthApiError("timeout", "The health request timed out.");
    }
  };

  try {
    let response: Response;
    try {
      throwIfAborted();
      response = await fetch(READINESS_PATH, {
        headers: {
          Accept: "application/json",
        },
        signal: requestController.signal,
      });
      throwIfAborted();
    } catch (error: unknown) {
      if (error instanceof HealthApiError) {
        throw error;
      }
      throwIfAborted();
      throw new HealthApiError(
        "network_or_invalid_response",
        "The API could not be reached.",
      );
    }

    if (response.status !== 200 && response.status !== 503) {
      throw new HealthApiError(
        "network_or_invalid_response",
        "The API returned an unexpected status.",
      );
    }

    let payload: unknown;
    try {
      payload = await response.json();
    } catch {
      throwIfAborted();
      throw new HealthApiError(
        "network_or_invalid_response",
        "The API returned unreadable health data.",
      );
    }

    throwIfAborted();
    if (!isReadinessResponse(payload)) {
      throw new HealthApiError(
        "network_or_invalid_response",
        "The API returned an invalid health response.",
      );
    }

    return {
      data: payload,
      httpStatus: response.status,
    };
  } finally {
    window.clearTimeout(timeoutId);
    signal?.removeEventListener("abort", forwardAbort);
  }
}
