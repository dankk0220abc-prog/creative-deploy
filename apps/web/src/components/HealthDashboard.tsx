import { useCallback, useEffect, useRef, useState } from "react";

import { fetchReadiness, HealthApiError } from "../api/health";
import { type DisplayStatus, StatusBadge } from "./StatusBadge";

interface DashboardState {
  api: DisplayStatus;
  database: DisplayStatus;
  message: string;
  latencyMs: number | null;
}

const initialState: DashboardState = {
  api: "checking",
  database: "checking",
  message: "Checking the API and PostgreSQL connection.",
  latencyMs: null,
};

interface HealthCardProps {
  description: string;
  label: string;
  status: DisplayStatus;
}

function HealthCard({ description, label, status }: HealthCardProps) {
  return (
    <article className="rounded-2xl border border-white/10 bg-white/[0.035] p-5 shadow-2xl shadow-black/10 backdrop-blur-sm sm:p-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-base font-semibold text-slate-100">{label}</h2>
          <p className="mt-2 text-sm leading-6 text-slate-400">{description}</p>
        </div>
        <StatusBadge label={label} status={status} />
      </div>
    </article>
  );
}

interface HealthDashboardProps {
  readinessFetcher?: typeof fetchReadiness;
}

export function HealthDashboard({
  readinessFetcher = fetchReadiness,
}: HealthDashboardProps = {}) {
  const [dashboardState, setDashboardState] = useState<DashboardState>(initialState);
  const controllerRef = useRef<AbortController | null>(null);
  const mountedRef = useRef(false);
  const requestGenerationRef = useRef(0);

  const startHealthCheck = useCallback((onRequestStarted?: () => void) => {
    controllerRef.current?.abort();
    const requestId = requestGenerationRef.current + 1;
    requestGenerationRef.current = requestId;
    const controller = new AbortController();
    controllerRef.current = controller;
    onRequestStarted?.();

    const isCurrentRequest = () =>
      mountedRef.current &&
      requestGenerationRef.current === requestId &&
      controllerRef.current === controller &&
      !controller.signal.aborted;

    void readinessFetcher(controller.signal)
      .then((result) => {
        if (!isCurrentRequest()) {
          return;
        }

        if (result.httpStatus === 503 || result.data.checks.database.status === "error") {
          setDashboardState({
            api: "healthy",
            database: "unavailable",
            message:
              "FastAPI is responding, but PostgreSQL is unavailable. Retry after the database recovers.",
            latencyMs: null,
          });
          return;
        }

        setDashboardState({
          api: "healthy",
          database: "healthy",
          message: "The browser, FastAPI, and PostgreSQL readiness path is healthy.",
          latencyMs: result.data.checks.database.latency_ms,
        });
      })
      .catch((error: unknown) => {
        if (
          !isCurrentRequest() ||
          (error instanceof HealthApiError && error.kind === "caller_aborted")
        ) {
          return;
        }

        const message =
          error instanceof HealthApiError && error.kind === "timeout"
            ? "The FastAPI health request timed out. Check the API process and retry."
            : "FastAPI could not be reached or returned invalid health data.";

        setDashboardState({
          api: "unavailable",
          database: "unknown",
          message,
          latencyMs: null,
        });
      })
      .finally(() => {
        if (
          requestGenerationRef.current === requestId &&
          controllerRef.current === controller
        ) {
          controllerRef.current = null;
        }
      });
  }, [readinessFetcher]);

  useEffect(() => {
    mountedRef.current = true;
    startHealthCheck();

    return () => {
      mountedRef.current = false;
      requestGenerationRef.current += 1;
      controllerRef.current?.abort();
      controllerRef.current = null;
    };
  }, [startHealthCheck]);

  const retry = () => {
    startHealthCheck(() => setDashboardState(initialState));
  };

  return (
    <section aria-labelledby="health-heading">
      <div className="mb-5 flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div>
          <p className="text-xs font-semibold tracking-[0.18em] text-slate-500 uppercase">
            Live environment
          </p>
          <h2 id="health-heading" className="mt-2 text-2xl font-semibold text-white">
            Service health
          </h2>
        </div>
        <button
          type="button"
          onClick={retry}
          className="inline-flex min-h-10 items-center justify-center rounded-xl border border-white/12 bg-white/6 px-4 py-2 text-sm font-semibold text-slate-200 transition-colors hover:border-teal-300/30 hover:bg-teal-300/10 hover:text-teal-100"
        >
          Retry check
        </button>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <HealthCard
          label="Web Application"
          description="The Vite-powered React interface is rendering in this browser."
          status="healthy"
        />
        <HealthCard
          label="FastAPI Service"
          description="The local API must respond through the Vite development proxy."
          status={dashboardState.api}
        />
        <HealthCard
          label="PostgreSQL Database"
          description="FastAPI performs a timed SELECT 1 readiness query."
          status={dashboardState.database}
        />
      </div>

      <div
        aria-live="polite"
        className="mt-5 flex min-h-20 flex-col justify-center rounded-2xl border border-white/8 bg-slate-950/45 px-5 py-4 text-sm leading-6 text-slate-300 sm:flex-row sm:items-center sm:justify-between sm:gap-4"
      >
        <p>{dashboardState.message}</p>
        {dashboardState.latencyMs === null ? null : (
          <p className="mt-2 shrink-0 font-mono text-xs text-teal-200 sm:mt-0">
            DB latency {dashboardState.latencyMs.toFixed(2)} ms
          </p>
        )}
      </div>
    </section>
  );
}
