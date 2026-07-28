import { Component, type ReactNode } from "react";

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
          <p className="eyebrow">PaintPilot</p>
          <h1>The workspace could not be displayed</h1>
          <p>
            Your project data was not changed. Reload the workspace to try again.
          </p>
          <a className="button button--primary" href="/paintpilot/projects">
            Reload Projects
          </a>
        </div>
      </main>
    );
  }
}
