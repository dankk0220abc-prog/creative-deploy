import { useCallback, useEffect, useRef, useState } from "react";

import { fetchReadiness, HealthApiError } from "../api/health";
import { useAppTranslation } from "../i18n";
import { type DisplayStatus, StatusBadge } from "./StatusBadge";

interface DashboardState {
  api: DisplayStatus;
  database: DisplayStatus;
  messageKey: string;
  latencyMs: number | null;
}

function initialState(): DashboardState {
  return {
  api: "checking",
  database: "checking",
  messageKey: "health.checking",
  latencyMs: null,
  };
}

interface HealthCardProps {
  description: string;
  label: string;
  status: DisplayStatus;
}

function HealthCard({ description, label, status }: HealthCardProps) {
  return (
    <article className="health-card">
      <div className="health-card__heading">
        <div>
          <h3>{label}</h3>
          <p>{description}</p>
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
  const { t } = useAppTranslation();
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
            messageKey: "health.databaseUnavailable",
            latencyMs: null,
          });
          return;
        }

        setDashboardState({
          api: "healthy",
          database: "healthy",
          messageKey: "health.healthy",
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

        const messageKey =
          error instanceof HealthApiError && error.kind === "timeout"
            ? "health.timeout"
            : "health.apiUnavailable";

        setDashboardState({
          api: "unavailable",
          database: "unknown",
          messageKey,
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
    startHealthCheck(() => setDashboardState(initialState()));
  };

  return (
    <section aria-labelledby="health-heading" className="health-dashboard">
      <div className="health-dashboard__heading">
        <div>
          <p className="context-label">{t("health.live")}</p>
          <h2 id="health-heading">{t("health.heading")}</h2>
        </div>
        <button
          aria-busy={dashboardState.api === "checking"}
          className="button button--secondary"
          onClick={retry}
          type="button"
        >
          {t("health.retry")}
        </button>
      </div>

      <div className="health-grid">
        <HealthCard
          label={t("health.web")}
          description={t("health.webCopy")}
          status="healthy"
        />
        <HealthCard
          label={t("health.api")}
          description={t("health.apiCopy")}
          status={dashboardState.api}
        />
        <HealthCard
          label={t("health.database")}
          description={t("health.databaseCopy")}
          status={dashboardState.database}
        />
      </div>

      <div
        aria-live="polite"
        className="health-summary"
      >
        <p>{t(dashboardState.messageKey)}</p>
        {dashboardState.latencyMs === null ? null : (
          <p className="health-summary__latency">
            {t("health.latency", { value: dashboardState.latencyMs.toFixed(2) })}
          </p>
        )}
      </div>
    </section>
  );
}
