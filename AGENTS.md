# CreativeDeploy Agent Guide

## Project Goal

CreativeDeploy is a deployment-engineering portfolio project. PaintPilot is its primary,
planning-only case. The approved product contract keeps deterministic program state,
model suggestions, and human-owned facts separate.

## Current Implemented Capability

Phase 1B and the Phase 1D-1A database foundation are complete. The current implementation remains
limited to foundation capabilities:

- monorepo foundation;
- FastAPI process liveness;
- real PostgreSQL readiness using `SELECT 1`;
- local PostgreSQL through Docker Compose;
- React health dashboard through the Vite development proxy;
- backend and frontend automated quality checks;
- browser-based healthy, failure, and recovery validation;
- one shared SQLAlchemy Declarative Base with a runtime-immutable naming convention;
- an Online-only async Alembic environment with no business revisions or tables.

These statements are supported by local automated tests and smoke-test evidence. They do
not mean PaintPilot itself is implemented.

The PaintProject business implementation has not started. Phase 1D-1B ORM models and the first
Migration candidate are the next planned implementation step and remain `NOT_STARTED`. The
foundation health page is not the final PaintPilot UI. Phase 1C design direction is approved;
follow its specifications and discuss any proposed UX change with the project owner. Codex must
not unilaterally apply a generic administration-dashboard template.

## Not Implemented

Do not claim or imply implementation of:

- PaintProject or any business entity;
- authentication, authorization, or Principal Adapter;
- image upload, analysis, segmentation, or Polygon Editor;
- AI providers, Agent workflows, RAG, inventory, citations, or Trace;
- HumanApproval or workflow state transitions;
- business Migration revisions, database tables, Redis, workers, CI, or production deployment.

## Directory Responsibilities

- `apps/api`: the independent uv-managed FastAPI package, health schemas, configuration,
  async database engine, shared empty Metadata, Alembic foundation, readiness service, and
  pytest tests.
- `apps/web`: the pnpm-managed React/Vite health dashboard and Vitest tests.
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

These commands never generate or upgrade a revision. The current repository has no business
revision or business table.

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
- The current repository has no business Revision, business table, or PaintProject ORM Model.
- Phase 1D-1A must not introduce a PaintProject Model.
- Preserve safe 503 responses: never expose database URLs, passwords, stack traces, or raw
  infrastructure exceptions.
- Preserve the frontend AbortController and request-generation guards so late health
  responses cannot overwrite newer state.
