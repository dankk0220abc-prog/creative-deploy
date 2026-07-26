# Phase 1D-2 — PaintProject Persistence and API Candidate

- Phase Status: `IMPLEMENTED_PENDING_REVIEW`
- Contract Status: `APPROVED`
- Implementation Status: `IMPLEMENTED_PENDING_REVIEW`
- Approval Status: `NOT_APPROVED`
- Commit Status: `UNCOMMITTED — NO_NEW_COMMIT_CREATED`
- Protected Baseline:
  `2c76e5ef51e4fea726407d5cccfe409a2643d694`
- Phase 1D-1B Status: `COMPLETE_AND_COMMITTED`
- Migration Status: `APPROVED_AND_COMMITTED_UNCHANGED`
- Revision ID: `a10d3d8dab38`
- Review Date: `2026-07-26`

## Resolved Phase Scope

The implementation request called this stage Phase 1D-1C. The approved repository plan names the
next formal stage **Phase 1D-2 — PaintProject Persistence and API**. That formal name and its
approved boundary are authoritative.

The stage goal is to provide the database-backed backend half of the first PaintProject vertical
slice:

- configured human Principal context;
- one AsyncSession per request;
- owner-scoped persistence access;
- create/list/detail application services;
- one atomic create transaction containing the PaintProject, initial audit event and idempotency
  result;
- stable API request, response and error contracts;
- backend unit and real PostgreSQL integration evidence.

Phase 1D-3 owns React Router and the Projects, Create and Detail pages. It remains `NOT_STARTED`.
This candidate therefore does not claim the browser product loop, production validation or
real-user validation.

## Authority

- PaintPilot MVP Product Contract `0.1.3 APPROVED_FOR_IMPLEMENTATION`;
- PaintPilot Domain Data Dictionary `0.1.3 APPROVED_FOR_IMPLEMENTATION`;
- Workflow State Machine `0.1.1 APPROVED_FOR_IMPLEMENTATION`;
- ADR-0002 `Accepted`;
- ADR-0003 `Accepted`;
- Phase 1D PaintProject Vertical Slice Implementation Plan;
- approved and committed Phase 1D-1B schema at Commit 8.

No contract ambiguity or conflict was found. No schema decision was required.

## F-09 Final Remediation Status

- F-09-01 Demo Principal fail-closed:
  `REMEDIATED_AWAITING_INDEPENDENT_REVIEW`;
- F-09-02 finite PostgreSQL lock/statement wait:
  `REMEDIATED_AWAITING_INDEPENDENT_REVIEW`;
- F-09-03 precise SQLAlchemy error classification:
  `REMEDIATED_AWAITING_INDEPENDENT_REVIEW`;
- F-09-04 deterministic A–I concurrency/idempotency matrix:
  `REMEDIATED_AWAITING_INDEPENDENT_REVIEW`.

Phase 1D-2 remains `IMPLEMENTED_PENDING_REVIEW`, its Approval remains `NOT_APPROVED`, Commit 9 is
`NOT_CREATED`, and Phase 1D-3 remains `NOT_STARTED`. These remediation states are implementer
evidence only and require a final independent read-only review.

## Phase 1D-1B Closure

Phase 1D-1B is immutable historical foundation:

- status: `COMPLETE_AND_COMMITTED`;
- independent review: `APPROVED_FOR_COMMIT_8`;
- commit: `2c76e5ef51e4fea726407d5cccfe409a2643d694`;
- subject: `feat(api): add PaintProject persistence foundation`;
- sole Migration: `a10d3d8dab38`;
- findings: F-01 through F-05 `CLOSED`;
- ORM, Migration and PostgreSQL Catalog consistency: verified;
- concurrent temporary-database ownership and global hygiene regressions: passed.

That closure does not claim that Phase 1D-1B itself implemented an API, Repository, Service,
Principal Adapter, frontend page or complete product loop.

## Implemented Architecture

### Principal Adapter

`PrincipalContext` is a frozen, strict boundary model with the approved `human` and `system`
principal types. `APP_ENV` has no code default and accepts only `development`, `test` or
`production`. The configured Principal ID and display name also have no code defaults.
Development/test startup requires both values; production rejects the current
`configured_demo_operator` Adapter even if Demo Principal values are present. Authorization uses
only the stable Principal ID; the display name is an audit snapshot and is never an authorization
key.

The create request cannot provide owner, actor, style, planning mode or status. A non-human
Principal is rejected by the application service. List and detail are always scoped by the current
Principal ID, and a missing or other-owner project produces the same 404 response.

This is the approved local/internal/protected configured-Principal boundary, not public
authentication. JWT, OAuth, registration, Workspace and role expansion remain out of scope.
Production and public writes must wait for a separately approved real Principal Adapter or explicit
deployment-platform access protection.

### Session and Dependencies

The application lifespan owns one async session factory derived from the existing engine. Each
request receives one `AsyncSession` with `autoflush=False` and `expire_on_commit=False`, and the
session closes at dependency exit.

Explicit FastAPI dependencies provide:

- request correlation UUID;
- configured Principal;
- request AsyncSession;
- PaintProject application service.

No Migration runs at application startup.

### Schemas

The create body is strict and accepts only:

- `title`: trimmed, 1–80 Unicode code points;
- `description`: optional, trimmed, maximum 500, empty becomes `null`.

The read response exposes exactly the nine approved PaintProject fields. Timestamps must be
timezone-aware, status is limited to the approved 16-state set, and list responses use the frozen
`items`, `total`, `limit`, `offset` envelope.

### Repository

The repository is domain-specific rather than a general framework. It:

- parameterizes positive millisecond values into transaction-local PostgreSQL
  `set_config('lock_timeout', ..., true)` and `set_config('statement_timeout', ..., true)` before
  idempotency arbitration;
- arbitrates idempotency with PostgreSQL `INSERT ... ON CONFLICT DO NOTHING`;
- omits nullable result columns from the initial in-progress insert so they remain SQL `NULL`, not
  JSON `null`;
- reads the committed winner after a unique conflict;
- stages the project and initial event without committing;
- completes the acquired idempotency result;
- lists projects by owner in `updated_at DESC, id DESC` order;
- retrieves project detail by both project ID and owner Principal ID.

Routes contain no SQL and the repository contains no HTTP behavior.

The runtime defaults are `DATABASE_LOCK_TIMEOUT_MS=2000` and
`DATABASE_STATEMENT_TIMEOUT_MS=5000`; both accept only integers from 1 through 60000. They are
server configuration, never request inputs. Transaction-local scope prevents pool contamination.

### Service and Transaction

The application service owns business rules and the explicit transaction boundary. Create uses one
`async with session.begin()` block. The successful winner performs exactly one transaction commit;
an exception rolls back the idempotency claim, PaintProject and initial event together.

The server determines:

- `owner_principal_id` from Principal context;
- `requested_target_style=cel_shading`;
- `planning_mode=planning_only_demo`;
- `status=DRAFT`;
- UUIDs and timezone-aware timestamps.

The initial authoritative event is written in the same transaction:

- transition: `null -> DRAFT`;
- event: `create_project`;
- actor type: `user`;
- actor Principal and display snapshot: current configured human Principal;
- reason: `project_created`;
- correlation ID: request ID;
- metadata: `{}`.

No other transition or future workflow behavior is invented.

### Idempotency

Create requires a UUID `Idempotency-Key`. The server computes scope
`principal:{principal_id}:command:create_paint_project`, with no project ID supplied or derived.

The v1 payload hash is lowercase SHA-256 over deterministic UTF-8 JSON containing the normalized
title, normalized description and explicit serialization version. Keys are sorted and separators
are fixed.

Behavior:

- a new scope/key claims execution and atomically commits one project, one initial event and one
  completed replay record;
- the same scope/key and same payload returns the committed snapshot with
  `Idempotent-Replayed: true`;
- the same scope/key and different payload returns
  `409 IDEMPOTENCY_KEY_REUSED`;
- concurrent identical commands rely on the database unique constraint and transaction visibility,
  not a process-local lock;
- a rolled-back winner leaves no committed claim, so a waiter or retry can acquire the command;
- the 24-hour `expires_at` is cleanup eligibility metadata and does not weaken replay/conflict
  semantics while an existing row remains.

### API

Implemented under `/api/v1`:

- `POST /paint-projects`;
- `GET /paint-projects`;
- `GET /paint-projects/{project_id}`.

Create returns 201 for both the original committed result and an approved replay; replay is
identified by response header. List supports bounded `limit` and non-negative `offset`. Detail does
not disclose another owner's resource.

### Errors and Logging

Validation, application, database and unexpected failures map to the approved safe error envelope:

- `error_code`;
- `category`;
- `message`;
- `retryable`;
- `request_id`;
- `current_state`;
- `allowed_actions`;
- `safe_details`.

Validation details are controlled field/message pairs. Connection failures, connection-invalidated
errors and create-policy PostgreSQL wait timeouts return safe retryable 503 responses. Tagged
lock/statement timeouts use `DATABASE_WAIT_TIMEOUT`; other connection infrastructure uses
`DATABASE_UNAVAILABLE`. Idempotency payload reuse remains the approved 409.

Unexpected IntegrityError, ProgrammingError, DataError and unclassified SQLAlchemyError return safe
500 `INTERNAL_ERROR` with `retryable=false`. Classification uses exception class,
`connection_invalidated` and structured SQLSTATE/driver attributes, never exception-message
matching. An untagged query-cancelled SQLSTATE is not automatically a retryable wait timeout, and
`asyncio.CancelledError` is not converted. Logs contain only controlled exception class,
classification, SQLSTATE and request ID; no statement, params, database URL, Secret, request
payload, idempotency key or personal credential is logged.

## Deferred Scope

Phase 1D-3 or later retains:

- React Router dependency and application routes;
- Projects Empty/Active/Failure views;
- Create Project form and unsaved-change protection;
- Project Detail view;
- browser smoke review and the UI create/list/reopen/restart loop;
- Image Upload, Image Quality, AI, RAG, Polygon, AgentRun, HumanApproval and PaintPlan;
- update/delete/owner transfer;
- public authentication, Workspace and multi-tenant behavior;
- background idempotency cleanup worker;
- future `current_*` and `agent_run_id` fields.

No speculative frontend, provider or future-domain abstraction was added.

## Candidate Scope

Modified:

- `.env.example`;
- `AGENTS.md`;
- `README.md`;
- `apps/api/src/creativedeploy_api/api/router.py`;
- `apps/api/src/creativedeploy_api/app_factory.py`;
- `apps/api/src/creativedeploy_api/core/config.py`;
- `apps/api/tests/conftest.py` (approved scope expansion for explicit trusted test Settings only);
- `docs/progress/phase-1d-1b-paintproject-models-and-migration-candidate.md`;
- `docs/progress/phase-1d-paint-project-vertical-slice-plan.md`.

New:

- `apps/api/src/creativedeploy_api/api/dependencies.py`;
- `apps/api/src/creativedeploy_api/api/error_handlers.py`;
- `apps/api/src/creativedeploy_api/api/routes/paint_projects.py`;
- `apps/api/src/creativedeploy_api/core/principal.py`;
- `apps/api/src/creativedeploy_api/db/session.py`;
- `apps/api/src/creativedeploy_api/repositories/__init__.py`;
- `apps/api/src/creativedeploy_api/repositories/paint_projects.py`;
- `apps/api/src/creativedeploy_api/schemas/errors.py`;
- `apps/api/src/creativedeploy_api/schemas/paint_projects.py`;
- `apps/api/src/creativedeploy_api/services/paint_projects.py`;
- `apps/api/tests/integration/test_paint_project_api.py`;
- `apps/api/tests/unit/test_paint_project_principal_and_schemas.py`;
- `apps/api/tests/unit/test_paint_project_repository_and_dependencies.py`;
- `apps/api/tests/unit/test_paint_project_routes.py`;
- `apps/api/tests/unit/test_paint_project_service.py`;
- this candidate record.

Deleted: none.

The candidate changes no Migration, ORM model, database constant, state-machine contract,
dependency manifest, Lockfile or frontend source.

The approved candidate scope is now exactly 25 files: the original 24 plus
`apps/api/tests/conftest.py`. That fixture explicitly supplies valid test environment and Demo
Principal values; it does not bypass Settings validation, inject production identity, accept HTTP
identity input or implement authentication.

## Test Evidence

Backend unit suite:

- 160 passed;
- 98% combined source coverage;
- strict schemas and Principal normalization;
- explicit test Settings plus missing/blank/unknown environment, missing/blank/long Principal and
  production-rejection regressions;
- canonical payload and scope generation;
- service winner, replay, conflict, authorization, list and detail behavior;
- route validation, connection/invalidation/wait-timeout 503 classification, non-retryable
  Integrity/Programming/Data/generic SQLAlchemy 500 classification, cancellation propagation and
  stable redacted error envelopes;
- repository SQL-null insert contract, parameterized transaction-local timeout SQL and dependency
  lifecycle.

PostgreSQL integration suite:

- 29 passed: the protected readiness test, all 15 protected schema/Migration tests and 13 Phase
  1D-2 API/concurrency scenarios;
- real create writes exactly one project, one initial event and one completed idempotency row;
- normalized data and server-owned fields are persisted;
- same-key replay does not duplicate data;
- different-payload reuse returns 409 without mutation;
- owner-scoped list/detail and non-disclosing 404 are enforced;
- API process recreation reads committed data;
- a real database constraint failure rolls back all three records, the same session recovers, and
  the key can be retried successfully;
- A–I matrix uses independent AsyncSessions, explicit Event barriers or PostgreSQL-observed blocking,
  TaskGroup time bounds and exact row counts;
- same-key same-payload overlap creates once/replays once; different payload overlap produces one
  success and one stable 409 with the winner hash;
- cross-Principal same-key overlap and different-key overlap preserve independent command scopes;
- response confirmation loss occurs after a real commit and retry replays without duplication;
- a waiter confirmed blocked through `pg_stat_activity` and `pg_blocking_pids` acquires after winner
  rollback;
- existing expired records preserve concurrent replay/conflict behavior;
- a real lock waiter returns bounded safe 503 without partial writes and succeeds after winner
  release; a real statement timeout is tagged separately;
- transaction-local timeout values are visible inside the create transaction and absent from the
  following transaction;
- an actual connection failure produces the safe 503 envelope;
- temporary database ownership, overlap, 42P04 and orphan-detection regressions remain green.

Test synchronization wrappers preserve production behavior:

- `BarrierPaintProjectRepository` signals immediately before calling the real claim method;
- `SignalingPaintProjectRepository` records the real backend PID and then calls the real claim;
- the response-loss wrapper raises only after the real Service transaction has committed;
- `StatementDelayRepository` executes real PostgreSQL `pg_sleep` and would call the real claim if the
  configured statement timeout did not cancel it.

No wrapper replaces project, event or idempotency persistence with a fake result.

## Verification Evidence

- Ruff lint: passed;
- Ruff format check: passed without writing;
- strict mypy: passed for 31 source files;
- `uv lock --check`: passed;
- locked sync dry run: no change required;
- full backend: 160 unit and 29 integration tests passed;
- existing frontend: ESLint, TypeScript, 11 Vitest tests and production build passed;
- `make check`: passed;
- Alembic current/head/history/check: sole Head `a10d3d8dab38`, one Revision, no pending operation;
- development database: explicit `head -> base -> head` passed;
- final Catalog: three business tables, 37 named contract constraints, three explicit indexes, 43
  approved identifiers, maximum 62 bytes;
- final business rows: zero;
- temporary databases and owner roles: zero.

The pre-existing Starlette TestClient/httpx deprecation warning remains non-blocking. No dependency
change was authorized or made to suppress it.

## Protected Integrity and Git Boundary

The remediation protected manifest contains 93 files. Final comparison reports zero mismatches. In
particular,
the sole Migration, all three ORM models, database constants, Alembic environment, prior tests,
frontend source, `.env`, dependency manifests and Lockfiles remain byte-identical to the protected
baseline.

The approved `apps/api/tests/conftest.py` expansion changed from SHA-256
`a67ae14f1f9a59682ae50061e54cce7eec66b9f1b79de15b4f45e1842c705dc1` to
`e98f2702e0e27dae4c0804ef34a2380800a017cfd0b324e9d08c89fda29cd9a3`; its only purpose is explicit,
per-test trusted runtime configuration.

HEAD remains `2c76e5ef51e4fea726407d5cccfe409a2643d694` with eight commits. The Candidate is exactly 25 files:
the original 24 plus the approved `apps/api/tests/conftest.py` expansion. No file is staged, no new
commit, remote, tag, second Revision or unexpected candidate file exists.

## Runtime Cleanup

The PostgreSQL container was returned to the pre-task stopped state and its named Volume was
retained. Immediately before shutdown, the development database was at the sole Head, the
development and maintenance databases were present, all three business tables were empty, and the
temporary database and owner-role counts were zero. After shutdown, ports 5432, 8000 and 5173 had
no listener, and no Uvicorn, Vite or Alembic process remained.

## Remaining Risks and Open Questions

### Blocker

None.

### Major

None.

### Minor

None.

### Note

- Independent focused read-only review is still required before commit authorization.
- The configured demo Principal must remain behind protected/local access; it is not public
  authentication.
- The existing Starlette TestClient/httpx deprecation warning should be handled in a separately
  authorized dependency update.
- Phase 1D-3 must complete the frontend and browser evidence before the full vertical slice can be
  called complete.

No blocking contract question remains.

## Recommended Next Task

Perform a focused read-only Phase 1D-2 PaintProject Persistence and API review. Do not stage,
commit or begin Phase 1D-3 as part of that review.
