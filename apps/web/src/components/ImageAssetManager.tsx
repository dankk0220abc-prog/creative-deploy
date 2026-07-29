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
  imageIntendedUsages,
  ImageAssetApiError,
  imageSourceTypes,
  listImageAssets,
  type ImageAsset,
  type ImageIntendedUsage,
  type ImageSourceType,
  uploadImageAsset,
} from "../api/imageAssets";
import type { PaintProject } from "../api/paintProjects";
import { formatProjectTimestamp } from "../utils/format";
import { FeedbackPanel } from "./FeedbackPanel";

const MAX_IMAGE_BYTES = 20 * 1024 * 1024;
const acceptedImageTypes = new Set(["image/jpeg", "image/png", "image/webp"]);
const replacementStates = new Set([
  "IMAGE_REVIEW_REQUIRED",
  "IMAGE_VALIDATION_FAILED",
]);

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

interface ImageAssetManagerProps {
  onProjectChanged: () => void;
  project: PaintProject;
}

interface UploadAttempt {
  fingerprint: string;
  idempotencyKey: string;
}

type ImageListState =
  | { status: "error"; error: ImageAssetApiError }
  | { status: "loaded"; images: ImageAsset[] }
  | { status: "loading" };

function asImageApiError(error: unknown): ImageAssetApiError {
  if (error instanceof ImageAssetApiError) {
    return error;
  }
  return new ImageAssetApiError(
    "internal",
    "The image request could not be completed safely.",
  );
}

function uploadFingerprint(
  file: File,
  sourceType: ImageSourceType,
  intendedUsage: ImageIntendedUsage[],
): string {
  return [
    file.name,
    file.size,
    file.lastModified,
    file.type,
    sourceType,
    [...intendedUsage].sort().join(","),
  ].join("\u001f");
}

function uploadErrorMessage(error: ImageAssetApiError): string {
  if (error.kind === "network") {
    return "The API connection was interrupted. Retry keeps the same protected upload attempt.";
  }
  if (error.kind === "storage") {
    return "Private image storage is temporarily unavailable. Retry keeps the same protected upload attempt.";
  }
  if (error.kind === "conflict") {
    return "The upload conflicts with the saved command or the current workflow state. Refresh the project before trying again.";
  }
  if (error.kind === "validation") {
    return "The file or rights declaration was rejected. Choose a supported image and review the declaration.";
  }
  if (error.kind === "not_found") {
    return "The project is no longer available to the current operator.";
  }
  return "The image service returned an incomplete or unexpected response.";
}

function imageHistoryLabel(image: ImageAsset): string {
  return image.is_current
    ? `Current primary image, version ${image.version}`
    : `Retained primary image, version ${image.version}`;
}

export function ImageAssetManager({
  onProjectChanged,
  project,
}: ImageAssetManagerProps) {
  const [listState, setListState] = useState<ImageListState>({ status: "loading" });
  const [listReloadToken, setListReloadToken] = useState(0);
  const [file, setFile] = useState<File | null>(null);
  const [sourceType, setSourceType] =
    useState<ImageSourceType>("user_provided");
  const [intendedUsage, setIntendedUsage] = useState<ImageIntendedUsage[]>([
    "private_project",
  ]);
  const [rightsConfirmed, setRightsConfirmed] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [uploadError, setUploadError] = useState<ImageAssetApiError | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadSucceeded, setUploadSucceeded] = useState(false);
  const attemptRef = useRef<UploadAttempt | null>(null);
  const inFlightRef = useRef(false);

  useEffect(() => {
    const controller = new AbortController();
    void listImageAssets(project.id, controller.signal)
      .then(({ items }) => {
        if (!controller.signal.aborted) {
          setListState({ status: "loaded", images: items });
        }
      })
      .catch((error: unknown) => {
        const apiError = asImageApiError(error);
        if (!controller.signal.aborted && apiError.kind !== "aborted") {
          setListState({ status: "error", error: apiError });
        }
      });
    return () => controller.abort();
  }, [listReloadToken, project.id]);

  const images = useMemo(
    () => (listState.status === "loaded" ? listState.images : []),
    [listState],
  );
  const currentImage = images.find((image) => image.is_current) ?? null;
  const hasCurrentImage =
    currentImage !== null || project.current_image_asset_id !== null;
  const mayUploadFirst = project.status === "DRAFT" && !hasCurrentImage;
  const mayReplace =
    hasCurrentImage && replacementStates.has(project.status);
  const uploadAllowed = mayUploadFirst || mayReplace;

  const sortedHistory = useMemo(
    () => [...images].sort((left, right) => right.version - left.version),
    [images],
  );

  const clearAttempt = useCallback(() => {
    attemptRef.current = null;
    setUploadError(null);
    setUploadSucceeded(false);
  }, []);

  function updateFile(event: ChangeEvent<HTMLInputElement>) {
    clearAttempt();
    setFormError(null);
    setFile(event.target.files?.item(0) ?? null);
  }

  function updateSource(event: ChangeEvent<HTMLSelectElement>) {
    clearAttempt();
    setSourceType(event.target.value as ImageSourceType);
  }

  function toggleUsage(usage: ImageIntendedUsage) {
    clearAttempt();
    setIntendedUsage((current) =>
      current.includes(usage)
        ? current.filter((item) => item !== usage)
        : [...current, usage],
    );
  }

  async function submitUpload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (inFlightRef.current || !uploadAllowed) {
      return;
    }
    setFormError(null);
    setUploadSucceeded(false);

    if (file === null) {
      setFormError("Choose one JPEG, PNG, or WebP image.");
      return;
    }
    if (!acceptedImageTypes.has(file.type)) {
      setFormError("Choose a JPEG, PNG, or WebP image.");
      return;
    }
    if (file.size < 1 || file.size > MAX_IMAGE_BYTES) {
      setFormError("The image must be larger than 0 bytes and no more than 20 MiB.");
      return;
    }
    if (intendedUsage.length === 0) {
      setFormError("Choose at least one intended use.");
      return;
    }
    if (!rightsConfirmed) {
      setFormError("Confirm the source, rights, and intended-use declaration.");
      return;
    }

    const fingerprint = uploadFingerprint(file, sourceType, intendedUsage);
    if (
      attemptRef.current === null ||
      attemptRef.current.fingerprint !== fingerprint
    ) {
      attemptRef.current = {
        fingerprint,
        idempotencyKey: createImageIdempotencyKey(),
      };
    }

    const attempt = attemptRef.current;
    inFlightRef.current = true;
    setUploading(true);
    setUploadError(null);
    try {
      await uploadImageAsset(
        project.id,
        {
          file,
          intendedUsage,
          role: "primary_mvp_input",
          sourceType,
        },
        attempt.idempotencyKey,
      );
      attemptRef.current = null;
      setFile(null);
      setRightsConfirmed(false);
      setUploadSucceeded(true);
      setListState({ status: "loading" });
      setListReloadToken((current) => current + 1);
      onProjectChanged();
    } catch (error: unknown) {
      const apiError = asImageApiError(error);
      if (!apiError.retryable) {
        attemptRef.current = null;
      }
      setUploadError(apiError);
    } finally {
      inFlightRef.current = false;
      setUploading(false);
    }
  }

  return (
    <section
      aria-labelledby="image-asset-heading"
      className="image-assets"
      data-project-status={project.status}
    >
      <div className="section-heading image-assets__heading">
        <div>
          <p className="eyebrow">Phase 1E-1 · Private immutable asset</p>
          <h2 id="image-asset-heading">Primary planning image</h2>
        </div>
        <span className="image-assets__slot">1 formal slot</span>
      </div>

      <p className="image-assets__boundary">
        PaintPilot stores one original primary image for planning. Upload checks are
        deterministic file-safety checks only; no AI analysis, quality approval, color
        matching, or legal verification occurs here.
      </p>

      {listState.status === "loading" ? (
        <div aria-busy="true" className="image-assets__loading">
          <progress aria-label="Loading private image history" />
          <p role="status">Loading private image history…</p>
        </div>
      ) : null}

      {listState.status === "error" ? (
        <FeedbackPanel
          action={{
            label: "Retry image history",
            onClick: () => {
              setListState({ status: "loading" });
              setListReloadToken((current) => current + 1);
            },
          }}
          eyebrow="Private image history unavailable"
          heading="The image records could not be loaded"
          kind="error"
        >
          <p>
            No image facts were inferred. Retry the owner-scoped API request when the
            service is available.
          </p>
        </FeedbackPanel>
      ) : null}

      {listState.status === "loaded" && currentImage === null ? (
        <div className="image-assets__empty">
          <p className="eyebrow">Primary slot empty</p>
          <h3>No image has been stored</h3>
          <p>
            Add one supported original image and record your source and intended-use
            declaration.
          </p>
        </div>
      ) : null}

      {currentImage === null ? null : (
        <article
          aria-label={imageHistoryLabel(currentImage)}
          className="image-card image-card--current"
        >
          <div className="image-card__preview">
            <img
              alt={`Private preview of ${currentImage.original_filename}`}
              src={currentImage.content_url}
            />
          </div>
          <div className="image-card__body">
            <p className="eyebrow">Current · version {currentImage.version}</p>
            <h3>{currentImage.original_filename}</h3>
            <dl className="image-card__facts">
              <div>
                <dt>Dimensions</dt>
                <dd>
                  {currentImage.width} × {currentImage.height} px
                </dd>
              </div>
              <div>
                <dt>Stored size</dt>
                <dd>{(currentImage.byte_size / 1024 / 1024).toFixed(2)} MiB</dd>
              </div>
              <div>
                <dt>Format</dt>
                <dd>{currentImage.detected_format.toUpperCase()}</dd>
              </div>
              <div>
                <dt>Upload checks</dt>
                <dd>Accepted</dd>
              </div>
              <div>
                <dt>Rights record</dt>
                <dd>User attestation confirmed</dd>
              </div>
              <div>
                <dt>Stored</dt>
                <dd>{formatProjectTimestamp(currentImage.created_at)}</dd>
              </div>
            </dl>
          </div>
        </article>
      )}

      {sortedHistory.length <= 1 ? null : (
        <details className="image-history">
          <summary>Retained image history ({sortedHistory.length - 1})</summary>
          <ol>
            {sortedHistory
              .filter((image) => !image.is_current)
              .map((image) => (
                <li key={image.id}>
                  <article
                    aria-label={imageHistoryLabel(image)}
                    className="image-history__item"
                  >
                    <div>
                      <strong>
                        Version {image.version} · {image.original_filename}
                      </strong>
                      <span>
                        {image.width} × {image.height} px ·{" "}
                        {formatProjectTimestamp(image.created_at)}
                      </span>
                    </div>
                    <a href={image.content_url} rel="noreferrer" target="_blank">
                      Open private original
                    </a>
                  </article>
                </li>
              ))}
          </ol>
        </details>
      )}

      {!uploadAllowed ? (
        <aside className="image-assets__locked" role="note">
          <p className="eyebrow">Workflow-controlled</p>
          <h3>Image upload is not available in {project.status}</h3>
          <p>
            A first image is accepted only from DRAFT. Replacement is accepted only
            after image review is required or image validation has failed. Existing
            originals remain retained.
          </p>
        </aside>
      ) : (
        <form className="image-upload" noValidate onSubmit={submitUpload}>
          <div>
            <p className="eyebrow">
              {mayReplace ? "Controlled replacement" : "Fill primary slot"}
            </p>
            <h3>
              {mayReplace ? "Upload a replacement original" : "Upload the original"}
            </h3>
            <p>
              {mayReplace
                ? "A successful replacement becomes current. The previous original remains in immutable history."
                : "A successful upload becomes the current primary planning image."}
            </p>
          </div>

          <div className="image-upload__grid">
            <div className="image-upload__field">
              <label htmlFor="primary-image-file">Image file</label>
              <input
                accept=".jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp"
                disabled={uploading}
                id="primary-image-file"
                name="primary-image-file"
                onChange={updateFile}
                type="file"
              />
              <p>JPEG, PNG, or non-animated WebP · 768–8192 px per side · 20 MiB max.</p>
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
                clearAttempt();
                setRightsConfirmed(event.target.checked);
              }}
              type="checkbox"
            />
            <span>
              I confirm that the source above is accurate, that I have the rights or
              permission needed for the selected uses, and that this declaration will
              be bound to this immutable image version.
            </span>
          </label>

          {formError === null ? null : (
            <p className="image-upload__error" role="alert">
              {formError}
            </p>
          )}
          {uploadError === null ? null : (
            <div className="image-upload__error" role="alert">
              <p>{uploadErrorMessage(uploadError)}</p>
              {uploadError.retryable ? (
                <p>Do not change the selected file or declaration before retrying.</p>
              ) : null}
            </div>
          )}
          {uploadSucceeded ? (
            <p className="image-upload__success" role="status">
              The immutable image was stored. Refreshing project and image history…
            </p>
          ) : null}
          {uploading ? (
            <div aria-busy="true" className="image-upload__progress">
              <progress aria-label="Uploading and checking image" />
              <p role="status">Uploading and checking the original image…</p>
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
                : mayReplace
                  ? "Store replacement"
                  : "Store primary image"}
            </button>
          </div>
        </form>
      )}
    </section>
  );
}
