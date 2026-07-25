# CreativeDeploy

Project Status: Phase 1D-1A — Database Foundation Complete

Implementation Status:

- Foundation implemented
- Database metadata and Alembic foundation complete
- PaintPilot business features `NOT_STARTED`
- Next implementation phase: Phase 1D-1B ORM Models and First Migration Candidate `NOT_STARTED`

Browser Review: `PASSED`

CreativeDeploy 的主案例是 PaintPilot。Phase 0 已建立 Golden Case、MVP Product Contract、状态机、领域数据字典和 ADR。Phase 1B 现在提供一条最小、真实的本地健康检查链路：

- React 开发页面；
- FastAPI liveness 和 PostgreSQL readiness API；
- Docker Compose PostgreSQL；
- Vite `/api` 开发代理；
- Python 和前端质量门禁、自动化测试与前端构建；
- 基于浏览器的健康、故障与恢复验证。

这不是 PaintPilot 业务实现。当前不存在 PaintProject、Authentication / Principal
Adapter、图片上传、区域分析、Polygon Editor、AI Provider、RAG、Paint inventory、
Agent 工作流、HumanApproval、Trace、业务 Migration、CI 或生产部署能力。

Phase 1D-1A 只增加统一 SQLAlchemy Metadata 和 Alembic 管理基础设施。当前仍没有
PaintProject ORM Model、业务表或业务 Revision。

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

## Database Migration Foundation

Alembic async 环境已经建立，并复用应用的仓库根目录 Settings 和数据库 Engine
创建边界。当前没有业务 Revision，也没有 PaintProject 或其他业务表。

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

这只是数据库迁移基础设施，不表示 PaintProject 数据库已经实现。

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
- 数据库仍没有业务表、ORM Entity 或业务 Revision；Alembic 仅完成基础环境；
- 前端只展示基础设施状态，不是 PaintPilot 产品页面；
- 未配置 CORS，开发访问依赖 Vite Proxy；
- 未实现认证、授权、多用户、AI、RAG、Trace、后台任务或 Redis。

## 素材使用边界

PaintPilot Golden Case 使用项目用户本人拍摄并授权用于本项目、公开 GitHub 和公开求职展示的手办照片。案例涉及第三方角色和产品造型，仅用于个人、非商业技术演示；CreativeDeploy、PaintPilot 及项目作者与相关版权方、品牌方或制造商不存在官方关联。详细记录见 `data/golden-cases/paintpilot-v0.1/sources.md`。
