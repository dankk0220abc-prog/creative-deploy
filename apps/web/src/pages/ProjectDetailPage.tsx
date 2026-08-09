import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { Link, useLocation, useParams } from "react-router";

import {
  getPaintProject,
  isPaintProjectId,
  PaintProjectApiError,
  type PaintProject,
} from "../api/paintProjects";
import { phase3aFixtureEnabled } from "../api/aiFoundation";
import { FeedbackPanel } from "../components/FeedbackPanel";
import { ImageAssetManager } from "../components/ImageAssetManager";
import { ProjectStatusBadge } from "../components/ProjectStatusBadge";
import { ReviewerMembershipManager } from "../components/ReviewerMembershipManager";
import { useAppTranslation } from "../i18n";
import { formatProjectStatus, formatProjectTimestamp } from "../utils/format";

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
  const { t } = useAppTranslation();
  if (error.kind === "network") {
    return (
      <FeedbackPanel
        action={{ label: t("detail.retry"), onClick: onRetry }}
        eyebrow={t("detail.apiUnavailable")}
        heading={t("detail.apiHeading")}
        headingLevel={1}
        kind="error"
      >
        <p>{t("detail.apiCopy")}</p>
      </FeedbackPanel>
    );
  }

  if (error.kind === "unavailable") {
    return (
      <FeedbackPanel
        action={{ label: t("detail.retry"), onClick: onRetry }}
        eyebrow={t("detail.databaseUnavailable")}
        heading={t("detail.databaseHeading")}
        headingLevel={1}
        kind="error"
      >
        <p>{t("detail.databaseCopy")}</p>
      </FeedbackPanel>
    );
  }

  return (
    <FeedbackPanel
      action={{ label: t("detail.retry"), onClick: onRetry }}
      eyebrow={t("detail.unavailable")}
      heading={t("detail.unavailableHeading")}
      headingLevel={1}
      kind="error"
    >
      <p>{t("detail.unavailableCopy")}</p>
    </FeedbackPanel>
  );
}

export function ProjectDetailPage() {
  const { i18n, t } = useAppTranslation();
  const { projectId } = useParams();
  const location = useLocation();
  const createdNavigation = wasCreatedNavigation(location.state);
  const [reloadToken, setReloadToken] = useState(0);
  const [membershipsOpen, setMembershipsOpen] = useState(false);
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
        ? t("title.projectNotFound")
        : t("title.projectDetails");
  }, [currentState.status, i18n.resolvedLanguage, projectIdIsValid, t]);

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
        <Link to="/paintpilot/projects">← {t("detail.back")}</Link>
      </div>

      {createdNavigation ? (
        <div aria-live="polite" className="success-banner" role="status">
          <span aria-hidden="true">✓</span>
          {t("detail.createdBanner")}
        </div>
      ) : null}

      {projectIdIsValid && currentState.status === "loading" ? (
        <section aria-busy="true" className="detail-loading">
          <p className="context-label">{t("detail.loadingEyebrow")}</p>
          <h1>{t("detail.loadingHeading")}</h1>
          <p aria-label={t("detail.reading")} role="status">
            {t("detail.reading")}
          </p>
          <div aria-hidden="true" className="detail-loading__surface" />
        </section>
      ) : null}

      {!projectIdIsValid ? (
        <FeedbackPanel
          eyebrow={t("detail.invalidAddress")}
          heading={t("detail.invalidId")}
          headingLevel={1}
          kind="error"
        >
          <p>{t("detail.invalidCopy")}</p>
          <Link className="button button--secondary" to="/paintpilot/projects">
            {t("detail.viewProjects")}
          </Link>
        </FeedbackPanel>
      ) : null}

      {projectIdIsValid && currentState.status === "not_found" ? (
        <FeedbackPanel
          eyebrow={t("detail.notFound")}
          heading={t("detail.unavailableProject")}
          headingLevel={1}
          kind="error"
        >
          <p>{t("detail.notFoundCopy")}</p>
          <Link className="button button--secondary" to="/paintpilot/projects">
            {t("detail.returnProjects")}
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
              <p className="context-label">
                {t("detail.role", {
                  role: currentState.project.access_role === "owner"
                    ? t("common.owner")
                    : t("common.reviewer"),
                })}
              </p>
              <h1>{currentState.project.title}</h1>
              <p className="project-detail__description">
                {currentState.project.description ?? t("common.noDescription")}
              </p>
            </div>
            <ProjectStatusBadge status={currentState.project.status} />
          </header>

          <section
            aria-labelledby="project-next-action-heading"
            className="project-command-strip"
          >
            <div className="project-command-strip__lead">
              <p className="context-label">{t("detail.currentSequence")}</p>
              <h2 id="project-next-action-heading">
                {currentState.project.current_image_asset_id === null
                  ? t("detail.startImages")
                  : t("detail.continueWorkspace")}
              </h2>
              <p>
                {currentState.project.access_role === "owner"
                  ? t("detail.ownerSequence")
                  : t("detail.reviewerSequence")}
              </p>
            </div>
            <nav aria-label={t("detail.sectionsLabel")} className="project-local-nav">
              <a href="#image-set-workbench">
                <span>01</span>
                {t("detail.imagesReadiness")}
              </a>
              {currentState.project.access_role === "owner" ? (
                <a href="#reviewer-access">
                  <span>02</span>
                  {t("detail.reviewerAccess")}
                </a>
              ) : null}
              <Link to={`/paintpilot/projects/${currentState.project.id}/regions`}>
                <span>{currentState.project.access_role === "owner" ? "03" : "02"}</span>
                {t("detail.regionWorkspace")}
              </Link>
              {phase3aFixtureEnabled && currentState.project.access_role === "owner" ? (
                <Link
                  to={`/paintpilot/projects/${currentState.project.id}/ai-model-policy`}
                >
                  <span>04</span>
                  {t("detail.aiModelPolicy")}
                </Link>
              ) : null}
            </nav>
          </section>

          <section
            aria-labelledby="project-overview-heading"
            className="project-detail__overview"
          >
            <div className="section-heading">
              <div>
                <p className="context-label">{t("detail.persistedFacts")}</p>
                <h2 id="project-overview-heading">{t("detail.overview")}</h2>
              </div>
            </div>

            <dl className="detail-facts">
              <div>
                <dt>{t("detail.targetStyle")}</dt>
                <dd>{t("detail.targetStyleValue")}</dd>
              </div>
              <div>
                <dt>{t("detail.planningMode")}</dt>
                <dd>{t("detail.planningModeValue")}</dd>
              </div>
              <div>
                <dt>{t("detail.workflowStatus")}</dt>
                <dd>{formatProjectStatus(currentState.project.status)}</dd>
              </div>
              <div>
                <dt>{t("detail.accessScope")}</dt>
                <dd>
                  {currentState.project.access_role === "owner"
                    ? t("detail.ownerScope")
                    : t("detail.reviewerScope")}
                </dd>
              </div>
              <div>
                <dt>{t("common.created")}</dt>
                <dd>
                  <time dateTime={currentState.project.created_at}>
                    {formatProjectTimestamp(currentState.project.created_at)}
                  </time>
                </dd>
              </div>
              <div>
                <dt>{t("common.updated")}</dt>
                <dd>
                  <time dateTime={currentState.project.updated_at}>
                    {formatProjectTimestamp(currentState.project.updated_at)}
                  </time>
                </dd>
              </div>
              <div className="detail-facts__identifier">
                <dt>{t("detail.projectId")}</dt>
                <dd>{currentState.project.id}</dd>
              </div>
            </dl>
          </section>

          <ImageAssetManager
            canManageImages={currentState.project.access_role === "owner"}
            onProjectChanged={() => setReloadToken((current) => current + 1)}
            project={currentState.project}
          />

          {currentState.project.access_role === "owner" && membershipsOpen ? (
            <ReviewerMembershipManager projectId={currentState.project.id} />
          ) : currentState.project.access_role === "owner" ? (
            <section className="project-memberships" id="reviewer-access">
              <p className="context-label">{t("detail.ownerGoverned")}</p>
              <h2>{t("detail.reviewerAccess")}</h2>
              <p>{t("detail.reviewerAccessCopy")}</p>
              <button
                className="button button--secondary"
                onClick={() => setMembershipsOpen(true)}
                type="button"
              >
                {t("detail.manageReviewerAccess")}
              </button>
            </section>
          ) : null}

          {phase3aFixtureEnabled && currentState.project.access_role === "owner" ? (
            <aside className="ai-project-entry" aria-labelledby="ai-project-entry-heading">
              <div>
                <p className="context-label">{t("detail.aiFixtureEyebrow")}</p>
                <h2 id="ai-project-entry-heading">{t("detail.aiFixtureHeading")}</h2>
                <p>{t("detail.aiFixtureCopy")}</p>
              </div>
              <Link
                className="button button--secondary"
                to={`/paintpilot/projects/${currentState.project.id}/ai-model-policy`}
              >
                {t("detail.openAiPolicy")}
              </Link>
            </aside>
          ) : null}

          <aside className="next-boundary" aria-labelledby="next-boundary-heading">
            <div aria-hidden="true" className="next-boundary__index">
              {currentState.project.access_role === "owner" ? "03" : "02"}
            </div>
            <div>
              <p className="context-label">{t("detail.humanWorkspace")}</p>
              <h2 id="next-boundary-heading">{t("detail.regionHeading")}</h2>
              <p>{t("detail.regionCopy")}</p>
              <Link
                className="button button--primary next-boundary__action"
                to={`/paintpilot/projects/${currentState.project.id}/regions`}
              >
                {t("detail.openRegion")}
              </Link>
            </div>
          </aside>
        </article>
      ) : null}
    </div>
  );
}
