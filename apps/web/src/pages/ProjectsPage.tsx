import { useEffect, useRef, useState } from "react";
import { Link } from "react-router";

import {
  listPaintProjects,
  PaintProjectApiError,
  type PaintProjectList,
} from "../api/paintProjects";
import { FeedbackPanel } from "../components/FeedbackPanel";
import { ProjectCard } from "../components/ProjectCard";

const PAGE_SIZE = 20;

type ProjectsState =
  | { status: "error"; error: PaintProjectApiError }
  | { status: "loaded"; data: PaintProjectList }
  | { status: "loading" };

function asApiError(error: unknown): PaintProjectApiError {
  if (error instanceof PaintProjectApiError) {
    return error;
  }
  return new PaintProjectApiError(
    "internal",
    "The project workspace could not complete this request.",
  );
}

function ListError({
  error,
  onRetry,
}: {
  error: PaintProjectApiError;
  onRetry: () => void;
}) {
  if (error.kind === "network") {
    return (
      <FeedbackPanel
        action={{ label: "Retry projects", onClick: onRetry }}
        eyebrow="API unavailable"
        heading="The project service could not be reached"
        kind="error"
      >
        <p>
          The workspace shell is available, but the PaintPilot API is not responding.
          Check the local API process and retry.
        </p>
      </FeedbackPanel>
    );
  }

  if (error.kind === "unavailable") {
    return (
      <FeedbackPanel
        action={{ label: "Retry projects", onClick: onRetry }}
        eyebrow="Database unavailable"
        heading="Project data is temporarily unavailable"
        kind="error"
      >
        <p>
          The API responded safely, but PostgreSQL could not provide project data.
          Nothing has been replaced with local or sample records.
        </p>
      </FeedbackPanel>
    );
  }

  return (
    <FeedbackPanel
      action={{ label: "Retry projects", onClick: onRetry }}
      eyebrow="Projects unavailable"
      heading="The workspace could not load project data"
      kind="error"
    >
      <p>
        The service returned an incomplete or unexpected response. No internal details
        were displayed, and no project data was changed.
      </p>
    </FeedbackPanel>
  );
}

function ProjectsLoading() {
  return (
    <section aria-busy="true" aria-labelledby="projects-loading-heading">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Your projects</p>
          <h2 id="projects-loading-heading">Loading project records</h2>
        </div>
        <span
          aria-label="Reading from PaintPilot…"
          className="loading-copy"
          role="status"
        >
          Reading from PaintPilot…
        </span>
      </div>
      <div className="project-grid project-grid--loading" aria-hidden="true">
        {[0, 1, 2].map((item) => (
          <div className="project-skeleton" key={item}>
            <span />
            <span />
            <span />
          </div>
        ))}
      </div>
    </section>
  );
}

export function ProjectsPage() {
  const [offset, setOffset] = useState(0);
  const [reloadToken, setReloadToken] = useState(0);
  const [state, setState] = useState<ProjectsState>({ status: "loading" });
  const requestGenerationRef = useRef(0);

  useEffect(() => {
    const controller = new AbortController();
    const generation = requestGenerationRef.current + 1;
    requestGenerationRef.current = generation;

    void listPaintProjects({
      limit: PAGE_SIZE,
      offset,
      signal: controller.signal,
    })
      .then((data) => {
        if (
          controller.signal.aborted ||
          requestGenerationRef.current !== generation
        ) {
          return;
        }
        setState({ status: "loaded", data });
      })
      .catch((error: unknown) => {
        if (
          controller.signal.aborted ||
          (error instanceof PaintProjectApiError && error.kind === "aborted") ||
          requestGenerationRef.current !== generation
        ) {
          return;
        }
        setState({ status: "error", error: asApiError(error) });
      });

    return () => {
      controller.abort();
    };
  }, [offset, reloadToken]);

  const retry = () => {
    setState({ status: "loading" });
    setReloadToken((current) => current + 1);
  };

  const moveToOffset = (nextOffset: number) => {
    setState({ status: "loading" });
    setOffset(nextOffset);
  };

  const isEmpty = state.status === "loaded" && state.data.total === 0;

  return (
    <div className="page page--projects">
      <section className="workspace-hero" aria-labelledby="projects-page-title">
        <div className="workspace-hero__copy">
          <p className="eyebrow">PaintPilot workspace</p>
          <h1 id="projects-page-title">Paint projects</h1>
          <p className="workspace-hero__lede">
            Create, revisit, and track database-backed repaint planning projects with
            an explicit human-control boundary.
          </p>
        </div>
        {!isEmpty ? (
          <Link className="button button--primary button--hero" to="/paintpilot/projects/new">
            <span aria-hidden="true">＋</span>
            Create project
          </Link>
        ) : null}
        <div className="workspace-hero__particles" aria-hidden="true">
          <span />
          <span />
          <span />
          <span />
          <span />
        </div>
      </section>

      <div className="page__content">
        {state.status === "loading" ? <ProjectsLoading /> : null}

        {state.status === "error" ? (
          <ListError error={state.error} onRetry={retry} />
        ) : null}

        {state.status === "loaded" && state.data.total === 0 ? (
          <FeedbackPanel
            eyebrow="Your projects"
            heading="No paint projects yet"
            kind="empty"
          >
            <p>
              Start with a title and optional description. The new project will be saved
              in PostgreSQL as a planning-only draft.
            </p>
            <Link className="button button--primary" to="/paintpilot/projects/new">
              Create your first project
            </Link>
          </FeedbackPanel>
        ) : null}

        {state.status === "loaded" && state.data.total > 0 ? (
          <section aria-labelledby="your-projects-heading">
            <div className="section-heading">
              <div>
                <p className="eyebrow">Database records</p>
                <h2 id="your-projects-heading">Your projects</h2>
              </div>
              <p aria-live="polite" className="result-count">
                {state.data.total} {state.data.total === 1 ? "project" : "projects"}
              </p>
            </div>

            <div className="project-grid">
              {state.data.items.map((project) => (
                <ProjectCard key={project.id} project={project} />
              ))}
            </div>

            {state.data.total > state.data.limit ? (
              <nav aria-label="Project pages" className="pagination">
                <button
                  className="button button--secondary"
                  disabled={state.data.offset === 0}
                  onClick={() =>
                    moveToOffset(Math.max(0, state.data.offset - state.data.limit))
                  }
                  type="button"
                >
                  Previous
                </button>
                <span>
                  Showing {state.data.offset + 1}–
                  {state.data.offset + state.data.items.length} of {state.data.total}
                </span>
                <button
                  className="button button--secondary"
                  disabled={
                    state.data.offset + state.data.items.length >= state.data.total
                  }
                  onClick={() =>
                    moveToOffset(state.data.offset + state.data.limit)
                  }
                  type="button"
                >
                  Next
                </button>
              </nav>
            ) : null}
          </section>
        ) : null}

        <aside className="capability-note" aria-label="Current PaintPilot capability">
          <span className="capability-note__mark" aria-hidden="true">
            i
          </span>
          <div>
            <strong>Current release boundary</strong>
            <p>
              Project cards remain metadata-only. Open a project detail to manage its
              private immutable multi-role image set, human readiness history, and
              versioned Polygon workspace. Automated image quality assessment, viewpoint
              analysis, inventory, knowledge retrieval, and paint-plan generation remain
              outside the current release.
            </p>
          </div>
        </aside>
      </div>
    </div>
  );
}
