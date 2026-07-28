import { BrowserRouter } from "react-router";

import { AppErrorBoundary } from "./components/AppErrorBoundary";
import { AppRoutes } from "./router/AppRoutes";

export function App() {
  return (
    <BrowserRouter>
      <AppErrorBoundary>
        <AppRoutes />
      </AppErrorBoundary>
    </BrowserRouter>
  );
}
