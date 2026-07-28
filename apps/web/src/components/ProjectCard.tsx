import { Link } from "react-router";

import type { PaintProject } from "../api/paintProjects";
import {
  formatProjectTimestamp,
  summarizeDescription,
} from "../utils/format";
import { ProjectStatusBadge } from "./ProjectStatusBadge";

interface ProjectCardProps {
  project: PaintProject;
}

export function ProjectCard({ project }: ProjectCardProps) {
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
          <span className="project-card__visual-label">Image not added</span>
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

          <p className="project-card__description">
            {summarizeDescription(project.description)}
          </p>

          <div className="project-card__status-row">
            <ProjectStatusBadge status={project.status} />
            <span className="review-gate">
              <span aria-hidden="true" />
              No active review gate
            </span>
          </div>

          <dl className="project-card__facts">
            <div>
              <dt>Style</dt>
              <dd>Cel Shading</dd>
            </div>
            <div>
              <dt>Mode</dt>
              <dd>Planning only</dd>
            </div>
            <div>
              <dt>Created</dt>
              <dd>
                <time dateTime={project.created_at}>
                  {formatProjectTimestamp(project.created_at)}
                </time>
              </dd>
            </div>
            <div>
              <dt>Updated</dt>
              <dd>
                <time dateTime={project.updated_at}>
                  {formatProjectTimestamp(project.updated_at)}
                </time>
              </dd>
            </div>
          </dl>
        </div>
      </Link>
    </article>
  );
}
