import { HealthDashboard } from "./components/HealthDashboard";

export function App() {
  return (
    <main className="relative min-h-screen overflow-hidden px-5 py-10 text-slate-100 sm:px-8 sm:py-16">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-0 top-0 h-96 bg-[radial-gradient(circle_at_top_left,rgba(45,212,191,0.16),transparent_45%),radial-gradient(circle_at_top_right,rgba(96,165,250,0.14),transparent_42%)]"
      />

      <div className="relative mx-auto max-w-6xl">
        <header className="mb-10 max-w-3xl sm:mb-14">
          <div className="mb-5 inline-flex items-center gap-2 rounded-full border border-teal-300/20 bg-teal-300/8 px-3 py-1.5 text-xs font-semibold tracking-[0.16em] text-teal-200 uppercase">
            <span className="h-1.5 w-1.5 rounded-full bg-teal-300" />
            Foundation connectivity
          </div>
          <h1 className="text-4xl font-semibold tracking-[-0.04em] text-white sm:text-6xl">
            CreativeDeploy
          </h1>
          <p className="mt-4 text-lg text-slate-300 sm:text-xl">
            PaintPilot · Phase 1B Foundation
          </p>
          <p className="mt-5 max-w-2xl text-sm leading-7 text-slate-400 sm:text-base">
            A minimal end-to-end signal across the browser, FastAPI, and PostgreSQL.
            This page reports infrastructure readiness without implying product capability.
          </p>
        </header>

        <HealthDashboard />

        <footer className="mt-8 border-t border-white/8 pt-6 text-sm leading-6 text-slate-500">
          Foundation connectivity check only. PaintPilot features are not implemented yet.
        </footer>
      </div>
    </main>
  );
}
