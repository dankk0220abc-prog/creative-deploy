import { Navigate, Outlet, Route, Routes, useLocation } from "react-router";

import { useAuth } from "../auth/AuthContext";
import { AppShell } from "../components/AppShell";
import { CreateProjectPage } from "../pages/CreateProjectPage";
import { NotFoundPage } from "../pages/NotFoundPage";
import { LoginPage } from "../pages/LoginPage";
import { ProjectDetailPage } from "../pages/ProjectDetailPage";
import { ProjectsPage } from "../pages/ProjectsPage";
import { RegionWorkspacePage } from "../pages/RegionWorkspacePage";

const appRoutes = {
  createProject: "/paintpilot/projects/new",
  paintPilotEntry: "/paintpilot",
  projectDetail: "/paintpilot/projects/:projectId",
  projectRegions: "/paintpilot/projects/:projectId/regions",
  projects: "/paintpilot/projects",
  root: "/",
} as const;

function RequireAuthentication() {
  const { state } = useAuth();
  const location = useLocation();
  if (state.status === "loading") {
    return <LoginPage />;
  }
  if (state.status !== "authenticated") {
    const returnTo = `${location.pathname}${location.search}`;
    return (
      <Navigate
        replace
        to={`/paintpilot/login?${new URLSearchParams({ return_to: returnTo })}`}
      />
    );
  }
  return <Outlet />;
}

export function AppRoutes() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<Navigate replace to={appRoutes.projects} />} />
        <Route
          element={<Navigate replace to={appRoutes.projects} />}
          path="paintpilot"
        />
        <Route element={<LoginPage />} path="paintpilot/login" />
        <Route element={<RequireAuthentication />}>
          <Route element={<ProjectsPage />} path="paintpilot/projects" />
          <Route element={<CreateProjectPage />} path="paintpilot/projects/new" />
          <Route
            element={<ProjectDetailPage />}
            path="paintpilot/projects/:projectId"
          />
          <Route
            element={<RegionWorkspacePage />}
            path="paintpilot/projects/:projectId/regions"
          />
        </Route>
        <Route element={<NotFoundPage />} path="*" />
      </Route>
    </Routes>
  );
}
