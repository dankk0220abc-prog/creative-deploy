import type { WorkflowStatus } from "../api/paintProjects";

const statusLabels: Record<WorkflowStatus, string> = {
  DRAFT: "Draft",
  IMAGE_UPLOADED: "Image uploaded",
  IMAGE_REVIEW_REQUIRED: "Image review required",
  IMAGE_VALIDATION_FAILED: "Image validation failed",
  IMAGE_VALIDATED: "Image validated",
  REGION_ANALYSIS_RUNNING: "Region analysis running",
  REGION_REVIEW_REQUIRED: "Region review required",
  REGIONS_CONFIRMED: "Regions confirmed",
  PLAN_GENERATION_RUNNING: "Plan generation running",
  PLAN_REVIEW_REQUIRED: "Plan review required",
  PLAN_APPROVED: "Plan approved",
  COMPLETED: "Completed",
  BLOCKED_LOW_CONFIDENCE: "Blocked for review",
  FAILED_RETRYABLE: "Retry available",
  FAILED_FINAL: "Failed",
  ABANDONED: "Abandoned",
};

const UNKNOWN_UPDATE_TIME = "Unknown update time";

function parseTimestamp(value: string): number | null {
  const timestamp = Date.parse(value);
  return Number.isFinite(timestamp) ? timestamp : null;
}

export function codePointLength(value: string): number {
  return Array.from(value).length;
}

export function formatProjectStatus(status: WorkflowStatus): string {
  return statusLabels[status];
}

export function formatProjectTimestamp(value: string): string {
  const timestamp = parseTimestamp(value);
  if (timestamp === null) {
    return UNKNOWN_UPDATE_TIME;
  }

  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(timestamp);
}

export function formatProjectAccessibleTimestamp(value: string): string {
  const timestamp = parseTimestamp(value);
  if (timestamp === null) {
    return UNKNOWN_UPDATE_TIME;
  }

  return new Intl.DateTimeFormat("en-US", {
    dateStyle: "long",
    timeStyle: "long",
    timeZone: "UTC",
  }).format(timestamp);
}

export function formatProjectRelativeTime(
  value: string,
  nowMilliseconds = Date.now(),
): string {
  const timestamp = parseTimestamp(value);
  if (timestamp === null || !Number.isFinite(nowMilliseconds)) {
    return UNKNOWN_UPDATE_TIME;
  }

  const secondsFromNow = (timestamp - nowMilliseconds) / 1_000;
  const absoluteSeconds = Math.abs(secondsFromNow);

  if (absoluteSeconds < 60) {
    return secondsFromNow <= 0 ? "just now" : "in less than a minute";
  }

  let divisor: number;
  let unit: Intl.RelativeTimeFormatUnit;
  if (absoluteSeconds < 60 * 60) {
    divisor = 60;
    unit = "minute";
  } else if (absoluteSeconds < 24 * 60 * 60) {
    divisor = 60 * 60;
    unit = "hour";
  } else {
    divisor = 24 * 60 * 60;
    unit = "day";
  }

  return new Intl.RelativeTimeFormat("en", { numeric: "always" }).format(
    Math.round(secondsFromNow / divisor),
    unit,
  );
}

export function toProjectISOString(value: string): string | null {
  const timestamp = parseTimestamp(value);
  return timestamp === null ? null : new Date(timestamp).toISOString();
}

export function summarizeDescription(
  description: string | null,
  maximumCodePoints = 140,
): string {
  if (description === null) {
    return "No description provided.";
  }

  const codePoints = Array.from(description);
  if (codePoints.length <= maximumCodePoints) {
    return description;
  }
  return `${codePoints.slice(0, maximumCodePoints - 1).join("")}…`;
}
