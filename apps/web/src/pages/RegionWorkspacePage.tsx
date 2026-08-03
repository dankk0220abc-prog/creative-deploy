import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router";

import { isPaintProjectId } from "../api/paintProjects";
import { FeedbackPanel } from "../components/FeedbackPanel";
import { RegionAnnotationWorkspace } from "../components/RegionAnnotationWorkspace";
import { useAppTranslation } from "../i18n";

type RegionPageState =
  | "current"
  | "error"
  | "historical"
  | "loading"
  | "not_found";

function titleKeyForState(state: RegionPageState): string {
  if (state === "not_found") {
    return "title.projectNotFound";
  }
  if (state === "error") {
    return "title.regionError";
  }
  if (state === "historical") {
    return "title.regionHistory";
  }
  if (state === "loading") {
    return "title.regionLoading";
  }
  return "title.regionAnnotation";
}

export function RegionWorkspacePage() {
  const { i18n, t } = useAppTranslation();
  const { projectId } = useParams();
  const pageRef = useRef<HTMLDivElement>(null);
  const valid = isPaintProjectId(projectId);
  const [reportedState, setReportedState] = useState<{
    projectId: string;
    state: RegionPageState;
  }>({ projectId: projectId ?? "", state: "loading" });
  const effectiveState: RegionPageState = !valid
    ? "not_found"
    : reportedState.projectId === projectId
      ? reportedState.state
      : "loading";
  const reportState = useCallback(
    (state: RegionPageState) => {
      setReportedState({ projectId: projectId ?? "", state });
    },
    [projectId],
  );

  useLayoutEffect(() => {
    const heading = pageRef.current?.querySelector<HTMLElement>("h1");
    if (heading !== null && heading !== undefined) {
      heading.tabIndex = -1;
      heading.focus({ preventScroll: true });
    }
  }, [effectiveState, projectId]);

  useEffect(() => {
    document.title = t(titleKeyForState(effectiveState));
  }, [effectiveState, i18n.resolvedLanguage, projectId, t]);

  return (
    <div className="page page--regions" ref={pageRef}>
      <div className="detail-breadcrumb">
        <Link to={`/paintpilot/projects/${projectId ?? ""}`}>
          ← {t("regionPage.back")}
        </Link>
      </div>
      {valid ? (
        <RegionAnnotationWorkspace
          onViewStateChange={reportState}
          projectId={projectId}
        />
      ) : (
        <FeedbackPanel
          eyebrow={t("regionPage.invalidAddress")}
          heading={t("regionPage.invalidId")}
          headingLevel={1}
          kind="error"
        >
          <p>{t("regionPage.noRequest")}</p>
          <Link className="button button--secondary" to="/paintpilot/projects">
            {t("regionPage.viewProjects")}
          </Link>
        </FeedbackPanel>
      )}
    </div>
  );
}
