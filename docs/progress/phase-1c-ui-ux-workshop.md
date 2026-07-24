# Phase 1C — PaintPilot UI/UX Workshop Freeze

- Phase Status: `COMPLETE`
- Date: `2026-07-24`
- Approval Date: `2026-07-24`
- Implementation Status: `NOT_STARTED`
- Code Change Status: `NO_CODE_CHANGES`
- Visual Direction: `OWNER_APPROVED`
- Direction Name: `Nocturne Studio`
- Layout Subdirection: `Spacious Editorial`
- Layout Direction Status: `OWNER_APPROVED`
- Experience Architecture: `OWNER_APPROVED`
- Product Entry Concept: `OWNER_APPROVED`
- Nocturne Studio: `OWNER_APPROVED`
- Product Entry Implementation: `NOT_STARTED`
- Projects Workspace Direction: `OWNER_APPROVED`
- Create Project UX: `READY_FOR_IMPLEMENTATION`
- Create Project Owner Decisions: `OWNER_DECISIONS_RESOLVED`
- Real-product Priority: `CONFIRMED`
- Phase 1D Plan: `READY_FOR_IMPLEMENTATION`
- Phase 1D Implementation: `NOT_STARTED`
- Product Contract Amendment: `0.1.2 APPROVED_FOR_IMPLEMENTATION`
- Data Dictionary Amendment: `0.1.2 APPROVED_FOR_IMPLEMENTATION`
- ADR-0002: `Accepted`
- Contract Alignment Review: `APPROVED`
- Decision Authority: `Project Owner`

## Workshop Goal

Freeze the approved PaintPilot experience architecture and Create Paint Project UX while recording
the accepted, versioned contract amendment for the Phase 1D create/list/open/persist slice. This
approval closes Phase 1C and enables separately authorized Phase 1D implementation planning without
starting Migration, business code, dependencies or UI work.

Phase 1C completion means page responsibilities and experience direction are approved and can
support Phase 1D. It does not mean the Product Entry, complex particles, Projects Workspace,
Create Project, Detail page or any PaintProject business capability has been implemented.

## Product Entry Concept Approval

`OWNER_APPROVED`

Approved:

- Route: `/paintpilot`.
- Experience: Cinematic Product Entry.
- Direction: Nocturne Studio.
- Layout: spacious, low-density, single-primary-action.
- Primary CTA: `Enter PaintPilot Workspace`.
- Visual subject: non-character Abstract Material Study.
- Visual language: magnetic particles, Polygon nodes, light direction, material / color zones
  and depth transitions.
- Narrative: Capture, Structure, Direct, Plan.

Prohibited:

- robot, mecha, anime/game character, Tarot symbol or unauthorized IP;
- Project Cards in the Hero;
- dense dashboard or fake user data.

The approved concept image confirms visual direction only. It is not a formal image asset, does
not enter the product or public repository and does not prove that Product Entry motion or any
related business capability is implemented.

## Real-product Priority

CreativeDeploy / PaintPilot exists first to become a real, usable and sustainably iterated product,
not only a job-search demonstration.

Implementation priority:

1. PaintProject creation and database persistence.
2. Project list and project opening.
3. Image upload and quality checks.
4. Human region confirmation.
5. Repaint-planning workflow.
6. Complete cinematic Product Entry motion.

The `/paintpilot` visual direction is approved, but complex particles and scroll narrative do not
block core product flows. Portfolio claims must be grounded in real capability, tests, evaluations
and usage evidence.

## Architecture Correction

The owner found that the Spacious Nocturne Project Home still lacked the premium quality associated
with Spline / Ori Scan-style product experiences.

Formal analysis:

- Product Marketing Experience and Application Workspace were incorrectly combined.
- A project-management page cannot also carry the complete product narrative and daily operations.
- Adjusting particles, cards or color alone cannot resolve the responsibility conflict.

Formal decision:

- `/paintpilot`: Cinematic Product Entry.
- `/paintpilot/projects`: Spacious Application Workspace.
- `/paintpilot/projects/new`: Immersive Create Project.
- `/paintpilot/projects/:projectId`: Minimum Project Detail in Phase 1D and future Precision
  Workspace.

Product Entry owns the single visual subject and Capture / Structure / Direct / Plan story.
Projects Workspace owns stable project tasks. Precision Workspace owns neutral, high-accuracy
operation. No route or page is implemented by this decision.

## Confirmed

- CreativeDeploy remains a domain-neutral platform brand.
- PaintPilot is the current Featured Deployment.
- Arcana remains a future Planned / Upcoming Deployment and is not promoted alongside
  PaintPilot on the current product surface.
- PaintPilot should balance a premium creative tool, a professional AI engineering platform,
  and an approachable repaint-planning workspace.
- Product Entry uses one non-character Abstract Material Study and one
  `Enter PaintPilot Workspace` CTA.
- Product Entry concept status is `OWNER_APPROVED`; implementation remains `NOT_STARTED`.
- Product Entry does not show Project Cards, Create Project or management controls.
- Projects Workspace prioritizes large visual Project Cards and stable daily use.
- Create Project uses an independent immersive page rather than a large inline form.
- Projects Workspace uses a dark Nocturne shell and a spacious dark matte gallery; a warm neutral
  precision canvas is reserved for the future project-specific Workspace.
- Development UI copy is English; future localization includes Chinese.
- Motion may be visibly designed, but precision work areas remain stable.
- UI/UX decisions require continued discussion with the project owner.
- A generic administration-dashboard template is not an approved default.
- Direction: `Nocturne Studio`
- Layout Subdirection: `Spacious Editorial`
- Theme: dark professional creative workspace
- Product Entry: Cinematic Product Entry with four-stage scroll narrative
- Projects Workspace: Option C2 Spacious Nocturne Editorial
- Product Entry Hero: one Abstract Material Study, abstract magnetic particles and
  `Enter PaintPilot Workspace`
- Product Entry Motion: cinematic but controlled scroll rhythm and depth transitions
- Projects Workspace Motion: low-intensity Header particles, light card feedback and short transitions
- Precision canvas: warm neutral
- Project cards: large, limited dark matte gallery; at most three in the first desktop viewport
- Empty state: honest `No projects yet`, without fake projects
- UI assets: real user project content or neutral, original, non-character placeholders only
- Arcana: platform-level future deployment only; never a PaintPilot module or navigation item
- Create Project: immersive standalone page at planned route
  `/paintpilot/projects/new`
- Create Project first release: real PaintProject creation and database persistence only.
- Create Project excludes image upload, AI, Provider, inventory, knowledge, Polygon, multi-tenant
  controls, member invitations and complex settings.
- Create Project Title is trim + `1–80`; Description is trim + maximum `500`, with empty normalized
  to `null`.
- Target Style is fixed to `cel_shading` and shown as `Cel Shading · Current release`, not a selector.
- Planning Mode is fixed by the server to `planning_only_demo` and shown only as a capability note.
- Create Project uses the warm-neutral matte form canvas by default.
- Create success always opens `/paintpilot/projects/:projectId`; Phase 1D includes a minimum
  database-backed detail page rather than a long-term list fallback.
- Create Project owner decisions are `OWNER_DECISIONS_RESOLVED`.

## Latest Owner Feedback

- The Product Entry direction is approved.
- The Create Project field, visual-surface, success-route and capability-boundary decisions are
  resolved for implementation planning.
- Rights Attestation belongs to the future per-ImageAsset upload flow, not empty-project creation.
- Real product capability and sustainable iteration take priority over portfolio-only spectacle.
- Complex Product Entry motion must not block PaintProject creation and persistence.
- The Spacious Nocturne Project Home still lacked the intended Spline / Ori Scan-style premium
  product-entry quality.
- Product storytelling and application tasks must be separated rather than restyled together.
- The previous concept was too crowded.
- It showed too many cards and functions at once.
- The density weakened the intended premium quality.
- The owner wants a simpler, more direct layout with larger elements and stronger whitespace.
- Robots, mecha and anime characters must not be used as UI decoration.
- PaintPilot must not contain a Tarot or Arcana Future Module.

## Create Project UX Freeze

`READY_FOR_IMPLEMENTATION`

Frozen decisions:

- user inputs are Title and optional Description only;
- Title is required, trimmed and `1–80` Unicode code points;
- Description is optional, trimmed, maximum `500`, and empty becomes `null`;
- the service writes `requested_target_style=cel_shading`, `planning_mode=planning_only_demo`,
  `status=DRAFT`, Owner, ID and timestamps;
- Target Style and Planning Mode are readable product information, not disabled or editable controls;
- the default form surface is warm-neutral matte inside the Nocturne Studio dark shell;
- Create Project is the only primary CTA;
- success requires a real service project ID and opens `/paintpilot/projects/:projectId`;
- the detail page reloads the project from the API and states
  `Image upload is not implemented yet`;
- duplicate and unknown-outcome retries require end-to-end idempotency, not only a disabled button.

The UX and wireframe documents remain implementation specifications. No form, route, API, table or
animation has been implemented by this freeze.

## Rights Attestation Relocation

Create Project no longer displays, validates or submits a Rights Attestation. The control is retained
as a future Image Upload requirement tied to the exact ImageAsset:

- persist `rights_attestation_status` for each uploaded asset;
- bind the declaration to the file, attesting Principal and `intended_usage`;
- block region analysis unless the status is `confirmed`;
- retain attestation history for audit;
- do not present the platform as independently proving third-party rights.

This relocation agrees with the current Product Contract and Data Dictionary. Those Phase 0B controls
were inspected but not modified.

## Phase 1D Planning Result

The Phase 1D plan is `READY_FOR_IMPLEMENTATION`; implementation remains `NOT_STARTED`.

The planned slice includes:

- Alembic-managed PostgreSQL persistence;
- PaintProject, creation StateTransitionEvent and CommandIdempotencyRecord;
- configured PrincipalContext and owner-scoped reads;
- POST create, GET list and GET detail APIs;
- `react-router` v8 Declarative Mode for Projects, Create and Detail;
- real empty/loaded/failure states without fake projects;
- explicit transaction, idempotency, rollback and safe-error behavior;
- backend, integration, frontend and browser-smoke verification.

## Phase 1D-0 Contract Alignment

Product Contract 0.1.2 and Data Dictionary 0.1.2 are
`APPROVED_FOR_IMPLEMENTATION`; ADR-0002 is `Accepted`. The approved alignment records:

- Title trim + `1–80` and Description trim + maximum `500`, with empty Description normalized to
  `null`;
- `PaintProject.requested_target_style=cel_shading` as the initial intent;
- current user-confirmed StyleConfiguration as the future detailed configuration authority;
- `PaintProject.planning_mode=planning_only_demo` as a server-owned project boundary;
- server-computed create scope_key with unique `scope_key + idempotency_key`;
- no deterministic Project UUID, no client Project ID and no ID derivation from Idempotency-Key;
- initial `null → DRAFT` StateTransitionEvent in the same transaction as the Project and completed
  idempotency result;
- HTTP 201 create, paginated list Envelope and other-owner detail HTTP 404;
- configured human Principal for Phase 1D;
- planned `react-router` v8 and manually reviewed Alembic autogenerate.

The amendment does not change the 16 states, 47 Transitions, 17 numbered Guards, Golden Case art
rules, ImageAsset Rights Attestation, planning-only boundary, Arcana timing, Phase 1B implementation
or frozen Create Project UX. Phase 1D remains `NOT_STARTED`.

## Created Documents

1. `docs/design/paintpilot-visual-direction-v0.1.md`
   - three-layer Brand Experience / Application / Precision architecture;
   - typography, material, motion and reduced-motion direction;
   - Spacious Editorial density rules and UI Content and Asset Policy;
   - CreativeDeploy / PaintPilot / Arcana boundary.
2. `docs/design/paintpilot-project-home-ux-spec-v0.1.md`
   - `/paintpilot/projects` Projects Workspace responsibility;
   - one project-management task with simplified Projects / Create Project navigation;
   - honest Empty Mode and limited Active Projects Mode;
   - reduced first-card metadata and deferred engineering fields;
   - loading, empty, failure, responsive and accessibility behavior.
3. `docs/design/paintpilot-project-home-wireframes-v0.1.md`
   - historical Options A, B and C marked as superseded;
   - owner-approved Option C2 for `/paintpilot/projects`;
   - spacious desktop/mobile Empty and Active wireframes with restrained motion.
4. `docs/design/paintpilot-nocturne-studio-render-brief-v0.1.md`
   - Product Entry-only desktop 16:10 and mobile 390 px concept requirements;
   - Abstract Material Study, Hero, narrative preview and Entry transition;
   - dashboard-free negative prompt and pre-implementation review checklist.
5. `docs/design/paintpilot-product-entry-ux-spec-v0.1.md`
   - owner-approved Product Entry purpose, Hero, CTA and four-part scroll narrative;
   - mobile, accessibility, performance-budget and capability boundaries;
   - CSS + Canvas, WebGL / Three.js and Spline Runtime comparison.
6. `docs/design/paintpilot-product-entry-wireframes-v0.1.md`
   - owner-approved desktop and mobile Hero direction;
   - Capture / Structure / Direct / Plan focus states;
   - transition to Projects Workspace and reduced-motion states.
7. `docs/design/paintpilot-create-project-ux-spec-v0.1.md`
   - owner-resolved real PaintProject field contract and validation;
   - fixed style/mode, submission, idempotency and recovery behavior;
   - per-ImageAsset Rights Attestation relocation;
   - fixed detail-page success, accessibility, responsive and real-product boundaries.
8. `docs/design/paintpilot-create-project-wireframes-v0.1.md`
   - frozen desktop and mobile Create Paint Project forms;
   - validation, submitting, success, unsaved changes and unknown-outcome states;
   - warm-neutral form, read-only capability information and reduced-motion behavior.
9. `docs/progress/phase-1d-paint-project-vertical-slice-plan.md`
   - create/list/open/persist vertical-slice scope;
   - Alembic, async session, Principal, API, routing and persistence plan;
   - scope_key idempotency, transaction boundary and rollback plan;
   - list Envelope, owner-safe 404 and multi-layer test plan.
10. `docs/decisions/ADR-0002-paintproject-creation-and-idempotency-boundary.md`
    - requested Target Style and StyleConfiguration authority boundary;
    - planning mode ownership and configured Principal boundary;
    - resource-creation idempotency without deterministic Project UUID;
    - API ownership, React Router and Alembic decisions.

## Future Refinement

The following design work remains useful but does not block Phase 1D:

1. Final typography pairing.
2. Particle implementation technology.
3. Particle budget for low-performance devices.
4. Complete Product Entry scroll motion.
5. Exact Precision Workspace canvas details.

At implementation start, official React Router v8 and Alembic 1.x stable versions and compatible
ranges still require fresh verification.

## Capability Boundary

- PaintProject, project list and create-project behavior are not implemented.
- Image upload, AI analysis, RAG, Polygon Editor, inventory, Agent workflow, HumanApproval and
  Trace are not implemented.
- The workshop does not implement business API routes or database schema. The Phase 1D document
  plans their shape but keeps Migration, ORM, components and Design Tokens unimplemented.
- Future project status must come from deterministic program state.
- Model suggestions cannot be presented as user-confirmed facts.
- Human Review remains visible and version-bound in future workflow designs.

## No Code Changes

This freeze modifies only the authorized design, product, architecture, decision and progress
Markdown. It does not modify frontend or backend code, dependencies, lockfiles, configuration,
images, Workflow State Machine, ADR-0001 or Phase 1B evidence. No Migration, Figma file, generated
UI image, Storybook, component library or route is created.

## Next Review Step

`Phase 1D-1 — Database Foundation and First Alembic Migration Planning`

Implementation does not begin in this freeze task. The approved contracts allow the next separately
authorized task to plan the database foundation and first Alembic Migration.
