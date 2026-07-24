export type DisplayStatus = "checking" | "healthy" | "unavailable" | "unknown";

interface StatusBadgeProps {
  label: string;
  status: DisplayStatus;
}

const statusDetails: Record<
  DisplayStatus,
  { label: string; badgeClassName: string; dotClassName: string }
> = {
  checking: {
    label: "Checking",
    badgeClassName: "border-amber-300/20 bg-amber-300/10 text-amber-200",
    dotClassName: "bg-amber-300",
  },
  healthy: {
    label: "Healthy",
    badgeClassName: "border-emerald-300/20 bg-emerald-300/10 text-emerald-200",
    dotClassName: "bg-emerald-300",
  },
  unavailable: {
    label: "Unavailable",
    badgeClassName: "border-rose-300/20 bg-rose-300/10 text-rose-200",
    dotClassName: "bg-rose-300",
  },
  unknown: {
    label: "Unknown",
    badgeClassName: "border-slate-300/15 bg-slate-300/8 text-slate-300",
    dotClassName: "bg-slate-400",
  },
};

export function StatusBadge({ label, status }: StatusBadgeProps) {
  const details = statusDetails[status];

  return (
    <span
      role="status"
      aria-label={`${label} status: ${details.label}`}
      className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-semibold ${details.badgeClassName}`}
    >
      <span aria-hidden="true" className={`h-1.5 w-1.5 rounded-full ${details.dotClassName}`} />
      {details.label}
    </span>
  );
}
