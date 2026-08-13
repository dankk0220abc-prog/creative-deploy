import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router";

import { phase3aFixtureEnabled } from "../api/aiFoundation";
import { isPaintProjectId } from "../api/paintProjects";
import {
  approvePaintPlan,
  editPaintPlan,
  generatePaintPlan,
  getPaintPlanWorkbench,
  PaintPlanApiError,
  type PaintPlan,
  type PaintPlanApiErrorKind,
  type PaintPlanDocument,
  type PaintPlanProviderChoice,
  type PaintPlanReviewEvent,
  type PaintPlanSelectionInput,
  type PaintPlanWorkbench,
  previewPaintPlan,
  type PaintPlanPreview,
  regeneratePaintPlan,
  rejectPaintPlan,
  stablePaintPlanIdempotencyKey,
  submitPaintPlan,
} from "../api/paintPlans";
import { FeedbackPanel } from "../components/FeedbackPanel";
import { useAppTranslation } from "../i18n";
import { formatProjectTimestamp } from "../utils/format";

type WorkbenchState =
  | { status: "error"; error: PaintPlanApiError; projectId: string }
  | { status: "loading"; projectId: string }
  | { status: "ready"; projectId: string; workbench: PaintPlanWorkbench };

type CommandState =
  | { status: "idle"; noticeKey: string | null }
  | { status: "busy"; labelKey: string }
  | { status: "error"; error: PaintPlanApiError; labelKey: string };

interface SelectionState {
  projectId: string;
  providerId: string;
  modelId: string;
  credentialId: string;
  intent: string;
}

interface PaintPlanPreviewSnapshot {
  identity: string;
  value: PaintPlanPreview;
}

interface PaintPlanEditDraft {
  basePlanId: string;
  baseVersion: number;
  document: PaintPlanDocument;
  projectId: string;
}

interface PaintPlanReviewReasonDraft {
  basePlanId: string;
  baseVersion: number;
  projectId: string;
  value: string;
}

type EditableInstructionField =
  | "target_color"
  | "preparation"
  | "base_coat"
  | "layer_strategy"
  | "edge_treatment"
  | "lighting_guidance"
  | "material_guidance";

const instructionFields: readonly {
  key: EditableInstructionField;
  labelKey: string;
  maximumLength: number;
}[] = [
  { key: "target_color", labelKey: "paintPlan.field.targetColor", maximumLength: 120 },
  { key: "preparation", labelKey: "paintPlan.field.preparation", maximumLength: 600 },
  { key: "base_coat", labelKey: "paintPlan.field.baseCoat", maximumLength: 600 },
  { key: "layer_strategy", labelKey: "paintPlan.field.layerStrategy", maximumLength: 1000 },
  { key: "edge_treatment", labelKey: "paintPlan.field.edgeTreatment", maximumLength: 600 },
  { key: "lighting_guidance", labelKey: "paintPlan.field.lighting", maximumLength: 600 },
  { key: "material_guidance", labelKey: "paintPlan.field.material", maximumLength: 600 },
];

const knownBlockerKeys: Readonly<Record<string, string>> = {
  authenticated_user_required: "paintPlan.blocker.authenticatedUserRequired",
  image_assets_incomplete: "paintPlan.blocker.imageAssetsIncomplete",
  image_set_fingerprint_changed: "paintPlan.blocker.imageSetChanged",
  image_set_readiness_review_changed:
    "paintPlan.blocker.readinessReviewChanged",
  image_set_incomplete: "paintPlan.blocker.imageSetNotReady",
  image_set_not_ready: "paintPlan.blocker.imageSetNotReady",
  image_set_stale: "paintPlan.blocker.imageSetChanged",
  live_execution_authorization_required: "paintPlan.blocker.liveAuthorization",
  owner_required: "paintPlan.blocker.ownerRequired",
  paint_regions_missing: "paintPlan.blocker.paintRegionsMissing",
  prompt_template_unavailable: "paintPlan.blocker.promptUnavailable",
  provider_disabled: "paintPlan.blocker.providerUnavailable",
  provider_model_not_found: "paintPlan.blocker.providerUnavailable",
  provider_unsupported: "paintPlan.blocker.providerUnavailable",
  project_abandoned: "paintPlan.blocker.projectAbandoned",
  primary_front_changed: "paintPlan.blocker.regionSetChanged",
  readiness_review_missing: "paintPlan.blocker.readinessMissing",
  region_geometry_changed: "paintPlan.blocker.regionSetChanged",
  region_set_changed: "paintPlan.blocker.regionSetChanged",
  region_set_missing: "paintPlan.blocker.regionSetMissing",
  region_set_not_approved: "paintPlan.blocker.regionSetNotApproved",
  region_set_not_current: "paintPlan.blocker.regionSetChanged",
  region_set_stale: "paintPlan.blocker.regionSetChanged",
};

function toApiError(error: unknown): PaintPlanApiError {
  if (error instanceof PaintPlanApiError) {
    return error;
  }
  return new PaintPlanApiError(
    "internal",
    "The Paint Plan workspace could not complete the request.",
  );
}

function defaultSelection(
  workbench: PaintPlanWorkbench,
  projectId: string,
): SelectionState {
  const provider =
    workbench.providers.find((item) => item.provider_key === "fixture_local") ??
    workbench.providers[0];
  const model =
    provider?.models.find(
      (item) => item.supports_vision && item.supports_structured_output,
    ) ?? provider?.models[0];
  const credential = workbench.credentials.find(
    (item) =>
      item.provider_key === provider?.provider_key &&
      item.active_grant &&
      item.status === "active",
  );
  return {
    projectId,
    providerId: provider?.id ?? "",
    modelId: model?.id ?? "",
    credentialId: credential?.id ?? "",
    intent: "",
  };
}

function cloneDocument(document: PaintPlanDocument): PaintPlanDocument {
  return {
    ...document,
    instructions: document.instructions.map((instruction) => ({
      ...instruction,
      warnings: [...instruction.warnings],
    })),
    safety_notes: [...document.safety_notes],
  };
}

function splitLines(value: string): string[] {
  return value
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter((item) => item.length > 0);
}

function providerForSelection(
  workbench: PaintPlanWorkbench,
  selection: SelectionState,
): PaintPlanProviderChoice | undefined {
  return workbench.providers.find((item) => item.id === selection.providerId);
}

function selectionInput(
  workbench: PaintPlanWorkbench,
  selection: SelectionState,
  generationLocale: "zh-CN" | "en-US",
): PaintPlanSelectionInput | null {
  const provider = providerForSelection(workbench, selection);
  const model = provider?.models.find((item) => item.id === selection.modelId);
  const credential = workbench.credentials.find(
    (item) =>
      item.id === selection.credentialId &&
      item.provider_key === provider?.provider_key &&
      item.active_grant &&
      item.status === "active",
  );
  if (
    workbench.image_set_fingerprint === null ||
    workbench.region_set === null ||
    provider === undefined ||
    model === undefined ||
    !model.supports_vision ||
    !model.supports_structured_output ||
    credential === undefined
  ) {
    return null;
  }
  return {
    image_set_fingerprint: workbench.image_set_fingerprint,
    region_set_id: workbench.region_set.id,
    provider_definition_id: selection.providerId,
    model_definition_id: selection.modelId,
    credential_id: selection.credentialId,
    generation_locale: generationLocale,
    intent: selection.intent.trim().length === 0 ? null : selection.intent.trim(),
  };
}

function previewIdentity(input: PaintPlanSelectionInput): string {
  return JSON.stringify(input);
}

function lifecycleKey(lifecycle: PaintPlan["effective_lifecycle"]): string {
  return `paintPlan.lifecycle.${lifecycle}`;
}

function approvalStatusKey(plan: PaintPlan): string {
  if (plan.approval_valid && plan.effective_lifecycle === "approved") {
    return "paintPlan.approvalStatus.approved";
  }
  if (plan.effective_lifecycle === "under_review") {
    return "paintPlan.approvalStatus.underReview";
  }
  if (plan.effective_lifecycle === "rejected") {
    return "paintPlan.approvalStatus.rejected";
  }
  if (plan.effective_lifecycle === "generated" || plan.effective_lifecycle === "edited") {
    return "paintPlan.approvalStatus.notSubmitted";
  }
  return "paintPlan.approvalStatus.noneCurrent";
}

function reviewActionKey(action: PaintPlanReviewEvent["action"]): string {
  return `paintPlan.reviewAction.${action}`;
}

const systemFixtureRegionLabels: Readonly<Record<string, string>> = {
  "Accent plane": "强调区域",
  "Main body panel": "主体区域",
  "Primary color field": "主色区域",
  "Protected trim": "保护边界",
  "Reference boundary": "参考边界",
};

function sourceRegionLabel(label: string, language: string | undefined): string {
  if (language?.startsWith("zh") !== true) {
    return label;
  }
  return systemFixtureRegionLabels[label] ?? label;
}

function errorCopyKey(kind: PaintPlanApiErrorKind): string {
  if (kind === "network" || kind === "invalid_response") {
    return "paintPlan.error.uncertain";
  }
  if (kind === "conflict") {
    return "paintPlan.error.conflict";
  }
  if (kind === "provider") {
    return "paintPlan.error.provider";
  }
  if (kind === "unavailable") {
    return "paintPlan.error.unavailable";
  }
  return "paintPlan.error.generic";
}

function PlanDocumentView({ plan }: { plan: PaintPlan }) {
  const { i18n, t } = useAppTranslation();
  return (
    <div className="paint-plan-document">
      <div className="paint-plan-document__intro">
        <h3>{t("paintPlan.productRevisionTitle", { version: plan.version })}</h3>
        <p>{plan.document.overall_approach}</p>
      </div>

      <div className="paint-plan-instructions">
        {plan.document.instructions.map((instruction, index) => (
          <article className="paint-plan-instruction" key={instruction.region_id}>
            <header>
              <span>{t("paintPlan.instructionNumber", { number: index + 1 })}</span>
              <h3>{instruction.region_label}</h3>
              <strong>{instruction.target_color}</strong>
            </header>
            <dl>
              <div>
                <dt>{t("paintPlan.field.preparation")}</dt>
                <dd>{instruction.preparation}</dd>
              </div>
              <div>
                <dt>{t("paintPlan.field.baseCoat")}</dt>
                <dd>{instruction.base_coat}</dd>
              </div>
              <div>
                <dt>{t("paintPlan.field.layerStrategy")}</dt>
                <dd>{instruction.layer_strategy}</dd>
              </div>
              <div>
                <dt>{t("paintPlan.field.edgeTreatment")}</dt>
                <dd>{instruction.edge_treatment}</dd>
              </div>
              <div>
                <dt>{t("paintPlan.field.lighting")}</dt>
                <dd>{instruction.lighting_guidance}</dd>
              </div>
              <div>
                <dt>{t("paintPlan.field.material")}</dt>
                <dd>{instruction.material_guidance}</dd>
              </div>
            </dl>
            {instruction.warnings.length > 0 ? (
              <div className="paint-plan-instruction__warnings">
                <h4>{t("paintPlan.warnings")}</h4>
                <ul>
                  {instruction.warnings.map((warning) => (
                    <li key={warning}>{warning}</li>
                  ))}
                </ul>
              </div>
            ) : null}
            <p className="paint-plan-confidence">
              {t("paintPlan.confidence", {
                value: new Intl.NumberFormat(
                  i18n.resolvedLanguage ?? "en-US",
                  {
                    maximumFractionDigits: 1,
                    style: "percent",
                  },
                ).format(instruction.confidence_ppm / 1_000_000),
              })}
            </p>
          </article>
        ))}
      </div>

      <section className="paint-plan-safety" aria-labelledby="paint-plan-safety-heading">
        <h3 id="paint-plan-safety-heading">{t("paintPlan.safetyNotes")}</h3>
        {plan.document.safety_notes.length > 0 ? (
          <ul>
            {plan.document.safety_notes.map((note) => (
              <li key={note}>{note}</li>
            ))}
          </ul>
        ) : (
          <p>{t("paintPlan.noSafetyNotes")}</p>
        )}
      </section>

      {plan.document.knowledge_citations.length > 0 ? (
        <details className="paint-plan-technical paint-plan-citations">
          <summary>{t("paintPlan.citations")}</summary>
          <p>{t("paintPlan.citationsCopy")}</p>
          <ul>
            {plan.document.knowledge_citations.map((citation) => {
              const source = plan.retrieved_context.find(
                (item) =>
                  item.source_id === citation.source_id &&
                  item.chunk_id === citation.chunk_id,
              );
              return (
                <li key={`${citation.source_id}:${citation.chunk_id}:${citation.target_path}`}>
                  <strong>{source?.source_title ?? citation.source_id}</strong>
                  <span>{source?.section ?? citation.chunk_id} · {citation.target_path}</span>
                </li>
              );
            })}
          </ul>
        </details>
      ) : null}
    </div>
  );
}

function LatestReviewAudit({
  compact = false,
  review,
}: {
  compact?: boolean;
  review: PaintPlanReviewEvent | null;
}) {
  const { t } = useAppTranslation();
  return (
    <div
      aria-label={t("paintPlan.latestReview")}
      className={`paint-plan-review-audit${
        compact ? " paint-plan-review-audit--compact" : ""
      }`}
    >
      <p className="paint-plan-review-audit__label">
        {t("paintPlan.latestReview")}
      </p>
      {review === null ? (
        <p>{t("paintPlan.noLatestReview")}</p>
      ) : (
        <dl>
          <div>
            <dt>{t("paintPlan.reviewEventAction")}</dt>
            <dd>{t(reviewActionKey(review.action))}</dd>
          </div>
          <div>
            <dt>{t("paintPlan.reviewEventActor")}</dt>
            <dd>{review.actor_display_name_snapshot}</dd>
          </div>
          <div>
            <dt>{t("paintPlan.reviewEventTime")}</dt>
            <dd>
              <time dateTime={review.created_at}>
                {formatProjectTimestamp(review.created_at)}
              </time>
            </dd>
          </div>
          <div>
            <dt>{t("paintPlan.reviewEventReason")}</dt>
            <dd>{review.reason ?? t("paintPlan.noReviewReason")}</dd>
          </div>
        </dl>
      )}
    </div>
  );
}

function PlanEditor({
  document,
  disabled,
  onChange,
}: {
  document: PaintPlanDocument;
  disabled: boolean;
  onChange: (document: PaintPlanDocument) => void;
}) {
  const { t } = useAppTranslation();

  const updateInstruction = (
    index: number,
    field: EditableInstructionField,
    value: string,
  ) => {
    onChange({
      ...document,
      instructions: document.instructions.map((instruction, itemIndex) =>
        itemIndex === index ? { ...instruction, [field]: value } : instruction,
      ),
    });
  };

  const updateWarnings = (index: number, value: string) => {
    onChange({
      ...document,
      instructions: document.instructions.map((instruction, itemIndex) =>
        itemIndex === index
          ? { ...instruction, warnings: splitLines(value) }
          : instruction,
      ),
    });
  };

  return (
    <div className="paint-plan-editor">
      <label>
        <span>{t("paintPlan.field.title")}</span>
        <input
          disabled={disabled}
          maxLength={160}
          onChange={(event) => onChange({ ...document, title: event.target.value })}
          required
          value={document.title}
        />
      </label>
      <label>
        <span>{t("paintPlan.field.overallApproach")}</span>
        <textarea
          disabled={disabled}
          maxLength={2000}
          onChange={(event) =>
            onChange({ ...document, overall_approach: event.target.value })
          }
          required
          rows={5}
          value={document.overall_approach}
        />
      </label>

      {document.instructions.map((instruction, index) => (
        <fieldset disabled={disabled} key={instruction.region_id}>
          <legend>
            {t("paintPlan.editRegion", {
              number: index + 1,
              region: instruction.region_label,
            })}
          </legend>
          <p className="paint-plan-editor__identity">
            {t("paintPlan.regionIdentityLocked")}
          </p>
          {instructionFields.map((field) => (
            <label key={field.key}>
              <span>{t(field.labelKey)}</span>
              {field.key === "target_color" ? (
                <input
                  maxLength={field.maximumLength}
                  onChange={(event) =>
                    updateInstruction(index, field.key, event.target.value)
                  }
                  required
                  value={instruction[field.key]}
                />
              ) : (
                <textarea
                  maxLength={field.maximumLength}
                  onChange={(event) =>
                    updateInstruction(index, field.key, event.target.value)
                  }
                  required
                  rows={3}
                  value={instruction[field.key]}
                />
              )}
            </label>
          ))}
          <label>
            <span>{t("paintPlan.warningsPerLine")}</span>
            <textarea
              maxLength={1927}
              onChange={(event) => updateWarnings(index, event.target.value)}
              rows={3}
              value={instruction.warnings.join("\n")}
            />
          </label>
        </fieldset>
      ))}

      <label>
        <span>{t("paintPlan.safetyPerLine")}</span>
        <textarea
          disabled={disabled}
          maxLength={6415}
          onChange={(event) =>
            onChange({ ...document, safety_notes: splitLines(event.target.value) })
          }
          rows={4}
          value={document.safety_notes.join("\n")}
        />
      </label>
    </div>
  );
}

export function PaintPlanWorkspacePage() {
  const { i18n, t } = useAppTranslation();
  const generationLocale =
    i18n.resolvedLanguage === "zh-CN" ? "zh-CN" : "en-US";
  const { projectId } = useParams();
  const validProjectId = isPaintProjectId(projectId);
  const [reloadToken, setReloadToken] = useState(0);
  const [refreshing, setRefreshing] = useState(false);
  const [state, setState] = useState<WorkbenchState>({
    status: "loading",
    projectId: projectId ?? "",
  });
  const [selection, setSelection] = useState<SelectionState | null>(null);
  const [previewSnapshot, setPreviewSnapshot] =
    useState<PaintPlanPreviewSnapshot | null>(null);
  const [previewBusy, setPreviewBusy] = useState(false);
  const [maxAttempts, setMaxAttempts] = useState(1);
  const [fixtureConfirmed, setFixtureConfirmed] = useState(false);
  const [historicalPlanId, setHistoricalPlanId] = useState<string | null>(null);
  const [editDraft, setEditDraft] = useState<PaintPlanEditDraft | null>(null);
  const [reviewReasonDraft, setReviewReasonDraft] =
    useState<PaintPlanReviewReasonDraft | null>(null);
  const [command, setCommand] = useState<CommandState>({
    status: "idle",
    noticeKey: null,
  });
  const [retryAvailable, setRetryAvailable] = useState(false);
  const loadGenerationRef = useRef(0);
  const pageRef = useRef<HTMLDivElement>(null);
  const commandNoticeRef = useRef<HTMLDivElement>(null);
  const outputHeadingRef = useRef<HTMLHeadingElement>(null);
  const previousEditActiveRef = useRef(false);
  const previousHistoricalPlanIdRef = useRef<string | null>(null);
  const commandControllerRef = useRef<AbortController | null>(null);
  const previewControllerRef = useRef<AbortController | null>(null);
  const idempotencyKeysRef = useRef(
    new Map<string, { fingerprint: string; key: string }>(),
  );
  const retryCommandRef = useRef<(() => void) | null>(null);

  const currentState: WorkbenchState =
    validProjectId && state.projectId === projectId
      ? state
      : { status: "loading", projectId: projectId ?? "" };

  useLayoutEffect(() => {
    document.title = t("title.paintPlans");
  }, [i18n.resolvedLanguage, t]);

  useLayoutEffect(() => {
    const heading = pageRef.current?.querySelector<HTMLElement>("h1");
    if (heading === null || heading === undefined) {
      return;
    }
    heading.tabIndex = -1;
    heading.focus({ preventScroll: true });
  }, [currentState.status, projectId]);

  useEffect(() => {
    const historyChanged =
      previousHistoricalPlanIdRef.current !== historicalPlanId;
    const editIsActive = editDraft !== null;
    const editChanged = previousEditActiveRef.current !== editIsActive;
    if (historyChanged) {
      outputHeadingRef.current?.focus({ preventScroll: true });
    } else if (editChanged && editIsActive) {
      pageRef.current
        ?.querySelector<HTMLInputElement>(".paint-plan-editor input")
        ?.focus({ preventScroll: true });
    } else if (editChanged) {
      outputHeadingRef.current?.focus({ preventScroll: true });
    }
    previousHistoricalPlanIdRef.current = historicalPlanId;
    previousEditActiveRef.current = editIsActive;
  }, [editDraft, historicalPlanId]);

  useEffect(() => {
    if (command.status === "idle" && command.noticeKey !== null) {
      commandNoticeRef.current?.focus({ preventScroll: true });
    }
  }, [command]);

  useEffect(() => {
    const idempotencyKeys = idempotencyKeysRef.current;
    return () => {
      commandControllerRef.current?.abort();
      previewControllerRef.current?.abort();
      commandControllerRef.current = null;
      previewControllerRef.current = null;
      loadGenerationRef.current += 1;
      retryCommandRef.current = null;
      idempotencyKeys.clear();
    };
  }, []);

  useEffect(() => {
    if (!isPaintProjectId(projectId)) {
      return;
    }
    const controller = new AbortController();
    const generation = loadGenerationRef.current + 1;
    loadGenerationRef.current = generation;
    void getPaintPlanWorkbench(projectId, controller.signal)
      .then((workbench) => {
        if (controller.signal.aborted || loadGenerationRef.current !== generation) {
          return;
        }
        setState({ status: "ready", projectId, workbench });
        setPreviewSnapshot(null);
        setFixtureConfirmed(false);
        setPreviewBusy(false);
        setSelection((current) => {
          const selectionIsStillValid =
            current?.projectId === projectId &&
            selectionInput(workbench, current, generationLocale) !== null;
          return selectionIsStillValid
            ? current
            : defaultSelection(workbench, projectId);
        });
        setHistoricalPlanId((current) =>
          current !== null && workbench.history.some((plan) => plan.id === current)
            ? current
            : null,
        );
        setEditDraft((current) =>
          current !== null &&
          current.projectId === projectId &&
          workbench.current_plan?.id === current.basePlanId &&
          workbench.current_plan.version === current.baseVersion
            ? current
            : null,
        );
        setReviewReasonDraft((current) =>
          current !== null &&
          current.projectId === projectId &&
          workbench.current_plan?.id === current.basePlanId &&
          workbench.current_plan.version === current.baseVersion
            ? current
            : null,
        );
        setRefreshing(false);
      })
      .catch((error: unknown) => {
        if (
          controller.signal.aborted ||
          (error instanceof PaintPlanApiError && error.kind === "aborted") ||
          loadGenerationRef.current !== generation
        ) {
          return;
        }
        setState({ status: "error", error: toApiError(error), projectId });
        setRefreshing(false);
      });

    return () => controller.abort();
  }, [generationLocale, projectId, reloadToken]);

  const beginWorkbenchReload = () => {
    previewControllerRef.current?.abort();
    commandControllerRef.current?.abort();
    setPreviewSnapshot(null);
    setFixtureConfirmed(false);
    setPreviewBusy(false);
    setHistoricalPlanId(null);
    setEditDraft(null);
    setReviewReasonDraft(null);
    setCommand({ status: "idle", noticeKey: null });
    setRetryAvailable(false);
    retryCommandRef.current = null;
    idempotencyKeysRef.current.clear();
    setRefreshing(true);
    setReloadToken((current) => current + 1);
  };

  if (!validProjectId) {
    return (
      <div className="page page--paint-plan" ref={pageRef}>
        <FeedbackPanel
          eyebrow={t("paintPlan.invalidAddress")}
          heading={t("paintPlan.invalidHeading")}
          headingLevel={1}
          kind="error"
        >
          <p>{t("paintPlan.invalidCopy")}</p>
          <Link className="button button--secondary" to="/paintpilot/projects">
            {t("paintPlan.backProjects")}
          </Link>
        </FeedbackPanel>
      </div>
    );
  }

  if (currentState.status === "loading") {
    return (
      <div className="page page--paint-plan" ref={pageRef}>
        <section aria-busy="true" className="paint-plan-loading">
          <h1>{t("paintPlan.loadingHeading")}</h1>
          <p role="status">{t("paintPlan.loadingCopy")}</p>
          <div aria-hidden="true" className="paint-plan-loading__image" />
        </section>
      </div>
    );
  }

  if (currentState.status === "error") {
    return (
      <div className="page page--paint-plan" ref={pageRef}>
        <FeedbackPanel
          action={{
            label: t("paintPlan.retryWorkbench"),
            onClick: beginWorkbenchReload,
          }}
          eyebrow={t("paintPlan.unavailable")}
          heading={t("paintPlan.unavailableHeading")}
          headingLevel={1}
          kind="error"
        >
          <p>{t(errorCopyKey(currentState.error.kind))}</p>
        </FeedbackPanel>
      </div>
    );
  }

  const { workbench } = currentState;
  const resolvedSelection =
    selection?.projectId === projectId
      ? selection
      : defaultSelection(workbench, projectId);
  const selectedProvider = providerForSelection(workbench, resolvedSelection);
  const selectedModel = selectedProvider?.models.find(
    (model) => model.id === resolvedSelection.modelId,
  );
  const matchingCredentials = workbench.credentials.filter(
    (credential) =>
      credential.provider_key === selectedProvider?.provider_key &&
      credential.active_grant &&
      credential.status === "active",
  );
  const selectedCredential = matchingCredentials.find(
    (credential) => credential.id === resolvedSelection.credentialId,
  );
  const requestSelection = selectionInput(
    workbench,
    resolvedSelection,
    generationLocale,
  );
  const currentPreviewIdentity =
    requestSelection === null ? null : previewIdentity(requestSelection);
  const preview =
    currentPreviewIdentity !== null &&
    previewSnapshot?.identity === currentPreviewIdentity
      ? previewSnapshot.value
      : null;
  const viewedPlan =
    historicalPlanId === null
      ? workbench.current_plan
      : workbench.history.find((plan) => plan.id === historicalPlanId) ?? null;
  const isHistorical = historicalPlanId !== null;
  const editDocument =
    !isHistorical &&
    viewedPlan !== null &&
    editDraft?.projectId === projectId &&
    editDraft.basePlanId === viewedPlan.id &&
    editDraft.baseVersion === viewedPlan.version
      ? editDraft.document
      : null;
  const reviewReason =
    !isHistorical &&
    viewedPlan !== null &&
    reviewReasonDraft?.projectId === projectId &&
    reviewReasonDraft.basePlanId === viewedPlan.id &&
    reviewReasonDraft.baseVersion === viewedPlan.version
      ? reviewReasonDraft.value
      : "";
  const isBusy = refreshing || command.status === "busy" || previewBusy;
  const authorityStale =
    command.status === "error" && command.error.kind === "conflict";
  const uncertainRetryPending =
    command.status === "error" && retryAvailable && command.error.retryable;
  const commandControlsLocked = isBusy || authorityStale || uncertainRetryPending;
  const generationControlsLocked =
    commandControlsLocked || isHistorical || editDocument !== null;
  const canPreview =
    !generationControlsLocked &&
    requestSelection !== null &&
    workbench.allowed_actions.includes("preview");
  const generationAction = workbench.current_plan === null ? "generate" : "regenerate";
  const hasAdmissiblePreview =
    currentPreviewIdentity !== null &&
    previewSnapshot?.identity === currentPreviewIdentity &&
    preview?.admissible === true &&
    preview.source_ready &&
    preview.blockers.length === 0 &&
    (preview.execution_mode === "fixture_available" ||
      (preview.provider_key === "zhipu" && preview.live_execution_authorized)) &&
    preview.provider_key === selectedProvider?.provider_key &&
    preview.model_id === selectedModel?.model_id;
  const isGenerationSelection =
    (selectedProvider?.execution_mode === "fixture_available" ||
      selectedProvider?.provider_key === "zhipu") &&
    selectedCredential?.active_grant === true;
  const canGenerate =
    !generationControlsLocked &&
    fixtureConfirmed &&
    requestSelection !== null &&
    isGenerationSelection &&
    workbench.allowed_actions.includes(generationAction);

  const changeSelection = (next: SelectionState) => {
    setSelection(next);
    setPreviewSnapshot(null);
    setFixtureConfirmed(false);
    setCommand({ status: "idle", noticeKey: null });
    setRetryAvailable(false);
    retryCommandRef.current = null;
  };

  const keyForCommand = (name: string, fingerprint: string): string => {
    const current = idempotencyKeysRef.current.get(name);
    const key = stablePaintPlanIdempotencyKey(
      current?.fingerprint === fingerprint ? current.key : null,
    );
    idempotencyKeysRef.current.set(name, { fingerprint, key });
    return key;
  };

  const applyPlanResult = (_plan: PaintPlan, noticeKey: string) => {
    setHistoricalPlanId(null);
    setEditDraft(null);
    setReviewReasonDraft(null);
    setPreviewSnapshot(null);
    setFixtureConfirmed(false);
    setCommand({ status: "idle", noticeKey });
    setRetryAvailable(false);
    retryCommandRef.current = null;
    setRefreshing(true);
    setReloadToken((current) => current + 1);
  };

  const runProtectedCommand = (
    name: string,
    labelKey: string,
    fingerprint: string,
    noticeKey: string,
    operation: (key: string, signal: AbortSignal) => Promise<PaintPlan>,
  ) => {
    if (command.status === "busy" || previewBusy || authorityStale) {
      return;
    }
    const retry = () =>
      runProtectedCommand(name, labelKey, fingerprint, noticeKey, operation);
    retryCommandRef.current = retry;
    setRetryAvailable(false);
    const controller = new AbortController();
    commandControllerRef.current?.abort();
    commandControllerRef.current = controller;
    const key = keyForCommand(name, fingerprint);
    setCommand({ status: "busy", labelKey });
    void operation(key, controller.signal)
      .then((plan) => {
        if (controller.signal.aborted) {
          return;
        }
        idempotencyKeysRef.current.delete(name);
        applyPlanResult(plan, noticeKey);
      })
      .catch((error: unknown) => {
        if (
          controller.signal.aborted ||
          (error instanceof PaintPlanApiError && error.kind === "aborted")
        ) {
          return;
        }
        const apiError = toApiError(error);
        if (apiError.kind === "conflict") {
          idempotencyKeysRef.current.delete(name);
          setPreviewSnapshot(null);
          setFixtureConfirmed(false);
          setEditDraft(null);
          setReviewReasonDraft(null);
          retryCommandRef.current = null;
          setRetryAvailable(false);
          setCommand({ status: "error", error: apiError, labelKey });
          return;
        }
        if (!apiError.retryable) {
          idempotencyKeysRef.current.delete(name);
        }
        setCommand({ status: "error", error: apiError, labelKey });
        setRetryAvailable(apiError.retryable);
      });
  };

  const requestPreview = (
    onAdmissible?: () => void,
    preserveConfirmation = false,
  ) => {
    if (
      !canPreview ||
      requestSelection === null ||
      selectedProvider === undefined ||
      selectedModel === undefined ||
      workbench.region_set === null
    ) {
      return;
    }
    const controller = new AbortController();
    previewControllerRef.current?.abort();
    previewControllerRef.current = controller;
    const identity = previewIdentity(requestSelection);
    const expectedProviderKey = selectedProvider.provider_key;
    const expectedModelId = selectedModel.model_id;
    setPreviewBusy(true);
    setPreviewSnapshot(null);
    if (!preserveConfirmation) {
      setFixtureConfirmed(false);
    }
    setCommand({ status: "idle", noticeKey: null });
    setRetryAvailable(false);
    void previewPaintPlan(projectId, requestSelection, controller.signal)
      .then((result) => {
        if (controller.signal.aborted) {
          return;
        }
        if (
          result.provider_key !== expectedProviderKey ||
          result.model_id !== expectedModelId
        ) {
          setPreviewBusy(false);
          const error = new PaintPlanApiError(
            "invalid_response",
            "The Paint Plan preview did not match the selected provider and model.",
            { retryable: true },
          );
          setCommand({
            status: "error",
            error,
            labelKey: "paintPlan.previewing",
          });
          retryCommandRef.current = requestPreview;
          setRetryAvailable(true);
          return;
        }
        setPreviewSnapshot({ identity, value: result });
        setPreviewBusy(false);
        if (
          result.admissible &&
          result.source_ready &&
          result.blockers.length === 0 &&
          (result.execution_mode === "fixture_available" ||
            (result.provider_key === "zhipu" && result.live_execution_authorized))
        ) {
          onAdmissible?.();
        }
      })
      .catch((error: unknown) => {
        if (
          controller.signal.aborted ||
          (error instanceof PaintPlanApiError && error.kind === "aborted")
        ) {
          return;
        }
        setPreviewBusy(false);
        const apiError = toApiError(error);
        setCommand({
          status: "error",
          error: apiError,
          labelKey: "paintPlan.previewing",
        });
        retryCommandRef.current = requestPreview;
        setRetryAvailable(apiError.retryable);
      });
  };

  const startGeneration = () => {
    const selectedRegionSet = workbench.region_set;
    if (
      requestSelection === null ||
      selectedProvider === undefined ||
      selectedModel === undefined ||
      selectedRegionSet === null
    ) {
      return;
    }
    const expectedSelection = {
      provider_key: selectedProvider.provider_key,
      model_id: selectedModel.model_id,
      source_image_assets: workbench.image_assets,
      region_set: selectedRegionSet,
    };
    if (generationAction === "generate") {
      const input = {
        ...requestSelection,
        confirm_generation: true as const,
        max_attempts: maxAttempts,
      };
      runProtectedCommand(
        "generate",
        "paintPlan.generating",
        JSON.stringify(input),
        "paintPlan.notice.generated",
        (key, signal) =>
          generatePaintPlan(
            projectId,
            input,
            expectedSelection,
            key,
            signal,
          ),
      );
      return;
    }
    const currentPlan = workbench.current_plan;
    if (currentPlan === null) {
      return;
    }
    const input = {
      ...requestSelection,
      expected_current_plan_id: currentPlan.id,
      expected_current_version: currentPlan.version,
      confirm_generation: true as const,
      max_attempts: maxAttempts,
    };
    runProtectedCommand(
      "regenerate",
      "paintPlan.regenerating",
      JSON.stringify(input),
      "paintPlan.notice.regenerated",
      (key, signal) =>
        regeneratePaintPlan(
          projectId,
          currentPlan.id,
          input,
          expectedSelection,
          key,
          signal,
        ),
    );
  };

  const requestGeneration = () => {
    if (!canGenerate) {
      return;
    }
    if (hasAdmissiblePreview) {
      startGeneration();
      return;
    }
    requestPreview(startGeneration, true);
  };

  const saveEdit = () => {
    const authoritativePlan = workbench.current_plan;
    if (
      viewedPlan === null ||
      editDraft === null ||
      isHistorical ||
      editDraft.projectId !== projectId ||
      editDraft.basePlanId !== viewedPlan.id ||
      editDraft.baseVersion !== viewedPlan.version ||
      authoritativePlan?.id !== editDraft.basePlanId ||
      authoritativePlan.version !== editDraft.baseVersion
    ) {
      setEditDraft(null);
      return;
    }
    const input = {
      expected_current_plan_id: editDraft.basePlanId,
      expected_current_version: editDraft.baseVersion,
      document: editDraft.document,
    };
    runProtectedCommand(
      "edit",
      "paintPlan.savingEdit",
      JSON.stringify(input),
      "paintPlan.notice.edited",
      (key, signal) =>
        editPaintPlan(
          projectId,
          editDraft.basePlanId,
          input,
          authoritativePlan,
          key,
          signal,
        ),
    );
  };

  const submitForReview = () => {
    if (
      viewedPlan === null ||
      isHistorical ||
      workbench.current_plan?.id !== viewedPlan.id ||
      workbench.current_plan.version !== viewedPlan.version
    ) {
      return;
    }
    const input = {
      expected_current_plan_id: viewedPlan.id,
      expected_current_version: viewedPlan.version,
    };
    runProtectedCommand(
      "submit",
      "paintPlan.submitting",
      JSON.stringify(input),
      "paintPlan.notice.submitted",
      (key, signal) => submitPaintPlan(projectId, viewedPlan.id, input, key, signal),
    );
  };

  const reviewPlan = (action: "approve" | "reject") => {
    if (
      viewedPlan === null ||
      isHistorical ||
      workbench.current_plan?.id !== viewedPlan.id ||
      workbench.current_plan.version !== viewedPlan.version
    ) {
      return;
    }
    const trimmedReason = reviewReason.trim();
    if (action === "reject" && trimmedReason.length === 0) {
      setCommand({
        status: "error",
        error: new PaintPlanApiError("validation", "A rejection reason is required."),
        labelKey: "paintPlan.reviewing",
      });
      setRetryAvailable(false);
      return;
    }
    const input = {
      expected_current_plan_id: viewedPlan.id,
      expected_current_version: viewedPlan.version,
      reason: trimmedReason.length === 0 ? null : trimmedReason,
    };
    runProtectedCommand(
      action,
      "paintPlan.reviewing",
      JSON.stringify(input),
      action === "approve"
        ? "paintPlan.notice.approved"
        : "paintPlan.notice.rejected",
      (key, signal) =>
        action === "approve"
          ? approvePaintPlan(projectId, viewedPlan.id, input, key, signal)
          : rejectPaintPlan(projectId, viewedPlan.id, input, key, signal),
    );
  };

  const paintRegions = workbench.region_set?.regions.filter(
    (region) => region.kind === "paint",
  ) ?? [];
  const excludedRegions = workbench.region_set?.regions.filter(
    (region) => region.kind === "exclude",
  ) ?? [];

  return (
    <div className="page page--paint-plan" ref={pageRef}>
      <nav aria-label={t("paintPlan.breadcrumbLabel")} className="detail-breadcrumb">
        <Link to={`/paintpilot/projects/${projectId}`}>
          {t("paintPlan.backProject")}
        </Link>
      </nav>

      <header className="paint-plan-header">
        <div>
          <p className="context-label">
            {t("paintPlan.role", {
              role:
                workbench.access_role === "owner"
                  ? t("common.owner")
                  : t("common.reviewer"),
            })}
          </p>
          <h1>{t("paintPlan.heading")}</h1>
          <p>{t("paintPlan.lede")}</p>
        </div>
        <button
          className="button button--secondary"
          disabled={isBusy || editDocument !== null}
          onClick={beginWorkbenchReload}
          type="button"
        >
          {refreshing ? t("paintPlan.refreshing") : t("paintPlan.refresh")}
        </button>
      </header>

      <section
        aria-labelledby="paint-plan-source-heading"
        className="paint-plan-source"
      >
        <div className="section-heading">
          <div>
            <p className="context-label">{t("paintPlan.stepSource")}</p>
            <h2 id="paint-plan-source-heading">{t("paintPlan.sourceHeading")}</h2>
            <p>{t("paintPlan.sourceCopy")}</p>
          </div>
          <span className="paint-plan-source__status">
            {workbench.source_ready
              ? t("paintPlan.sourceReady")
              : t("paintPlan.sourceBlocked")}
          </span>
        </div>

        {workbench.image_assets.length > 0 ? (
          <div className="paint-plan-image-grid">
            {workbench.image_assets.slice(0, 4).map((asset) => (
              <figure key={asset.id}>
                <img
                  alt={t("paintPlan.imageAlt", {
                    role: t(`image.role.${asset.role}`),
                  })}
                  height={asset.height}
                  src={asset.content_url}
                  width={asset.width}
                />
                <figcaption>
                  <strong>{t(`image.role.${asset.role}`)}</strong>
                  <span>{t("paintPlan.imageVersion", { version: asset.version })}</span>
                </figcaption>
              </figure>
            ))}
          </div>
        ) : (
          <div className="paint-plan-empty">
            <h3>{t("paintPlan.noImagesHeading")}</h3>
            <p>{t("paintPlan.noImagesCopy")}</p>
          </div>
        )}

        <div className="paint-plan-region-summary">
          <div>
            <span>{t("paintPlan.paintRegions")}</span>
            <strong>{paintRegions.length}</strong>
            <p>
              {paintRegions
                .map((region) => sourceRegionLabel(region.label, i18n.resolvedLanguage))
                .join(", ") || t("common.none")}
            </p>
          </div>
          <div>
            <span>{t("paintPlan.excludeRegions")}</span>
            <strong>{excludedRegions.length}</strong>
            <p>
              {excludedRegions
                .map((region) => sourceRegionLabel(region.label, i18n.resolvedLanguage))
                .join(", ") ||
                t("common.none")}
            </p>
          </div>
          <div>
            <span>{t("paintPlan.regionRevision")}</span>
            <strong>
              {workbench.region_set === null
                ? t("common.none")
                : t("paintPlan.versionValue", { version: workbench.region_set.version })}
            </strong>
            <p>
              {workbench.region_set?.stale
                ? t("paintPlan.regionStale")
                : workbench.region_set === null
                  ? t("common.unavailable")
                  : t(
                      `region.lifecycle.${workbench.region_set.effective_lifecycle}`,
                    )}
            </p>
          </div>
        </div>

        {!workbench.source_ready ? (
          <div className="paint-plan-blockers" role="status">
            <h3>{t("paintPlan.sourceNeedsAttention")}</h3>
            <ul>
              {workbench.blockers.map((blocker) => (
                <li key={blocker}>
                  {t(knownBlockerKeys[blocker] ?? "paintPlan.blocker.other")}
                </li>
              ))}
            </ul>
            <Link
              className="button button--secondary"
              to={`/paintpilot/projects/${projectId}`}
            >
              {t("paintPlan.reviewSources")}
            </Link>
          </div>
        ) : null}

        <details className="paint-plan-technical">
          <summary>{t("paintPlan.technicalSource")}</summary>
          <dl>
            <div>
              <dt>{t("paintPlan.imageFingerprint")}</dt>
              <dd>{workbench.image_set_fingerprint ?? t("common.unavailable")}</dd>
            </div>
            <div>
              <dt>{t("paintPlan.regionSetId")}</dt>
              <dd>{workbench.region_set?.id ?? t("common.unavailable")}</dd>
            </div>
            <div>
              <dt>{t("paintPlan.geometryFingerprint")}</dt>
              <dd>{workbench.region_set?.geometry_fingerprint ?? t("common.unavailable")}</dd>
            </div>
            {workbench.region_set !== null ? (
              <div className="paint-plan-technical__wide">
                <dt>{t("paintPlan.sourceRegionDetails")}</dt>
                <dd>
                  <ul className="paint-plan-source-assets">
                    {workbench.region_set.regions.map((region) => (
                      <li key={region.id}>
                        <strong>{region.label}</strong>
                        <span>{t(`paintPlan.regionKind.${region.kind}`)}</span>
                        <code>{region.stable_region_key}</code>
                      </li>
                    ))}
                  </ul>
                </dd>
              </div>
            ) : null}
          </dl>
        </details>
      </section>

      {workbench.access_role === "owner" ? (
        <section
          aria-labelledby="paint-plan-generation-heading"
          className="paint-plan-generation"
        >
          <div className="section-heading">
            <div>
              <p className="context-label">{t("paintPlan.stepGenerate")}</p>
              <h2 id="paint-plan-generation-heading">
                {t("paintPlan.generationHeading")}
              </h2>
              <p>{t("paintPlan.generationCopy")}</p>
            </div>
          </div>

          <div className="paint-plan-test-mode" role="status">
            <strong>{selectedProvider?.provider_key === "zhipu" ? t("paintPlan.liveMode") : t("paintPlan.testMode")}</strong>
            <span>{selectedProvider?.provider_key === "zhipu" ? t("paintPlan.liveModeCopy") : t("paintPlan.testModeCopy")}</span>
          </div>

          {workbench.source_ready &&
          (!workbench.allowed_actions.includes("preview") ||
            workbench.blockers.length > 0) ? (
            <div className="paint-plan-generation-boundary" role="status">
              <strong>{t("paintPlan.generationUnavailable")}</strong>
              <p>{t("paintPlan.generationUnavailableCopy")}</p>
              {workbench.blockers.length > 0 ? (
                <ul>
                  {workbench.blockers.map((blocker) => (
                    <li key={blocker}>
                      {t(knownBlockerKeys[blocker] ?? "paintPlan.blocker.other")}
                    </li>
                  ))}
                </ul>
              ) : null}
            </div>
          ) : null}

          <div className="paint-plan-routing">
            <label>
              <span>{t("paintPlan.model")}</span>
              <select
                disabled={generationControlsLocked || selectedProvider === undefined}
                onChange={(event) =>
                  changeSelection({ ...resolvedSelection, modelId: event.target.value })
                }
                value={resolvedSelection.modelId}
              >
                {(selectedProvider?.models ?? []).map((model) => (
                  <option key={model.id} value={model.id}>
                    {model.display_name}
                  </option>
                ))}
              </select>
              {selectedModel !== undefined ? (
                <small>
                  {selectedModel.supports_vision && selectedModel.supports_structured_output
                    ? selectedModel.execution_mode === "fixture_available"
                      ? t("paintPlan.localModelCompatible")
                      : t("paintPlan.modelCompatible")
                    : t("paintPlan.modelIncompatible")}
                </small>
              ) : null}
            </label>
            <label>
              <span>{t("paintPlan.credential")}</span>
              <select
                disabled={generationControlsLocked || matchingCredentials.length === 0}
                onChange={(event) =>
                  changeSelection({
                    ...resolvedSelection,
                    credentialId: event.target.value,
                  })
                }
                value={resolvedSelection.credentialId}
              >
                {matchingCredentials.length === 0 ? (
                  <option value="">{t("paintPlan.noActiveCredential")}</option>
                ) : null}
                {matchingCredentials.map((credential) => (
                  <option disabled={!credential.active_grant} key={credential.id} value={credential.id}>
                    {credential.alias} — {credential.active_grant
                      ? t("paintPlan.activeGrant")
                      : t("paintPlan.inactiveGrant")}
                  </option>
                ))}
              </select>
            </label>
            <label className="paint-plan-routing__intent">
              <span>{t("paintPlan.intent")}</span>
              <textarea
                disabled={generationControlsLocked}
                maxLength={1200}
                onChange={(event) =>
                  changeSelection({ ...resolvedSelection, intent: event.target.value })
                }
                placeholder={t("paintPlan.intentPlaceholder")}
                rows={3}
                value={resolvedSelection.intent}
              />
              <small>{t("paintPlan.intentHelp")}</small>
            </label>
            <details className="paint-plan-provider-choice">
              <summary>{t("paintPlan.modelSource")}</summary>
              <label>
                <span>{t("paintPlan.modelSource")}</span>
                <select
                  disabled={generationControlsLocked}
                  onChange={(event) => {
                    const provider = workbench.providers.find(
                      (item) => item.id === event.target.value,
                    );
                    const model =
                      provider?.models.find(
                        (item) =>
                          item.supports_vision && item.supports_structured_output,
                      ) ?? provider?.models[0];
                    const credential = workbench.credentials.find(
                      (item) =>
                        item.provider_key === provider?.provider_key &&
                        item.active_grant &&
                        item.status === "active",
                    );
                    changeSelection({
                      ...resolvedSelection,
                      providerId: provider?.id ?? "",
                      modelId: model?.id ?? "",
                      credentialId: credential?.id ?? "",
                    });
                    if (provider?.provider_key === "zhipu") setMaxAttempts(1);
                  }}
                  value={resolvedSelection.providerId}
                >
                  {workbench.providers.map((provider) => (
                    <option key={provider.id} value={provider.id}>
                      {provider.display_name} — {provider.execution_mode === "fixture_available"
                        ? t("paintPlan.localTestAvailable")
                        : t("paintPlan.liveAuthorizationRequired")}
                    </option>
                  ))}
                </select>
              </label>
            </details>
          </div>

          {selectedProvider?.execution_mode === "live_authorization_required" ? (
            <div className="paint-plan-live-boundary" role="status">
              <strong>{preview?.live_execution_authorized ? t("paintPlan.liveGateAuthorized") : t("paintPlan.liveAuthorizationRequired")}</strong>
              <p>{preview?.live_execution_authorized ? t("paintPlan.liveGateAuthorizedCopy") : t("paintPlan.liveBlockedCopy")}</p>
            </div>
          ) : null}

          {matchingCredentials.length === 0 ? (
            <div className="paint-plan-credential-boundary">
              <p>{t("paintPlan.credentialRequiredCopy")}</p>
              {phase3aFixtureEnabled ? (
                <Link
                  className="button button--secondary"
                  to="/paintpilot/settings/ai/credentials"
                >
                  {t("paintPlan.openCredentials")}
                </Link>
              ) : null}
            </div>
          ) : null}

          <div className="paint-plan-command-row">
            <button
              className="button button--secondary"
              disabled={!canPreview}
              onClick={() => requestPreview()}
              type="button"
            >
              {previewBusy ? t("paintPlan.previewing") : t("paintPlan.preview")}
            </button>
            <details className="paint-plan-attempt-options">
              <summary>{t("paintPlan.advancedGenerationOptions")}</summary>
              <label>
                <span>{t("paintPlan.maxAttempts")}</span>
                <select
                  disabled={generationControlsLocked || selectedProvider?.provider_key === "zhipu"}
                  onChange={(event) => {
                    setMaxAttempts(Number(event.target.value));
                    setPreviewSnapshot(null);
                    setFixtureConfirmed(false);
                  }}
                  value={maxAttempts}
                >
                  <option value={1}>1</option>
                  {selectedProvider?.provider_key !== "zhipu" ? <><option value={2}>2</option><option value={3}>3</option></> : null}
                </select>
              </label>
            </details>
          </div>

          {preview !== null ? (
            <div
              className={`paint-plan-preview ${
                preview.admissible ? "paint-plan-preview--ready" : "paint-plan-preview--blocked"
              }`}
              role="status"
            >
              <div>
                <span>{t("paintPlan.previewResult")}</span>
                <strong>
                  {preview.admissible
                    ? t("paintPlan.previewAdmissible")
                    : t("paintPlan.previewBlocked")}
                </strong>
              </div>
              <div>
                <span>{t("paintPlan.estimatedCost")}</span>
                <strong>
                  {preview.estimate_status === "estimated" &&
                  preview.estimated_cost_minor_units !== null
                    ? preview.currency === "USD" || preview.currency === "CNY"
                      ? new Intl.NumberFormat(i18n.resolvedLanguage ?? "en-US", {
                          currency: preview.currency,
                          style: "currency",
                        }).format(preview.estimated_cost_minor_units / 100)
                      : t("paintPlan.fixtureCreditsValue", {
                          amount: preview.estimated_cost_minor_units,
                        })
                    : t("paintPlan.costUnavailable")}
                </strong>
              </div>
              {preview.blockers.length > 0 ? (
                <ul>
                  {preview.blockers.map((blocker) => (
                    <li key={blocker}>
                      {t(knownBlockerKeys[blocker] ?? "paintPlan.blocker.other")}
                    </li>
                  ))}
                </ul>
              ) : null}
            </div>
          ) : null}

          {isGenerationSelection ? (
            <label className="paint-plan-confirmation">
              <input
                checked={fixtureConfirmed}
                disabled={generationControlsLocked}
                onChange={(event) => setFixtureConfirmed(event.target.checked)}
                type="checkbox"
              />
              <span>{selectedProvider?.provider_key === "zhipu" ? t("paintPlan.confirmZhipuLive") : t("paintPlan.confirmFixture")}</span>
            </label>
          ) : null}

          <button
            className="button button--primary paint-plan-generate"
            disabled={!canGenerate}
            onClick={requestGeneration}
            type="button"
          >
            {command.status === "busy" &&
            (command.labelKey === "paintPlan.generating" ||
              command.labelKey === "paintPlan.regenerating")
              ? t(command.labelKey)
              : generationAction === "generate"
                ? t(selectedProvider?.provider_key === "zhipu" ? "paintPlan.generateZhipu" : "paintPlan.generateFixture")
                : t(selectedProvider?.provider_key === "zhipu" ? "paintPlan.regenerateZhipu" : "paintPlan.regenerateFixture")}
          </button>
          <p className="paint-plan-guidance-boundary">
            {t("paintPlan.guidanceBoundary")}
          </p>
        </section>
      ) : null}

      {command.status === "busy" ? (
        <div
          aria-live="polite"
          className="paint-plan-command-progress"
          role="status"
        >
          {t(command.labelKey)}
        </div>
      ) : null}
      {command.status === "error" ? (
        <div className="paint-plan-command-error" role="alert">
          <div>
            <strong>{t("paintPlan.commandFailed")}</strong>
            <p>{t(errorCopyKey(command.error.kind))}</p>
          </div>
          {retryAvailable && command.error.retryable ? (
            <button
              className="button button--secondary"
              onClick={() => retryCommandRef.current?.()}
              type="button"
            >
              {t("paintPlan.retrySafely")}
            </button>
          ) : command.error.kind === "conflict" ? (
            <button
              className="button button--secondary"
              onClick={beginWorkbenchReload}
              type="button"
            >
              {t("paintPlan.refresh")}
            </button>
          ) : null}
        </div>
      ) : null}
      {command.status === "idle" && command.noticeKey !== null ? (
        <div
          className="paint-plan-command-notice"
          ref={commandNoticeRef}
          role="status"
          tabIndex={-1}
        >
          {t(command.noticeKey)}
        </div>
      ) : null}

      <section
        aria-labelledby="paint-plan-document-heading"
        className="paint-plan-output"
      >
        <div className="section-heading">
          <div>
            <p className="context-label">{t("paintPlan.stepPlan")}</p>
            <h2
              id="paint-plan-document-heading"
              ref={outputHeadingRef}
              tabIndex={-1}
            >
              {t(
                isHistorical
                  ? "paintPlan.historicalOutputHeading"
                  : "paintPlan.outputHeading",
              )}
            </h2>
            <p>{t("paintPlan.outputCopy")}</p>
          </div>
        </div>

        {viewedPlan === null ? (
          <div className="paint-plan-empty">
            <h3>{t("paintPlan.noPlanHeading")}</h3>
            <p>{
              workbench.access_role === "owner"
                ? t("paintPlan.noPlanOwnerCopy")
                : t("paintPlan.noPlanReviewerCopy")
            }</p>
          </div>
        ) : (
          <>
            <div className="paint-plan-record-header">
              <div>
                <span>{t("paintPlan.currentRevision")}</span>
                <strong>{t("paintPlan.versionValue", { version: viewedPlan.version })}</strong>
              </div>
              <div>
                <span>{t("paintPlan.savedLifecycle")}</span>
                <strong>{t(lifecycleKey(viewedPlan.lifecycle))}</strong>
              </div>
              <div>
                <span>{t("paintPlan.effectiveLifecycle")}</span>
                <strong>{t(lifecycleKey(viewedPlan.effective_lifecycle))}</strong>
              </div>
              <div>
                <span>{t("paintPlan.approval")}</span>
                <strong>
                  {t(approvalStatusKey(viewedPlan))}
                </strong>
              </div>
            </div>
            <LatestReviewAudit review={viewedPlan.latest_review} />

            {isHistorical ? (
              <div className="paint-plan-history-boundary" role="status">
                <strong>{t("paintPlan.historicalHeading")}</strong>
                <p>{t("paintPlan.historicalCopy")}</p>
                <button
                  className="button button--secondary"
                  disabled={commandControlsLocked}
                  onClick={() => {
                    setHistoricalPlanId(null);
                    setEditDraft(null);
                    setReviewReasonDraft(null);
                  }}
                  type="button"
                >
                  {t("paintPlan.returnCurrent")}
                </button>
              </div>
            ) : null}
            {viewedPlan.stale ? (
              <div className="paint-plan-stale" role="status">
                <strong>{t("paintPlan.staleHeading")}</strong>
                <p>
                  {t(
                    workbench.access_role === "owner"
                      ? "paintPlan.staleOwnerCopy"
                      : "paintPlan.staleReviewerCopy",
                  )}
                </p>
                <ul>
                  {viewedPlan.stale_reasons.map((reason) => (
                    <li key={reason}>
                      {t(knownBlockerKeys[reason] ?? "paintPlan.blocker.other")}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}

            {editDocument === null ? (
              <PlanDocumentView plan={viewedPlan} />
            ) : (
              <PlanEditor
                disabled={commandControlsLocked}
                document={editDocument}
                onChange={(document) =>
                  setEditDraft((current) =>
                    current === null ? null : { ...current, document },
                  )
                }
              />
            )}

            {!isHistorical ? (
              <div className="paint-plan-actions">
                {viewedPlan.allowed_actions.includes("edit") ? (
                  editDocument === null ? (
                    <button
                      className="button button--secondary"
                      disabled={commandControlsLocked}
                      onClick={() =>
                        setEditDraft({
                          basePlanId: viewedPlan.id,
                          baseVersion: viewedPlan.version,
                          document: cloneDocument(viewedPlan.document),
                          projectId,
                        })
                      }
                      type="button"
                    >
                      {t("paintPlan.editPlan")}
                    </button>
                  ) : (
                    <>
                      <button
                        className="button button--primary"
                        disabled={commandControlsLocked}
                        onClick={saveEdit}
                        type="button"
                      >
                        {command.status === "busy" &&
                        command.labelKey === "paintPlan.savingEdit"
                          ? t("paintPlan.savingEdit")
                          : t("paintPlan.saveExactRevision")}
                      </button>
                      <button
                        className="button button--secondary"
                        disabled={commandControlsLocked}
                        onClick={() => setEditDraft(null)}
                        type="button"
                      >
                        {t("common.cancel")}
                      </button>
                    </>
                  )
                ) : null}
                {viewedPlan.allowed_actions.includes("submit") &&
                editDocument === null ? (
                  <button
                    className="button button--primary"
                    disabled={commandControlsLocked}
                    onClick={submitForReview}
                    type="button"
                  >
                    {t("paintPlan.submitReview")}
                  </button>
                ) : null}
              </div>
            ) : null}

            {!isHistorical &&
            (viewedPlan.allowed_actions.includes("approve") ||
              viewedPlan.allowed_actions.includes("reject")) ? (
              <div className="paint-plan-review">
                <h3>{t("paintPlan.reviewHeading")}</h3>
                <p>{t("paintPlan.reviewCopy")}</p>
                <label>
                  <span>{t("paintPlan.reviewReason")}</span>
                  <textarea
                    disabled={commandControlsLocked}
                    maxLength={1000}
                    onChange={(event) =>
                      setReviewReasonDraft({
                        basePlanId: viewedPlan.id,
                        baseVersion: viewedPlan.version,
                        projectId,
                        value: event.target.value,
                      })
                    }
                    rows={4}
                    value={reviewReason}
                  />
                  <small>{t("paintPlan.rejectReasonRequired")}</small>
                </label>
                <div>
                  {viewedPlan.allowed_actions.includes("approve") ? (
                    <button
                      className="button button--primary"
                      disabled={commandControlsLocked}
                      onClick={() => reviewPlan("approve")}
                      type="button"
                    >
                      {t("paintPlan.approve")}
                    </button>
                  ) : null}
                  {viewedPlan.allowed_actions.includes("reject") ? (
                    <button
                      className="button button--danger"
                      disabled={commandControlsLocked || reviewReason.trim().length === 0}
                      onClick={() => reviewPlan("reject")}
                      type="button"
                    >
                      {t("paintPlan.reject")}
                    </button>
                  ) : null}
                </div>
              </div>
            ) : null}

            <details className="paint-plan-technical">
              <summary>{t("paintPlan.technicalPlan")}</summary>
              <dl>
                <div><dt>{t("paintPlan.planId")}</dt><dd>{viewedPlan.id}</dd></div>
                <div><dt>{t("paintPlan.lineage")}</dt><dd>{viewedPlan.lineage_id} / {t("paintPlan.lineageRevisionValue", { revision: viewedPlan.lineage_revision })}</dd></div>
                <div><dt>{t("paintPlan.invocationId")}</dt><dd>{viewedPlan.source_invocation_id}</dd></div>
                <div><dt>{t("paintPlan.attemptId")}</dt><dd>{viewedPlan.source_attempt_id}</dd></div>
                <div><dt>{t("paintPlan.providerModel")}</dt><dd>{viewedPlan.provider_key} / {viewedPlan.model_id}</dd></div>
                <div><dt>{t("paintPlan.sourceImageFingerprint")}</dt><dd>{viewedPlan.source_image_set_fingerprint}</dd></div>
                <div className="paint-plan-technical__wide">
                  <dt>{t("paintPlan.sourceImageAssets")}</dt>
                  <dd>
                    <ul className="paint-plan-source-assets">
                      {viewedPlan.source_image_assets.map((asset) => (
                        <li key={asset.id}>
                          <strong>{t("paintPlan.sourceImageAssetHeading", { role: t(`image.role.${asset.role}`), version: asset.version })}</strong>
                          <span>{t("paintPlan.sourceImageAssetGeometry", { bytes: asset.byte_length, height: asset.height, mediaType: asset.media_type, width: asset.width })}</span>
                          <span>{t("paintPlan.sourceImageAssetGovernance", { rights: asset.rights_attestation_status, rightsVersion: asset.rights_attestation_version, upload: asset.upload_validation_result, usage: asset.intended_usage.join(", ") })}</span>
                          <code>{t("paintPlan.sourceImageAssetId", { value: asset.id })}</code>
                          <code>{t("paintPlan.sourceImageAssetSha", { value: asset.sha256 })}</code>
                          <code>{t("paintPlan.sourceImageAssetUrl", { value: asset.content_url })}</code>
                        </li>
                      ))}
                    </ul>
                  </dd>
                </div>
                <div><dt>{t("paintPlan.sourceReadinessReview")}</dt><dd>{viewedPlan.source_readiness_review_id} / {t("paintPlan.versionValue", { version: viewedPlan.source_readiness_review_version })}</dd></div>
                <div><dt>{t("paintPlan.sourceRegionSet")}</dt><dd>{viewedPlan.source_region_set_id} / {t("paintPlan.versionValue", { version: viewedPlan.source_region_set_version })}</dd></div>
                <div><dt>{t("paintPlan.sourceGeometryFingerprint")}</dt><dd>{viewedPlan.source_geometry_fingerprint}</dd></div>
                <div><dt>{t("paintPlan.providerDefinitionId")}</dt><dd>{viewedPlan.provider_definition_id} / {t("paintPlan.definitionRevisionValue", { revision: viewedPlan.provider_revision_snapshot })}</dd></div>
                <div><dt>{t("paintPlan.modelDefinitionId")}</dt><dd>{viewedPlan.model_definition_id} / {t("paintPlan.definitionRevisionValue", { revision: viewedPlan.model_revision_snapshot })}</dd></div>
                <div><dt>{t("paintPlan.pricingSnapshotId")}</dt><dd>{viewedPlan.provider_pricing_snapshot_id ?? t("common.unavailable")}</dd></div>
                <div><dt>{t("paintPlan.promptTemplate")}</dt><dd>{viewedPlan.prompt_template_key} / {viewedPlan.prompt_template_id} / {t("paintPlan.versionValue", { version: viewedPlan.prompt_version })}</dd></div>
                <div><dt>{t("paintPlan.promptHash")}</dt><dd>{viewedPlan.prompt_hash}</dd></div>
                <div><dt>{t("paintPlan.generationLocale")}</dt><dd>{viewedPlan.generation_locale}</dd></div>
                <div><dt>{t("paintPlan.generatedFixtureTitle")}</dt><dd>{viewedPlan.document.title}</dd></div>
                <div><dt>{t("paintPlan.contentHash")}</dt><dd>{viewedPlan.content_hash}</dd></div>
                <div><dt>{t("paintPlan.schemaVersion")}</dt><dd>{viewedPlan.schema_version}</dd></div>
                <div><dt>{t("paintPlan.providerRequestId")}</dt><dd>{viewedPlan.provider_request_id_status === "provided" && viewedPlan.provider_request_id !== null ? viewedPlan.provider_request_id : t(`paintPlan.providerRequestStatus.${viewedPlan.provider_request_id_status}`)}</dd></div>
                <div><dt>{t("paintPlan.usageStatus")}</dt><dd>{t(`paintPlan.measurementStatus.${viewedPlan.usage_measurement_status}`)}</dd></div>
                <div><dt>{t("paintPlan.inputUnits")}</dt><dd>{viewedPlan.input_units === null ? t("paintPlan.measurementUnavailable") : t("paintPlan.unitsValue", { value: viewedPlan.input_units })}</dd></div>
                <div><dt>{t("paintPlan.outputUnits")}</dt><dd>{viewedPlan.output_units === null ? t("paintPlan.measurementUnavailable") : t("paintPlan.unitsValue", { value: viewedPlan.output_units })}</dd></div>
                <div><dt>{t("paintPlan.costStatus")}</dt><dd>{t(`paintPlan.measurementStatus.${viewedPlan.cost_measurement_status}`)}</dd></div>
                <div><dt>{t("paintPlan.recordedCost")}</dt><dd>{viewedPlan.cost_minor_units === null ? t("paintPlan.costUnavailable") : viewedPlan.cost_currency === "USD" || viewedPlan.cost_currency === "CNY" ? new Intl.NumberFormat(i18n.resolvedLanguage ?? "en-US", { currency: viewedPlan.cost_currency, style: "currency" }).format(viewedPlan.cost_minor_units / 100) : t("paintPlan.fixtureCreditsValue", { amount: viewedPlan.cost_minor_units })}</dd></div>
                <div><dt>{t("paintPlan.requestedByUser")}</dt><dd>{viewedPlan.requested_by_user_id}</dd></div>
                <div><dt>{t("paintPlan.invocationCreatedAt")}</dt><dd><time dateTime={viewedPlan.invocation_created_at}>{formatProjectTimestamp(viewedPlan.invocation_created_at)}</time></dd></div>
                <div><dt>{t("paintPlan.createdBy")}</dt><dd>{t(`paintPlan.actorType.${viewedPlan.created_by_actor_type}`)} / {viewedPlan.created_by_actor_display_name_snapshot} ({viewedPlan.created_by_actor_id})</dd></div>
                <div><dt>{t("paintPlan.createdAt")}</dt><dd><time dateTime={viewedPlan.created_at}>{formatProjectTimestamp(viewedPlan.created_at)}</time></dd></div>
              </dl>
            </details>
          </>
        )}
      </section>

      <section
        aria-labelledby="paint-plan-history-heading"
        className="paint-plan-history"
      >
        <div className="section-heading">
          <div>
            <p className="context-label">{t("paintPlan.stepHistory")}</p>
            <h2 id="paint-plan-history-heading">{t("paintPlan.historyHeading")}</h2>
            <p>{t("paintPlan.historyCopy")}</p>
          </div>
        </div>
        {workbench.history.length === 0 ? (
          <p className="paint-plan-history__empty">{t("paintPlan.noHistory")}</p>
        ) : (
          <ol>
            {workbench.history.map((plan) => (
              <li key={plan.id}>
                <div className="paint-plan-history__record">
                  <div className="paint-plan-history__facts">
                    <strong>{t("paintPlan.versionValue", { version: plan.version })}</strong>
                    <span>{t("paintPlan.historySavedLifecycle", { lifecycle: t(lifecycleKey(plan.lifecycle)) })}</span>
                    <span>{t("paintPlan.historyEffectiveLifecycle", { lifecycle: t(lifecycleKey(plan.effective_lifecycle)) })}</span>
                    <span>{t("paintPlan.historyApproval", { approval: t(approvalStatusKey(plan)) })}</span>
                    <time dateTime={plan.created_at}>
                      {formatProjectTimestamp(plan.created_at)}
                    </time>
                  </div>
                  <LatestReviewAudit compact review={plan.latest_review} />
                </div>
                <button
                  aria-label={t(
                    plan.is_current
                      ? "paintPlan.viewCurrentRevisionLabel"
                      : "paintPlan.viewHistoricalRevisionLabel",
                    { version: plan.version },
                  )}
                  aria-pressed={
                    plan.is_current
                      ? historicalPlanId === null
                      : historicalPlanId === plan.id
                  }
                  className="button button--quiet"
                  disabled={commandControlsLocked || editDocument !== null}
                  onClick={() => {
                    setHistoricalPlanId(plan.is_current ? null : plan.id);
                    setEditDraft(null);
                    setReviewReasonDraft(null);
                  }}
                  type="button"
                >
                  {plan.is_current
                    ? t("paintPlan.viewCurrent")
                    : t("paintPlan.viewHistorical")}
                </button>
              </li>
            ))}
          </ol>
        )}
      </section>
    </div>
  );
}
