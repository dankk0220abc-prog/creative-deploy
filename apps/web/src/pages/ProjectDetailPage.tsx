import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { Link, useLocation, useParams } from "react-router";

import {
  getPaintProject,
  isPaintProjectId,
  PaintProjectApiError,
  type PaintProject,
} from "../api/paintProjects";
import { FeedbackPanel } from "../components/FeedbackPanel";
import { ImageAssetManager } from "../components/ImageAssetManager";
import { ProjectStatusBadge } from "../components/ProjectStatusBadge";
import { formatProjectTimestamp } from "../utils/format";

type DetailState =
  | { status: "error"; error: PaintProjectApiError; projectId: string }
  | { status: "found"; project: PaintProject; projectId: string }
  | { status: "loading"; projectId: string }
  | { status: "not_found"; projectId: string };

function wasCreatedNavigation(state: unknown): boolean {
  return (
    typeof state === "object" &&
    state !== null &&
    "projectCreated" in state &&
    state.projectCreated === true
  );
}

function asApiError(error: unknown): PaintProjectApiError {
  if (error instanceof PaintProjectApiError) {
    return error;
  }
  return new PaintProjectApiError(
    "internal",
    "The project detail request could not be completed.",
  );
}

function DetailError({
  error,
  onRetry,
}: {
  error: PaintProjectApiError;
  onRetry: () => void;
}) {
  if (error.kind === "network") {
    return (
      <FeedbackPanel
        action={{ label: "Retry project", onClick: onRetry }}
        eyebrow="API unavailable"
        heading="The project service could not be reached"
        headingLevel={1}
        kind="error"
      >
        <p>
          This page has no in-memory project fallback. Restart the local API if needed,
          then retry the database-backed detail request.
        </p>
      </FeedbackPanel>
    );
  }

  if (error.kind === "unavailable") {
    return (
      <FeedbackPanel
        action={{ label: "Retry project", onClick: onRetry }}
        eyebrow="Database unavailable"
        heading="Project data is temporarily unavailable"
        headingLevel={1}
        kind="error"
      >
        <p>
          The API responded safely, but PostgreSQL could not read this project. Retry
          after the database is available.
        </p>
      </FeedbackPanel>
    );
  }

  return (
    <FeedbackPanel
      action={{ label: "Retry project", onClick: onRetry }}
      eyebrow="Detail unavailable"
      heading="The project could not be displayed"
      headingLevel={1}
      kind="error"
    >
      <p>
        The service returned an incomplete or unexpected response. No internal error
        details were shown.
      </p>
    </FeedbackPanel>
  );
}

export function ProjectDetailPage() {
  const { projectId } = useParams();
  const location = useLocation();
  const createdNavigation = wasCreatedNavigation(location.state);
  const [reloadToken, setReloadToken] = useState(0);
  const [state, setState] = useState<DetailState>({
    status: "loading",
    projectId: projectId ?? "",
  });
  const pageRef = useRef<HTMLDivElement>(null);
  const requestGenerationRef = useRef(0);
  const projectIdIsValid = isPaintProjectId(projectId);
  const currentState: DetailState =
    projectIdIsValid && state.projectId === projectId
      ? state
      : { status: "loading", projectId: projectId ?? "" };

  useLayoutEffect(() => {
    document.title =
      !projectIdIsValid || currentState.status === "not_found"
        ? "Project Not Found — PaintPilot"
        : "Project Details — PaintPilot";
  }, [currentState.status, projectIdIsValid]);

  useLayoutEffect(() => {
    const heading = pageRef.current?.querySelector<HTMLElement>("h1");
    if (heading === null || heading === undefined) {
      return;
    }
    heading.tabIndex = -1;
    heading.focus({ preventScroll: true });
  }, [currentState.status, projectId]);

  useEffect(() => {
    if (!isPaintProjectId(projectId)) {
      return;
    }

    const controller = new AbortController();
    const generation = requestGenerationRef.current + 1;
    requestGenerationRef.current = generation;

    void getPaintProject(projectId, controller.signal)
      .then((project) => {
        if (
          controller.signal.aborted ||
          requestGenerationRef.current !== generation
        ) {
          return;
        }
        setState({ status: "found", project, projectId });
      })
      .catch((error: unknown) => {
        if (
          controller.signal.aborted ||
          (error instanceof PaintProjectApiError && error.kind === "aborted") ||
          requestGenerationRef.current !== generation
        ) {
          return;
        }

        const apiError = asApiError(error);
        if (apiError.kind === "not_found") {
          setState({ status: "not_found", projectId });
        } else {
          setState({ status: "error", error: apiError, projectId });
        }
      });

    return () => controller.abort();
  }, [projectId, reloadToken]);

  return (
    <div className="page page--detail" ref={pageRef}>
      <div className="detail-breadcrumb">
        <Link to="/paintpilot/projects">← Back to projects</Link>
      </div>

      {createdNavigation ? (
        <div aria-live="polite" className="success-banner" role="status">
          <span aria-hidden="true">✓</span>
          Project created and saved. This detail view is reading the persisted API
          record.
        </div>
      ) : null}

      {projectIdIsValid && currentState.status === "loading" ? (
        <section aria-busy="true" className="detail-loading">
          <p className="eyebrow">PaintProject detail</p>
          <h1>Loading saved project</h1>
          <p aria-label="Reading the project from PaintPilot…" role="status">
            Reading the project from PaintPilot…
          </p>
          <div aria-hidden="true" className="detail-loading__surface" />
        </section>
      ) : null}

      {!projectIdIsValid ? (
        <FeedbackPanel
          eyebrow="Invalid project address"
          heading="This project ID is not a valid UUID"
          headingLevel={1}
          kind="error"
        >
          <p>
            No API request was sent. Return to Projects and open a project from its
            database-backed card.
          </p>
          <Link className="button button--secondary" to="/paintpilot/projects">
            View projects
          </Link>
        </FeedbackPanel>
      ) : null}

      {projectIdIsValid && currentState.status === "not_found" ? (
        <FeedbackPanel
          eyebrow="Project not found"
          heading="This project is unavailable"
          headingLevel={1}
          kind="error"
        >
          <p>
            The project may not exist or may not belong to the current configured demo
            operator. PaintPilot uses the same safe response for both cases.
          </p>
          <Link className="button button--secondary" to="/paintpilot/projects">
            Return to projects
          </Link>
        </FeedbackPanel>
      ) : null}

      {projectIdIsValid && currentState.status === "error" ? (
        <DetailError
          error={currentState.error}
          onRetry={() => {
            setState({ status: "loading", projectId });
            setReloadToken((current) => current + 1);
          }}
        />
      ) : null}

      {projectIdIsValid && currentState.status === "found" ? (
        <article className="project-detail">
          <header className="project-detail__header">
            <div>
              <p className="eyebrow">PaintProject · Read only</p>
              <h1>{currentState.project.title}</h1>
              <p className="project-detail__description">
                {currentState.project.description ?? "No description provided."}
              </p>
            </div>
            <ProjectStatusBadge status={currentState.project.status} />
          </header>

          <section
            aria-labelledby="project-overview-heading"
            className="project-detail__overview"
          >
            <div className="section-heading">
              <div>
                <p className="eyebrow">Persisted project facts</p>
                <h2 id="project-overview-heading">Project overview</h2>
              </div>
            </div>

            <dl className="detail-facts">
              <div>
                <dt>Target style</dt>
                <dd>Cel Shading · Current release</dd>
              </div>
              <div>
                <dt>Planning mode</dt>
                <dd>Planning-only demo</dd>
              </div>
              <div>
                <dt>Workflow status</dt>
                <dd>{currentState.project.status}</dd>
              </div>
              <div>
                <dt>Access scope</dt>
                <dd>Current configured demo operator</dd>
              </div>
              <div>
                <dt>Created</dt>
                <dd>
                  <time dateTime={currentState.project.created_at}>
                    {formatProjectTimestamp(currentState.project.created_at)}
                  </time>
                </dd>
              </div>
              <div>
                <dt>Updated</dt>
                <dd>
                  <time dateTime={currentState.project.updated_at}>
                    {formatProjectTimestamp(currentState.project.updated_at)}
                  </time>
                </dd>
              </div>
              <div className="detail-facts__identifier">
                <dt>Project ID</dt>
                <dd>{currentState.project.id}</dd>
              </div>
            </dl>
          </section>

          <ImageAssetManager
            onProjectChanged={() => setReloadToken((current) => current + 1)}
            project={currentState.project}
          />

          <aside className="next-boundary" aria-labelledby="next-boundary-heading">
            <div aria-hidden="true" className="next-boundary__visual">
              <span />
              <span />
              <span />
            </div>
            <div>
              <p className="eyebrow">Next governed boundary</p>
              <h2 id="next-boundary-heading">
                Human-guided region planning is not implemented yet
              </h2>
              <p>
                Phase 1E-2 ends with a human-confirmed multi-role image set. Region
                drawing, RegionSet creation, AI analysis, inventory matching, and
                PaintPlan generation remain outside this workbench and require the
                next independently reviewed and sealed phase.
              </p>
            </div>
          </aside>
        </article>
      ) : null}
    </div>
  );
}
