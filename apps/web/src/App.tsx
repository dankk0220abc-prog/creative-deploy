import { BrowserRouter } from "react-router";

import { AuthProvider } from "./auth/AuthContext";
import { AppErrorBoundary } from "./components/AppErrorBoundary";
import { AppRoutes } from "./router/AppRoutes";

export function App() {
  return (
    <BrowserRouter>
      <AppErrorBoundary>
        <AuthProvider>
          <AppRoutes />
        </AuthProvider>
      </AppErrorBoundary>
    </BrowserRouter>
  );
}
