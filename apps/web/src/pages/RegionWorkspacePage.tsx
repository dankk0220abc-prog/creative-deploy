import { useCallback, useLayoutEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router";

import { isPaintProjectId } from "../api/paintProjects";
import { FeedbackPanel } from "../components/FeedbackPanel";
import { RegionAnnotationWorkspace } from "../components/RegionAnnotationWorkspace";

type RegionPageState =
  | "current"
  | "error"
  | "historical"
  | "loading"
  | "not_found";

function titleForState(state: RegionPageState): string {
  if (state === "not_found") {
    return "Project Not Found — PaintPilot";
  }
  if (state === "error") {
    return "Region Workspace Error — PaintPilot";
  }
  if (state === "historical") {
    return "Region History — PaintPilot";
  }
  if (state === "loading") {
    return "Loading Region Workspace — PaintPilot";
  }
  return "Region Annotation — PaintPilot";
}

export function RegionWorkspacePage() {
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
    document.title = titleForState(effectiveState);
    const heading = pageRef.current?.querySelector<HTMLElement>("h1");
    if (heading !== null && heading !== undefined) {
      heading.tabIndex = -1;
      heading.focus({ preventScroll: true });
    }
  }, [effectiveState, projectId]);

  return (
    <div className="page page--regions" ref={pageRef}>
      <div className="detail-breadcrumb">
        <Link to={`/paintpilot/projects/${projectId ?? ""}`}>
          ← Back to project
        </Link>
      </div>
      {valid ? (
        <RegionAnnotationWorkspace
          onViewStateChange={reportState}
          projectId={projectId}
        />
      ) : (
        <FeedbackPanel
          eyebrow="Invalid project address"
          heading="This project ID is not a valid UUID"
          headingLevel={1}
          kind="error"
        >
          <p>No region API request was sent.</p>
          <Link className="button button--secondary" to="/paintpilot/projects">
            View projects
          </Link>
        </FeedbackPanel>
      )}
    </div>
  );
}
