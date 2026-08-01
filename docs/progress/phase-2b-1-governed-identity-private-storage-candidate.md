# Phase 2B-1 — Governed Identity, Authorization, and Private Storage Candidate

Candidate state: `REMEDIATION_IMPLEMENTED_READY_FOR_INDEPENDENT_REVIEW`<br>
Date: 2026-08-01<br>
Repository: `/Users/danke/Developer/CreativeDeploy`

## 1. Verdict

`PHASE_2B_1_REMEDIATION_IMPLEMENTED_READY_FOR_INDEPENDENT_REVIEW`

The authorized identity, authorization, private object storage, database-role,
migration, frontend, test, artifact, browser, supply-chain, and cleanup work is
implemented as an unstaged/uncommitted Candidate.

This is not independent approval, Git sealing, or a production-ready statement.
Phase 2B-2 was not started. No AI, OCR, Agent, RAG, or visual-model capability
was added.

## Final Remediation: F-01 and F-02

The remediation began by reproducing both independent Blocking Medium findings
against the exact original Candidate. A signed token with valid issuer, audience,
nonce, `exp`, and `nbf` but an hour-old `iat` was accepted. A simulated legacy S3
copy could return success and permit a database update after writing corrupted
destination facts because it did not perform a post-write HEAD.

- F-01 root cause: OIDC validation delegated lifetime primarily to `exp` and had no
  required, configured maximum age for `iat`. The client now requires numeric finite
  `iat`, captures time once, applies a default 300-second maximum age and 30-second
  skew with strict safe ranges, and retains signature/issuer/audience/nonce/`exp`/`nbf`
  checks behind one stable non-sensitive error.
- F-02 root cause: the legacy copy path could reuse only pre-write facts. The S3
  adapter now performs a fresh destination HEAD after PUT and verifies size,
  controlled SHA-256 metadata, and content type before returning a receipt. Existing
  exact objects resume idempotently; mismatches and HEAD failures refuse the database
  update while preserving the source and target for safe retry. ETag is not used as a
  checksum.

Remediation files are limited to OIDC configuration/client wiring and tests, S3 copy
verification and migration-tool tests, artifact configuration/smoke isolation, the
example environment, Make environment denylist, and these existing Candidate/contract/
ledger/evidence/Manifest records. Revision `2b1c4d5e6f70` and its hash are unchanged.

Remediation verification:

- OIDC focused: 25 passed; S3 adapter plus migration tool: 16 passed; combined: 41
  passed.
- Direct auth regression: 51 passed; direct storage regression: 39 passed.
- Canonical `make check`: Ruff/format 91 files, mypy 64 files, API unit 290 passed
  (66% coverage), real PostgreSQL integration 54 passed, Web 13 files/154 tests,
  lint/typecheck/build PASS, Vite 98 modules.
- Artifact `phase2b1_remediation_artifact_02`: PASS, including a real MinIO legacy
  copy, mandatory post-write verification, exact-object resume, session expiry,
  restart, roles, and exact cleanup.
- In-app browser `phase2b1_remediation_browser_03`: Owner A login/project/private
  upload, reviewer pre-assignment denial, assignment, private preview with zero Owner
  controls, API/OIDC/Web/MinIO restart persistence, immediate revocation, Owner B safe
  unavailable response, logout, and empty console warning/error set.
- Final isolation `phase2b1_remediation_isolation_04`: PASS and exact cleanup.
- Manifest-inclusive Gitleaks `phase2b1_remediation_finalscan_05`: no leaks;
  pip-audit and pnpm production audit: no known vulnerabilities; immutable-reference
  gate: 3 Actions/9 container references PASS; `git diff --check`: PASS.

This remains implementer evidence. It is not independent approval or Git sealing and
does not authorize Phase 2B-2.

## 2. Verified Baseline

- Git top-level: `/Users/danke/Developer/CreativeDeploy`
- Branch: `main`
- HEAD: `771b53914f51245d6c62c569e40ddd061ae7ec6e`
- Tree: `26f395ef6c217bc7f5f997309c12893618ce5634`
- Commit count: `22`
- Starting worktree: clean
- Starting Alembic head: `7f3a2b9c4d1e`
- Starting database: PostgreSQL, nine business tables plus `alembic_version`
- Starting object storage: private local filesystem, development/test only

The similarly named `/Users/danke/Documents/creativedeploy` directory was not
used for implementation. Phase 2A-1 was not reopened or re-reviewed.

The private `.env` contained a partial legacy PostgreSQL component set and did
not describe the active Compose service. It was preserved unchanged. Real
database verification used a process-only URL read from the exact active
CreativeDeploy PostgreSQL container and an empty temporary env file.

## 3. Architecture Decisions

- ADR-0008 defines provider-neutral OIDC, internal identity, project roles,
  API-only S3 delivery, fail-closed production configuration, database-role
  separation, migration guard, and threat boundaries.
- External identity is unique by `issuer + subject`; profile email/name never
  authorizes.
- Owner remains the existing project owner fact; reviewer is one explicit
  project membership. The workflow state machine is unchanged.
- Local OIDC and MinIO are synthetic development/CI services, not real provider
  selections.
- No public/signed URL, deletion, retention, owner transfer, or workflow role
  expansion exists.

## 4. Authentication

- Authorization Code + S256 PKCE with discovery/JWKS and backend code exchange.
- Strict state, browser binding, nonce, redirect, issuer, audience, RS256
  signature, `exp`, `nbf`, bounded `iat`, subject, and profile validation.
- One-time database flow consumption rejects callback replay.
- Opaque server session and CSRF hashes; prior-session rotation prevents
  fixation; logout revokes the server session.
- Browser receives HttpOnly session and flow cookies, never provider tokens.
  Production uses Secure `__Host-` cookies and HTTPS-only OIDC configuration.
- `/auth/login`, `/auth/callback`, `/auth/session`, and `/auth/logout` are
  implemented.
- IdP discovery/protocol failure displays an explicit retryable login error and
  never substitutes Demo identity.
- Production refuses missing OIDC fields, Demo Principal, insecure URLs, and
  local backchannel rewriting.

## 5. Authorization

- Newly OIDC-created projects store the stable internal user UUID as Owner.
- Owner can create/mutate a project and manage reviewer assignment.
- Assigned reviewer can list/read that project and private images and invoke
  only the already-existing permitted human review operations.
- Reviewer cannot upload/replace/fork/save/submit or manage membership.
- Owner B and unassigned users receive the same safe 404 for project, image,
  membership, and region resources.
- Membership removal is checked on the next request, including an existing
  authenticated session.
- `(project_id, user_id)` uniqueness plus locked/idempotent service behavior
  makes repeated/concurrent assignment converge on one row.
- Frontend role hiding mirrors the API policy but is not the security boundary.

## 6. Private Object Storage

- S3-compatible adapter verifies a private canonical-user ACL and refuses
  bucket policies.
- Controlled immutable keys, exclusive staging, `If-None-Match: *`, content
  length/type, SHA-256 request/metadata, and post-write HEAD verification.
- Existing ImageAsset checksum/size/type/project/rights/role/history facts are
  preserved.
- Browser bytes are streamed only from the authenticated project content API.
  Responses expose no bucket, key, endpoint, credential, ETag, VersionId,
  provider URL, or `X-Amz-*` data.
- Adapter intentionally has no public or presigned URL operation.
- Upload failure is never returned as success. Receipt-bound compensation
  refuses uncertain ownership/reference cases.
- Legacy tool defaults to dry-run, copies and verifies, updates only an exact
  unchanged row, supports idempotent resume, and reports `source_deleted=0`.

## 7. Database Migration and Roles

- Revision: `2b1c4d5e6f70`
- Parent: `7f3a2b9c4d1e`
- Migration SHA-256:
  `cb2356309f88187da26d7f1b061a716600a8cb6397333f54683775a00194f322`
- Added tables: `user_accounts`, `external_identities`,
  `project_memberships`, `oidc_login_flows`, `auth_sessions`
- Upgraded schema: fourteen business tables plus `alembic_version`
- Existing ImageAsset rows are untouched; only the provider constraint gains
  `s3`.
- Upgrade, empty downgrade, re-upgrade, current, heads, and autogenerate check
  passed on isolated real PostgreSQL.
- Downgrade with any governed identity/session/membership fact or S3 reference
  fails closed with SQLSTATE `55000`; it does not delete data.
- Admin provisioner creates/updates distinct NOSUPERUSER roles. Migrator owns
  the schema/DDL; runtime has table DML and sequence usage only.
- Artifact proof: migrator owned all fourteen business tables; runtime DML
  succeeded and runtime CREATE/DDL was refused.

## 8. Frontend UX

- Login entry, in-progress state, provider/sign-in failure with retry, current
  user, logout, and expired/anonymous session behavior.
- Auth guard preserves the requested local route.
- Owner and assigned-reviewer project lists use server-returned access roles.
- Owner-only reviewer manager requires explicit interaction before fetching
  assignable users and supports assignment/removal.
- Reviewer UI keeps private preview and allowed human review surfaces while
  hiding upload, edit, fork/submit, and reviewer-management controls.
- Safe unavailable/unauthorized pages reveal no project or image facts.
- Existing PaintPilot shell, route shape, visual language, and workflow states
  are preserved.

## 9. Tests and Browser Evidence

Canonical `make check` (exit 0):

- Ruff: 91 files, PASS
- mypy: 64 source files, PASS
- API unit: 290 passed, zero skipped/xfail, one known Starlette deprecation
  warning, 66% aggregate coverage
- real PostgreSQL integration: 54 passed, zero skipped/xfail, one known
  Starlette deprecation warning
- Web: 13 files / 154 tests passed
- ESLint, TypeScript, and Vite production build: PASS
- Vite build: 98 modules; generated HTML/CSS/JS successfully

Original implementation focused evidence is retained below; the final remediation
focused counts are recorded in the remediation section above.

Focused:

- OIDC client: 10 passed
- S3 adapter/migration behavior: 5 passed
- governed migration round-trip/unsafe downgrade: 2 passed
- corrected prior-head rollback expectation: 2 passed
- login/provider failure route: included in 16 passing AppRoutes tests

Final artifact `phase2b1_final_20` (exit 0) proved real synthetic OIDC,
callback replay refusal, session rotation, CSRF, explicit database-backed
session expiry, private MinIO upload/API checksum stream, provider non-leakage,
Owner A/B isolation, concurrent and repeated assignment idempotency, two
reviewers on one project, one reviewer on two projects, reviewer private-image
access and an existing READY review action, immediate removal,
logout/expired-session object 401, production fail-closed, role separation,
runtime DDL refusal, restart recovery, database degradation, headers,
non-root/read-only runtime, and exact cleanup.

Real in-app browser `phase2b1_browser_12` proved:

1. Owner A/Owner B/reviewer OIDC login with synthetic users.
2. Owner A project creation and a program-generated 768×768 JPEG upload with
   rights attestation.
3. Private image source used the project API content route, not S3/MinIO.
4. Owner B and the unassigned reviewer received the same unavailable state.
5. After explicit assignment the reviewer saw reviewer role/private preview
   and no upload or reviewer-management controls.
6. After removal a fresh reviewer login received the unavailable state;
   same-session immediate removal is separately proven by artifact smoke.
7. API/IdP/Web/MinIO restart retained the session/project/object.
8. IdP shutdown showed the explicit provider-unavailable UI with no Demo
   identity fallback; retry succeeded after restart.
9. Browser console warning/error set was empty.

## 10. Security and Supply Chain

- Final manifest-inclusive Gitleaks rerun `phase2b1_finalscan_21`: no leaks.
- pip-audit: no known vulnerabilities; unpublished local package explicitly
  skipped.
- pnpm production audit: no known vulnerabilities after a registry retry
  warning.
- Immutable references: 3 Actions and 9 tag-plus-digest container reference
  occurrences, PASS.
- Final attempt isolation `phase2b1_isolation_22`: two parallel Phase 2B-1
  attempts had distinct containers, networks, volumes, database/role names,
  credentials, and exact cleanup.
- `git diff --check`: PASS.
- API/lock hashes:
  - `apps/api/uv.lock`:
    `414278ee4cb05f036a1466118ffd86988072ed5fb8c2d85c8d7e2af272baa1ca`
  - `pnpm-lock.yaml`:
    `c7a6e2eb86d8feb722b1e2fffcafa0db40dc7448a5860fed8066ba62eb7354a9`

## 11. Invalid Attempts

Preserved as failures/invalid attempts, not counted as PASS:

- initial psql quoting error before robust baseline query;
- unit settings run with the example/private env instead of an isolated env;
- frontend lint/test failures from effect state and fetch-count assumptions;
- stale ORM count, Alembic constraint naming, OIDC callback diagnostics,
  identity insert ordering, and strict JSON UUID parsing found by real tests;
- unresolvable MinIO tag/digest attempts before the current pinned reference;
- canonical runs stopped by unchanged partial `.env`, an unavailable legacy
  port, nonexistent `/dev/null` Make env file, two Ruff format findings, and
  two stale migration-head assertions;
- one frontend focused command used a package-relative path twice and found no
  tests; corrected package-relative path passed;
- browser direct post-logout object navigation was blocked by the browser
  client and not treated as application evidence; artifact curl proved 401;
- first browser restart command omitted required smoke variables and did not
  restart services; exact container restart and start-time checks passed;
- first browser cleanup command was rejected by tool safety; exact `unlink`
  and attempt-scoped Compose cleanup passed;
- first final pip-audit query timed out against PyPI; retry passed;
- immutable-reference count and attempt-isolation environment were stale after
  adding MinIO/OIDC/role inputs; both gates were corrected and passed.
- the first manifest-inclusive Gitleaks run classified the API lockfile
  SHA-256 as a generic API key. The established inline allow marker was added
  to that manifest metadata line; the redacted diagnostic found no other
  finding and the exact scan rerun passed.
- the first redacted Gitleaks diagnostic package omitted its destination
  directory, and the first read-only residual database query had invalid shell
  quoting. Neither produced evidence; corrected reruns identified the single
  Manifest false positive and then zero Phase 2B-1 databases or roles.
- the final targeted Ruff format check found one mechanically unwrapped line
  in the immutable-reference validator; Ruff formatted it and the exact check
  rerun passed.
- `make artifact-config-check` was not a real target and produced no evidence;
  the repository target `make artifact-config RUN_ID=phase2b1_config_24
  ARTIFACT_SMOKE_PORT=54724` passed.
- `phase2b1_final_16` exposed a simultaneous-restart race: NGINX could exit
  while its dependencies restarted and had no recovery policy. Long-lived
  services now use validated `unless-stopped`; one-shot jobs do not.
- `phase2b1_final_18` reached the new expiry fixture but the first fixture put
  expiry before creation and was correctly rejected by its database check. The
  rerun used a valid historical-created/now-expired row.

The command ledger records exit codes and the valid reruns.

## 12. Cleanup

- `phase2b1_browser_12`, `phase2b1_final_13`,
  `phase2b1_final_16`, `phase2b1_final_18`, `phase2b1_final_19`,
  `phase2b1_final_20`, `phase2b1_isolation_15_{a,b}`, and
  `phase2b1_isolation_22_{a,b}` containers, networks, volumes, and locally
  built attempt images were removed by exact RUN_ID.
- Program-generated browser fixture and empty temporary env files were removed.
- The retained synthetic `phase2b1_diag_07` diagnostic directory was inspected
  and then removed by its exact path.
- Migration/integration fixtures used unique resources and their exact
  ownership-aware cleanup.
- No unknown process, port owner, Docker resource, database, role, object, or
  user file was deleted.
- The user's `.env` was not edited.

## 13. Candidate Manifest and Hashes

The final Candidate Manifest declares its exact scope as tracked modifications
plus untracked leaf files from porcelain-v1-z. It records status, bytes,
SHA-256, and repository-relative path, excluding only itself to avoid recursive
hashing.

- Manifest:
  `docs/progress/phase-2b-1-candidate-manifest.txt`
- Migration SHA-256:
  `cb2356309f88187da26d7f1b061a716600a8cb6397333f54683775a00194f322`
- Manifest SHA-256: reported in the external handoff after final generation
- Exact payload/status/diff hashes: recorded in the Manifest and external
  handoff

## 14. Final Repository State

- Branch: `main`
- HEAD: `771b53914f51245d6c62c569e40ddd061ae7ec6e`
- Tree: `26f395ef6c217bc7f5f997309c12893618ce5634`
- Commit count: `22`
- Staged paths: `0`
- Candidate: tracked modifications plus untracked files, all intentionally
  unstaged
- No add, commit, push, tag, PR, reset, checkout, clean, or stash
- No production deployment or public endpoint

Exact final tracked/untracked counts are frozen in the Manifest.

## 15. Residual Risks

- No independent reviewer has yet reproduced or approved this Candidate.
- The synthetic local IdP does not prove interoperability with a selected
  enterprise provider or its key-rotation/tenant policy.
- MinIO proves the private S3-compatible contract, not a selected managed
  provider, IAM policy, backup, restore, retention, or incident process.
- Real secret management, domain/TLS, monitoring, audit retention, operational
  revocation, data migration planning, and deployment ownership are unresolved.
- Two framework deprecation warnings remain known and non-blocking.
- The user-owned `.env` retains historical partial PostgreSQL configuration and
  was intentionally not modified.
- Browser implementation evidence is not independent review evidence.

## 16. Exact Next Action

Stop implementation. Give this unstaged Candidate, ADR/contracts, runbook,
command ledger, browser/validation summaries, and exact Manifest to a fresh
read-only independent Phase 2B-1 Product & Security reviewer.

The reviewer should reproduce focused auth/storage/migration tests, canonical
validation, isolated Alembic upgrade/downgrade/current/heads/check, final
artifact smoke, Owner/reviewer browser closure, supply-chain checks, hashes, and
exact cleanup without modifying the Candidate.

Only after a separate independent PASS may the user authorize Git sealing.
Do not start Phase 2B-2 and do not add AI, OCR, Agent, or RAG.
