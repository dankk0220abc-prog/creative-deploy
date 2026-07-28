import { Link } from "react-router";

import { FeedbackPanel } from "../components/FeedbackPanel";

export function NotFoundPage() {
  return (
    <div className="page page--not-found">
      <FeedbackPanel
        eyebrow="Unknown workspace route"
        heading="This PaintPilot page does not exist"
        headingLevel={1}
        kind="info"
      >
        <p>
          The address does not match a supported frontend route. This is different from
          a valid project detail URL whose project is missing.
        </p>
        <Link className="button button--primary" to="/paintpilot/projects">
          Open projects
        </Link>
      </FeedbackPanel>
    </div>
  );
}
