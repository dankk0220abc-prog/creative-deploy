# ADR-0003: Physical Identifiers and State Event Boundary

- Status: `Accepted`
- Date: `2026-07-26`
- Accepted Date: `2026-07-26`
- Decision Owners: `Project Owner / System Architect`
- Implementation Status: `NOT_STARTED`
- Product Contract Amendment: `0.1.3 APPROVED_FOR_IMPLEMENTATION`
- Data Dictionary Amendment: `0.1.3 APPROVED_FOR_IMPLEMENTATION`
- Supersedes: No prior ADR; narrows the physical implementation boundary of ADR-0002

This ADR accepts the physical string limits and first-persistence boundary required for
Phase 1D-1B to implement PaintProject ORM models and the first business Migration. Accepted means
the decision is approved; it does not mean ORM models, a Migration Revision or business tables have
been implemented.

## Context

Phase 1D-1A established the shared SQLAlchemy Metadata and async Alembic foundation without business
entities or revisions. Phase 1D-1B then stopped during contract review because the approved documents
did not define physical maximum lengths for Principal identifiers, command scopes and several audit
tokens. The StateTransitionEvent definition also used a generic `metadata` name that conflicts with
SQLAlchemy's `Base.metadata`, while its logical `agent_run_id` referenced a table that does not yet
exist.

Choosing arbitrary `VARCHAR` limits, renaming an audit field only in code, or creating a naked UUID
would make the first Migration depend on undocumented implementation guesses. The contract therefore
needs an explicit, narrow amendment before implementation resumes.

## Decision

1. Define one logical `PrincipalId` Value Type. Its PostgreSQL representation is `VARCHAR(128)`.
   Values are trimmed, contain 1–128 Unicode characters and are stable opaque internal identifiers.
2. Do not use email or display name as PrincipalId. A future external authentication subject must be
   mapped to PrincipalId by a Principal Adapter; this decision does not create a Principal table.
3. Use `VARCHAR(512)` for server-generated `scope_key`.
4. Use `VARCHAR(64)` for `command_type`, `event` and `resource_type`.
5. Use `VARCHAR(128)` for controlled `reason` codes.
6. Use `VARCHAR(200)` for the human-readable `actor_display_name_snapshot`.
7. Rename StateTransitionEvent's generic `metadata` field to `event_metadata` in both the logical
   contract and future ORM/database column.
8. Persist `event_metadata` as non-null PostgreSQL JSONB with server default `{}` and a named Check
   Constraint requiring a JSON object.
9. Keep `event_metadata` limited to Event Contract-approved, non-sensitive structured audit
   supplements. It is not an arbitrary context store and cannot replace first-class domain fields.
10. Keep `agent_run_id` as a nullable logical StateTransitionEvent field but defer its physical
    column until the `agent_runs` table exists.
11. When introduced, `agent_run_id` must be UUID with a real Foreign Key to `agent_runs.id`, use
    `NO ACTION / RESTRICT` unless a future approved contract changes it, and backfill existing rows
    with `null`.
12. Do not create a naked future-resource UUID, a placeholder `agent_runs` table, or an ORM
    relationship before the referenced table exists.
13. Freeze the first Phase 1D-1B `state_transition_events` table at exactly 12 physical columns:
    `id`, `project_id`, `from_state`, `to_state`, `event`, `actor_type`,
    `actor_principal_id`, `actor_display_name_snapshot`, `reason`, `correlation_id`,
    `event_metadata` and `created_at`.
14. Preserve the existing Create Project transaction and idempotency semantics, Rights Attestation
    phase boundary, 16 workflow states, 47 transitions and 17 numbered Guards.
15. Keep `reason` as a lowercase snake_case machine reason code. A future human explanation requires
    a separately approved field rather than overloading `reason`.
16. Apply canonical syntax `^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$` to `command_type`, `event`,
    `reason`, `resource_type`, `actor_type`, `execution_status`, `requested_target_style` and
    `planning_mode`. Length, format and allowed-values constraints remain independent and cumulative.

All string lengths count Unicode characters at the API and product-contract level. PostgreSQL uses
`VARCHAR(n)`, and future Pydantic validation must enforce the same upper limits.

## Physical Type Matrix

### `paint_projects`

| Column | PostgreSQL type | Boundary |
| --- | --- | --- |
| `owner_principal_id` | `VARCHAR(128)` | Non-null PrincipalId; trim; 1–128 |
| `title` | `VARCHAR(80)` | Non-null; trim; 1–80 |
| `description` | `VARCHAR(500)` | Nullable; trim when present |
| `requested_target_style` | `VARCHAR(32)` | Non-null; currently `cel_shading` |
| `planning_mode` | `VARCHAR(32)` | Non-null; currently `planning_only_demo` |
| `status` | `VARCHAR(64)` | Non-null; all 16 approved states |

### `state_transition_events`

| Column | PostgreSQL type | Boundary |
| --- | --- | --- |
| `from_state` | `VARCHAR(64)` | Nullable; approved workflow state when present |
| `to_state` | `VARCHAR(64)` | Non-null approved workflow state |
| `event` | `VARCHAR(64)` | Lowercase snake_case controlled token; 1–64 |
| `actor_type` | `VARCHAR(32)` | Controlled `user/api/worker/system` token |
| `actor_principal_id` | `VARCHAR(128)` | Non-null PrincipalId; trim; 1–128 |
| `actor_display_name_snapshot` | `VARCHAR(200)` | Conditional; Unicode; trim; 1–200 |
| `reason` | `VARCHAR(128)` | Conditional lowercase snake_case reason code; 1–128 |
| `event_metadata` | `JSONB` | Non-null object; server default `{}` |

The remaining first-table columns are UUID `id`, UUID Foreign Key `project_id`, UUID
`correlation_id` and timezone-aware `created_at`. `agent_run_id` is not a Phase 1D-1B physical
column.

### `command_idempotency_records`

| Column | PostgreSQL type | Boundary |
| --- | --- | --- |
| `scope_key` | `VARCHAR(512)` | Non-null; server-generated; trim; 1–512 |
| `principal_id` | `VARCHAR(128)` | Non-null PrincipalId; trim; 1–128 |
| `command_type` | `VARCHAR(64)` | Lowercase snake_case controlled token; 1–64 |
| `payload_hash` | `VARCHAR(64)` | Exactly 64 lowercase SHA-256 hex characters |
| `execution_status` | `VARCHAR(32)` | `in_progress/completed` |
| `resource_type` | `VARCHAR(64)` | Nullable until completed; controlled token |

The remaining columns retain their approved physical families: UUID `id`, UUID
`idempotency_key`, nullable UUID `resource_id`, integer `http_status`, JSONB
`response_snapshot`, and timezone-aware `created_at` and `expires_at`.

Canonical lowercase machine-token syntax is:

`^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$`

It applies to `requested_target_style`, `planning_mode`, `event`, `actor_type`, `reason`,
`command_type`, `execution_status` and `resource_type`. A token begins with a lowercase ASCII
letter; later segments contain lowercase ASCII letters or digits and are separated by one
underscore. Uppercase letters, spaces, hyphens, consecutive underscores and trailing underscores
are rejected. The format Check does not replace approved-value allowlists.

`status`, `from_state` and `to_state` store the 16 approved uppercase Workflow States and do not use
the lowercase regular expression. Their names, count and case remain unchanged.

PrincipalId, `scope_key`, `title`, `description`, `actor_display_name_snapshot`, `payload_hash`,
UUID and JSONB fields do not use the machine-token expression. `payload_hash` independently uses
`^[0-9a-f]{64}$`; PrincipalId intentionally has no restrictive character expression; `scope_key`
uses its server-side structural format.

## Event Metadata Contract

`event_metadata` may contain only keys explicitly approved by the relevant Event Contract and values
that are non-sensitive, serializable, machine-readable and necessary to reconstruct audit meaning.
The `create_project` event requires no supplement and stores `{}`.

The following are prohibited:

- raw request or response bodies;
- Authorization headers, cookies, credentials, DATABASE_URL values or other secrets;
- stack traces or raw exception objects;
- model prompts or complete model output;
- image binaries or arbitrary file contents;
- unversioned free-text context;
- core business fields placed in JSON to avoid proper modeling.

Phase 1D-1B creates no GIN Index, JSON path Index, metadata query API or full-text search for this
column. The stable object constraint is
`ck_state_transition_events_event_metadata_is_object`.

## Alternatives Considered

### A. Use `VARCHAR(255)` for every string

Rejected. A uniform default hides distinct domain semantics, wastes the opportunity to express
known boundaries and still does not safely accommodate the approved structured `scope_key`.

### B. Use PostgreSQL `TEXT` and validate only in the application

Rejected. Database writes outside the future API could bypass product limits, and the Migration
would fail to encode the reviewed contract.

### C. Create a Principal table now

Rejected. PrincipalContext remains a non-persistent Value Object. Phase 1D only needs stable internal
identifiers and does not yet require accounts, registration, tenants, ownership transfer or RBAC.

### D. Keep the generic `metadata` name

Rejected. It collides conceptually and operationally with SQLAlchemy Declarative
`Base.metadata` and obscures that the field belongs specifically to event auditing.

### E. Delete event metadata entirely

Rejected. Later approved event types may require small, versioned structured supplements that do not
belong as universal first-class columns. Removing the field would force a later avoidable schema
addition or overload a text field.

### F. Create `agent_run_id` now without a Foreign Key

Rejected. A bare UUID cannot guarantee referential integrity and violates the rule that future
resource references arrive with their target table and real Foreign Key.

### G. Create the AgentRun table early

Rejected. AgentRun persistence is outside Phase 1D-1B and would expand the first Migration into AI
execution, retry and cancellation concerns that are not needed for Create Project.

## Consequences

### Positive

- Phase 1D-1B can implement every string column without inventing a length.
- Principal attribution uses one consistent physical boundary across the three initial tables and
  future Principal-linked entities.
- The StateTransitionEvent ORM can use `event_metadata` without conflicting with
  `Base.metadata`.
- The first event table supports the complete Create Project audit event without premature
  AgentRun persistence.
- Database constraints can test exact length and JSON object boundaries.

### Negative / Trade-offs

- Future token growth beyond the approved limits requires a reviewed contract and Migration.
- `event_metadata` needs per-event schemas before non-empty objects are introduced.
- Events created before AgentRun persistence cannot reference a run; this is acceptable because the
  current Create Project flow has no AgentRun.
- Adding `agent_run_id` later requires a separate nullable-column Migration and relationship update.

## Security Considerations

- PrincipalId is non-secret but must be logged only when operationally necessary.
- `scope_key` is server-generated and cannot contain secrets or raw request bodies.
- Display snapshots are sensitive historical data and never participate in authorization.
- Machine token fields cannot accept user-facing prose.
- `event_metadata` rejects credentials, infrastructure locations, raw errors, request/response
  bodies, model content, binaries and arbitrary files.
- This decision does not weaken owner isolation or permit anonymous public writes.

## Migration Consequences

If approved, the first Phase 1D-1B Migration must:

1. create exactly `paint_projects`, `state_transition_events` and
   `command_idempotency_records`;
2. use the exact physical types and nullability in this ADR and the Data Dictionary;
3. create the 12-column StateTransitionEvent table with `event_metadata` and without
   `agent_run_id`;
4. add a non-null JSONB server default `{}` plus
   `ck_state_transition_events_event_metadata_is_object`;
5. create no Principal, AgentRun, User, Workspace or Tenant table;
6. create no naked future-resource UUID or event JSON Index;
7. test lower, exact-upper and over-limit boundaries for every Phase 1D string class;
8. test canonical machine-token syntax separately from each approved-value allowlist and test
   `payload_hash` against `^[0-9a-f]{64}$`;
9. test that JSON objects are accepted and array, string, number, boolean and JSON null are
   rejected;
10. preserve valid downgrade and re-upgrade behavior.

This ADR itself creates no Migration or database object. Phase 1D-1B is
`READY_FOR_IMPLEMENTATION / NOT_STARTED`.

## Revisit Triggers

- a real authentication Adapter requires a stable internal identifier longer than 128 characters;
- a reviewed command scope cannot fit within 512 characters;
- a new machine token or reason code exceeds its approved bound;
- audit display snapshots need a product-approved localization or retention change;
- a non-empty event metadata schema is proposed;
- AgentRun persistence is authorized and `agent_run_id` can be introduced with a real Foreign Key;
- a future event requires database-queryable data that should be promoted from JSONB to a first-class
  column;
- compliance or audit policy requires stricter deletion, encryption or retention controls.
