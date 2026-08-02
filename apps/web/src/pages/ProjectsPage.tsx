import { useEffect, useRef, useState } from "react";
import { Link } from "react-router";

import {
  listPaintProjects,
  PaintProjectApiError,
  type PaintProjectList,
} from "../api/paintProjects";
import { FeedbackPanel } from "../components/FeedbackPanel";
import { ProjectCard } from "../components/ProjectCard";
import { useAppTranslation } from "../i18n";

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
  const { t } = useAppTranslation();
  if (error.kind === "network") {
    return (
      <FeedbackPanel
        action={{ label: t("projects.retry"), onClick: onRetry }}
        eyebrow={t("projects.apiUnavailable")}
        heading={t("projects.apiHeading")}
        kind="error"
      >
        <p>{t("projects.apiCopy")}</p>
      </FeedbackPanel>
    );
  }

  if (error.kind === "unavailable") {
    return (
      <FeedbackPanel
        action={{ label: t("projects.retry"), onClick: onRetry }}
        eyebrow={t("projects.databaseUnavailable")}
        heading={t("projects.databaseHeading")}
        kind="error"
      >
        <p>{t("projects.databaseCopy")}</p>
      </FeedbackPanel>
    );
  }

  return (
    <FeedbackPanel
      action={{ label: t("projects.retry"), onClick: onRetry }}
      eyebrow={t("projects.listUnavailable")}
      heading={t("projects.listHeading")}
      kind="error"
    >
      <p>{t("projects.listCopy")}</p>
    </FeedbackPanel>
  );
}

function ProjectsLoading() {
  const { t } = useAppTranslation();
  return (
    <section aria-busy="true" aria-labelledby="projects-loading-heading">
      <div className="section-heading">
        <div>
          <p className="context-label">{t("projects.yours")}</p>
          <h2 id="projects-loading-heading">{t("projects.loadingHeading")}</h2>
        </div>
        <span
          aria-label={t("projects.reading")}
          className="loading-copy"
          role="status"
        >
          {t("projects.reading")}
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
  const { t } = useAppTranslation();
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
      <section
        className="workspace-hero workspace-hero--projects"
        aria-labelledby="projects-page-title"
      >
        <div className="workspace-hero__copy">
          <p className="context-label">{t("projects.workspace")}</p>
          <h1 id="projects-page-title">{t("projects.heading")}</h1>
          <p className="workspace-hero__lede">{t("projects.lede")}</p>
        </div>
        {!isEmpty ? (
          <Link className="button button--primary button--hero" to="/paintpilot/projects/new">
            <span aria-hidden="true">＋</span>
            {t("projects.create")}
          </Link>
        ) : null}
      </section>

      <div className="page__content">
        {state.status === "loading" ? <ProjectsLoading /> : null}

        {state.status === "error" ? (
          <ListError error={state.error} onRetry={retry} />
        ) : null}

        {state.status === "loaded" && state.data.total === 0 ? (
          <FeedbackPanel
            eyebrow={t("projects.yours")}
            heading={t("projects.emptyHeading")}
            kind="empty"
          >
            <p>{t("projects.emptyCopy")}</p>
            <Link className="button button--primary" to="/paintpilot/projects/new">
              {t("projects.createFirst")}
            </Link>
          </FeedbackPanel>
        ) : null}

        {state.status === "loaded" && state.data.total > 0 ? (
          <section aria-labelledby="your-projects-heading">
            <div className="section-heading">
              <div>
                <p className="context-label">{t("projects.activeWorkspace")}</p>
                <h2 id="your-projects-heading">{t("projects.yours")}</h2>
              </div>
              <p aria-live="polite" className="result-count">
                {t("projects.count", { count: state.data.total })}
              </p>
            </div>

            <div className="project-grid">
              {state.data.items.map((project) => (
                <ProjectCard key={project.id} project={project} />
              ))}
            </div>

            {state.data.total > state.data.limit ? (
              <nav aria-label={t("projects.pagesLabel")} className="pagination">
                <button
                  className="button button--secondary"
                  disabled={state.data.offset === 0}
                  onClick={() =>
                    moveToOffset(Math.max(0, state.data.offset - state.data.limit))
                  }
                  type="button"
                >
                  {t("projects.previous")}
                </button>
                <span>
                  {t("projects.showing", {
                    from: state.data.offset + 1,
                    to: state.data.offset + state.data.items.length,
                    total: state.data.total,
                  })}
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
                  {t("projects.next")}
                </button>
              </nav>
            ) : null}
          </section>
        ) : null}

        <aside className="capability-note" aria-label={t("projects.capabilityLabel")}>
          <span className="capability-note__mark" aria-hidden="true">
            i
          </span>
          <div>
            <strong>{t("projects.releaseBoundary")}</strong>
            <p>{t("projects.releaseBoundaryCopy")}</p>
          </div>
        </aside>
      </div>
    </div>
  );
}
