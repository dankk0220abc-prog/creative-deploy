import { useEffect, useRef } from "react";
import { useAppTranslation } from "../i18n";

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
  const { t } = useAppTranslation();
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
        <p className="context-label">{t("unsaved.eyebrow")}</p>
        <h2 id="unsaved-dialog-title">{t("unsaved.heading")}</h2>
        <p id="unsaved-dialog-description">{t("unsaved.copy")}</p>
        <div className="confirmation-dialog__actions">
          <button
            className="button button--primary"
            onClick={onContinueEditing}
            ref={continueButtonRef}
            type="button"
          >
            {t("unsaved.continue")}
          </button>
          <button
            className="button button--danger"
            onClick={onDiscard}
            ref={discardButtonRef}
            type="button"
          >
            {t("unsaved.discard")}
          </button>
        </div>
      </section>
    </div>
  );
}
