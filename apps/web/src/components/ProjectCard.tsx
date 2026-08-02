import { Link } from "react-router";

import type { PaintProject } from "../api/paintProjects";
import { useAppTranslation } from "../i18n";
import {
  formatProjectAccessibleTimestamp,
  formatProjectRelativeTime,
  toProjectISOString,
} from "../utils/format";
import { ProjectStatusBadge } from "./ProjectStatusBadge";

interface ProjectCardProps {
  project: PaintProject;
}

function imageSlotKey(project: PaintProject): string {
  return project.current_image_asset_id === null
    ? "projectCard.noPrimary"
    : "projectCard.primaryStored";
}

function reviewGateKey(project: PaintProject): string {
  if (project.status === "IMAGE_REVIEW_REQUIRED") {
    return "projectCard.imageReviewRequired";
  }
  if (project.status === "IMAGE_VALIDATION_FAILED") {
    return "projectCard.imageValidationFailed";
  }
  return "projectCard.noActiveGate";
}

export function ProjectCard({ project }: ProjectCardProps) {
  const { t } = useAppTranslation();
  const exactUpdatedTime = formatProjectAccessibleTimestamp(project.updated_at);
  const updatedDateTime = toProjectISOString(project.updated_at) ?? project.updated_at;

  return (
    <article className="project-card">
      <Link
        aria-label={t("projectCard.open", { title: project.title })}
        className="project-card__link"
        to={`/paintpilot/projects/${project.id}`}
      >
        <div className="project-card__visual" aria-hidden="true">
          <span className="project-card__monogram">
            {Array.from(project.title)[0]?.toLocaleUpperCase() ?? "P"}
          </span>
          <span className="project-card__visual-copy">
            <span>{t("projectCard.material")}</span>
            <strong>{t(imageSlotKey(project))}</strong>
          </span>
        </div>

        <div className="project-card__body">
          <div className="project-card__heading">
            <div>
              <p className="project-card__context">{t("projectCard.kicker")}</p>
              <h3>{project.title}</h3>
            </div>
          </div>

          <div className="project-card__status-row">
            <ProjectStatusBadge status={project.status} />
            <span className="review-gate">
              <span aria-hidden="true" />
              {t(reviewGateKey(project))}
            </span>
          </div>

          <dl className="project-card__facts">
            <div>
              <dt>{t("projectCard.updated")}</dt>
              <dd>
                <time
                  aria-label={t("projectCard.updatedAccessible", { time: exactUpdatedTime })}
                  dateTime={updatedDateTime}
                >
                  {formatProjectRelativeTime(project.updated_at)}
                </time>
              </dd>
            </div>
            <div>
              <dt>{t("projectCard.nextView")}</dt>
              <dd>{t("projectCard.openWorkspace")}</dd>
            </div>
          </dl>
        </div>
      </Link>
    </article>
  );
}
