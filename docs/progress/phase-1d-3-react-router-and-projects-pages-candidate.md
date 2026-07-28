# Phase 1D-3 — React Router and Projects Pages Candidate

## Current Governance Status — 2026-07-29

- Current code baseline / remediation commit:
  `2f99aaf8e1726761c2d89ac444af8380a1cedb79`
- Commit 10:
  `5965a8707a6ccb06d2f58d8655aabac9630e4abd`
- Commit 10 status: `EXISTS_IN_GIT_HISTORY`
- Technical remediation status: `PHASE_1D_3_UX_REMEDIATION_SEALED`
- Governance reconciliation independent review:
  `PHASE_1D_3_GOVERNANCE_RECONCILIATION_PASS_READY_FOR_SEALING`
- Governance seal commit:
  `ac8630ae393cb6ca5bf3a2d1db5070531d6f3f52`
- Phase 1D-3 governance closure: `CLOSED`
- Phase 1D: `IN_PROGRESS`
- Phase 1D-4 — Integrated Product Review: `NOT_STARTED`
- Phase 1E-1: `NOT_STARTED`
- Image-asset phase: `NOT_STARTED`

Evidence boundary: the two commit hashes and their relationship are `GIT_VERIFIED_FACT`; the
no-prior-approval, retrospective-review, focused-review, and independent-review records are
`OWNER_SUPPLIED_EXTERNAL_REVIEW_RECORD`; the governance seal is a `GIT_VERIFIED_FACT`.

Commit 10 entered Git history without a formal prior repository approval record. No prior
repository approval evidence was found. The later review does not backdate approval. A
retrospective independent review later required F-01/F-02 remediation; the remediation was
independently reviewed and sealed in
`2f99aaf8e1726761c2d89ac444af8380a1cedb79`.

The governance reconciliation passed independent review and was sealed by
`ac8630ae393cb6ca5bf3a2d1db5070531d6f3f52`. Its full evidence classification, process-exception
record, sealed candidate, and final closure record are in
`docs/progress/phase-1d-3-governance-reconciliation-candidate.md`. Phase 1D-3 is closed without
backdating Commit 10 approval. Phase 1D-4 is the next formal phase and remains `NOT_STARTED`;
Phase 1E-1 remains `NOT_STARTED`.

## Historical Candidate Snapshot — 2026-07-27 (Preserved)

Everything below this heading is the Phase 1D-3 candidate snapshot that entered Git with Commit
10. Its `NOT_APPROVED` and `NOT_CREATED` statements are preserved as historical evidence of the
process exception. They are not current repository facts and must not be used to claim that Commit
10 is still uncreated.

- Phase 1D-3: `IMPLEMENTED_PENDING_REVIEW`
- Contract Status: governing contract frozen for this candidate
- Phase 1D-3 Approval: `NOT_APPROVED`
- Commit 10: `NOT_CREATED`
- Protected Baseline:
  `6d2c3d8001c3737e2e441ee1c0df4179660f0c57`
- Phase 1D-2 Status: `COMPLETE_AND_COMMITTED`
- Phase 1D-2 Approval: `APPROVED_FOR_COMMIT_9`
- Phase 1D-2 Commit:
  `6d2c3d8001c3737e2e441ee1c0df4179660f0c57`
- Migration Status: `APPROVED_AND_COMMITTED_UNCHANGED`
- Revision ID: `a10d3d8dab38`
- Candidate Date: `2026-07-27`
- MAJOR-01: `REMEDIATED_AWAITING_FINAL_INDEPENDENT_REVIEW`
- MAJOR-02: `REMEDIATED_AWAITING_FINAL_INDEPENDENT_REVIEW`
- MAJOR-03: `REMEDIATED_AWAITING_FINAL_INDEPENDENT_REVIEW`
- Browser evidence: `IMPLEMENTED_AWAITING_FINAL_INDEPENDENT_REVIEW`
- Phase 1D-4: `NOT_STARTED`
- Independent Review Status: `REQUIRED_BEFORE_ANY_COMMIT`

## Documentation Status Contract Remediation

The final independent technical review confirmed that the strict API Schema, route accessibility,
and real-browser keyboard, repeated-Enter, and HTTP 409 UI behavior each passed their technical
verification. Commit 10 authorization was nevertheless held because the prior documentation used
status vocabulary that did not match this governance contract. This documentation-only correction
does not approve Phase 1D-3 or create Commit 10; the final focused independent read-only review
remains required.

## Resolved Phase Scope

The formal repository phase name is **Phase 1D-3 — React Router and Projects Pages**. The
browser vertical slice is acceptance evidence inside this phase, not a separate formal phase.

Authority:

- PaintPilot MVP Product Contract `0.1.3 APPROVED_FOR_IMPLEMENTATION`;
- PaintPilot Domain Data Dictionary `0.1.3 APPROVED_FOR_IMPLEMENTATION`;
- Workflow State Machine `0.1.1 APPROVED_FOR_IMPLEMENTATION`;
- ADR-0001, ADR-0002 and ADR-0003;
- Phase 1C approved UI/UX direction, Create Project UX and Project Workspace wireframes;
- Phase 1D PaintProject Vertical Slice Implementation Plan;
- committed Phase 1D-2 create/list/detail API contract.

No blocking contract ambiguity was found. An early workshop note about preallocating a project ID
was superseded by the approved Product Contract, ADR-0003 and phase plan: the server creates the
project ID and the frontend navigates using the successful 201 response.

This candidate does not modify backend routes, schemas, services, repositories, Principal
behavior, ORM models, Migration history or database constraints.

## Phase 1D-2 Closure

Phase 1D-2 is immutable committed history:

- status: `COMPLETE_AND_COMMITTED`;
- independent review: `APPROVED_FOR_COMMIT_9`;
- commit: `6d2c3d8001c3737e2e441ee1c0df4179660f0c57`;
- subject: `feat(api): add PaintProject persistence and API`;
- F-09-01 through F-09-04: `CLOSED`;
- sole Migration: `a10d3d8dab38`.

That closure covers the configured Demo Principal, AsyncSession, Repository, Service,
idempotent create transaction and owner-scoped create/list/detail APIs. It does not claim
Phase 1D-3 approval, image functionality, real authentication, production deployment or
Integrated Product Review.

## Frontend Architecture

### Routes

React Router `8.3.0` Declarative Mode provides:

| Route | Result |
| --- | --- |
| `/` | replace redirect to `/paintpilot/projects` |
| `/paintpilot` | replace redirect to `/paintpilot/projects` |
| `/paintpilot/projects` | database-backed Projects workspace |
| `/paintpilot/projects/new` | Create PaintProject form |
| `/paintpilot/projects/:projectId` | database-backed read-only detail |
| unmatched route | safe PaintPilot not-found page |

The shared shell contains CreativeDeploy/PaintPilot identity, a skip link, semantic main region,
Projects/Create navigation with active state and the permanent planning-only/Demo limitation.

### API Client

`apps/web/src/api/paintProjects.ts` is independent of React. It:

- uses same-origin `/api/v1/paint-projects` paths and the existing Vite proxy;
- defines the exact nine-field PaintProject response, 16 workflow states and frozen list envelope;
- rejects extra or missing keys at the Project, list-envelope and safe-error-envelope boundaries;
- accepts only plain JSON objects, rejecting arrays, `null`, `Date` instances and other prototypes;
- validates UUIDs, normalized Unicode strings, timezone-aware timestamps, fixed style/mode and
  list pagination at runtime;
- sends only `title` and `description` in create JSON;
- requires exact 201 for create and exact 200 for list/detail;
- parses only a structurally valid error envelope;
- maps 404, 409, 422, 500 and 503 without copying raw server messages;
- treats intermediary 502/504 responses as retryable API-unavailable results;
- fails closed for empty, non-JSON, damaged or schema-invalid responses;
- forwards AbortSignal and distinguishes caller abort from transport failure.

No database URL, Principal header, owner selector, update route, delete route or broad CORS change
was introduced.

### State and Idempotency

List and detail fetch on mount/direct load. AbortController plus request generations prevent late
responses from overwriting a newer route or unmounted component. Pages contain no local project
array, optimistic fake record or localStorage persistence.

Each logical create attempt receives one browser-generated UUID idempotency key. An unchanged
payload reuses that key after an unknown transport outcome, invalid response or retryable 503.
Editing either field clears the attempt, and 409 or non-retryable 500 starts the next activation
with a new key. A synchronous in-flight guard and disabled form controls prevent double-click and
keyboard duplication. The key is never displayed, logged or accepted from user input.

The approved documents define no durable browser key protocol. Therefore the key exists only for
the current mounted Create page. Refreshing the page loses an unconfirmed pending key; this
candidate deliberately does not invent a long-lived localStorage protocol.

## Page Implementation

### Projects

- loading state with an announced database read;
- honest empty state with no sample projects;
- server-envelope pagination without client-side sorting or filtering;
- cards keyed by project ID and rendered in backend order;
- persisted title, optional description, workflow status, style, planning mode and timestamps;
- explicit `No active review gate` because no review-gate entity exists;
- distinct API-unavailable, database-unavailable and unexpected-response states;
- explicit user-activated retry with no automatic request storm.

### Create

- Title and optional Short Description only;
- read-only `Cel Shading · Current release` and planning-only boundary;
- Unicode code-point limits of 80 and 500, client summary and server field mapping;
- value retention across controlled failures;
- exact 201 navigation followed by a new detail GET;
- custom unsaved-change dialog for Cancel/internal links, beforeunload protection and guarded
  browser history;
- focusable error summary, permanent labels, character counts, aria-invalid relationships,
  live submission status and keyboard submit.

There are no style selectors, Rights Attestation, upload, AI prompt, Provider, inventory,
knowledge, Polygon, tenant or member controls.

### Detail and Not Found

- UUID validation before any request;
- direct-route loading and API fetch;
- owner-safe 404 copy that does not distinguish absent from other-owner;
- persisted title, description/explicit empty value, style, planning mode, status, timestamps and
  project ID;
- raw owner Principal ID is not displayed;
- explicit `Image upload is not implemented yet` boundary;
- distinct frontend unknown-route page.

### Styling and Accessibility

The approved Phase 1C Nocturne Studio direction is implemented with dark workspace surfaces,
warm neutral form canvas, restrained teal/gold accents and system fonts. Layouts cover desktop,
tablet and 390 px mobile. Semantic headings/regions, skip navigation, visible focus, permanent
labels, live status, alert summary, modal focus restoration/trapping, forced-colors support and
reduced-motion overrides are included.

The skip link moves focus to the stable, programmatically focusable `main`. Actual pathname/search
transitions and pagination changes move focus to the new page `h1`, with `main` as a safe fallback.
Projects list/detail and Create have exactly one correct `aria-current="page"` value; an unknown
route has none. Projects, Create, every Detail state and the unknown route render exactly one
page-level `h1`. Route titles include distinct Project Not Found and Page Not Found states.

## Automated Evidence

Final frontend evidence:

- ESLint: passed;
- TypeScript project build: passed;
- Vitest: `89 passed` across 6 files, repeated twice after the final title-timing repair;
- Vite production build: passed with 87 transformed modules;
- API client coverage includes exact-key acceptance/rejection through public client calls, create
  201, list, detail, 404, 409, 422, 500, 502, 503, 504, non-JSON, empty response, damaged schema,
  non-plain objects, abort and synthetic-secret suppression;
- router coverage includes redirects, skip-link focus, route/pagination focus, active navigation,
  document titles, list, create, direct detail, invalid UUID, project 404, unknown route and
  back/forward;
- page coverage includes loading, empty, success, pagination, navigation, retry, 503, transport
  failure, server validation, same-key retry, changed-payload key reset, double submit, keyboard
  submit, unsaved changes, abort-on-unmount and owner-safe detail behavior.

Repository regression evidence:

- Ruff: passed;
- Ruff format check: passed;
- strict mypy: passed;
- backend unit tests: `160 passed`, 98% coverage;
- PostgreSQL integration tests: `30 passed`;
- uv lock check and locked sync: passed;
- pnpm frozen install: passed without changing package metadata or the lockfile;
- full `make check`: passed when supplied the active Compose database URL ephemerally.

The first unoverridden `make check` reached integration and failed because the pre-existing `.env`
still points at a different `127.0.0.1:5432` PostgreSQL service. The file was not changed. The
complete command was rerun with a connection string derived in memory from the already-running
CreativeDeploy Compose PostgreSQL container; all gates then passed.

## Browser Vertical Slice Evidence

The remediation used the installed system Chrome and the environment-provided Playwright runtime;
no repository browser dependency, package or audit script was added.

Observed real-browser evidence:

1. A real system `Tab` focused the skip link and `Enter` moved focus to `main`, with the matching
   `#main-content` hash.
2. A mouse-free keyboard journey covered Projects → Create → validation summary/field → unsaved
   dialog traversal and Escape restoration → one successful create → Detail `h1` → Projects `h1`.
   The browser issued one POST, used one key and performed one detail navigation; PostgreSQL showed
   exactly `1/1/1` Project/Event/Idempotency rows before exact cleanup.
3. Five actual Enter key events during one held in-flight request still produced one POST, one key,
   one navigation and one `1/1/1` transaction.
4. A real backend 409 was produced by rewriting only the first browser request key to a pre-seeded
   conflicting key. The alert received focus, retained payload B, exposed no key, Principal or
   payload hash, performed no automatic retry, and recovered only after the user activated a new
   protected attempt with a new key.
5. Confirmation loss after a committed malformed 201 retried the unchanged payload with the same
   key and replayed the single committed row. Transport abort, 502, 503 and 504 also waited for user
   recovery and reused the same key for unchanged payload. Editing after transport failure used a
   new key. Every scenario performed exactly two browser attempts, one final navigation and one
   `1/1/1` database result before cleanup.
6. Direct detail, reload, Detail → Projects, Projects → Create and browser back/forward all produced
   the correct single `h1`, focus, active navigation and title. Invalid UUID made no API request;
   project 404 and unknown frontend route had distinct `h1` and titles. Returning through history
   to the unknown route focused its `h1` and left all normal nav items non-current.
7. With 21 real temporary projects, 25 actual Tab presses reached Next; Enter changed to items
   21–21 and restored focus to the Projects `h1`. Previous behaved the same. The audit rows were
   then deleted exactly.
8. Desktop 1440 px, tablet 768 px and mobile 390×844 rendered three, two and one project-card
   columns respectively, with no document-level horizontal overflow.
9. The production preview returned HTTP 200 for direct Create and unknown routes, with correct
   titles, one `h1`, active-nav semantics and no mobile overflow.

Critical success paths had zero browser console errors, zero warnings and zero page/unhandled
errors. Deliberate 404/409/502/503/504 and aborted-request probes produced only Chrome's expected
resource-level failure diagnostics; no application console error, React warning or leaked secret
was observed. No screenshot, video or recording artifact was retained in the workspace or task
temporary paths.

## Alembic and PostgreSQL Evidence

- `current`: `a10d3d8dab38 (head)`;
- `heads`: exactly `a10d3d8dab38 (head)`;
- `history`: one `<base> -> a10d3d8dab38` revision;
- `alembic check`: no new upgrade operations;
- development database round trip: `head -> base -> head`;
- base Catalog: only empty `alembic_version`;
- restored Catalog: `alembic_version` plus the three approved business tables and 37 business
  constraints and three explicit indexes;
- final revision: exactly `a10d3d8dab38`, revision count `1`;
- browser test data final state: Project/Event/Idempotency `0/0/0`;
- temporary migration databases/roles final state: `0/0`;
- development and maintenance databases both remained present.

## Candidate Boundary

The candidate changes only frontend code/configuration, the workspace pnpm lockfile and phase
documentation. It adds one direct dependency, `react-router ~8.3.0`; the lockfile adds only
React Router and its required transitive package. No package family was broadly upgraded.

Protected backend source, tests, uv metadata, ORM models, Migration, compose configuration,
Makefile, approved product/architecture/decision documents and `.env` remain unchanged.
There are no deleted files.

## Remaining Limits and Next Phase

- Demo Principal configuration is not public authentication or a real-user system.
- Create/list/detail are the only business operations; detail is read-only.
- Image upload, analysis, Polygon editing, inventory, RAG, AI providers, Agent workflows,
  HumanApproval and paint-plan generation remain unimplemented.
- No CI, application containers, production deployment or production validation is claimed.
- Phase 1D-3 remains `NOT_APPROVED`; Commit 10 does not exist.
- After a focused independent Phase 1D-3 read-only review, the next planned phase is
  **Phase 1D-4 — Integrated Product Review**.
