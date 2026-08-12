import { useLocation } from "react-router";

import { loginUrl } from "../api/auth";
import { useAuth } from "../auth/AuthContext";
import { FeedbackPanel } from "../components/FeedbackPanel";
import { useAppTranslation } from "../i18n";

export function LoginPage() {
  const { t } = useAppTranslation();
  const location = useLocation();
  const { state, retry } = useAuth();
  const query = new URLSearchParams(location.search);
  const returnTo = query.get("return_to");
  const authError = query.get("auth_error");
  const safeReturn =
    returnTo?.startsWith("/paintpilot") === true || returnTo?.startsWith("/arcana") === true
      ? returnTo
      : "/paintpilot/projects";
  const isArcanaLogin = safeReturn.startsWith("/arcana");
  const retryLogin = () => {
    window.location.assign(loginUrl(safeReturn));
  };

  if (state.status === "loading") {
    return (
      <section aria-busy="true" className="page page--projects">
        <p className="context-label">{t("login.secureSession")}</p>
        <h1>{t("login.checking")}</h1>
        <p role="status">{t("login.loading")}</p>
      </section>
    );
  }

  if (state.status === "error") {
    return (
      <div className="page page--projects">
        <FeedbackPanel
          action={{ label: t("login.retrySession"), onClick: retry }}
          eyebrow={t("login.identityUnavailable")}
          heading={t("login.sessionCheckFailed")}
          headingLevel={1}
          kind="error"
        >
          <p>{t("login.noSubstitutionShort")}</p>
        </FeedbackPanel>
      </div>
    );
  }

  if (authError === "identity_provider_unavailable" || authError === "login_failed") {
    return (
      <div className="page page--projects">
        <FeedbackPanel
          action={{ label: t("login.retrySignIn"), onClick: retryLogin }}
          eyebrow={
            authError === "identity_provider_unavailable"
              ? t("login.providerUnavailable")
              : t("login.signInFailed")
          }
          heading={
            authError === "identity_provider_unavailable"
              ? t("login.providerHeading")
              : t("login.failedHeading")
          }
          headingLevel={1}
          kind="error"
        >
          <p>{t("login.noSubstitution")}</p>
        </FeedbackPanel>
      </div>
    );
  }

  return (
    <div className={`page page--login${isArcanaLogin ? " page--arcana-login" : ""}`}>
      <div className="login-layout">
      <section className="workspace-hero workspace-hero--login" aria-labelledby="login-title">
        {isArcanaLogin ? <span aria-hidden="true" className="arcana-login__orbit" /> : null}
        <div className="workspace-hero__copy">
          <p className="context-label">{t("login.governedAccess")}</p>
          <h1 id="login-title">
            {state.status === "authenticated"
              ? t("login.signedInAs", { name: state.user.display_name })
              : state.reason === "session_expired"
                ? t("login.sessionExpired")
                : t("login.signInHeading")}
          </h1>
          <p className="workspace-hero__lede">
            {t("login.lede")}
          </p>
        </div>
        <a className="button button--primary button--hero" href={loginUrl(safeReturn)}>
          {state.status === "authenticated" ? t("login.continue") : t("shell.signIn")}
        </a>
      </section>
      <aside className="login-proof" aria-label={t("login.boundariesLabel")}>
        <p className="context-label">{t("login.controlledWorkspace")}</p>
        <ol>
          <li>
            <span>01</span>
            <div>
              <strong>{t("login.privateImages")}</strong>
              <p>{t("login.privateImagesCopy")}</p>
            </div>
          </li>
          <li>
            <span>02</span>
            <div>
              <strong>{t("login.humanGeometry")}</strong>
              <p>{t("login.humanGeometryCopy")}</p>
            </div>
          </li>
          <li>
            <span>03</span>
            <div>
              <strong>{t("login.traceableReview")}</strong>
              <p>{t("login.traceableReviewCopy")}</p>
            </div>
          </li>
        </ol>
        <p className="login-proof__session">
          OIDC Authorization Code + PKCE · private HttpOnly session
        </p>
      </aside>
      </div>
    </div>
  );
}
