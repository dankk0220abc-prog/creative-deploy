import { Link } from "react-router";

import type { PaintProject } from "../api/paintProjects";
import {
  formatProjectAccessibleTimestamp,
  formatProjectRelativeTime,
  toProjectISOString,
} from "../utils/format";
import { ProjectStatusBadge } from "./ProjectStatusBadge";

interface ProjectCardProps {
  project: PaintProject;
}

function imageSlotLabel(project: PaintProject): string {
  return project.current_image_asset_id === null
    ? "Primary image not added"
    : "Primary image stored";
}

function reviewGateLabel(project: PaintProject): string {
  if (project.status === "IMAGE_REVIEW_REQUIRED") {
    return "Image review required";
  }
  if (project.status === "IMAGE_VALIDATION_FAILED") {
    return "Image validation failed";
  }
  return "No active review gate";
}

export function ProjectCard({ project }: ProjectCardProps) {
  const exactUpdatedTime = formatProjectAccessibleTimestamp(project.updated_at);
  const updatedDateTime = toProjectISOString(project.updated_at) ?? project.updated_at;

  return (
    <article className="project-card">
      <Link
        aria-label={`Open project ${project.title}`}
        className="project-card__link"
        to={`/paintpilot/projects/${project.id}`}
      >
        <div className="project-card__visual" aria-hidden="true">
          <span className="project-card__orbit project-card__orbit--one" />
          <span className="project-card__orbit project-card__orbit--two" />
          <span className="project-card__monogram">
            {Array.from(project.title)[0]?.toLocaleUpperCase() ?? "P"}
          </span>
          <span className="project-card__visual-label">
            {imageSlotLabel(project)}
          </span>
        </div>

        <div className="project-card__body">
          <div className="project-card__heading">
            <div>
              <p className="project-card__kicker">Paint project</p>
              <h3>{project.title}</h3>
            </div>
            <span aria-hidden="true" className="project-card__arrow">
              ↗
            </span>
          </div>

          <div className="project-card__status-row">
            <ProjectStatusBadge status={project.status} />
            <span className="review-gate">
              <span aria-hidden="true" />
              {reviewGateLabel(project)}
            </span>
          </div>

          <dl className="project-card__facts">
            <div>
              <dt>Updated</dt>
              <dd>
                <time
                  aria-label={`Updated ${exactUpdatedTime}`}
                  dateTime={updatedDateTime}
                >
                  {formatProjectRelativeTime(project.updated_at)}
                </time>
              </dd>
            </div>
          </dl>
        </div>
      </Link>
    </article>
  );
}
