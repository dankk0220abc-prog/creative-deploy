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
import { formatProjectTimestamp } from "../utils/format";
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

const roleLabels: Record<ImageRole, string> = {
  primary_front: "Primary front",
  reference_back: "Reference back",
  reference_angle: "Reference angle",
  reference_detail: "Reference detail",
};

const roleDescriptions: Record<ImageRole, string> = {
  primary_front: "The formal front view and Phase 1E-1 compatible primary image.",
  reference_back: "A distinct back reference for later human-guided planning.",
  reference_angle: "A distinct angled reference for later human-guided planning.",
  reference_detail: "An optional detail reference; it does not block minimum readiness.",
};

const sourceLabels: Record<ImageSourceType, string> = {
  user_provided: "Provided by me",
  user_photographed: "Photographed by me",
  user_provided_other: "Provided by another source",
};

const usageLabels: Record<ImageIntendedUsage, string> = {
  private_project: "Private project planning",
  portfolio_demo: "Portfolio demonstration",
  public_repository: "Public repository",
};

const checklistLabels = {
  required_roles_present: "All required roles present",
  deterministic_validation_accepted: "Deterministic upload checks accepted",
  rights_complete: "Rights attestations complete",
  content_distinct: "Required images have distinct content",
  objects_available: "Private objects available and intact",
  snapshot_current: "Latest review matches this image set",
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

function commandErrorMessage(error: ImageAssetApiError): string {
  if (error.kind === "network") {
    return "The API connection was interrupted. Retry keeps the same protected command.";
  }
  if (error.kind === "storage") {
    return "Private image storage is temporarily unavailable. Retry keeps the same protected command.";
  }
  if (error.kind === "conflict") {
    return "The saved command or current image set changed. Refresh before starting a new command.";
  }
  if (error.kind === "validation") {
    if (error.errorCode === "REJECTED_DIMENSIONS") {
      return "Choose an image whose shortest side is at least 768 px and whose longest side is no more than 8192 px, then upload it again.";
    }
    if (error.errorCode === "REJECTED_TOO_LARGE") {
      return "Choose an image no larger than 20 MiB, then upload the smaller file.";
    }
    if (error.errorCode === "REJECTED_PIXEL_LIMIT") {
      return "Choose an image with no more than 40,000,000 total pixels, then upload it again.";
    }
    if (
      error.errorCode === "REJECTED_UNSUPPORTED_FORMAT" ||
      error.errorCode === "REJECTED_CONTENT_TYPE_MISMATCH"
    ) {
      return "Choose a static JPEG, PNG, or WebP file. GIF, SVG, animated WebP, renamed extensions, and mismatched file bytes are not accepted.";
    }
    if (error.errorCode === "REJECTED_CORRUPT") {
      return "Export the image again as a complete static JPEG, PNG, or WebP file, then retry.";
    }
    return "Check the file and declaration: use a static JPEG, PNG, or WebP; keep it within 20 MiB, 768–8192 px, and 40,000,000 pixels; choose an intended use; and confirm the rights statement before retrying.";
  }
  if (error.kind === "not_found") {
    return "The project is no longer available to the current operator.";
  }
  return "The image service returned an incomplete or unexpected response.";
}

function statusHeading(imageSet: ImageSet): string {
  if (imageSet.status === "ready") {
    return "Ready — current human confirmation";
  }
  if (imageSet.status === "stale") {
    return "Stale — image set changed after review";
  }
  if (imageSet.status === "not_ready") {
    return "Not ready — current human decision";
  }
  return "Incomplete — human readiness not confirmed";
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

function imageMutationLockMessage(
  projectStatus: WorkflowStatus,
  role: ImageRole,
  operation: ImageMutationPermission["operation"],
): string {
  if (projectStatus === "IMAGE_VALIDATED") {
    return "All image roles are frozen after image validation.";
  }
  if (role === "primary_front") {
    if (operation === "first upload") {
      return "The first Primary front upload is available only while the project is in DRAFT.";
    }
    return "Primary front replacement is available only when image review is required or image validation has failed.";
  }
  return `This reference-role ${operation} is locked in ${projectStatus}.`;
}

export function ImageAssetManager({
  canManageImages = true,
  onProjectChanged,
  project,
}: ImageAssetManagerProps) {
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
    setSourceType(event.target.value as ImageSourceType);
  }

  function toggleUsage(usage: ImageIntendedUsage) {
    clearUploadAttempt();
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
      setUploadFormError("Choose one JPEG, PNG, or WebP image.");
      return;
    }
    if (!acceptedImageTypes.has(file.type)) {
      setUploadFormError("Choose a JPEG, PNG, or WebP image.");
      return;
    }
    if (file.size < 1 || file.size > MAX_IMAGE_BYTES) {
      setUploadFormError(
        "The image must be larger than 0 bytes and no more than 20 MiB.",
      );
      return;
    }
    if (intendedUsage.length === 0) {
      setUploadFormError("Choose at least one intended use.");
      return;
    }
    if (!rightsConfirmed) {
      setUploadFormError(
        "Confirm the source, rights, and intended-use declaration.",
      );
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
      setReviewFormError("Explain why this image set is not ready.");
      return;
    }
    if (normalizedReason.length > 1000) {
      setReviewFormError("Keep the readiness reason within 1000 characters.");
      return;
    }
    if (verdict === "ready" && !imageSet.checklist.can_mark_ready) {
      setReviewFormError(
        "Resolve every deterministic checklist blocker before confirming READY.",
      );
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
    >
      <div className="section-heading image-assets__heading">
        <div>
          <p className="eyebrow">Phase 1E-2 · Governed private image set</p>
          <h2 id="image-set-heading">Multi-role image-set workbench</h2>
        </div>
        <span className="image-assets__slot">4 formal roles</span>
      </div>

      <p className="image-assets__boundary">
        Upload checks, role completeness, rights records, byte distinctness, and
        private-object availability are deterministic. READY and NOT READY are human
        decisions. No AI analysis, angle recognition, quality score, legal
        verification, public URL, or deletion is provided.
      </p>

      {state.status === "loading" ? (
        <div aria-busy="true" className="image-assets__loading">
          <progress aria-label="Loading image-set workbench" />
          <p role="status">Loading the private image set and review history…</p>
        </div>
      ) : null}

      {state.status === "error" ? (
        <FeedbackPanel
          action={{
            label: "Retry image set",
            onClick: reloadWorkbench,
          }}
          eyebrow="Private image set unavailable"
          heading="The image-set workbench could not be loaded"
          kind="error"
        >
          <p>
            No image or readiness facts were inferred. Retry the owner-scoped API
            request when the service is available.
          </p>
        </FeedbackPanel>
      ) : null}

      {imageSet === null ? null : (
        <>
          <section
            aria-labelledby="image-set-status-heading"
            className={`image-set-status image-set-status--${imageSet.status}`}
          >
            <p className="eyebrow">Current image-set state</p>
            <h3 id="image-set-status-heading">{statusHeading(imageSet)}</h3>
            {imageSet.status === "stale" ? (
              <p>
                The saved review remains immutable history. The current assets no
                longer match its snapshot and require a new human confirmation.
              </p>
            ) : null}
            {imageSet.status === "ready" ? (
              <p>Image set ready for human-guided region planning</p>
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
                    <p className="eyebrow">
                      {slot.required ? "Required role" : "Optional role"}
                    </p>
                    <h3 id={`image-role-${slot.role}`}>
                      {roleLabels[slot.role]}
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
                      ? "Missing"
                      : slot.object_available
                        ? "Available"
                        : "Unavailable"}
                  </span>
                </header>
                <p>{roleDescriptions[slot.role]}</p>

                {slot.current === null ? (
                  <div className="image-role-card__empty">
                    <span aria-hidden="true">+</span>
                    <p>No current asset</p>
                  </div>
                ) : (
                  <>
                    <div className="image-card__preview">
                      <img
                        alt={`Private preview of ${roleLabels[slot.role]}: ${slot.current.original_filename}`}
                        src={slot.current.content_url}
                      />
                    </div>
                    <dl className="image-role-card__facts">
                      <div>
                        <dt>Version</dt>
                        <dd>{slot.current.version}</dd>
                      </div>
                      <div>
                        <dt>Dimensions</dt>
                        <dd>
                          {slot.current.width} × {slot.current.height}
                        </dd>
                      </div>
                      <div>
                        <dt>Upload checks</dt>
                        <dd>Accepted</dd>
                      </div>
                      <div>
                        <dt>Rights</dt>
                        <dd>
                          {slot.current.rights_attestation_status === "confirmed"
                            ? "Attested"
                            : "Incomplete"}
                        </dd>
                      </div>
                    </dl>
                  </>
                )}

                {slot.history.length > 1 ? (
                  <details className="image-history image-role-card__history">
                    <summary>
                      Version history ({slot.history.length})
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
                            Open private original
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
                    {slot.current === null ? "Add this role" : "Replace safely"}
                  </button>
                ) : (
                  <p className="image-role-card__lock">
                    {imageMutationLockMessage(
                      project.status,
                      slot.role,
                      mutation.operation,
                    )}
                  </p>
                )}
                </article>
              );
            })}
          </div>

          {!canManageImages ? (
            <aside className="image-assets__locked" role="note">
              <p className="eyebrow">Reviewer access</p>
              <h3>Image uploads and replacements are owner-only</h3>
              <p>
                Private originals, immutable history, readiness checks, and human
                review remain available to you.
              </p>
            </aside>
          ) : !uploadAllowed ? (
            <aside className="image-assets__locked" role="note">
              <p className="eyebrow">Workflow-controlled</p>
              <h3>
                {roleLabels[selectedRole]} {selectedMutation?.operation ?? "change"} is
                locked in {project.status}
              </h3>
              <p>
                {imageMutationLockMessage(
                  project.status,
                  selectedRole,
                  selectedMutation?.operation ?? "first upload",
                )}
              </p>
              <p>Existing private assets and immutable history remain readable.</p>
            </aside>
          ) : (
            <form
              aria-labelledby="role-upload-heading"
              className="image-upload image-set-upload"
              noValidate
              onSubmit={submitUpload}
            >
              <div>
                <p className="eyebrow">
                  {selectedSlot?.current === null
                    ? "Fill role"
                    : "Controlled replacement"}
                </p>
                <h3 id="role-upload-heading">
                  {selectedSlot?.current === null
                    ? `Add ${roleLabels[selectedRole]}`
                    : `Replace ${roleLabels[selectedRole]}`}
                </h3>
                <p>
                  A successful replacement creates a new immutable version. Every old
                  row, file, and rights declaration remains retained.
                </p>
              </div>

              <div className="image-upload__grid">
                <div className="image-upload__field">
                  <label htmlFor="role-image-file">Image file</label>
                  <input
                    accept=".jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp"
                    disabled={uploading}
                    id="role-image-file"
                    name="role-image-file"
                    onChange={updateFile}
                    type="file"
                  />
                  <p>
                    Static JPEG, PNG, or WebP · shortest side at least 768 px ·
                    longest side at most 8192 px · 40,000,000 pixels and 20 MiB max.
                  </p>
                </div>

                <div className="image-upload__field">
                  <label htmlFor="image-source-type">Image source</label>
                  <select
                    disabled={uploading}
                    id="image-source-type"
                    onChange={updateSource}
                    value={sourceType}
                  >
                    {imageSourceTypes.map((source) => (
                      <option key={source} value={source}>
                        {sourceLabels[source]}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <fieldset className="image-upload__choices" disabled={uploading}>
                <legend>Intended use</legend>
                {imageIntendedUsages.map((usage) => (
                  <label key={usage}>
                    <input
                      checked={intendedUsage.includes(usage)}
                      onChange={() => toggleUsage(usage)}
                      type="checkbox"
                    />
                    <span>{usageLabels[usage]}</span>
                  </label>
                ))}
              </fieldset>

              <label className="image-upload__attestation">
                <input
                  checked={rightsConfirmed}
                  disabled={uploading}
                  onChange={(event) => {
                    clearUploadAttempt();
                    setRightsConfirmed(event.target.checked);
                  }}
                  type="checkbox"
                />
                <span>
                  I confirm that the source above is accurate, that I have the rights
                  or permission needed for the selected uses, and that this
                  declaration will be bound to this immutable image version.
                </span>
              </label>

              {uploadFormError === null ? null : (
                <p className="image-upload__error" role="alert">
                  {uploadFormError}
                </p>
              )}
              {uploadError === null ? null : (
                <div className="image-upload__error" role="alert">
                  <p>{commandErrorMessage(uploadError)}</p>
                  {uploadError.retryable ? (
                    <p>
                      Do not change the selected file, role, or declaration before
                      retrying.
                    </p>
                  ) : null}
                </div>
              )}
              {uploadSucceeded ? (
                <p className="image-upload__success" role="status">
                  The immutable role version was stored. Refreshing the image set…
                </p>
              ) : null}
              {uploading ? (
                <div aria-busy="true" className="image-upload__progress">
                  <progress aria-label="Uploading and checking role image" />
                  <p role="status">Uploading and checking the private image…</p>
                </div>
              ) : null}

              <div className="image-upload__actions">
                <button
                  className="button button--primary"
                  disabled={uploading}
                  type="submit"
                >
                  {uploading
                    ? "Storing protected upload…"
                    : selectedSlot?.current === null
                      ? `Store ${roleLabels[selectedRole]}`
                      : `Store ${roleLabels[selectedRole]} replacement`}
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
                <p className="eyebrow">Deterministic, non-AI prerequisites</p>
                <h3 id="readiness-checklist-heading">Readiness checklist</h3>
              </div>
            </div>
            <ul className="readiness-checklist">
              {(
                Object.keys(checklistLabels) as Array<
                  keyof typeof checklistLabels
                >
              ).map((key) => {
                const passed = imageSet.checklist[key];
                return (
                  <li className={passed ? "is-pass" : "is-blocked"} key={key}>
                    <span aria-hidden="true">{passed ? "✓" : "!"}</span>
                    <span>{checklistLabels[key]}</span>
                  </li>
                );
              })}
            </ul>
            {imageSet.checklist.required_roles_present &&
            !imageSet.checklist.content_distinct ? (
              <p className="readiness-warning" role="alert">
                Duplicate content detected across required roles. READY is blocked
                until the current required images use distinct SHA-256 content.
              </p>
            ) : null}
          </section>

          <section
            aria-labelledby="readiness-review-heading"
            className="readiness-panel readiness-review"
          >
            <div className="section-heading">
              <div>
                <p className="eyebrow">Human decision · append-only</p>
                <h3 id="readiness-review-heading">Readiness review</h3>
              </div>
            </div>

            {imageSet.latest_review === null ? (
              <p>No human readiness review has been saved for this project.</p>
            ) : (
              <article className="latest-review">
                <p className="eyebrow">
                  Latest review · version {imageSet.latest_review.version}
                </p>
                <h4>
                  {imageSet.latest_review.verdict === "ready"
                    ? "READY"
                    : "NOT READY"}
                </h4>
                <p>
                  {imageSet.latest_review.reason ??
                    "All deterministic prerequisites were accepted at confirmation."}
                </p>
                <p>
                  By {imageSet.latest_review.actor_display_name_snapshot} ·{" "}
                  {formatProjectTimestamp(imageSet.latest_review.created_at)}
                </p>
              </article>
            )}

            <form className="readiness-form" noValidate onSubmit={submitReview}>
              <fieldset disabled={reviewing}>
                <legend>Human verdict</legend>
                <label>
                  <input
                    checked={verdict === "ready"}
                    name="readiness-verdict"
                    onChange={() => {
                      clearReviewAttempt();
                      setVerdict("ready");
                    }}
                    type="radio"
                  />
                  <span>READY</span>
                </label>
                <label>
                  <input
                    checked={verdict === "not_ready"}
                    name="readiness-verdict"
                    onChange={() => {
                      clearReviewAttempt();
                      setVerdict("not_ready");
                    }}
                    type="radio"
                  />
                  <span>NOT READY</span>
                </label>
              </fieldset>

              <div className="image-upload__field">
                <label htmlFor="readiness-reason">
                  Reason {verdict === "not_ready" ? "(required)" : "(optional)"}
                </label>
                <textarea
                  disabled={reviewing}
                  id="readiness-reason"
                  maxLength={1000}
                  onChange={(event) => {
                    clearReviewAttempt();
                    setReason(event.target.value);
                  }}
                  rows={4}
                  value={reason}
                />
              </div>

              {reviewFormError === null ? null : (
                <p className="image-upload__error" role="alert">
                  {reviewFormError}
                </p>
              )}
              {reviewError === null ? null : (
                <div className="image-upload__error" role="alert">
                  <p>{commandErrorMessage(reviewError)}</p>
                  {reviewError.retryable ? (
                    <p>
                      Do not change the verdict or reason before retrying this command.
                    </p>
                  ) : null}
                </div>
              )}
              {reviewSucceeded ? (
                <p className="image-upload__success" role="status">
                  The immutable human review was saved. Refreshing readiness…
                </p>
              ) : null}

              <button
                className="button button--primary"
                disabled={
                  reviewing ||
                  (verdict === "ready" &&
                    !imageSet.checklist.can_mark_ready)
                }
                type="submit"
              >
                {reviewing
                  ? "Saving protected review…"
                  : verdict === "ready"
                    ? "Confirm READY"
                    : "Record NOT READY"}
              </button>
            </form>

            {state.status === "loaded" && state.reviews.length > 0 ? (
              <details className="review-history">
                <summary>Review history ({state.reviews.length})</summary>
                <ol>
                  {state.reviews.map((review) => (
                    <li key={review.id}>
                      <strong>
                        v{review.version} ·{" "}
                        {review.verdict === "ready" ? "READY" : "NOT READY"}
                      </strong>
                      <span>
                        {review.reason ?? "No reason supplied"} ·{" "}
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
