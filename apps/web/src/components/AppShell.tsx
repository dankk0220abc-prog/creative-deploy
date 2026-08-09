import {
  type MouseEvent as ReactMouseEvent,
  useLayoutEffect,
  useRef,
  useState,
} from "react";
import { Link, Outlet, useLocation } from "react-router";

import { loginUrl } from "../api/auth";
import { phase3aFixtureEnabled } from "../api/aiFoundation";
import { isPaintProjectId } from "../api/paintProjects";
import { useAuth } from "../auth/AuthContext";
import { useAppTranslation } from "../i18n";
import { LocaleSwitcher } from "./LocaleSwitcher";

const PROJECTS_PATH = "/paintpilot/projects";
const CREATE_PROJECT_PATH = "/paintpilot/projects/new";
const AI_SETTINGS_PATH = "/paintpilot/settings/ai";
const isArtifactSmoke = import.meta.env.VITE_RUNTIME_PROFILE === "artifact-smoke";
const isPublicDemo = import.meta.env.VITE_RUNTIME_PROFILE === "public-demo";

function navigationClassName(isActive: boolean): string {
  return isActive ? "shell-nav__link shell-nav__link--active" : "shell-nav__link";
}

function normalizePathname(pathname: string): string {
  return pathname.length > 1 ? pathname.replace(/\/+$/, "") : pathname;
}

function isProjectDetailPath(pathname: string): boolean {
  const normalizedPathname = normalizePathname(pathname);
  return (
    normalizedPathname.startsWith(`${PROJECTS_PATH}/`) &&
    normalizedPathname !== CREATE_PROJECT_PATH &&
    normalizedPathname.slice(PROJECTS_PATH.length + 1).length > 0 &&
    !normalizedPathname.slice(PROJECTS_PATH.length + 1).includes("/")
  );
}

function isRegionWorkspacePath(pathname: string): boolean {
  const normalizedPathname = normalizePathname(pathname);
  const prefix = `${PROJECTS_PATH}/`;
  if (!normalizedPathname.startsWith(prefix) || !normalizedPathname.endsWith("/regions")) {
    return false;
  }
  const projectId = normalizedPathname.slice(
    prefix.length,
    -"/regions".length,
  );
  return projectId.length > 0 && !projectId.includes("/");
}

function titleKeyForPath(pathname: string): string {
  const normalizedPathname = normalizePathname(pathname);
  if (normalizedPathname === PROJECTS_PATH) {
    return "title.projects";
  }
  if (normalizedPathname === CREATE_PROJECT_PATH) {
    return "title.createProject";
  }
  if (normalizedPathname === "/paintpilot/login") {
    return "title.login";
  }
  if (normalizedPathname.startsWith(AI_SETTINGS_PATH)) {
    return "title.aiSettings";
  }
  if (normalizedPathname.endsWith("/ai-model-policy")) {
    return "title.aiProjectPolicy";
  }
  if (isRegionWorkspacePath(normalizedPathname)) {
    const projectId = normalizedPathname.slice(
      PROJECTS_PATH.length + 1,
      -"/regions".length,
    );
    return isPaintProjectId(projectId)
      ? "title.regionLoading"
      : "title.projectNotFound";
  }
  if (isProjectDetailPath(normalizedPathname)) {
    const projectId = normalizedPathname.slice(PROJECTS_PATH.length + 1);
    return isPaintProjectId(projectId)
      ? "title.projectDetails"
      : "title.projectNotFound";
  }
  return "title.pageNotFound";
}

function focusPageHeading(main: HTMLElement | null): void {
  if (main === null) {
    return;
  }

  const heading = main.querySelector<HTMLElement>("h1");
  const target = heading ?? main;
  if (target !== main) {
    target.tabIndex = -1;
  }
  target.focus({ preventScroll: true });
  target.scrollIntoView?.({ block: "start" });
}

export function AppShell() {
  const { i18n, t } = useAppTranslation();
  const { logout, state: authState } = useAuth();
  const location = useLocation();
  const mainRef = useRef<HTMLElement>(null);
  const previousRouteRef = useRef<string | null>(null);
  const [paginationFocusToken, setPaginationFocusToken] = useState(0);
  const normalizedPathname = normalizePathname(location.pathname);
  const projectsIsCurrent =
    normalizedPathname === PROJECTS_PATH ||
    isProjectDetailPath(normalizedPathname) ||
    isRegionWorkspacePath(normalizedPathname);
  const createProjectIsCurrent = normalizedPathname === CREATE_PROJECT_PATH;
  const aiSettingsIsCurrent =
    normalizedPathname.startsWith(AI_SETTINGS_PATH) ||
    normalizedPathname.endsWith("/ai-model-policy");

  useLayoutEffect(() => {
    document.title = t(titleKeyForPath(location.pathname));
  }, [i18n.resolvedLanguage, location.pathname, t]);

  useLayoutEffect(() => {
    const routeKey = `${location.pathname}${location.search}`;
    const previousRoute = previousRouteRef.current;
    previousRouteRef.current = routeKey;
    if (previousRoute !== null && previousRoute !== routeKey) {
      focusPageHeading(mainRef.current);
    }
  }, [location.pathname, location.search]);

  useLayoutEffect(() => {
    if (paginationFocusToken > 0) {
      focusPageHeading(mainRef.current);
    }
  }, [paginationFocusToken]);

  const focusMainContent = (event: ReactMouseEvent<HTMLAnchorElement>) => {
    event.preventDefault();
    const main = mainRef.current;
    if (main === null) {
      return;
    }

    if (window.location.hash !== "#main-content") {
      window.history.replaceState(
        window.history.state,
        "",
        `${window.location.pathname}${window.location.search}#main-content`,
      );
    }
    main.focus({ preventScroll: true });
    main.scrollIntoView?.({ block: "start" });
  };

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content" onClick={focusMainContent}>
        {t("shell.skip")}
      </a>

      <header className="platform-header">
        <div className="platform-header__inner">
          <Link
            aria-label={t("shell.brandLabel")}
            className="brand-lockup"
            to={PROJECTS_PATH}
          >
            <span className="brand-lockup__platform">CreativeDeploy</span>
            <span aria-hidden="true" className="brand-lockup__divider" />
            <span className="brand-lockup__product">
              <span aria-hidden="true" className="brand-lockup__mark">
                P
              </span>
              PaintPilot
            </span>
          </Link>

          <nav aria-label={t("shell.navigationLabel")} className="shell-nav">
            <Link
              aria-current={projectsIsCurrent ? "page" : undefined}
              className={navigationClassName(projectsIsCurrent)}
              to={PROJECTS_PATH}
            >
              {t("shell.projects")}
            </Link>
            {!isPublicDemo ? (
              <Link
                aria-current={createProjectIsCurrent ? "page" : undefined}
                className={navigationClassName(createProjectIsCurrent)}
                to={CREATE_PROJECT_PATH}
              >
                {t("shell.createProject")}
              </Link>
            ) : null}
            {phase3aFixtureEnabled && authState.status === "authenticated" ? (
              <Link
                aria-current={aiSettingsIsCurrent ? "page" : undefined}
                className={navigationClassName(aiSettingsIsCurrent)}
                to={`${AI_SETTINGS_PATH}/models-providers`}
              >
                {t("shell.aiSettings")}
              </Link>
            ) : null}
            {authState.status === "authenticated" ? (
              <>
                <span className="shell-nav__identity">
                  <span className="shell-nav__identity-copy">
                    <small>{t("shell.signedIn")}</small>
                    <span>{authState.user.display_name}</span>
                  </span>
                  <button
                    className="shell-nav__logout"
                    onClick={() => void logout()}
                    type="button"
                  >
                    {t("shell.logOut")}
                  </button>
                </span>
                <details className="shell-account-menu">
                  <summary aria-label={t("shell.accountActions")}>
                    {authState.user.display_name}
                  </summary>
                  <button onClick={() => void logout()} type="button">
                    {t("shell.logOut")}
                  </button>
                </details>
              </>
            ) : (
              <a className="shell-nav__link" href={loginUrl(location.pathname)}>
                {t("shell.signIn")}
              </a>
            )}
          </nav>
          <LocaleSwitcher />
        </div>
      </header>

      {isPublicDemo ? (
        <aside aria-label={t("shell.demoLabel")} className="demo-banner">
          <div>
            <strong>{t("shell.demoLabel")}</strong>
            <span>{t("shell.demoCopy")}</span>
          </div>
        </aside>
      ) : null}

      <main
        className="workspace-main"
        id="main-content"
        onClickCapture={(event) => {
          const target = event.target;
          const paginationButton =
            target instanceof Element
              ? target.closest(".pagination button")
              : null;
          if (
            paginationButton instanceof HTMLButtonElement &&
            !paginationButton.disabled
          ) {
            setPaginationFocusToken((current) => current + 1);
          }
        }}
        ref={mainRef}
        tabIndex={-1}
      >
        <Outlet />
      </main>

      <footer className="workspace-footer">
        <details className="workspace-footer__details">
          <summary>{t("shell.environmentDetails")}</summary>
          <div>
            <span className="workspace-footer__label">{t("shell.footerLabel")}</span>
            <span>{t("shell.footerCopy")}</span>
          </div>
        </details>
        {isArtifactSmoke ? (
          <p className="workspace-footer__runtime-label">
            LOCAL_PRODUCTION_STYLE_SMOKE · NOT_REAL_PRODUCTION
          </p>
        ) : null}
      </footer>
    </div>
  );
}
