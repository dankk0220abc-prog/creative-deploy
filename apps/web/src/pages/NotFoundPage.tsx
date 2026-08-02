import { Link } from "react-router";

import { FeedbackPanel } from "../components/FeedbackPanel";
import { useAppTranslation } from "../i18n";

export function NotFoundPage() {
  const { t } = useAppTranslation();
  return (
    <div className="page page--not-found">
      <FeedbackPanel
        eyebrow={t("notFound.eyebrow")}
        heading={t("notFound.heading")}
        headingLevel={1}
        kind="info"
      >
        <p>{t("notFound.copy")}</p>
        <Link className="button button--primary" to="/paintpilot/projects">
          {t("notFound.action")}
        </Link>
      </FeedbackPanel>
    </div>
  );
}
