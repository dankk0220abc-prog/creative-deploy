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

export function codePointLength(value: string): number {
  return Array.from(value).length;
}

export function formatProjectStatus(status: WorkflowStatus): string {
  return statusLabels[status];
}

export function formatProjectTimestamp(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
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
