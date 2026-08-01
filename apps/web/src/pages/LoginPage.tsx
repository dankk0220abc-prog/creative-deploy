import { useLocation } from "react-router";

import { loginUrl } from "../api/auth";
import { useAuth } from "../auth/AuthContext";
import { FeedbackPanel } from "../components/FeedbackPanel";

export function LoginPage() {
  const location = useLocation();
  const { state, retry } = useAuth();
  const query = new URLSearchParams(location.search);
  const returnTo = query.get("return_to");
  const authError = query.get("auth_error");
  const safeReturn =
    returnTo?.startsWith("/paintpilot") === true
      ? returnTo
      : "/paintpilot/projects";
  const retryLogin = () => {
    window.location.assign(loginUrl(safeReturn));
  };

  if (state.status === "loading") {
    return (
      <section aria-busy="true" className="page page--projects">
        <p className="eyebrow">Secure session</p>
        <h1>Checking your PaintPilot session</h1>
        <p role="status">Loading sign-in state…</p>
      </section>
    );
  }

  if (state.status === "error") {
    return (
      <div className="page page--projects">
        <FeedbackPanel
          action={{ label: "Retry session", onClick: retry }}
          eyebrow="Identity service unavailable"
          heading="PaintPilot could not check your session"
          headingLevel={1}
          kind="error"
        >
          <p>No Demo Principal or client-provided identity was substituted.</p>
        </FeedbackPanel>
      </div>
    );
  }

  if (authError === "identity_provider_unavailable" || authError === "login_failed") {
    return (
      <div className="page page--projects">
        <FeedbackPanel
          action={{ label: "Try sign in again", onClick: retryLogin }}
          eyebrow={
            authError === "identity_provider_unavailable"
              ? "Identity provider unavailable"
              : "Sign-in failed"
          }
          heading={
            authError === "identity_provider_unavailable"
              ? "PaintPilot could not reach the identity provider"
              : "PaintPilot could not complete sign-in"
          }
          headingLevel={1}
          kind="error"
        >
          <p>
            No Demo Principal, request header, email, or client-provided role was
            substituted. Retry when the governed identity service is available.
          </p>
        </FeedbackPanel>
      </div>
    );
  }

  return (
    <div className="page page--projects">
      <section className="workspace-hero" aria-labelledby="login-title">
        <div className="workspace-hero__copy">
          <p className="eyebrow">Governed access</p>
          <h1 id="login-title">
            {state.status === "authenticated"
              ? `Signed in as ${state.user.display_name}`
              : state.reason === "session_expired"
                ? "Your session expired"
                : "Sign in to PaintPilot"}
          </h1>
          <p className="workspace-hero__lede">
            PaintPilot uses an OIDC Authorization Code flow with PKCE and a private
            HttpOnly server session.
          </p>
        </div>
        <a className="button button--primary button--hero" href={loginUrl(safeReturn)}>
          {state.status === "authenticated" ? "Continue" : "Sign in"}
        </a>
      </section>
    </div>
  );
}
