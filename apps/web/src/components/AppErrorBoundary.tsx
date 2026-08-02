import { Component, type ReactNode } from "react";
import { i18n } from "../i18n";

interface AppErrorBoundaryProps {
  children: ReactNode;
}

interface AppErrorBoundaryState {
  hasError: boolean;
}

export class AppErrorBoundary extends Component<
  AppErrorBoundaryProps,
  AppErrorBoundaryState
> {
  state: AppErrorBoundaryState = { hasError: false };

  static getDerivedStateFromError(): AppErrorBoundaryState {
    return { hasError: true };
  }

  componentDidCatch() {
    console.error("PaintPilot interface render failure.");
  }

  render() {
    if (!this.state.hasError) {
      return this.props.children;
    }

    return (
      <main className="app-fallback">
        <div className="app-fallback__panel" role="alert">
          <p className="context-label">PaintPilot</p>
          <h1>{i18n.t("errorBoundary.heading")}</h1>
          <p>{i18n.t("errorBoundary.copy")}</p>
          <a className="button button--primary" href="/paintpilot/projects">
            {i18n.t("errorBoundary.action")}
          </a>
        </div>
      </main>
    );
  }
}
