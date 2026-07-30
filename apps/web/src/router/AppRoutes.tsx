import { Navigate, Route, Routes } from "react-router";

import { AppShell } from "../components/AppShell";
import { CreateProjectPage } from "../pages/CreateProjectPage";
import { NotFoundPage } from "../pages/NotFoundPage";
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

export function AppRoutes() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<Navigate replace to={appRoutes.projects} />} />
        <Route
          element={<Navigate replace to={appRoutes.projects} />}
          path="paintpilot"
        />
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
        <Route element={<NotFoundPage />} path="*" />
      </Route>
    </Routes>
  );
}
