# CreativeDeploy

Project Status: Phase 1D `IN_PROGRESS` — Phase 1D-3 `CLOSED`

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
- Next formal phase: Phase 1D-4 — Integrated Product Review (`NOT_STARTED`)
- Phase 1E-1 remains `NOT_STARTED`; do not enter the image-asset phase

Phase 1D-2 Commit:

- Hash: `6d2c3d8001c3737e2e441ee1c0df4179660f0c57`
- Subject: `feat(api): add PaintProject persistence and API`
- Revision: `a10d3d8dab38`
- Independent review: Commit 9 was authorized as historical baseline

Phase 1D-3 Closure Baseline:

- Current HEAD / Phase 1D-3 closure commit:
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

- `IN_PROGRESS`

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

- `NOT_STARTED`
- Remains **Integrated Product Review** and is the next formal phase
- Has not formally passed

Phase 1E-1:

- `NOT_STARTED`
- Do not enter the image-asset phase until Phase 1D-4 passes and Phase 1D final sealing is complete

CreativeDeploy 的主案例是 PaintPilot。Phase 0 已建立 Golden Case、MVP Product
Contract、状态机、领域数据字典和 ADR。Phase 1B 提供最小、真实的本地健康检查链路；
Phase 1D-1B 已提交三个 ORM Model 和唯一业务 Migration；Phase 1D-2 已提交真实
PaintProject 后端持久化/API 闭环；Commit 10 已提交首个 PaintPilot 前端产品闭环，
其 F-01/F-02 UX 修复已在当前 HEAD 封存：

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

当前治理状态不倒填 Commit 10 创建前的批准，也不把后续复审伪装成提交前证据。治理
reconciliation 已通过独立复审并由 `ac8630ae393cb6ca5bf3a2d1db5070531d6f3f52`
封存；Phase 1D-3 已由 `c8043b9a75aa9363a661fa245c7ac999961788fd` 正式关闭。当前仍
没有公开认证、真实用户授权、图片上传、区域分析、Polygon Editor、AI Provider、RAG、
Paint inventory、Agent 工作流、HumanApproval、CI 或生产部署能力。

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

Alembic async 环境复用应用的仓库根目录 Settings 和数据库 Engine 创建边界。当前
只有一个已批准并提交的业务 Revision `a10d3d8dab38`，创建
`paint_projects`、`state_transition_events` 和 `command_idempotency_records`。

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

应用启动不会自动 Migration；不要重写该历史 Revision，也不要在未批准的任务中创建
第二个 Revision。

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
- Phase 1D-4 和 Phase 1E-1 均为 `NOT_STARTED`；
- Phase 1D-2 的 F-09-01、F-09-02、F-09-03、F-09-04 已在 Commit 9 前关闭；
- 当前只有三个基础业务表和 create/list/detail API，没有 update、delete 或 Owner transfer；
- 配置型单 Principal 不是公共认证、多人授权或真实用户系统，production 明确拒绝它；
- Create 幂等 key 仅在当前页面生命周期内保留；浏览器刷新不会恢复尚未确认请求的 key，
  且本阶段不自行引入 localStorage 持久化协议；
- 前端项目详情只读，卡片没有真实图片或 review-gate 数据；
- 未配置 CORS，开发访问依赖 Vite Proxy；
- 未实现图片、AI、RAG、完整 Trace、HumanApproval、后台任务或 Redis。

## 素材使用边界

PaintPilot Golden Case 使用项目用户本人拍摄并授权用于本项目、公开 GitHub 和公开求职展示的手办照片。案例涉及第三方角色和产品造型，仅用于个人、非商业技术演示；CreativeDeploy、PaintPilot 及项目作者与相关版权方、品牌方或制造商不存在官方关联。详细记录见 `data/golden-cases/paintpilot-v0.1/sources.md`。
