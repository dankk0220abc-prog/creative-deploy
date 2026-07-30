# CreativeDeploy Agent Guide

## Project Goal

CreativeDeploy is a deployment-engineering portfolio project. PaintPilot is its primary,
planning-only case. The approved product contract keeps deterministic program state,
model suggestions, and human-owned facts separate.

## Current Implemented Capability

Phase 1B, Phase 1D-1A, Phase 1D-1B and Phase 1D-2 are complete and committed. Commit 8
`2c76e5ef51e4fea726407d5cccfe409a2643d694` contains the approved three-model
PaintProject persistence foundation and sole Alembic Revision `a10d3d8dab38`. Commit 9
`6d2c3d8001c3737e2e441ee1c0df4179660f0c57` contains the independently reviewed
PaintProject persistence and API implementation.

Phase 1D-3 — React Router and Projects Pages entered history as Commit 10
`5965a8707a6ccb06d2f58d8655aabac9630e4abd`. Its source-code baseline is the UX remediation
child `2f99aaf8e1726761c2d89ac444af8380a1cedb79`
(`fix(web): align project home UX contract`). The deterministic Phase 1D-3 closure commit is
`c8043b9a75aa9363a661fa245c7ac999961788fd`; its parent and governance seal is
`ac8630ae393cb6ca5bf3a2d1db5070531d6f3f52`.

Phase 1E-1 — ImageAsset Foundation is `CLOSED`. Its independently reviewed implementation was
sealed by `9b3b23ac3e1f056a73e3934d3da51b24aa7f671d` with verdict
`PHASE_1E_1_PASS_READY_FOR_SEALING` and Revision `5ed9906e7d33`. It adds one private immutable
`primary_mvp_input` slot, deterministic file acceptance, user rights attestation, owner-scoped
metadata/content, retained replacement history, and a provider-neutral storage boundary with a
development/test-only local adapter. It does not add image quality assessment or AI.
Independent review F-01 proved the original `os.replace` publication could overwrite an existing
immutable object. The remediation uses atomic no-replace publication, typed collisions, and
receipt-bound compensation that revalidates object identity and database references. Upload
idempotency remains formally Project-scoped. The code and canonical automated gates pass. The
first browser upload used a prohibited
private-photo fixture and remains `INVALID_ATTEMPT`; that dedicated test project and object were
precisely cleaned. A later real-browser continuation used only program-generated JPEG, PNG, WebP,
and invalid fixtures and passed upload, safe retry, retained replacement, private preview,
restarts, responsive checks, and exact cleanup. A new post-remediation synthetic run repeated the
complete journey. The first independent review returned
`PHASE_1E_1_FAIL_REMEDIATION_REQUIRED`; Security Remediation Round 1 added no-replace publication
and receipt compensation, and the second independent review authorized sealing.

The user confirmed the historical approximately 60% checkpoint direction for Phase 1E-2 —
Multi-Role ImageSet and Readiness. The original independent review returned
`CONTRACT_OR_ARCHITECTURE_DECISION_REQUIRED`: F-01 demonstrated a real 201 `primary_front`
replacement in unauthorized `IMAGE_UPLOADED`. Project control retained ADR-0004, and the focused
remediation made the Service role/current/operation/state policy the final authority. A fresh
independent review returned
`PHASE_1E_2_WORKFLOW_GATE_REMEDIATION_PASS_READY_FOR_SEALING`; the implementation was sealed by
`cc89aa246607f7c44b4639149a3b251b803d3a80`, and Phase 1E-2 is `CLOSED`. It adds exact roles
`primary_front`, `reference_back`, `reference_angle`, and optional `reference_detail`; preserves
per-role immutable history; derives deterministic ImageSet readiness facts; and appends human
READY / NOT READY fingerprint-bound reviews. Revision `d4c8a1f7b2e9` maps sealed
`primary_mvp_input` rows in place and adds `image_set_readiness_reviews` without changing the
historical revisions. The original failure remains historical evidence and is not rewritten as
an initial pass.

The overall project checkpoint is approximately 70% (`approximately_70_percent`). Phase 1F —
Human-Governed Region Annotation and Review is
`PHASE_1F_SNAPSHOT_TARGET_REMEDIATION_IMPLEMENTED_READY_FOR_INDEPENDENT_REVIEW`.
Candidate Revision `7f3a2b9c4d1e` adds immutable human RegionSet/Region/Vertex/Review persistence,
deterministic ppm simple-Polygon validation, ImageSet-fingerprint staleness, Project-scoped
idempotent save/submit/review commands, append-only review, and an SVG workbench. This is not
independent approval, a Git seal, production readiness, or phase closure. AI is
`NOT_AUTHORIZED`; external object storage is `NOT_SELECTED`; public/signed URLs are
`NOT_AUTHORIZED`; deletion and real authentication are `NOT_IMPLEMENTED`; local storage is
development/test only; production storage is `NOT_READY`.

The historical implementation conversation ended `PHASE_1F_IMPLEMENTATION_FAILED` despite
passing technical gates: one supplemental final-source browser attempt used the wrong Vite proxy
variable and sent one unsuccessful Create request to the unrelated service on port 8000. Its
formal classification is `ENVIRONMENT_ISOLATION_INVALID_ATTEMPT`; that deviation remains
historical evidence and must not be rewritten. A later controller-authorized continuation started
from the corrected 35-path baseline, used API `18160`, Vite `15160`, and a request-audit proxy on
`18161`, enforced an explicit not-port-8000 target guard, and performed no VisualEngineer request,
check, log, container, database, or file operation. The full isolated browser journey and exact
cleanup passed. The candidate is now ready only for a fresh independent focused read-only review;
this is not approval or authorization to seal.

The current source and verification evidence include:

- monorepo foundation;
- FastAPI process liveness;
- real PostgreSQL readiness using `SELECT 1`;
- local PostgreSQL through Docker Compose;
- same-origin PaintProject API traffic through the Vite development proxy;
- backend and frontend automated quality checks;
- browser-based product-loop, failure and recovery validation;
- one shared SQLAlchemy Declarative Base with a runtime-immutable naming convention;
- one reviewed business Revision with `PaintProject`, `StateTransitionEvent` and
  `CommandIdempotencyRecord`;
- an explicit-configuration, non-production single human `configured_demo_operator` Principal
  Adapter with no fallback identity;
- one request-scoped `AsyncSession`, a PaintProject-specific Repository and an application Service;
- atomic project creation with initial audit event and completed idempotency result;
- bounded transaction-local PostgreSQL lock/statement waits and narrow safe database-error
  classification;
- owner-scoped create, list and detail APIs at `/api/v1/paint-projects`;
- deterministic real-PostgreSQL regressions for replay, conflict, rollback, response-loss recovery,
  timeout, concurrency, owner isolation and process restart persistence.
- React Router v8 Declarative Mode with redirects for `/` and `/paintpilot`, business routes for
  Projects, Create and Detail, and a safe unknown-route page;
- a shared CreativeDeploy/PaintPilot shell using the approved Phase 1C visual direction;
- a contract-validating same-origin PaintProject API client with abort support and controlled
  201/404/409/422/500/502/503/504 handling;
- database-backed list, create and read-only detail pages with loading, empty, safe error and
  explicit retry states;
- page-lifetime UUID idempotency protection, same-payload retry, edit/conflict key reset and
  duplicate-submit prevention without localStorage or visible keys;
- real-browser create/list/detail/reopen, frontend restart, API restart, 404, database 503,
  API-unavailable recovery, browser-history and 390 px responsive verification.
- one sealed ImageAsset model and Revision `5ed9906e7d33`, preserving historical
  Revision `a10d3d8dab38`;
- composite owner/project/current/lineage constraints and one-current partial uniqueness;
- streamed private storage with SHA-256, atomic no-replace publication, typed collision failure,
  publish receipts, identity/reference-checked database-failure compensation, orphan detection,
  traversal protection, and explicit production rejection;
- owner-scoped upload/list/detail/private-content APIs with command replay/conflict and retained
  replacements;
- a single-slot upload/attestation/private-preview/history UI with safe retry and duplicate-submit
  protection.
- a compliant real-browser JPEG/PNG/WebP continuation with one-shot confirmation-loss replay,
  immutable three-version history, invalid-file rejection, API/Vite restart persistence,
  1440×900, 768×1024 and 390×844 verification, and zero-residual cleanup.
- one sealed Phase 1E-2 Revision `d4c8a1f7b2e9` with exact four-role ImageAsset vocabulary,
  in-place Phase 1E-1 compatibility mapping, and one append-only readiness-review table;
- a derived owner-scoped ImageSet with per-role current/history, deterministic checklist,
  canonical fingerprint, `incomplete/ready/not_ready/stale` states, and explicit stale reasons;
- Project-locked, Project-scoped idempotent human readiness review creation with database-enforced
  owner/Project/role snapshots and upload/review race coverage;
- a four-role workbench with required/optional labels, private previews, immutable histories,
  safe add/replace, blockers, human READY / NOT READY, retry, history, and reconfirmation.
- a Phase 1F candidate with four append-only annotation/review tables, normalized ppm simple
  Polygons, deterministic geometry fingerprints, source staleness, optimistic version conflicts,
  and Project-row locking for save/submit/review versus image mutation;
- an owner-scoped RegionSet API and `/paintpilot/projects/:projectId/regions` SVG workbench with
  draw/edit, visibility, opacity, undo/redo, immutable history, submit, review, stale recovery,
  and responsive behavior.

The Phase 1D-3 F-01/F-02 technical remediation was independently reviewed and sealed. This does
not cure or erase the governance exception: Commit 10 entered Git history without a formal prior
repository approval record, and no prior repository approval evidence was found. The later review
does not backdate approval.

The commit hashes and relationships are `GIT_VERIFIED_FACT`. The no-prior-approval,
retrospective-review, focused-review, and sealing records are
`OWNER_SUPPLIED_EXTERNAL_REVIEW_RECORD`. The governance seal is a `GIT_VERIFIED_FACT`.

## Phase 1D Closed Governance Boundary

The reconciliation record at
`docs/progress/phase-1d-3-governance-reconciliation-candidate.md` passed independent review with
verdict `PHASE_1D_3_GOVERNANCE_RECONCILIATION_PASS_READY_FOR_SEALING` and was sealed by
`ac8630ae393cb6ca5bf3a2d1db5070531d6f3f52`. Phase 1D-3 is `CLOSED`.

Phase 1D-4 retained its original verdict `PHASE_1D_4_FAIL_REMEDIATION_REQUIRED`; the reviewer did
not ignore the README phase-state contradiction. That sole blocker was later independently
remediated, independently reviewed with verdict
`README_PHASE_STATE_REMEDIATION_PASS_READY_FOR_SEALING`, and sealed by
`707bdfa3c5931867125cc9c7dc11067a86f5f343`. The combined evidence closes Phase 1D-4 without
rewriting the original failure. Phase 1D-4 is `CLOSED`, Phase 1D is `COMPLETE`, and Phase 1E-1 is
`CLOSED`. Its implementation seal is `9b3b23ac3e1f056a73e3934d3da51b24aa7f671d`; this does not
authorize production storage, image quality assessment, AI integration, or a later product phase.
See `docs/progress/phase-1e-1-imageasset-foundation-closure.md`.

The user later authorized Phase 1E-2 at the checkpoint. Its implementation passed the fresh
independent remediation review, was sealed by
`cc89aa246607f7c44b4639149a3b251b803d3a80`, and is `CLOSED`; this does not alter the closed
Phase 1E-1 record. Phase 1F is now an unsealed implementation candidate and remains pending a
fresh independent read-only review.

For every subsequent Codex task:

- do not claim Commit 10 is uncreated;
- do not claim or imply Commit 10 was approved before creation;
- preserve the process exception and evidence-source classification;
- preserve the governance seal commit and do not reopen Phase 1D-3;
- preserve the Phase 1D-4 original failure and later blocker-remediation evidence;
- do not reopen or re-enter Phase 1D-3, Phase 1D-4, or Phase 1D;
- keep Phase 1E-1 `CLOSED` and preserve its implementation seal and complete review history;
- keep Phase 1E-2 `CLOSED`, preserve implementation seal
  `cc89aa246607f7c44b4639149a3b251b803d3a80`, and do not reopen it;
- preserve the original Phase 1E-2 F-01/real-201 evidence; ADR-0005 does not supersede the
  ADR-0004 primary workflow gate;
- do not claim the sealed Phase 1E-1 implementation is production-ready;
- do not integrate AI;
- do not select external object storage, public URLs, irreversible deletion, real authentication,
  or major permission changes;
- keep Phase 1F as
  `PHASE_1F_SNAPSHOT_TARGET_REMEDIATION_IMPLEMENTED_READY_FOR_INDEPENDENT_REVIEW` until a fresh
  read-only review passes and a separate authorized task performs Git sealing; do not describe
  it as approved or closed;
- do not rewrite historical snapshots into fictional pre-commit approval.

Phase 1D completion closes the specified PaintProject vertical slice. The closed Phase 1E-1 work
does not claim production validation, real-user validation, image-quality implementation, or AI
authorization.

## Not Implemented

Do not claim or imply implementation or independent approval of:

- public authentication, full authorization, JWT, OAuth or a real-user Principal Adapter;
- ImageQualityAssessment, automated viewpoint analysis, segmentation, automated Polygon
  generation, automated semantic labels, or automated region analysis;
- AI providers, Agent workflows, RAG, inventory, citations, or Trace;
- a HumanApproval entity or workflow transitions beyond `null -> DRAFT` and guarded
  `upload_image -> IMAGE_UPLOADED`; Phase 1E-2 readiness reviews are append-only human records,
  not workflow transitions;
- PaintProject update/delete/owner transfer;
- image-backed project cards, editable PaintProject fields, image update/delete, or public images;
- Redis, workers, CI, production deployment or real-user validation.

## Directory Responsibilities

- `apps/api`: the independent uv-managed FastAPI package, health, PaintProject, and ImageAsset schemas,
  configuration, async database engine/session, shared Metadata, Alembic, the approved three-model
  Phase 1D persistence foundation, the committed Phase 1D-2 Repository/Service/API, the sealed
  Phase 1E-1 ImageAsset foundation, the sealed Phase 1E-2 ImageSet/readiness foundation, the
  unsealed Phase 1F RegionSet candidate, and pytest tests.
- `apps/web`: the pnpm-managed React/Vite PaintPilot application shell, routes, API client,
  Projects/Create/Detail/Region Workspace pages and Vitest tests.
- `docs/product`, `docs/architecture`, `docs/decisions`: approved Phase 0 baselines; do not
  edit them casually.
- `docs/progress`: implementation evidence and phase status.
- `data/golden-cases`: user-authorized reference material; do not modify or repurpose it
  without explicit approval.
- `compose.yaml`: local PostgreSQL only.

## Required Reading Before Product Changes

Before changing product behavior, workflow, domain fields, or architecture, read:

1. `docs/product/paintpilot-mvp-product-contract-v0.1.md`
2. `docs/architecture/paintpilot-workflow-state-machine-v0.1.md`
3. `docs/architecture/paintpilot-domain-data-dictionary-v0.1.md`
4. `docs/decisions/ADR-0001-paintpilot-mvp-scope-and-control-model.md`

## Commands

Bootstrap:

```bash
make bootstrap
```

`make bootstrap` creates `.env` only when it is missing and preserves any existing file.
Run Make commands from the repository root. API settings resolve the repository-root
`.env` independently of the current working directory.

`APP_ENV` must be explicit and is limited to `development`, `test` or `production`. The current
Demo Principal Adapter requires explicit ID and display-name configuration in development/test and
rejects production. It is not public authentication; do not expose its write API publicly without
separately approved real authentication or deployment-platform access protection.

PostgreSQL:

```bash
make db-up
make db-down
```

Migration foundation:

```bash
make migration-current
make migration-heads
make migration-history
make migration-check
```

These commands never generate or upgrade a revision. The repository preserves historical
Revision `a10d3d8dab38`; the Phase 1E-1 implementation seal adds Revision `5ed9906e7d33` and a
fourth business table. The Phase 1E-2 implementation seal adds child Revision `d4c8a1f7b2e9`
and a fifth business table. Candidate child Revision `7f3a2b9c4d1e` adds four Phase 1F tables
without changing the sealed revisions. This does not imply production storage readiness,
independent Phase 1F approval, or phase closure.

Backend:

```bash
make api
make lint-api
make format-check-api
make typecheck-api
make test-api
make test-api-integration
```

Frontend:

```bash
make web
make lint-web
make typecheck-web
make test-web
make build-web
```

Full quality gate, with PostgreSQL already running:

```bash
make check
```

## Frontend Environment Boundary

Run standard frontend tasks through the Make targets above. Every pnpm Recipe must invoke
`$(PNPM)` through the shared `WEB_COMMAND_ENV` denylist so known CreativeDeploy backend
application and PostgreSQL variables are removed before pnpm or its lifecycle scripts start.
Any new pnpm Recipe must reuse that same boundary; never restore a global `.env` import or
export.

This denylist is not a complete operating-system process sandbox and does not claim to remove
unknown secrets. A pnpm command run directly from a shell inherits that shell's environment
under normal operating-system rules, unlike the standard Make targets.

## Non-negotiable Rules

- Never invent or overstate implemented capability.
- Never commit secrets or a real `.env`.
- Keep the database URL as `SecretStr` and unwrap it only at the SQLAlchemy Engine boundary.
- Never export the complete `.env` to unrelated frontend or dependency-install processes.
- Do not use the system default `python3` for project work.
- Run Python tooling through uv and keep `apps/api/uv.lock` current.
- Run Node tooling through Corepack pnpm and keep `pnpm-lock.yaml` current.
- Use `docker compose`, not a standalone Compose installation.
- Do not add a top-level `version:` field to `compose.yaml`.
- Do not add business entities, tables, revisions, AI SDKs, Redis, app Dockerfiles, or
  production infrastructure unless an approved task explicitly includes them.
- Keep PostgreSQL bound to `127.0.0.1` for local development.
- Every ORM entity must inherit the single `creativedeploy_api.db.Base`.
- Never create a second declarative Base or independent application MetaData.
- Use stable database constraint names; every `CheckConstraint` requires an explicit name.
- Never store `DATABASE_URL` or credentials in `alembic.ini`.
- Never run `alembic upgrade` automatically during application startup.
- Treat autogenerate output only as a candidate and review every detected operation manually.
- Every Migration must provide valid upgrade and downgrade paths and have integration coverage.
- Run `alembic check` after changing ORM models.
- Never create empty revisions.
- Do not rewrite a shared or applied historical Migration merely to silence a diff.
- Preserve historical business Revision `a10d3d8dab38`; never rewrite it.
- Preserve the sealed Phase 1E-1 Revision `5ed9906e7d33`, ImageAsset physical constraints,
  private-storage boundary, and committed Phase 1D-2 API contracts during focused review.
- Preserve sealed Revision `d4c8a1f7b2e9`, the ImageSet/readiness implementation, and both
  historical parent revisions; never rewrite any of the three.
- Treat candidate Revision `7f3a2b9c4d1e` and all Phase 1F paths as unsealed review material;
  do not rewrite historical revisions or describe the candidate as approved before review.
- Preserve safe 503 responses: never expose database URLs, passwords, stack traces, or raw
  infrastructure exceptions.
- Keep Create Project database waits finite and transaction-local. Do not remove the positive,
  bounded lock/statement timeout settings, interpolate timeout SQL, or replace PostgreSQL
  arbitration with a process-local lock.
- Do not classify every SQLAlchemy exception as retryable: connection/invalidation and tagged
  database-wait failures may return safe 503; unexpected integrity, programming, data and generic
  SQLAlchemy failures remain safe non-retryable 500 responses.
- Never introduce a default Demo Principal, allow HTTP fields to select it, or permit the current
  Demo Principal Adapter in production.
- Preserve the frontend AbortController and request-generation guards so late health
  or PaintProject responses cannot overwrite newer state.
- Preserve same-payload idempotency-key reuse after uncertain transport/503 outcomes, reset the key
  after field edits or conflict, and never persist the key to localStorage or expose it in the UI.
- Preserve Project-scoped upload idempotency: the same Principal/Project/key replays or conflicts
  by payload, while a different Project or Principal is an independent command scope.
- Never replace, truncate, or delete a pre-existing formal image object. Only a successful
  no-replace publish receipt may authorize compensation, and cleanup must revalidate object
  identity plus absence from all database references.
- Preserve Commit 10 `5965a8707a6ccb06d2f58d8655aabac9630e4abd` and the current code baseline
  `2f99aaf8e1726761c2d89ac444af8380a1cedb79` as immutable Git history; never backdate approval.
- Preserve the independently reviewed Phase 1D-3 governance reconciliation and its seal commit
  `ac8630ae393cb6ca5bf3a2d1db5070531d6f3f52`; do not reopen Phase 1D-3 or backdate Commit 10
  approval.
- Preserve the independently reviewed README remediation and its seal commit
  `707bdfa3c5931867125cc9c7dc11067a86f5f343`; do not rewrite the original Phase 1D-4 failure.
- Keep Phase 1D-3 and Phase 1D-4 `CLOSED` and Phase 1D `COMPLETE`; do not reopen Phase 1D.
- Keep Phase 1E-1 and Phase 1E-2 `CLOSED`; keep Phase 1F
  `PHASE_1F_SNAPSHOT_TARGET_REMEDIATION_IMPLEMENTED_READY_FOR_INDEPENDENT_REVIEW` until
  independent review and separately authorized sealing. Do not integrate AI or image quality
  assessment, select external object storage, add public URLs, irreversible deletion, real
  authentication, or major permission changes.
