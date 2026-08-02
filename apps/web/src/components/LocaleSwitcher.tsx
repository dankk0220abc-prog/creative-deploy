import { currentLocale, setLocale, useAppTranslation } from "../i18n";

export function LocaleSwitcher() {
  const { t } = useAppTranslation();
  const locale = currentLocale();
  const currentLanguage = locale === "zh-CN" ? t("locale.chinese") : t("locale.english");

  return (
    <div aria-label={t("locale.current", { language: currentLanguage })} className="locale-switcher" role="group">
      <span className="locale-switcher__label">{t("locale.switcherLabel")}</span>
      <button aria-pressed={locale === "zh-CN"} className="locale-switcher__option" onClick={() => void setLocale("zh-CN")} type="button">
        {t("locale.chinese")}
      </button>
      <button aria-pressed={locale === "en-US"} className="locale-switcher__option" onClick={() => void setLocale("en-US")} type="button">
        {t("locale.english")}
      </button>
    </div>
  );
}
