import i18n from "i18next";
import { initReactI18next, useTranslation } from "react-i18next";

import { enUS, zhCN } from "./resources";

export const SUPPORTED_LOCALES = ["en-US", "zh-CN"] as const;
export type SupportedLocale = (typeof SUPPORTED_LOCALES)[number];
export const LOCALE_STORAGE_KEY = "creativedeploy.locale";
export const FALLBACK_LOCALE: SupportedLocale = "en-US";

function normalizeLocale(value: string | null | undefined): SupportedLocale | null {
  if (value === null || value === undefined) return null;
  const normalized = value.trim().toLowerCase();
  if (normalized === "en" || normalized.startsWith("en-")) return "en-US";
  if (normalized === "zh" || normalized.startsWith("zh-cn") || normalized.startsWith("zh-hans")) {
    return "zh-CN";
  }
  return null;
}

function readStoredLocale(): SupportedLocale | null {
  try {
    return normalizeLocale(window.localStorage.getItem(LOCALE_STORAGE_KEY));
  } catch {
    return null;
  }
}

function browserLocales(): readonly string[] {
  if (typeof navigator === "undefined") return [];
  return navigator.languages.length > 0 ? navigator.languages : [navigator.language];
}

export function resolveInitialLocale(options?: {
  stored?: string | null;
  browser?: readonly string[];
  configuredDefault?: string | null;
}): SupportedLocale {
  const stored = options && "stored" in options
    ? normalizeLocale(options.stored)
    : typeof window === "undefined" ? null : readStoredLocale();
  if (stored !== null) return stored;
  for (const candidate of options?.browser ?? browserLocales()) {
    const locale = normalizeLocale(candidate);
    if (locale !== null) return locale;
  }
  return normalizeLocale(options?.configuredDefault ?? import.meta.env.VITE_DEFAULT_LOCALE) ?? FALLBACK_LOCALE;
}

const initialLocale = resolveInitialLocale();
void i18n.use(initReactI18next).init({
  fallbackLng: FALLBACK_LOCALE,
  initImmediate: false,
  interpolation: { escapeValue: false },
  keySeparator: false,
  lng: initialLocale,
  parseMissingKeyHandler: () =>
    i18n.language?.toLowerCase().startsWith("zh") ? "暂不可用" : "Unavailable",
  resources: { "en-US": { translation: enUS }, "zh-CN": { translation: zhCN } },
  returnEmptyString: false,
  showSupportNotice: false,
  supportedLngs: [...SUPPORTED_LOCALES],
});

function syncDocumentLanguage(locale: string): void {
  if (typeof document !== "undefined") {
    document.documentElement.lang = normalizeLocale(locale) ?? FALLBACK_LOCALE;
  }
}
syncDocumentLanguage(i18n.resolvedLanguage ?? initialLocale);
i18n.on("languageChanged", syncDocumentLanguage);

export async function setLocale(locale: SupportedLocale): Promise<void> {
  try {
    window.localStorage.setItem(LOCALE_STORAGE_KEY, locale);
  } catch {
    // Persistence is optional; the in-memory language switch still succeeds.
  }
  await i18n.changeLanguage(locale);
}

export function currentLocale(): SupportedLocale {
  return normalizeLocale(i18n.resolvedLanguage ?? i18n.language) ?? FALLBACK_LOCALE;
}

export { i18n, useTranslation as useAppTranslation };
