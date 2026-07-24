# Phase 1B — Monorepo Foundation and First Health-check Vertical Slice

- Phase Status: `COMPLETE`
- Date: `2026-07-24`
- Completion Date: `2026-07-24`
- Technical Review: `PASSED`
- Browser Review: `PASSED`
- Final Result: `APPROVED`
- Scope: local development foundation only

## Goal

Establish the smallest real monorepo slice connecting:

```text
React/Vite → FastAPI → PostgreSQL
```

The slice must show healthy infrastructure, degrade safely when PostgreSQL is unavailable,
and avoid implying that PaintPilot product features exist.

## Implemented Scope

- root pnpm workspace with one web package;
- independent uv package for the FastAPI application;
- Docker Compose PostgreSQL 17.10 service;
- FastAPI application factory and lifespan-managed async SQLAlchemy Engine;
- liveness endpoint that does not touch PostgreSQL;
- readiness endpoint backed by a timed `SELECT 1`;
- strict shared 200/503 readiness schema;
- React health dashboard with Checking, Healthy, Unavailable, and Unknown states;
- Vite `/api` development proxy;
- generation-guarded retry, timeout, caller cancellation, abort-on-unmount, and accessible
  live status behavior;
- backend unit/integration tests and frontend component tests;
- Ruff, mypy, ESLint, TypeScript, Vitest, coverage, and Vite build checks.

## Excluded Scope

No business entities, authentication, Principal Adapter, image handling, region analysis,
Polygon Editor, AI provider, RAG, inventory, Agent state machine, HumanApproval, Trace,
Alembic, Redis, workers, CI, application Dockerfile, or production deployment was added.

## Technical Decisions

- React and FastAPI run directly on the development host.
- Only PostgreSQL runs in Docker.
- PostgreSQL is bound to `127.0.0.1` and uses a named Volume.
- The API uses `postgresql+psycopg`, SQLAlchemy AsyncEngine, `pool_pre_ping`, and a configured
  readiness timeout.
- Pydantic Settings reads environment configuration; the database URL is required and has no
  code default.
- Routes delegate the SQL check to `DatabaseHealthService`.
- Frontend health data is validated from `unknown` without adding a schema library.
- Tailwind uses its official Vite plugin and no PostCSS or Tailwind config file.

## Review Fixes

- Retry now synchronously aborts the prior request and invalidates late responses with a
  monotonic generation ID.
- Caller cancellation, internal timeout, and network/invalid responses have distinct client
  error semantics.
- The database URL is a `SecretStr` and is unwrapped only by the Engine factory.
- Settings uses the repository-root `.env` regardless of the process working directory.
- Make no longer imports or globally exports `.env`; Compose receives it through an explicit
  `--env-file`, and Bootstrap preserves an existing file.
- Every pnpm Recipe now uses one explicit denylist boundary that removes the project's known
  backend application and PostgreSQL variables inherited from the parent shell.
- Direct httpx and Ruff development dependencies have bounded version ranges.
- Database timeout, connection failure, SQLAlchemy failure, and cancellation behavior have
  focused service tests.

## Final Environment Boundary Fix

The second independent read-only review found F-03-R1: although Make no longer loaded or
globally exported `.env`, normal parent-shell inheritance could still expose backend variables
to pnpm and frontend lifecycle scripts.

The Makefile now provides an overridable `PNPM` command and routes every pnpm Recipe through
the shared `WEB_COMMAND_ENV` denylist. A one-time probe in the system temporary directory
verified `bootstrap`, `web`, `test-web`, `lint-web`, `typecheck-web`, and `build-web`; all six
targets removed the known backend variables before the probe process started, and the probe
was deleted afterward.

This is an explicit boundary for known CreativeDeploy backend configuration, not a complete
process sandbox for arbitrary unknown secrets. Direct pnpm commands still inherit their
calling shell environment. The focused read-only technical review and browser acceptance both
passed, and Phase 1B is complete.

## Verification Checklist

- pnpm Recipe environment boundary probe (6 targets): PASS
- `docker compose config`: PASS
- PostgreSQL container healthcheck: PASS
- Backend Ruff lint: PASS
- Backend Ruff format check: PASS
- Backend strict mypy: PASS
- Backend unit tests: 13 passed
- Backend coverage: 95%
- `DatabaseHealthService` coverage: 100%
- Backend PostgreSQL integration test: 1 passed
- Frontend ESLint: PASS
- Frontend TypeScript: PASS
- Frontend Vitest: 11 passed
- Frontend production build: PASS
- `make check`: PASS
- OpenAPI health paths: PASS
- Vite proxy readiness path: PASS

## Browser Review

- Healthy desktop: PASS
- Healthy mobile at a `390 × 844` viewport: PASS
- PostgreSQL unavailable and recovery: PASS
- FastAPI unavailable and recovery: PASS
- Retry with mouse, Enter, and Space: PASS
- Horizontal overflow at 390 px: none
- Unexpected browser runtime errors: none
- Sensitive information displayed: no

## Failure Cases Verified

- PostgreSQL stopped while FastAPI remained live.
- Liveness continued to return HTTP 200 without querying PostgreSQL.
- Readiness returned HTTP 503 with `DATABASE_UNAVAILABLE`.
- The 503 payload did not contain a database URL, password, traceback, or raw exception.
- PostgreSQL restart restored readiness to HTTP 200.
- Frontend tests cover network failure, timeout, caller cancellation, immediate Retry abort,
  stale-response rejection, unmount cleanup, and explicit retry.
- Focused backend tests cover timeout, connection failure, SQLAlchemy failure, safe logging,
  and cancellation propagation.
- Missing `DATABASE_URL` produces a clear Pydantic configuration error.

## Evidence

- Healthy live response: status `ok`, service `creativedeploy-api`, version `0.1.0`.
- Healthy ready response: status `ok`, database status `ok`, non-negative latency.
- Degraded ready response: status `degraded`, database status `error`, stable error code.
- Vite proxy response traversed Vite → FastAPI → PostgreSQL and returned status `ok`.
- PostgreSQL image: `postgres:17.10-alpine3.24`.
- Port binding: `127.0.0.1:5432`.
- Final project containers: none.
- Named PostgreSQL Volume: retained.
- Uvicorn and Vite listeners: stopped after smoke testing.
- Original browser screenshots are retained in a private evidence directory outside the Git
  repository and are not committed to the public repository.
- Any future public screenshots require a new privacy and presentation-suitability review.

## Dependency Baseline

Python lock highlights:

- FastAPI 0.139.2
- Uvicorn 0.51.0
- Pydantic Settings 2.14.2
- SQLAlchemy 2.0.51
- Psycopg 3.3.4
- pytest 9.1.1
- Ruff 0.15.22
- mypy 2.3.0

Frontend lock highlights:

- React / React DOM 19.2.8
- Vite 8.1.5
- React Vite Plugin 6.0.4
- Tailwind CSS / Vite Plugin 4.3.3
- Vitest 4.1.10
- TypeScript 5.9.3
- pnpm 11.14.0

## Known Issues and Limitations

- FastAPI's current TestClient path emits an upstream deprecation warning recommending
  `httpx2`; the approved dependency baseline explicitly uses `httpx`, and all tests pass.
- The implementation is local-development-only and has no production security or deployment
  configuration.
- The database contains no application tables and is not a PaintPilot data model.
- The dashboard is infrastructure evidence, not a product feature preview.

## Next Candidate

The only next action is Phase 1C Planning — PaintProject Creation Vertical Slice and UI/UX
Workshop. Phase 1C implementation has not started.
