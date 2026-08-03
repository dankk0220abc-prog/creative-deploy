# Phase 2B-2 — Staging Operations and Production Hardening Candidate

Candidate state: `FINAL_REMEDIATION_READY_FOR_INDEPENDENT_REVIEW`<br>
Date: 2026-08-02<br>
Repository: `<repository-root>`

## 1. Verdict

`PHASE_2B_2_FINAL_REMEDIATION_READY_FOR_INDEPENDENT_REVIEW`

The authorized staging topology, TLS/exact-origin, secret-file, complete
readiness, structured-log, coordinated backup/restore, operations, CI, and
real-browser gates pass as one unstaged/uncommitted Candidate. Browser trust was
limited to the current synthetic certificate's SPKI in one dedicated Chrome
process/profile; no global certificate-error bypass, macOS Keychain change, or
system trust-store mutation occurred.

This is not independent approval, Git sealing, or a production-ready claim. No
public deployment/domain binding, real secret/data, paid service, public/signed
URL, retention deletion, AI, OCR, Agent, or RAG was added.

## 2. Verified Baseline

- Git root: `<repository-root>`
- Branch: `main`
- HEAD: `511e42ecb2adccc55e75cb4d801181206b1b337a`
- Tree: `05420278f8da5478be39832466fc60609c215313`
- Commit count: `23`
- Candidate takeover: 21 tracked modified paths, 17 untracked leaves, staged 0
- Takeover status fingerprint: `a2d7cf1e2b8157297c927c2a7a09999fb0e73f0729e56d595fee341b1d4eb034`
- Private `.env`: ignored/untracked, Git status empty, unchanged SHA-256
  `4b0b5d93f30da2d6751c43fd62ca3e5de60fcc91f93c7374e68f78f70492ef85`
- Alembic head: `2b1c4d5e6f70`
- Baseline production artifact config: PASS

The F-02-01 final-remediation takeover independently rechecked the expected
40-entry Candidate: 21 tracked modified paths, 19 untracked leaves, staged 0;
Manifest SHA-256
`60607f13b3cf8048e1425f771ab7d43590943ebddc346fc6f9607ffe5a90e918`,
payload SHA-256
`b892ad4105be4a78a765d4fdcbc667d67c11f8ea98f92d9126040c968fd117c8`,
tracked binary patch SHA-256
`ed2b11d69a999d8c918b696dc3602cb89ecc4777dd8ecd55e4ff7098c7ce5ff6`,
and porcelain SHA-256
`6d1072a49d24e5bd348275f8835852361659b409e38212c5074cb94cb35a49bd`
all matched before remediation. The private `.env` hash also matched and the
file was not edited.

The existing 38-path Candidate was explicitly authorized for takeover. Every
path was attributable to Phase 2B-2; no unknown product change, Phase 2B-1
sealed-file regression, or private `.env` edit was found. The similarly named
Documents checkout was not used. Phase 2B-1 was not reopened or re-reviewed.

## 3. Staging Architecture

- `compose.staging.yaml` supplies TLS ingress, production Web/API, one-shot
  role-provision/migration/grant jobs, PostgreSQL, private MinIO, synthetic OIDC,
  and an on-demand operations container.
- Only configurable HTTP/HTTPS loopback ports are exposed. App/data networks
  are internal; PostgreSQL, MinIO, OIDC, and API have no host binding.
- API waits for role provisioning → migration → grants and for OIDC/MinIO
  health. Web and TLS wait for the downstream service.
- Runtime services are non-root, read-only, capability-dropped, and
  `no-new-privileges`; writable paths are bounded tmpfs/owned volumes.
- Unique run IDs label projects, volumes, databases, buckets, credentials,
  temporary evidence, and exact cleanup.

## 4. TLS and Origin

- Outer NGINX terminates TLS 1.2/1.3, redirects HTTP 308 to the exact HTTPS
  origin, and emits HSTS only on HTTPS.
- Exact `PUBLIC_ORIGIN`, trusted Host, OIDC callback, forwarded host/protocol,
  and unsafe API Origin are required. `Forwarded`, wildcard hosts/origins, and
  mismatched callbacks fail closed.
- HTTPS production cookies use `__Host-`, Secure, explicit SameSite, and
  HttpOnly for the session.
- OIDC-flow, session, and CSRF Cookie expiry preserves the required Secure,
  SameSite, HttpOnly, and `/` attributes. This closed the real TLS-only logout
  defect where Chrome correctly refused an insecure deletion header for a
  `__Host-` Cookie.
- SPA deep links, API, OIDC protocol endpoints, and authenticated private image
  streaming work through the same HTTPS authority.
- Certificate/key are read-only attempt secrets outside Git. The contract is
  provider-neutral and does not bind a real domain or issuer.
- Real Chrome 150 reported `secure` with TLS 1.3 and subject `localhost` under
  an exact process-scoped SPKI allowlist. The certificate was a two-day,
  `CA:FALSE`, localhost-only synthetic leaf. Its profile, certificate, key, and
  SPKI material were removed after the run.

## 5. Secret Management

- Direct-or-file settings exist for runtime database URL, OIDC client secret,
  and S3 access pair; exactly one source is allowed.
- The strict reader rejects missing, empty/multiline, symlinked, unstable,
  overlarge, executable, group/world-writable, or non-UTF-8 files.
- Staging separates admin/migrator/runtime database material, OIDC, S3, TLS
  certificate, TLS key, and backup signing key across twelve read-only mounts.
  The signing key is mounted only into the operations container. Synthetic generation
  uses private directory/file modes and never prints values.
- Secret fields are excluded from frontend/test command environments. Logs,
  health, config audit, backup output, browser state, build args/layers, and CI
  do not contain secret values.

## 6. Backup and Restore

- Root cause F-01: the previous file-hash Manifest was self-asserted; an attacker
  able to replace the backup could update both content and checksums. The fix
  uses an independent `*_FILE` signing key and explicit key ID to protect the
  complete canonical Manifest with HMAC-SHA-256 in detached
  `manifest.hmac.json`. Restore/dry-run verifies authenticity with constant-time
  comparison before constructing database or object-storage clients.
- Canonicalization is uniquely defined as UTF-8 JSON, ASCII escaping, sorted
  object keys, and compact separators. The signed content includes format/
  version/time, backup/run/source/application/Alembic/schema/database facts,
  table/file/object inventory, sizes/checksums/content metadata, and signing
  algorithm/canonicalization/key ID/signature filename. Duplicate JSON keys,
  missing/wrong key identity, unsafe key files, missing signature, and any
  governed-field tamper fail closed without disclosing key/signature/Manifest.
- Root cause F-02-01: backup/restore already streamed object bodies, but the
  shared `copy_verified_object()` boundary still used destination HEAD size,
  content type, and metadata checksum as final content identity. A same-size
  object with matching metadata but different bytes could therefore be reused.
  The shared S3 adapter now streams a real GET body in 64 KiB chunks after a new
  PUT and before existing-object exact retry, counts actual bytes, calculates
  SHA-256 locally, closes the body, and requires actual size/digest plus content
  type and metadata. HEAD/ETag/provider checksum/metadata/size remain auxiliary
  only. Verification precedes every success receipt and database reference
  update; any failure leaves the existing object and original file untouched.

- Backup requires API quiescence and performs dry-run first. A repeatable-read,
  read-only transaction exports fourteen business tables, deferred pointers,
  schema/version facts, application/source revision, and DB object inventory.
- Every private object is checked and copied with size, SHA-256 and content
  metadata. A complete manifest covers every backup file; partial work is never
  published.
- Restore requires explicit consent and a new database matching `p2b2r_...`.
  It checks format, manifest/file hashes, application/Alembic/schema versions,
  bucket freshness, then restores objects/data and byte-verifies all exported
  facts and database/object correspondence.
- Exact retries succeed without duplicates. Unexpected partial state,
  mismatched object, or tampered file returns safe exit 2. No in-place restore,
  source/backup deletion, retention automation, or destructive downgrade exists.
- Canonical synthetic drill: one project, Owner, Reviewer membership, history,
  and private image; source removed; new environment restored; identity/role/
  project/object SHA preserved; exact retry passed; tampered CSV refused with
  zero data change. Backup 9 s, restore 8 s, quiesced synthetic RPO 0 s.

Final object-integrity drill `p2b2finald_0802a` used a new source and a distinct
fresh restore environment. It proved detached authenticity, source removal,
fresh restore, exact retry, signed-Manifest field tamper refusal with zero
target change, and refusal of an existing object with matching size/content
type/metadata checksum but different real bytes. Owner/Reviewer/Project/history,
private bytes/SHA, references, login, and permissions survived. Backup was 8 s,
restore 8 s, and quiesced synthetic RPO 0 s.

## 7. Observability and Operations

- API liveness and readiness are distinct. Readiness concurrently checks
  PostgreSQL, private storage, and identity metadata with bounded timeouts and
  safe component codes.
- JSON logs contain timestamp, level, logger, event, correlation ID, method,
  normalized path, status, and duration only. Query strings, bodies, cookies,
  secrets, and exception representations are excluded.
- One valid inbound request ID is preserved through both proxies and API;
  otherwise ingress creates one. Safe startup/shutdown and request completion
  events are emitted.
- Stopping MinIO produced readiness 503 while liveness stayed 200; restart
  restored readiness and persistent state. Runbook covers deploy order, secret
  rotation, application rollback, temporary data recovery, faults, and exact
  cleanup.

## 8. Tests and Browser Evidence

- Final F-02-01 focused adapter/migration/restore suite: 42 PASS. It covers
  new PUT re-GET, exact-retry body hashing, forged metadata, same-looking ETag,
  same size/content type/metadata with different bytes, GET/stream/type/size
  failures, body-read/close assertions, database update ordering, original-file
  retention, dry-run zero writes, and database-failure safe resume. F-01
  authenticity tests remain PASS and F-01 remains closed.
- Independent reviewer probe now rejects the governed negative with
  `real_get=1`, `body_read=1`, `sha256_from_body=1`, and
  `existing_preserved=1`.
- Final `make check ENV_FILE=.env.example`: PASS; Ruff/format/mypy, 326 API unit
  tests at 66% aggregate coverage, 54 real PostgreSQL integration tests, Web
  lint/typecheck, 154 Web tests, and 98-module production build passed. The one
  Starlette/httpx deprecation warning is unchanged.
- Final Alembic head/current/check passed at unchanged `2b1c4d5e6f70` in exact
  temporary database `p2b2finalm_0802b`, which was then dropped.
- Artifact test/build/smoke `p2b2finala_0802a`: PASS; legacy copy performed
  post-write real GET/hash and exact retry; exact resources were removed.
- Targeted final HTTPS browser acceptance `p2b2finalb_0802a`: Chrome used
  a fresh profile and the exact synthetic certificate SPKI, reported a secure
  connection with a valid exact `localhost` certificate, TLS 1.3, HTTP 308 and
  HSTS, completed Owner sign-in/project creation/private JPEG upload, and
  visibly rendered the 1320x1656 private image. Exact resources, profile, and
  listeners were removed.

- Focused API gates after the Cookie fix: Ruff PASS; mypy PASS; 56 focused
  health/TLS/origin/secret/Cookie tests PASS, with one known Starlette/httpx
  deprecation warning.
- Canonical `make check ENV_FILE=.env.example`: PASS; Ruff/format/mypy, 300 API
  unit tests at 62% aggregate coverage, 54 real PostgreSQL integration tests,
  Web lint/typecheck, 154 Web tests, and production build passed. Skip/xfail: 0.
- Alembic upgrade/current/heads/history/check: PASS at `2b1c4d5e6f70` in
  confirmed-absent temporary database `p2b2m_0801i`; ownership was checked and
  the database was dropped exactly.
- Artifact config/test/build/smoke: PASS in `p2b2_artifact_0801h`; Web output
  was 98 modules, 348.08 kB JS / 104.11 kB gzip. Exact resources were removed.
- Canonical source-to-new-environment HTTPS recovery drill
  `p2b2_drill_0801g`: PASS. Backup dry-run/real, restore dry-run/real, exact
  retry, checksum refusal, private-object/permission preservation, and cleanup
  all passed.
- Real Chrome HTTPS acceptance `p2b2_browser_0801f`: PASS. HTTP 308, HTTPS-only
  HSTS, TLS 1.3 secure state, exact localhost certificate, Secure/HttpOnly
  Cookies, login/logout, Owner create/upload, Reviewer grant/access/revoke,
  non-member/revoked 404, private streaming, responsive 1440/768/390 layouts,
  API/Web/OIDC/MinIO/PostgreSQL restart recovery, fresh restore, exact retry,
  and expired-session 401 with zero write all passed.
- Browser cleanliness: 0 unexplained console errors, 0 exceptions, 0
  unexplained network failures. Three Chrome `source=network` error entries
  were retained as explained exact 401/404 negative responses; two canceled
  navigation requests were retained as expected aborts.
- Browser evidence SHA-256:
  `43cfbbf566933f7bfb3799e894e71ff75643f94961ce5fa86c4c0693043c91cf`;
  browser backup manifest SHA-256:
  `00eee9fa14a7d5f791d72187b11da0901c0f398cb75cae33b843efc8dcb0d61e`.
  The temporary evidence files were summarized here and then removed with the
  attempt; neither contained Cookie/token/Secret/private-key values.

## 9. Security and Supply Chain

- CI now runs the canonical staging drill in addition to existing quality,
  migration, production artifact, HTTPS-independent artifact smoke, Gitleaks,
  dependency audit, and immutable-reference gates.
- Staging's PostgreSQL and MinIO executable inputs are tag-plus-SHA-256 pinned;
  immutable validation covers three full-SHA Actions and eleven container
  references.
- No secrets are supplied through GitHub Actions, build arguments, or frontend
  variables. Gitleaks scanned about 2.90 MB across tracked and untracked
  Candidate leaves and found 0 leaks.
- `pip-audit`: no known vulnerabilities; the local non-PyPI
  `creativedeploy-api 0.1.0` was the single explicit skip. `pnpm audit --prod`:
  no known vulnerabilities. Immutable references: PASS, 3 Actions and 11
  container references.
- No public/signed object endpoint, retention/deletion automation, real account,
  paid monitor, or model integration exists.

## 10. Invalid Attempts

All invalid attempts preceded the final full rerun and remain in the Command
Ledger:

1. macOS temporary-root resolution and missing operations-profile config were
   rejected before containers; both validators were corrected.
2. direct/file secret assignment initially re-triggered mutual-exclusion
   validation; consumed file fields are now explicitly cleared.
3. API healthcheck referenced an unavailable host variable; it now derives the
   exact authority from `PUBLIC_ORIGIN`.
4. the first request-ID NGINX map used unquoted brace regex and Web failed
   startup; regexes are quoted and correlation is exact end to end.
5. backup recovery trap embedded spaced JSON, the operations command was
   overridden, and consent was not passed into the container. Each attempt
   failed before backup publication; recovery now uses an exact container,
   operations has a fixed entrypoint, and boolean consent is explicit.
6. the first canonical `make check` stopped at Ruff format-check on two changed
   files; only mechanical formatting was applied, then the complete gate reran
   and passed.
7. migration commands against the existing development database found its
   historical revision instead of the Candidate head. That database was not
   modified; a confirmed-absent exact temporary database was created, all four
   gates passed there, and it was dropped exactly.
8. the in-app browser refused the loopback self-signed certificate with
   `ERR_CERT_AUTHORITY_INVALID`; this remains an invalid blocked attempt. The
   authorized continuation used a fresh real Chrome profile and exact SPKI
   trust without system/global trust mutation.
9. raw CDP harness development first encountered a missing REPL WebSocket,
   redirect-response capture, ambiguous sign-in selector, unreliable coordinate
   submit, and an already-visible upload form. Each failed before or at its
   recorded business step; fresh run IDs were used after state-changing attempts.
10. focused Cookie test initially used `get_list` instead of Starlette
    `getlist` (1 failed/55 passed); the test typo was corrected and 56 passed.
11. the first end-to-end TLS run reached logout and exposed a real product bug:
    insecure deletion attributes left a `__Host-` session Cookie in Chrome. The
    API now uses centralized secure expiry helpers and the complete journey was
    rerun from fresh state.
12. a zsh port-splitting helper failed before certificate/container/browser
    creation; its image-only temp root was removed. A later expired-session
    coordinate click issued no request, and a later cleanliness assertion
    initially treated expected Chrome 401/404 network logs as unexplained. The
    harness now uses deterministic activation and only classifies exact
    URL+status-declared negative cases as explained.
13. one exact Chrome process ignored SIGTERM after a failed run; its PID,
    debug port, and profile were matched before SIGKILL, and all child processes
    and listeners were verified absent. Successful runs closed via CDP.
14. the first focused remediation dry-run fixture inherited private `.env`
    configuration; this was a test-fixture error, `.env` was unchanged, and the
    isolated fixture then passed.
15. drill attempts `p2b2_fix_drill_0801a` through `0801c` preserved their first
    failures: negative-reason observation, a diagnostic grep mismatch, then a
    valid non-fresh-database refusal because browser login rows preceded the
    byte-mismatch probe. The probe was moved before those writes; fresh full
    runs `0801d` and final `0801l` passed.
16. Gitleaks correctly flagged the initial synthetic signing-key test literal;
    the fixture was rewritten without key-like material and fresh secret/full
    supply-chain scans passed with zero leaks.
17. the in-app browser again refused the self-signed leaf. No warning bypass was
    used; a fresh Chrome profile with only the exact SPKI continued. One SPA
    load-event wait timed out after successful navigation; page state and CDP
    telemetry confirmed success. Chrome updater/GCM process-global messages
    were not app-page errors.
18. the first final Alembic check accurately found the shared development
    database at `7f3a2b9c4d1e`; it was not migrated. A first isolated command
    omitted the explicit env-file setting and therefore did not upgrade; that
    empty database was dropped. Fresh `p2b2_fix_alembic_0801k` then passed and
    was dropped exactly.
19. the first F-02-01 focused run passed all 42 tests but Ruff found one
    overlong test line and format-check requested one mechanical rewrite; only
    formatting changed, then all focused gates passed.
20. the first isolated final-remediation Alembic command used invalid SQL shell
    quoting and failed before database creation; the corrected confirmed-absent
    database passed and was dropped.
21. the final-remediation in-app browser again refused the self-signed leaf.
    No interstitial or global bypass was used; the dedicated exact-SPKI Chrome
    run passed. A later optional telemetry probe had no Node WebSocket and
    produced no evidence or product action; protocol/UI evidence remained the
    acceptance basis.
22. the first exact-root cleanup command was rejected before execution because
    it used an `rm -rf` form; the same three verified absolute RUN_ID paths were
    removed with bounded `find -depth -delete`.

No failed attempt was relabeled as a pass. Successful browser, recovery,
artifact, migration, and security gates used fresh IDs and complete cleanup.

## 11. Cleanup

- Probe, canonical drill, artifact, migration, and browser attempts'
  containers, networks, volumes, local images, databases, secret roots, backup
  roots, and temporary evidence were removed by exact ownership.
- Every dedicated Chrome process/profile, debug listener, certificate, key,
  SPKI file, and CDP helper was removed. macOS Keychain/system trust was never
  changed.
- Existing in-scope and unrelated local Compose projects and unknown
  ports/processes were not touched.
- No real provider, domain, external account, public resource, or production
  data existed to clean.
- Final-remediation attempts `p2b2finala_0802a`, `p2b2finald_0802a`,
  `p2b2finalb_0802a`, and `p2b2finalm_0802b` have no owned process, listener,
  container, network, volume, image, database, Secret/backup root, browser
  profile, certificate, signing key, or temporary evidence remaining.

## 12. Candidate Manifest and Hashes

- Deterministic manifest:
  `docs/progress/phase-2b-2-candidate-manifest.txt`.
- It includes the exact baseline, staged count, tracked/untracked counts, every
  non-manifest Candidate leaf's byte length/SHA-256, tracked binary-patch hash,
  exact porcelain-status hash, and sorted Candidate-entry payload hash.
- The manifest excludes only its own recursive row. Its final file SHA-256 is
  reported externally with the handoff and is verified after generation.

## 13. Final Repository State

- Branch remains `main`; HEAD/tree/commit count remain the verified baseline.
- Alembic remains the single unchanged head `2b1c4d5e6f70`; no migration was
  added.
- Candidate files are unstaged and uncommitted. No add, commit, push, tag, or PR
  was performed.
- The final worktree is the verified 40-entry starting Candidate plus three
  newly modified tracked files: 24 tracked modified, 19 untracked, 43 status
  entries, staged 0.

## 14. Residual Risks

- Real IdP/client ownership, managed PostgreSQL/S3/IAM, certificate automation,
  DNS/domain, secret manager, deployment/incident ownership, independent backup
  storage, production RPO/RTO, monitoring/on-call, retention/legal rules, and
  cutover remain unselected and unverified.
- The local self-signed certificate, synthetic OIDC, MinIO, tiny data set, and
  measured 8-second recovery prove mechanisms, not provider interoperability,
  scale, durability, or a production SLO.
- Application-level quiescence temporarily rejects writes. A real deployment
  needs an independently reviewed traffic-drain and backup scheduler design.
- Process-scoped SPKI trust proves this exact synthetic certificate/browser
  combination only; it does not prove a selected production CA, managed
  browser fleet, certificate rotation automation, or provider interoperability.
- HMAC key version creation, backup-to-key inventory, rotation, availability,
  revocation, and retirement remain manual operator responsibilities until a
  real Secret Manager and backup lifetime policy receive separate authorization.
- Independent security/operations review and Git sealing remain required.

## 15. Exact Next Action

Hand this exact unstaged Candidate and deterministic manifest to a fresh
independent Phase 2B-2 security/operations reviewer. Do not stage, commit, seal,
deploy publicly, bind a real domain, provision real/paid services, or start
another phase unless that independent review returns an explicit passing
verdict and separate project control authorizes the next action.
