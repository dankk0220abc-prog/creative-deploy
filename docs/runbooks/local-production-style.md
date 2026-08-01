# Local Production-Style Runbook

This runbook operates a local build-shaped environment only. Every integrated
run is `LOCAL_PRODUCTION_STYLE_SMOKE` and `NOT_REAL_PRODUCTION`.

For the separate loopback HTTPS, file-secret, dependency readiness, and
temporary backup/restore profile, use `docs/runbooks/staging-operations.md`.

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

## Phase 2B-1 Identity, Storage, and Database Roles

The Phase 2B-1 smoke profile adds a repository-owned synthetic OIDC Provider,
private MinIO, and distinct PostgreSQL roles. They are local/CI test
infrastructure, not real production accounts.

The production API configuration requires:

```dotenv
APP_ENV=production
DATABASE_URL=postgresql+psycopg://<runtime-role>:<secret>@<host>/<database>
IDENTITY_PROVIDER=oidc
OIDC_ISSUER=https://<provider-issuer>
OIDC_CLIENT_ID=<confidential-client-id>
OIDC_CLIENT_SECRET=<secret>
OIDC_REDIRECT_URI=https://<application-host>/api/v1/auth/callback
IMAGE_STORAGE_PROVIDER=s3
S3_ENDPOINT_URL=https://<private-s3-endpoint>
S3_REGION=<region>
S3_BUCKET=<private-bucket>
S3_ACCESS_KEY_ID=<access-key>
S3_SECRET_ACCESS_KEY=<secret>
S3_CREATE_BUCKET=false
S3_ALLOW_INSECURE_HTTP=false
```

Do not place production values in `.env`, Compose, command history, evidence,
or Git. Inject them through the selected deployment secret manager. Production
refuses Demo identity, local storage, HTTP OIDC/S3 endpoints, local OIDC
backchannel rewriting, and application bucket creation.

Provision roles once with an administrative database connection supplied only
to the provisioning process:

```bash
DATABASE_URL='postgresql+psycopg://<admin>:<secret>@<host>/<database>' \
DATABASE_MIGRATOR_ROLE='<migrator-role>' \
DATABASE_MIGRATOR_PASSWORD='<secret>' \
DATABASE_RUNTIME_ROLE='<runtime-role>' \
DATABASE_RUNTIME_PASSWORD='<secret>' \
CREATIVEDEPLOY_ENV_FILE=/dev/null \
uv run --project apps/api \
python -m creativedeploy_api.tools.provision_database_roles
```

Then run Alembic with the migrator URL and the API with the runtime URL. Never
run the API as the admin or migrator. The runtime role has table DML and
sequence usage only; the artifact gate verifies that runtime DDL is refused.

## Integrated Smoke

The canonical self-cleaning gate is:

```bash
RUN_ID=review_20260731_a1 make artifact-smoke
```

It verifies:

- the Web proxy, API readiness, and PostgreSQL;
- real Authorization Code + S256 PKCE against the synthetic OIDC Provider;
- one-time state/callback consumption, nonce, stable issuer+subject identity,
  session rotation, logout, and CSRF rejection;
- anonymous refusal, Owner A/Owner B isolation, assigned reviewer access,
  repeated membership idempotency, and immediate removal;
- private MinIO ACL/policy, conditional upload, API-only streaming/checksum,
  bucket unauthenticated refusal, and absence of provider/public/signed URLs;
- separate admin/migrator/runtime credentials, migrator-owned schema, runtime
  DML, and runtime DDL refusal;
- API/IdP/Web/MinIO restart recovery and database-degraded behavior;
- SPA deep-link fallback and same-origin `/api/`;
- HTML no-store and hashed-asset immutable caching;
- CSP, frame protection, `nosniff`, referrer and permissions policies;
- no HSTS on HTTP;
- non-root and read-only runtime boundaries;
- exact oversized-request rejection and unknown-Host rejection;
- no-store headers on ordinary API success, validation, not-found, proxy-limit,
  and invalid-Host responses;
- production startup refusal of Demo Principal/local storage and incomplete
  OIDC/S3 configuration;
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

## Migration and Rollback

Revision `2b1c4d5e6f70` is the sole head and child of `7f3a2b9c4d1e`.
Use the migrator URL:

```bash
CREATIVEDEPLOY_ENV_FILE=/dev/null \
DATABASE_URL='postgresql+psycopg://<migrator>:<secret>@<host>/<database>' \
uv run --project apps/api alembic -c apps/api/alembic.ini heads

CREATIVEDEPLOY_ENV_FILE=/dev/null \
DATABASE_URL='postgresql+psycopg://<migrator>:<secret>@<host>/<database>' \
uv run --project apps/api alembic -c apps/api/alembic.ini upgrade head

CREATIVEDEPLOY_ENV_FILE=/dev/null \
DATABASE_URL='postgresql+psycopg://<migrator>:<secret>@<host>/<database>' \
uv run --project apps/api alembic -c apps/api/alembic.ini current

CREATIVEDEPLOY_ENV_FILE=/dev/null \
DATABASE_URL='postgresql+psycopg://<migrator>:<secret>@<host>/<database>' \
uv run --project apps/api alembic -c apps/api/alembic.ini check
```

Before any downgrade, take an independently verified database backup and
confirm the rollback objective. `alembic downgrade 7f3a2b9c4d1e` succeeds only
when all Phase 2B-1 identity/session/membership tables are empty and no
ImageAsset references S3. Otherwise it fails closed with SQLSTATE `55000`; do
not bypass that guard or delete governed facts in this Phase.

## Non-Destructive Local-to-S3 Copy

Configure the source local root, destination S3 values, and a database URL.
Dry-run is the default:

```bash
CREATIVEDEPLOY_ENV_FILE=<complete-private-env-file> \
uv run --project apps/api \
python -m creativedeploy_api.tools.migrate_image_storage
```

After reviewing the exact verified count, execute with an optional positive
limit:

```bash
CREATIVEDEPLOY_ENV_FILE=<complete-private-env-file> \
uv run --project apps/api \
python -m creativedeploy_api.tools.migrate_image_storage --execute --limit 100
```

The tool recomputes source size/SHA-256, conditionally copies or resumes an
exact destination, verifies it, and updates only an unchanged matching row.
It never deletes a source object. Do not add deletion, retention, or lifecycle
policy to this procedure.

## Health and Troubleshooting

- `GET /health/live` is NGINX-local and proves the proxy process serves.
- `GET /health/ready` is proxied to the API and requires PostgreSQL.
- A 503 readiness with 200 liveness is the intended degraded state.
- An unknown Host is rejected by the default NGINX server.
- An explicit login-page identity-provider-unavailable state is expected while
  the configured IdP is down; it must not fall back to Demo identity.
- A production startup failure is expected when any required OIDC, S3, or
  explicit database setting is absent or insecure.
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

Phase 2B-1 implements provider-neutral OIDC/private S3 boundaries, and Phase
2B-2 adds a separate synthetic TLS/file-secret/temporary-recovery proof. Neither
selects or configures real providers. Do not deploy publicly until the user
selects identity/client and database/object/IAM ownership, domain/certificate
automation, secret management, deployment/backup ownership, production
RPO/RTO, monitoring/on-call, retention/legal rules, cutover, and incident
response. Independent security/operations review and Git sealing are still
required. AI remains unauthorized.
