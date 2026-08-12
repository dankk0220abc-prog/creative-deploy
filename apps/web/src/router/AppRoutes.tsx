import {
  Navigate,
  Outlet,
  Route,
  Routes,
  useLocation,
  useParams,
} from "react-router";

import { useAuth } from "../auth/AuthContext";
import { phase3aFixtureEnabled } from "../api/aiFoundation";
import { phase3bPaintPlanEnabled } from "../api/paintPlans";
import { AppShell } from "../components/AppShell";
import { CreateProjectPage } from "../pages/CreateProjectPage";
import { NotFoundPage } from "../pages/NotFoundPage";
import { LoginPage } from "../pages/LoginPage";
import { ProjectDetailPage } from "../pages/ProjectDetailPage";
import { ProjectsPage } from "../pages/ProjectsPage";
import { RegionWorkspacePage } from "../pages/RegionWorkspacePage";
import { AIProjectPolicyPage } from "../pages/AIProjectPolicyPage";
import { AISettingsPage } from "../pages/AISettingsPage";
import { PaintPlanWorkspacePage } from "../pages/PaintPlanWorkspacePage";
import { ArcanaHistoryPage } from "../pages/ArcanaHistoryPage";
import { ArcanaPage } from "../pages/ArcanaPage";
import { ArcanaReadingPage } from "../pages/ArcanaReadingPage";
import { ArcanaSharePage } from "../pages/ArcanaSharePage";
import { ProductChooserPage } from "../pages/ProductChooserPage";

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

function PaintPlanWorkspaceRoute() {
  const { projectId } = useParams();
  return <PaintPlanWorkspacePage key={projectId ?? "invalid-project"} />;
}

export function AppRoutes() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<ProductChooserPage />} />
        <Route
          element={<Navigate replace to={appRoutes.projects} />}
          path="paintpilot"
        />
        <Route element={<LoginPage />} path="paintpilot/login" />
        <Route element={<RequireAuthentication />}>
          <Route element={<ProjectsPage />} path="paintpilot/projects" />
          <Route element={<ArcanaPage />} path="arcana" />
          <Route element={<ArcanaHistoryPage />} path="arcana/journal" />
          <Route element={<ArcanaReadingPage />} path="arcana/readings/:readingId" />
          <Route element={<ArcanaSharePage />} path="arcana/readings/:readingId/share" />
          <Route element={<CreateProjectPage />} path="paintpilot/projects/new" />
          <Route
            element={<ProjectDetailPage />}
            path="paintpilot/projects/:projectId"
          />
          <Route
            element={<RegionWorkspacePage />}
            path="paintpilot/projects/:projectId/regions"
          />
          {phase3bPaintPlanEnabled ? (
            <Route
              element={<PaintPlanWorkspaceRoute />}
              path="paintpilot/projects/:projectId/paint-plans"
            />
          ) : null}
          {phase3aFixtureEnabled ? (
            <>
              <Route
                element={<Navigate replace to="/paintpilot/settings/ai/models-providers" />}
                path="paintpilot/settings/ai"
              />
              <Route
                element={<AISettingsPage />}
                path="paintpilot/settings/ai/:tab"
              />
              <Route
                element={<AIProjectPolicyPage />}
                path="paintpilot/projects/:projectId/ai-model-policy"
              />
            </>
          ) : null}
        </Route>
        <Route element={<NotFoundPage />} path="*" />
      </Route>
    </Routes>
  );
}
