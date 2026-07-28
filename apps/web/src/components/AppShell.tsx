import {
  type MouseEvent as ReactMouseEvent,
  useLayoutEffect,
  useRef,
  useState,
} from "react";
import { Link, Outlet, useLocation } from "react-router";

import { isPaintProjectId } from "../api/paintProjects";

const PROJECTS_PATH = "/paintpilot/projects";
const CREATE_PROJECT_PATH = "/paintpilot/projects/new";

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

function titleForPath(pathname: string): string {
  const normalizedPathname = normalizePathname(pathname);
  if (normalizedPathname === PROJECTS_PATH) {
    return "Projects — PaintPilot";
  }
  if (normalizedPathname === CREATE_PROJECT_PATH) {
    return "Create Project — PaintPilot";
  }
  if (isProjectDetailPath(normalizedPathname)) {
    const projectId = normalizedPathname.slice(PROJECTS_PATH.length + 1);
    return isPaintProjectId(projectId)
      ? "Project Details — PaintPilot"
      : "Project Not Found — PaintPilot";
  }
  return "Page Not Found — PaintPilot";
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
  const location = useLocation();
  const mainRef = useRef<HTMLElement>(null);
  const previousRouteRef = useRef<string | null>(null);
  const [paginationFocusToken, setPaginationFocusToken] = useState(0);
  const normalizedPathname = normalizePathname(location.pathname);
  const projectsIsCurrent =
    normalizedPathname === PROJECTS_PATH ||
    isProjectDetailPath(normalizedPathname);
  const createProjectIsCurrent = normalizedPathname === CREATE_PROJECT_PATH;

  useLayoutEffect(() => {
    document.title = titleForPath(location.pathname);
  }, [location.pathname]);

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
        Skip to main content
      </a>

      <header className="platform-header">
        <div className="platform-header__inner">
          <div className="brand-lockup" aria-label="CreativeDeploy, PaintPilot workspace">
            <span className="brand-lockup__platform">CreativeDeploy</span>
            <span aria-hidden="true" className="brand-lockup__divider" />
            <span className="brand-lockup__product">
              <span aria-hidden="true" className="brand-lockup__mark">
                P
              </span>
              PaintPilot
            </span>
          </div>

          <nav aria-label="PaintPilot navigation" className="shell-nav">
            <Link
              aria-current={projectsIsCurrent ? "page" : undefined}
              className={navigationClassName(projectsIsCurrent)}
              to={PROJECTS_PATH}
            >
              Projects
            </Link>
            <Link
              aria-current={createProjectIsCurrent ? "page" : undefined}
              className={navigationClassName(createProjectIsCurrent)}
              to={CREATE_PROJECT_PATH}
            >
              Create project
            </Link>
          </nav>
        </div>
      </header>

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
        <div>
          <span className="workspace-footer__label">Planning-only workspace</span>
          <span>
            Guidance is not a verified repaint outcome. Access uses one configured demo
            operator, not public authentication.
          </span>
        </div>
      </footer>
    </div>
  );
}
