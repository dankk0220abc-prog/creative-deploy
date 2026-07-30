# Local Production-Style Runbook

This runbook operates a local build-shaped environment only. Every integrated
run is `LOCAL_PRODUCTION_STYLE_SMOKE` and `NOT_REAL_PRODUCTION`.

## Preconditions

- Run from `/Users/danke/Developer/CreativeDeploy`.
- Docker Desktop, uv 0.11.30-compatible tooling, Node 24.17.0, and Corepack
  pnpm 11.14.0 are available.
- The regular development PostgreSQL service, when needed, is exactly
  `creativedeploy-postgres-1` on `127.0.0.1:55432`.
- Do not expose or probe API port 8000. The artifact profile publishes only
  `127.0.0.1:18080` unless `ARTIFACT_SMOKE_PORT` is deliberately set to another
  free loopback port.

## Local Configuration Source

New installs:

```bash
make bootstrap-env
make config-check
make db-up
```

Local development uses the complete `POSTGRES_HOST`, `POSTGRES_USER`,
`POSTGRES_PASSWORD`, `POSTGRES_DB`, and `POSTGRES_PORT` set in the selected
environment file. Settings derives the SQLAlchemy URL. A partial set or a
conflicting `DATABASE_URL` is an error. Process environment has the normal
settings precedence over the environment file. Production instead requires an
explicit injected `DATABASE_URL`.

`make bootstrap-env` will not overwrite an existing `.env`.

### Existing private `.env` drift

If `make config-check` reports that the private `.env` disagrees with the
Compose database, stop the API and migrations, make a private backup outside
Git, then manually update only these values to the intended local Compose
service:

```dotenv
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=55432
POSTGRES_USER=creativedeploy
POSTGRES_PASSWORD=<the password used by compose.yaml>
POSTGRES_DB=creativedeploy
```

Remove a stale local `DATABASE_URL` or make it exactly equivalent. Never commit
the private file and never copy its contents into logs or Candidate evidence.
Re-run `make config-check`, `make ensure-db`, and the four migration read-only
checks.

## Build and Static Validation

```bash
RUN_ID=review_20260731_a1 make artifact-config
RUN_ID=review_20260731_a1 make artifact-build
```

`RUN_ID` must match `^[a-z0-9][a-z0-9_]{0,39}$`. Use a new value for every
implementation or review attempt. It becomes part of the Compose project,
database principal/database name, temporary directory, Gitleaks container, and
artifact image identity. Never reuse another live attempt's identifier.

The build context excludes `.env`, local private storage, tests, Git metadata,
and development caches. The API runtime contains neither pytest nor application
source/test directories. The migration image contains Alembic and psycopg but
not pytest, pip-audit, Ruff, or mypy. Both runtime containers execute as
non-root.

## Integrated Smoke

The canonical self-cleaning gate is:

```bash
RUN_ID=review_20260731_a1 make artifact-smoke
```

It verifies:

- the Web proxy, API readiness, and PostgreSQL;
- SPA deep-link fallback and same-origin `/api/`;
- HTML no-store and hashed-asset immutable caching;
- CSP, frame protection, `nosniff`, referrer and permissions policies;
- no HSTS on HTTP;
- non-root and read-only runtime boundaries;
- exact oversized-request rejection and unknown-Host rejection;
- no-store headers on ordinary API success, validation, not-found, proxy-limit,
  and invalid-Host responses;
- production startup refusal of Demo Principal/local storage;
- production refusal of derived `POSTGRES_*` when explicit `DATABASE_URL` is
  absent;
- migration-image dependency minimization;
- readiness 503 and liveness 200 while PostgreSQL is unavailable;
- exact Compose project teardown with volumes.

The cross-attempt isolation regression is:

```bash
RUN_ID=review_isolation make artifact-isolation-test
```

It starts two uniquely labelled PostgreSQL attempts, removes the first, proves
the second remains, and then removes only the second.

For interactive synthetic browser evidence only:

```bash
RUN_ID=browser_20260731_a1 make artifact-smoke-up
```

Use only new synthetic data. When finished:

```bash
RUN_ID=browser_20260731_a1 make artifact-smoke-down
```

Do not use this profile for real data.

## Health and Troubleshooting

- `GET /health/live` is NGINX-local and proves the proxy process serves.
- `GET /health/ready` is proxied to the API and requires PostgreSQL.
- A 503 readiness with 200 liveness is the intended degraded state.
- An unknown Host is rejected by the default NGINX server.
- A production import failure mentioning unavailable adapters is expected until
  real authentication and storage decisions are implemented.
- Registry or package-index EOF/TLS failures are environmental
  `INVALID_ATTEMPT`s. Preserve the first result and re-run the full affected
  gate after connectivity returns.

## Supply Chain and CI

```bash
RUN_ID=review_20260731_a1 make secret-scan
make audit-api
make audit-web
make immutable-reference-check
RUN_ID=review_20260731_a1 make supply-chain-check
```

Gitleaks scans the tracked and untracked Candidate through a read-only,
network-disabled, attempt-labelled container. pip-audit and pnpm audit use the
locked dependency sets. `immutable-reference-check` requires full commit SHAs
for Actions and tag-plus-digest references for every executable container
input. The single GitHub Actions workflow repeats quality, migration, artifact,
smoke, isolation, and supply-chain gates without a private `.env` or production
Secret.

## Production Gaps Requiring User Decisions

Do not deploy publicly until the user selects real authentication and identity
ownership, external private-object storage, domain/TLS termination, secrets
management, deployment ownership, backups/restore, monitoring, and retention.
AI remains unauthorized.
