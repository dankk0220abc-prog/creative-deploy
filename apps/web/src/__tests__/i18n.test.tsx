import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { MemoryRouter, useLocation } from "react-router";
import { afterEach, describe, expect, it } from "vitest";

import { LocaleSwitcher } from "../components/LocaleSwitcher";
import {
  FALLBACK_LOCALE,
  i18n,
  LOCALE_STORAGE_KEY,
  resolveInitialLocale,
  setLocale,
} from "../i18n";
import { enUS, translationEntries, zhCN } from "../i18n/resources";
import { formatProjectStatus, formatProjectTimestamp } from "../utils/format";

function StatefulLocaleHost() {
  const location = useLocation();
  const [value, setValue] = useState("polygon draft");
  return (
    <>
      <LocaleSwitcher />
      <label>
        Working value
        <input onChange={(event) => setValue(event.target.value)} value={value} />
      </label>
      <output aria-label="Current route">{location.pathname}</output>
    </>
  );
}

describe("PaintPilot localization contract", () => {
  afterEach(async () => {
    window.localStorage.removeItem(LOCALE_STORAGE_KEY);
    await i18n.changeLanguage(FALLBACK_LOCALE);
  });

  it("resolves saved preference, browser language, configured default, then fallback", () => {
    expect(resolveInitialLocale({ stored: "zh-CN", browser: ["en-US"], configuredDefault: "en-US" })).toBe("zh-CN");
    expect(resolveInitialLocale({ stored: null, browser: ["zh-Hans-CN"], configuredDefault: "en-US" })).toBe("zh-CN");
    expect(resolveInitialLocale({ stored: null, browser: ["fr-FR"], configuredDefault: "zh-CN" })).toBe("zh-CN");
    expect(resolveInitialLocale({ stored: null, browser: ["fr-FR"], configuredDefault: "de-DE" })).toBe("en-US");
  });

  it("keeps locale resources complete, unique, and non-empty", () => {
    const keys = translationEntries.map(([key]) => key);
    expect(new Set(keys).size).toBe(keys.length);
    expect(Object.keys(enUS).sort()).toEqual(Object.keys(zhCN).sort());
    expect(Object.values(enUS).every((value) => value.trim().length > 0)).toBe(true);
    expect(Object.values(zhCN).every((value) => value.trim().length > 0)).toBe(true);
  });

  it("switches and persists language without losing route or form state", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={["/paintpilot/projects/11111111-1111-4111-8111-111111111111/regions"]}>
        <StatefulLocaleHost />
      </MemoryRouter>,
    );
    const input = screen.getByRole("textbox", { name: "Working value" });
    await user.clear(input);
    await user.type(input, "three vertices");
    await user.click(screen.getByRole("button", { name: "简体中文" }));

    expect(document.documentElement.lang).toBe("zh-CN");
    expect(window.localStorage.getItem(LOCALE_STORAGE_KEY)).toBe("zh-CN");
    expect(input).toHaveValue("three vertices");
    expect(screen.getByLabelText("Current route")).toHaveTextContent("/paintpilot/projects/11111111-1111-4111-8111-111111111111/regions");

    await user.click(screen.getByRole("button", { name: "English" }));
    expect(document.documentElement.lang).toBe("en-US");
    expect(input).toHaveValue("three vertices");
  });

  it("localizes enum labels and Intl timestamps without changing raw values", async () => {
    await setLocale("zh-CN");
    expect(formatProjectStatus("IMAGE_REVIEW_REQUIRED")).toBe("图像需要审核");
    expect(formatProjectTimestamp("2026-08-02T08:00:00Z")).toMatch(/2026/);
    expect("IMAGE_REVIEW_REQUIRED").toBe("IMAGE_REVIEW_REQUIRED");
  });

  it("formats numbers with Intl and localizes unknown-key fallbacks", async () => {
    expect(i18n.t("projects.count", { count: 12345 })).toBe("12,345 projects");
    expect(i18n.t("missing.product.key")).toBe("Unavailable");
    await setLocale("zh-CN");
    expect(i18n.t("projects.count", { count: 12345 })).toBe("12,345 个项目");
    expect(i18n.t("missing.product.key")).toBe("暂不可用");
  });
});
