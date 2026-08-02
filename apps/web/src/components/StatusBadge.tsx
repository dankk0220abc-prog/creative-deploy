import { useAppTranslation } from "../i18n";

export type DisplayStatus = "checking" | "healthy" | "unavailable" | "unknown";

interface StatusBadgeProps {
  label: string;
  status: DisplayStatus;
}

const statusDetails: Record<
  DisplayStatus,
  { labelKey: string; tone: string }
> = {
  checking: {
    labelKey: "health.status.checking",
    tone: "checking",
  },
  healthy: {
    labelKey: "health.status.healthy",
    tone: "healthy",
  },
  unavailable: {
    labelKey: "health.status.unavailable",
    tone: "unavailable",
  },
  unknown: {
    labelKey: "health.status.unknown",
    tone: "unknown",
  },
};

export function StatusBadge({ label, status }: StatusBadgeProps) {
  const { t } = useAppTranslation();
  const details = statusDetails[status];
  const statusLabel = t(details.labelKey);

  return (
    <span
      role="status"
      aria-label={t("health.statusAccessible", { label, status: statusLabel })}
      className={`health-status health-status--${details.tone}`}
    >
      <span aria-hidden="true" className="health-status__dot" />
      {statusLabel}
    </span>
  );
}
