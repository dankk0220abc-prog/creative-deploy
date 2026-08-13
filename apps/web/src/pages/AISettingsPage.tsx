import { type FormEvent, useEffect, useMemo, useState } from "react";
import { Link, Navigate, useParams, useSearchParams } from "react-router";

import {
  AIFoundationApiError,
  createCredential,
  getUserPreference,
  grantCredential,
  isZhipuCredentialInputWellFormed,
  listAudit,
  listCapabilities,
  listCredentials,
  listModels,
  listProviders,
  phase3aFixtureEnabled,
  replaceCredential,
  revokeCredential,
  updateUserPreference,
  validateSavedCredential,
  validateTemporaryCredential,
  type AuditEvent,
  type CapabilityDefinition,
  type CredentialRecord,
  type ModelDefinition,
  type ProviderKey,
  type ProviderDefinition,
  type UserPreference,
} from "../api/aiFoundation";
import { FeedbackPanel } from "../components/FeedbackPanel";
import { useAppTranslation } from "../i18n";

type SettingsTab = "credentials" | "models" | "usage";

interface FoundationData {
  capabilities: CapabilityDefinition[];
  credentials: CredentialRecord[];
  models: ModelDefinition[];
  preference: UserPreference;
  providers: ProviderDefinition[];
}

const tabPaths: Record<SettingsTab, string> = {
  models: "/paintpilot/settings/ai/models-providers",
  credentials: "/paintpilot/settings/ai/credentials",
  usage: "/paintpilot/settings/ai/usage-audit",
};

function asSettingsError(error: unknown): AIFoundationApiError {
  return error instanceof AIFoundationApiError
    ? error
    : new AIFoundationApiError("fixture_foundation_request_failed");
}

function SettingsTabs({ active }: { active: SettingsTab }) {
  const { t } = useAppTranslation();
  return (
    <nav aria-label={t("ai.tabsLabel")} className="ai-tabs">
      {(["models", "credentials", "usage"] as const).map((tab) => (
        <Link
          aria-current={active === tab ? "page" : undefined}
          className={active === tab ? "ai-tabs__link ai-tabs__link--active" : "ai-tabs__link"}
          key={tab}
          to={tabPaths[tab]}
        >
          {t(`ai.tab.${tab}`)}
        </Link>
      ))}
    </nav>
  );
}

function ProviderBoundary() {
  const { t } = useAppTranslation();
  return (
    <details className="ai-boundary" role="note">
      <summary>
        <span className="ai-boundary__signal" aria-hidden="true" />
        <strong>{t("ai.providerBoundary")}</strong>
        <span className="ai-boundary__learn">{t("ai.learnDetails")}</span>
      </summary>
      <div className="ai-boundary__details">
        <p>{t("ai.providerBoundaryCopy")}</p>
        <dl>
          <div><dt>Fixture</dt><dd>{t("ai.fixtureDefault")}</dd></div>
          <div><dt>Zhipu</dt><dd>{t("ai.liveGateOff")}</dd></div>
          <div><dt>BYOK</dt><dd>{t("ai.encryptedAtRest")}</dd></div>
          <div><dt>Live cap</dt><dd>1.00 CNY</dd></div>
        </dl>
      </div>
    </details>
  );
}

function SetupPath({ active }: { active?: SettingsTab }) {
  const { t } = useAppTranslation();
  const steps = [
    { key: "credentials", to: tabPaths.credentials },
    { key: "models", to: tabPaths.models },
    { key: "project", to: "/paintpilot/projects" },
    { key: "usage", to: tabPaths.usage },
  ] as const;
  return (
    <nav aria-label={t("ai.flowLabel")} className="ai-setup-path">
      {steps.map((step, index) => (
        <Link
          aria-current={active === step.key ? "step" : undefined}
          className={active === step.key ? "ai-setup-path__link ai-setup-path__link--active" : "ai-setup-path__link"}
          key={step.key}
          to={step.to}
        >
          <span>{index + 1}</span>{t(`ai.flow.${step.key}`)}
        </Link>
      ))}
    </nav>
  );
}

function displayStatus(t: (key: string) => string, value: string | null | undefined): string {
  switch (value) {
    case "active": return t("ai.status.active");
    case "revoked": return t("ai.status.revoked");
    case "replaced": return t("ai.status.replaced");
    case "ready": return t("ai.status.ready");
    case "succeeded": return t("ai.status.succeeded");
    case "failed": return t("ai.status.failed");
    case "running": return t("ai.status.running");
    case "pending": return t("ai.status.pending");
    case "cancelled": return t("ai.status.cancelled");
    case "outcome_unknown": return t("ai.status.outcomeUnknown");
    default: return t("ai.status.notConfigured");
  }
}

function activityLabel(t: (key: string) => string, action: string): string {
  if (action.startsWith("invocation")) return t("ai.activity.localTest");
  if (action.startsWith("credential")) return t("ai.activity.credential");
  if (action.includes("policy")) return t("ai.activity.policy");
  return t("ai.activity.updated");
}

function valueFromMetadata(metadata: Record<string, unknown>, key: string): string | null {
  const value = metadata[key];
  return typeof value === "string" || typeof value === "number" ? String(value) : null;
}

function ModelsPanel({ data, onReload }: { data: FoundationData; onReload: () => void }) {
  const { t } = useAppTranslation();
  const initialProviderId = data.preference.default_provider_definition_id
    ?? data.providers.find((item) => item.provider_key === "fixture_local")?.id
    ?? data.providers[0]?.id
    ?? "";
  const [providerId, setProviderId] = useState(initialProviderId);
  const provider = data.providers.find((item) => item.id === providerId);
  const providerModels = data.models.filter((item) => item.provider_key === provider?.provider_key);
  const activeCredentials = data.credentials.filter(
    (item) => item.status === "active" && item.provider_key === provider?.provider_key,
  );
  const [modelId, setModelId] = useState(
    data.preference.default_model_definition_id
      ?? data.models.find((item) => item.provider_key === "fixture_local")?.id
      ?? "",
  );
  const preferredCredentialIsActive = activeCredentials.some(
    (item) => item.id === data.preference.default_credential_id,
  );
  const [credentialId, setCredentialId] = useState(
    preferredCredentialIsActive
      ? (data.preference.default_credential_id ?? "")
      : (activeCredentials[0]?.id ?? ""),
  );
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState<"conflict" | "error" | "saved" | null>(null);

  const chooseProvider = (nextProviderId: string) => {
    const nextProvider = data.providers.find((item) => item.id === nextProviderId);
    setProviderId(nextProviderId);
    setModelId(data.models.find((item) => item.provider_key === nextProvider?.provider_key)?.id ?? "");
    setCredentialId(
      data.credentials.find(
        (item) => item.status === "active" && item.provider_key === nextProvider?.provider_key,
      )?.id ?? "",
    );
    setNotice(null);
  };

  const savePreference = async (event: FormEvent) => {
    event.preventDefault();
    if (provider === undefined || modelId === "" || credentialId === "") {
      setNotice("error");
      return;
    }
    setSaving(true);
    setNotice(null);
    try {
      const model = providerModels.find((item) => item.id === modelId);
      if (model?.pricing_currency === null || model?.pricing_currency === undefined) {
        setNotice("error");
        return;
      }
      await updateUserPreference({ enabled: true, providerId: provider.id, modelId, credentialId, currency: model.pricing_currency, expectedRevision: data.preference.revision });
      setNotice("saved");
      onReload();
    } catch (error: unknown) {
      setNotice(asSettingsError(error).status === 409 ? "conflict" : "error");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="ai-settings-stack">
      <section aria-labelledby="available-models-heading" className="ai-panel ai-panel--registry">
        <div className="ai-panel__heading"><h2 id="available-models-heading">{t("ai.availableModels")}</h2></div>
        <div className="ai-model-list">
          {data.models.map((model) => (
            <article className="ai-model-row" key={model.id}>
              <div><h3>{model.display_name}</h3><p>{model.capabilities.some((item) => item.capability_key === "vision_understanding") ? t("ai.modelVisionCopy") : t("ai.modelTextCopy")}</p></div>
              <span className={model.local_only ? "ai-status ai-status--ready" : "ai-status"}>{model.local_only ? t("ai.simulated") : t("ai.liveGated")}</span>
              <details className="ai-disclosure"><summary>{t("ai.technicalDetails")}</summary><dl><div><dt>Provider</dt><dd>{model.provider_key}</dd></div><div><dt>Model ID</dt><dd>{model.model_id}</dd></div><div><dt>Capabilities</dt><dd>{model.capabilities.map((item) => item.capability_key).join(", ")}</dd></div></dl></details>
            </article>
          ))}
        </div>
      </section>

      <div className="ai-settings-grid ai-settings-grid--balanced">
        <section aria-labelledby="default-routing-heading" className="ai-panel ai-panel--control">
          <div className="ai-panel__heading"><h2 id="default-routing-heading">{t("ai.defaultSettings")}</h2><span className={data.preference.enabled ? "ai-status ai-status--ready" : "ai-status"}>{data.preference.enabled ? t("ai.enabled") : t("ai.status.notConfigured")}</span></div>
          <p className="ai-panel__copy">{t("ai.defaultSettingsCopy")}</p>
          <form className="ai-form" onSubmit={(event) => void savePreference(event)}>
              <label><span>{t("ai.defaultProvider")}</span><select onChange={(event) => chooseProvider(event.target.value)} value={providerId}>{data.providers.map((item) => <option disabled={!item.enabled || !data.models.some((model) => model.provider_key === item.provider_key && model.status === "active")} key={item.id} value={item.id}>{item.display_name}</option>)}</select></label>
              <label><span>{t("ai.defaultModel")}</span><select disabled={providerModels.length === 0} onChange={(event) => setModelId(event.target.value)} value={modelId}>{providerModels.map((model) => <option key={model.id} value={model.id}>{model.display_name}</option>)}</select></label>
          {activeCredentials.length === 0 ? <div className="ai-empty-action ai-empty-action--embedded"><p>{t("ai.noProviderCredential")}</p><Link className="button button--primary" to={tabPaths.credentials}>{t("ai.addCredential")}</Link></div> : (
              <>
              <label><span>{t("ai.defaultCredential")}</span><select onChange={(event) => setCredentialId(event.target.value)} value={credentialId}>{activeCredentials.map((credential) => <option key={credential.id} value={credential.id}>{credential.alias} · ••••{credential.last_four}</option>)}</select></label>
              {notice === "saved" ? <p className="ai-form__notice ai-form__notice--success" role="status">{t("ai.preferenceSaved")}</p> : null}
              {notice === "error" ? <p className="ai-form__notice" role="alert">{t("ai.saveFailed")}</p> : null}
              {notice === "conflict" ? <p className="ai-form__notice" role="alert">{t("ai.saveConflict")}</p> : null}
              <button className="button button--primary" disabled={saving} type="submit">{saving ? t("ai.saving") : t("ai.savePreference")}</button>
              </>
          )}
            </form>
        </section>
        <section aria-labelledby="test-credits-heading" className="ai-panel ai-panel--quiet"><div className="ai-panel__heading"><h2 id="test-credits-heading">{provider?.provider_key === "zhipu" ? t("ai.liveBudget") : t("ai.testCredits")}</h2></div><div className="ai-limit-list">{provider?.provider_key === "zhipu" ? <><strong>{t("ai.liveHardCap")}</strong><strong>{t("ai.noAutomaticRetry")}</strong><p>{t("ai.liveBudgetCopy")}</p></> : <><strong>{t("ai.perCallLimit")}</strong><strong>{t("ai.dailyLimit")}</strong><p>{t("ai.localCreditCopy")}</p></>}</div></section>
      </div>
    </div>
  );
}

function CredentialsPanel({ credentials, providers, onReload }: { credentials: CredentialRecord[]; providers: ProviderDefinition[]; onReload: () => void }) {
  const { t } = useAppTranslation();
  const [searchParams] = useSearchParams();
  const scopedProjectId = searchParams.get("project")?.match(/^[0-9a-f-]{36}$/i)?.[0] ?? "";
  const [alias, setAlias] = useState("");
  const [providerKey, setProviderKey] = useState<ProviderKey>("fixture_local");
  const [secret, setSecret] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const [validated, setValidated] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [projectIds, setProjectIds] = useState<Record<string, string>>({});
  const [replacementFor, setReplacementFor] = useState<string | null>(null);
  const [replacementAlias, setReplacementAlias] = useState("");
  const [replacementSecret, setReplacementSecret] = useState("");
  const [replacementConfirmed, setReplacementConfirmed] = useState(false);

  const validate = async () => {
    if (!isZhipuCredentialInputWellFormed(providerKey, secret)) {
      setValidated(false);
      setNotice("zhipuFormat");
      return;
    }
    setBusy("validate");
    setNotice(null);
    try {
      const result = await validateTemporaryCredential(providerKey, secret);
      setValidated(result.valid);
      setNotice(result.valid ? (result.validation_status === "live_validation_not_authorized" ? "acceptedPending" : "valid") : "invalid");
    } catch {
      setValidated(false);
      setSecret("");
      setNotice("error");
    } finally {
      setBusy(null);
    }
  };

  const save = async (event: FormEvent) => {
    event.preventDefault();
    if (!isZhipuCredentialInputWellFormed(providerKey, secret)) {
      setValidated(false);
      setNotice("zhipuFormat");
      return;
    }
    if (!validated || !confirmed || alias.trim() === "" || secret === "") {
      setNotice("confirm");
      return;
    }
    setBusy("save");
    try {
      await createCredential(providerKey, alias.trim(), secret);
      setAlias("");
      setSecret("");
      setConfirmed(false);
      setValidated(false);
      setNotice("saved");
      onReload();
    } catch {
      setSecret("");
      setValidated(false);
      setNotice("error");
    } finally {
      setBusy(null);
    }
  };

  const runCredentialAction = async (key: string, action: () => Promise<unknown>) => {
    setBusy(key);
    setNotice(null);
    try {
      await action();
      setNotice("actionSaved");
      onReload();
    } catch {
      if (key.startsWith("replace-")) setReplacementSecret("");
      setNotice("error");
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="ai-settings-grid ai-settings-grid--credentials">
      <section aria-labelledby="credential-vault-heading" className="ai-panel ai-panel--control">
        <div className="ai-panel__heading"><h2 id="credential-vault-heading">{t("ai.addCredential")}</h2></div>
        <p className="ai-panel__copy">{t("ai.credentialSaveCopy")}</p>
        <form className="ai-form" onSubmit={(event) => void save(event)}>
          <label><span>{t("ai.provider")}</span><select onChange={(event) => { setProviderKey(event.target.value as ProviderKey); setSecret(""); setValidated(false); setNotice(null); }} value={providerKey}>{providers.filter((item) => item.provider_key === "fixture_local" || item.provider_key === "zhipu").map((item) => <option key={item.id} value={item.provider_key}>{item.display_name}</option>)}</select></label>
          <label><span>{t("ai.credentialName")}</span><input autoComplete="off" maxLength={120} onChange={(event) => setAlias(event.target.value)} value={alias} /></label>
          <label><span>{t("ai.accessKey")}</span><input autoComplete="new-password" onChange={(event) => { setSecret(event.target.value); setValidated(false); }} placeholder={providerKey === "zhipu" ? "Zhipu API key" : "fixture-sk-…"} type="password" value={secret} /></label>
          <div className="ai-form__actions">
            <button className="button button--secondary" disabled={busy !== null || secret.length < 20} onClick={() => void validate()} type="button">{busy === "validate" ? t("ai.validating") : t("ai.validateCredential")}</button>
            <label className="ai-confirm"><input checked={confirmed} onChange={(event) => setConfirmed(event.target.checked)} type="checkbox" /><span>{t("ai.confirmEncryptedSave")}</span></label>
          </div>
          {notice !== null ? <p className={notice === "valid" || notice === "acceptedPending" || notice === "saved" || notice === "actionSaved" ? "ai-form__notice ai-form__notice--success" : "ai-form__notice"} role={notice === "valid" || notice === "acceptedPending" || notice === "saved" || notice === "actionSaved" ? "status" : "alert"}>{t(`ai.notice.${notice}`)}</p> : null}
          <button className="button button--primary" disabled={busy !== null || !validated || !confirmed || secret === ""} type="submit">{busy === "save" ? t("ai.saving") : t("ai.saveSecurely")}</button>
          <details className="ai-disclosure ai-disclosure--form"><summary>{t("ai.securityMechanism")}</summary><p>{t("ai.credentialCopy")}</p></details>
        </form>
      </section>

      <section aria-labelledby="saved-credentials-heading" className="ai-panel ai-panel--registry">
        <div className="ai-panel__heading"><h2 id="saved-credentials-heading">{t("ai.savedHeading")}</h2><span className="ai-count">{credentials.length}</span></div>
        {credentials.length === 0 ? <div className="ai-empty-action"><p>{t("ai.noSavedCredentials")}</p><p>{t("ai.savedCredentialsCopy")}</p></div> : (
          <div className="ai-credential-list">
            {credentials.map((credential) => (
              <article className="ai-credential-row" key={credential.id}>
                <div className="ai-credential-row__top">
                  <div><h3>{credential.alias}</h3><code>•••• {credential.last_four ?? "—"}</code></div>
                  <span className={credential.status === "active" ? "ai-status ai-status--ready" : "ai-status"}>{displayStatus(t, credential.status)}</span>
                </div>
                <p className="ai-credential-row__summary">{t("ai.savedCredentialsCopy")}</p>
                {credential.status === "active" ? (
                  <div className="ai-credential-actions">
                    <button className="button button--secondary" disabled={busy !== null} onClick={() => void runCredentialAction(`validate-${credential.id}`, () => validateSavedCredential(credential.id))} type="button">{t("ai.validateSaved")}</button>
                    <button className="button button--secondary" disabled={busy !== null} onClick={() => { setReplacementFor(credential.id); setReplacementAlias(`${credential.alias} replacement`); setReplacementSecret(""); setReplacementConfirmed(false); }} type="button">{t("ai.replace")}</button>
                    {scopedProjectId !== "" ? <button className="button button--secondary" disabled={busy !== null} onClick={() => void runCredentialAction(`grant-${credential.id}`, () => grantCredential(credential, scopedProjectId))} type="button">{t("ai.grantProject")}</button> : <div className="ai-grant-control"><input aria-label={t("ai.projectId")} onChange={(event) => setProjectIds((current) => ({ ...current, [credential.id]: event.target.value }))} placeholder={t("ai.projectId")} value={projectIds[credential.id] ?? ""} /><button className="button button--secondary" disabled={busy !== null || !(projectIds[credential.id] ?? "").match(/^[0-9a-f-]{36}$/i)} onClick={() => void runCredentialAction(`grant-${credential.id}`, () => grantCredential(credential, projectIds[credential.id] ?? ""))} type="button">{t("ai.grantProject")}</button></div>}
                    <button className="ai-text-action ai-text-action--danger" disabled={busy !== null} onClick={() => { if (window.confirm(t("ai.confirmRevoke", { alias: credential.alias }))) void runCredentialAction(`revoke-${credential.id}`, () => revokeCredential(credential)); }} type="button">{t("ai.revoke")}</button>
                  </div>
                ) : null}
                <details className="ai-disclosure ai-disclosure--row"><summary>{t("ai.technicalDetails")}</summary><dl><div><dt>Provider</dt><dd>{credential.provider_key}</dd></div><div><dt>Validation</dt><dd>{credential.last_validation_status ?? t("common.unknown")}</dd></div><div><dt>Revision</dt><dd>r{credential.revision}</dd></div></dl></details>
                {replacementFor === credential.id ? (
                  <form className="ai-replacement-form" onSubmit={(event) => { event.preventDefault(); if (!isZhipuCredentialInputWellFormed(credential.provider_key, replacementSecret)) { setNotice("zhipuFormat"); return; } void runCredentialAction(`replace-${credential.id}`, async () => { const result = await replaceCredential(credential, replacementAlias.trim(), replacementSecret); setReplacementFor(null); setReplacementAlias(""); setReplacementSecret(""); setReplacementConfirmed(false); return result; }); }}>
                    <strong>{t("ai.replaceHeading")}</strong>
                    <label><span>{t("ai.credentialAlias")}</span><input maxLength={120} onChange={(event) => setReplacementAlias(event.target.value)} value={replacementAlias} /></label>
                    <label><span>{t("ai.replacementCredential")}</span><input autoComplete="new-password" onChange={(event) => setReplacementSecret(event.target.value)} placeholder={credential.provider_key === "zhipu" ? "Zhipu API key" : "fixture-sk-…"} type="password" value={replacementSecret} /></label>
                    <label className="ai-confirm"><input checked={replacementConfirmed} onChange={(event) => setReplacementConfirmed(event.target.checked)} type="checkbox" /><span>{t("ai.confirmReplace")}</span></label>
                    <div><button className="button button--secondary" onClick={() => { setReplacementFor(null); setReplacementSecret(""); }} type="button">{t("common.cancel")}</button><button className="button button--primary" disabled={!replacementConfirmed || replacementSecret.length < 20 || replacementAlias.trim() === ""} type="submit">{t("ai.replaceAndErase")}</button></div>
                  </form>
                ) : null}
              </article>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

function UsagePanel() {
  const { t, i18n } = useAppTranslation();
  const [items, setItems] = useState<AuditEvent[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [reloadToken, setReloadToken] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    void listAudit(undefined, controller.signal).then((result) => { setItems(result.items); setFailed(false); }).catch(() => setFailed(true));
    return () => controller.abort();
  }, [reloadToken]);
  if (failed) return <FeedbackPanel action={{ label: t("ai.refresh"), onClick: () => { setItems(null); setFailed(false); setReloadToken((value) => value + 1); } }} eyebrow={t("ai.page.usage.title")} heading={t("ai.activityUnavailable")} kind="error"><p>{t("ai.activityUnavailableCopy")}</p><details className="ai-disclosure"><summary>{t("ai.technicalDetails")}</summary><p>{t("ai.loadFailedCopy")}</p></details></FeedbackPanel>;
  return (
    <section aria-labelledby="usage-audit-heading" className="ai-panel ai-panel--registry">
      <div className="ai-panel__heading"><h2 id="usage-audit-heading">{t("ai.page.usage.title")}</h2><span className="ai-status">{t("ai.governedActivity")}</span></div>
      {items === null ? <p className="loading-copy" role="status">{t("common.loading")}</p> : items.length === 0 ? <div className="ai-empty-action"><p>{t("ai.noActivity")}</p><p>{t("ai.noActivityCopy")}</p><Link className="button button--primary" to={tabPaths.models}>{t("ai.goToModels")}</Link></div> : (
        <div className="ai-audit-list" aria-label={t("ai.page.usage.title")}>
          {items.map((item) => {
            const model = valueFromMetadata(item.safe_metadata, "model") ?? valueFromMetadata(item.safe_metadata, "model_id") ?? t("ai.unknown");
            const attempt = valueFromMetadata(item.safe_metadata, "attempt") ?? "1";
            const cost = valueFromMetadata(item.safe_metadata, "cost_minor_units") ?? "-";
            const currency = valueFromMetadata(item.safe_metadata, "currency") ?? t("ai.unknown");
            return <article className="ai-audit-row" key={item.id}><div className="ai-audit-row__main"><div><strong>{activityLabel(t, item.action)}</strong><span>{t("ai.activity.model")}: {model}</span></div><span className="ai-status">{displayStatus(t, item.outcome)}</span></div><dl><div><dt>{t("ai.activity.attempt")}</dt><dd>{attempt}</dd></div><div><dt>{t("ai.activity.cost")}</dt><dd>{cost} {currency}</dd></div><div><dt>{t("ai.activity.time")}</dt><dd><time dateTime={item.created_at}>{new Intl.DateTimeFormat(i18n.resolvedLanguage, { dateStyle: "medium", timeStyle: "short" }).format(new Date(item.created_at))}</time></dd></div></dl><details className="ai-disclosure ai-disclosure--row"><summary>{t("ai.viewDetails")}</summary><dl><div><dt>Internal ID</dt><dd>{item.id}</dd></div><div><dt>Invocation ID</dt><dd>{item.invocation_id ?? t("ai.unknown")}</dd></div><div><dt>Metadata</dt><dd>{JSON.stringify(item.safe_metadata)}</dd></div></dl></details></article>;
          })}
        </div>
      )}
    </section>
  );
}

export function AISettingsPage() {
  const { t } = useAppTranslation();
  const { tab } = useParams();
  const active: SettingsTab = tab === "credentials" || tab === "usage-audit" ? (tab === "usage-audit" ? "usage" : "credentials") : "models";
  const [reloadToken, setReloadToken] = useState(0);
  const [data, setData] = useState<FoundationData | null>(null);
  const [error, setError] = useState<AIFoundationApiError | null>(null);
  const abortable = useMemo(() => active !== "usage", [active]);

  useEffect(() => {
    if (!abortable || !phase3aFixtureEnabled) return;
    const controller = new AbortController();
    void Promise.all([
      listProviders(controller.signal),
      listCapabilities(controller.signal),
      listCredentials(controller.signal),
      getUserPreference(controller.signal),
    ]).then(async ([providers, capabilities, credentials, preference]) => {
      const models = (await Promise.all(providers.map((provider) => listModels(provider.provider_key, controller.signal)))).flat();
      setError(null);
      setData({ providers, models, capabilities, credentials, preference });
    }).catch((caught: unknown) => { if (!controller.signal.aborted) setError(asSettingsError(caught)); });
    return () => controller.abort();
  }, [abortable, reloadToken]);

  if (!phase3aFixtureEnabled) return <Navigate replace to="/paintpilot/projects" />;
  const pageCopy: [string, string] = active === "models" ? ["ai.page.models.title", "ai.page.models.copy"] : active === "credentials" ? ["ai.page.credentials.title", "ai.page.credentials.copy"] : ["ai.page.usage.title", "ai.page.usage.copy"];
  return (
    <div className="page page--ai-settings">
      <header className="ai-settings-header"><div><h1>{t(pageCopy[0])}</h1><p>{t(pageCopy[1])}</p></div></header>
      <ProviderBoundary />
      <SetupPath active={active} />
      <SettingsTabs active={active} />
      <div className="page__content ai-settings-content">
        {active !== "usage" && data === null && error === null ? <section className="ai-loading" aria-busy="true"><p className="context-label">{t("ai.loadingEyebrow")}</p><h2>{t("ai.loadingHeading")}</h2><div aria-hidden="true" /></section> : null}
        {error !== null ? <FeedbackPanel action={{ label: t("common.retry"), onClick: () => { setError(null); setData(null); setReloadToken((value) => value + 1); } }} eyebrow={t("ai.unavailableEyebrow")} heading={t("ai.loadFailed")} kind="error"><p>{error.status === 404 ? t("ai.disabledCopy") : t("ai.loadFailedCopy")}</p></FeedbackPanel> : null}
        {data !== null && active === "models" ? <ModelsPanel data={data} onReload={() => setReloadToken((value) => value + 1)} /> : null}
        {data !== null && active === "credentials" ? <CredentialsPanel credentials={data.credentials} providers={data.providers} onReload={() => setReloadToken((value) => value + 1)} /> : null}
        {active === "usage" ? <UsagePanel /> : null}
      </div>
    </div>
  );
}
