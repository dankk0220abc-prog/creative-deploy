import type { ReactNode } from "react";

interface FeedbackPanelProps {
  action?: {
    label: string;
    onClick: () => void;
  };
  children?: ReactNode;
  eyebrow: string;
  heading: string;
  headingLevel?: 1 | 2;
  kind: "empty" | "error" | "info";
}

export function FeedbackPanel({
  action,
  children,
  eyebrow,
  heading,
  headingLevel = 2,
  kind,
}: FeedbackPanelProps) {
  const Heading = headingLevel === 1 ? "h1" : "h2";

  return (
    <section
      aria-live={kind === "error" ? "assertive" : "polite"}
      className={`feedback-panel feedback-panel--${kind}`}
    >
      <div className="feedback-panel__signal" aria-hidden="true">
        <span />
        <span />
        <span />
      </div>
      <div className="feedback-panel__content">
        <p className="eyebrow">{eyebrow}</p>
        <Heading>{heading}</Heading>
        {children === undefined ? null : (
          <div className="feedback-panel__copy">{children}</div>
        )}
        {action === undefined ? null : (
          <button className="button button--secondary" onClick={action.onClick} type="button">
            {action.label}
          </button>
        )}
      </div>
    </section>
  );
}
