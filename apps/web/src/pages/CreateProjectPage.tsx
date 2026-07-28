import {
  type FormEvent,
  useEffect,
  useRef,
  useState,
} from "react";
import { useNavigate } from "react-router";

import {
  createIdempotencyKey,
  createPaintProject,
  normalizeCreatePaintProjectInput,
  PaintProjectApiError,
  type CreatePaintProjectInput,
} from "../api/paintProjects";
import { UnsavedChangesDialog } from "../components/UnsavedChangesDialog";
import { codePointLength } from "../utils/format";

type FieldName = "description" | "title";
type FieldErrors = Partial<Record<FieldName, string>>;

interface LogicalCreateAttempt {
  idempotencyKey: string;
  payload: CreatePaintProjectInput;
}

type SubmissionState =
  | { status: "error"; error: PaintProjectApiError }
  | { status: "idle" }
  | { status: "submitting" };

function validateFields(title: string, description: string): FieldErrors {
  const errors: FieldErrors = {};
  const normalizedTitle = title.trim();
  const normalizedDescription = description.trim();

  if (codePointLength(normalizedTitle) === 0) {
    errors.title = "Enter a project title.";
  } else if (codePointLength(normalizedTitle) > 80) {
    errors.title = "Project title must contain 80 characters or fewer.";
  }

  if (codePointLength(normalizedDescription) > 500) {
    errors.description = "Description must contain 500 characters or fewer.";
  }
  return errors;
}

function submissionHeading(error: PaintProjectApiError): string {
  switch (error.kind) {
    case "conflict":
      return "This protected attempt conflicts with earlier details";
    case "internal":
    case "server":
      return "The project could not be created";
    case "invalid_response":
      return "We could not confirm the create result";
    case "network":
      return "We could not confirm whether the project was created";
    case "unavailable":
      return "Project creation is temporarily unavailable";
    case "validation":
      return "The service needs corrected project details";
    default:
      return "The project could not be created";
  }
}

function submissionCopy(error: PaintProjectApiError): string {
  switch (error.kind) {
    case "conflict":
      return "The request identifier was already used with different data. Start a new protected attempt; no local project has been invented.";
    case "internal":
    case "server":
      return "The service returned a safe non-retryable error. Your values are still here, and no success is being claimed.";
    case "invalid_response":
      return "The service response was empty, damaged, or not valid JSON. Retry safely with the same protected attempt.";
    case "network":
      return "The API connection ended without a confirmed result. Retry safely with the same project details and protected attempt.";
    case "unavailable":
      return "PostgreSQL or the project service is temporarily unavailable. Retry safely without changing the project details.";
    case "validation":
      return "Review the highlighted fields. The server remains the final validation authority.";
    default:
      return "Your values are still here. Review them before trying again.";
  }
}

function asApiError(error: unknown): PaintProjectApiError {
  if (error instanceof PaintProjectApiError) {
    return error;
  }
  return new PaintProjectApiError(
    "internal",
    "The create request could not be completed.",
  );
}

export function CreateProjectPage() {
  const navigate = useNavigate();
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [submission, setSubmission] = useState<SubmissionState>({ status: "idle" });
  const [dialogOpen, setDialogOpen] = useState(false);
  const [pendingDestination, setPendingDestination] = useState<string | null>(null);
  const [errorFocusToken, setErrorFocusToken] = useState(0);
  const attemptRef = useRef<LogicalCreateAttempt | null>(null);
  const requestControllerRef = useRef<AbortController | null>(null);
  const inFlightRef = useRef(false);
  const mountedRef = useRef(true);
  const allowNavigationRef = useRef(false);
  const dialogTriggerRef = useRef<HTMLElement | null>(null);
  const errorSummaryRef = useRef<HTMLDivElement>(null);
  const titleInputRef = useRef<HTMLInputElement>(null);
  const cancelButtonRef = useRef<HTMLButtonElement>(null);

  const dirty = title.length > 0 || description.length > 0;
  const isSubmitting = submission.status === "submitting";
  const hasErrorSummary =
    Object.keys(fieldErrors).length > 0 || submission.status === "error";

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      requestControllerRef.current?.abort();
    };
  }, []);

  useEffect(() => {
    if (hasErrorSummary) {
      errorSummaryRef.current?.focus();
    }
  }, [errorFocusToken, hasErrorSummary]);

  useEffect(() => {
    if (!dirty || allowNavigationRef.current) {
      return;
    }

    const handleBeforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, [dirty]);

  useEffect(() => {
    if (!dirty || isSubmitting || allowNavigationRef.current) {
      return;
    }

    const handleDocumentClick = (event: MouseEvent) => {
      if (
        event.defaultPrevented ||
        event.button !== 0 ||
        event.metaKey ||
        event.ctrlKey ||
        event.shiftKey ||
        event.altKey
      ) {
        return;
      }

      const target = event.target;
      const anchor = target instanceof Element ? target.closest("a[href]") : null;
      if (!(anchor instanceof HTMLAnchorElement) || anchor.target === "_blank") {
        return;
      }

      const destination = new URL(anchor.href, window.location.href);
      if (
        destination.origin !== window.location.origin ||
        (destination.pathname === window.location.pathname &&
          destination.search === window.location.search)
      ) {
        return;
      }

      event.preventDefault();
      event.stopPropagation();
      dialogTriggerRef.current = anchor;
      setPendingDestination(
        `${destination.pathname}${destination.search}${destination.hash}`,
      );
      setDialogOpen(true);
    };

    document.addEventListener("click", handleDocumentClick, true);
    return () => document.removeEventListener("click", handleDocumentClick, true);
  }, [dirty, isSubmitting]);

  useEffect(() => {
    if (!dirty || isSubmitting || allowNavigationRef.current) {
      return;
    }

    const handlePopState = () => {
      const discard = window.confirm(
        "Discard unsaved changes? Your project has not been created.",
      );
      if (discard) {
        allowNavigationRef.current = true;
      } else {
        window.history.forward();
      }
    };

    window.addEventListener("popstate", handlePopState, { capture: true });
    return () =>
      window.removeEventListener("popstate", handlePopState, { capture: true });
  }, [dirty, isSubmitting]);

  const resetAttemptAfterEdit = () => {
    attemptRef.current = null;
    if (submission.status === "error") {
      setSubmission({ status: "idle" });
    }
  };

  const updateTitle = (value: string) => {
    setTitle(value);
    setFieldErrors((current) => {
      const remaining = { ...current };
      delete remaining.title;
      return remaining;
    });
    resetAttemptAfterEdit();
  };

  const updateDescription = (value: string) => {
    setDescription(value);
    setFieldErrors((current) => {
      const remaining = { ...current };
      delete remaining.description;
      return remaining;
    });
    resetAttemptAfterEdit();
  };

  const submit = async (event?: FormEvent<HTMLFormElement>) => {
    event?.preventDefault();
    if (inFlightRef.current) {
      return;
    }

    const nextErrors = validateFields(title, description);
    if (Object.keys(nextErrors).length > 0) {
      setFieldErrors(nextErrors);
      setSubmission({ status: "idle" });
      setErrorFocusToken((current) => current + 1);
      return;
    }

    const payload = normalizeCreatePaintProjectInput(title, description);
    const attempt =
      attemptRef.current ??
      ({
        idempotencyKey: createIdempotencyKey(),
        payload,
      } satisfies LogicalCreateAttempt);
    attemptRef.current = attempt;

    const controller = new AbortController();
    requestControllerRef.current = controller;
    inFlightRef.current = true;
    setFieldErrors({});
    setSubmission({ status: "submitting" });

    try {
      const project = await createPaintProject(
        attempt.payload,
        attempt.idempotencyKey,
        controller.signal,
      );
      allowNavigationRef.current = true;
      attemptRef.current = null;
      navigate(`/paintpilot/projects/${project.id}`, {
        state: { projectCreated: true },
      });
    } catch (error: unknown) {
      const apiError = asApiError(error);
      if (apiError.kind === "aborted" || !mountedRef.current) {
        return;
      }

      if (
        apiError.kind === "conflict" ||
        apiError.kind === "internal" ||
        apiError.kind === "server"
      ) {
        attemptRef.current = null;
      }

      if (apiError.kind === "validation") {
        const serverFieldErrors: FieldErrors = {};
        for (const fieldName of apiError.fieldNames) {
          serverFieldErrors[fieldName] =
            fieldName === "title"
              ? "Check the project title and try again."
              : "Check the description and try again.";
        }
        setFieldErrors(serverFieldErrors);
      }

      setSubmission({ status: "error", error: apiError });
      setErrorFocusToken((current) => current + 1);
    } finally {
      if (mountedRef.current) {
        inFlightRef.current = false;
        requestControllerRef.current = null;
      }
    }
  };

  const requestCancel = () => {
    if (!dirty) {
      allowNavigationRef.current = true;
      navigate("/paintpilot/projects");
      return;
    }
    dialogTriggerRef.current = cancelButtonRef.current;
    setPendingDestination("/paintpilot/projects");
    setDialogOpen(true);
  };

  const discardAndNavigate = () => {
    allowNavigationRef.current = true;
    setDialogOpen(false);
    navigate(pendingDestination ?? "/paintpilot/projects");
  };

  const safeRetry =
    submission.status === "error" &&
    (submission.error.kind === "invalid_response" ||
      submission.error.kind === "network" ||
      submission.error.kind === "unavailable");

  return (
    <div className="page page--create">
      <section className="create-intro" aria-labelledby="create-page-title">
        <p className="eyebrow">New PaintProject</p>
        <h1 id="create-page-title">Create paint project</h1>
        <p>
          Start with the two facts needed to create a real, database-backed
          planning-only project.
        </p>
        <div className="create-intro__particles" aria-hidden="true">
          <span />
          <span />
          <span />
        </div>
      </section>

      <form
        aria-busy={isSubmitting}
        className="create-form"
        noValidate
        onSubmit={(event) => void submit(event)}
      >
        {hasErrorSummary ? (
          <div
            aria-labelledby="create-error-heading"
            className="error-summary"
            ref={errorSummaryRef}
            role="alert"
            tabIndex={-1}
          >
            <span aria-hidden="true" className="error-summary__icon">
              !
            </span>
            <div>
              <h2 id="create-error-heading">
                {submission.status === "error"
                  ? submissionHeading(submission.error)
                  : `Please correct ${
                      Object.keys(fieldErrors).length
                    } project field${Object.keys(fieldErrors).length === 1 ? "" : "s"}`}
              </h2>
              {submission.status === "error" ? (
                <p>{submissionCopy(submission.error)}</p>
              ) : null}
              {Object.keys(fieldErrors).length > 0 ? (
                <ul>
                  {fieldErrors.title === undefined ? null : (
                    <li>
                      <a href="#project-title">{fieldErrors.title}</a>
                    </li>
                  )}
                  {fieldErrors.description === undefined ? null : (
                    <li>
                      <a href="#project-description">{fieldErrors.description}</a>
                    </li>
                  )}
                </ul>
              ) : null}
            </div>
          </div>
        ) : null}

        <div className="form-field">
          <div className="form-field__label-row">
            <label htmlFor="project-title">
              Project title <span aria-hidden="true">*</span>
            </label>
            <span aria-live="polite" className="character-count">
              {codePointLength(title)} / 80
            </span>
          </div>
          <input
            aria-describedby={`project-title-help${
              fieldErrors.title === undefined ? "" : " project-title-error"
            }`}
            aria-invalid={fieldErrors.title === undefined ? undefined : true}
            autoComplete="off"
            disabled={isSubmitting}
            id="project-title"
            name="title"
            onBlur={() => {
              const nextErrors = validateFields(title, description);
              if (nextErrors.title !== undefined) {
                setFieldErrors((current) => ({
                  ...current,
                  title: nextErrors.title,
                }));
              }
            }}
            onChange={(event) => updateTitle(event.target.value)}
            ref={titleInputRef}
            required
            type="text"
            value={title}
          />
          <p className="form-field__help" id="project-title-help">
            Use a clear name you can recognize later.
          </p>
          {fieldErrors.title === undefined ? null : (
            <p className="form-field__error" id="project-title-error">
              <span aria-hidden="true">!</span> {fieldErrors.title}
            </p>
          )}
        </div>

        <div className="form-field">
          <div className="form-field__label-row">
            <label htmlFor="project-description">Short description</label>
            <span aria-live="polite" className="character-count">
              {codePointLength(description)} / 500
            </span>
          </div>
          <textarea
            aria-describedby={`project-description-help${
              fieldErrors.description === undefined
                ? ""
                : " project-description-error"
            }`}
            aria-invalid={fieldErrors.description === undefined ? undefined : true}
            disabled={isSubmitting}
            id="project-description"
            name="description"
            onBlur={() => {
              const nextErrors = validateFields(title, description);
              if (nextErrors.description !== undefined) {
                setFieldErrors((current) => ({
                  ...current,
                  description: nextErrors.description,
                }));
              }
            }}
            onChange={(event) => updateDescription(event.target.value)}
            rows={5}
            value={description}
          />
          <p className="form-field__help" id="project-description-help">
            Optional context only. No AI prompt or image upload occurs here.
          </p>
          {fieldErrors.description === undefined ? null : (
            <p className="form-field__error" id="project-description-error">
              <span aria-hidden="true">!</span> {fieldErrors.description}
            </p>
          )}
        </div>

        <dl className="fixed-project-facts">
          <div>
            <dt>Target style</dt>
            <dd>
              Cel Shading <span>Current release</span>
            </dd>
          </div>
          <div>
            <dt>Planning-only demo</dt>
            <dd>
              Results are planning guidance and are not verified repaint outcomes.
            </dd>
          </div>
        </dl>

        <div className="form-actions">
          <button
            className="button button--primary button--large"
            disabled={isSubmitting}
            type="submit"
          >
            {isSubmitting
              ? "Creating project…"
              : safeRetry
                ? "Retry safely"
                : submission.status === "error" &&
                    submission.error.kind === "conflict"
                  ? "Start new protected attempt"
                  : "Create project"}
          </button>
          <button
            className="button button--quiet"
            disabled={isSubmitting}
            onClick={requestCancel}
            ref={cancelButtonRef}
            type="button"
          >
            Cancel
          </button>
        </div>

        <p aria-live="polite" className="submission-status" role="status">
          {isSubmitting
            ? "Sending one protected request. Duplicate submission is disabled."
            : safeRetry
              ? "Retry will reuse the same protected request identifier while these values remain unchanged."
              : "A successful create opens a detail page that reads the saved project from the API."}
        </p>
      </form>

      <p className="create-boundary">
        <span aria-hidden="true">◇</span>
        No image upload, analysis, Polygon editing, or paint-plan generation occurs on
        this page.
      </p>

      <UnsavedChangesDialog
        onContinueEditing={() => {
          setDialogOpen(false);
          setPendingDestination(null);
          const focusTarget = dialogTriggerRef.current ?? titleInputRef.current;
          dialogTriggerRef.current = null;
          focusTarget?.focus();
        }}
        onDiscard={discardAndNavigate}
        open={dialogOpen}
      />
    </div>
  );
}
