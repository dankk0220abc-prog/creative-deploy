# Phase 1D-1B — PaintProject Models and Migration Candidate

- Phase Status: `COMPLETE_AND_COMMITTED`
- Contract Status: `APPROVED`
- Implementation Status: `COMPLETE_AND_COMMITTED`
- Migration Status: `APPROVED_AND_COMMITTED`
- Commit Status: `COMMITTED_AS_COMMIT_8`
- Phase 1D-1A Status: `COMPLETE_AND_COMMITTED`
- Phase 1D-1B Approval: `APPROVED_FOR_COMMIT_8`
- Revision ID: `a10d3d8dab38`
- Revision Parent: `None`
- Review Date: `2026-07-26`

## Goal

Establish the first reviewable persistence schema for the PaintProject vertical slice without
implementing project creation behavior. This phase registers three SQLAlchemy 2.0 ORM models in the
single application Metadata and provides one reversible Alembic candidate for PostgreSQL.

## Scope

Implemented:

- `PaintProject`;
- `StateTransitionEvent`;
- `CommandIdempotencyRecord`;
- immutable physical-schema constants;
- explicit model registration in application and Alembic Metadata;
- one initial Migration candidate;
- Metadata, model, identifier, Migration and isolated PostgreSQL constraint tests.

This phase does not implement an API, Principal Adapter, Repository, Service, project creation
transaction, idempotency execution algorithm, initial-event business write path or frontend page.
It does not complete the vertical slice, a real product loop, production validation, repainting
validation or real-user validation. ORM, Migration and PostgreSQL Catalog consistency is only
schema evidence; it does not expand Phase 1D-1B into later application or product layers. The
focused independent review approved this bounded schema work for Commit 8.

## Contract Sources

- PaintPilot MVP Product Contract `0.1.3 APPROVED_FOR_IMPLEMENTATION`;
- PaintPilot Domain Data Dictionary `0.1.3 APPROVED_FOR_IMPLEMENTATION`;
- Workflow State Machine `0.1.1 APPROVED_FOR_IMPLEMENTATION`;
- ADR-0002 `Accepted`;
- ADR-0003 `Accepted`;
- Phase 1D Vertical Slice Plan;
- Owner implementation addenda for conditional audit fields and PostgreSQL identifier length.

## Physical Schema Matrix

| Table | Columns | Primary purpose |
| --- | ---: | --- |
| `paint_projects` | 9 | Initial aggregate identity, ownership, user text, creation intent, status and timestamps |
| `state_transition_events` | 12 | Authoritative state-transition audit facts |
| `command_idempotency_records` | 13 | Future transactional command replay boundary |

All identifiers use PostgreSQL UUID, JSON structures use JSONB, and timestamps are timezone-aware.
UUID primary keys use Python `uuid.uuid4`; there is no UUID extension or deterministic ID derivation.

## ORM Models

All three models inherit the existing unique `creativedeploy_api.db.Base` and use `Mapped` plus
`mapped_column`. Model import creates no Settings, Engine, Session or database connection.
`REGISTERED_MODELS` explicitly contains exactly the three approved models; neither package scanning
nor dynamic plugin loading is used.

## Deferred Fields

- `current_image_asset_id`;
- `current_region_version_id`;
- `current_plan_id`;
- `agent_run_id`.

These fields arrive only with their future target tables and real Foreign Keys. No placeholder UUID,
relationship or fake target table was introduced.

## Constraint Matrix

| Area | Implemented database protection |
| --- | --- |
| PaintProject text | Owner, Title and optional Description normalization; `VARCHAR` bounds |
| Creation intent | Machine-token format plus current style and planning-mode allowlists |
| Workflow state | Full 16-state allowlist; `DRAFT` remains only the creation default |
| Project time | `updated_at >= created_at` |
| State event | State allowlists, event/actor/reason token formats, actor allowlist and project FK |
| Conditional display snapshot | Nullable globally; normalized when present; required for `actor_type=user` |
| Conditional reason | Nullable globally; `create_project` requires non-null `project_created` |
| Event metadata | Non-null JSONB object with `{}` server default |
| Idempotency | Normalized scope/Principal, payload hash, execution status and unique scope/key |
| Completed result | Completed rows require resource type/ID, HTTP status and response object |
| Idempotency time | `expires_at > created_at` |

The initial task incorrectly made the two audit fields globally non-null. The contract gate stopped
before coding. The Owner retained the approved conditional contract, and the implementation uses
nullable columns plus current-event conditional Checks. No placeholder display name or reason is
stored for missing semantics.

## Index Matrix

| Index | Ordered columns |
| --- | --- |
| `ix_paint_projects_owner_updated_at_id` | `owner_principal_id, updated_at, id` |
| `ix_state_transition_events_project_created_at_id` | `project_id, created_at, id` |
| `ix_command_idempotency_records_expires_at` | `expires_at` |

No JSONB GIN or JSON path Index was created.

## Model Registration

`creativedeploy_api.db.models` explicitly imports and exports the three model classes. Alembic
imports `REGISTERED_MODELS` before binding `target_metadata`, which remains identical to
`Base.metadata`. The formal Metadata contains exactly the three business tables.

## Revision ID

- Revision: `a10d3d8dab38`
- Parent: `None`
- Heads: one
- Revisions: one
- Candidate committed: yes, as Commit 8
- Commit: `2c76e5ef51e4fea726407d5cccfe409a2643d694`
- Commit subject: `feat(api): add PaintProject persistence foundation`

## Autogenerate Output

Before generation, the development database was at base with no Revision. `alembic check` returned
non-zero and detected exactly three new tables and their three indexes. The authorized autogenerate
command was executed once. No Revision was deleted, regenerated or supplemented with a second
Revision.

## Manual Migration Corrections

The candidate was reviewed and directly corrected before commit:

1. reordered upgrade to PaintProject, StateTransitionEvent and CommandIdempotencyRecord, with reverse
   downgrade order;
2. retained every named Check, Foreign Key, Unique constraint and Index;
3. corrected SQLAlchemy textual parsing that rendered canonical `?:` as `?NULL`;
4. used the PostgreSQL-compatible equivalent machine-token expression
   `^[a-z][a-z0-9]*(_[a-z0-9]+)*$`;
5. made the `create_project` reason Check explicitly null-safe under SQL three-valued logic;
6. changed the 65-byte display-snapshot constraint name to the Owner-approved 60-byte
   `ck_state_transition_events_actor_display_snapshot_normalized`.

The Migration remains self-contained and imports no application model, constant, Settings or
database configuration.

## PostgreSQL Identifier Correction

The first Catalog review found that
`ck_state_transition_events_actor_display_name_snapshot_normalized` is 65 ASCII bytes. PostgreSQL
supports at most 63 bytes and SQLAlchemy deterministically compiled the name with an `_8ef7` suffix.
This was framework truncation, not database damage, but it did not satisfy the explicit naming
policy. Implementation stopped safely, the Owner approved
`ck_state_transition_events_actor_display_snapshot_normalized`, and the then-uncommitted Candidate
was revised without creating a second Revision.

The final Metadata audit covers 43 tables/constraints/indexes. Every identifier is lowercase ASCII,
uses only letters, digits and underscores, and is at most 63 UTF-8 bytes. The maximum is 62 bytes.
The final Catalog exactly matches all 43 ORM/Migration identifiers and contains no auto-truncated
name.

## Pre-generation Check

- Database state: base;
- heads/history: empty;
- result: non-zero as required;
- detected: exactly the three approved tables and their indexes;
- Secret or database URL output: none.

## Post-generation Check

At base, Alembic first correctly reported that the target database was not up to date. After explicit
upgrade to the sole Head, `alembic check` reported `No new upgrade operations detected.` This is the
expected distinction between database revision state and Metadata drift.

## Upgrade Evidence

Upgrade from base created:

- `alembic_version`;
- `paint_projects`;
- `state_transition_events`;
- `command_idempotency_records`.

The sole Revision row is `a10d3d8dab38`, all three business tables contain zero rows, Catalog names
exactly match Metadata, and no PostgreSQL Enum type or extra business object exists.

## Downgrade Evidence

Downgrade to base removed all three business tables, their indexes and their constraints. Public
schema retained only an empty `alembic_version`; no business Index or PostgreSQL Enum remained.

## Re-upgrade Evidence

Re-upgrade restored the same sole Head and the same empty three-table schema. The final development
database remains at `a10d3d8dab38`, and `alembic check` reports no pending operation.

## Temporary Database Test Strategy

The Migration integration test derives connection coordinates from the existing SecretStr-backed
development configuration without printing the URL. It creates a random
`creativedeploy_migration_test_<safe_hex>` database and a separate random
`creativedeploy_migration_owner_<safe_hex>` role. The role uses an independent strict name regex.
The fixture verifies that the role is absent, then creates it as `NOLOGIN` and writes a unique
ownership token to its role comment in the same PostgreSQL transaction. A collision or an
unconfirmed marker refuses the claim and prevents database creation.

Database creation is one autocommit `CREATE DATABASE ... OWNER ...` statement with both identifiers
quoted by `psycopg.sql.Identifier`; PostgreSQL therefore binds the database owner atomically at
creation. A database name, absence precheck, attempted CREATE or current existence is never treated
as ownership. Destructive cleanup requires the safe database and role names, an exact role token,
`NOLOGIN`, the current `pg_database.datdba` role, and no explicit 42P04 result. Those facts are
rechecked before connection termination and again before DROP. Connection termination uses the same
Catalog predicates in its SQL statement. DROP executes under `SET ROLE` for the ephemeral owner, so
PostgreSQL also rejects the statement if current ownership changes at execution time. The role is
dropped only after database cleanup, after its marker is rechecked, without `DROP OWNED` or
`CASCADE`.

The earlier cleanup-candidate-before-CREATE design did close the uncertain-success residual window,
but independent red-team testing found a TOCTOU race: another connection could create the checked
name, make the fixture receive 42P04, and then have its database and connection destroyed by
teardown. The current fixture records 42P04 as a definite non-claim and performs no destructive
database cleanup on that path, while still removing its own unused owner role when safe.

After that ownership remediation, an independent overlapping-fixture probe found a separate false
failure: Fixture A correctly removed its own database and role, but its teardown then applied a
server-global prefix count while Fixture B was still valid and active. A therefore failed even
though both fixtures ultimately cleaned up to zero resources.

Per-fixture exact cleanup and global hygiene are now separate contracts. Resource teardown validates
only its exact database name, exact owner role, exact ownership marker and exact database
connections, plus continued existence of the development and maintenance databases. It does not
require every temporary prefix to be absent and cannot classify another active fixture as an
orphan. The global hygiene audit remains detection-only: it reports database and role residual
counts separately with safe resource names, never emits the ownership token or database URL, and
never drops a residual.

The repository has no pytest-xdist dependency or loaded plugin, no pytest worker option and no
parallel integration Make target. A module-scoped lifecycle gate can therefore audit once before
module resources start and once after all module fixture teardowns finish, independently of test
names and collection order. Explicit audit regression calls also occur only before a resource is
created or after all resources in that scenario have exited.

Dedicated real-PostgreSQL regressions cover normal success, definite failure before database
creation, actual server-side creation followed by synthetic confirmation loss, pre-existing
database protection, the real concurrent 42P04 race through fixture control flow, missing and
mismatched ownership markers, owner change before DROP, and pre-existing role collision. A new
two-resource regression proves both databases, roles and distinct markers coexist; Fixture A exits
without error while Fixture B's same live backend connection remains usable; Fixture B then exits
and the global audit observes zero database and role residuals. A separate test creates a real
marked orphan database and role, proves the audit fails without deleting either resource, performs
ownership-proven exact cleanup in `finally`, and proves the next audit passes. The development
public schema is never reset.

## Constraint Test Evidence

The isolated PostgreSQL test verifies:

- valid and invalid PaintProject text, enum, state and timestamp boundaries;
- all 16 approved workflow states from an independent test-local tuple, plus exact rejection of the
  unknown seventeenth state;
- valid initial `null -> DRAFT` `create_project` audit event;
- exact 200-character Unicode display snapshot acceptance, 201-character rejection, optional
  non-user snapshot, required user snapshot and normalization failures;
- required `project_created` creation reason, optional non-create reason, valid reason token and
  invalid reason boundaries;
- event metadata object acceptance and rejection of array, string, number, boolean and JSON null;
- project Foreign Key enforcement;
- machine-token and exact `VARCHAR` upper boundaries;
- payload hash acceptance at 64 lowercase hexadecimal characters, Check violations at 63,
  uppercase and non-hex input, and SQLSTATE `22001` at 65 characters;
- completed and in-progress idempotency rows;
- HTTP status acceptance at 100 and 599 and exact Check violations at 99 and 600;
- scope/key uniqueness, result completeness, response object and expiration constraints;
- expected SQLSTATE and exact constraint identity for every Check, Foreign Key and Unique rejection,
  plus SQLSTATE `22001` with no fabricated constraint name for `VARCHAR` overflow;
- rollback after every expected database rejection.

The round-trip test passes and leaves no temporary database or ephemeral owner role.

## Focused Review Finding Closure

| Finding | Closure evidence | Status |
| --- | --- | --- |
| F-01 | Tests define independent immutable Python/PostgreSQL regex contracts and a complete 43-identifier contract, then compare production constants, ORM Metadata and Migration source separately against those test-local values. | `CLOSED` |
| F-02 | Integration rejection helpers assert case label, SQLSTATE and exact database constraint name, roll back the failing transaction/savepoint and prove the same connection remains usable. | `CLOSED` |
| F-03 | Owner-role proof closed the 42P04 TOCTOU deletion race, after which an independent overlap probe found per-fixture server-global zero counts falsely rejected a still-active peer fixture. Teardown now verifies only the fixture's exact database, owner role, marker and connections; a separate module lifecycle gate performs detection-only global audits when no valid module fixture is active. Real PostgreSQL regressions prove A exits while B and its same connection remain usable, both later reach zero residuals, and a real marked orphan is detected without auto-deleting it. Existing 42P04, marker, owner-change, role-collision, uncertain-success, definite-failure and pre-existing-resource protections remain covered. | `CLOSED` |
| F-04 | Independent database boundaries cover all 16 states and approved edge values; the ORM regression invokes the JSON object default twice and proves mutation isolation. | `CLOSED` |
| F-05 | Both progress documents explicitly distinguish approved Contract, implemented-but-unapproved Phase 1D-1B, Candidate Migration and the uncreated eighth Commit without claiming product completion. | `CLOSED` |

The focused F-03 lifecycle run passed 12 cases, and the complete Migration integration module passed
all 15 cases. The implementation rerun also passed 74 backend unit tests at 97% coverage, all 16
integration tests, Ruff, format check, strict mypy, uv lock checks, all frontend checks and
`make check`. The development database completed `head -> base -> head`; final Catalog evidence was
three tables, 37 named contract constraints, three explicit indexes, 43 approved identifiers,
maximum 62 bytes, empty business tables and zero temporary databases/roles. The focused independent review closed
F-01 through F-05 and authorized Commit 8. Commit
`2c76e5ef51e4fea726407d5cccfe409a2643d694` is now the protected baseline for the next phase.

## Security Boundary

- no database URL, credential or Secret is stored in the Revision or test output;
- no real email or personal data is used;
- JSON audit/response fields contain only controlled test structures;
- no Seed, extension, trigger, function, view, RLS or automatic application-start migration exists;
- `.env`, dependency manifests and Lockfiles remain unchanged.

## Known Limitations

Phase 1D-1B intentionally delivered schema only; it did not itself make PaintProject creation
usable. Phase 1D-2 now has an uncommitted Principal/Repository/Service/API candidate, while the
frontend remains deferred. Future event/reason pairing beyond the approved `create_project` case
remains a service-contract and later-Migration concern.

## Remaining Risks

- the approved historical Migration and ORM models must remain immutable during Phase 1D-2;
- Phase 1D-2 service/API behavior requires its own focused read-only review;
- future event contracts may require additional conditional database constraints;
- schema approval does not imply frontend or integrated product completion.

## Next Task

Perform the focused read-only Phase 1D-2 PaintProject persistence/API review. Do not start Phase
1D-3 frontend implementation until that candidate is independently approved.
