# Phase 1D — PaintProject Vertical Slice Implementation Plan

- Phase Status: `READY_FOR_IMPLEMENTATION`
- Approval Date: `2026-07-24`
- Implementation Status: `NOT_STARTED`
- Plan Status: `APPROVED`
- Product: `CreativeDeploy / PaintPilot`
- Planned Routes: `/paintpilot/projects`, `/paintpilot/projects/new`,
  `/paintpilot/projects/:projectId`
- Product Contract: `0.1.2 APPROVED_FOR_IMPLEMENTATION`
- Data Dictionary: `0.1.2 APPROVED_FOR_IMPLEMENTATION`
- Decision Record: `ADR-0002 Accepted`

本文档已获准用于拆分 Phase 1D 实现任务，但仍只描述计划，不表示 Migration、数据表、
API、前端路由、页面或测试已经实现。Product Contract 0.1.2、Data Dictionary 0.1.2
和 ADR-0002 已批准或接受；任何实现仍需在后续授权任务中完成。

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

Phase 1D-0 records the narrow alignment as Product Contract 0.1.2 and Data Dictionary 0.1.2 draft
amendments plus proposed ADR-0002:

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

Rights Attestation remains attached to each ImageAsset and is not part of Create Project. The 16
states, 47 Transitions, 17 numbered Guards, Golden Case art rules and planning-only validation
boundary are unchanged.

The alignment remains a draft until Owner review. Migration and business-code implementation are
blocked until the draft amendments and ADR-0002 are accepted.

## 5. Database Plan

### 5.1 `paint_projects`

The first `paint_projects` Migration contains exactly these nine physical columns:

| Column | Planned type / constraint |
| --- | --- |
| `id` | UUID primary key; generated before insert |
| `owner_principal_id` | Non-null stable Principal ID; immutable in Phase 1D |
| `title` | Non-null trimmed string; non-empty check; proposed maximum `80` |
| `description` | Nullable trimmed string; proposed maximum `500` |
| `requested_target_style` | Non-null; current allowed value `cel_shading`; immutable initial intent |
| `planning_mode` | Non-null; current allowed value `planning_only_demo`; server-owned |
| `status` | Non-null; initial value `DRAFT`; guarded program write |
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

Use the version 0.1.2 draft Data Dictionary names and semantics:

| Column | Purpose |
| --- | --- |
| `id` | UUID record ID |
| `scope_key` | Stable server-computed command scope |
| `principal_id` | Stable authorized Principal |
| `command_type` | Controlled value for create project |
| `idempotency_key` | Validated client UUID |
| `payload_hash` | SHA-256 of versioned canonical request |
| `execution_status` | Full dictionary allows `in_progress/completed`; committed Phase 1D create record is `completed` |
| `resource_type` | Controlled resource type, `paint_project` for create |
| `resource_id` | Created project ID when completed |
| `http_status` | Original HTTP status; 201 for successful create |
| `response_snapshot` | Controlled response-schema JSON with no secret |
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

FR-001 and the version 0.1.2 draft Data Dictionary require creation to record the initial transition
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
- `created_at` is timezone-aware.

The exact table fields follow the version 0.1.2 draft Data Dictionary. Phase 1D must not create a
reduced incompatible audit schema.

## 6. Alembic Migration Plan

Planned initialization location:

- `apps/api/alembic.ini`
- `apps/api/alembic/`
- `apps/api/alembic/env.py`
- `apps/api/alembic/versions/`

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

No Alembic files or dependency changes are made by this planning task.

## 7. Principal and Ownership Plan

- Implement a small PrincipalContext Adapter using approved `configured_demo_operator` semantics.
- Source a stable, non-secret `principal_id` and display name from configuration.
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
- Do not expose an anonymous online write entry before real authentication; use protected access.

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
- The transaction contains only local database work and no external network call.
- As long as a record exists, same key + same payload replays the original response and same key +
  different payload returns 409, even after `expires_at`.
- A future cleanup task may delete eligible records under a separately approved policy. A deleted
  key may no longer be recognized, but clients must never depend on long-term key reuse.
- Phase 1D implements no cleanup worker or background queue; cleanup is deferred to a future
  background-task phase.

## 11. Frontend Routing Plan

Use package `react-router` v8 Declarative Mode. Do not add the `react-router-dom` package removed from
v8. The current official stable version verification result is `8.2.0`, and the planned compatible
range is `>=8.2.0,<9.0.0`. The exact resolved version will be locked by `pnpm-lock.yaml`.
Immediately before dependency changes, query the official documentation again and recheck React 19,
Vite 8 and Node 24 compatibility. This planning task does not modify `package.json` or
`pnpm-lock.yaml`.

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
- Validation uses 422; database unavailable uses 503; unexpected server failures use a safe 500.
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
- rollback leaves no partial rows;
- database failure returns a safe response;
- owner isolation across two test Principal contexts.

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

Playwright remains out of scope unless separately approved.

## 17. Implementation Sequence

1. Owner reviews and accepts Product Contract 0.1.2, Data Dictionary 0.1.2 and ADR-0002.
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
- list and detail read only the current owner's real data;
- list uses the frozen Envelope and ordering; other-owner detail returns 404;
- success navigates to the detail route and refresh reads the same record;
- API restart preserves the record;
- Projects empty state contains no fake projects;
- Detail states the honest image-upload boundary;
- backend and frontend planned tests pass;
- browser smoke evidence covers the real loop and failure recovery;
- no unimplemented image, AI, RAG, Polygon or approval capability is presented as available.

Until these checks pass, implementation and portfolio claims remain `NOT_STARTED` or in-progress, not
complete.

## 19. Planned Evidence

- reviewed Migration revision and empty-database upgrade output;
- backend unit and integration test results;
- frontend lint, typecheck, test and build results;
- API request/response examples with secrets removed;
- database row/count evidence for project, initial event and idempotency record;
- browser screenshots for empty, create, detail, list/reopen and mobile states;
- restart persistence evidence;
- final Git scope and Lockfile verification.

Evidence must describe observed behavior only. It must not imply Image Upload, AI or deployment
capabilities that Phase 1D does not implement.
