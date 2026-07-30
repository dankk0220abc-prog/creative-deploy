# CreativeDeploy

Project Status: Phase 1D `COMPLETE` — Phase 1E-1 `CLOSED` — Phase 1E-2 `CLOSED` —
Phase 1F `PHASE_1F_SNAPSHOT_TARGET_REMEDIATION_IMPLEMENTED_READY_FOR_INDEPENDENT_REVIEW`

Implementation Status:

- Foundation implemented
- Database metadata and Alembic foundation complete
- Phase 1D-1B persistence schema is committed history
- Phase 1D-2 persistence and API are committed history
- Phase 1D-3 frontend implementation exists in Commit 10
- F-01/F-02 UX remediation is committed as the source-code baseline
- Phase 1D-3 governance reconciliation passed independent review and is sealed in
  `ac8630ae393cb6ca5bf3a2d1db5070531d6f3f52`
- Phase 1D-3 is `CLOSED`
- Phase 1D-4 — Integrated Product Review is `CLOSED`
- Phase 1D is `COMPLETE`
- Phase 1E-1 ImageAsset Foundation is `CLOSED`; its independently reviewed implementation is
  sealed by `9b3b23ac3e1f056a73e3934d3da51b24aa7f671d`
- The final independent review verdict is `PHASE_1E_1_PASS_READY_FOR_SEALING`
- Atomic no-overwrite publication, receipt-bound compensation, Project-scoped upload
  idempotency, canonical automated gates, and the program-generated JPEG/PNG/WebP real-browser
  run are preserved as sealed evidence
- The user confirmed the historical approximately 60% checkpoint direction for Phase 1E-2
- Phase 1E-2 adds a four-role ImageSet, deterministic readiness prerequisites,
  append-only human READY / NOT READY reviews, staleness, and a responsive Project Detail
  workbench
- Its original independent review returned `CONTRACT_OR_ARCHITECTURE_DECISION_REQUIRED` after
  a real 201 proved F-01: `primary_front` replacement bypassed the sealed workflow gate in
  `IMAGE_UPLOADED`
- Project control retained ADR-0004, the focused role-aware Service/UI/test remediation restored
  that boundary, and a fresh independent review returned
  `PHASE_1E_2_WORKFLOW_GATE_REMEDIATION_PASS_READY_FOR_SEALING`
- The independently reviewed implementation is sealed by
  `cc89aa246607f7c44b4639149a3b251b803d3a80`; Phase 1E-2 is `CLOSED`
- Overall project progress is approximately 70% (`approximately_70_percent`)
- Phase 1F — Human-Governed Region Annotation and Review is
  `PHASE_1F_SNAPSHOT_TARGET_REMEDIATION_IMPLEMENTED_READY_FOR_INDEPENDENT_REVIEW`; it is not
  independently approved, sealed, closed, or commit-ready
- The Phase 1F candidate adds immutable human RegionSet snapshots, deterministic ppm Polygon
  geometry, ImageSet-fingerprint staleness, Project-scoped save/submit/review idempotency,
  append-only reviews, and an SVG annotation workspace
- AI is `NOT_AUTHORIZED`; external object storage is `NOT_SELECTED`; public/signed URLs are
  `NOT_AUTHORIZED`; deletion and real authentication are `NOT_IMPLEMENTED`
- Automated Polygon generation and automated region analysis remain `NOT_IMPLEMENTED`
- Local storage is development/test only and production storage is `NOT_READY`

Phase 1D-2 Commit:

- Hash: `6d2c3d8001c3737e2e441ee1c0df4179660f0c57`
- Subject: `feat(api): add PaintProject persistence and API`
- Revision: `a10d3d8dab38`
- Independent review: Commit 9 was authorized as historical baseline

Phase 1D-3 Closure Baseline:

- Phase 1D-3 closure commit:
  `c8043b9a75aa9363a661fa245c7ac999961788fd`
- Parent / Governance seal:
  `ac8630ae393cb6ca5bf3a2d1db5070531d6f3f52`
- Source-code baseline / UX remediation:
  `2f99aaf8e1726761c2d89ac444af8380a1cedb79`
- Remediation parent / Commit 10:
  `5965a8707a6ccb06d2f58d8655aabac9630e4abd`

Commit 10:

- Hash: `5965a8707a6ccb06d2f58d8655aabac9630e4abd`
- Subject: `feat(web): add PaintProject routes and project pages`
- Status: `EXISTS_IN_GIT_HISTORY`

Phase 1D-3 Technical Remediation:

- `PHASE_1D_3_UX_REMEDIATION_SEALED`

Phase 1D-3 Governance Reconciliation:

- Independent review:
  `PHASE_1D_3_GOVERNANCE_RECONCILIATION_PASS_READY_FOR_SEALING`
- Governance seal commit:
  `ac8630ae393cb6ca5bf3a2d1db5070531d6f3f52`
- Closure: `CLOSED`

Phase 1D:

- `COMPLETE`

Process Record:

- Commit 10 entered Git history without a formal prior repository approval record.
- No prior repository approval evidence was found.
- The later review does not backdate approval.
- The remediation was independently reviewed and sealed.
- The governance reconciliation passed independent review and was sealed without changing the
  historical process exception.
- Full classification, sealed candidate, and closure record:
  `docs/progress/phase-1d-3-governance-reconciliation-candidate.md`

The commit hashes and relationships above are Git-verified facts. The no-prior-approval,
retrospective-review, focused-review, and independent-review records are owner-supplied external
review records; they do not become pre-Commit-10 evidence. The governance seal is Git-verified.

Phase 1D-4:

- `CLOSED`
- Original review verdict: `PHASE_1D_4_FAIL_REMEDIATION_REQUIRED`
- Technical and product gates: `PASS`
- The original single README phase-state blocker was independently remediated and sealed by
  `707bdfa3c5931867125cc9c7dc11067a86f5f343`
- Closure record:
  `docs/progress/phase-1d-4-integrated-product-review-closure.md`

Phase 1E-1:

- Status: `CLOSED`
- Implementation seal commit: `9b3b23ac3e1f056a73e3934d3da51b24aa7f671d`
- Independent review verdict: `PHASE_1E_1_PASS_READY_FOR_SEALING`
- Migration Revision: `5ed9906e7d33`
- Closure record: `docs/progress/phase-1e-1-imageasset-foundation-closure.md`
- One private immutable `primary_mvp_input` slot, replacement history, rights attestation,
  deterministic upload acceptance, and owner-scoped preview are sealed
- The original private-photo browser attempt remains `INVALID_ATTEMPT`; its rows and object were
  precisely cleaned. A later program-generated JPEG/PNG/WebP browser continuation passed upload,
  safe retry, retained replacements, rejection, restart persistence, three viewports, and cleanup
- Independent review F-01 proved that the former `os.replace` publication could overwrite an
  immutable object. Remediation now uses atomic no-replace publication and a verified publish
  receipt before any uncommitted-object compensation.
- Upload `Idempotency-Key` is formally Project-scoped: the same key is replay/conflict protected
  within one Principal and Project, while different Projects or Principals are independent.
- Local filesystem storage is `NOT_FOR_PRODUCTION_OBJECT_STORAGE`; production fails closed
- Candidate evidence:
  `docs/progress/phase-1e-1-imageasset-foundation-candidate.md`
- Historical Phase 1E-1 closure checkpoint: `approximately_60_percent`
- AI: `NOT_AUTHORIZED`
- External object storage: `NOT_SELECTED`
- Public/signed URLs: `NOT_AUTHORIZED`
- Deletion: `NOT_IMPLEMENTED`
- Real authentication: `NOT_IMPLEMENTED`
- Local storage: development/test only
- Production storage: `NOT_READY`
- Historical next state after closure:
  `NEXT_PHASE_REQUIRES_60_PERCENT_CHECKPOINT_CONFIRMATION`; the user later supplied that
  confirmation for Phase 1E-2

Phase 1E-2:

- Status: `CLOSED`
- Historical candidate verdict:
  `PHASE_1E_2_WORKFLOW_GATE_REMEDIATION_IMPLEMENTED_READY_FOR_INDEPENDENT_REVIEW`
- Original independent review: `CONTRACT_OR_ARCHITECTURE_DECISION_REQUIRED`
- Final independent review:
  `PHASE_1E_2_WORKFLOW_GATE_REMEDIATION_PASS_READY_FOR_SEALING`
- Baseline: `7b0777c393af705637a1e63f7f25f1dc06f75c1e`
- Implementation seal commit: `cc89aa246607f7c44b4639149a3b251b803d3a80`
- Migration Revision: `d4c8a1f7b2e9`, parent `5ed9906e7d33`
- Closure record:
  `docs/progress/phase-1e-2-multi-role-image-set-and-readiness-closure.md`
- Overall project progress: `approximately_70_percent`
- Required roles: `primary_front`, `reference_back`, `reference_angle`
- Optional role: `reference_detail`
- Existing `primary_mvp_input` assets map in place to `primary_front`; identity, version,
  private bytes, SHA-256, storage key, lineage, and Project current pointer are preserved
- Deterministic prerequisites cover role presence, accepted upload checks, attestation
  completeness, required-content distinctness, and private-object availability
- READY / NOT READY is an append-only human record bound to a canonical ImageSet fingerprint;
  later role replacement or fact change preserves the record and derives `stale`
- ADR-0005 does not supersede ADR-0004's workflow gate: primary first upload is `DRAFT`-only,
  primary replacement is review-required/validation-failed-only, references are mutable only in
  the four pre-validation states, and `IMAGE_VALIDATED` freezes every role
- The backend Service is final authority; denied operations return safe 409 before staging and
  do not create asset, object, command, event, pointer, or readiness side effects
- Candidate evidence:
  `docs/progress/phase-1e-2-multi-role-image-set-and-readiness-candidate.md`
- The original workflow-gate failure remains part of the record; it was not rewritten as an
  initial pass
- No production authorization, AI authorization, push, tag, or PR was created by sealing

Phase 1F:

- Name: Human-Governed Region Annotation and Review
- Status: `PHASE_1F_SNAPSHOT_TARGET_REMEDIATION_IMPLEMENTED_READY_FOR_INDEPENDENT_REVIEW`
- Environment-isolated continuation verdict:
  `PHASE_1F_SNAPSHOT_TARGET_REMEDIATION_IMPLEMENTED_READY_FOR_INDEPENDENT_REVIEW`
- Historical implementation-conversation verdict: `PHASE_1F_IMPLEMENTATION_FAILED`
- Historical incident classification: `ENVIRONMENT_ISOLATION_INVALID_ATTEMPT`
- Historical process deviation: one final supplemental browser attempt used the wrong Vite proxy variable and
  sent one unsuccessful Create request to the unrelated service already listening on port 8000;
  the historical no-VisualEngineer-operation completion condition therefore was not claimed
- The controller-authorized continuation used API `18160`, Vite `15160`, and a request-audit proxy
  on `18161`, enforced an explicit not-port-8000 target guard, and performed no VisualEngineer
  request, check, log, container, database, or file operation
- The isolated PostgreSQL schema, private storage, fixtures, processes, and listeners were exactly
  cleaned after the full real-browser journey; public CreativeDeploy business rows remained zero
- Migration Revision: `7f3a2b9c4d1e`, parent `d4c8a1f7b2e9`
- Polygon: human-authored simple Polygon with normalized integer ppm coordinates
- RegionSet: immutable draft/submitted snapshots with derived approval, changes-requested,
  superseded, and stale states
- Review: append-only human `APPROVED` / `CHANGES_REQUESTED` against an exact submitted snapshot
- Workbench: `/paintpilot/projects/:projectId/regions`
- Snapshot-target remediation: exact historical source fork with current ID/version optimistic
  precondition, Project-scoped idempotency, immutable exact-source geometry copy, and
  current-image rebinding
- Candidate evidence: `docs/progress/phase-1f-human-region-annotation-candidate.md`
- This candidate is not independently approved, ready for sealing, Git-sealed, production-ready,
  or phase-closed
- AI: `NOT_AUTHORIZED`
- External object storage: `NOT_SELECTED`
- Public/signed URLs: `NOT_AUTHORIZED`
- Deletion: `NOT_IMPLEMENTED`
- Real authentication: `NOT_IMPLEMENTED`
- The configured Demo Principal is a local development/test identity, not an independent
  enterprise approver or real authentication system

CreativeDeploy 的主案例是 PaintPilot。Phase 0 已建立 Golden Case、MVP Product
Contract、状态机、领域数据字典和 ADR。Phase 1B 提供最小、真实的本地健康检查链路；
Phase 1D-1B 已提交三个 ORM Model 和唯一业务 Migration；Phase 1D-2 已提交真实
PaintProject 后端持久化/API 闭环；Commit 10 已提交首个 PaintPilot 前端产品闭环，
其 F-01/F-02 UX 修复已在 Git 历史中封存：

- React 开发页面；
- FastAPI liveness 和 PostgreSQL readiness API；
- Docker Compose PostgreSQL；
- Vite `/api` 开发代理；
- Python 和前端质量门禁、自动化测试与前端构建；
- 基于浏览器的健康、故障与恢复验证。
- 配置型单 human `configured_demo_operator` Principal Adapter；
- 请求级异步数据库 Session；
- PaintProject-specific Repository 和 application Service；
- PaintProject、初始 `null -> DRAFT` 事件及 completed 幂等结果的单事务写入；
- 同 key/same payload replay、different payload conflict 和数据库唯一约束并发仲裁；
- transaction-local PostgreSQL lock/statement timeout 与精确数据库错误分类；
- owner-scoped create、list 和 detail API。
- React Router v8 Declarative Mode 与 `/paintpilot/projects`、
  `/paintpilot/projects/new`、`/paintpilot/projects/:projectId`；
- 共享 CreativeDeploy/PaintPilot 应用 shell；
- 只使用同源 `/api` 的合同校验 API client；
- 数据库支持的项目列表、创建和只读详情页；
- loading、empty、安全 error、503/API unavailable 与显式 retry；
- 页面生命周期内的 UUID 幂等 key、同 payload 安全重试和双重提交保护；
- 真实浏览器 create/list/detail/reopen、前端/API 重启、故障恢复和 390 px 响应式验证。
- ImageAsset 物理字段、版本链、同 owner/project Foreign Key 与 current partial unique；
- provider-neutral storage port 和仅 development/test 可用的私有本地文件适配器；
- 基于同文件系统 `link` 的原子 no-replace publish、类型化碰撞失败、publish receipt
  身份校验与数据库引用保护的补偿删除；
- JPEG/PNG/WebP 文件头、MIME、完整解码、尺寸、像素、动画、SHA-256 与 20 MiB 限制；
- owner-scoped upload/list/detail/private-content API、upload 幂等 replay/conflict、
  数据库失败补偿与 orphan detection；
- 单一主图槽位、用户权利 attestation、私有预览、不可变历史和受状态机保护的替换 UI。
- 四个正式角色的独立 current/不可变历史、派生 ImageSet、确定性 readiness checklist 与
  fingerprint、append-only 人工 READY / NOT READY 记录、stale/reconfirm、Project-scoped
  幂等与上传/复核竞争保护；
- 四角色私有预览/历史/add/replace 工作台；不包含删除、AI 视角识别、质量分数或公开 URL。
- 纯人工 SVG Polygon 绘制与编辑、ppm 整数坐标、不可变 RegionSet draft/submit 快照、
  ImageSet fingerprint 绑定与 stale、append-only 人工区域复核、Owner 隔离、幂等和并发冲突。

当前治理状态不倒填 Commit 10 创建前的批准，也不把后续复审伪装成提交前证据。治理
reconciliation 已通过独立复审并由 `ac8630ae393cb6ca5bf3a2d1db5070531d6f3f52`
封存；Phase 1D-3 已由 `c8043b9a75aa9363a661fa245c7ac999961788fd` 正式关闭。Phase
1D-4 原复审如实保留失败结论，其唯一 README 状态阻断项后来通过独立修复、独立复审并由
`707bdfa3c5931867125cc9c7dc11067a86f5f343` 封存；结合两部分证据，Phase 1D-4 现已
`CLOSED`，Phase 1D 现已 `COMPLETE`。Phase 1E-1 ImageAsset Foundation 的代码候选、
自动化门禁与程序生成 JPEG/PNG/WebP 浏览器续跑均已通过，首次私人图片浏览器尝试仍如实
保留为 `INVALID_ATTEMPT` 且已精确清理；第一次独立复审发现 storage key overwrite 并返回
`PHASE_1E_1_FAIL_REMEDIATION_REQUIRED`，Security Remediation Round 1 完成 no-replace publish
与 receipt compensation 后，第二次独立复审给出
`PHASE_1E_1_PASS_READY_FOR_SEALING`。实现已由
`9b3b23ac3e1f056a73e3934d3da51b24aa7f671d` 封存，Phase 1E-1 当前为 `CLOSED`。用户随后
确认历史约 60% 检查点的 Phase 1E-2 方向。首次独立复审以真实 201 证明 F-01：
`primary_front` 替换可从 `IMAGE_UPLOADED` 绕过已封存 workflow gate，并返回
`CONTRACT_OR_ARCHITECTURE_DECISION_REQUIRED`。项目总控选择保留 ADR-0004，聚焦修复恢复
角色级后端门禁、前端镜像和零副作用负向测试；新的独立复审给出
`PHASE_1E_2_WORKFLOW_GATE_REMEDIATION_PASS_READY_FOR_SEALING`，实现由
`cc89aa246607f7c44b4639149a3b251b803d3a80` 封存，Phase 1E-2 当前为 `CLOSED`。项目总体
进度仍约 70%；Phase 1F — Human-Governed Region Annotation and Review 当前为
`PHASE_1F_SNAPSHOT_TARGET_REMEDIATION_IMPLEMENTED_READY_FOR_INDEPENDENT_REVIEW`，尚未独立批准、
封存或关闭。当前仍没有公开认证、
真实用户授权、正式图片质量评估、自动区域分析、AI Provider、RAG、Paint inventory、
Agent 工作流、通用 HumanApproval、CI、生产对象存储或生产部署能力。

## Prerequisites

- macOS arm64；
- Homebrew Python 3.13 与 uv；
- Node.js 24、Corepack 和 pnpm 11.14.0；
- Docker Desktop 与 `docker compose`。

项目要求 Python `>=3.13,<3.14`、Node `>=24,<25`。Python 命令必须通过 uv 执行；Node workspace 命令必须通过 Corepack 管理的 pnpm 执行。

## Quick Start

首次启动：

```bash
make bootstrap
make db-up
```

`make bootstrap` 只在 `.env` 不存在时从 `.env.example` 创建它；已有 `.env`
会被保留，不会覆盖。示例凭据只用于本地开发，不可用于生产，`.env` 被 Git
忽略。Make 不会把其中的数据库变量导出给前端安装、测试或构建进程。

`APP_ENV` 没有代码缺省值，只允许 `development`、`test` 和 `production`。当前仅实现
Demo Principal Adapter，因此 `production` 会拒绝启动；`development`/`test` 也必须
显式提供 `PAINTPILOT_DEMO_PRINCIPAL_ID` 和
`PAINTPILOT_DEMO_PRINCIPAL_DISPLAY_NAME`。Demo Principal 不是公共认证，公网写入口必须
等待后续获批的真实 Principal Adapter，或由部署平台提供额外访问保护。

以下命令均从仓库根目录执行。终端一，启动 API：

```bash
make api
```

这是正式支持的 API 启动入口。Settings 始终定位仓库根目录的 `.env`，不依赖
当前工作目录；因此从 `apps/api` 目录直接调试 API 时也会读取同一文件。

终端二，启动 Web：

```bash
make web
```

打开 `http://127.0.0.1:5173`。浏览器请求 `/api` 时由 Vite 转发到本机 FastAPI。

## Health API

- `GET /api/v1/health/live`：只验证 API 进程，不访问数据库；
- `GET /api/v1/health/ready`：使用异步 SQLAlchemy Engine 对 PostgreSQL 执行 `SELECT 1`；
- PostgreSQL 不可用时，readiness 返回 HTTP 503 和稳定的 `DATABASE_UNAVAILABLE`，不返回连接地址或内部异常；
- OpenAPI：`http://127.0.0.1:8000/openapi.json`。

## PaintProject API

- `POST /api/v1/paint-projects`：只接受 Title、可选 Description 和 UUID
  `Idempotency-Key`；Owner、风格、planning mode、状态、ID 和时间由服务端拥有；
- `GET /api/v1/paint-projects`：按当前 Principal 隔离，返回
  `items/total/limit/offset`，默认 `limit=20`、`offset=0`；
- `GET /api/v1/paint-projects/{project_id}`：按 ID 与 Owner 同时过滤，missing 与
  other-owner 都返回 404；
- 当前 Principal 来自非秘密配置
  `PAINTPILOT_DEMO_PRINCIPAL_ID` / `PAINTPILOT_DEMO_PRINCIPAL_DISPLAY_NAME`；
- 两项 Principal 配置都没有代码默认值；普通请求 body、query 或 header 不能切换身份；
- 该 Adapter 只用于受保护的本地、内部或单操作者演示，不是公共认证系统；
- Create 事务默认使用 transaction-local `DATABASE_LOCK_TIMEOUT_MS=2000` 和
  `DATABASE_STATEMENT_TIMEOUT_MS=5000`，两者必须为 `1–60000` 的整数；事务结束后不会
  污染连接池；
- 配置触发的 lock/statement timeout 返回安全、可重试的 503
  `DATABASE_WAIT_TIMEOUT`；连接类故障返回 503 `DATABASE_UNAVAILABLE`；
  未预期 Integrity、Programming、Data 或其他 SQLAlchemy 错误返回安全、
  `retryable=false` 的 500，不伪装成基础设施故障。

## Private ImageAsset API

- `POST /api/v1/paint-projects/{project_id}/images`：只接受一个
  `primary_mvp_input` JPEG/PNG/WebP、UUID `Idempotency-Key`、来源、预期用途与明确的
  rights attestation；成功进入 `IMAGE_UPLOADED`；
- 首次上传只允许 `DRAFT`；替换只允许 `IMAGE_REVIEW_REQUIRED` 或
  `IMAGE_VALIDATION_FAILED`，旧版本和旧文件都保留；
- `GET /api/v1/paint-projects/{project_id}/images` 和
  `GET /api/v1/paint-projects/{project_id}/images/{image_asset_id}` 返回 owner-scoped
  元数据，不返回 storage key、路径、owner/actor ID；
- `GET .../{image_asset_id}/content` 先授权再读取私有对象，返回
  `private, no-store` / `nosniff` 响应，不支持 Range；
- 本阶段的 `upload_validation_result=accepted` 只表示确定性文件接收检查通过，不是
  ImageQualityAssessment、AI 结论、颜色准确声明或法律权利验证；
- development/test 使用 `.local/private-image-storage`（可配置）并跨进程重启保留；
  production 明确拒绝该本地适配器。

## Quality and Tests

PostgreSQL 运行时执行完整检查：

```bash
make check
```

也可以分别运行：

```bash
make lint-api
make format-check-api
make typecheck-api
make test-api
make test-api-integration
make lint-web
make typecheck-web
make test-web
make build-web
```

停止 PostgreSQL：

```bash
make db-down
```

该命令保留命名 Volume，不执行 prune 或数据重置。

## Database Migration

Alembic async 环境复用应用的仓库根目录 Settings 和数据库 Engine 创建边界。历史
Revision `a10d3d8dab38` 仍保持不变；Phase 1E-1 implementation seal 包含第二份 Revision
`5ed9906e7d33`，创建 `image_assets` 并同时引入受复合 Foreign Key 保护的
`paint_projects.current_image_asset_id`。Phase 1E-2 implementation seal
`cc89aa246607f7c44b4639149a3b251b803d3a80` 包含唯一子 Revision
`d4c8a1f7b2e9`，原位映射封存角色并添加 append-only
`image_set_readiness_reviews`；这份 Revision 已封存。Phase 1F candidate Revision
`7f3a2b9c4d1e` 是其唯一子节点，新增四个 append-only annotation/review 表；它尚未经过
独立复审或 Git sealing。

Migration 必须由开发者明确运行；应用启动不会自动执行 Migration。以下只读或差异
检查命令从仓库根目录运行：

```bash
make migration-current
make migration-heads
make migration-history
make migration-check
```

当前环境只支持 Online Migration，不支持离线 SQL 生成。未来 autogenerate 输出只能
作为 Migration Candidate：每份 Revision 都必须人工检查 upgrade、downgrade、约束
名称以及是否误删或误改对象。`alembic check` 只检查 ORM Metadata 与现有 Revision
的差异，不能替代人工审查。

应用启动不会自动 Migration；不要重写历史 Revision。第二份 Revision 已随 Phase 1E-1
implementation seal `9b3b23ac3e1f056a73e3934d3da51b24aa7f671d` 封存；这不表示生产存储
已就绪或后续阶段已获授权。

## Repository Structure

```text
.
├── apps/
│   ├── api/               # FastAPI、配置、数据库 Metadata/Alembic 基础和 pytest
│   └── web/               # React、Vite、Tailwind、Vitest
├── data/golden-cases/     # 用户授权的只读 Golden Case 素材
├── docs/
│   ├── architecture/      # 已批准的架构基线
│   ├── decisions/         # ADR
│   ├── product/           # Product Contract
│   └── progress/          # 阶段证据
├── compose.yaml           # 仅本地 PostgreSQL
├── Makefile               # 本地开发和质量入口
└── pnpm-workspace.yaml    # 当前只包含 apps/web
```

## Known Limitations

- 仅支持本机开发，不包含 API/Web Dockerfile、CI 或生产部署；
- Commit 10 和 UX remediation commit 已存在，但 Commit 10 创建前没有可用的正式仓库
  approval record；后续复审不构成倒填批准；
- Phase 1D-3 技术 remediation 与 governance reconciliation 均已封存，Phase 1D-3 当前为
  `CLOSED`；Commit 10 的提交前批准并未被倒填；
- Phase 1D-4 当前为 `CLOSED`；Phase 1E-1 也已 `CLOSED`，implementation seal 为
  `9b3b23ac3e1f056a73e3934d3da51b24aa7f671d`；Phase 1E-2 已由
  `cc89aa246607f7c44b4639149a3b251b803d3a80` 封存并 `CLOSED`，项目总体约 70%；
  Phase 1F 为
  `PHASE_1F_SNAPSHOT_TARGET_REMEDIATION_IMPLEMENTED_READY_FOR_INDEPENDENT_REVIEW`，AI 接入仍未授权；
- Phase 1D-2 的 F-09-01、F-09-02、F-09-03、F-09-04 已在 Commit 9 前关闭；
- 当前封存基线有五个业务表，Phase 1F candidate 使 Metadata 共九个业务表；
  readiness/RegionSet review 只能 append，PaintProject 仍没有 update、delete 或 Owner
  transfer，ImageAsset 和已封存 RegionSet 历史也没有 update/delete；
- 配置型单 Principal 不是公共认证、多人授权或真实用户系统，production 明确拒绝它；
- Create 幂等 key 仅在当前页面生命周期内保留；浏览器刷新不会恢复尚未确认请求的 key，
  且本阶段不自行引入 localStorage 持久化协议；
- 项目详情中的项目字段仍只读；图片工作台只处理人选角色、attestation、私有预览、
  版本历史与 readiness review，不包含 ImageQualityAssessment、自动视角识别或质量评分；
- Human Polygon/RegionSet candidate 已实现但未独立批准；自动分割、自动标签和自动区域
  分析仍未实现；
- 未配置 CORS，开发访问依赖 Vite Proxy；
- 未实现图片质量评估、AI、RAG、完整 Trace、HumanApproval、后台任务或 Redis。

## 素材使用边界

PaintPilot Golden Case 使用项目用户本人拍摄并授权用于本项目、公开 GitHub 和公开求职展示的手办照片。案例涉及第三方角色和产品造型，仅用于个人、非商业技术演示；CreativeDeploy、PaintPilot 及项目作者与相关版权方、品牌方或制造商不存在官方关联。详细记录见 `data/golden-cases/paintpilot-v0.1/sources.md`。
