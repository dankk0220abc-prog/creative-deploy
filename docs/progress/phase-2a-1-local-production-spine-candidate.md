# Phase 2A-1 — Final Remediation Implementation Candidate

Candidate state: `IMPLEMENTED_READY_FOR_FOCUSED_INDEPENDENT_REVIEW`<br>
Date: 2026-07-31<br>
Repository: `/Users/danke/Developer/CreativeDeploy`

## 1. Verdict

`PHASE_2A_1_REMEDIATION_IMPLEMENTED_READY_FOR_FOCUSED_INDEPENDENT_REVIEW`

F-001 through F-010 have implementation, focused-test, canonical-test,
artifact, browser, supply-chain, and cleanup evidence. This is an implementer
handoff only. It is not independent approval, Git sealing, production
readiness, or authorization for a later product phase.

## 2. Verified Starting Candidate

- Branch `main`
- HEAD `f0563dc1c5800f9d1ec35efaac77d169ab08c6da`
- Tree `6a3a4b6d8ca2a73f4e62c4948f39239535e9949b`
- Commit count `21`
- Staged/tracked-modified/untracked-leaf `0 / 22 / 26`
- Alembic head `7f3a2b9c4d1e`
- Starting Candidate Manifest SHA-256
  `5d728b060f9c432fd0e78bb687fc3bbd3765776e315aac67f64600a158705de6`
- Starting tracked binary patch SHA-256
  `de724afe57873ae06070e0f172338b7b798243d7ee4dfcab1a46ab738386e3a1`
- Starting exact porcelain-v1-z SHA-256
  `f8db9439da42aad4e0902c4f0a36047fddc6900e731c7f632295ece69929aef2`
- Independent review Attempt 2 verdict remains
  `PHASE_2A_1_INDEPENDENT_REVIEW_FAIL_REMEDIATION_REQUIRED`.

The remediation began from that exact failed Candidate. Reviewer evidence under
the attempt-unique `/tmp` directory was read-only and remains preserved.

## 3. Facts / Inferences / Unknowns

Confirmed facts:

- A real pointer event over the child SVG image was rejected by the former
  root-target equality check.
- The prior Candidate did not provide acceptable live-browser visual closure.
- New isolated-browser evidence shows the real source image, paint area,
  exclusion hatch, selected outline, opacity, zoom/Fit, history, refresh, and
  mobile input path from the running artifact.
- Live DOM evidence records the source image, polygon coordinates, ordering,
  viewBox, computed presentation, and lack of clipping/hidden presentation.
- The persisted opacity contract remains 10–100%; zero is tested only as a
  defensive presentation value and is not made persistable.

Inference:

- The old empty captures combined an invalid evidence path with SVG
  presentation defects. Because that old browser session is not reproducible,
  the relative contribution of its capture compositor versus presentation
  defects cannot be isolated retroactively.

Unknown until the next review:

- Whether an independent reviewer reproduces every gate from the regenerated
  Manifest.
- Real deployment/authentication/object-storage choices; they remain outside
  this Phase.

## 4. F-001 Remediation

- Pointer coordinates are derived from `event.currentTarget`, a live
  `SVGSVGElement`, `createSVGPoint()`, and
  `getScreenCTM().inverse()`.
- Image, root SVG, and ordinary non-interactive overlay targets can add points.
  Explicit region/vertex interactive nodes remain excluded.
- Only primary, primary-button input is accepted; pointer capture and default
  prevention remain scoped to the drawing interaction.
- Tests cover image/root targets, first and subsequent points, explicit overlay
  exclusion, zoom/resize transforms, repeated input, and a 320 px touch path.
- Real browser: the first image click produced normalized point
  `884615,529259` at 320×844; desktop paint and exclusion polygons were created
  and saved through the UI without API fixture injection.

## 5. F-002 Remediation

- The SVG now has explicit full-surface width/height and a single
  `0..1,000,000` image/polygon coordinate system.
- The invalid non-scaling-stroke presentation was removed; zoom-dependent
  stroke width is bounded in user space.
- The accepted proof is a current live-browser raster plus an exact crop of
  that unmodified raster, not an offline reconstruction:
  `remediation-final-20260731/10-live-svg-browser-raster.jpeg` and
  `10-live-svg-element-crop.png`.
- Paired live evidence includes SVG outerHTML, DOM facts, computed polygon
  presentation, and browser-derived pixel samples.
- The real artifact retained correct visuals after zoom/Fit, API/Web restart,
  deep-link reload, history viewing, current return, and mobile resize.
- Console warning/error sets were empty. Network evidence contains only the
  intentional Owner B 404 and separately controlled HTTP probes.

## 6. F-003 Remediation

- Pattern generation retains the original region index, so paint and exclusion
  colors no longer shift after filtering.
- Paint uses `#63b3a6`; the second ordered exclusion base uses `#d2a45f`.
- Both exclusion pattern base and hatch stroke use the region opacity.
- The selected white outline remains independently visible at reduced/zero
  presentation opacity; unselected outlines remain dark.
- Automated presentation coverage includes 0%, the persisted 10% lower bound,
  30%, and 100%, plus selected/unselected identity.
- Real browser evidence verifies 10%, 30%, and 100%; the saved final exclusion
  opacity is 30%. Zero remains outside the sealed persistence contract.

## 7. F-004 Remediation

- Any present `POSTGRES_*` value requires the complete host/user/password/
  database/port set; partial and whitespace-only values fail closed.
- An explicit URL and complete components must be semantically equivalent.
- Production requires an explicitly supplied
  `postgresql+psycopg://` `DATABASE_URL`; derived components cannot satisfy it.
- Error output identifies configuration fields without printing the password.
- Make targets explicitly map `ENV_FILE` to `CREATIVEDEPLOY_ENV_FILE`; config
  validation runs through the locked project Python environment.
- Runtime, Alembic, readiness, and integration tests share the same resolved
  settings policy. No migration, ORM, or database model changed.

## 8. F-005 Remediation

- Every trusted-host entry is normalized and must be exact; any wildcard,
  empty entry, invalid port, invalid IPv4/IPv6 form, or unnormalizable value is
  rejected.
- Case, trailing dot, explicit port, loopback, IPv4, and bracketed IPv6 are
  handled deterministically.
- Application middleware evaluates Host and forwarded-host consistency rather
  than trusting a forwarded bypass.
- Unknown or inconsistent Host values return a stable 400.
- Focused tests cover allowed and denied exact hosts, wildcard/suffix/prefix
  tricks, case/trailing-dot/port forms, and forwarded-host cases.

## 9. F-006 Remediation

- Application middleware and error handlers provide `Cache-Control: no-store`
  for the API boundary.
- NGINX hides any upstream Cache-Control value and emits one defensive no-store
  policy for generic API/readiness responses and its own rejections.
- Artifact probes verified no-store on 200, 201, 404, 422, 413, and invalid-Host
  400 responses. Unit tests cover validation and controlled server errors.
- HTML remains no-store, fingerprinted assets remain immutable, and the
  HTTP-only artifact still emits no HSTS.

## 10. F-007 Remediation

- Alembic moved into a dedicated migration dependency group.
- The migration builder uses frozen, no-default-group, migration-only
  installation from `uv.lock`; no floating installer step was added.
- The final migration image contains Alembic and psycopg but not pytest,
  pip-audit, Ruff, or mypy.
- Runtime remains non-root with the minimal application/migration file set and
  no tests, private environment file, or private data.
- No migration revision was added; the database and script head remain
  `7f3a2b9c4d1e`.

## 11. F-008 Remediation

- The two rejected Safari captures were removed from the repository and
  retained in this attempt's exact quarantine directory for traceability.
- A new isolated in-app browser session generated CreativeDeploy-only,
  synthetic-data evidence. It was finalized after capture.
- The accepted browser evidence contains no unrelated project tab, account,
  secret, or private user file.
- Invalid clip/full-page capture attempts are outside the Candidate in the
  attempt-unique temporary directory.
- The reviewer evidence directory was not modified or deleted.

## 12. F-009 Remediation

- `RUN_ID`/`ATTEMPT_ID` is validated or safely generated and drives Compose
  project, containers, network, volumes, database principal/database,
  temporary directory, private storage, artifact images, and Gitleaks identity.
- The artifact Web port is dynamically allocated unless explicitly overridden.
- Exit traps remove only exact attempt resources; there is no shared hardcoded
  project or unnamed scan container.
- CI derives its run identity from run, attempt, and job context.
- `RUN_ID=focused_f009 make artifact-isolation-test` created two distinct
  PostgreSQL attempts, removed A while B remained, then removed B. PASS.

## 13. F-010 Remediation

Actions are pinned by verified full commit SHA with readable version comments:

- checkout v4.4.0:
  `11d5960a326750d5838078e36cf38b85af677262`
- setup-uv v7.6.0:
  `37802adc94f370d6bfd71619e3f0bf239e1f3b78`
- setup-node v6.5.0:
  `249970729cb0ef3589644e2896645e5dc5ba9c38`

Executable container inputs retain a readable tag and verified index digest:

- Python:
  `sha256:9d7f287598e1a5a978c015ee176d8216435aaf335ed69ac3c38dd1bbb10e8d64`
- uv:
  `sha256:93b61e21202b1dab861092748e46bbd6e0e41dd84f59b9174efd2353186e1b47`
- Node:
  `sha256:7c70d1235c0b4c2bc9eeed5393d19f1bbdde6885ba0d58ba62bb385d7b0f3ff1`
- NGINX:
  `sha256:4655ddff4704d6b6c85f5a5862b5d0840941fcc95a4f4668f04b1d6f85858e7c`
- PostgreSQL:
  `sha256:742f40ea20b9ff2ff31db5458d127452988a2164df9e17441e191f3b72252193`
- Gitleaks:
  `sha256:c00b6bd0aeb3071cbcb79009cb16a60dd9e0a7c60e2be9ab65d25e6bc8abbb7f`

`verify_immutable_references.py` fails closed on mutable Actions or executable
container references and passed with 3 Actions / 8 reference occurrences.
Artifact build and smoke succeeded with the pinned inputs.

## 14. Additional Advisory Fixes

- Implemented explicit `ENV_FILE` propagation and locked project-Python config
  execution from the review advisory.
- Added one centralized, secret-safe configuration audit and a real database
  probe rather than relying on parsing shell output.
- Added explicit smoke failure messages for the production database policy.
- Updated the runbook with unique-run operation, isolation regression, API
  cache probes, migration dependency inventory, and immutable-reference gate.

## 15. Modified Files

Final status contains 24 tracked modifications and 71 untracked leaf files
(95 exact paths), all represented in the regenerated Manifest except the
Manifest itself.

- Frontend/product behavior: Region workspace, image manager, shell/pages,
  styles, and focused tests.
- API/config/security: settings, middleware, handlers/factory, database
  plumbing, focused unit/integration tests, dependency groups, and lockfile.
- Artifact/CI: Makefile, Compose files, Dockerfiles, NGINX policy, workflow,
  secret scan, artifact smoke, attempt isolation, immutable-reference check,
  and artifact validation.
- Documentation/evidence: environment example, README/AGENTS, ADR, Phase plan,
  runbook, Candidate, isolated browser evidence, validation summary, evidence
  index, and Manifest.

The Manifest is the authoritative exact path/byte/SHA list.

## 16. Focused Tests

- Initial F-001 regression: 1 failed / 150 passed, preserving the image-target
  defect before repair.
- Final Region workspace file: 14 passed.
- Final complete Web suite: 13 files / 153 passed.
- Focused config/Host/no-store backend suite: 67 passed.
- Migration dependency inventory: required modules present, four forbidden
  development tools absent.
- Attempt isolation: PASS.
- Immutable references: PASS.
- No existing assertion was weakened and no snapshot was bulk-updated.

The first zero-opacity test injection was clamped by the production range
minimum. That attempt is preserved; the valid rerun injects an impossible
presentation value only after lowering the test DOM minimum, without changing
the product contract.

## 17. Canonical Verification

- `make check ENV_FILE=.env.example`: exit 0
- Ruff: 73 files; mypy: 50 source files
- API unit: 249 passed, 1 known framework deprecation warning, 73% coverage
- PostgreSQL integration: 53 passed, 1 known framework deprecation warning
- Web: 153 passed
- ESLint / TypeScript: PASS
- Vite: 93 modules, production build PASS
- Migration current/heads/history/check: exit 0; one head
  `7f3a2b9c4d1e`; four revisions; no new operations
- `RUN_ID=remed_20260731_a1 make artifact-build`: PASS
- `RUN_ID=remed_20260731_a1 make artifact-smoke`: PASS
- `git diff --check`: PASS

## 18. Browser Evidence

Runtime path: isolated Browser → pinned production NGINX/Web → production API
→ isolated PostgreSQL/private volume. Browser logs identify Chrome 150.0.0.0.

Verified through the real UI:

1. Project creation and rejected text upload with valid retry.
2. Three distinct synthetic image roles, rights attestations, and READY.
3. First point, complete paint polygon, complete exclusion polygon, selection.
4. Opacity 10/30/100, zoom, Fit, save v1/v2, submit v3.
5. Historical v1 read-only, return current, restart/deep-link persistence.
6. Owner B safe 404 and Owner A restoration.
7. Fork v2 into current v4 draft while submitted v3 remains in history.
8. 320/375/390 widths with no horizontal overflow; 320 touch first point.
9. Empty console warning/error set and explained network status set.

Synthetic source SHA-256:

- primary:
  `e4f4161284e68f2d1a0794b69b48b6b0c2605f974ca763a33dbf81e324d67db2`
- reference back:
  `1422e455186960dc4f946b394b5757db4b111050b3c2ab16fde80d950eced7f1`
- reference angle:
  `5fbf37d05532843baed0bdccb4f097de29355bc4afbcbc1080985fd613537b07`

The evidence index records hashes for all 43 evidence payload files.

## 19. Supply Chain Evidence

`RUN_ID=remed_20260731_a1 make supply-chain-check` passed:

- Gitleaks: no leaks.
- pip-audit: no known vulnerabilities; the unpublished local package was
  explicitly skipped.
- pnpm production audit: no known vulnerabilities after one recorded network
  retry.
- Immutable reference check: 3 Actions / 8 container references, PASS.
- No external cloud, authentication, telemetry, AI, or storage SDK was added.

## 20. Invalid Attempts

Preserved and not used as PASS:

- default private environment: partial legacy PostgreSQL set rejected;
- nonexistent `/dev/null` environment-file selection rejected;
- empty isolated environment: real database probe rejected unusable URL;
- first valid root run: two Ruff formatting failures;
- one unrelated Web fetch-count race, followed by full Web and root reruns;
- first defensive zero-opacity injection clamped to 10%;
- first artifact smoke: inherited empty URL changed the expected negative-test
  message;
- first pnpm audit: `ECONNRESET`;
- first evidence index: temporary output recursively entered its own scope;
- first final-document Gitleaks run: the labelled API lockfile SHA-256 in the
  Candidate and Manifest produced two generic-key false positives;
- first final diagnostic cleanup command: rejected by tool safety policy before
  execution, then replaced by exact per-directory deletion;
- clipped/responsive-mutating browser capture modes.

The complete affected gate reran successfully after every valid correction.

## 21. Cleanup

Exact final checks found:

- task containers/volumes/networks/locally built images: `0 / 0 / 0 / 0`;
- exact scan container and isolation A/B containers: `0`;
- listeners on task ports 55000, 55001, and 55002: `0`;
- exact browser artifact database/storage resources: removed;
- private `.env` hash and byte size: unchanged;
- two rejected captures: exact quarantine outside the repository;
- reviewer evidence: preserved.

No global Docker catalog, unrelated process/listener, or user browser tab was
modified.

## 22. Candidate Manifest and Hashes

Hash algorithms and scope are declared in the Manifest/evidence index:

- final tracked `git diff --binary` SHA-256:
  `4f2e6f6e566e132bcb477e140794f24660d628bccb8f9a683f3e55d7fa5cbdc7`
- exact `git status --porcelain=v1 -z --untracked-files=all` stdout SHA-256:
  `edabcdac0b7723f0b512b3b01544c9392684140d08c489f399cbbfacc184a59a`
- migration aggregate SHA-256:
  `b2b93eb84aa22792c5d645ca69e478f88270639d1af6c5e4ef71856903343188`
- API lockfile SHA-256: <!-- gitleaks:allow -->
  `098bf7f8a84c5afe4334e3c1fba72746fc5c4fbb8c389a1a840543b28ff98e21`
- Web lockfile SHA-256:
  `c7a6e2eb86d8feb722b1e2fffcafa0db40dc7448a5860fed8066ba62eb7354a9`
- evidence index SHA-256:
  `a7d10066803c494875fb80d9c36b2296bc040af6a47852ef4cf4ef413bcd4f0a`

The Manifest excludes itself to avoid recursive hashing. Its final file
SHA-256 is therefore reported in the external handoff, not embedded in this
payload file (which the Manifest hashes).

## 23. Final Repository State

- Branch `main`
- HEAD `f0563dc1c5800f9d1ec35efaac77d169ab08c6da`
- Tree `6a3a4b6d8ca2a73f4e62c4948f39239535e9949b`
- Commit count `21`
- Staged files `0`
- Tracked modified `24`
- Untracked leaf files `71`
- No commit, push, tag, PR, reset, checkout, clean, or stash
- No new migration revision, ORM schema, external service, or AI feature
- Private `.env` unchanged

## 24. Residual Risks

- No independent reviewer has verified this regenerated Candidate yet.
- The private local environment retains legacy partial configuration; it was
  deliberately not edited. Canonical validation uses the complete example
  environment.
- Two known framework deprecation warnings remain non-blocking.
- Persisted opacity remains 10–100%; defensive zero rendering is test-only.
- Real production still requires separate user decisions for authentication,
  private object storage, domains/TLS/proxy trust, secrets, monitoring,
  backup/restore, retention, and incident ownership.
- Browser evidence is implementation evidence and must not be treated as an
  independent Gate C approval.

## 25. Exact Next Action

Stop implementation. Give the regenerated Candidate, Manifest, evidence index,
and reviewer Attempt 2 findings to a fresh read-only independent Phase 2A-1
Product & Security reviewer. The reviewer must reproduce the focused gates,
canonical check, pinned artifact build/smoke, live-browser polygon loop,
supply-chain gates, exact cleanup, and hashes without modifying the Candidate.
Only a later explicit user authorization after an independent PASS may begin a
separate Git-sealing action. Do not start another product phase or authorize AI.
