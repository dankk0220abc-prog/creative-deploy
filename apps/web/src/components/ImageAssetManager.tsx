import {
  type ChangeEvent,
  type FormEvent,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import {
  createImageIdempotencyKey,
  createReadinessReview,
  getImageSet,
  imageIntendedUsages,
  ImageAssetApiError,
  type ImageIntendedUsage,
  type ImageRole,
  type ImageSet,
  type ImageSetReadinessReview,
  type ImageSourceType,
  imageSourceTypes,
  listReadinessReviews,
  type ReadinessVerdict,
  uploadImageAsset,
} from "../api/imageAssets";
import type { PaintProject, WorkflowStatus } from "../api/paintProjects";
import { useAppTranslation } from "../i18n";
import { formatProjectTimestamp } from "../utils/format";
import { formatProjectStatus } from "../utils/format";
import { FeedbackPanel } from "./FeedbackPanel";

const MAX_IMAGE_BYTES = 20 * 1024 * 1024;
const acceptedImageTypes = new Set(["image/jpeg", "image/png", "image/webp"]);
const primaryReplacementStates = new Set<WorkflowStatus>([
  "IMAGE_REVIEW_REQUIRED",
  "IMAGE_VALIDATION_FAILED",
]);
const referenceMutationStates = new Set<WorkflowStatus>([
  "DRAFT",
  "IMAGE_UPLOADED",
  "IMAGE_REVIEW_REQUIRED",
  "IMAGE_VALIDATION_FAILED",
]);

const roleLabelKeys: Record<ImageRole, string> = {
  primary_front: "image.role.primary_front",
  reference_back: "image.role.reference_back",
  reference_angle: "image.role.reference_angle",
  reference_detail: "image.role.reference_detail",
};

const roleDescriptionKeys: Record<ImageRole, string> = {
  primary_front: "image.roleDescription.primary_front",
  reference_back: "image.roleDescription.reference_back",
  reference_angle: "image.roleDescription.reference_angle",
  reference_detail: "image.roleDescription.reference_detail",
};

const sourceLabelKeys: Record<ImageSourceType, string> = {
  user_provided: "image.source.user_provided",
  user_photographed: "image.source.user_photographed",
  user_provided_other: "image.source.user_provided_other",
};

const usageLabelKeys: Record<ImageIntendedUsage, string> = {
  private_project: "image.usage.private_project",
  portfolio_demo: "image.usage.portfolio_demo",
  public_repository: "image.usage.public_repository",
};

const checklistLabelKeys = {
  required_roles_present: "image.check.required_roles_present",
  deterministic_validation_accepted: "image.check.deterministic_validation_accepted",
  rights_complete: "image.check.rights_complete",
  content_distinct: "image.check.content_distinct",
  objects_available: "image.check.objects_available",
  snapshot_current: "image.check.snapshot_current",
} as const;

interface ImageAssetManagerProps {
  canManageImages?: boolean;
  onProjectChanged: () => void;
  project: PaintProject;
}

interface CommandAttempt {
  fingerprint: string;
  idempotencyKey: string;
}

interface ImageMutationPermission {
  allowed: boolean;
  operation: "first upload" | "replacement";
}

type WorkbenchState =
  | { status: "error"; error: ImageAssetApiError }
  | {
      status: "loaded";
      imageSet: ImageSet;
      reviews: ImageSetReadinessReview[];
    }
  | { status: "loading" };

function asImageApiError(error: unknown): ImageAssetApiError {
  if (error instanceof ImageAssetApiError) {
    return error;
  }
  return new ImageAssetApiError(
    "internal",
    "The image-set request could not be completed safely.",
  );
}

function uploadFingerprint(
  role: ImageRole,
  file: File,
  sourceType: ImageSourceType,
  intendedUsage: ImageIntendedUsage[],
): string {
  return [
    role,
    file.name,
    file.size,
    file.lastModified,
    file.type,
    sourceType,
    [...intendedUsage].sort().join(","),
  ].join("\u001f");
}

function reviewFingerprint(
  imageSetFingerprint: string,
  verdict: ReadinessVerdict,
  reason: string,
): string {
  return [imageSetFingerprint, verdict, reason.trim()].join("\u001f");
}

function commandErrorKey(error: ImageAssetApiError): string {
  if (error.kind === "network") {
    return "image.error.network";
  }
  if (error.kind === "storage") {
    return "image.error.storage";
  }
  if (error.kind === "conflict") {
    return "image.error.conflict";
  }
  if (error.kind === "validation") {
    if (error.errorCode === "REJECTED_DIMENSIONS") {
      return "image.error.dimensions";
    }
    if (error.errorCode === "REJECTED_TOO_LARGE") {
      return "image.error.tooLarge";
    }
    if (error.errorCode === "REJECTED_PIXEL_LIMIT") {
      return "image.error.pixelLimit";
    }
    if (
      error.errorCode === "REJECTED_UNSUPPORTED_FORMAT" ||
      error.errorCode === "REJECTED_CONTENT_TYPE_MISMATCH"
    ) {
      return "image.error.format";
    }
    if (error.errorCode === "REJECTED_CORRUPT") {
      return "image.error.corrupt";
    }
    return "image.error.validation";
  }
  if (error.kind === "not_found") {
    return "image.error.notFound";
  }
  return "image.error.unexpected";
}

function statusHeadingKey(imageSet: ImageSet): string {
  if (imageSet.status === "ready") {
    return "image.status.ready";
  }
  if (imageSet.status === "stale") {
    return "image.status.stale";
  }
  if (imageSet.status === "not_ready") {
    return "image.status.notReady";
  }
  return "image.status.incomplete";
}

function imageMutationPermission(
  projectStatus: WorkflowStatus,
  role: ImageRole,
  hasCurrentAsset: boolean,
): ImageMutationPermission {
  const operation = hasCurrentAsset ? "replacement" : "first upload";
  if (role === "primary_front") {
    return {
      allowed: hasCurrentAsset
        ? primaryReplacementStates.has(projectStatus)
        : projectStatus === "DRAFT",
      operation,
    };
  }
  return {
    allowed: referenceMutationStates.has(projectStatus),
    operation,
  };
}

function imageMutationLockKey(
  projectStatus: WorkflowStatus,
  role: ImageRole,
  operation: ImageMutationPermission["operation"],
): string {
  if (projectStatus === "IMAGE_VALIDATED") {
    return "image.lock.validated";
  }
  if (role === "primary_front") {
    if (operation === "first upload") {
      return "image.lock.firstPrimary";
    }
    return "image.lock.replacePrimary";
  }
  return "image.lock.reference";
}

export function ImageAssetManager({
  canManageImages = true,
  onProjectChanged,
  project,
}: ImageAssetManagerProps) {
  const { t } = useAppTranslation();
  const [state, setState] = useState<WorkbenchState>({ status: "loading" });
  const [reloadToken, setReloadToken] = useState(0);
  const [selectedRole, setSelectedRole] =
    useState<ImageRole>("primary_front");
  const [file, setFile] = useState<File | null>(null);
  const [sourceType, setSourceType] =
    useState<ImageSourceType>("user_provided");
  const [intendedUsage, setIntendedUsage] = useState<ImageIntendedUsage[]>([
    "private_project",
  ]);
  const [rightsConfirmed, setRightsConfirmed] = useState(false);
  const [uploadError, setUploadError] = useState<ImageAssetApiError | null>(null);
  const [uploadFormError, setUploadFormError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadSucceeded, setUploadSucceeded] = useState(false);
  const uploadAttemptRef = useRef<CommandAttempt | null>(null);
  const uploadInFlightRef = useRef(false);

  const [verdict, setVerdict] = useState<ReadinessVerdict>("ready");
  const [reason, setReason] = useState("");
  const [reviewError, setReviewError] = useState<ImageAssetApiError | null>(null);
  const [reviewFormError, setReviewFormError] = useState<string | null>(null);
  const [reviewing, setReviewing] = useState(false);
  const [reviewSucceeded, setReviewSucceeded] = useState(false);
  const reviewAttemptRef = useRef<CommandAttempt | null>(null);
  const reviewInFlightRef = useRef(false);

  useEffect(() => {
    const controller = new AbortController();
    void Promise.all([
      getImageSet(project.id, controller.signal),
      listReadinessReviews(project.id, controller.signal),
    ])
      .then(([imageSet, history]) => {
        if (!controller.signal.aborted) {
          setState({ status: "loaded", imageSet, reviews: history.items });
        }
      })
      .catch((error: unknown) => {
        const apiError = asImageApiError(error);
        if (!controller.signal.aborted && apiError.kind !== "aborted") {
          setState({ status: "error", error: apiError });
        }
      });
    return () => controller.abort();
  }, [project.id, reloadToken]);

  const imageSet = state.status === "loaded" ? state.imageSet : null;
  const selectedSlot = useMemo(
    () => imageSet?.roles.find((slot) => slot.role === selectedRole) ?? null,
    [imageSet, selectedRole],
  );
  const selectedMutation =
    selectedSlot === null
      ? null
      : imageMutationPermission(
          project.status,
          selectedRole,
          selectedSlot.current !== null,
        );
  const uploadAllowed =
    canManageImages && (selectedMutation?.allowed ?? false);

  const reloadWorkbench = useCallback(() => {
    setState({ status: "loading" });
    setReloadToken((current) => current + 1);
  }, []);

  const clearUploadAttempt = useCallback(() => {
    uploadAttemptRef.current = null;
    setUploadError(null);
    setUploadSucceeded(false);
  }, []);

  const clearReviewAttempt = useCallback(() => {
    reviewAttemptRef.current = null;
    setReviewError(null);
    setReviewSucceeded(false);
  }, []);

  function chooseRole(role: ImageRole) {
    clearUploadAttempt();
    setUploadFormError(null);
    setFile(null);
    setRightsConfirmed(false);
    setSelectedRole(role);
  }

  function updateFile(event: ChangeEvent<HTMLInputElement>) {
    clearUploadAttempt();
    setUploadFormError(null);
    setFile(event.target.files?.item(0) ?? null);
  }

  function updateSource(event: ChangeEvent<HTMLSelectElement>) {
    clearUploadAttempt();
    setUploadFormError(null);
    setSourceType(event.target.value as ImageSourceType);
  }

  function toggleUsage(usage: ImageIntendedUsage) {
    clearUploadAttempt();
    setUploadFormError(null);
    setIntendedUsage((current) =>
      current.includes(usage)
        ? current.filter((item) => item !== usage)
        : [...current, usage],
    );
  }

  async function submitUpload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (uploadInFlightRef.current || !uploadAllowed) {
      return;
    }
    setUploadFormError(null);
    setUploadSucceeded(false);
    if (file === null) {
      setUploadFormError("image.form.choose");
      return;
    }
    if (!acceptedImageTypes.has(file.type)) {
      setUploadFormError("image.form.type");
      return;
    }
    if (file.size < 1 || file.size > MAX_IMAGE_BYTES) {
      setUploadFormError("image.form.size");
      return;
    }
    if (intendedUsage.length === 0) {
      setUploadFormError("image.form.usage");
      return;
    }
    if (!rightsConfirmed) {
      setUploadFormError("image.form.rights");
      return;
    }

    const fingerprint = uploadFingerprint(
      selectedRole,
      file,
      sourceType,
      intendedUsage,
    );
    if (
      uploadAttemptRef.current === null ||
      uploadAttemptRef.current.fingerprint !== fingerprint
    ) {
      uploadAttemptRef.current = {
        fingerprint,
        idempotencyKey: createImageIdempotencyKey(),
      };
    }
    const attempt = uploadAttemptRef.current;
    uploadInFlightRef.current = true;
    setUploading(true);
    setUploadError(null);
    try {
      await uploadImageAsset(
        project.id,
        {
          file,
          intendedUsage,
          role: selectedRole,
          sourceType,
        },
        attempt.idempotencyKey,
      );
      uploadAttemptRef.current = null;
      setFile(null);
      setRightsConfirmed(false);
      setUploadSucceeded(true);
      reloadWorkbench();
      onProjectChanged();
    } catch (error: unknown) {
      const apiError = asImageApiError(error);
      if (!apiError.retryable) {
        uploadAttemptRef.current = null;
      }
      setUploadError(apiError);
    } finally {
      uploadInFlightRef.current = false;
      setUploading(false);
    }
  }

  async function submitReview(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (reviewInFlightRef.current || imageSet === null) {
      return;
    }
    setReviewFormError(null);
    setReviewSucceeded(false);
    const normalizedReason = reason.trim();
    if (verdict === "not_ready" && normalizedReason.length === 0) {
      setReviewFormError("image.review.reasonRequired");
      return;
    }
    if (normalizedReason.length > 1000) {
      setReviewFormError("image.review.reasonLength");
      return;
    }
    if (verdict === "ready" && !imageSet.checklist.can_mark_ready) {
      setReviewFormError("image.review.blockers");
      return;
    }

    const fingerprint = reviewFingerprint(
      imageSet.image_set_fingerprint,
      verdict,
      normalizedReason,
    );
    if (
      reviewAttemptRef.current === null ||
      reviewAttemptRef.current.fingerprint !== fingerprint
    ) {
      reviewAttemptRef.current = {
        fingerprint,
        idempotencyKey: createImageIdempotencyKey(),
      };
    }
    const attempt = reviewAttemptRef.current;
    reviewInFlightRef.current = true;
    setReviewing(true);
    setReviewError(null);
    try {
      await createReadinessReview(
        project.id,
        {
          verdict,
          reason: normalizedReason.length === 0 ? null : normalizedReason,
        },
        attempt.idempotencyKey,
      );
      reviewAttemptRef.current = null;
      setReason("");
      setReviewSucceeded(true);
      reloadWorkbench();
    } catch (error: unknown) {
      const apiError = asImageApiError(error);
      if (!apiError.retryable) {
        reviewAttemptRef.current = null;
      }
      setReviewError(apiError);
    } finally {
      reviewInFlightRef.current = false;
      setReviewing(false);
    }
  }

  return (
    <section
      aria-labelledby="image-set-heading"
      className="image-assets image-set-workbench"
      data-project-status={project.status}
      id="image-set-workbench"
    >
      <div className="section-heading image-assets__heading">
        <div>
          <p className="context-label">{t("image.eyebrow")}</p>
          <h2 id="image-set-heading">{t("image.heading")}</h2>
        </div>
        <span className="image-assets__slot">{t("image.formalRoles")}</span>
      </div>

      <p className="image-assets__boundary">{t("image.boundary")}</p>

      {state.status === "loading" ? (
        <div aria-busy="true" className="image-assets__loading">
          <progress aria-label={t("image.loadingLabel")} />
          <p role="status">{t("image.loading")}</p>
        </div>
      ) : null}

      {state.status === "error" ? (
        <FeedbackPanel
          action={{
            label: t("image.retry"),
            onClick: reloadWorkbench,
          }}
          eyebrow={t("image.unavailable")}
          heading={t("image.unavailableHeading")}
          kind="error"
        >
          <p>{t("image.unavailableCopy")}</p>
        </FeedbackPanel>
      ) : null}

      {imageSet === null ? null : (
        <>
          <section
            aria-labelledby="image-set-status-heading"
            className={`image-set-status image-set-status--${imageSet.status}`}
          >
            <p className="context-label">{t("image.currentState")}</p>
            <h3 id="image-set-status-heading">{t(statusHeadingKey(imageSet))}</h3>
            {imageSet.status === "stale" ? (
              <p>{t("image.staleCopy")}</p>
            ) : null}
            {imageSet.status === "ready" ? (
              <p>{t("image.readyCopy")}</p>
            ) : null}
          </section>

          <div className="image-role-grid">
            {imageSet.roles.map((slot) => {
              const mutation = imageMutationPermission(
                project.status,
                slot.role,
                slot.current !== null,
              );
              return (
                <article
                  aria-labelledby={`image-role-${slot.role}`}
                  className={`image-role-card ${
                    selectedRole === slot.role ? "image-role-card--selected" : ""
                  }`}
                  key={slot.role}
                >
                <header>
                  <div>
                    <p className="context-label">
                      {slot.required ? t("image.requiredRole") : t("image.optionalRole")}
                    </p>
                    <h3 id={`image-role-${slot.role}`}>
                      {t(roleLabelKeys[slot.role])}
                    </h3>
                  </div>
                  <span
                    className={`role-state role-state--${
                      slot.missing
                        ? "missing"
                        : slot.object_available
                          ? "available"
                          : "unavailable"
                    }`}
                  >
                    {slot.missing
                      ? t("image.missing")
                      : slot.object_available
                        ? t("image.available")
                        : t("common.unavailable")}
                  </span>
                </header>
                <p>{t(roleDescriptionKeys[slot.role])}</p>

                {slot.current === null ? (
                  <div className="image-role-card__empty">
                    <span aria-hidden="true">+</span>
                    <p>{t("image.noCurrent")}</p>
                  </div>
                ) : (
                  <>
                    <div className="image-card__preview">
                      <img
                        alt={t("image.previewAlt", {
                          role: t(roleLabelKeys[slot.role]),
                          filename: slot.current.original_filename,
                        })}
                        src={slot.current.content_url}
                      />
                    </div>
                    <dl className="image-role-card__facts">
                      <div>
                        <dt>{t("common.version")}</dt>
                        <dd>{slot.current.version}</dd>
                      </div>
                      <div>
                        <dt>{t("image.dimensions")}</dt>
                        <dd>
                          {slot.current.width} × {slot.current.height}
                        </dd>
                      </div>
                      <div>
                        <dt>{t("image.uploadChecks")}</dt>
                        <dd>{t("common.accepted")}</dd>
                      </div>
                      <div>
                        <dt>{t("image.rights")}</dt>
                        <dd>
                          {slot.current.rights_attestation_status === "confirmed"
                            ? t("image.attested")
                            : t("common.incomplete")}
                        </dd>
                      </div>
                    </dl>
                  </>
                )}

                {slot.history.length > 1 ? (
                  <details className="image-history image-role-card__history">
                    <summary>
                      {t("image.versionHistory", { count: slot.history.length })}
                    </summary>
                    <ol>
                      {slot.history.map((image) => (
                        <li key={image.id}>
                          <span>
                            v{image.version} · {image.original_filename}
                          </span>
                          <a
                            href={image.content_url}
                            rel="noreferrer"
                            target="_blank"
                          >
                            {t("image.openOriginal")}
                          </a>
                        </li>
                      ))}
                    </ol>
                  </details>
                ) : null}

                {canManageImages && mutation.allowed ? (
                  <button
                    aria-pressed={selectedRole === slot.role}
                    className="button button--secondary image-role-card__action"
                    disabled={uploading}
                    onClick={() => chooseRole(slot.role)}
                    type="button"
                  >
                    {slot.current === null ? t("image.addRole") : t("image.replaceSafely")}
                  </button>
                ) : (
                  <p className="image-role-card__lock">
                    {t(imageMutationLockKey(project.status, slot.role, mutation.operation), {
                      operation: t(mutation.operation === "first upload" ? "image.operation.first" : "image.operation.replacement"),
                      status: formatProjectStatus(project.status),
                    })}
                  </p>
                )}
                </article>
              );
            })}
          </div>

          {!canManageImages ? (
            <aside className="image-assets__locked" role="note">
              <p className="context-label">{t("image.reviewerAccess")}</p>
              <h3>{t("image.ownerOnly")}</h3>
              <p>{t("image.ownerOnlyCopy")}</p>
            </aside>
          ) : !uploadAllowed ? (
            <aside className="image-assets__locked" role="note">
              <p className="context-label">{t("image.workflowControlled")}</p>
              <h3>
                {t("image.lockHeading", {
                  role: t(roleLabelKeys[selectedRole]),
                  operation: selectedMutation === null
                    ? t("common.unknown")
                    : t(selectedMutation.operation === "first upload" ? "image.operation.first" : "image.operation.replacement"),
                  status: formatProjectStatus(project.status),
                })}
              </h3>
              <p>
                {t(imageMutationLockKey(
                  project.status,
                  selectedRole,
                  selectedMutation?.operation ?? "first upload",
                ), {
                  operation: t((selectedMutation?.operation ?? "first upload") === "first upload" ? "image.operation.first" : "image.operation.replacement"),
                  status: formatProjectStatus(project.status),
                })}
              </p>
              <p>{t("image.historyReadable")}</p>
            </aside>
          ) : (
            <form
              aria-labelledby="role-upload-heading"
              className="image-upload image-set-upload"
              noValidate
              onSubmit={submitUpload}
            >
              <div>
                <p className="context-label">
                  {selectedSlot?.current === null
                    ? t("image.fillRole")
                    : t("image.controlledReplacement")}
                </p>
                <h3 id="role-upload-heading">
                  {selectedSlot?.current === null
                    ? t("image.addHeading", { role: t(roleLabelKeys[selectedRole]) })
                    : t("image.replaceHeading", { role: t(roleLabelKeys[selectedRole]) })}
                </h3>
                <p>{t("image.replacementCopy")}</p>
              </div>

              <div className="image-upload__grid">
                <div className="image-upload__field">
                  <label htmlFor="role-image-file">{t("image.file")}</label>
                  <input
                    accept=".jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp"
                    aria-describedby={`role-image-file-help${
                      uploadFormError === "image.form.choose" ||
                      uploadFormError === "image.form.type" ||
                      uploadFormError === "image.form.size"
                        ? " image-upload-form-error"
                        : ""
                    }`}
                    aria-invalid={
                      uploadFormError === "image.form.choose" ||
                      uploadFormError === "image.form.type" ||
                      uploadFormError === "image.form.size"
                        ? true
                        : undefined
                    }
                    disabled={uploading}
                    id="role-image-file"
                    name="role-image-file"
                    onChange={updateFile}
                    type="file"
                  />
                  <p id="role-image-file-help">{t("image.fileRules")}</p>
                </div>

                <div className="image-upload__field">
                  <label htmlFor="image-source-type">{t("image.source")}</label>
                  <select
                    disabled={uploading}
                    id="image-source-type"
                    onChange={updateSource}
                    value={sourceType}
                  >
                    {imageSourceTypes.map((source) => (
                      <option key={source} value={source}>
                        {t(sourceLabelKeys[source])}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <fieldset
                aria-describedby={
                  uploadFormError === "image.form.usage"
                    ? "image-upload-form-error"
                    : undefined
                }
                aria-invalid={
                  uploadFormError === "image.form.usage" ? true : undefined
                }
                className="image-upload__choices"
                disabled={uploading}
              >
                <legend>{t("image.intendedUse")}</legend>
                {imageIntendedUsages.map((usage) => (
                  <label key={usage}>
                    <input
                      checked={intendedUsage.includes(usage)}
                      onChange={() => toggleUsage(usage)}
                      type="checkbox"
                    />
                    <span>{t(usageLabelKeys[usage])}</span>
                  </label>
                ))}
              </fieldset>

              <label className="image-upload__attestation">
                <input
                  aria-describedby={
                    uploadFormError === "image.form.rights"
                      ? "image-upload-form-error"
                      : undefined
                  }
                  aria-invalid={
                    uploadFormError === "image.form.rights" ? true : undefined
                  }
                  checked={rightsConfirmed}
                  disabled={uploading}
                  onChange={(event) => {
                    clearUploadAttempt();
                    setUploadFormError(null);
                    setRightsConfirmed(event.target.checked);
                  }}
                  type="checkbox"
                />
                <span>
                  {t("image.attestation")}
                </span>
              </label>

              {uploadFormError === null ? null : (
                <p
                  className="image-upload__error"
                  id="image-upload-form-error"
                  role="alert"
                >
                  {t(uploadFormError)}
                </p>
              )}
              {uploadError === null ? null : (
                <div className="image-upload__error" role="alert">
                  <p>{t(commandErrorKey(uploadError))}</p>
                  {uploadError.retryable ? (
                    <p>
                      {t("image.retryUnchanged")}
                    </p>
                  ) : null}
                </div>
              )}
              {uploadSucceeded ? (
                <p className="image-upload__success" role="status">
                  {t("image.uploadSuccess")}
                </p>
              ) : null}
              {uploading ? (
                <div aria-busy="true" className="image-upload__progress">
                  <progress aria-label={t("image.uploadingLabel")} />
                  <p role="status">{t("image.uploading")}</p>
                </div>
              ) : null}

              <div className="image-upload__actions">
                <button
                  aria-busy={uploading}
                  className="button button--primary"
                  disabled={uploading}
                  type="submit"
                >
                  {uploading
                    ? t("image.storing")
                    : selectedSlot?.current === null
                      ? t("image.store", { role: t(roleLabelKeys[selectedRole]) })
                      : t("image.storeReplacement", { role: t(roleLabelKeys[selectedRole]) })}
                </button>
              </div>
            </form>
          )}

          <section
            aria-labelledby="readiness-checklist-heading"
            className="readiness-panel"
          >
            <div className="section-heading">
              <div>
                <p className="context-label">{t("image.checklistEyebrow")}</p>
                <h3 id="readiness-checklist-heading">{t("image.checklistHeading")}</h3>
              </div>
            </div>
            <ul className="readiness-checklist">
              {(
                Object.keys(checklistLabelKeys) as Array<
                  keyof typeof checklistLabelKeys
                >
              ).map((key) => {
                const passed = imageSet.checklist[key];
                return (
                  <li className={passed ? "is-pass" : "is-blocked"} key={key}>
                    <span aria-hidden="true" />
                    <span>{t(checklistLabelKeys[key])}</span>
                  </li>
                );
              })}
            </ul>
            {imageSet.checklist.required_roles_present &&
            !imageSet.checklist.content_distinct ? (
              <p className="readiness-warning" role="alert">
                {t("image.duplicateWarning")}
              </p>
            ) : null}
          </section>

          <section
            aria-labelledby="readiness-review-heading"
            className="readiness-panel readiness-review"
          >
            <div className="section-heading">
              <div>
                <p className="context-label">{t("image.reviewEyebrow")}</p>
                <h3 id="readiness-review-heading">{t("image.reviewHeading")}</h3>
              </div>
            </div>

            {imageSet.latest_review === null ? (
              <p>{t("image.reviewEmpty")}</p>
            ) : (
              <article className="latest-review">
                <p className="context-label">
                  {t("image.latestReview", { version: imageSet.latest_review.version })}
                </p>
                <h4>
                  {imageSet.latest_review.verdict === "ready"
                    ? t("image.ready")
                    : t("image.notReady")}
                </h4>
                <p>
                  {imageSet.latest_review.reason ??
                    t("image.defaultReason")}
                </p>
                <p>
                  {t("image.by", {
                    name: imageSet.latest_review.actor_display_name_snapshot,
                    date: formatProjectTimestamp(imageSet.latest_review.created_at),
                  })}
                </p>
              </article>
            )}

            <form className="readiness-form" noValidate onSubmit={submitReview}>
              <fieldset disabled={reviewing}>
                <legend>{t("image.humanVerdict")}</legend>
                <label>
                  <input
                    checked={verdict === "ready"}
                    name="readiness-verdict"
                    onChange={() => {
                      clearReviewAttempt();
                      setReviewFormError(null);
                      setVerdict("ready");
                    }}
                    type="radio"
                  />
                  <span>{t("image.ready")}</span>
                </label>
                <label>
                  <input
                    checked={verdict === "not_ready"}
                    name="readiness-verdict"
                    onChange={() => {
                      clearReviewAttempt();
                      setReviewFormError(null);
                      setVerdict("not_ready");
                    }}
                    type="radio"
                  />
                  <span>{t("image.notReady")}</span>
                </label>
              </fieldset>

              <div className="image-upload__field">
                <label htmlFor="readiness-reason">
                  {verdict === "not_ready" ? t("image.reasonRequired") : t("image.reasonOptional")}
                </label>
                <textarea
                  aria-describedby={`readiness-reason-help${
                    reviewFormError === "image.review.reasonRequired" ||
                    reviewFormError === "image.review.reasonLength"
                      ? " readiness-review-form-error"
                      : ""
                  }`}
                  aria-invalid={
                    reviewFormError === "image.review.reasonRequired" ||
                    reviewFormError === "image.review.reasonLength"
                      ? true
                      : undefined
                  }
                  disabled={reviewing}
                  id="readiness-reason"
                  maxLength={1000}
                  onChange={(event) => {
                    clearReviewAttempt();
                    setReviewFormError(null);
                    setReason(event.target.value);
                  }}
                  rows={4}
                  value={reason}
                />
                <p id="readiness-reason-help">{t("image.reasonHelp")}</p>
              </div>

              {reviewFormError === null ? null : (
                <p
                  className="image-upload__error"
                  id="readiness-review-form-error"
                  role="alert"
                >
                  {t(reviewFormError)}
                </p>
              )}
              {reviewError === null ? null : (
                <div className="image-upload__error" role="alert">
                  <p>{t(commandErrorKey(reviewError))}</p>
                  {reviewError.retryable ? (
                    <p>
                      {t("image.retryReviewUnchanged")}
                    </p>
                  ) : null}
                </div>
              )}
              {reviewSucceeded ? (
                <p className="image-upload__success" role="status">
                  {t("image.reviewSuccess")}
                </p>
              ) : null}

              <button
                aria-busy={reviewing}
                className="button button--primary"
                disabled={
                  reviewing ||
                  (verdict === "ready" &&
                    !imageSet.checklist.can_mark_ready)
                }
                type="submit"
              >
                {reviewing
                  ? t("image.savingReview")
                  : verdict === "ready"
                    ? t("image.confirmReady")
                    : t("image.recordNotReady")}
              </button>
            </form>

            {state.status === "loaded" && state.reviews.length > 0 ? (
              <details className="review-history">
                <summary>{t("image.reviewHistory", { count: state.reviews.length })}</summary>
                <ol>
                  {state.reviews.map((review) => (
                    <li key={review.id}>
                      <strong>
                        v{review.version} ·{" "}
                        {review.verdict === "ready" ? t("image.ready") : t("image.notReady")}
                      </strong>
                      <span>
                        {review.reason ?? t("image.noReason")} ·{" "}
                        {formatProjectTimestamp(review.created_at)}
                      </span>
                    </li>
                  ))}
                </ol>
              </details>
            ) : null}
          </section>
        </>
      )}
    </section>
  );
}
