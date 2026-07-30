import { useLayoutEffect, useRef } from "react";
import { Link, useParams } from "react-router";

import { isPaintProjectId } from "../api/paintProjects";
import { FeedbackPanel } from "../components/FeedbackPanel";
import { RegionAnnotationWorkspace } from "../components/RegionAnnotationWorkspace";

export function RegionWorkspacePage() {
  const { projectId } = useParams();
  const pageRef = useRef<HTMLDivElement>(null);
  const valid = isPaintProjectId(projectId);

  useLayoutEffect(() => {
    document.title = valid
      ? "Region Annotation — PaintPilot"
      : "Project Not Found — PaintPilot";
    const heading = pageRef.current?.querySelector<HTMLElement>("h1");
    if (heading !== null && heading !== undefined) {
      heading.tabIndex = -1;
      heading.focus({ preventScroll: true });
    }
  }, [valid, projectId]);

  return (
    <div className="page page--regions" ref={pageRef}>
      <div className="detail-breadcrumb">
        <Link to={`/paintpilot/projects/${projectId ?? ""}`}>
          ← Back to project
        </Link>
      </div>
      {valid ? (
        <RegionAnnotationWorkspace projectId={projectId} />
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
