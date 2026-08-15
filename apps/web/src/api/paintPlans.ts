import { fetchWithCsrf } from "./auth";
import { imageRoles, type ImageRole } from "./imageAssets";
import { regionLifecycles, type RegionLifecycle } from "./regionSets";

const uuidPattern =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const sha256Pattern = /^[0-9a-f]{64}$/;
const timezonePattern = /(Z|[+-]\d{2}:\d{2})$/;
const forbiddenResponseKeyPattern =
  /(^|[_-])(access[_-]?token|api[_-]?key|authorization|body|ciphertext|cookies?|headers?|password|plaintext|provider[_-]?response|raw|raw[_-]?response|refresh[_-]?token|response|secret)([_-]|$)/i;

export const phase3bPaintPlanEnabled =
  import.meta.env.VITE_PHASE3B_PAINT_PLAN_ENABLED === "true";

export const providerExecutionModes = [
  "fixture_available",
  "live_authorization_required",
] as const;
export const paintPlanRevisionKinds = [
  "generated",
  "edited",
  "regenerated",
] as const;
export const paintPlanLifecycles = [
  "generated",
  "edited",
  "under_review",
  "approved",
  "rejected",
  "superseded",
] as const;

export type ProviderExecutionMode = (typeof providerExecutionModes)[number];
export type PaintPlanRevisionKind = (typeof paintPlanRevisionKinds)[number];
export type PaintPlanLifecycle = (typeof paintPlanLifecycles)[number];
export type PaintPlanProviderKey = "fixture_local" | "openai" | "zhipu";
export type PaintPlanCurrency = "FIXTURE_CREDITS" | "USD" | "CNY";
export type PaintPlanGenerationLocale = "zh-CN" | "en-US";

const requiredPaintPlanImageRoles: readonly ImageRole[] = [
  "primary_front",
  "reference_back",
  "reference_angle",
];

export interface PaintPlanRegionInstruction {
  region_id: string;
  stable_region_key: string;
  region_label: string;
  target_color: string;
  preparation: string;
  base_coat: string;
  layer_strategy: string;
  edge_treatment: string;
  lighting_guidance: string;
  material_guidance: string;
  warnings: string[];
  confidence_ppm: number;
}

export interface RetrievedCitation {
  source_id: string;
  chunk_id: string;
  target_path: string;
}

export interface RetrievedContextUnit {
  source_id: string;
  source_title: string;
  source_type: string;
  repository_reference: string;
  chunk_id: string;
  section: string;
  content: string;
  retrieval_rationale: string;
  retrieval_score_ppm: number | null;
  locale: PaintPlanGenerationLocale;
  corpus_id: string;
  corpus_version: string;
}

export interface PaintPlanDocument {
  schema_version: "paint-plan.v1";
  title: string;
  overall_approach: string;
  instructions: PaintPlanRegionInstruction[];
  safety_notes: string[];
  knowledge_citations: RetrievedCitation[];
}

export interface PaintPlanSelectionInput {
  image_set_fingerprint: string;
  region_set_id: string;
  provider_definition_id: string;
  model_definition_id: string;
  credential_id: string;
  generation_locale: PaintPlanGenerationLocale;
  intent: string | null;
}

export interface PaintPlanExpectedSelectionProjection {
  provider_key: PaintPlanProviderKey;
  model_id: string;
  source_image_assets: PaintPlanImageAsset[];
  region_set: PaintPlanRegionSet;
}

export interface PaintPlanGenerateInput extends PaintPlanSelectionInput {
  confirm_generation: true;
  max_attempts: number;
}

export interface PaintPlanEditInput {
  expected_current_plan_id: string;
  expected_current_version: number;
  document: PaintPlanDocument;
}

export interface PaintPlanRevisionInput {
  expected_current_plan_id: string;
  expected_current_version: number;
}

export interface PaintPlanReviewInput extends PaintPlanRevisionInput {
  reason: string | null;
}

export interface PaintPlanRegenerateInput
  extends PaintPlanSelectionInput,
    PaintPlanRevisionInput {
  confirm_generation: true;
  max_attempts: number;
}

export interface PaintPlanImageAsset {
  id: string;
  role: ImageRole;
  version: number;
  content_url: string;
  sha256: string;
  media_type: "image/jpeg" | "image/png" | "image/webp";
  byte_length: number;
  width: number;
  height: number;
  upload_validation_result: string;
  rights_attestation_status: string;
  rights_attestation_version: number;
  intended_usage: string[];
}

export interface PaintPlanRegionSource {
  id: string;
  stable_region_key: string;
  kind: "paint" | "exclude";
  label: string;
  normalized_label: string;
  z_index: number;
  opacity_ppm: number;
  notes: string | null;
  bbox_min_x_ppm: number;
  bbox_min_y_ppm: number;
  bbox_max_x_ppm: number;
  bbox_max_y_ppm: number;
  vertices: [number, number][];
}

export interface PaintPlanRegionSet {
  id: string;
  version: number;
  geometry_fingerprint: string;
  effective_lifecycle: RegionLifecycle;
  stale: boolean;
  regions: PaintPlanRegionSource[];
}

export interface PaintPlanModelChoice {
  id: string;
  model_id: string;
  display_name: string;
  execution_mode: ProviderExecutionMode;
  currency: PaintPlanCurrency;
  supports_vision: boolean;
  supports_structured_output: boolean;
}

export interface PaintPlanProviderChoice {
  id: string;
  provider_key: PaintPlanProviderKey;
  display_name: string;
  execution_mode: ProviderExecutionMode;
  models: PaintPlanModelChoice[];
}

export interface PaintPlanCredentialChoice {
  id: string;
  alias: string;
  provider_key: PaintPlanProviderKey;
  active_grant: boolean;
  status: string;
}

export interface PaintPlanPreview {
  admissible: boolean;
  execution_mode: ProviderExecutionMode;
  provider_key: PaintPlanProviderKey;
  model_id: string;
  source_ready: boolean;
  estimated_cost_minor_units: number | null;
  currency: PaintPlanCurrency;
  estimate_status: "estimated" | "unavailable";
  live_execution_authorized: boolean;
  blockers: string[];
}

export interface PaintPlanReviewEvent {
  id: string;
  action: "submit" | "approve" | "reject";
  reason: string | null;
  actor_id: string;
  actor_display_name_snapshot: string;
  created_at: string;
}

export interface PaintPlan {
  id: string;
  lineage_id: string;
  paint_project_id: string;
  version: number;
  lineage_revision: number;
  parent_plan_id: string | null;
  revision_kind: PaintPlanRevisionKind;
  lifecycle: PaintPlanLifecycle;
  effective_lifecycle: PaintPlanLifecycle;
  is_current: boolean;
  stale: boolean;
  stale_reasons: string[];
  approval_valid: boolean;
  source_invocation_id: string;
  source_attempt_id: string;
  source_image_set_fingerprint: string;
  source_image_assets: PaintPlanImageAsset[];
  source_readiness_review_id: string;
  source_readiness_review_version: number;
  source_region_set_id: string;
  source_region_set_version: number;
  source_geometry_fingerprint: string;
  provider_definition_id: string;
  provider_key: PaintPlanProviderKey;
  provider_revision_snapshot: number;
  model_definition_id: string;
  model_id: string;
  model_revision_snapshot: number;
  provider_pricing_snapshot_id: string | null;
  prompt_template_id: string;
  prompt_template_key: "paint-plan";
  prompt_version: number;
  prompt_hash: string;
  generation_locale: PaintPlanGenerationLocale;
  schema_version: "paint-plan.v1";
  content_hash: string;
  document: PaintPlanDocument;
  retrieved_context: RetrievedContextUnit[];
  provider_request_id_status: "absent" | "provided" | "unavailable";
  provider_request_id: string | null;
  usage_measurement_status: "measured" | "unavailable";
  input_units: number | null;
  output_units: number | null;
  cost_measurement_status: "estimated" | "measured" | "unavailable";
  cost_minor_units: number | null;
  cost_currency: PaintPlanCurrency;
  latest_review: PaintPlanReviewEvent | null;
  allowed_actions: string[];
  requested_by_user_id: string;
  invocation_created_at: string;
  created_by_actor_type: "provider" | "user";
  created_by_actor_id: string;
  created_by_actor_display_name_snapshot: string;
  created_at: string;
}

export interface PaintPlanHistory {
  items: PaintPlan[];
}

export interface PaintPlanWorkbench {
  paint_project_id: string;
  access_role: "owner" | "reviewer";
  image_set_status: string;
  image_set_fingerprint: string | null;
  readiness_review_id: string | null;
  image_assets: PaintPlanImageAsset[];
  region_set: PaintPlanRegionSet | null;
  source_ready: boolean;
  blockers: string[];
  providers: PaintPlanProviderChoice[];
  credentials: PaintPlanCredentialChoice[];
  current_plan: PaintPlan | null;
  history: PaintPlan[];
  allowed_actions: string[];
}

const imageAssetKeys = Object.freeze([
  "id",
  "role",
  "version",
  "content_url",
  "sha256",
  "media_type",
  "byte_length",
  "width",
  "height",
  "upload_validation_result",
  "rights_attestation_status",
  "rights_attestation_version",
  "intended_usage",
] satisfies ReadonlyArray<keyof PaintPlanImageAsset>);
const regionSourceKeys = Object.freeze([
  "id",
  "stable_region_key",
  "kind",
  "label",
  "normalized_label",
  "z_index",
  "opacity_ppm",
  "notes",
  "bbox_min_x_ppm",
  "bbox_min_y_ppm",
  "bbox_max_x_ppm",
  "bbox_max_y_ppm",
  "vertices",
] satisfies ReadonlyArray<keyof PaintPlanRegionSource>);
const regionSetKeys = Object.freeze([
  "id",
  "version",
  "geometry_fingerprint",
  "effective_lifecycle",
  "stale",
  "regions",
] satisfies ReadonlyArray<keyof PaintPlanRegionSet>);
const modelChoiceKeys = Object.freeze([
  "id",
  "model_id",
  "display_name",
  "execution_mode",
  "currency",
  "supports_vision",
  "supports_structured_output",
] satisfies ReadonlyArray<keyof PaintPlanModelChoice>);
const providerChoiceKeys = Object.freeze([
  "id",
  "provider_key",
  "display_name",
  "execution_mode",
  "models",
] satisfies ReadonlyArray<keyof PaintPlanProviderChoice>);
const credentialChoiceKeys = Object.freeze([
  "id",
  "alias",
  "provider_key",
  "active_grant",
  "status",
] satisfies ReadonlyArray<keyof PaintPlanCredentialChoice>);
const previewKeys = Object.freeze([
  "admissible",
  "execution_mode",
  "provider_key",
  "model_id",
  "source_ready",
  "estimated_cost_minor_units",
  "currency",
  "estimate_status",
  "live_execution_authorized",
  "blockers",
] satisfies ReadonlyArray<keyof PaintPlanPreview>);
const instructionKeys = Object.freeze([
  "region_id",
  "stable_region_key",
  "region_label",
  "target_color",
  "preparation",
  "base_coat",
  "layer_strategy",
  "edge_treatment",
  "lighting_guidance",
  "material_guidance",
  "warnings",
  "confidence_ppm",
] satisfies ReadonlyArray<keyof PaintPlanRegionInstruction>);
const documentKeys = Object.freeze([
  "schema_version",
  "title",
  "overall_approach",
  "instructions",
  "safety_notes",
  "knowledge_citations",
] satisfies ReadonlyArray<keyof PaintPlanDocument>);
const citationKeys = Object.freeze([
  "source_id",
  "chunk_id",
  "target_path",
] satisfies ReadonlyArray<keyof RetrievedCitation>);
const retrievedContextKeys = Object.freeze([
  "source_id",
  "source_title",
  "source_type",
  "repository_reference",
  "chunk_id",
  "section",
  "content",
  "retrieval_rationale",
  "retrieval_score_ppm",
  "locale",
  "corpus_id",
  "corpus_version",
] satisfies ReadonlyArray<keyof RetrievedContextUnit>);
const reviewEventKeys = Object.freeze([
  "id",
  "action",
  "reason",
  "actor_id",
  "actor_display_name_snapshot",
  "created_at",
] satisfies ReadonlyArray<keyof PaintPlanReviewEvent>);
const paintPlanKeys = Object.freeze([
  "id",
  "lineage_id",
  "paint_project_id",
  "version",
  "lineage_revision",
  "parent_plan_id",
  "revision_kind",
  "lifecycle",
  "effective_lifecycle",
  "is_current",
  "stale",
  "stale_reasons",
  "approval_valid",
  "source_invocation_id",
  "source_attempt_id",
  "source_image_set_fingerprint",
  "source_image_assets",
  "source_readiness_review_id",
  "source_readiness_review_version",
  "source_region_set_id",
  "source_region_set_version",
  "source_geometry_fingerprint",
  "provider_definition_id",
  "provider_key",
  "provider_revision_snapshot",
  "model_definition_id",
  "model_id",
  "model_revision_snapshot",
  "provider_pricing_snapshot_id",
  "prompt_template_id",
  "prompt_template_key",
  "prompt_version",
  "prompt_hash",
  "generation_locale",
  "schema_version",
  "content_hash",
  "document",
  "retrieved_context",
  "provider_request_id_status",
  "provider_request_id",
  "usage_measurement_status",
  "input_units",
  "output_units",
  "cost_measurement_status",
  "cost_minor_units",
  "cost_currency",
  "latest_review",
  "allowed_actions",
  "requested_by_user_id",
  "invocation_created_at",
  "created_by_actor_type",
  "created_by_actor_id",
  "created_by_actor_display_name_snapshot",
  "created_at",
] satisfies ReadonlyArray<keyof PaintPlan>);
const workbenchKeys = Object.freeze([
  "paint_project_id",
  "access_role",
  "image_set_status",
  "image_set_fingerprint",
  "readiness_review_id",
  "image_assets",
  "region_set",
  "source_ready",
  "blockers",
  "providers",
  "credentials",
  "current_plan",
  "history",
  "allowed_actions",
] satisfies ReadonlyArray<keyof PaintPlanWorkbench>);
const errorEnvelopeKeys = Object.freeze([
  "error_code",
  "category",
  "message",
  "retryable",
  "request_id",
  "current_state",
  "allowed_actions",
  "safe_details",
]);
const selectionInputKeys = Object.freeze([
  "image_set_fingerprint",
  "region_set_id",
  "provider_definition_id",
  "model_definition_id",
  "credential_id",
  "generation_locale",
  "intent",
] satisfies ReadonlyArray<keyof PaintPlanSelectionInput>);
const generateInputKeys = Object.freeze([
  ...selectionInputKeys,
  "confirm_generation",
  "max_attempts",
] satisfies ReadonlyArray<keyof PaintPlanGenerateInput>);
const editInputKeys = Object.freeze([
  "expected_current_plan_id",
  "expected_current_version",
  "document",
] satisfies ReadonlyArray<keyof PaintPlanEditInput>);
const revisionInputKeys = Object.freeze([
  "expected_current_plan_id",
  "expected_current_version",
] satisfies ReadonlyArray<keyof PaintPlanRevisionInput>);
const reviewInputKeys = Object.freeze([
  ...revisionInputKeys,
  "reason",
] satisfies ReadonlyArray<keyof PaintPlanReviewInput>);
const regenerateInputKeys = Object.freeze([
  ...selectionInputKeys,
  ...revisionInputKeys,
  "confirm_generation",
  "max_attempts",
] satisfies ReadonlyArray<keyof PaintPlanRegenerateInput>);
const errorCategories = [
  "VALIDATION_ERROR",
  "NOT_FOUND",
  "IDEMPOTENCY_KEY_REUSED",
  "INVALID_STATE_TRANSITION",
  "CONFLICT",
  "DATABASE_UNAVAILABLE",
  "STORAGE_ERROR",
  "PROVIDER_TIMEOUT",
  "PROVIDER_RATE_LIMIT",
  "PROVIDER_RESPONSE_INVALID",
  "RETRIEVAL_ERROR",
  "SCHEMA_VALIDATION_ERROR",
  "INTERNAL_ERROR",
] as const;

interface PaintPlanValidationFieldDetail {
  field: string;
  message: string;
}

export type PaintPlanSafeDetails =
  | Readonly<{ blockers: readonly string[] }>
  | Readonly<{ fields: readonly PaintPlanValidationFieldDetail[] }>
  | Readonly<Record<string, never>>;

function isPlainObject(value: unknown): value is Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    return false;
  }
  const prototype = Object.getPrototypeOf(value) as unknown;
  return prototype === Object.prototype || prototype === null;
}

function hasExactKeys(
  value: Record<string, unknown>,
  expected: readonly string[],
): boolean {
  const actual = Object.keys(value);
  return (
    actual.length === expected.length &&
    expected.every((key) => Object.prototype.hasOwnProperty.call(value, key))
  );
}

function hasEqualJsonValue(left: unknown, right: unknown): boolean {
  if (Object.is(left, right)) {
    return true;
  }
  if (Array.isArray(left) || Array.isArray(right)) {
    return (
      Array.isArray(left) &&
      Array.isArray(right) &&
      left.length === right.length &&
      left.every((item, index) => hasEqualJsonValue(item, right[index]))
    );
  }
  if (!isPlainObject(left) || !isPlainObject(right)) {
    return false;
  }
  const keys = Object.keys(left);
  return (
    keys.length === Object.keys(right).length &&
    keys.every(
      (key) =>
        Object.prototype.hasOwnProperty.call(right, key) &&
        hasEqualJsonValue(left[key], right[key]),
    )
  );
}

function isEnum<T extends string>(
  value: unknown,
  choices: readonly T[],
): value is T {
  return typeof value === "string" && choices.includes(value as T);
}

function isArrayOf<T>(
  value: unknown,
  validator: (item: unknown) => item is T,
): value is T[] {
  return Array.isArray(value) && value.every(validator);
}

function isUuid(value: unknown): value is string {
  return typeof value === "string" && uuidPattern.test(value);
}

function isSha256(value: unknown): value is string {
  return typeof value === "string" && sha256Pattern.test(value);
}

function isTimestamp(value: unknown): value is string {
  return (
    typeof value === "string" &&
    timezonePattern.test(value) &&
    Number.isFinite(Date.parse(value))
  );
}

function isInteger(
  value: unknown,
  minimum: number,
  maximum = Number.MAX_SAFE_INTEGER,
): value is number {
  return (
    typeof value === "number" &&
    Number.isSafeInteger(value) &&
    value >= minimum &&
    value <= maximum
  );
}

function isBoundedText(
  value: unknown,
  minimum: number,
  maximum: number,
  allowMarkup = false,
): value is string {
  const hasControlCharacter =
    typeof value === "string" &&
    Array.from(value).some((character) => {
      const codePoint = character.codePointAt(0) ?? 0;
      return codePoint <= 31 || codePoint === 127;
    });
  return (
    typeof value === "string" &&
    value.length >= minimum &&
    value.length <= maximum &&
    !hasControlCharacter &&
    (allowMarkup || (!value.includes("<") && !value.includes(">")))
  );
}

function normalizedRequestText(value: string): string {
  return value.trim().split(/\s+/u).join(" ");
}

function normalizedRequestDocument(
  document: PaintPlanDocument,
): PaintPlanDocument {
  return {
    ...document,
    title: normalizedRequestText(document.title),
    overall_approach: normalizedRequestText(document.overall_approach),
    instructions: document.instructions.map((instruction) => ({
      ...instruction,
      region_label: normalizedRequestText(instruction.region_label),
      target_color: normalizedRequestText(instruction.target_color),
      preparation: normalizedRequestText(instruction.preparation),
      base_coat: normalizedRequestText(instruction.base_coat),
      layer_strategy: normalizedRequestText(instruction.layer_strategy),
      edge_treatment: normalizedRequestText(instruction.edge_treatment),
      lighting_guidance: normalizedRequestText(instruction.lighting_guidance),
      material_guidance: normalizedRequestText(instruction.material_guidance),
      warnings: instruction.warnings.map(normalizedRequestText),
    })),
    safety_notes: document.safety_notes.map(normalizedRequestText),
  };
}

function isRequestText(
  value: unknown,
  minimum: number,
  maximum: number,
  allowMarkup = false,
): value is string {
  if (
    typeof value !== "string" ||
    value.length < minimum ||
    value.length > maximum
  ) {
    return false;
  }
  const normalized = normalizedRequestText(value);
  return isBoundedText(normalized, 1, maximum, allowMarkup);
}

function isStringList(
  value: unknown,
  options: { maxItems?: number; minLength?: number; maxLength?: number } = {},
): value is string[] {
  const minimumLength = options.minLength ?? 0;
  const maximumLength = options.maxLength ?? Number.MAX_SAFE_INTEGER;
  return (
    Array.isArray(value) &&
    (options.maxItems === undefined || value.length <= options.maxItems) &&
    value.every(
      (item) =>
        typeof item === "string" &&
        item.length >= minimumLength &&
        item.length <= maximumLength,
    )
  );
}

function containsForbiddenResponseData(value: unknown): boolean {
  if (Array.isArray(value)) {
    return value.some(containsForbiddenResponseData);
  }
  if (!isPlainObject(value)) {
    return false;
  }
  return Object.entries(value).some(
    ([key, nested]) =>
      forbiddenResponseKeyPattern.test(key) || containsForbiddenResponseData(nested),
  );
}

function isPaintPlanSafeDetails(
  value: unknown,
  errorCode: string,
  category: (typeof errorCategories)[number],
): value is PaintPlanSafeDetails {
  if (!isPlainObject(value) || containsForbiddenResponseData(value)) {
    return false;
  }
  if (errorCode === "REQUEST_VALIDATION_FAILED") {
    return (
      category === "VALIDATION_ERROR" &&
      hasExactKeys(value, ["fields"]) &&
      Array.isArray(value.fields) &&
      value.fields.length <= 64 &&
      value.fields.every(
        (field) =>
          isPlainObject(field) &&
          hasExactKeys(field, ["field", "message"]) &&
          isBoundedText(field.field, 1, 240) &&
          isBoundedText(field.message, 1, 240),
      )
    );
  }
  if (
    errorCode === "PAINT_PLAN_SOURCE_NOT_READY" ||
    errorCode === "LIVE_PROVIDER_EXECUTION_NOT_AUTHORIZED"
  ) {
    return (
      category === "CONFLICT" &&
      hasExactKeys(value, ["blockers"]) &&
      isStringList(value.blockers, {
        maxItems: 64,
        minLength: 1,
        maxLength: 160,
      })
    );
  }
  return hasExactKeys(value, []);
}

function isImageAsset(value: unknown, projectId?: string): value is PaintPlanImageAsset {
  return (
    isPlainObject(value) &&
    hasExactKeys(value, imageAssetKeys) &&
    isUuid(value.id) &&
    isEnum(value.role, imageRoles) &&
    isInteger(value.version, 1) &&
    typeof value.content_url === "string" &&
    (projectId === undefined ||
      value.content_url ===
        `/api/v1/paint-projects/${projectId}/images/${value.id}/content`) &&
    isSha256(value.sha256) &&
    isEnum(value.media_type, ["image/jpeg", "image/png", "image/webp"] as const) &&
    isInteger(value.byte_length, 1, 20_971_520) &&
    isInteger(value.width, 1, 8192) &&
    isInteger(value.height, 1, 8192) &&
    typeof value.upload_validation_result === "string" &&
    typeof value.rights_attestation_status === "string" &&
    isInteger(value.rights_attestation_version, 1) &&
    isStringList(value.intended_usage)
  );
}

function isGovernedPlanSourceAssets(
  value: unknown,
  projectId: string,
): value is PaintPlanImageAsset[] {
  if (
    !isArrayOf(value, (asset): asset is PaintPlanImageAsset =>
      isImageAsset(asset, projectId),
    ) ||
    value.length < 3 ||
    value.length > 4 ||
    new Set(value.map((asset) => asset.id)).size !== value.length ||
    new Set(value.map((asset) => asset.role)).size !== value.length
  ) {
    return false;
  }
  return (
    requiredPaintPlanImageRoles.every((role) =>
      value.some((asset) => asset.role === role),
    ) &&
    value.every(
      (asset) =>
        asset.upload_validation_result === "accepted" &&
        asset.rights_attestation_status === "confirmed",
    )
  );
}

function isRegionSource(value: unknown): value is PaintPlanRegionSource {
  return (
    isPlainObject(value) &&
    hasExactKeys(value, regionSourceKeys) &&
    isUuid(value.id) &&
    isUuid(value.stable_region_key) &&
    isEnum(value.kind, ["paint", "exclude"] as const) &&
    isBoundedText(value.label, 1, 80) &&
    isBoundedText(value.normalized_label, 1, 80) &&
    isInteger(value.z_index, 0, 127) &&
    isInteger(value.opacity_ppm, 100_000, 1_000_000) &&
    (value.notes === null || isBoundedText(value.notes, 1, 1000)) &&
    isInteger(value.bbox_min_x_ppm, 0, 1_000_000) &&
    isInteger(value.bbox_min_y_ppm, 0, 1_000_000) &&
    isInteger(value.bbox_max_x_ppm, 0, 1_000_000) &&
    isInteger(value.bbox_max_y_ppm, 0, 1_000_000) &&
    Array.isArray(value.vertices) &&
    value.vertices.length >= 3 &&
    value.vertices.length <= 256 &&
    value.vertices.every(
      (vertex) =>
        Array.isArray(vertex) &&
        vertex.length === 2 &&
        isInteger(vertex[0], 0, 1_000_000) &&
        isInteger(vertex[1], 0, 1_000_000),
    )
  );
}

function isRegionSet(value: unknown): value is PaintPlanRegionSet {
  if (
    !isPlainObject(value) ||
    !hasExactKeys(value, regionSetKeys) ||
    !isUuid(value.id) ||
    !isInteger(value.version, 1) ||
    !isSha256(value.geometry_fingerprint) ||
    !isEnum(value.effective_lifecycle, regionLifecycles) ||
    typeof value.stale !== "boolean" ||
    !isArrayOf(value.regions, isRegionSource)
  ) {
    return false;
  }
  return (
    new Set(value.regions.map((region) => region.id)).size ===
      value.regions.length &&
    new Set(value.regions.map((region) => region.stable_region_key)).size ===
      value.regions.length
  );
}

function isModelChoice(value: unknown): value is PaintPlanModelChoice {
  return (
    isPlainObject(value) &&
    hasExactKeys(value, modelChoiceKeys) &&
    isUuid(value.id) &&
    isBoundedText(value.model_id, 1, 160) &&
    isBoundedText(value.display_name, 1, 160) &&
    isEnum(value.execution_mode, providerExecutionModes) &&
    isEnum(value.currency, ["FIXTURE_CREDITS", "USD", "CNY"] as const) &&
    typeof value.supports_vision === "boolean" &&
    typeof value.supports_structured_output === "boolean"
  );
}

function isProviderChoice(value: unknown): value is PaintPlanProviderChoice {
  if (
    !isPlainObject(value) ||
    !hasExactKeys(value, providerChoiceKeys) ||
    !isUuid(value.id) ||
    !isEnum(value.provider_key, ["fixture_local", "openai", "zhipu"] as const) ||
    typeof value.display_name !== "string" ||
    !isEnum(value.execution_mode, providerExecutionModes) ||
    !isArrayOf(value.models, isModelChoice)
  ) {
    return false;
  }
  const expectedMode: ProviderExecutionMode =
    value.provider_key === "fixture_local"
      ? "fixture_available"
      : "live_authorization_required";
  const expectedCurrency: PaintPlanCurrency =
    value.provider_key === "fixture_local"
      ? "FIXTURE_CREDITS"
      : value.provider_key === "zhipu"
        ? "CNY"
        : "USD";
  return (
    value.execution_mode === expectedMode &&
    new Set(value.models.map((model) => model.id)).size === value.models.length &&
    new Set(value.models.map((model) => model.model_id)).size ===
      value.models.length &&
    value.models.every(
      (model) =>
        model.execution_mode === expectedMode && model.currency === expectedCurrency,
    )
  );
}

function isCredentialChoice(value: unknown): value is PaintPlanCredentialChoice {
  return (
    isPlainObject(value) &&
    hasExactKeys(value, credentialChoiceKeys) &&
    isUuid(value.id) &&
    typeof value.alias === "string" &&
    isEnum(value.provider_key, ["fixture_local", "openai", "zhipu"] as const) &&
    typeof value.active_grant === "boolean" &&
    typeof value.status === "string"
  );
}

function isPreview(value: unknown): value is PaintPlanPreview {
  if (
    !(
    isPlainObject(value) &&
    hasExactKeys(value, previewKeys) &&
    typeof value.admissible === "boolean" &&
    isEnum(value.execution_mode, providerExecutionModes) &&
    isEnum(value.provider_key, ["fixture_local", "openai", "zhipu"] as const) &&
    isBoundedText(value.model_id, 1, 160) &&
    typeof value.source_ready === "boolean" &&
    (value.estimated_cost_minor_units === null ||
      isInteger(value.estimated_cost_minor_units, 0)) &&
    isEnum(value.currency, ["FIXTURE_CREDITS", "USD", "CNY"] as const) &&
    isEnum(value.estimate_status, ["estimated", "unavailable"] as const) &&
    typeof value.live_execution_authorized === "boolean" &&
    isStringList(value.blockers, {
      maxItems: 64,
      minLength: 1,
      maxLength: 160,
    }) &&
    new Set(value.blockers).size === value.blockers.length
    )
  ) {
    return false;
  }
  if (
    (value.estimate_status === "estimated") !==
    (value.estimated_cost_minor_units !== null)
  ) {
    return false;
  }
  if (
    (value.execution_mode === "fixture_available" &&
      (value.provider_key !== "fixture_local" ||
        value.currency !== "FIXTURE_CREDITS")) ||
    (value.execution_mode === "live_authorization_required" &&
      !((value.provider_key === "openai" && value.currency === "USD") ||
        (value.provider_key === "zhipu" && value.currency === "CNY")))
  ) {
    return false;
  }
  if (!value.source_ready && (value.admissible || value.blockers.length === 0)) {
    return false;
  }
  if (value.execution_mode === "live_authorization_required") {
    if (value.provider_key === "openai") {
      return !value.live_execution_authorized && !value.admissible && value.blockers.includes("live_execution_authorization_required");
    }
    if (!value.live_execution_authorized) {
      return !value.admissible && value.blockers.includes("live_execution_authorization_required");
    }
    return value.admissible
      ? value.source_ready && value.blockers.length === 0 && value.estimate_status === "estimated"
      : value.blockers.length > 0;
  }
  return !value.live_execution_authorized && (value.admissible
    ? value.source_ready &&
        value.blockers.length === 0 &&
        value.estimate_status === "estimated"
    : value.blockers.length > 0 && value.estimate_status === "unavailable");
}

function isCitation(value: unknown): value is RetrievedCitation {
  return isPlainObject(value)
    && hasExactKeys(value, citationKeys)
    && isBoundedText(value.source_id, 1, 160)
    && isBoundedText(value.chunk_id, 1, 200)
    && isBoundedText(value.target_path, 1, 240);
}

function isRetrievedContext(value: unknown): value is RetrievedContextUnit {
  return isPlainObject(value)
    && hasExactKeys(value, retrievedContextKeys)
    && isBoundedText(value.source_id, 1, 160)
    && isBoundedText(value.source_title, 1, 300)
    && isBoundedText(value.source_type, 1, 160)
    && isBoundedText(value.repository_reference, 1, 512)
    && value.repository_reference.startsWith("repo://")
    && isBoundedText(value.chunk_id, 1, 200)
    && isBoundedText(value.section, 1, 120)
    && isBoundedText(value.content, 1, 4000)
    && isBoundedText(value.retrieval_rationale, 1, 500)
    && (value.retrieval_score_ppm === null || isInteger(value.retrieval_score_ppm, 0, 1_000_000))
    && isEnum(value.locale, ["zh-CN", "en-US"] as const)
    && isBoundedText(value.corpus_id, 1, 120)
    && isBoundedText(value.corpus_version, 1, 80);
}

function isRetrievedContextList(value: unknown): value is RetrievedContextUnit[] {
  return isArrayOf(value, isRetrievedContext)
    && value.length <= 24
    && new Set(value.map((item) => `${item.source_id}:${item.chunk_id}`)).size === value.length;
}

function documentCitationsBelongToContext(document: unknown, context: unknown): boolean {
  if (!isDocument(document) || !isRetrievedContextList(context)) return false;
  return document.knowledge_citations.every((citation) =>
    context.some(
      (unit) => unit.source_id === citation.source_id && unit.chunk_id === citation.chunk_id,
    ),
  );
}

function isInstruction(value: unknown): value is PaintPlanRegionInstruction {
  return (
    isPlainObject(value) &&
    hasExactKeys(value, instructionKeys) &&
    isUuid(value.region_id) &&
    isUuid(value.stable_region_key) &&
    isBoundedText(value.region_label, 1, 80) &&
    isBoundedText(value.target_color, 1, 120) &&
    isBoundedText(value.preparation, 1, 600) &&
    isBoundedText(value.base_coat, 1, 600) &&
    isBoundedText(value.layer_strategy, 1, 1000) &&
    isBoundedText(value.edge_treatment, 1, 600) &&
    isBoundedText(value.lighting_guidance, 1, 600) &&
    isBoundedText(value.material_guidance, 1, 600) &&
    isStringList(value.warnings, {
      maxItems: 8,
      minLength: 1,
      maxLength: 240,
    }) &&
    new Set(value.warnings).size === value.warnings.length &&
    isInteger(value.confidence_ppm, 0, 1_000_000)
  );
}

function isDocument(value: unknown): value is PaintPlanDocument {
  if (
    !isPlainObject(value) ||
    !hasExactKeys(value, documentKeys) ||
    value.schema_version !== "paint-plan.v1" ||
    !isBoundedText(value.title, 1, 160) ||
    !isBoundedText(value.overall_approach, 1, 2000) ||
    !Array.isArray(value.instructions) ||
    value.instructions.length < 1 ||
    value.instructions.length > 128 ||
    !value.instructions.every(isInstruction) ||
    !isStringList(value.safety_notes, {
      maxItems: 16,
      minLength: 1,
      maxLength: 400,
    }) ||
    !isArrayOf(value.knowledge_citations, isCitation) ||
    value.knowledge_citations.length > 24 ||
    new Set(value.knowledge_citations.map((item) => `${item.source_id}:${item.chunk_id}:${item.target_path}`)).size !== value.knowledge_citations.length ||
    new Set(value.safety_notes).size !== value.safety_notes.length
  ) {
    return false;
  }
  const regionIds = value.instructions.map((item) => item.region_id);
  const stableKeys = value.instructions.map((item) => item.stable_region_key);
  return (
    new Set(regionIds).size === regionIds.length &&
    new Set(stableKeys).size === stableKeys.length
  );
}

function isRequestInstruction(
  value: unknown,
): value is PaintPlanRegionInstruction {
  return (
    isPlainObject(value) &&
    hasExactKeys(value, instructionKeys) &&
    isUuid(value.region_id) &&
    isUuid(value.stable_region_key) &&
    isRequestText(value.region_label, 1, 80) &&
    isRequestText(value.target_color, 1, 120) &&
    isRequestText(value.preparation, 1, 600) &&
    isRequestText(value.base_coat, 1, 600) &&
    isRequestText(value.layer_strategy, 1, 1000) &&
    isRequestText(value.edge_treatment, 1, 600) &&
    isRequestText(value.lighting_guidance, 1, 600) &&
    isRequestText(value.material_guidance, 1, 600) &&
    isArrayOf(value.warnings, (warning): warning is string =>
      isRequestText(warning, 1, 240),
    ) &&
    value.warnings.length <= 8 &&
    new Set(value.warnings.map(normalizedRequestText)).size ===
      value.warnings.length &&
    isInteger(value.confidence_ppm, 0, 1_000_000)
  );
}

function isRequestDocument(value: unknown): value is PaintPlanDocument {
  if (
    !isPlainObject(value) ||
    !hasExactKeys(value, documentKeys) ||
    value.schema_version !== "paint-plan.v1" ||
    !isRequestText(value.title, 1, 160) ||
    !isRequestText(value.overall_approach, 1, 2000) ||
    !isArrayOf(value.instructions, isRequestInstruction) ||
    value.instructions.length < 1 ||
    value.instructions.length > 128 ||
    !isArrayOf(value.safety_notes, (note): note is string =>
      isRequestText(note, 1, 400),
    ) ||
    value.safety_notes.length > 16 ||
    !isArrayOf(value.knowledge_citations, isCitation) ||
    value.knowledge_citations.length > 24 ||
    new Set(value.safety_notes.map(normalizedRequestText)).size !==
      value.safety_notes.length
  ) {
    return false;
  }
  const regionIds = value.instructions.map((item) => item.region_id);
  const stableKeys = value.instructions.map((item) => item.stable_region_key);
  return (
    new Set(regionIds).size === regionIds.length &&
    new Set(stableKeys).size === stableKeys.length
  );
}

function isReviewEvent(value: unknown): value is PaintPlanReviewEvent {
  return (
    isPlainObject(value) &&
    hasExactKeys(value, reviewEventKeys) &&
    isUuid(value.id) &&
    isEnum(value.action, ["submit", "approve", "reject"] as const) &&
    (value.reason === null || isBoundedText(value.reason, 1, 1000, true)) &&
    (value.action !== "submit" || value.reason === null) &&
    (value.action !== "reject" || value.reason !== null) &&
    typeof value.actor_id === "string" &&
    typeof value.actor_display_name_snapshot === "string" &&
    isTimestamp(value.created_at)
  );
}

function hasExactStringItems(
  value: unknown,
  expected: readonly string[],
): value is string[] {
  return (
    Array.isArray(value) &&
    value.length === expected.length &&
    value.every((item, index) => item === expected[index])
  );
}

function isPlanActionList(
  value: unknown,
  lifecycle: PaintPlanLifecycle,
  isCurrent: boolean,
  stale: boolean,
): value is string[] {
  if (!isCurrent || stale || lifecycle === "superseded") {
    return hasExactStringItems(value, []);
  }
  if (hasExactStringItems(value, [])) {
    return true;
  }
  if (lifecycle === "generated" || lifecycle === "edited") {
    return hasExactStringItems(value, ["edit", "regenerate", "submit"]);
  }
  if (lifecycle === "approved" || lifecycle === "rejected") {
    return hasExactStringItems(value, ["edit", "regenerate"]);
  }
  return (
    lifecycle === "under_review" &&
    hasExactStringItems(value, ["approve", "reject"])
  );
}

function expectedPlanActions(
  plan: PaintPlan,
  accessRole: PaintPlanWorkbench["access_role"],
): readonly string[] {
  if (!plan.is_current || plan.stale || plan.lifecycle === "superseded") {
    return [];
  }
  if (accessRole === "reviewer") {
    return plan.lifecycle === "under_review" ? ["approve", "reject"] : [];
  }
  if (plan.lifecycle === "generated" || plan.lifecycle === "edited") {
    return ["edit", "regenerate", "submit"];
  }
  return plan.lifecycle === "approved" || plan.lifecycle === "rejected"
    ? ["edit", "regenerate"]
    : [];
}

function hasConsistentLatestReview(
  lifecycle: PaintPlanLifecycle,
  latestReview: PaintPlanReviewEvent | null,
): boolean {
  if (lifecycle === "generated" || lifecycle === "edited") {
    return latestReview === null;
  }
  if (lifecycle === "under_review") {
    return latestReview?.action === "submit";
  }
  if (lifecycle === "approved") {
    return latestReview?.action === "approve";
  }
  if (lifecycle === "rejected") {
    return latestReview?.action === "reject";
  }
  return (
    latestReview === null ||
    latestReview.action === "submit" ||
    latestReview.action === "approve" ||
    latestReview.action === "reject"
  );
}

function isPaintPlan(
  value: unknown,
  expectedProjectId?: string,
  expectedPlanId?: string,
): value is PaintPlan {
  return (
    isPlainObject(value) &&
    hasExactKeys(value, paintPlanKeys) &&
    isUuid(value.id) &&
    (expectedPlanId === undefined || value.id === expectedPlanId) &&
    isUuid(value.lineage_id) &&
    isUuid(value.paint_project_id) &&
    (expectedProjectId === undefined ||
      value.paint_project_id === expectedProjectId) &&
    isInteger(value.version, 1) &&
    isInteger(value.lineage_revision, 1) &&
    (value.parent_plan_id === null || isUuid(value.parent_plan_id)) &&
    (value.parent_plan_id === null || value.parent_plan_id !== value.id) &&
    isEnum(value.revision_kind, paintPlanRevisionKinds) &&
    ((value.revision_kind === "generated" &&
      value.lineage_id === value.id &&
      value.lineage_revision === 1 &&
      value.parent_plan_id === null) ||
      (value.revision_kind === "edited" &&
        value.lineage_id !== value.id &&
        value.lineage_revision >= 2 &&
        value.parent_plan_id !== null) ||
      (value.revision_kind === "regenerated" &&
        value.lineage_id === value.id &&
        value.lineage_revision === 1 &&
        value.parent_plan_id !== null)) &&
    isEnum(value.lifecycle, paintPlanLifecycles) &&
    isEnum(value.effective_lifecycle, paintPlanLifecycles) &&
    typeof value.is_current === "boolean" &&
    (!value.is_current || value.lifecycle !== "superseded") &&
    typeof value.stale === "boolean" &&
    isStringList(value.stale_reasons) &&
    new Set(value.stale_reasons).size === value.stale_reasons.length &&
    value.stale === (value.stale_reasons.length > 0) &&
    value.effective_lifecycle ===
      (!value.is_current || value.stale ? "superseded" : value.lifecycle) &&
    value.approval_valid ===
      (value.effective_lifecycle === "approved" && !value.stale) &&
    isUuid(value.source_invocation_id) &&
    isUuid(value.source_attempt_id) &&
    isSha256(value.source_image_set_fingerprint) &&
    isGovernedPlanSourceAssets(
      value.source_image_assets,
      typeof value.paint_project_id === "string" ? value.paint_project_id : "",
    ) &&
    isUuid(value.source_readiness_review_id) &&
    isInteger(value.source_readiness_review_version, 1) &&
    isUuid(value.source_region_set_id) &&
    isInteger(value.source_region_set_version, 1) &&
    isSha256(value.source_geometry_fingerprint) &&
    isUuid(value.provider_definition_id) &&
    isEnum(value.provider_key, ["fixture_local", "openai", "zhipu"] as const) &&
    isInteger(value.provider_revision_snapshot, 1) &&
    isUuid(value.model_definition_id) &&
    isBoundedText(value.model_id, 1, 160) &&
    isInteger(value.model_revision_snapshot, 1) &&
    (value.provider_pricing_snapshot_id === null ||
      isUuid(value.provider_pricing_snapshot_id)) &&
    isUuid(value.prompt_template_id) &&
    value.prompt_template_key === "paint-plan" &&
    isInteger(value.prompt_version, 1) &&
    isSha256(value.prompt_hash) &&
    isEnum(value.generation_locale, ["zh-CN", "en-US"] as const) &&
    value.schema_version === "paint-plan.v1" &&
    isSha256(value.content_hash) &&
    documentCitationsBelongToContext(value.document, value.retrieved_context) &&
    isEnum(
      value.provider_request_id_status,
      ["absent", "provided", "unavailable"] as const,
    ) &&
    (value.provider_request_id === null ||
      isBoundedText(value.provider_request_id, 1, 200)) &&
    ((value.provider_request_id_status === "provided" &&
      value.provider_request_id !== null) ||
      (value.provider_request_id_status !== "provided" &&
        value.provider_request_id === null)) &&
    isEnum(value.usage_measurement_status, ["measured", "unavailable"] as const) &&
    (value.input_units === null || isInteger(value.input_units, 0)) &&
    (value.output_units === null || isInteger(value.output_units, 0)) &&
    ((value.usage_measurement_status === "measured" &&
      value.input_units !== null &&
      value.output_units !== null) ||
      (value.usage_measurement_status === "unavailable" &&
        value.input_units === null &&
        value.output_units === null)) &&
    isEnum(
      value.cost_measurement_status,
      ["estimated", "measured", "unavailable"] as const,
    ) &&
    (value.cost_minor_units === null || isInteger(value.cost_minor_units, 0)) &&
    ((value.cost_measurement_status === "unavailable" &&
      value.cost_minor_units === null) ||
      (value.cost_measurement_status !== "unavailable" &&
        value.cost_minor_units !== null)) &&
    isEnum(value.cost_currency, ["FIXTURE_CREDITS", "USD", "CNY"] as const) &&
    (value.latest_review === null || isReviewEvent(value.latest_review)) &&
    hasConsistentLatestReview(value.lifecycle, value.latest_review) &&
    isPlanActionList(
      value.allowed_actions,
      value.lifecycle,
      value.is_current,
      value.stale,
    ) &&
    isUuid(value.requested_by_user_id) &&
    isTimestamp(value.invocation_created_at) &&
    isEnum(value.created_by_actor_type, ["provider", "user"] as const) &&
    ((value.revision_kind === "edited" &&
      value.created_by_actor_type === "user") ||
      (value.revision_kind !== "edited" &&
        value.created_by_actor_type === "provider")) &&
    ((value.provider_key === "fixture_local" &&
      value.cost_currency === "FIXTURE_CREDITS") ||
      (value.provider_key === "openai" && value.cost_currency === "USD") ||
      (value.provider_key === "zhipu" && value.cost_currency === "CNY")) &&
    (value.provider_key !== "fixture_local" ||
      (value.provider_pricing_snapshot_id === null &&
        value.provider_request_id_status === "absent" &&
        value.provider_request_id === null)) &&
    typeof value.created_by_actor_id === "string" &&
    typeof value.created_by_actor_display_name_snapshot === "string" &&
    isTimestamp(value.created_at)
  );
}

function hasLinkedPlanCollection(
  plans: PaintPlan[],
  projectId: string,
): boolean {
  const ids = new Set(plans.map((plan) => plan.id));
  const versions = new Set(plans.map((plan) => plan.version));
  if (
    ids.size !== plans.length ||
    versions.size !== plans.length ||
    plans.some((plan) => plan.paint_project_id !== projectId) ||
    plans.filter((plan) => plan.is_current).length > 1
  ) {
    return false;
  }
  if (plans.length === 0) {
    return true;
  }
  const root = plans[plans.length - 1];
  const currentIndex = plans.findIndex((plan) => plan.is_current);
  if (
    root === undefined ||
    root.version !== 1 ||
    root.revision_kind !== "generated" ||
    root.parent_plan_id !== null ||
    currentIndex !== 0 ||
    plans.some((plan, index) => plan.version !== plans.length - index)
  ) {
    return false;
  }
  const lineageRevisions = new Set(
    plans.map((plan) => `${plan.lineage_id}:${plan.lineage_revision}`),
  );
  if (lineageRevisions.size !== plans.length) {
    return false;
  }
  return plans.every((plan) => {
    if (plan.parent_plan_id !== null) {
      const parent = plans.find((item) => item.id === plan.parent_plan_id);
      if (parent === undefined || parent.version !== plan.version - 1) {
        return false;
      }
      if (
        (plan.revision_kind === "edited" &&
          (parent.lineage_id !== plan.lineage_id ||
            parent.lineage_revision + 1 !== plan.lineage_revision ||
            !hasInheritedEditProvenance(plan, parent))) ||
        (plan.revision_kind === "regenerated" &&
          parent.lineage_id === plan.lineage_id)
      ) {
        return false;
      }
    } else if (plan.version !== 1) {
      return false;
    }
    if (plan.revision_kind === "edited") {
      const lineageRoot = plans.find((item) => item.id === plan.lineage_id);
      return (
        lineageRoot !== undefined &&
        lineageRoot.lineage_id === lineageRoot.id &&
        lineageRoot.version < plan.version
      );
    }
    return true;
  });
}

function isHistory(
  value: unknown,
  expectedProjectId: string,
): value is PaintPlanHistory {
  return (
    isPlainObject(value) &&
    hasExactKeys(value, ["items"]) &&
    Array.isArray(value.items) &&
    value.items.every((plan) => isPaintPlan(plan, expectedProjectId)) &&
    hasLinkedPlanCollection(value.items, expectedProjectId)
  );
}

function isPlanLinkedToWorkbench(
  plan: PaintPlan,
  workbench: Pick<
    PaintPlanWorkbench,
    | "image_assets"
    | "image_set_fingerprint"
    | "image_set_status"
    | "providers"
    | "readiness_review_id"
    | "region_set"
  >,
): boolean {
  const provider = workbench.providers.find(
    (item) => item.id === plan.provider_definition_id,
  );
  const model = provider?.models.find(
    (item) => item.id === plan.model_definition_id,
  );
  if (
    provider === undefined ||
    model === undefined ||
    provider.provider_key !== plan.provider_key ||
    model.model_id !== plan.model_id
  ) {
    return false;
  }
  const regionSet = workbench.region_set;
  const knownSourceMismatch =
    workbench.image_set_status !== "ready" ||
    plan.source_image_set_fingerprint !== workbench.image_set_fingerprint ||
    plan.source_readiness_review_id !== workbench.readiness_review_id ||
    regionSet === null ||
    plan.source_region_set_id !== regionSet.id ||
    plan.source_region_set_version !== regionSet.version ||
    plan.source_geometry_fingerprint !== regionSet.geometry_fingerprint;
  if (knownSourceMismatch && !plan.stale) {
    return false;
  }
  if (plan.source_image_set_fingerprint === workbench.image_set_fingerprint) {
    const currentAssets = [...workbench.image_assets].sort((left, right) =>
      left.id.localeCompare(right.id),
    );
    const sourceAssets = [...plan.source_image_assets].sort((left, right) =>
      left.id.localeCompare(right.id),
    );
    if (
      currentAssets.length !== sourceAssets.length ||
      currentAssets.some(
        (asset, index) => !hasEqualJsonValue(asset, sourceAssets[index]),
      )
    ) {
      return false;
    }
  }
  if (
    regionSet === null ||
    plan.source_region_set_id !== regionSet.id ||
    plan.source_region_set_version !== regionSet.version ||
    plan.source_geometry_fingerprint !== regionSet.geometry_fingerprint
  ) {
    return true;
  }
  const governedPaintRegions = regionSet.regions
    .filter((region) => region.kind === "paint")
    .map((region) =>
      JSON.stringify([region.id, region.stable_region_key, region.label]),
    )
    .sort();
  const instructionRegions = plan.document.instructions
    .map((instruction) =>
      JSON.stringify([
        instruction.region_id,
        instruction.stable_region_key,
        instruction.region_label,
      ]),
    )
    .sort();
  return (
    governedPaintRegions.length === instructionRegions.length &&
    governedPaintRegions.every(
      (identity, index) => identity === instructionRegions[index],
    )
  );
}

function hasInheritedEditProvenance(
  edited: PaintPlan,
  parent: PaintPlan,
): boolean {
  const inheritedKeys = [
    "paint_project_id",
    "source_invocation_id",
    "source_attempt_id",
    "source_image_set_fingerprint",
    "source_image_assets",
    "source_readiness_review_id",
    "source_readiness_review_version",
    "source_region_set_id",
    "source_region_set_version",
    "source_geometry_fingerprint",
    "provider_definition_id",
    "provider_key",
    "provider_revision_snapshot",
    "model_definition_id",
    "model_id",
    "model_revision_snapshot",
    "provider_pricing_snapshot_id",
    "prompt_template_id",
    "prompt_template_key",
    "prompt_version",
    "prompt_hash",
    "generation_locale",
    "schema_version",
    "provider_request_id_status",
    "provider_request_id",
    "usage_measurement_status",
    "input_units",
    "output_units",
    "cost_measurement_status",
    "cost_minor_units",
    "cost_currency",
    "requested_by_user_id",
    "invocation_created_at",
  ] as const satisfies readonly (keyof PaintPlan)[];
  return (
    edited.lineage_id === parent.lineage_id &&
    edited.lineage_revision === parent.lineage_revision + 1 &&
    inheritedKeys.every((key) =>
      hasEqualJsonValue(edited[key], parent[key]),
    )
  );
}

function hasExpectedSelectionProjection(
  plan: PaintPlan,
  expected: PaintPlanExpectedSelectionProjection,
): boolean {
  const actualAssets = [...plan.source_image_assets].sort((left, right) =>
    left.id.localeCompare(right.id),
  );
  const expectedAssets = [...expected.source_image_assets].sort((left, right) =>
    left.id.localeCompare(right.id),
  );
  return (
    plan.provider_key === expected.provider_key &&
    plan.model_id === expected.model_id &&
    plan.source_region_set_id === expected.region_set.id &&
    plan.source_region_set_version === expected.region_set.version &&
    plan.source_geometry_fingerprint ===
      expected.region_set.geometry_fingerprint &&
    actualAssets.length === expectedAssets.length &&
    actualAssets.every((asset, index) =>
      hasEqualJsonValue(asset, expectedAssets[index]),
    ) &&
    (() => {
      const expectedRegions = expected.region_set.regions
        .filter((region) => region.kind === "paint")
        .map((region) =>
          JSON.stringify([region.id, region.stable_region_key, region.label]),
        )
        .sort();
      const instructionRegions = plan.document.instructions
        .map((instruction) =>
          JSON.stringify([
            instruction.region_id,
            instruction.stable_region_key,
            instruction.region_label,
          ]),
        )
        .sort();
      return (
        expectedRegions.length === instructionRegions.length &&
        expectedRegions.every(
          (identity, index) => identity === instructionRegions[index],
        )
      );
    })()
  );
}

function isWorkbench(
  value: unknown,
  expectedProjectId: string,
): value is PaintPlanWorkbench {
  if (
    !isPlainObject(value) ||
    !hasExactKeys(value, workbenchKeys) ||
    !isUuid(value.paint_project_id) ||
    value.paint_project_id !== expectedProjectId
  ) {
    return false;
  }
  const projectId = value.paint_project_id;
  if (
    !isEnum(value.access_role, ["owner", "reviewer"] as const) ||
    typeof value.image_set_status !== "string" ||
    (value.image_set_fingerprint !== null &&
      !isSha256(value.image_set_fingerprint)) ||
    (value.readiness_review_id !== null &&
      !isUuid(value.readiness_review_id)) ||
    !isArrayOf(value.image_assets, (asset): asset is PaintPlanImageAsset =>
      isImageAsset(asset, projectId),
    ) ||
    value.image_assets.length > 4 ||
    (value.region_set !== null && !isRegionSet(value.region_set)) ||
    typeof value.source_ready !== "boolean" ||
    !isStringList(value.blockers) ||
    !isArrayOf(value.providers, isProviderChoice) ||
    !isArrayOf(value.credentials, isCredentialChoice) ||
    (value.current_plan !== null &&
      !isPaintPlan(value.current_plan, expectedProjectId)) ||
    !isArrayOf(value.history, (plan): plan is PaintPlan =>
      isPaintPlan(plan, expectedProjectId),
    ) ||
    !isStringList(value.allowed_actions)
  ) {
    return false;
  }
  const accessRole = value.access_role as PaintPlanWorkbench["access_role"];
  const currentPlan = value.current_plan;
  const history = value.history;
  const providers = value.providers;
  const credentials = value.credentials;
  const providerIds = providers.map((provider) => provider.id);
  const providerKeys = providers.map((provider) => provider.provider_key);
  const modelIds = providers.flatMap((provider) =>
    provider.models.map((model) => model.id),
  );
  const credentialIds = credentials.map((credential) => credential.id);
  const imageAssets = value.image_assets;
  const imageAssetIds = imageAssets.map((asset) => asset.id);
  const imageAssetRoles = imageAssets.map((asset) => asset.role);
  if (
    new Set(providerIds).size !== providerIds.length ||
    new Set(providerKeys).size !== providerKeys.length ||
    new Set(modelIds).size !== modelIds.length ||
    new Set(credentialIds).size !== credentialIds.length ||
    new Set(imageAssetIds).size !== imageAssetIds.length ||
    new Set(imageAssetRoles).size !== imageAssetRoles.length ||
    credentials.some(
      (credential) =>
        !providers.some(
          (provider) => provider.provider_key === credential.provider_key,
        ),
    ) ||
    new Set(value.allowed_actions).size !== value.allowed_actions.length
  ) {
    return false;
  }
  if (
    (!value.source_ready && value.blockers.length === 0) ||
    value.source_ready &&
    (value.image_set_status !== "ready" ||
      value.image_set_fingerprint === null ||
      value.readiness_review_id === null ||
      imageAssets.length < 3 ||
      imageAssets.length > 4 ||
      value.region_set === null ||
      value.region_set.effective_lifecycle !== "approved" ||
      value.region_set.stale ||
      !requiredPaintPlanImageRoles.every((role) =>
        imageAssets.some((asset) => asset.role === role),
      ) ||
      imageAssets.some(
        (asset) =>
          asset.upload_validation_result !== "accepted" ||
          asset.rights_attestation_status !== "confirmed",
      ) ||
      !value.region_set.regions.some((region) => region.kind === "paint"))
  ) {
    return false;
  }
  const canPreview = value.allowed_actions.includes("preview");
  const canGenerate = value.allowed_actions.includes("generate");
  const canRegenerate = value.allowed_actions.includes("regenerate");
  const expectedWorkbenchActions = ["read_history"];
  if (
    value.access_role === "owner" &&
    value.source_ready &&
    value.blockers.length === 0
  ) {
    expectedWorkbenchActions.push(
      "preview",
      currentPlan === null ? "generate" : "regenerate",
    );
  }
  if (
    !hasExactStringItems(value.allowed_actions, expectedWorkbenchActions) ||
    !history.every((plan) =>
      hasExactStringItems(
        plan.allowed_actions,
        expectedPlanActions(plan, accessRole),
      ),
    ) ||
    (currentPlan !== null &&
      !hasExactStringItems(
        currentPlan.allowed_actions,
        expectedPlanActions(currentPlan, accessRole),
      )) ||
    ((canPreview || canGenerate || canRegenerate) &&
      (value.access_role !== "owner" ||
        !value.source_ready ||
        value.blockers.length > 0)) ||
    ((canGenerate || canRegenerate) && !canPreview) ||
    (canGenerate && canRegenerate) ||
    (canGenerate && currentPlan !== null) ||
    (canRegenerate && currentPlan === null)
  ) {
    return false;
  }
  const planLinkSource = {
    image_assets: value.image_assets,
    image_set_fingerprint: value.image_set_fingerprint,
    image_set_status: value.image_set_status,
    providers,
    readiness_review_id: value.readiness_review_id,
    region_set: value.region_set,
  };
  if (!hasLinkedPlanCollection(history, expectedProjectId)) {
    return false;
  }
  if (currentPlan === null) {
    if (history.some((plan) => plan.is_current)) {
      return false;
    }
  } else if (
    !currentPlan.is_current ||
    !history.some((plan) => hasEqualJsonValue(plan, currentPlan)) ||
    !isPlanLinkedToWorkbench(currentPlan, planLinkSource)
  ) {
    return false;
  }
  return history.every((plan) =>
    isPlanLinkedToWorkbench(plan, planLinkSource),
  );
}

interface PaintPlanErrorEnvelope {
  error_code: string;
  category: (typeof errorCategories)[number];
  message: string;
  request_id: string;
  retryable: boolean;
  current_state: string | null;
  allowed_actions: string[];
  safe_details: PaintPlanSafeDetails;
}

function isErrorEnvelope(value: unknown): value is PaintPlanErrorEnvelope {
  return (
    isPlainObject(value) &&
    hasExactKeys(value, errorEnvelopeKeys) &&
    typeof value.error_code === "string" &&
    isEnum(value.category, errorCategories) &&
    typeof value.message === "string" &&
    typeof value.retryable === "boolean" &&
    isUuid(value.request_id) &&
    (value.current_state === null || typeof value.current_state === "string") &&
    isStringList(value.allowed_actions) &&
    isPaintPlanSafeDetails(
      value.safe_details,
      value.error_code,
      value.category,
    )
  );
}

export type PaintPlanApiErrorKind =
  | "aborted"
  | "conflict"
  | "internal"
  | "invalid_response"
  | "network"
  | "not_found"
  | "provider"
  | "unavailable"
  | "validation";

export class PaintPlanApiError extends Error {
  readonly allowedActions: string[];
  readonly currentState: string | null;
  readonly errorCode: string | null;
  readonly kind: PaintPlanApiErrorKind;
  readonly retryable: boolean;
  readonly safeDetails: PaintPlanSafeDetails;
  readonly status: number | null;

  constructor(
    kind: PaintPlanApiErrorKind,
    message: string,
    options: {
      allowedActions?: string[];
      currentState?: string | null;
      errorCode?: string;
      retryable?: boolean;
      safeDetails?: PaintPlanSafeDetails;
      status?: number;
    } = {},
  ) {
    super(message);
    this.name = "PaintPlanApiError";
    this.kind = kind;
    this.allowedActions = options.allowedActions ?? [];
    this.currentState = options.currentState ?? null;
    this.errorCode = options.errorCode ?? null;
    this.retryable = options.retryable ?? false;
    this.safeDetails = options.safeDetails ?? {};
    this.status = options.status ?? null;
  }
}

async function readJson(response: Response): Promise<unknown> {
  let text: string;
  try {
    text = await response.text();
  } catch {
    throw new PaintPlanApiError(
      "invalid_response",
      "The Paint Plan service returned an unreadable response.",
      { retryable: true, status: response.status },
    );
  }
  try {
    return JSON.parse(text) as unknown;
  } catch {
    throw new PaintPlanApiError(
      "invalid_response",
      "The Paint Plan service returned an unreadable response.",
      { retryable: true, status: response.status },
    );
  }
}

function errorFromResponse(
  response: Response,
  envelope: PaintPlanErrorEnvelope,
): PaintPlanApiError {
  const options = {
    allowedActions: envelope.allowed_actions,
    currentState: envelope.current_state,
    errorCode: envelope.error_code,
    retryable: envelope.retryable,
    safeDetails: envelope.safe_details,
    status: response.status,
  };
  if (response.status === 404) {
    return new PaintPlanApiError(
      "not_found",
      "The project or Paint Plan is not available to this operator.",
      options,
    );
  }
  if (response.status === 409) {
    return new PaintPlanApiError(
      "conflict",
      "The governed source, exact revision, or command state changed.",
      options,
    );
  }
  if (response.status === 403 || response.status === 422) {
    return new PaintPlanApiError(
      "validation",
      "The Paint Plan command is not allowed by the current server state.",
      options,
    );
  }
  if (response.status === 503 || envelope.category === "DATABASE_UNAVAILABLE") {
    return new PaintPlanApiError(
      "unavailable",
      "The Paint Plan service is temporarily unavailable.",
      options,
    );
  }
  if (
    response.status === 502 ||
    envelope.category === "PROVIDER_TIMEOUT" ||
    envelope.category === "PROVIDER_RATE_LIMIT" ||
    envelope.category === "PROVIDER_RESPONSE_INVALID" ||
    envelope.category === "SCHEMA_VALIDATION_ERROR"
  ) {
    return new PaintPlanApiError(
      "provider",
      "The provider attempt did not produce a confirmed valid Paint Plan.",
      options,
    );
  }
  return new PaintPlanApiError(
    "internal",
    "The Paint Plan service could not complete this request.",
    options,
  );
}

async function requestJson<T>(
  input: RequestInfo | URL,
  init: RequestInit,
  expectedStatus: number,
  validator: (value: unknown) => value is T,
): Promise<T> {
  let response: Response;
  try {
    response = await fetchWithCsrf(input, init);
  } catch {
    if (init.signal?.aborted) {
      throw new PaintPlanApiError("aborted", "The Paint Plan request was cancelled.");
    }
    throw new PaintPlanApiError(
      "network",
      "The PaintPilot Paint Plan API could not be reached.",
      { retryable: true },
    );
  }
  const payload = await readJson(response);
  if (response.status === expectedStatus) {
    if (containsForbiddenResponseData(payload) || !validator(payload)) {
      throw new PaintPlanApiError(
        "invalid_response",
        "The Paint Plan service returned an unexpected response.",
        { retryable: true, status: response.status },
      );
    }
    return payload;
  }
  if (!isErrorEnvelope(payload)) {
    throw new PaintPlanApiError(
      "invalid_response",
      "The Paint Plan service returned an unexpected response.",
      { retryable: true, status: response.status },
    );
  }
  throw errorFromResponse(response, payload);
}

function assertUuid(value: string, message: string): void {
  if (!isUuid(value)) {
    throw new PaintPlanApiError("validation", message);
  }
}

function assertRequestShape(value: unknown, expectedKeys: readonly string[]): void {
  if (
    !isPlainObject(value) ||
    !hasExactKeys(value, expectedKeys) ||
    containsForbiddenResponseData(value)
  ) {
    throw new PaintPlanApiError(
      "validation",
      "The Paint Plan request does not match the strict command contract.",
    );
  }
}

function assertSelection(input: PaintPlanSelectionInput): void {
  if (
    !isSha256(input.image_set_fingerprint) ||
    !isUuid(input.region_set_id) ||
    !isUuid(input.provider_definition_id) ||
    !isUuid(input.model_definition_id) ||
    !isUuid(input.credential_id) ||
    !isEnum(input.generation_locale, ["zh-CN", "en-US"] as const) ||
    (input.intent !== null && !isRequestText(input.intent, 1, 1200))
  ) {
    throw new PaintPlanApiError(
      "validation",
      "The governed source and model selection is invalid.",
    );
  }
}

function assertRevision(input: PaintPlanRevisionInput): void {
  if (
    !isUuid(input.expected_current_plan_id) ||
    !isInteger(input.expected_current_version, 1)
  ) {
    throw new PaintPlanApiError(
      "validation",
      "The expected current Paint Plan revision is invalid.",
    );
  }
}

function mutationHeaders(idempotencyKey: string): HeadersInit {
  assertUuid(idempotencyKey, "A protected Paint Plan command could not be started.");
  return {
    Accept: "application/json",
    "Content-Type": "application/json",
    "Idempotency-Key": idempotencyKey,
  };
}

export function createPaintPlanIdempotencyKey(): string {
  const key = globalThis.crypto.randomUUID();
  assertUuid(key, "A protected Paint Plan command could not be started.");
  return key;
}

export function stablePaintPlanIdempotencyKey(
  existingKey: string | null | undefined,
): string {
  if (existingKey !== null && existingKey !== undefined) {
    assertUuid(existingKey, "The protected Paint Plan command identifier is invalid.");
    return existingKey;
  }
  return createPaintPlanIdempotencyKey();
}

export async function getPaintPlanWorkbench(
  projectId: string,
  signal?: AbortSignal,
): Promise<PaintPlanWorkbench> {
  assertUuid(projectId, "The project address is invalid.");
  return requestJson(
    `/api/v1/paint-projects/${encodeURIComponent(projectId)}/paint-plans/workbench`,
    { method: "GET", headers: { Accept: "application/json" }, signal },
    200,
    (value): value is PaintPlanWorkbench => isWorkbench(value, projectId),
  );
}

export async function previewPaintPlan(
  projectId: string,
  input: PaintPlanSelectionInput,
  signal?: AbortSignal,
): Promise<PaintPlanPreview> {
  assertUuid(projectId, "The project address is invalid.");
  assertRequestShape(input, selectionInputKeys);
  assertSelection(input);
  return requestJson(
    `/api/v1/paint-projects/${encodeURIComponent(projectId)}/paint-plans/preview`,
    {
      method: "POST",
      headers: { Accept: "application/json", "Content-Type": "application/json" },
      body: JSON.stringify(input),
      signal,
    },
    200,
    isPreview,
  );
}

export async function generatePaintPlan(
  projectId: string,
  input: PaintPlanGenerateInput,
  expectedSelection: PaintPlanExpectedSelectionProjection,
  idempotencyKey: string,
  signal?: AbortSignal,
): Promise<PaintPlan> {
  assertUuid(projectId, "The project address is invalid.");
  assertRequestShape(input, generateInputKeys);
  assertSelection(input);
  if (input.confirm_generation !== true || !isInteger(input.max_attempts, 1, 3)) {
    throw new PaintPlanApiError("validation", "The generation confirmation is invalid.");
  }
  return requestJson(
    `/api/v1/paint-projects/${encodeURIComponent(projectId)}/paint-plans/generate`,
    {
      method: "POST",
      headers: mutationHeaders(idempotencyKey),
      body: JSON.stringify(input),
      signal,
    },
    201,
    (value): value is PaintPlan =>
      isPaintPlan(value, projectId) &&
      value.revision_kind === "generated" &&
      value.version === 1 &&
      value.parent_plan_id === null &&
      value.source_image_set_fingerprint === input.image_set_fingerprint &&
      value.source_region_set_id === input.region_set_id &&
      value.provider_definition_id === input.provider_definition_id &&
      value.model_definition_id === input.model_definition_id &&
      hasExpectedSelectionProjection(value, expectedSelection),
  );
}

export async function editPaintPlan(
  projectId: string,
  planId: string,
  input: PaintPlanEditInput,
  expectedParent: PaintPlan,
  idempotencyKey: string,
  signal?: AbortSignal,
): Promise<PaintPlan> {
  assertUuid(projectId, "The project address is invalid.");
  assertUuid(planId, "The Paint Plan address is invalid.");
  assertRequestShape(input, editInputKeys);
  assertRevision(input);
  if (
    input.expected_current_plan_id !== planId ||
    expectedParent.id !== planId ||
    expectedParent.paint_project_id !== projectId ||
    expectedParent.version !== input.expected_current_version ||
    !isPaintPlan(expectedParent, projectId, planId)
  ) {
    throw new PaintPlanApiError(
      "validation",
      "The edit target does not match the expected current Paint Plan.",
    );
  }
  if (!isRequestDocument(input.document)) {
    throw new PaintPlanApiError("validation", "The structured Paint Plan is invalid.");
  }
  return requestJson(
    `/api/v1/paint-projects/${encodeURIComponent(projectId)}/paint-plans/${encodeURIComponent(planId)}/edits`,
    {
      method: "POST",
      headers: mutationHeaders(idempotencyKey),
      body: JSON.stringify(input),
      signal,
    },
    201,
    (value): value is PaintPlan =>
      isPaintPlan(value, projectId) &&
      value.id !== planId &&
      value.revision_kind === "edited" &&
      value.parent_plan_id === planId &&
      value.version === input.expected_current_version + 1 &&
      hasInheritedEditProvenance(value, expectedParent) &&
      hasEqualJsonValue(
        value.document,
        normalizedRequestDocument(input.document),
      ),
  );
}

async function revisePaintPlan(
  projectId: string,
  planId: string,
  action: "submit" | "approve" | "reject",
  input: PaintPlanRevisionInput | PaintPlanReviewInput,
  idempotencyKey: string,
  signal?: AbortSignal,
): Promise<PaintPlan> {
  assertUuid(projectId, "The project address is invalid.");
  assertUuid(planId, "The Paint Plan address is invalid.");
  assertRequestShape(
    input,
    action === "submit" ? revisionInputKeys : reviewInputKeys,
  );
  assertRevision(input);
  if (input.expected_current_plan_id !== planId) {
    throw new PaintPlanApiError(
      "validation",
      "The review target does not match the expected current Paint Plan.",
    );
  }
  if (
    "reason" in input &&
    input.reason !== null &&
    !isRequestText(input.reason, 1, 1000, true)
  ) {
    throw new PaintPlanApiError("validation", "The review reason is invalid.");
  }
  if (action === "reject" && (!("reason" in input) || input.reason === null)) {
    throw new PaintPlanApiError("validation", "A rejection reason is required.");
  }
  const expectedReviewReason =
    action === "submit" || !("reason" in input) || input.reason === null
      ? null
      : normalizedRequestText(input.reason);
  return requestJson(
    `/api/v1/paint-projects/${encodeURIComponent(projectId)}/paint-plans/${encodeURIComponent(planId)}/${action}`,
    {
      method: "POST",
      headers: mutationHeaders(idempotencyKey),
      body: JSON.stringify(input),
      signal,
    },
    201,
    (value): value is PaintPlan => {
      if (
        !isPaintPlan(value, projectId, planId) ||
        value.version !== input.expected_current_version
      ) {
        return false;
      }
      if (action === "approve" || action === "reject") {
        const expectedLifecycle = action === "approve" ? "approved" : "rejected";
        return (
          (value.lifecycle === expectedLifecycle ||
            value.lifecycle === "superseded") &&
          value.latest_review?.action === action &&
          value.latest_review.reason === expectedReviewReason
        );
      }
      return (
        (value.lifecycle === "under_review" &&
          value.latest_review?.action === "submit" &&
          value.latest_review.reason === null) ||
        (value.lifecycle === "approved" &&
          value.latest_review?.action === "approve") ||
        (value.lifecycle === "rejected" &&
          value.latest_review?.action === "reject") ||
        (value.lifecycle === "superseded" &&
          (value.latest_review?.action === "submit" ||
            value.latest_review?.action === "approve" ||
            value.latest_review?.action === "reject"))
      );
    },
  );
}

export function submitPaintPlan(
  projectId: string,
  planId: string,
  input: PaintPlanRevisionInput,
  idempotencyKey: string,
  signal?: AbortSignal,
): Promise<PaintPlan> {
  return revisePaintPlan(projectId, planId, "submit", input, idempotencyKey, signal);
}

export function approvePaintPlan(
  projectId: string,
  planId: string,
  input: PaintPlanReviewInput,
  idempotencyKey: string,
  signal?: AbortSignal,
): Promise<PaintPlan> {
  return revisePaintPlan(projectId, planId, "approve", input, idempotencyKey, signal);
}

export function rejectPaintPlan(
  projectId: string,
  planId: string,
  input: PaintPlanReviewInput,
  idempotencyKey: string,
  signal?: AbortSignal,
): Promise<PaintPlan> {
  return revisePaintPlan(projectId, planId, "reject", input, idempotencyKey, signal);
}

export async function regeneratePaintPlan(
  projectId: string,
  planId: string,
  input: PaintPlanRegenerateInput,
  expectedSelection: PaintPlanExpectedSelectionProjection,
  idempotencyKey: string,
  signal?: AbortSignal,
): Promise<PaintPlan> {
  assertUuid(projectId, "The project address is invalid.");
  assertUuid(planId, "The Paint Plan address is invalid.");
  assertRequestShape(input, regenerateInputKeys);
  assertRevision(input);
  if (input.expected_current_plan_id !== planId) {
    throw new PaintPlanApiError(
      "validation",
      "The regeneration target does not match the expected current Paint Plan.",
    );
  }
  assertSelection(input);
  if (input.confirm_generation !== true || !isInteger(input.max_attempts, 1, 3)) {
    throw new PaintPlanApiError("validation", "The regeneration confirmation is invalid.");
  }
  return requestJson(
    `/api/v1/paint-projects/${encodeURIComponent(projectId)}/paint-plans/${encodeURIComponent(planId)}/regenerate`,
    {
      method: "POST",
      headers: mutationHeaders(idempotencyKey),
      body: JSON.stringify(input),
      signal,
    },
    201,
    (value): value is PaintPlan =>
      isPaintPlan(value, projectId) &&
      value.id !== planId &&
      value.revision_kind === "regenerated" &&
      value.parent_plan_id === planId &&
      value.version === input.expected_current_version + 1 &&
      value.lineage_revision === 1 &&
      value.source_image_set_fingerprint === input.image_set_fingerprint &&
      value.source_region_set_id === input.region_set_id &&
      value.provider_definition_id === input.provider_definition_id &&
      value.model_definition_id === input.model_definition_id &&
      hasExpectedSelectionProjection(value, expectedSelection),
  );
}

export async function getPaintPlan(
  projectId: string,
  planId: string,
  signal?: AbortSignal,
): Promise<PaintPlan> {
  assertUuid(projectId, "The project address is invalid.");
  assertUuid(planId, "The Paint Plan address is invalid.");
  return requestJson(
    `/api/v1/paint-projects/${encodeURIComponent(projectId)}/paint-plans/${encodeURIComponent(planId)}`,
    { method: "GET", headers: { Accept: "application/json" }, signal },
    200,
    (value): value is PaintPlan => isPaintPlan(value, projectId, planId),
  );
}

export async function getPaintPlanHistory(
  projectId: string,
  signal?: AbortSignal,
): Promise<PaintPlanHistory> {
  assertUuid(projectId, "The project address is invalid.");
  return requestJson(
    `/api/v1/paint-projects/${encodeURIComponent(projectId)}/paint-plans`,
    { method: "GET", headers: { Accept: "application/json" }, signal },
    200,
    (value): value is PaintPlanHistory => isHistory(value, projectId),
  );
}
