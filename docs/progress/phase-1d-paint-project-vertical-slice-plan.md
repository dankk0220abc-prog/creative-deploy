# Phase 1D — PaintProject Vertical Slice Implementation Plan

- Phase Status: `IN_PROGRESS`
- Approval Date: `2026-07-24`
- Implementation Status: Phase 1D-3 is implemented and awaiting final independent review
- Migration Status: `APPROVED_AND_COMMITTED`
- Contract Status: `APPROVED`
- Commit Status: Commit 9 is historical baseline; Commit 10 has not been created
- Plan Status: `APPROVED`
- Unblocked Date: `2026-07-26`
- Product: `CreativeDeploy / PaintPilot`
- Planned Routes: `/paintpilot/projects`, `/paintpilot/projects/new`,
  `/paintpilot/projects/:projectId`
- Product Contract: `0.1.3 APPROVED_FOR_IMPLEMENTATION`
- Data Dictionary: `0.1.3 APPROVED_FOR_IMPLEMENTATION`
- Decision Records: `ADR-0002 Accepted`; `ADR-0003 Accepted`

本文档已获准用于拆分 Phase 1D 实现任务。Phase 1D-1B 的三个 ORM Model、唯一
Migration 和数据库测试已经独立复审、批准并作为 Commit 8
`2c76e5ef51e4fea726407d5cccfe409a2643d694` 提交；F-01 至 F-05 均已关闭。Phase
1D-2 的 Principal Adapter、AsyncSession 边界、Repository、Service、创建幂等事务和
create/list/detail API 已通过最终独立复审并作为 Commit 9
`6d2c3d8001c3737e2e441ee1c0df4179660f0c57` 提交；F-09-01 至 F-09-04 均已关闭。
Phase 1D-3 的 React Router、Projects/Create/Detail 页面和真实浏览器闭环现已实现为
未提交候选；2026-07-27 最大安全修复批次已在允许文件内完成严格响应边界、路由级
无障碍和真实浏览器键盘/409 三项 MAJOR 的技术修复，状态以本计划中的精确治理字段为准，
仍等待聚焦只读复审。本实施记录只陈述候选证据，不构成对 Phase 1D-3 的独立批准或 Commit 10。

## Implementation Progress

- Phase 1D-1A — Database Metadata and Alembic Foundation: `COMPLETE_AND_COMMITTED`
- Phase 1D-1B — PaintProject ORM Models and First Migration Candidate:
  `COMPLETE_AND_COMMITTED`
- Phase 1D-1B Implementation: `COMPLETE_AND_COMMITTED`
- Phase 1D-1B Approval: `APPROVED_FOR_COMMIT_8`
- Phase 1D-1B Commit:
  `2c76e5ef51e4fea726407d5cccfe409a2643d694 — feat(api): add PaintProject persistence foundation`
- Phase 1D-1B Findings: `F-01 THROUGH F-05 CLOSED`
- Phase 1D-1B F-03 Ownership Proof: each fixture transactionally claims a unique `NOLOGIN` role
  with a unique comment token, then uses `CREATE DATABASE ... OWNER ...`; 42P04 never acquires
  ownership, and teardown revalidates the role token, `NOLOGIN` state and current database owner
  before any connection termination or DROP.
- Phase 1D-1B F-03 Cleanup Separation: a fixture teardown verifies only its exact database, owner
  role, ownership marker and connections while preserving the development and maintenance
  databases; it never requires other valid fixture resources or all test prefixes to be absent.
- Phase 1D-1B F-03 Global Hygiene Gate: the current repository has no pytest-xdist dependency,
  worker option or parallel integration command, so a module lifecycle gate performs prefix-wide
  zero-residual audits only before any module fixture and after all module fixtures have exited,
  without relying on test-name or collection order.
- Phase 1D-1B F-03 Race Evidence: real PostgreSQL regressions preserve the concurrent actor database
  and live actor connection after 42P04, prove Fixture A can cleanly exit while Fixture B and its
  connection remain active, detect a real marked orphan without auto-deleting it, retain resources
  when ownership proof changes, and safely recover uncertain success belonging to the fixture.
- Phase 1D-1B F-03 Verification: 12 focused lifecycle/ownership cases, the complete 15-case
  Migration integration module, 74 backend unit tests at 97% coverage, all 16 integration tests,
  Ruff, format check, strict mypy, uv lock checks, all frontend checks and `make check` passed.
  The development database completed `head -> base -> head`; final Catalog evidence remains three
  tables, 37 named contract constraints, three explicit indexes, 43 approved identifiers, maximum
  62 bytes, empty business tables and zero temporary databases/roles.
- Phase 1D-1B Unblocked Date: `2026-07-26`
- Phase 1D-2 — PaintProject Persistence and API: `COMPLETE_AND_COMMITTED`
- Phase 1D-2 Approval: `APPROVED_FOR_COMMIT_9`
- Phase 1D-2 Commit:
  `6d2c3d8001c3737e2e441ee1c0df4179660f0c57 — feat(api): add PaintProject persistence and API`
- Phase 1D-2 F-09-01 Demo Principal fail-closed:
  `CLOSED`
- Phase 1D-2 F-09-02 finite PostgreSQL wait policy:
  `CLOSED`
- Phase 1D-2 F-09-03 SQLAlchemy error classification:
  `CLOSED`
- Phase 1D-2 F-09-04 deterministic concurrency matrix:
  `CLOSED`
- Phase 1D-2 Verification: 160 backend unit tests at 98% coverage, all 30 PostgreSQL integration
  tests, Ruff, format check, strict mypy, uv lock checks, all existing frontend checks and
  `make check` passed. The development database completed `head -> base -> head`; the sole Revision
  remains `a10d3d8dab38`, all business tables are empty, and no temporary database or role remains.
- Phase 1D-3: `IMPLEMENTED_PENDING_REVIEW`
- Phase 1D-3 Approval: `NOT_APPROVED`
- Commit 10: `NOT_CREATED`
- MAJOR-01: `REMEDIATED_AWAITING_FINAL_INDEPENDENT_REVIEW`
- MAJOR-02: `REMEDIATED_AWAITING_FINAL_INDEPENDENT_REVIEW`
- MAJOR-03: `REMEDIATED_AWAITING_FINAL_INDEPENDENT_REVIEW`
- Phase 1D-3 Verification: 89 frontend tests across API client, route, list, create, detail and
  accessibility behavior; ESLint, strict TypeScript, frozen pnpm install, Vite production build
  and preview, uv locked verification, 160 backend unit tests at 98% coverage, all 30 PostgreSQL
  integration tests and full repository `make check`.
- Browser evidence: `IMPLEMENTED_AWAITING_FINAL_INDEPENDENT_REVIEW`
- Phase 1D-3 Real Browser Verification: system-Chrome skip-link probe; mouse-free create journey;
  five-Enter suppression; real 409 recovery; same-key confirmation-loss/transport/502/503/504
  recovery; changed-payload new-key recovery; direct detail, reload and back/forward; invalid UUID,
  project 404 and unknown route; 21-row pagination focus; and 1440, 768 and 390×844 responsive
  checks. Critical success paths had zero console errors, warnings and unhandled page errors.
- Phase 1D-3 Database Verification: development database completed `head -> base -> head`; final
  Catalog is revision `a10d3d8dab38`, three business tables, 37 constraints and three explicit
  indexes; business rows and temporary database/role residuals are `0/0/0` and `0/0`.
- Phase 1D-4 — Integrated Product Review: `NOT_STARTED`

Phase 1D-1A establishes only shared empty SQLAlchemy Metadata and Migration tooling. It does not
create an ORM entity, business Revision, database table, API or frontend page. Phase 1D-0C only
clarified contracts before implementation. Phase 1D-1B and Phase 1D-2 are approved and committed.
Phase 1D-3 now contains the implemented, uncommitted frontend candidate. It proves the local
database-backed create/list/detail browser loop, failure recovery, restart persistence and
responsive baseline, but it does not constitute independent Phase 1D-3 approval, Commit 10,
Integrated Product Review, production validation or real-user validation.

## 1. Objective

交付第一个真实、数据库支持的 PaintProject 纵向切片：

1. 用户在 Create Paint Project 页面提交有效 Title 和可选 Description；
2. 服务端从 PrincipalContext 写入 Owner，并确定性写入当前风格、能力边界和初始状态；
3. PaintProject、初始状态事件和幂等记录在同一事务中持久化；
4. 创建成功后进入真实详情页；
5. Projects 列表可以重新打开该项目；
6. 页面刷新以及 API 进程重启后，项目仍可从 PostgreSQL 读取。

“可创建、可保存、可列出、可重新打开”必须形成真实闭环。内存对象、fixture、localStorage
和虚构项目不能替代数据库事实。

## 2. Scope

### 2.1 In Scope

- Alembic 初始化和首个业务 Migration；
- SQLAlchemy 2.x async ORM / Core 映射和 AsyncSession 生命周期；
- `PaintProject`、`StateTransitionEvent` 和 `CommandIdempotencyRecord` 的最小合同实现；
- 配置型 `configured_demo_operator` Principal Adapter；
- 创建、列出和读取单个 PaintProject 的 API；
- React Router Declarative Mode 和三个 PaintPilot application routes；
- Projects Empty / Active / Failure 状态；
- Create Project 的真实验证、提交、恢复和未保存更改保护；
- 第一版只读 Project Detail；
- backend unit / integration tests、frontend tests 和浏览器 smoke review；
- 真实持久化、Owner 隔离、事务回滚和幂等行为的证据。

### 2.2 Out of Scope

- Update Project、Delete Project 和 Owner transfer；
- Image Upload、Image Quality、AI、RAG、Polygon、AgentRun、HumanApproval 和 PaintPlan；
- 公共注册、完整认证、Workspace、多租户和成员邀请；
- 后台队列和幂等记录自动清理 worker；
- Playwright E2E；
- 完整 Product Entry 粒子和滚动叙事；
- 用假数据或 disabled 功能墙模拟未来能力。

## 3. Frozen Create Project Contract

用户可编辑的请求字段：

| Field | Rule | Request representation |
| --- | --- | --- |
| `title` | Required; trim; `1–80` Unicode code points | Trimmed string |
| `description` | Optional; trim; maximum `500`; empty becomes `null` | String or `null` |

服务端确定的字段：

| Field | Phase 1D value | Authority |
| --- | --- | --- |
| `owner_principal_id` | Current stable Principal ID | PrincipalContext |
| `requested_target_style` | `cel_shading` | Program |
| `planning_mode` | `planning_only_demo` | Program |
| `status` | `DRAFT` | Program / state contract |
| `id`, timestamps | Generated values | Program / database |

Target Style 在 UI 中只显示 `Cel Shading · Current release`。Planning Mode 只显示
planning-only capability note。两者都不是选择控件，也不能由客户端覆盖。

## 4. Versioned Contract Alignment Gate

Phase 1D-0C records the approved physical-field alignment in Product Contract 0.1.3, Data Dictionary
0.1.3 and accepted ADR-0003, while ADR-0002 remains accepted:

| Topic | Aligned draft contract |
| --- | --- |
| Title | Trim; `1–80` Unicode code points in API and database |
| Description | Trim; empty becomes `null`; maximum `500` |
| Initial style | `PaintProject.requested_target_style=cel_shading` |
| Detailed style | Current user-confirmed `StyleConfiguration` is authoritative once created |
| Planning boundary | `PaintProject.planning_mode=planning_only_demo` |
| Create idempotency | Server-computed scope_key; no project ID in create scope |
| Initial audit | `null → DRAFT` StateTransitionEvent in the create transaction |
| Ownership | configured human Principal; non-Owner detail returns 404 |
| PrincipalId | Stable internal identifier; `VARCHAR(128)`; trim; 1–128 |
| Physical strings | Explicit Phase 1D `VARCHAR(n)` matrix |
| Event metadata | `event_metadata` JSONB object; no arbitrary/uncontracted content |
| AgentRun reference | Logical `agent_run_id` retained; physical column deferred with real FK |

Rights Attestation remains attached to each ImageAsset and is not part of Create Project. The 16
states, 47 Transitions, 17 numbered Guards, Golden Case art rules and planning-only validation
boundary are unchanged.

The 0.1.3 alignment is approved. Phase 1D-1B ORM and Migration implementation is
`COMPLETE_AND_COMMITTED`, and its sole Revision `a10d3d8dab38` is approved historical schema.
Earlier Phase 1D-1B implementation instructions are obsolete and are not contract sources. The
Phase 1D-2 backend candidate uses Product Contract 0.1.3, Data Dictionary 0.1.3 and ADR-0003 and
does not modify that Revision, its ORM models or its frozen constants.

## 5. Database Plan

### 5.1 `paint_projects`

The first `paint_projects` Migration contains exactly these nine physical columns:

| Column | Planned type / constraint |
| --- | --- |
| `id` | UUID primary key; generated before insert |
| `owner_principal_id` | `VARCHAR(128)`; non-null trimmed PrincipalId; 1–128; immutable in Phase 1D |
| `title` | `VARCHAR(80)`; non-null; trimmed; 1–80 |
| `description` | `VARCHAR(500)`; nullable; trimmed when present |
| `requested_target_style` | `VARCHAR(32)`; non-null; current allowed value `cel_shading` |
| `planning_mode` | `VARCHAR(32)`; non-null; current value `planning_only_demo` |
| `status` | `VARCHAR(64)`; non-null; initial `DRAFT`; all 16 approved states allowed |
| `created_at` | Non-null timezone-aware timestamp |
| `updated_at` | Non-null timezone-aware timestamp; maintained on real writes |

The implementation must use database constraints for invariant protection in addition to Pydantic and
service validation. Phase 1D has no update endpoint, so no client path may silently overwrite a project.

The full logical PaintProject definition still contains `current_image_asset_id`,
`current_region_version_id` and `current_plan_id`, but Phase 1D does not create these physical columns.
Each reference is introduced by a later Migration together with its target ImageAsset,
RegionGeometryVersion or PaintPlan table and a real Foreign Key. Do not create naked future UUID
columns or bring those target entities into Phase 1D early.

`DRAFT` is the server-owned creation default, not the database's only allowed status. The current
default plan uses a stable Check Constraint named `ck_paint_projects_status_allowed` containing all
16 approved workflow states. Tests must prove Create writes DRAFT, every approved state is
schema-valid, and an unknown string is rejected.

### 5.2 `command_idempotency_records`

Use the version 0.1.3 draft Data Dictionary names and semantics:

| Column | Physical type / purpose |
| --- | --- |
| `id` | UUID record ID |
| `scope_key` | `VARCHAR(512)`; server-generated; trimmed; 1–512 |
| `principal_id` | `VARCHAR(128)`; non-null trimmed PrincipalId; 1–128 |
| `command_type` | `VARCHAR(64)`; lowercase snake_case controlled token |
| `idempotency_key` | PostgreSQL UUID; validated client UUID |
| `payload_hash` | `VARCHAR(64)`; exactly 64 lowercase SHA-256 hex chars |
| `execution_status` | `VARCHAR(32)`; `in_progress/completed`; committed Phase 1D create is `completed` |
| `resource_type` | `VARCHAR(64)`; nullable until completed; `paint_project` for create |
| `resource_id` | UUID; nullable until completed; created project ID when completed |
| `http_status` | Original HTTP status; 201 for successful create |
| `response_snapshot` | PostgreSQL JSONB; nullable until completed; controlled response object |
| `created_at` | Timezone-aware creation timestamp |
| `expires_at` | Exactly 24 hours after creation; minimum retention / cleanup eligibility |

Unique scope:

`scope_key + idempotency_key`

Create Project scope:

`principal:{principal_id}:command:create_paint_project`

Existing-project command scope:

`principal:{principal_id}:project:{project_id}:command:{command_type}`

The server computes scope_key. Create idempotency does not require a project ID and must not derive or
deterministically preallocate the PaintProject UUID from the Idempotency-Key.

### 5.3 `state_transition_events`

FR-001 and the version 0.1.3 draft Data Dictionary require creation to record the initial transition
as an authoritative transactional fact. The initial Migration therefore includes the
`StateTransitionEvent` table.

For creation:

- `from_state=null`;
- `to_state=DRAFT`;
- `event=create_project`;
- `actor_type=user`;
- `actor_principal_id` and `actor_display_name_snapshot` come from the current human Principal;
- `reason=project_created`;
- `correlation_id` comes from the request;
- `event_metadata={}`;
- `created_at` is timezone-aware.

The first `state_transition_events` physical table contains exactly 12 columns:

| Column | Physical type / boundary |
| --- | --- |
| `id` | UUID primary key; generated before insert |
| `project_id` | UUID; non-null Foreign Key to `paint_projects.id`; no ORM delete cascade |
| `from_state` | `VARCHAR(64)`; nullable; approved state when present |
| `to_state` | `VARCHAR(64)`; non-null approved state |
| `event` | `VARCHAR(64)`; non-null lowercase snake_case controlled token |
| `actor_type` | `VARCHAR(32)`; non-null; `user/api/worker/system` |
| `actor_principal_id` | `VARCHAR(128)`; non-null trimmed PrincipalId |
| `actor_display_name_snapshot` | `VARCHAR(200)`; conditional; trimmed; 1–200 when present |
| `reason` | `VARCHAR(128)`; conditional lowercase snake_case controlled reason code |
| `correlation_id` | UUID; non-null |
| `event_metadata` | PostgreSQL JSONB; non-null; server default `{}`; JSON object only |
| `created_at` | Non-null timezone-aware timestamp; server default `now()` |

`event_metadata` can contain only non-sensitive, serializable, machine-readable keys approved by the
specific Event Contract. It must not become arbitrary or uncontracted metadata and must not contain
raw request/response bodies, credentials, secrets, database URLs, exceptions, stack traces, prompts,
model output, binaries, file contents or core business fields. The first Migration creates no GIN or
JSON path Index.

Earlier instructions that prohibited every metadata JSON field are obsolete. A revised Phase 1D-1B
implementation must include the constrained `event_metadata` column while continuing to prohibit
arbitrary or uncontracted metadata.

`agent_run_id` remains a nullable logical StateTransitionEvent field but is physically deferred until
the AgentRun persistence phase. That later Migration must add a UUID Foreign Key to `agent_runs.id`
with `NO ACTION / RESTRICT` unless a future approved contract changes it, backfill existing rows with
`null`, and then introduce the ORM relationship. Phase 1D-1B must not create the column, a naked UUID,
a fake `agent_runs` table or an `event_metadata` substitute for the relationship.

### 5.4 Phase 1D Physical String Matrix

| Table | Column | PostgreSQL type |
| --- | --- | --- |
| `paint_projects` | `owner_principal_id` | `VARCHAR(128)` |
| `paint_projects` | `title` | `VARCHAR(80)` |
| `paint_projects` | `description` | `VARCHAR(500)`, nullable |
| `paint_projects` | `requested_target_style` | `VARCHAR(32)` |
| `paint_projects` | `planning_mode` | `VARCHAR(32)` |
| `paint_projects` | `status` | `VARCHAR(64)` |
| `state_transition_events` | `from_state` | `VARCHAR(64)`, nullable |
| `state_transition_events` | `to_state` | `VARCHAR(64)` |
| `state_transition_events` | `event` | `VARCHAR(64)` |
| `state_transition_events` | `actor_type` | `VARCHAR(32)` |
| `state_transition_events` | `actor_principal_id` | `VARCHAR(128)` |
| `state_transition_events` | `actor_display_name_snapshot` | `VARCHAR(200)` |
| `state_transition_events` | `reason` | `VARCHAR(128)` |
| `command_idempotency_records` | `scope_key` | `VARCHAR(512)` |
| `command_idempotency_records` | `principal_id` | `VARCHAR(128)` |
| `command_idempotency_records` | `command_type` | `VARCHAR(64)` |
| `command_idempotency_records` | `payload_hash` | `VARCHAR(64)` |
| `command_idempotency_records` | `execution_status` | `VARCHAR(32)` |
| `command_idempotency_records` | `resource_type` | `VARCHAR(64)`, nullable until completed |

All API/product lengths count Unicode characters. Future Pydantic validation and PostgreSQL
`VARCHAR(n)` must enforce the same limits.

Canonical lowercase machine-token syntax is:

`^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$`

It applies to `command_type`, `event`, `reason`, `resource_type`, `actor_type`,
`execution_status`, `requested_target_style` and `planning_mode`. Tokens begin with a lowercase
ASCII letter; later segments contain lowercase ASCII letters or digits separated by one underscore.
Uppercase letters, spaces, hyphens, consecutive underscores and trailing underscores are invalid.
Format Checks do not replace approved-value allowlists; fixed enums require length, format and
allowed-values validation.

`status`, `from_state` and `to_state` do not use the lowercase expression. They continue to use the
approved 16 uppercase Workflow States without name, count or case changes.

PrincipalId, `scope_key`, `title`, `description`, `actor_display_name_snapshot`, `payload_hash`,
UUID and JSONB fields do not use the expression. `payload_hash` independently uses
`^[0-9a-f]{64}$`; PrincipalId receives no restrictive character regex; `scope_key` uses its
server-generated structural format.

## 6. Alembic Migration Plan

Planned initialization location:

- `apps/api/alembic.ini`
- `apps/api/migrations/`
- `apps/api/migrations/env.py`
- `apps/api/migrations/script.py.mako`
- `apps/api/migrations/versions/`

Implementation sequence:

1. At implementation start, query the official current Alembic stable release. Current planned
   Alembic 1.x range is `>=1.18.5,<2.0.0`.
2. Add the reviewed dependency only during authorized implementation; update
   `apps/api/pyproject.toml` and `apps/api/uv.lock` together.
3. Initialize Alembic inside `apps/api`.
4. Define one shared SQLAlchemy declarative metadata source and import it explicitly in Alembic
   `env.py`; avoid wildcard side-effect discovery.
5. Configure a consistent SQLAlchemy constraint naming convention.
6. Consume the existing Settings and SecretStr database URL without copying or printing it.
7. Use an async SQLAlchemy migration environment while keeping revision operations deterministic.
8. Generate and manually review the initial business revision; do not accept autogenerate output
   without checking types, enum/check constraints, foreign keys, indexes, uniqueness and downgrade.
9. Run `alembic check`.
10. Test `upgrade head` from an empty PostgreSQL database.
11. Verify schema and create/list/detail behavior.
12. Test downgrade to the prior revision on a disposable test database.
13. Re-run upgrade and verify the already-upgraded database reports head without duplicate objects
    or destructive work.
14. Never run Migration automatically during application startup.
15. Preserve the development volume during normal verification; destructive database resets require
    explicit test-database scope.

Planned stable database invariants include named constraints for nonblank/maximum-length fields,
current style and planning-mode values, owner non-null, status allowed-set Check/default, idempotency scope
uniqueness, execution status, completed-result completeness and expiration ordering. Both application
and database layers validate critical invariants.

Phase 1D-1A established Alembic without a business Revision. Phase 1D-1B supplied the sole approved
and committed business Migration `a10d3d8dab38`. Phase 1D-2 leaves that Migration, all ORM models,
dependency manifests and Lockfiles unchanged.

## 7. Principal and Ownership Plan

- Implement a small PrincipalContext Adapter using approved `configured_demo_operator` semantics.
- Require explicit `APP_ENV` from the finite `development/test/production` set.
- Source a stable, non-secret `principal_id` and display name from explicit configuration; neither
  has a code default.
- Reject current Demo Principal Adapter startup in `production`; a future approved real Principal
  Adapter is required before production or public writes.
- Require both configured Principal fields in development/test and fail during application
  construction when either is absent.
- Never use `display_name` for authorization.
- Never hardcode a personal email, password, token or API key.
- Inject PrincipalContext into routes/services through an explicit FastAPI dependency.
- Set `PaintProject.owner_principal_id` only in the service from PrincipalContext.
- Reject or ignore no client Owner field by defining a request schema that does not accept it.
- Scope list and detail queries by current `owner_principal_id`.
- Return HTTP 404 for both a missing project and a project owned by another Principal; never use 403
  to confirm that another Principal's resource exists.
- Require `principal_type=human` for Phase 1D project creation. A worker/system Principal cannot
  create a human-owned project.
- Do not add public registration, Workspace or multi-tenant abstractions.
- Do not expose an anonymous online write entry before real authentication; current API is only for
  local, internal or deployment-platform-protected access.

## 8. Async Session and Application Layer Plan

- Extend the existing application lifespan from engine-only management to an explicitly injectable
  async session factory.
- Provide one AsyncSession per request.
- Keep HTTP parsing and response mapping in route handlers.
- Put create/list/detail semantics, authorization checks and transaction boundaries in focused
  services.
- Use small domain-specific data-access functions or classes; do not introduce a general Repository
  framework.
- Do not execute SQL directly in routes.
- Ensure cancellation and exceptions roll back the active transaction and close the session.
- Keep health-check behavior independent and regression-tested.
- Apply positive, bounded PostgreSQL lock and statement timeouts before the create idempotency claim
  with parameterized transaction-local `set_config(..., true)`. Defaults are 2000 ms and 5000 ms;
  each setting is bounded at 60000 ms and is not client-controlled.
- Do not catch `asyncio.CancelledError` as an application/database response.

## 9. API Plan

### 9.1 `POST /api/v1/paint-projects`

Input:

- Required `Idempotency-Key` header containing a validated UUID;
- JSON body with `title` and optional `description` only.

Behavior:

1. Resolve PrincipalContext.
2. Normalize and validate the payload.
3. Compute `payload_hash` from a versioned canonical representation.
4. Compute create scope_key from current principal and command type.
5. In the same database transaction, use PostgreSQL
   `INSERT ... ON CONFLICT DO NOTHING` under `scope_key + idempotency_key`.
6. If inserted, generate a normal business project UUID independent of Idempotency-Key, insert the
   PaintProject and initial StateTransitionEvent, save the completed response snapshot, and commit.
7. If a unique conflict occurs, wait for the competing transaction to finish and read its committed
   record.
8. Replay the original HTTP 201 when payload_hash matches; return HTTP 409
   `IDEMPOTENCY_KEY_REUSED` when it differs.
9. If the competing transaction rolls back, acquire execution and continue the same create flow.

Errors use stable safe codes and field details. Database URLs, SQL, stack traces and raw driver
exceptions never enter the response.

### 9.2 `GET /api/v1/paint-projects`

- Return only projects owned by the current Principal.
- Return a stable Envelope with `items`, `total`, `limit` and `offset`.
- Default to `limit=20` and `offset=0`.
- Validate `limit` from 1 through 100 and `offset >= 0`.
- Define `total` as the current owner's matching count before limit/offset.
- Use deterministic ordering `updated_at DESC, id DESC`.
- Return empty `items` and `total=0` for a valid owner with no projects; never synthesize cards.
- Database failure maps to a safe retryable service-unavailable response.

### 9.3 `GET /api/v1/paint-projects/{project_id}`

- Parse a UUID path parameter.
- Read only within the current owner scope.
- Return Project Title, Short Description, Requested Target Style, Planning Mode, Workflow Status,
  Created At and Updated At.
- Return HTTP 404 for both missing and other-owner records.
- Remain read-only; no update or delete action is introduced.

## 10. Idempotency and Transaction Plan

- The frontend creates one UUID idempotency key per logical command. Every new logical command uses
  a new UUID; the client must not proactively reuse an old key across business operations.
- The server computes
  `scope_key=principal:{principal_id}:command:create_paint_project`.
- The unique database constraint is `scope_key + idempotency_key`.
- The client cannot provide scope_key or project ID.
- Do not derive or deterministically preallocate a Project UUID from Idempotency-Key.
- Disable duplicate UI activation, but treat database uniqueness as the authoritative concurrency
  guard.
- Retries of the same logical command after timeout or unknown outcome reuse the same key and
  unchanged canonical payload.
- `expires_at = created_at + 24 hours` is the earliest cleanup eligibility time and establishes
  minimum retention. It does not automatically invalidate a row or permit client key reuse.
- Normalize Title by trim and Description by trim plus empty-to-null before hashing.
- Version the canonical serialization; exclude Header order, authorization, database URLs, secrets,
  server-generated fields and transport noise.
- Start one short database transaction and attempt
  `INSERT ... ON CONFLICT DO NOTHING` for the unique scope/key.
- An inserted row grants execution. The same transaction creates the Project and initial event,
  stores HTTP 201 plus the safe response snapshot, and commits only the completed record.
- A unique conflict waits for the competing transaction. After it commits, read the committed record;
  after it rolls back, acquire execution and continue.
- Same scope/key + same payload + `completed` replays the stored HTTP 201 and response; the API may
  add `Idempotent-Replayed: true`.
- Same scope/key + different payload returns HTTP 409
  `IDEMPOTENCY_KEY_REUSED`.
- `in_progress` remains a full-dictionary value reserved for future asynchronous commands; it is not
  externally observable and has no Phase 1D API response path.
- Project, initial state event and completed idempotency result are committed atomically.
- A database failure rolls back all three; it cannot leave a half-created project or false success
  record. The same key remains safe to retry.
- Concurrent requests rely on the unique constraint and reviewed PostgreSQL transaction/lock
  behavior, not a check-then-insert race.
- Create transactions configure `lock_timeout` and `statement_timeout` locally before the
  conflicting INSERT. A waiter that exceeds either approved limit returns safe retryable 503
  `DATABASE_WAIT_TIMEOUT`; commit/rollback clears the local settings before pool reuse.
- The transaction contains only local database work and no external network call.
- As long as a record exists, same key + same payload replays the original response and same key +
  different payload returns 409, even after `expires_at`.
- A future cleanup task may delete eligible records under a separately approved policy. A deleted
  key may no longer be recognized, but clients must never depend on long-term key reuse.
- Phase 1D implements no cleanup worker or background queue; cleanup is deferred to a future
  background-task phase.

## 11. Frontend Routing Plan

Use package `react-router` v8 Declarative Mode. Do not add the `react-router-dom` package removed from
v8. Phase 1D-3 rechecked the official release and compatibility information immediately before the
dependency change, then locked direct range `~8.3.0` and resolved version `8.3.0`. The resolved
package requires Node `>=22.22.0` and React/React DOM `>=19.2.7`; the repository's Node 24 and
React/React DOM 19.2.8 satisfy those requirements. `package.json` and `pnpm-lock.yaml` now contain
only this approved frontend dependency change and its required transitive resolution.

Use React Router Declarative Mode for:

| Route | Page |
| --- | --- |
| `/paintpilot` | Existing/planned Product Entry boundary |
| `/paintpilot/projects` | Projects Workspace |
| `/paintpilot/projects/new` | Create Paint Project |
| `/paintpilot/projects/:projectId` | Minimum read-only Project Detail |

Phase 1D can implement the last three business routes first.

Route-level loading and errors must remain readable without cinematic assets. Direct navigation and
browser refresh must load data from the API, not prior component state.

## 12. Projects Workspace Plan

Supported states:

- `loading`;
- `loaded / empty`;
- `loaded / projects`;
- `API unavailable`;
- `database unavailable`;
- retrying.

Empty state:

- `No projects yet`;
- one clear `Create Project` action;
- no fixtures or sample project cards presented as user data.

Active state:

- cards are database records;
- list data comes from the `items/total/limit/offset` Envelope;
- no more than three large cards in the first desktop viewport;
- show Title, Workflow Status and Updated At;
- show Review Gate only from real supported data. Because Phase 1D has no persisted review-gate
  record, use an honest `Not started` or explicit empty state, not a fabricated gate;
- each card opens `/paintpilot/projects/:projectId`;
- loading and retry never replace stored truth with optimistic fake projects.

## 13. Create Page Plan

Implement the frozen UX spec and wireframes:

- Title and Description inputs;
- read-only `Cel Shading · Current release`;
- planning-only capability note;
- `Create Project` primary action and `Cancel`;
- client and server validation with retained values;
- submitting state and duplicate-click protection;
- safe retry using the same idempotency key after unknown outcome;
- distinct API unavailable, database unavailable and `409` conflict messages;
- unsaved-change protection for Cancel and supported navigation;
- keyboard operation, focusable error summary, permanent labels and reduced motion.

The page contains no Rights Attestation, upload, AI prompt, Provider, inventory, knowledge, Polygon,
tenant or member controls.

## 14. Project Detail Plan

Supported states:

- `loading`;
- `found`;
- `not found` or ownership-safe inaccessible result;
- `API unavailable`;
- `database unavailable`;
- retrying.

The first release is read-only and displays:

- Project Title;
- Short Description, or an explicit empty value;
- Requested Target Style, displayed as the current Target Style;
- Planning Mode;
- Workflow Status;
- Created At;
- Updated At;
- `Image upload is not implemented yet`;
- `Back to Projects`.

It must fetch by project ID on every direct load. It does not expose Update, Delete or fake upload
controls.

## 15. Error and Recovery Contract

- Validation errors use field identifiers and safe human-readable messages.
- Network unknown outcome retains inputs and retries with the original idempotency key.
- API unavailable and database unavailable are distinct when the server can safely distinguish them.
- A `409 IDEMPOTENCY_KEY_REUSED` explains that the protected request identifier was reused with
  different data and does not claim a project was created.
- Both missing and other-owner detail requests return 404.
- Validation uses 422; idempotency payload conflict remains 409; connection failure,
  connection invalidation and create-policy lock/statement timeout use safe retryable 503.
- Unexpected IntegrityError, ProgrammingError, DataError and unclassified SQLAlchemyError use safe
  non-retryable 500; raw query cancellation outside the tagged create wait policy is not
  automatically treated as retryable.
- All server failures log only controlled context; secrets, SQL parameters and raw driver messages
  are excluded.
- Retry actions remain keyboard-accessible and do not clear real loaded data unnecessarily.

## 16. Test Plan

### 16.1 Backend Unit

- create valid project;
- title empty;
- title over 80;
- description over 500;
- fixed style and planning mode;
- `requested_target_style` is server-owned and fixed to `cel_shading`;
- server owns `owner_principal_id`;
- same idempotency key + same payload;
- same key + different payload;
- server-computed scope_key;
- canonical payload normalization and hash version;
- unique-conflict wait followed by committed-response replay;
- winner rollback allows the waiting request to acquire execution;
- concurrent duplicate key;
- transaction rollback;
- project not found;
- other Principal receives 404 and cannot read project;
- list returns only current owner's projects;
- list Envelope, defaults, limits, offset and stable ordering;
- safe error mapping contains no database details.
- PrincipalId boundary: trimmed 1 and 128 accepted; blank and over 128 rejected;
- scope_key boundary: trimmed 1 and 512 accepted; blank and over 512 rejected;
- command_type, event and resource_type controlled-token boundaries through 64 characters;
- actor display snapshot Unicode and 200-character boundary;
- reason controlled-code boundary through 128 characters;
- every Phase 1D string column matches the frozen physical matrix;
- canonical machine-token syntax accepts valid lowercase segmented tokens and rejects uppercase,
  spaces, hyphens, consecutive underscores and trailing underscores;
- allowed-value constraints remain independent from the machine-token format Check;
- workflow-state fields use only the 16 uppercase allowlisted values and do not use the lowercase
  machine-token Check;
- payload_hash uses its independent `^[0-9a-f]{64}$` format;
- StateTransitionEvent model exposes `event_metadata`, not a conflicting `metadata` ORM attribute;
- StateTransitionEvent model does not expose `agent_run_id` before the AgentRun persistence phase.

### 16.2 Backend Integration

- Alembic migration from an empty PostgreSQL database;
- `alembic check`;
- migration downgrade and re-upgrade;
- already-upgraded database remains at head without duplicate objects;
- POST persists PaintProject, initial StateTransitionEvent and idempotency record atomically;
- POST returns 201 and replay preserves 201;
- GET list returns the created project;
- GET list returns `items/total/limit/offset` in stable order;
- GET detail returns the created project;
- other-owner detail returns 404;
- API process restart and browser refresh preserve the project;
- unique idempotency behavior under retry and concurrent submission;
- named database constraints reject blank/long fields, invalid current enum values, incomplete
  completed records, duplicate scope/key and invalid expiration ordering;
- retention tests prove `expires_at` is cleanup eligibility rather than automatic invalidation:
  an existing record still replays or conflicts after that timestamp;
- status constraint accepts all 16 approved states, while Create writes only DRAFT;
- first paint_projects schema has exactly nine columns and no current reference UUID columns;
- first state_transition_events schema has exactly the frozen 12 columns, includes
  `event_metadata`, and excludes `agent_run_id`;
- `event_metadata` accepts `{}` and JSON objects but rejects array, string, number, boolean and JSON
  null; it has no GIN or JSON path Index;
- migration constraints reject over-limit PrincipalId, scope_key, command_type, event, display
  snapshot, reason and resource_type values at their exact boundaries;
- rollback leaves no partial rows;
- database failure returns a safe response;
- owner isolation across two test Principal contexts.
- deterministic concurrent matrix:
  - A: same Principal/key/payload creates once and replays once;
  - B: same Principal/key with different payloads yields one 201 and one stable 409;
  - C: different Principals sharing a key remain independent;
  - D: different keys create distinct projects;
  - E: a committed response-confirmation loss replays without duplication;
  - F: a PostgreSQL-confirmed blocked waiter acquires after winner rollback;
  - G: expired existing records retain concurrent replay/conflict semantics;
  - H: a PostgreSQL-confirmed lock waiter reaches bounded safe 503 and succeeds after retry;
  - I: list/detail and same-key behavior preserve Owner isolation.
- all concurrent cases use explicit Event barriers or observed PostgreSQL blocking state, bounded
  TaskGroup execution, independent AsyncSessions and exact project/event/record counts; no fixed
  sleep is used to infer overlap or lock waiting.

### 16.3 Frontend

- empty project list;
- loaded project list;
- create validation;
- submit success and detail navigation;
- double-submit protection;
- idempotency key reuse for retry;
- idempotency conflict;
- list Envelope and pagination controls;
- direct detail route refresh;
- detail not found;
- API failure;
- database failure;
- unsaved changes;
- accessible names, error focus and keyboard behavior;
- mobile layout and reduced motion.

### 16.4 Browser Smoke Review

Browser smoke review remains required and must cover:

1. empty Projects Workspace;
2. create validation and keyboard behavior;
3. successful create;
4. detail route direct refresh;
5. list and reopen;
6. API process restart persistence;
7. API and database failure recovery;
8. duplicate retry behavior;
9. desktop and 390 px mobile layouts;
10. console free of unexpected JavaScript, React and Vite runtime errors.

Adding Playwright or another browser package to the repository remains out of scope. The
2026-07-27 Phase 1D-3 remediation explicitly allowed the environment-provided browser automation
runtime for an external audit; it added no dependency, package, lockfile entry or repository
script.

## 17. Implementation Sequence

1. Use the approved Product Contract 0.1.3, Data Dictionary 0.1.3 and ADR-0003 as the Phase 1D
   contract baseline; earlier implementation instructions are obsolete.
2. Reconfirm request/response/error schemas, scope_key format and canonical serialization version.
3. Query the official Alembic stable version; add the reviewed dependency and shared model metadata.
4. Implement named database constraints and manually review the initial Migration.
5. Run `alembic check`, empty-database upgrade, downgrade and re-upgrade verification.
6. Add AsyncSession dependency and configured Principal Adapter.
7. Implement domain-specific data access and PaintProject services.
8. Implement POST, list and detail APIs with backend tests.
9. Verify persistence, idempotency concurrency and rollback against disposable PostgreSQL test data.
10. Query the official React Router v8 release and add a pinned `react-router` compatible dependency.
11. Implement routes, Projects, Create and Detail pages.
12. Add frontend state, accessibility and recovery tests.
13. Run repository quality gates and browser smoke review.
14. Save evidence only after the real create/list/open/restart loop passes.

Each step should remain reviewable. Do not combine schema, API, router and cinematic Product Entry
work into one unbounded change.

Sequence status on 2026-07-27: steps 1–5 are complete in the approved Phase 1D-1B Commit 8; steps
6–9 are complete in the approved Phase 1D-2 Commit 9; steps 10–13 are implemented in the
uncommitted Phase 1D-3 candidate and await focused read-only review. Step 14 evidence is recorded
in the Phase 1D-3 candidate report, but Phase 1D-4 Integrated Product Review remains deferred.

## 18. Definition of Done

Phase 1D is complete only when:

- the approved contract and Migration agree;
- PaintProject stores `requested_target_style=cel_shading` and
  `planning_mode=planning_only_demo` as server-owned fields;
- a new database can upgrade from empty and the revision can downgrade on disposable test data;
- valid create persists exactly one owner-scoped PaintProject with `DRAFT` and its initial event;
- invalid fields never persist;
- create idempotency uses server-computed scope_key without project-ID derivation;
- same-key replay and different-payload conflict match the idempotency contract;
- transaction failure leaves no partial project, event or idempotency result;
- database status constraint permits all 16 approved states and rejects unknown values;
- first paint_projects Migration has nine columns; logical current references remain deferred until
  their target tables and Foreign Keys exist;
- first state_transition_events Migration has exactly 12 columns, uses constrained JSONB
  `event_metadata`, and defers logical `agent_run_id` until a real `agent_runs` Foreign Key exists;
- every Phase 1D string column uses the reviewed `VARCHAR(n)` limit and every PrincipalId column uses
  `VARCHAR(128)`;
- list and detail read only the current owner's real data;
- list uses the frozen Envelope and ordering; other-owner detail returns 404;
- success navigates to the detail route and refresh reads the same record;
- API restart preserves the record;
- Projects empty state contains no fake projects;
- Detail states the honest image-upload boundary;
- backend and frontend planned tests pass;
- browser smoke evidence covers the real loop and failure recovery;
- no unimplemented image, AI, RAG, Polygon or approval capability is presented as available.

The backend subset is complete and committed, and the frontend/browser subset is implemented
pending independent review. Until Phase 1D-3 receives independent approval and Phase 1D-4
Integrated Product Review completes, the full Phase 1D vertical slice and portfolio claims remain
in progress, not complete.

## 19. Planned Evidence

- reviewed Migration revision and empty-database upgrade output;
- backend unit and integration test results;
- frontend lint, typecheck, test and build results;
- API request/response examples with secrets removed;
- database row/count evidence for project, initial event and idempotency record;
- structured browser evidence for empty, create, detail, list/reopen and mobile states; no
  screenshot or recording is required to be retained when the same facts are captured as compact
  assertions;
- restart persistence evidence;
- final Git scope and Lockfile verification.

Evidence must describe observed behavior only. It must not imply Image Upload, AI or deployment
capabilities that Phase 1D does not implement.
