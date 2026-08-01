# Phase 2B-1 Command Ledger

Date: 2026-07-31<br>
Repository: `/Users/danke/Developer/CreativeDeploy`<br>
Secret policy: commands below omit/redact process-only synthetic credentials

## Baseline and Discovery

| Command / gate | Exit | Result |
|---|---:|---|
| `git rev-parse --show-toplevel`, branch, HEAD, tree, commit count, status | 0 | exact expected clean baseline |
| `alembic heads` | 0 | starting head `7f3a2b9c4d1e` |
| active Compose PostgreSQL inspection and read-only schema query | 0 | PostgreSQL on loopback 55432; nine business tables |
| local storage enumeration | 0 | no current local objects |
| initial quoted psql aggregate | nonzero | `INVALID_ATTEMPT`; shell quoting only |
| robust psql rerun | 0 | baseline counts confirmed |

## Focused Implementation Gates

| Command / gate | Exit | Result |
|---|---:|---|
| Ruff / formatter during implementation | nonzero then 0 | two formatting findings corrected |
| mypy API | 0 | 64 source files |
| OIDC focused pytest | 0 | 10 passed |
| S3 focused pytest | 0 | 5 passed |
| migration round-trip and unsafe downgrade | 0 | 2 passed |
| AppRoutes focused test (first path) | 1 | no files found; invalid package-relative path |
| AppRoutes focused test (correct path) | 0 | 16 passed |
| governed-fact rollback assertion with private env | 1 | config isolation invalid; no test body ran |
| same rollback cases with empty env file + real PG | 0 | 2 passed |

## Canonical Gate

The canonical command used an empty temporary env file and a process-only
database URL derived without logging its password:

```text
make check ENV_FILE=<empty-temporary-file>
```

| Sub-gate | Exit | Result |
|---|---:|---|
| config audit / database probe | 0 | active real PostgreSQL |
| Ruff | 0 | 90 files |
| formatter check | 0 | 90 files |
| mypy | 0 | 64 source files |
| API unit | 0 | 264 passed; 65% coverage; 0 skip/xfail |
| PostgreSQL integration | 0 | 54 passed; 0 skip/xfail |
| Web lint / typecheck | 0 | PASS |
| Web Vitest | 0 | 13 files / 154 tests |
| Web production build | 0 | 98 modules |

Earlier canonical attempts retained as invalid/failing:

- unchanged private `.env`: partial `POSTGRES_*` rejected;
- a one-command complete legacy URL: port 5432 unavailable;
- `ENV_FILE=/dev/null`: Make requires a regular file;
- first isolated canonical: two Ruff format findings;
- next real-PG canonical: 52/54 integration tests passed; two assertions still
  expected the parent migration after rollback. The candidate correctly
  remained at `2b1c4d5e6f70`; expectation was updated and the full canonical
  gate reran from the beginning.

## Migration Evidence

The real PostgreSQL migration integration exercises:

```text
upgrade head
current
heads
check
downgrade 7f3a2b9c4d1e
upgrade head
unsafe downgrade with governed facts
```

Result: exit 0, one head/current `2b1c4d5e6f70`, empty downgrade/re-upgrade
passed, autogenerate check reported no new operations, and unsafe downgrade
returned the expected SQLSTATE `55000` without fact loss.

The shared user development database was not upgraded; changing user data was
not required for Candidate validation.

## Artifact and Browser

| Command / gate | Exit | Result |
|---|---:|---|
| `make artifact-smoke RUN_ID=phase2b1_live_09` | 0 | first complete identity/storage/role smoke |
| `make artifact-smoke RUN_ID=phase2b1_live_11` | 0 | expanded authorization/restart smoke |
| browser stack `phase2b1_browser_12` | 0 | real UI Owner A/B/reviewer closure |
| `make artifact-smoke RUN_ID=phase2b1_final_13 ARTIFACT_SMOKE_PORT=54713` | 0 | pre-expiry final artifact PASS and exact cleanup |
| `make artifact-smoke RUN_ID=phase2b1_final_16 ARTIFACT_SMOKE_PORT=54716` | 2 | simultaneous restart did not recover Web inside old window; exact cleanup |
| `make artifact-smoke RUN_ID=phase2b1_final_18 ARTIFACT_SMOKE_PORT=54718` | 2 | restart recovered; first expiry fixture violated its creation/expiry check |
| `make artifact-smoke RUN_ID=phase2b1_final_19 ARTIFACT_SMOKE_PORT=54719` | 0 | final PASS including legal expired-session 401 and exact cleanup |
| `make artifact-smoke RUN_ID=phase2b1_final_20 ARTIFACT_SMOKE_PORT=54720` | 0 | expanded final PASS: concurrent/idempotent assignment, two reviewers, reviewer across two projects, private image read, READY review, and exact cleanup |
| first browser Compose restart command | nonzero | missing required synthetic env; did not restart |
| exact API/IdP/Web/MinIO container restart | 0 | start times changed; health/session/object restored |
| direct browser post-logout object navigation | n/a | browser runtime blocked navigation; not app evidence |
| artifact curl post-logout object probe | 0 | application returned 401 |
| first exact temp-file cleanup command | blocked | tool safety refused before execution |
| exact `unlink` + Compose attempt teardown | 0 | cleanup proved |

The passing final artifact emitted short 502 responses only inside the
intentional service-restart window. Its bounded retry recovered and the
complete script returned 0. Long-lived services use `unless-stopped`; one-shot
migration/role jobs are validated to have no restart policy.

## Security, Supply Chain, and Isolation

| Command / gate | Exit | Result |
|---|---:|---|
| Gitleaks `phase2b1_supply_14` | 0 | no leaks |
| first pip-audit | 2 | PyPI 60-second read timeout; no vulnerability conclusion |
| pip-audit retry | 0 | no known vulnerabilities; local package skipped |
| pnpm production audit | 0 | no known vulnerabilities; one registry retry warning |
| immutable reference check, first | 1 | stale expected count after adding MinIO |
| immutable reference check, corrected | 0 | 3 Actions / 9 container references |
| attempt isolation, first | 2 | old script lacked new required synthetic variables |
| `make artifact-isolation-test RUN_ID=phase2b1_isolation_15` | 0 | A/B isolated and exactly cleaned |
| `make secret-scan RUN_ID=phase2b1_finalscan_21` before Manifest | 0 | Candidate scan found no leaks |
| same scan after Manifest generation, first | 2 | API lockfile SHA metadata triggered generic-key heuristic |
| first redacted diagnostic packaging | nonzero | missing exact destination directory; produced no evidence |
| corrected redacted diagnostic | 0 | identified only the Manifest API lockfile SHA metadata line |
| manifest-inclusive `phase2b1_finalscan_21` rerun | 0 | established inline hash allow marker; no leaks |
| `make artifact-isolation-test RUN_ID=phase2b1_isolation_22` | 0 | final A/B isolation rerun passed and exactly cleaned |
| final targeted Ruff format check, first | 1 | immutable-reference validator had one mechanically unwrapped line |
| Ruff format/check rerun | 0 | two final Python validators formatted and lint-clean |
| `make artifact-config-check` | 2 | nonexistent target; produced no validation evidence |
| `make artifact-config RUN_ID=phase2b1_config_24 ARTIFACT_SMOKE_PORT=54724` | 0 | actual declarative artifact configuration target PASS |
| `git diff --check` | 0 | PASS |

## Cleanup and Git

- Every smoke/browser/isolation resource used an exact Phase 2B-1 RUN_ID.
- The retained synthetic `phase2b1_diag_07` temp directory was inspected and
  removed by its exact path.
- The first residual PostgreSQL query had invalid shell quoting and produced
  no evidence; the corrected read-only `starts_with` queries returned zero
  Phase 2B-1 databases and roles.
- No `git add`, commit, push, tag, PR, reset, checkout, clean, or stash ran.
- The final Git state remains an unstaged Candidate on the baseline commit.
- The private `.env` was not edited or printed.

## Final Remediation — 2026-08-01

### Exact Starting Candidate

| Fact | Verified value |
|---|---|
| branch / HEAD / tree / count | `main` / `771b53914f51245d6c62c569e40ddd061ae7ec6e` / `26f395ef6c217bc7f5f997309c12893618ce5634` / `22` |
| staged / tracked modified / untracked leaf / status entries | `0 / 47 / 31 / 78` |
| Manifest / migration | `c96f2f7f69e19b29c27051f9d92ee76d1c3e51fbd536da7e345f2ad25da37a2a` / `cb2356309f88187da26d7f1b061a716600a8cb6397333f54683775a00194f322` |
| payload / porcelain-v1-z / tracked binary patch | `b7e62e6b9f8fb27cd14057be44be895ccd5fae7cfb9bc035fe50557f13984014` / `290d753916af38fe6ab80d5338a4dbf550ef3e868833a4efdd6e187a2bfb061d` / `4e3ec5c61f743258cc31b02e55c746240775c3e4d9323732156940fa0e8dd520` |

The similarly named Documents path was rejected; all implementation and verification
used `/Users/danke/Developer/CreativeDeploy`. The private `.env` was hash/status checked
and left unchanged.

### Finding Reproduction and Focused Gates

| Command / gate | Exit | Result |
|---|---:|---|
| independent F-01 inline reproduction | 0 | valid signed future-expiry token with one-hour-old `iat` was accepted before repair |
| independent F-02 inline reproduction | 0 | corrupted destination could be reported successful with only pre-write HEAD facts before repair |
| new F-01 test before repair | 1 | expected stale-`iat` refusal was missing |
| new F-02 test before repair | 1 | expected post-write HEAD was missing |
| OIDC focused after repair | 0 | 25 passed, including missing/type/future/stale/boundary `iat`, `exp`, safe config, and no secret/token logging |
| S3 adapter plus migration tool | 0 | 16 passed, including post-write size/checksum/type/HEAD failures, exact resume, DB failure, dry-run, and no delete |
| combined remediation focused | 0 | 41 passed |
| direct auth regression | 0 | 51 passed; one existing Starlette deprecation warning |
| direct storage regression | 0 | 39 passed |
| artifact configuration `phase2b1_remediation_config_01` | 0 | exact maximum-age/skew policy PASS |
| hostile OIDC override through `make test-api` | 0 | Make denylist held; 290 passed |
| hostile OIDC override through `make lint-web` | 0 | Make denylist held; PASS |

The copy assertions prove that a successful new write is followed by a destination
HEAD and that the receipt facts come from that verified read. They do not infer this
from an unrelated total call count.

### Canonical, Artifact, Browser, and Isolation

| Gate | Exit | Result |
|---|---:|---|
| canonical `make check` with process-only real PostgreSQL URL and exact empty env | 0 | Ruff/format 91 files; mypy 64; API unit 290 passed, 66%; PostgreSQL integration 54 passed; Web 13 files/154 tests; lint/typecheck/build PASS, 98 modules |
| `make artifact-smoke RUN_ID=phase2b1_remediation_artifact_02 ARTIFACT_SMOKE_PORT=54802` | 0 | real MinIO legacy copy post-write verification and exact resume PASS; complete auth/storage/restart/expiry/role smoke PASS; exact teardown |
| browser stack `phase2b1_remediation_browser_03` | 0 | Owner/reviewer/private image/assign/revoke/Owner B/logout/restart closure; console warning/error set empty; exact teardown |
| `make artifact-isolation-test RUN_ID=phase2b1_remediation_isolation_04` | 0 | parallel A/B isolation PASS; exact teardown |
| `make secret-scan RUN_ID=phase2b1_remediation_finalscan_05` | 0 | manifest-inclusive scan and exact post-ledger/Manifest rerun found no leaks |
| `make audit-api` | 0 | no known vulnerabilities; unpublished local package skipped |
| `make audit-web` | 0 | no known production vulnerabilities |
| `make immutable-reference-check` | 0 | 3 Actions / 9 container references PASS |
| `git diff --check` | 0 | PASS |

The canonical run preceded the final Makefile-only environment-denylist addition. The
affected API and Web Make paths were rerun with hostile maximum-age/skew overrides and
passed; product code and all canonical product gates were unchanged, so the full
canonical entry was not repeated for form alone.

### Final Remediation Invalid Attempts

- The first porcelain parser used an f-string expression containing a backslash and
  raised `SyntaxError`; the robust binary parser established the exact baseline.
- The deliberately red F-01 and F-02 tests failed before repair and are retained as
  reproduction evidence, not PASS results.
- The first focused Ruff check found one unused `Any`; it was removed and the full
  lint/type suite passed.
- The first full OIDC rerun was 40/41 because a test referenced an unbound local
  `token`; the test was corrected to the intended attacker token and 41/41 passed.
- One intermediate Compose edit had incorrect OIDC-line indentation; it was caught
  before a gate, corrected, and the artifact configuration/smoke passed.
- A browser project-link selector correctly refused ambiguity at count two; the fresh
  snapshot supported a unique accessible-name locator and the journey continued.
- A diagnostic `.venv/bin/python` path did not exist; the project-owned `uv run`
  environment was used for the read-only image inspection.
- Two post-restart locator evaluations exceeded the browser client deadline; neither
  performed a mutation. A bounded page-scoped DOM read confirmed the loaded private
  image at `1320 x 1656`.
- The first combined residual-Docker read used escaped newlines and Docker rejected
  the malformed `ps` arguments before inspection. Separate exact read-only container,
  network, volume, and image queries then returned zero remediation resources.

### Remediation Cleanup

- Exact artifact, browser, and isolation RUN_ID containers, networks, volumes, local
  images, databases, roles, objects, synthetic identities/projects, and temp paths were
  removed by their owning teardown paths.
- No unknown listener/process or unrelated Docker/PostgreSQL/file resource was touched.
- No `git add`, commit, push, tag, PR, reset, checkout, clean, or stash ran.
