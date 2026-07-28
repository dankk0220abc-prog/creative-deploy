import type { WorkflowStatus } from "../api/paintProjects";
import { formatProjectStatus } from "../utils/format";

type StatusTone = "attention" | "complete" | "draft" | "error" | "progress";

const statusTones: Record<WorkflowStatus, StatusTone> = {
  DRAFT: "draft",
  IMAGE_UPLOADED: "progress",
  IMAGE_REVIEW_REQUIRED: "attention",
  IMAGE_VALIDATION_FAILED: "error",
  IMAGE_VALIDATED: "progress",
  REGION_ANALYSIS_RUNNING: "progress",
  REGION_REVIEW_REQUIRED: "attention",
  REGIONS_CONFIRMED: "progress",
  PLAN_GENERATION_RUNNING: "progress",
  PLAN_REVIEW_REQUIRED: "attention",
  PLAN_APPROVED: "complete",
  COMPLETED: "complete",
  BLOCKED_LOW_CONFIDENCE: "attention",
  FAILED_RETRYABLE: "attention",
  FAILED_FINAL: "error",
  ABANDONED: "error",
};

const toneSymbols: Record<StatusTone, string> = {
  attention: "!",
  complete: "✓",
  draft: "•",
  error: "×",
  progress: "→",
};

interface ProjectStatusBadgeProps {
  status: WorkflowStatus;
}

export function ProjectStatusBadge({ status }: ProjectStatusBadgeProps) {
  const tone = statusTones[status];
  const label = formatProjectStatus(status);

  return (
    <span
      aria-label={`Workflow status: ${label}`}
      className={`project-status project-status--${tone}`}
    >
      <span aria-hidden="true" className="project-status__symbol">
        {toneSymbols[tone]}
      </span>
      {label}
    </span>
  );
}
