import { useEffect, useRef } from "react";

interface UnsavedChangesDialogProps {
  onContinueEditing: () => void;
  onDiscard: () => void;
  open: boolean;
}

export function UnsavedChangesDialog({
  onContinueEditing,
  onDiscard,
  open,
}: UnsavedChangesDialogProps) {
  const continueButtonRef = useRef<HTMLButtonElement>(null);
  const discardButtonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (open) {
      continueButtonRef.current?.focus();
    }
  }, [open]);

  if (!open) {
    return null;
  }

  return (
    <div
      className="dialog-backdrop"
      onKeyDown={(event) => {
        if (event.key === "Escape") {
          event.preventDefault();
          onContinueEditing();
          return;
        }

        if (event.key === "Tab") {
          if (event.shiftKey && document.activeElement === continueButtonRef.current) {
            event.preventDefault();
            discardButtonRef.current?.focus();
          } else if (
            !event.shiftKey &&
            document.activeElement === discardButtonRef.current
          ) {
            event.preventDefault();
            continueButtonRef.current?.focus();
          }
        }
      }}
    >
      <section
        aria-describedby="unsaved-dialog-description"
        aria-labelledby="unsaved-dialog-title"
        aria-modal="true"
        className="confirmation-dialog"
        role="alertdialog"
      >
        <p className="eyebrow">Unsaved project</p>
        <h2 id="unsaved-dialog-title">Discard unsaved changes?</h2>
        <p id="unsaved-dialog-description">
          Your project has not been created. The current form values will be lost.
        </p>
        <div className="confirmation-dialog__actions">
          <button
            className="button button--primary"
            onClick={onContinueEditing}
            ref={continueButtonRef}
            type="button"
          >
            Continue editing
          </button>
          <button
            className="button button--danger"
            onClick={onDiscard}
            ref={discardButtonRef}
            type="button"
          >
            Discard changes
          </button>
        </div>
      </section>
    </div>
  );
}
