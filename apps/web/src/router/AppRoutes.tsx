import { Navigate, Route, Routes } from "react-router";

import { AppShell } from "../components/AppShell";
import { CreateProjectPage } from "../pages/CreateProjectPage";
import { NotFoundPage } from "../pages/NotFoundPage";
import { ProjectDetailPage } from "../pages/ProjectDetailPage";
import { ProjectsPage } from "../pages/ProjectsPage";

const appRoutes = {
  createProject: "/paintpilot/projects/new",
  paintPilotEntry: "/paintpilot",
  projectDetail: "/paintpilot/projects/:projectId",
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
        <Route element={<NotFoundPage />} path="*" />
      </Route>
    </Routes>
  );
}
