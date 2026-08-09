import { type FormEvent, useEffect, useMemo, useState } from "react";
import { Link, Navigate, useParams } from "react-router";

import {
  createFixtureInvocation,
  getProjectPolicy,
  listCapabilities,
  listCredentials,
  listModels,
  listProviders,
  phase3aFixtureEnabled,
  previewFixtureInvocation,
  updateProjectPolicy,
  type CapabilityDefinition,
  type CredentialRecord,
  type ModelDefinition,
  type InvocationPreview,
  type InvocationRecord,
  type ProjectPolicy,
  type ProviderDefinition,
} from "../api/aiFoundation";
import { isPaintProjectId } from "../api/paintProjects";
import { FeedbackPanel } from "../components/FeedbackPanel";
import { useAppTranslation } from "../i18n";

interface PolicyData {
  capabilities: CapabilityDefinition[];
  credentials: CredentialRecord[];
  models: ModelDefinition[];
  policy: ProjectPolicy;
  provider: ProviderDefinition;
}

function displayPolicyStatus(t: (key: string) => string, value: string): string {
  if (value === "ready") return t("ai.status.ready");
  if (value === "succeeded") return t("ai.status.succeeded");
  if (value === "failed") return t("ai.status.failed");
  return t("ai.status.notConfigured");
}

function displayCapability(t: (key: string) => string, capability: CapabilityDefinition): string {
  switch (capability.capability_key) {
    case "structured_output": return t("ai.capability.structuredOutput");
    case "text_generation": return t("ai.capability.textGeneration");
    case "vision_understanding": return t("ai.capability.visionUnderstanding");
    default: return capability.display_name;
  }
}

export function AIProjectPolicyPage() {
  const { t } = useAppTranslation();
  const { projectId } = useParams();
  const [data, setData] = useState<PolicyData | null>(null);
  const [failed, setFailed] = useState(false);
  const [reloadToken, setReloadToken] = useState(0);
  const [modelId, setModelId] = useState("");
  const [credentialId, setCredentialId] = useState("");
  const [capabilityIds, setCapabilityIds] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState<"error" | "saved" | null>(null);
  const [fixtureConfirmed, setFixtureConfirmed] = useState(false);
  const [invocationBusy, setInvocationBusy] = useState<"invoke" | "preview" | null>(null);
  const [invocationPreview, setInvocationPreview] = useState<InvocationPreview | null>(null);
  const [invocationResult, setInvocationResult] = useState<InvocationRecord | null>(null);
  const [invocationFailed, setInvocationFailed] = useState(false);

  useEffect(() => {
    if (!phase3aFixtureEnabled || !isPaintProjectId(projectId)) return;
    const controller = new AbortController();
    void Promise.all([
      listProviders(controller.signal),
      listModels("fixture_local", controller.signal),
      listCapabilities(controller.signal),
      listCredentials(controller.signal),
      getProjectPolicy(projectId, controller.signal),
    ]).then(([providers, models, capabilities, credentials, policy]) => {
      const provider = providers[0];
      if (provider === undefined) throw new Error("missing_fixture_provider");
      setFailed(false);
      setData({ provider, models, capabilities, credentials, policy });
      setModelId(policy.default_model_definition_id ?? models[0]?.id ?? "");
      setCredentialId(
        policy.default_credential_id ??
          credentials.find((item) =>
            policy.active_grant_credential_ids.includes(item.id),
          )?.id ??
          "",
      );
      setCapabilityIds(
        policy.capability_allowlist.length > 0
          ? policy.capability_allowlist
          : capabilities.map((item) => item.id),
      );
    }).catch(() => {
      if (!controller.signal.aborted) setFailed(true);
    });
    return () => controller.abort();
  }, [projectId, reloadToken]);

  const selectedModel = useMemo(
    () => data?.models.find((model) => model.id === modelId) ?? null,
    [data, modelId],
  );
  const grantedCredentials = useMemo(
    () =>
      data?.credentials.filter(
        (credential) =>
          credential.status === "active" &&
          data.policy.active_grant_credential_ids.includes(credential.id),
      ) ?? [],
    [data],
  );

  const resetTest = () => {
    setFixtureConfirmed(false);
    setInvocationPreview(null);
    setInvocationResult(null);
    setInvocationFailed(false);
  };

  const selectModel = (nextModelId: string) => {
    const nextModel = data?.models.find((model) => model.id === nextModelId);
    const supportedIds = new Set(nextModel?.capabilities.map((capability) => capability.id) ?? []);
    setModelId(nextModelId);
    setCapabilityIds((current) => current.filter((id) => supportedIds.has(id)));
    resetTest();
  };

  const selectCredential = (nextCredentialId: string) => {
    setCredentialId(nextCredentialId);
    resetTest();
  };

  const toggleCapability = (capabilityId: string, checked: boolean) => {
    setCapabilityIds((current) => checked ? [...new Set([...current, capabilityId])] : current.filter((id) => id !== capabilityId));
    resetTest();
  };

  const save = async (event: FormEvent) => {
    event.preventDefault();
    if (
      data === null ||
      !isPaintProjectId(projectId) ||
      modelId === "" ||
      credentialId === "" ||
      capabilityIds.length === 0
    ) {
      setNotice("error");
      return;
    }
    setSaving(true);
    setNotice(null);
    try {
      await updateProjectPolicy({
        projectId,
        providerId: data.provider.id,
        modelId,
        credentialId,
        capabilityIds,
        expectedRevision: data.policy.revision,
      });
      setNotice("saved");
      setReloadToken((value) => value + 1);
    } catch {
      setNotice("error");
    } finally {
      setSaving(false);
    }
  };

  const invocationInput = () => {
    if (data === null || !isPaintProjectId(projectId)) return null;
    const capabilityKeys = data.capabilities
      .filter((capability) => capabilityIds.includes(capability.id))
      .map((capability) => capability.capability_key);
    if (modelId === "" || credentialId === "" || capabilityKeys.length === 0) {
      return null;
    }
    return {
      projectId,
      providerId: data.provider.id,
      modelId,
      credentialId,
      capabilityKeys,
    };
  };

  const previewInvocation = async () => {
    const input = invocationInput();
    if (input === null) {
      setInvocationFailed(true);
      return;
    }
    setInvocationBusy("preview");
    setInvocationFailed(false);
    setInvocationResult(null);
    try {
      setInvocationPreview(await previewFixtureInvocation(input));
    } catch {
      setInvocationPreview(null);
      setInvocationFailed(true);
    } finally {
      setInvocationBusy(null);
    }
  };

  const invokeFixture = async () => {
    const input = invocationInput();
    if (input === null || !fixtureConfirmed || invocationPreview === null) {
      setInvocationFailed(true);
      return;
    }
    setInvocationBusy("invoke");
    setInvocationFailed(false);
    try {
      setInvocationResult(await createFixtureInvocation(input));
    } catch {
      setInvocationResult(null);
      setInvocationFailed(true);
    } finally {
      setInvocationBusy(null);
    }
  };

  if (!phase3aFixtureEnabled) return <Navigate replace to="/paintpilot/projects" />;
  if (!isPaintProjectId(projectId)) {
    return (
      <div className="page page--ai-policy">
        <FeedbackPanel eyebrow={t("detail.invalidAddress")} heading={t("detail.invalidId")} headingLevel={1} kind="error">
          <Link className="button button--secondary" to="/paintpilot/projects">{t("detail.viewProjects")}</Link>
        </FeedbackPanel>
      </div>
    );
  }

  return (
    <div className="page page--ai-policy">
      <div className="detail-breadcrumb"><Link to={`/paintpilot/projects/${projectId}`}>← {t("ai.backProject")}</Link></div>
      <header className="ai-settings-header ai-settings-header--project">
        <div><h1>{t("ai.page.project.title")}</h1><p>{t("ai.page.project.copy")}</p></div>
      </header>
      <details className="ai-boundary" role="note"><summary><span className="ai-boundary__signal" aria-hidden="true" /><strong>{t("ai.testMode")}</strong><span className="ai-boundary__learn">{t("ai.learnDetails")}</span></summary><div className="ai-boundary__details"><p>{t("ai.projectBoundaryCopy")}</p><dl><div><dt>Provider</dt><dd>Fixture Provider</dd></div><div><dt>Scope</dt><dd>Local only</dd></div><div><dt>Network</dt><dd>No provider calls</dd></div></dl></div></details>
      <nav aria-label={t("ai.flowLabel")} className="ai-setup-path"><Link className="ai-setup-path__link" to="/paintpilot/settings/ai/credentials"><span>1</span>{t("ai.flow.credentials")}</Link><Link className="ai-setup-path__link" to="/paintpilot/settings/ai/models-providers"><span>2</span>{t("ai.flow.models")}</Link><span className="ai-setup-path__link ai-setup-path__link--active"><span>3</span>{t("ai.flow.project")}</span><Link className="ai-setup-path__link" to="/paintpilot/settings/ai/usage-audit"><span>4</span>{t("ai.flow.usage")}</Link></nav>
      <div className="page__content ai-settings-content">
        {failed ? <FeedbackPanel action={{ label: t("common.retry"), onClick: () => { setFailed(false); setData(null); setReloadToken((value) => value + 1); } }} eyebrow={t("ai.unavailableEyebrow")} heading={t("ai.loadFailed")} kind="error"><p>{t("ai.loadFailedCopy")}</p></FeedbackPanel> : null}
        {!failed && data === null ? <section className="ai-loading" aria-busy="true"><p className="context-label">{t("ai.loadingEyebrow")}</p><h2>{t("ai.policyLoading")}</h2><div aria-hidden="true" /></section> : null}
        {data !== null ? (
          <form className="ai-policy-workspace" onSubmit={(event) => void save(event)}>
            <section className="ai-panel ai-panel--registry ai-policy-section ai-policy-section--selection" aria-labelledby="routing-policy-heading">
              <div className="ai-panel__heading"><h2 id="routing-policy-heading">{t("ai.selectModel")}</h2><span className={data.policy.enabled ? "ai-status ai-status--ready" : "ai-status"}>{data.policy.enabled ? t("ai.enabled") : t("ai.status.notConfigured")}</span></div>
              <div className="ai-routing-stack">
                <div className="ai-routing-step"><div><small>{t("ai.provider")}</small><strong>{data.provider.display_name}</strong></div></div>
                <label className="ai-routing-step"><div><small>{t("ai.defaultModel")}</small><select value={modelId} onChange={(event) => selectModel(event.target.value)}>{data.models.map((model) => <option value={model.id} key={model.id}>{model.display_name}</option>)}</select></div></label>
              </div>
            </section>

            <section className="ai-panel ai-panel--control ai-policy-section ai-policy-section--credential" aria-labelledby="credential-policy-heading">
              <div className="ai-panel__heading"><h2 id="credential-policy-heading">{t("ai.selectCredential")}</h2></div>
              {grantedCredentials.length === 0 ? <div className="ai-empty-action"><p>{t("ai.grantRequired")}</p><p>{t("ai.grantRequiredCopy")}</p><Link className="button button--primary" to={`${tabPathsCredentials()}?project=${projectId}`}>{t("ai.addAndGrantCredential")}</Link></div> : <label className="ai-routing-step ai-routing-step--single"><div><small>{t("ai.defaultCredential")}</small><select value={credentialId} onChange={(event) => selectCredential(event.target.value)}><option value="">{t("ai.chooseCredential")}</option>{grantedCredentials.map((credential) => <option value={credential.id} key={credential.id}>{credential.alias} · ••••{credential.last_four}</option>)}</select></div></label>}
            </section>

            <section className="ai-panel ai-panel--registry ai-policy-section" aria-labelledby="capability-policy-heading">
              <div className="ai-panel__heading"><h2 id="capability-policy-heading">{t("ai.modelCapabilities")}</h2><span className="ai-count">{capabilityIds.length}</span></div>
              <div className="ai-check-list">
                {data.capabilities.map((capability) => {
                  const supported = selectedModel?.capabilities.some((item) => item.id === capability.id) ?? false;
                  return <label className={!supported ? "ai-check ai-check--disabled" : "ai-check"} key={capability.id}><input checked={capabilityIds.includes(capability.id) && supported} disabled={!supported} onChange={(event) => toggleCapability(capability.id, event.target.checked)} type="checkbox" /><span><strong>{displayCapability(t, capability)}</strong></span><em>{supported ? t("ai.allow") : t("ai.unsupported")}</em></label>;
                })}
              </div>
              <details className="ai-disclosure ai-disclosure--form"><summary>{t("ai.technicalDetails")}</summary><p>{selectedModel?.capabilities.map((capability) => capability.capability_key).join(", ")}</p></details>
            </section>

            <section className="ai-panel ai-panel--quiet ai-policy-section" aria-labelledby="limits-heading">
              <div className="ai-panel__heading"><h2 id="limits-heading">{t("ai.callLimits")}</h2></div>
              <div className="ai-limit-list"><strong>{t("ai.projectPerCallLimit")}</strong><strong>{t("ai.projectDailyLimit")}</strong><strong>{t("ai.autoFallback")}</strong><strong>{t("ai.unknownCostBlocked")}</strong></div>
              {notice === "saved" ? <p className="ai-form__notice ai-form__notice--success" role="status">{t("ai.policySaved")}</p> : null}
              {notice === "error" ? <p className="ai-form__notice" role="alert">{t("ai.saveFailed")}</p> : null}
              <button className="button button--primary" disabled={saving || grantedCredentials.length === 0 || capabilityIds.length === 0} type="submit">{saving ? t("ai.saving") : t("ai.savePolicy")}</button>
            </section>

            <section className="ai-panel ai-panel--control ai-policy-section ai-policy-section--test" aria-labelledby="fixture-invocation-heading">
              <div className="ai-panel__heading"><h2 id="fixture-invocation-heading">{t("ai.testConfiguration")}</h2><span className="ai-status">{t("ai.simulated")}</span></div>
              <section className="ai-invocation-check" aria-labelledby="fixture-invocation-heading">
                <p>{t("ai.invocationCopy")}</p>
                <div className="ai-invocation-actions">
                  <button className="button button--secondary" disabled={invocationBusy !== null || data.policy.resolved_status !== "ready"} onClick={() => void previewInvocation()} type="button">{invocationBusy === "preview" ? t("ai.previewing") : t("ai.previewInvocation")}</button>
                  <label className="ai-confirm"><input checked={fixtureConfirmed} onChange={(event) => setFixtureConfirmed(event.target.checked)} type="checkbox" /><span>{t("ai.confirmFixtureInvocation")}</span></label>
                  <button className="button button--primary" disabled={invocationBusy !== null || !fixtureConfirmed || invocationPreview === null} onClick={() => void invokeFixture()} type="button">{invocationBusy === "invoke" ? t("ai.invoking") : t("ai.runLocalTest")}</button>
                </div>
                {invocationPreview !== null ? <dl className="ai-invocation-preview"><div><dt>{t("ai.defaultModel")}</dt><dd>{invocationPreview.model_id}</dd></div><div><dt>{t("ai.credentialAlias")}</dt><dd>{invocationPreview.credential_alias}</dd></div><div><dt>{t("ai.testCredits")}</dt><dd>{invocationPreview.estimated_cost_minor_units} {invocationPreview.currency}</dd></div></dl> : null}
                {invocationResult !== null ? <div className="ai-invocation-result" role="status"><div><strong>{t("ai.invocationComplete")}</strong><span className={invocationResult.status === "succeeded" ? "ai-status ai-status--ready" : "ai-status"}>{displayPolicyStatus(t, invocationResult.status)}</span></div><details className="ai-disclosure ai-disclosure--row"><summary>{t("ai.technicalDetails")}</summary><p>{invocationResult.id}</p>{invocationResult.attempts.map((attempt) => <p key={attempt.id}>{t("ai.attemptSummary", { number: attempt.attempt_number, provider: attempt.provider_key, model: attempt.model_id, status: displayPolicyStatus(t, attempt.status) })}</p>)}</details></div> : null}
                {invocationFailed ? <p className="ai-form__notice" role="alert">{t("ai.invocationRejected")}</p> : null}
              </section>
            </section>
          </form>
        ) : null}
      </div>
    </div>
  );
}

function tabPathsCredentials() {
  return "/paintpilot/settings/ai/credentials";
}
