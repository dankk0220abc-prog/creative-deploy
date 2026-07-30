# ADR-0007 — Local Production Artifact and Runtime Boundary

Status: Candidate for independent review<br>
Date: 2026-07-30

## Context

The sealed Phase 1F application was a local development system. It required a
repeatable production-built shape without pretending that authentication,
external object storage, a real domain, TLS termination, or production
operations already existed. The application also intentionally rejects its
Demo Principal and local-filesystem storage when `APP_ENV=production`.

## Decision

1. Build the API with a locked Python 3.13/uv multi-stage Dockerfile. The
   migration and runtime targets share the lock but the runtime excludes
   development/test dependencies and source-only tooling. The runtime executes
   Uvicorn without reload as a non-root UID.
2. Build the React application with a locked Node/Corepack/pnpm stage and copy
   only `dist` into the unprivileged NGINX runtime.
3. Make NGINX the only published endpoint. It binds to loopback in the smoke
   profile, proxies `/api/` internally, exposes a proxy-local liveness endpoint
   and API-backed readiness, serves deep links through `index.html`, rejects
   unknown hosts, disables directory listing, and does not trust arbitrary
   forwarded hosts.
4. Cache hashed assets immutably and the HTML shell with `no-store`. Preserve
   private API asset `no-store` behavior. Apply CSP without `unsafe-eval`,
   frame protection, `nosniff`, no-referrer, and a restrictive
   Permissions-Policy. Do not emit HSTS on the HTTP-only profile.
5. Keep the request-body boundary at 20 MiB plus the multipart overhead defined
   by the upload contract.
6. Name and label the only runnable integrated profile
   `LOCAL_PRODUCTION_STYLE_SMOKE` and `NOT_REAL_PRODUCTION`. It runs with
   `APP_ENV=test`, an isolated synthetic Demo Principal, PostgreSQL volume, and
   private local volume. This exception never applies to production.
7. Keep production fail-closed. Importing the API with `APP_ENV=production`
   while Demo Principal or local storage is configured must fail.
8. Use an explicit production `DATABASE_URL`. For local development, derive it
   from one complete `POSTGRES_*` set and reject partial or conflicting
   definitions. Never overwrite an existing private `.env`.
9. Use one CI workflow, lockfile installs, PostgreSQL integration, artifact
   builds/smoke, Alembic checks, Gitleaks, and dependency vulnerability audits.

## Consequences

The repository now has a realistic build and same-origin runtime spine that can
be tested repeatedly. It remains unsuitable for public production because
identity, external private-object storage, TLS/domain operations, monitoring,
backup/restore, retention, and deployment ownership are not selected.

No migration, ORM contract, external cloud SDK, public URL, deletion path, or
AI capability is introduced by this decision.

## Rejected Alternatives

- Treating the Vite development server or reload-enabled Uvicorn as a
  production artifact.
- Publishing the API directly or adding broad CORS for the smoke profile.
- Using a self-signed certificate and describing it as production TLS.
- Silently using a private `.env`, weakening the production adapter refusal, or
  naming the smoke profile production.
- Adding a second CI system or cloud-provider SDK before a user decision.
