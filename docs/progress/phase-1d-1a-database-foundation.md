# Phase 1D-1A — Database Metadata and Alembic Foundation

- Phase Status: `COMPLETE`
- Review Status: `PASSED`
- Final Result: `APPROVED`
- Implementation Status: `IMPLEMENTED`
- Completion Date: `2026-07-26`
- Product: `CreativeDeploy / PaintPilot`
- Business Model Status: `NOT_STARTED`
- Business Revision Status: `NOT_STARTED`

## Goal

Establish one SQLAlchemy declarative Metadata boundary and an explicit, asynchronous Alembic
environment that can inspect the local PostgreSQL database without creating PaintPilot business
models, revisions or tables.

## Scope

- one `DeclarativeBase` and one approved naming convention;
- Alembic 1.18 development dependency and locked transitive dependencies;
- Online-only Alembic environment using the existing Settings and async Engine Factory;
- root-directory and `apps/api` CLI operation;
- current, heads, history and metadata-difference checks;
- unit tests for Metadata identity, naming and import side effects;
- developer documentation and non-mutating Make targets.

## Out of Scope

- PaintProject, CommandIdempotencyRecord or StateTransitionEvent ORM models;
- any other ORM entity or business table;
- revision generation, autogeneration, upgrade or downgrade;
- Principal Adapter, business API, React Router or frontend business pages;
- background Migration execution, CI Migration execution or offline SQL generation.

## Dependency Change

- Requested range: `alembic>=1.18.5,<1.19.0`
- Locked version: `alembic==1.18.5`
- Required additions: `Mako==1.3.12`, `MarkupSafe==3.0.3`
- Unrelated upgrades: none
- SQLAlchemy remains `2.0.51`; Psycopg remains `3.3.4`

Alembic is in the existing `dev` dependency group. It is not an application runtime dependency.
No second database driver or Migration library was added.

## Metadata Foundation

`creativedeploy_api.db.base` defines `NAMING_CONVENTION` and the only official `Base`. The Base uses
SQLAlchemy 2.0 `DeclarativeBase` and an explicit `MetaData` instance. Importing it creates neither an
Engine nor a connection.

The official Metadata currently contains zero tables. Tests use separate temporary Metadata and do
not register test objects on `Base.metadata`.

## Naming Convention

| Kind | Convention |
| --- | --- |
| Index | `ix_%(column_0_label)s` |
| Unique | `uq_%(table_name)s_%(column_0_name)s` |
| Check | `ck_%(table_name)s_%(constraint_name)s` |
| Foreign key | `fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s` |
| Primary key | `pk_%(table_name)s` |

Every future `CheckConstraint` must provide an explicit stable constraint name.

## Alembic Environment

- Configuration: `apps/api/alembic.ini`
- Environment: `apps/api/migrations/env.py`
- Revision template: `apps/api/migrations/script.py.mako`
- Versions directory: `apps/api/migrations/versions/`
- Current version files: only `.gitkeep`
- `target_metadata`: the exact `Base.metadata` object
- Autogenerate preparation: `compare_type=True`, `include_schemas=False`

The script location and source path are anchored to `%(here)s`, so they do not depend on the caller's
working directory. The ini file contains no database URL or credential.

Autogenerate output is only a Migration Candidate. Every future revision requires manual review of
upgrade, downgrade, constraint names and unintended object changes. `alembic check` does not replace
that review, and neither application startup nor CI automatically accepts or runs new revisions.

## Online-only Migration Decision

The environment creates the existing application Async Engine, establishes an async connection,
uses `connection.run_sync(...)` for Alembic's synchronous Migration Context and disposes the Engine
in a `finally` block.

Offline mode fails with the fixed safe message:

`Offline migrations are not supported in the current database foundation.`

Offline SQL generation can be evaluated later through an ADR if deployment requirements need it.

## Settings and Secret Boundary

Alembic uses the existing Settings object, whose `.env` path is anchored to the repository root.
Only the existing `create_database_engine(...)` boundary unwraps `database_url`; `env.py` does not
unwrap, print or log it. Importing the environment does not instantiate Settings, create an Engine
or connect to PostgreSQL.

## CLI Verification

The following behavior was observed from both the repository root and `apps/api`:

| Command | Repository root | `apps/api` |
| --- | --- | --- |
| `current` | success; no current Revision output | success; no current Revision output |
| `heads` | success; empty | success; empty |
| `history` | success; empty | success; empty |
| `check` | `No new upgrade operations detected.` | same |

The four Make targets also succeeded. No command output contained a database URL or password.

`make check` retains its existing application-quality semantics and does not call
`migration-check`; Migration inspection remains an explicit developer action.

## Test Results

- `uv lock --check`: passed
- `uv sync --all-groups --locked`: passed
- Ruff lint: passed
- Ruff format check: passed
- strict mypy: passed, 16 source files
- backend unit tests: 32 passed
- backend coverage: 95%
- backend PostgreSQL integration tests: 1 passed
- frontend lint: passed
- frontend typecheck: passed
- frontend tests: 11 passed
- frontend build: passed
- `make check`: passed

The existing Starlette TestClient deprecation warning remains. It is unrelated to the database
foundation and did not fail tests.

## Known Limitations

- no business models;
- no business revisions;
- no PaintProject tables;
- no Migration upgrade/downgrade business test;
- no API or frontend business work;
- no offline Migration mode;
- no cleanup, background or automatic Migration task.

Alembic created the standard `public.alembic_version` infrastructure table while inspecting the
database. It contains zero Revision rows. No CreativeDeploy business table exists.

## Evidence

- both supported working directories produced identical Alembic results;
- official `Base.metadata.tables` count is zero;
- `public` schema contains only `alembic_version`, with zero rows;
- `versions/` contains only `.gitkeep`;
- dependency diff contains Alembic and its required template dependencies only;
- `.env` and frontend Lockfile hashes remained unchanged during verification;
- application startup behavior was not changed to run Migration.

## Minor Findings Closure

- F-01 closed: the public naming convention is now a runtime-immutable `Mapping`, and the exact
  same immutable object is installed on `Base.metadata`;
- F-02 closed: the source scan now detects direct or aliased `DeclarativeBase`, legacy
  `declarative_base()`, direct or assigned-registry `generate_base()`, and independent
  application `MetaData(...)` declarations while excluding test-only Metadata;
- F-03 closed: the Phase 1D plan now distinguishes `apps/api/alembic.ini` from the
  `apps/api/migrations/` environment and `apps/api/migrations/versions/` revision directory.

Targeted regression tests cover immutable access through both public references, all five naming
categories, the single official Base export, Alembic Metadata identity and import-side-effect
boundaries. Phase 1D-1A is `COMPLETE`; Phase 1D-1B remains `NOT_STARTED`.

## Next Task

`Phase 1D-1B — PaintProject ORM Models and First Migration Candidate`

That task must define the three approved ORM models, generate a candidate Revision, manually review
it and add real upgrade/downgrade integration coverage. It is not started by Phase 1D-1A.
