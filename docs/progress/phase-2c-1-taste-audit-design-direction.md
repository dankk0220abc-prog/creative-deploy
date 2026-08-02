# Phase 2C — Taste and Impeccable Audit and Design Direction

Date: 2026-08-02

## Execution Authority

`FRONTEND_SKILLS_LOADED`

Actual frontend Skills loaded for this refinement:

- `redesign-existing-projects` — audit-first assessment and constrained incremental refinement.
- `gpt-taste` — typography, interaction, anti-slop, and responsive hierarchy cross-check.
- `impeccable` v4.0.4 — scoped audit/detect and component-state craft-floor verification.

`design-taste-frontend` was deliberately not loaded. This is an authenticated, multi-step
product workbench rather than a brand-display page, so its landing-page-oriented rules were
not applicable.

## Existing Candidate Provenance

The Phase 2C-1 Candidate already present at entry was created without the named Taste Skills.
Its own prior plan, audit, and Candidate documents recorded that limitation. This continuation
preserves that Candidate and evaluates it in place; it does not reset, clean, checkout, or
rebuild it from scratch.

## Audit Findings

- **CreativeDeploy / PaintPilot identity:** the charcoal, warm-paper, oxidized-copper, and
  mineral-teal system was already coherent, but the platform frame could still read as a
  generic engineering shell when task state was not visually first.
- **Login and Projects:** the truthful access boundary, empty state, and create path existed.
  The Projects list needed a calmer, metadata-first card composition and a tablet-safe limit
  on decorative visual mass so project state and next view lead.
- **Project detail:** the earlier Candidate correctly exposed image readiness, reviewer access,
  Region work, history, and review, but oversized display type and an enclosed command strip
  made persisted facts compete with the current workflow sequence.
- **Owner/reviewer management:** it must remain a governed capability, not a marketing
  collaboration panel. The useful hierarchy is current members, explicit grant/revoke action,
  and the reviewer’s read-and-review boundary.
- **Upload, error, retry, and readiness:** the real validation/retry, immutable versions, and
  human readiness decision were already product facts. Their visual grouping needs to foreground
  the current role, accepted checks, and the next permitted human action.
- **Region/Polygon:** the image canvas, inspector, tools, immutable snapshots, and exact review
  are the work surface. It must stay image-forward and must not inherit Hero, Bento, carousel,
  or scroll-spectacle conventions.
- **Responsive and state coverage:** 390 px needs an explicit precision-editing limit without
  hiding persisted facts; 768 px needs a task-sized project card; 1440 px needs compact
  hierarchy without empty decorative columns. Empty, loading, failure, no-access, and completed
  states must remain truthful rather than be cosmetically normalized.
- **Anti-slop result:** no new gradients, ornamental particles, repetitive bento cards,
  testimonial/carousel patterns, or gratuitous animation were added. The audit found one real
  cascade placement issue during the first browser pass; it was corrected before final evidence
  was captured.
- **Impeccable detector:** the single scoped run over `apps/web/src` found two concrete visual
  inconsistencies: gray-on-teal Health hover contrast and an ornamental 3 px Login proof border.
  Both were corrected. The detector was not rerun, per its once-per-session contract.
- **Component/state consistency:** Button, Input, Select, Tabs, Badge, Card, Dialog, feedback,
  validation, disabled/loading/error, and focus-visible treatments now share the same restrained
  material language. Reviewer, upload/readiness, Region review, and health operations expose
  busy/help/error relationships without altering product behavior.

## Adopted Direction

- Retain the existing restrained material palette and improve task order: current state, next
  permitted action, then supporting facts.
- Use the locally available editorial display fallback stack before generic system fallbacks;
  do not download fonts, add packages, or create an external runtime dependency.
- Reduce navigation padding, cap the Projects grid at a workbench-appropriate two-column scale,
  and give tablet cards a material / facts split rather than a template-like card stack.
- Make project-detail headings, status, sequence, and command strip compact enough that a
  real task starts in the first working viewport.
- Keep the Region canvas visually primary. On small screens, communicate the precision limit
  and retain Pan, Fit, saved data, and history rather than simulate desktop precision.

## Taste Suggestions Deliberately Rejected

| Suggestion | Decision | Product reason |
| --- | --- | --- |
| Hero/AIDA conversion sequence | Rejected | A governed login, image workflow, reviewer boundary, and Polygon workspace are task flows, not a conversion landing page. |
| Bento/card-heavy composition | Rejected | Image roles, reviewer membership, and history have different operational densities; repeated marketing tiles would hide task order. |
| Testimonial carousel / inline editorial imagery | Rejected | No corresponding product facts exist, and private project imagery must not be repurposed as decoration. |
| Scroll pinning, scrubbing text reveals, or GSAP spectacle | Rejected | They would interfere with long forms, immutable history, keyboard access, and precise canvas work. |
| New gradients, generated visual assets, or external font loading | Rejected | The existing material direction is sufficient; extra decoration or network dependencies would not improve governed work. |

## Guardrails Preserved

No API, OIDC/session, owner/reviewer permission, Workflow State Machine, database, migration,
private storage, TLS, backup/restore, AI, OCR, Agent, or RAG behavior was changed. The only
incremental product source refinement in this continuation is Web presentation: the full
`en-US` / `zh-CN` resource layer, language preference and switcher, localized display mappings,
locale-aware dates/numbers, accessible labels/titles, component-state consistency, and CSS
hierarchy/responsive composition.

## Bilingual Product Direction

- Keep English as the safe fallback and provide complete Simplified Chinese coverage for the
  authenticated product, pre-login state, failures, retries, empty/loading states, image
  readiness, reviewer access, Region/Polygon work, and immutable history.
- Resolve locale as saved preference, browser language, configured default, then `en-US`.
  Switching language must not navigate, log out, or reset form/Polygon state.
- Translate product-owned display copy and API-enum labels only. Never translate project titles,
  user-entered descriptions, person names, filenames, UUIDs, hashes, object keys, logs, or raw
  request/response values.
- Synchronize visible copy, `document.title`, `<html lang>`, status semantics, and ARIA labels.
  Unknown keys use a localized safe fallback rather than exposing implementation keys.
- Use `Intl.DateTimeFormat`, `Intl.RelativeTimeFormat`, and i18next's Intl number formatter.
  Chinese layout uses the existing material direction with language-specific line-height and
  overflow safeguards; it does not introduce a second visual system.
