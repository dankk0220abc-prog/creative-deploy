import type { WorkflowStatus } from "../api/paintProjects";
import { currentLocale, i18n, type SupportedLocale } from "../i18n";

function parseTimestamp(value: string): number | null {
  const timestamp = Date.parse(value);
  return Number.isFinite(timestamp) ? timestamp : null;
}

export function codePointLength(value: string): number {
  return Array.from(value).length;
}

export function formatProjectStatus(status: WorkflowStatus): string {
  return i18n.t(`status.${status}`);
}

export function formatProjectTimestamp(value: string, locale = currentLocale()): string {
  const timestamp = parseTimestamp(value);
  if (timestamp === null) {
    return i18n.t("common.unknownUpdateTime");
  }

  return new Intl.DateTimeFormat(locale, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(timestamp);
}

export function formatProjectAccessibleTimestamp(
  value: string,
  locale: SupportedLocale = currentLocale(),
): string {
  const timestamp = parseTimestamp(value);
  if (timestamp === null) {
    return i18n.t("common.unknownUpdateTime");
  }

  return new Intl.DateTimeFormat(locale, {
    dateStyle: "long",
    timeStyle: "long",
    timeZone: "UTC",
  }).format(timestamp);
}

export function formatProjectRelativeTime(
  value: string,
  nowMilliseconds = Date.now(),
  locale: SupportedLocale = currentLocale(),
): string {
  const timestamp = parseTimestamp(value);
  if (timestamp === null || !Number.isFinite(nowMilliseconds)) {
    return i18n.t("common.unknownUpdateTime");
  }

  const secondsFromNow = (timestamp - nowMilliseconds) / 1_000;
  const absoluteSeconds = Math.abs(secondsFromNow);

  if (absoluteSeconds < 60) {
    return secondsFromNow <= 0
      ? i18n.t("relative.justNow")
      : i18n.t("relative.lessThanMinute");
  }

  let divisor: number;
  let unit: Intl.RelativeTimeFormatUnit;
  if (absoluteSeconds < 60 * 60) {
    divisor = 60;
    unit = "minute";
  } else if (absoluteSeconds < 24 * 60 * 60) {
    divisor = 60 * 60;
    unit = "hour";
  } else {
    divisor = 24 * 60 * 60;
    unit = "day";
  }

  return new Intl.RelativeTimeFormat(locale, { numeric: "always" }).format(
    Math.round(secondsFromNow / divisor),
    unit,
  );
}

export function toProjectISOString(value: string): string | null {
  const timestamp = parseTimestamp(value);
  return timestamp === null ? null : new Date(timestamp).toISOString();
}

export function summarizeDescription(
  description: string | null,
  maximumCodePoints = 140,
): string {
  if (description === null) {
    return i18n.t("common.noDescription");
  }

  const codePoints = Array.from(description);
  if (codePoints.length <= maximumCodePoints) {
    return description;
  }
  return `${codePoints.slice(0, maximumCodePoints - 1).join("")}…`;
}
