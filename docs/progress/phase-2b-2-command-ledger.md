# Phase 2B-2 — Command Ledger

Date: 2026-08-01<br>
Repository: `/Users/danke/Developer/CreativeDeploy`<br>
Role: implementation engineer; not independent reviewer or Git sealer

This ledger records safe command classes and outcomes. It never records secret
values, private backup content, cookie/token values, or exploit detail.

## Baseline

| Command/evidence | Result |
|---|---|
| `git rev-parse --show-toplevel` | exact Developer repository |
| `git branch --show-current` | `main` |
| `git rev-parse HEAD` | `511e42ecb2adccc55e75cb4d801181206b1b337a` |
| `git rev-parse HEAD^{tree}` | `05420278f8da5478be39832466fc60609c215313` |
| `git rev-list --count HEAD` | `23` |
| authorized Candidate takeover | 21 tracked modified + 17 untracked leaves; staged 0; all Phase 2B-2 |
| takeover status fingerprint | `a2d7cf1e2b8157297c927c2a7a09999fb0e73f0729e56d595fee341b1d4eb034` |
| private `.env` | ignored/untracked, Git status empty, unchanged SHA-256 `4b0b5d93f30da2d6751c43fd62ca3e5de60fcc91f93c7374e68f78f70492ef85` |
| `uv run --project apps/api alembic -c apps/api/alembic.ini heads` | `2b1c4d5e6f70 (head)` |
| `RUN_ID=p2b2_baseline_20260801 make artifact-config` | PASS |

## Final F-01/F-02 Remediation Baseline

| Command/evidence | Result |
|---|---|
| exact Candidate recheck | `main`; expected HEAD/tree/count; 21 tracked modified + 18 untracked; staged 0; 39 entries |
| original Candidate hashes | Manifest `f05dd48673582bb7349e67a5d174eb67301a632fac2dd68e9072bfb544482629`; payload `ae12237358d05b76df2de884b64b7091c79d298c2b4785b41b9bf529ea3f2bc7`; binary patch `240f17d53d912ae8a09a4e100f2dfe64f9947b2d7bd77919bf63fc43c42ad878`; porcelain `4270e64730f01ba9f1a4e740a2ba6fcc3c6c3e3171bb9e469a66f22697e37b8a` |
| private `.env` | unchanged SHA-256 `4b0b5d93f30da2d6751c43fd62ca3e5de60fcc91f93c7374e68f78f70492ef85` |
| authorized scope | F-01 independent Manifest authenticity and F-02 real destination-byte verification only |

## Final F-01/F-02 Remediation Gates

| Command/evidence | Result |
|---|---|
| focused backup/restore integrity suite | PASS, 22 tests |
| `make check ENV_FILE=.env.example` after final transaction change | PASS; 322 API unit at 66%, 54 PostgreSQL integration, 154 Web, 98-module production build |
| `p2b2_fix_alembic_0801k` isolated Alembic upgrade/current/check | PASS, unchanged `2b1c4d5e6f70`; exact database dropped |
| `RUN_ID=p2b2_fix_artifact_0801e make artifact-test artifact-build artifact-smoke` | PASS; bounded restart transient recovered; exact cleanup |
| `RUN_ID=p2b2_fix_drill_0801l make staging-drill` | PASS; backup 9 s, restore 8 s, RPO 0; detached authenticity/tamper/real-byte mismatch/exact retry/private data/permissions |
| targeted HTTPS Chrome `p2b2_fix_browser_0801i` | PASS; secure context, Owner create/upload, private 1320x1656 JPEG, zero app page errors/failures/bad responses |
| `RUN_ID=p2b2_fix_supply_0801m make supply-chain-check` | PASS; Gitleaks 0, pip-audit 0 known, pnpm production audit 0 known, immutable refs 3 Actions/11 containers |
| cleanup probes | PASS; exact containers/networks/volumes/images/databases/roots/profile/listeners absent |

## F-02-01 Final Object Integrity Remediation

| Command/evidence | Result |
|---|---|
| exact Candidate recheck | `main`; expected HEAD/tree/count; 21 tracked modified + 19 untracked; staged 0; 40 entries |
| approved starting hashes | Manifest `60607f13b3cf8048e1425f771ab7d43590943ebddc346fc6f9607ffe5a90e918`; payload `b892ad4105be4a78a765d4fdcbc667d67c11f8ea98f92d9126040c968fd117c8`; binary patch `ed2b11d69a999d8c918b696dc3602cb89ecc4777dd8ecd55e4ff7098c7ce5ff6`; porcelain `6d1072a49d24e5bd348275f8835852361659b409e38212c5074cb94cb35a49bd` |
| shared S3 boundary | real streaming GET/body SHA-256 for new PUT and existing retry before receipt/database update; HEAD/ETag/metadata/size auxiliary only |
| focused adapter/migration/restore suite | PASS, 42 tests; body-read/hash/close, failure zero-update/source retention/dry-run/resume covered; F-01 remains PASS |
| independent negative probe | PASS by refusal: same size + same content type + same metadata + different bytes; real GET/body hash observed; existing object preserved |
| `make check ENV_FILE=.env.example` | PASS; 326 API unit at 66%, 54 PostgreSQL integration, 154 Web, 98-module production build |
| isolated Alembic `p2b2finalm_0802b` | PASS; unchanged `2b1c4d5e6f70`; database dropped, residual 0 |
| artifact `p2b2finala_0802a` | PASS; post-write real GET/hash and exact retry; exact cleanup |
| staging drill `p2b2finald_0802a` | PASS; backup 8 s, restore 8 s, RPO 0; detached authenticity, exact retry, byte mismatch refusal, private object, permissions |
| HTTPS Chrome `p2b2finalb_0802a` | PASS; secure exact localhost certificate, TLS 1.3, HTTP 308/HSTS, Owner create/upload, visibly rendered private 1320x1656 JPEG |
| supply chain `p2b2finals_0802a` | PASS; Gitleaks 0, pip-audit 0 known, pnpm production audit 0 known, immutable refs 3 Actions/11 containers |
| cleanup probes | PASS; exact owned processes/listeners/containers/networks/volumes/images/databases/roots/profile absent |

Final-remediation invalid attempts preserved: the first focused run required
one Ruff line-length and one formatter-only correction; the first Alembic shell
command had invalid quoting and created no database; the in-app browser refused
the synthetic leaf; optional Node telemetry lacked WebSocket support; and the
first cleanup form was rejected before execution. None was counted as PASS.

## Focused Implementation Gates

| Command/evidence | Result |
|---|---|
| `make lint-api` | PASS |
| `make typecheck-api` | PASS, 68 source files |
| `make test-api` | PASS, 299 tests, 61% aggregate coverage |
| `sh -n scripts/verify_staging_drill.sh` | PASS |
| `make staging-config` in isolated probe | PASS |
| `make staging-build` in isolated probe | PASS |
| HTTPS curl/OpenSSL probes | 308 redirect; ready 200; deep-link 200; HSTS; wrong Host 400; TLS 1.1 refused; TLS 1.2 accepted |

## Invalid Attempts Preserved

| Attempt | First result | Classification / correction |
|---|---|---|
| staging secret/config probe 1 | macOS resolved temp parent differed from literal `/tmp`; operations profile absent from config | `INVALID_ATTEMPT`; accept the OS temp alias and validate with operations profile |
| staging startup 1/2 | secret direct/file exclusivity revalidated after file consumption | implementation failure; clear consumed file field before assignment |
| staging startup 3 | API healthcheck used absent `STAGING_HOST` | implementation failure; derive authority from `PUBLIC_ORIGIN` |
| request-correlation rebuild | NGINX rejected unquoted regex brace at config line 16; Web unhealthy | implementation failure; quote regex and rerun complete affected stack |
| backup probe 1 | recovery trap parsed spaced synthetic JSON as signals; no backup ran | implementation failure; exact secret-free `docker start` trap |
| backup probe 2 | Compose run replaced the operations module command | implementation failure; fixed module entrypoint |
| backup probe 3 | quiesce flag stayed in Compose CLI environment, not container | safe exit 2; pass explicit boolean container environment |
| canonical `make check` first run | Ruff format-check rejected two changed files | implementation failure; mechanically format and rerun the complete target |
| migration against existing development DB | database was at the historical revision, not Candidate head | `INVALID_ATTEMPT`; do not modify it; use a confirmed-absent exact temporary DB |
| in-app browser | `ERR_CERT_AUTHORITY_INVALID` before page navigation | blocked attempt preserved; no interstitial/global bypass or trust-store change |
| Node REPL CDP prototype | no global WebSocket in that environment | no page action; moved to a temporary raw-CDP Node harness |
| browser redirect capture | 308 was recorded in `redirectResponse`, not ordinary response event | no login/business write; corrected evidence capture |
| browser sign-in and create controls | duplicate Sign in text and coordinate activation ambiguity | selectors scoped; deterministic DOM activation; fresh state after writes |
| upload-role control | form already visible, so role button was absent | use existing form when present; fresh state after created project |
| focused Cookie test typo | 1 failed / 55 passed because `get_list` was not a Starlette API | corrected to `getlist`; complete focused file then 56 passed |
| first full TLS journey | logout left `__Host-paintpilot_session` in Chrome | real product defect: deletion omitted Secure; centralized secure Cookie expiry helpers added and fully rerun |
| zsh port allocator | three ports were not word-split | failed before cert/container/browser; image-only root removed; line-based allocation used |
| expired-session control | coordinate click sent no POST; page retained entered title | harness-only failure; DOM activation used on a fresh run |
| browser cleanliness | expected 401/404 appeared as Chrome `source=network` console errors | diagnostic proved exact response mapping; only declared exact URL+status negatives are explained |
| failed Chrome cleanup | exact process ignored SIGTERM | PID/debug port/profile matched before SIGKILL; children/listener verified absent; successful runs used CDP close |
| read-only target listing | Python f-string escaping syntax error | no browser/product action; corrected formatter and continued inspection |
| focused remediation dry-run fixture | accidentally inherited private `.env` configuration | test-fixture error; `.env` unchanged; isolated fixture and full focused suite passed |
| remediation drills `0801a`/`0801b` | negative-reason observation then diagnostic grep mismatch | harness diagnostics corrected; neither result counted as PASS |
| remediation drill `0801c` | byte-mismatch probe ran after browser login rows and restore correctly rejected non-fresh DB | fail-closed implementation was correct; reordered negative probe before those writes; fresh full runs passed |
| first remediation secret scan | synthetic signing-key fixture matched generic-key rule | fixture rewritten without key-like material; fresh Gitleaks and full supply-chain gates passed |
| remediation in-app browser | self-signed leaf rejected with `ERR_CERT_AUTHORITY_INVALID` | no interstitial/global bypass; fresh Chrome exact-SPKI profile used and cleaned |
| remediation Chrome SPA wait | load-event wait timed out after successful client-side navigation | page state and clean CDP telemetry confirmed navigation; no product failure |
| shared development Alembic gate | current `7f3a2b9c4d1e`, check failed | `INVALID_ATTEMPT`; shared DB not modified; exact isolated DB used |
| first isolated Alembic command | explicit env-file setting omitted, so empty DB remained unupgraded | harness invocation corrected; DB dropped; fresh isolated database passed |

The failed probe API was restarted by its exact attempt container name. Each
probe was subsequently torn down with its volumes/images, and its exact secret/
backup roots were removed. No existing Compose project was changed.

## Canonical Staging Recovery Drill

Historical implementation run `p2b2_drill_0801a` passed. The final canonical
rerun was `RUN_ID=p2b2_drill_0801g make staging-drill` and also passed.

Result: PASS.

- Source and restore used two distinct projects/databases/volumes and the same
  loopback HTTPS origin, with production-built Web/API and synthetic providers.
- HTTPS/TLS, exact Host/Origin, secure cookie, one request ID, deep-link,
  file-secret, structured-log, non-root/read-only, startup-order checks passed.
- Synthetic Owner/Reviewer/Project/membership/history/private JPEG created.
- Backup without quiescence failed exit 2 and published nothing.
- MinIO stop produced readiness 503 and liveness 200; restart recovered.
- Backup dry-run and execution completed: fourteen tables, one object,
  application/Alembic/schema/manifest/checksum metadata; final run 9 seconds.
- Source stack was removed before a new `p2b2r_...` target was created.
- Restore dry-run/execution completed; restored identities, Owner/reviewer role,
  project/history, private bytes and SHA-256 matched; final run 8 seconds.
- Exact restore retry completed without duplicate state.
- Tampered table CSV failed manifest checksum validation; restored state and
  private bytes remained unchanged.
- Service logs contained neither generated secret values nor query marker.
- Both attempts, volumes, local images, secret/backup roots, and temporary
  evidence were removed exactly.

Measured synthetic RPO: 0 seconds under application quiescence. These small
local timings are not production SLOs.

## Authorized TLS Continuation and Real Browser Gate

Successful command class: dedicated Chrome 150 with an attempt-owned `/tmp`
profile and `--ignore-certificate-errors-spki-list=<current-leaf-only-pin>`.
`--ignore-certificate-errors` was never used. macOS Keychain and system CA trust
were not modified.

Final run: `p2b2_browser_0801f` → PASS.

- Chrome Security state `secure`; TLS 1.3; exact `localhost` subject; HTTP 308;
  HSTS `max-age=86400` on HTTPS and absent from HTTP redirect.
- `__Host-paintpilot_session`: Secure, HttpOnly, SameSite=Lax, Path=/;
  `__Host-paintpilot_csrf`: Secure, not HttpOnly, SameSite=Strict, Path=/.
- Owner create/private upload, Reviewer grant/access, outsider safe 404,
  Reviewer revoke/project+content 404, logout Cookie clearance, and expired
  session create 401/zero rows passed.
- API, Web, OIDC, MinIO, and PostgreSQL each restarted with readiness 200 and
  persistent identity/project/private image recovery.
- Source backup and removal, fresh `p2b2r_...` restore, exact restore retry,
  restored Owner/Reviewer/private stream, and 1440/768/390 layout passed.
- Unexplained console errors: 0; exceptions: 0; unexplained network failures:
  0. Three exact 401/404 network-console entries and two canceled navigations
  remain explicitly explained evidence.
- Browser evidence SHA-256:
  `43cfbbf566933f7bfb3799e894e71ff75643f94961ce5fa86c4c0693043c91cf`.
  Browser backup manifest SHA-256:
  `00eee9fa14a7d5f791d72187b11da0901c0f398cb75cae33b843efc8dcb0d61e`.

The source/restore stacks, local images, volumes, networks, debug listener,
Chrome/profile, certificate/key/SPKI, backup root, and temporary CDP helpers
were removed by exact ownership.

## Canonical Full and Final Gates

- Focused health/TLS/origin/secret/Cookie file: PASS, 56 tests, 1 known
  Starlette/httpx deprecation warning.
- `RUN_ID=p2b2_drill_0801g make staging-drill`: PASS; backup dry-run/real 9 s,
  restore dry-run/real 8 s, exact retry, checksum refusal, one private object,
  permissions/history and zero-RPO quiesced proof; exact cleanup PASS.
- `RUN_ID=p2b2_artifact_0801h make artifact-test artifact-build artifact-smoke`:
  PASS; runtime restart/transient recovery and exact cleanup PASS.
- `make check ENV_FILE=.env.example`: PASS; Ruff/format/mypy; API 300 unit,
  62% aggregate coverage, 54 PostgreSQL integration; Web lint/typecheck, 154
  tests and production build; skip/xfail 0; one known deprecation warning.
- Alembic upgrade/current/heads/history/check: PASS at `2b1c4d5e6f70` in
  confirmed-absent `p2b2m_0801i`; owner confirmed, database dropped, absence
  verified.
- `RUN_ID=p2b2_security_0801j make supply-chain-check`: PASS. Gitleaks about
  2.83 MB / 0 leaks; pip-audit 0 known vulnerabilities with one explicit local
  non-PyPI package skip; pnpm production audit 0 known vulnerabilities;
  immutable references PASS (3 Actions, 11 container references).
- `git diff --check`: recorded after final documentation freeze.
- Candidate manifest generation and `--verify`: recorded after final
  documentation freeze; manifest self-hash reported externally to avoid
  recursive mutation.

## Governance Boundary

No `git add`, commit, push, tag, PR, public deployment, real domain/account,
real secret/data, paid service, retention/deletion, public/signed URL, AI, OCR,
Agent, or RAG action was performed.
