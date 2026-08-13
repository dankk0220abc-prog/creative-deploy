import { fetchWithCsrf } from "./auth";

const AI_PATH = "/api/v1/ai";

export const phase3aFixtureEnabled =
  import.meta.env.VITE_PHASE3A_FIXTURE_ENABLED === "true";

export type ProviderKey = "fixture_local" | "openai" | "zhipu";
export type AICurrency = "FIXTURE_CREDITS" | "USD" | "CNY";

export interface CapabilityDefinition {
  id: string;
  capability_key: string;
  display_name: string;
  status: string;
  source: string | null;
  trust_status: string | null;
}

export interface ProviderDefinition {
  id: string;
  provider_key: ProviderKey;
  display_name: string;
  adapter_type: string;
  enabled: boolean;
  status: string;
  catalog_status: string;
  catalog_fresh_at: string | null;
  local_only: boolean;
  real_model_calls: boolean;
  real_cost: boolean;
  capabilities: CapabilityDefinition[];
}

export interface ModelDefinition {
  id: string;
  provider_key: ProviderKey;
  model_id: string;
  display_name: string;
  catalog_source: string;
  catalog_status: string;
  catalog_fresh_at: string | null;
  status: string;
  context_window: number | null;
  pricing_minor_units: number | null;
  pricing_currency: AICurrency | null;
  local_only: boolean;
  capabilities: CapabilityDefinition[];
}

export interface CredentialRecord {
  id: string;
  alias: string;
  provider_key: ProviderKey;
  fingerprint: string;
  last_four: string | null;
  status: "active" | "revoked" | "replaced";
  created_at: string;
  updated_at: string;
  revoked_at: string | null;
  replaced_at: string | null;
  last_validation_status: string | null;
  last_successful_validation_at: string | null;
  revision: number;
}

export interface CredentialValidation {
  provider_key: ProviderKey;
  valid: boolean;
  validation_status:
    | "fixture_valid"
    | "fixture_invalid"
    | "live_validation_not_authorized"
    | "provider_valid"
    | "provider_invalid";
  message_code: string;
  fixture: boolean;
  local_only: boolean;
  persisted: boolean;
}

export interface UserPreference {
  enabled: boolean;
  default_provider_definition_id: string | null;
  default_model_definition_id: string | null;
  default_credential_id: string | null;
  timeout_ms: number;
  streaming_enabled: boolean;
  cost_warning_minor_units: number | null;
  currency: AICurrency;
  budget_per_invocation_minor_units: number | null;
  budget_cumulative_minor_units: number | null;
  budget_window_seconds: number | null;
  revision: number;
}

export interface ProjectPolicy {
  project_id: string;
  enabled: boolean;
  default_provider_definition_id: string | null;
  default_model_definition_id: string | null;
  default_credential_id: string | null;
  provider_allowlist: string[];
  model_allowlist: string[];
  capability_allowlist: string[];
  credential_allowlist: string[];
  active_grant_credential_ids: string[];
  per_invocation_limit_minor_units: number | null;
  cumulative_limit_minor_units: number | null;
  budget_window_seconds: number | null;
  currency: AICurrency;
  allow_unknown_cost: boolean;
  allow_manual_model_id: boolean;
  allow_fallback: boolean;
  require_paid_call_confirmation: boolean;
  resolved_status: string;
  revision: number;
}

export interface AuditEvent {
  id: string;
  created_at: string;
  action: string;
  outcome: string;
  project_id: string | null;
  credential_id: string | null;
  invocation_id: string | null;
  provider_definition_id: string | null;
  model_definition_id: string | null;
  safe_metadata: Record<string, unknown>;
}

export interface InvocationAttempt {
  id: string;
  attempt_number: number;
  provider_key: string;
  model_id: string;
  status: string;
  currency: "FIXTURE_CREDITS";
  dispatched_at: string | null;
  terminal_at: string | null;
  final_error_category: string | null;
  safe_provider_metadata: Record<string, unknown>;
}

export interface InvocationRecord {
  id: string;
  product_space: string;
  project_id: string | null;
  invocation_family: "fixture_invocation";
  canonicalization_version: "phase3a-v1";
  payload_hash: string;
  status:
    | "pending"
    | "admitted"
    | "running"
    | "succeeded"
    | "failed"
    | "cancelled"
    | "outcome_unknown";
  final_attempt_id: string | null;
  final_error_category: string | null;
  output: Record<string, unknown> | null;
  currency: "FIXTURE_CREDITS";
  created_at: string;
  updated_at: string;
  replayed: boolean;
  attempts: InvocationAttempt[];
}

export interface InvocationPreview {
  admissible: boolean;
  provider_key: string;
  model_id: string;
  credential_alias: string;
  required_grant: boolean;
  active_grant: boolean;
  estimated_cost_minor_units: number;
  currency: "FIXTURE_CREDITS";
  fixture: true;
  local_only: true;
  fallback_enabled: false;
  confirmation_required: boolean;
}

interface ApiErrorEnvelope {
  error_code?: string;
  message?: string;
  retryable?: boolean;
}

export class AIFoundationApiError extends Error {
  readonly errorCode: string | null;
  readonly retryable: boolean;
  readonly status: number | null;

  constructor(
    message: string,
    options: { errorCode?: string; retryable?: boolean; status?: number } = {},
  ) {
    super(message);
    this.name = "AIFoundationApiError";
    this.errorCode = options.errorCode ?? null;
    this.retryable = options.retryable ?? false;
    this.status = options.status ?? null;
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

async function requestJson<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  let response: Response;
  try {
    response = await fetchWithCsrf(path, {
      ...init,
      headers: {
        Accept: "application/json",
        ...(init.body === undefined ? {} : { "Content-Type": "application/json" }),
        ...init.headers,
      },
    });
  } catch {
    throw new AIFoundationApiError("fixture_foundation_network_unavailable");
  }
  let payload: unknown = null;
  try {
    payload = await response.json();
  } catch {
    if (response.ok) {
      throw new AIFoundationApiError("fixture_foundation_invalid_response", {
        status: response.status,
      });
    }
  }
  if (!response.ok) {
    const envelope = isRecord(payload) ? (payload as ApiErrorEnvelope) : {};
    throw new AIFoundationApiError("fixture_foundation_request_failed", {
      errorCode:
        typeof envelope.error_code === "string" ? envelope.error_code : undefined,
      retryable: envelope.retryable === true,
      status: response.status,
    });
  }
  if (!isRecord(payload)) {
    throw new AIFoundationApiError("fixture_foundation_invalid_response", {
      status: response.status,
    });
  }
  return payload as T;
}

function commandHeaders(): HeadersInit {
  return { "Idempotency-Key": crypto.randomUUID() };
}

export async function listProviders(signal?: AbortSignal) {
  const response = await requestJson<{ items: ProviderDefinition[] }>(
    `${AI_PATH}/providers`,
    { signal },
  );
  return response.items;
}

export async function listModels(providerKey: string, signal?: AbortSignal) {
  const response = await requestJson<{ items: ModelDefinition[] }>(
    `${AI_PATH}/providers/${encodeURIComponent(providerKey)}/models`,
    { signal },
  );
  return response.items;
}

export async function listCapabilities(signal?: AbortSignal) {
  const response = await requestJson<{ items: CapabilityDefinition[] }>(
    `${AI_PATH}/capabilities`,
    { signal },
  );
  return response.items;
}

export async function listCredentials(signal?: AbortSignal) {
  const response = await requestJson<{ items: CredentialRecord[] }>(
    `${AI_PATH}/credentials`,
    { signal },
  );
  return response.items;
}

export function validateTemporaryCredential(providerKey: ProviderKey, credential: string) {
  return requestJson<CredentialValidation>(`${AI_PATH}/credentials/validate`, {
    method: "POST",
    headers: commandHeaders(),
    body: JSON.stringify({ provider_key: providerKey, credential }),
  });
}

export function isZhipuCredentialInputWellFormed(
  providerKey: string,
  credential: string,
) {
  return providerKey !== "zhipu" || /^[\x21-\x7e]+$/u.test(credential);
}

export function createCredential(providerKey: ProviderKey, alias: string, credential: string) {
  return requestJson<CredentialRecord>(`${AI_PATH}/credentials`, {
    method: "POST",
    headers: commandHeaders(),
    body: JSON.stringify({
      provider_key: providerKey,
      alias,
      credential,
      confirm_save: true,
    }),
  });
}

export function validateSavedCredential(credentialId: string) {
  return requestJson<CredentialValidation>(
    `${AI_PATH}/credentials/${credentialId}/validate`,
    { method: "POST", headers: commandHeaders() },
  );
}

export function revokeCredential(credential: CredentialRecord) {
  return requestJson<CredentialRecord>(
    `${AI_PATH}/credentials/${credential.id}/revoke`,
    {
      method: "POST",
      headers: commandHeaders(),
      body: JSON.stringify({ expected_revision: credential.revision, confirm: true }),
    },
  );
}

export function replaceCredential(
  credential: CredentialRecord,
  alias: string,
  replacement: string,
) {
  return requestJson<CredentialRecord>(
    `${AI_PATH}/credentials/${credential.id}/replace`,
    {
      method: "POST",
      headers: commandHeaders(),
      body: JSON.stringify({
        alias,
        credential: replacement,
        expected_revision: credential.revision,
        confirm_replace: true,
      }),
    },
  );
}

export function grantCredential(credential: CredentialRecord, projectId: string) {
  return requestJson<{ id: string }>(
    `${AI_PATH}/credentials/${credential.id}/grants`,
    {
      method: "POST",
      headers: commandHeaders(),
      body: JSON.stringify({
        project_id: projectId,
        expected_credential_revision: credential.revision,
      }),
    },
  );
}

export function getUserPreference(signal?: AbortSignal) {
  return requestJson<UserPreference>(`${AI_PATH}/preferences`, { signal });
}

export function updateUserPreference(input: {
  enabled: boolean;
  providerId: string;
  modelId: string;
  credentialId: string;
  currency: AICurrency;
  expectedRevision: number;
}) {
  return requestJson<UserPreference>(`${AI_PATH}/preferences`, {
    method: "PATCH",
    headers: commandHeaders(),
    body: JSON.stringify({
      enabled: input.enabled,
      default_provider_definition_id: input.providerId,
      default_model_definition_id: input.modelId,
      default_credential_id: input.credentialId,
      timeout_ms: 30_000,
      streaming_enabled: false,
      cost_warning_minor_units: input.currency === "CNY" ? 20 : 800,
      currency: input.currency,
      budget_per_invocation_minor_units: input.currency === "CNY" ? 100 : 1_000,
      budget_cumulative_minor_units: input.currency === "CNY" ? 100 : 10_000,
      budget_window_seconds: 86_400,
      expected_revision: input.expectedRevision,
    }),
  });
}

export function getProjectPolicy(projectId: string, signal?: AbortSignal) {
  return requestJson<ProjectPolicy>(
    `/api/v1/paint-projects/${projectId}/ai-model-policy`,
    { signal },
  );
}

export function updateProjectPolicy(input: {
  projectId: string;
  providerId: string;
  modelId: string;
  credentialId: string;
  capabilityIds: string[];
  currency: AICurrency;
  expectedRevision: number;
}) {
  return requestJson<ProjectPolicy>(
    `/api/v1/paint-projects/${input.projectId}/ai-model-policy`,
    {
      method: "PATCH",
      headers: commandHeaders(),
      body: JSON.stringify({
        enabled: true,
        default_provider_definition_id: input.providerId,
        default_model_definition_id: input.modelId,
        default_credential_id: input.credentialId,
        provider_allowlist: [input.providerId],
        model_allowlist: [input.modelId],
        capability_allowlist: input.capabilityIds,
        credential_allowlist: [input.credentialId],
        per_invocation_limit_minor_units: input.currency === "CNY" ? 100 : 1_000,
        cumulative_limit_minor_units: input.currency === "CNY" ? 100 : 5_000,
        budget_window_seconds: 86_400,
        currency: input.currency,
        allow_unknown_cost: false,
        allow_manual_model_id: false,
        allow_fallback: false,
        require_paid_call_confirmation: true,
        expected_revision: input.expectedRevision,
      }),
    },
  );
}

export async function listAudit(projectId?: string, signal?: AbortSignal) {
  const search = projectId === undefined ? "" : `?project_id=${projectId}`;
  return requestJson<{ items: AuditEvent[]; total: number }>(
    `${AI_PATH}/audit${search}`,
    { signal },
  );
}

function invocationBody(input: {
  projectId: string;
  providerId: string;
  modelId: string;
  credentialId: string;
  capabilityKeys: string[];
  scenario?: string;
}) {
  return {
    product_space: "paintpilot",
    project_id: input.projectId,
    invocation_family: "fixture_invocation",
    provider_definition_id: input.providerId,
    model_definition_id: input.modelId,
    credential_id: input.credentialId,
    temporary_credential: null,
    requested_capabilities: input.capabilityKeys,
    artifacts: [],
    payload: {
      prompt_label: "paintpilot-policy-browser-check",
      fixture_input: "deterministic-local-fixture-request",
      scenario: input.scenario ?? "success",
    },
    confirm_fixture_use: true,
  };
}

export function previewFixtureInvocation(input: {
  projectId: string;
  providerId: string;
  modelId: string;
  credentialId: string;
  capabilityKeys: string[];
}) {
  return requestJson<InvocationPreview>(`${AI_PATH}/invocations/preview`, {
    method: "POST",
    body: JSON.stringify(invocationBody(input)),
  });
}

export function createFixtureInvocation(input: {
  projectId: string;
  providerId: string;
  modelId: string;
  credentialId: string;
  capabilityKeys: string[];
  scenario?: string;
}) {
  return requestJson<InvocationRecord>(`${AI_PATH}/invocations`, {
    method: "POST",
    headers: commandHeaders(),
    body: JSON.stringify({
      ...invocationBody(input),
      max_attempts: 1,
      total_elapsed_time_limit_ms: 30_000,
    }),
  });
}
