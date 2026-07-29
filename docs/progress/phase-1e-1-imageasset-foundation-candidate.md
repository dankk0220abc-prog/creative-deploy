# Phase 1E-1 — ImageAsset Foundation Candidate Evidence

- Candidate Status: `PHASE_1E_1_REMEDIATION_IMPLEMENTED_READY_FOR_INDEPENDENT_REVIEW`
- Date: `2026-07-29`
- Baseline HEAD: `881a2735aeb47ae8edbbd4810eb19f52e46232ff`
- Baseline Subject: `docs(progress): close phase 1d vertical slice`
- Branch: `main`
- Commit Created: `NO`
- Staged: `NO`
- Pushed / tagged: `NO`
- Independent Review: previous security review `FAIL`; remediation rereview `NOT_PERFORMED`

## Candidate boundary

This candidate implements the original, private, immutable `primary_mvp_input` ImageAsset
slice only. It does not implement ImageQualityAssessment, AI analysis, normalized copies,
regions, inventory, public access, deletion, production storage, or real authentication.
User `rights_attestation_status=confirmed` records a declaration and is not legal verification.

## Frozen decisions

- ADR:
  `docs/decisions/ADR-0004-imageasset-physical-storage-and-version-boundary.md`
- Physical fields:
  `docs/architecture/paintpilot-imageasset-physical-data-dictionary-v0.1.md`
- Plan:
  `docs/progress/phase-1e-1-imageasset-foundation-plan.md`
- Historical Revision hash was checked before work and the file was not modified.

## Implementation summary

- One new `image_assets` table and nullable guarded PaintProject current-image reference.
- Composite owner/project/current/lineage Foreign Keys and one-current partial uniqueness.
- Provider-neutral image storage port plus explicitly non-production local adapter.
- Streamed SHA-256 staging, atomic no-replace object publication, typed collision handling,
  publish receipts, identity/reference-checked compensation, orphan detection, and
  traversal/symlink defenses.
- Deterministic signature, declared-type, decoder, complete-load, static-image, dimensions,
  pixel-count, metadata, and corruption checks.
- Owner-scoped upload/list/detail/private-content routes, safe error envelopes, retained
  replacements, and command replay/conflict.
- Accessible main-image slot, rights declaration, upload progress, safe retry, duplicate
  suppression, private preview, history, and workflow-locked replacement UI.

## Verification ledger

The final candidate update must preserve invalid attempts rather than rewriting history:

| Gate | Result |
| --- | --- |
| Baseline identity, clean scope, historical Revision SHA-256 | `PASS` |
| First Ruff/mypy run | `INVALID_ATTEMPT` — three implementation findings were fixed |
| First backend unit run | `INVALID_ATTEMPT` — historical exact model/migration inventories required a Phase 1E-1 update |
| PostgreSQL command using repository `.env` | `INVALID_ATTEMPT` — stale port 5432 authentication; no schema change |
| First migration integration reruns | `INVALID_ATTEMPT` — old head assertion, then fixture constraint target; corrected and fully rerun |
| First ImageAsset API integration reruns | `INVALID_ATTEMPT` — multipart fixture encoding, JSONB replay decoding, then ORM/AsyncConnection row handling; corrected and fully rerun |
| First full frontend run | `INVALID_ATTEMPT` — five historical request-count assertions did not include the new image-history request |
| First full repository `make check` | `INVALID_ATTEMPT` — two new Python files required mechanical Ruff formatting; the complete gate was restarted |
| Frontend list-card focused rerun | `INVALID_ATTEMPT` — one new assertion matched both the status badge and review-gate label; the assertion was narrowed and fully rerun |
| First final-manifest read-only command | `INVALID_ATTEMPT` — zsh special variable `path` overwrote that child shell's PATH; no file was written and its cached-state line was discarded |
| Frontend lint + typecheck + 113 tests + production build | `PASS` |
| Focused ImageAsset real PostgreSQL/API suite | `PASS` — 4 tests |
| Backend Ruff + mypy | `PASS` |
| Isolated migration head/base/head and `alembic check` | `PASS` |
| Development database current/head/check | `PASS` |
| Final complete `make check` | `PASS` — 178 backend unit, 34 PostgreSQL integration, 113 frontend tests, production build |
| Real browser desktop and 390×844 | `INVALID_ATTEMPT` — upload used a prohibited private-photo fixture; evidence project/object were precisely cleaned |
| Synthetic JPEG/PNG/WebP real-browser continuation | `PASS` — real Vite/FastAPI/PostgreSQL/private-storage journey, replacements, retry, rejection, restarts, and three viewports |
| Continuation cleanup | `PASS` — exact rows, objects, temporary files, and listeners returned to their pre-run zero baseline |
| Independent security review F-01 | `PHASE_1E_1_FAIL_REMEDIATION_REQUIRED` — forced key collision overwrote an immutable object |
| Independent review F-02 | `REVIEW_EXPECTATION_CONFLICT_RESOLVED_BY_FORMAL_PROJECT_SCOPED_CONTRACT` |
| Remediation focused storage/unit suite | `PASS` — 23 tests |
| Remediation focused real PostgreSQL ImageAsset suite | `PASS` — 8 tests |
| Remediation migration current/heads/history/check | `PASS` — one head `5ed9906e7d33`, no diff |
| Remediation isolated upgrade/downgrade/upgrade and constraint lifecycle | `PASS` — 1 test |
| Remediation complete `make check` | `PASS` — 183 backend unit, 81% coverage, 38 PostgreSQL integration, 10 files / 113 frontend tests, production build |
| Remediation synthetic browser acceptance | `PASS` — new fixtures and isolated Browser/Vite/proxy/API/PostgreSQL/storage chain |
| Remediation cleanup | `PASS` — business tables, private storage, staging, migration fixtures, temporary root, and listeners returned to baseline |
| Final scope and SHA-256 manifest | `PASS` — companion manifest excludes only its own file |

## Safety evidence

- Other-owner project, metadata, and private-content requests return the safe not-found
  boundary.
- Storage key, local path, owner ID, and actor IDs are absent from the response projection.
- Private content uses no-store/no-sniff headers and rejects ranges.
- Same upload key and same bytes/declaration replay exactly; changed declaration conflicts.
- The upload key is Project-scoped: the same key in another Project or for another Principal
  creates an independent command and cannot reveal or reuse the first scope's result.
- Two concurrent same-key uploads produce exactly one asset and one replay.
- A formal object is published through an atomic hard-link create. A destination collision returns
  no receipt and leaves the pre-existing SHA-256 unchanged; concurrent publishers yield one
  complete object, one receipt, and one typed collision.
- A forced post-storage database failure removes only the exact receipt-proven uncommitted object
  and rolls back rows. Changed object identity or any database reference refuses deletion.
  Compensation failure is logged as detectable orphan state. A forced storage failure creates no
  database asset.
- Replacements retain prior rows and prior bytes; there is no delete endpoint or UI.
- Production refuses the local adapter.

## Invalid browser attempt and cleanup

- The real Vite proxy, FastAPI process, development PostgreSQL, and private local storage were
  exercised.
- Created the clearly labeled `Phase 1E-1 browser evidence` project under the dedicated
  `phase1e1-browser-operator` Principal.
- Uploaded Golden Case `primary-front.jpeg`. Although that asset is repository-authorized for
  the product case, it is a private photograph and the task expressly required a
  program-generated or explicitly synthetic browser fixture. Therefore the whole browser upload
  attempt is `INVALID_ATTEMPT`, not PASS.
- Observed `DRAFT -> IMAGE_UPLOADED`, one current version, 1320×1656 JPEG metadata,
  `User attestation confirmed`, and the workflow-locked no-replacement state.
- The browser decoded the private content route to natural size 1320×1656 and recorded no
  console errors.
- After stopping and restarting the API process, the invalid-attempt project, ImageAsset,
  private bytes, metadata, and decoded preview recovered; this proves persistence behavior but
  does not cure the fixture violation.
- At 390×844, the document and body scroll width remained exactly 390, the card and fact
  grid collapsed to one column, and the image card stayed within 16–374 px.
- The invalid attempt still found two stale project-list labels. They were corrected to
  `Primary image stored` and a current capability boundary; the 113-test frontend suite and
  browser list view were rerun after the correction.

Before cleanup, read-only proof showed exactly one project, one asset, two command records,
two state events, and the exact 332,641-byte private object, all under the dedicated test
Principal/project. A row-count-asserting transaction then removed only those test rows, and the
storage adapter removed only the now-unreferenced controlled key. Post-cleanup counts were all
zero and the exact file was absent.

That evidence remains historical `INVALID_ATTEMPT`. It is not reused as proof for the compliant
continuation below.

## Independent security findings and formal resolution

The first independent Phase 1E-1 security review did not approve the candidate. It returned
`PHASE_1E_1_FAIL_REMEDIATION_REQUIRED`.

- F-01 ran `duplicate_storage_key_preserves_existing_object` against the former `os.replace`
  publish. The existing object's SHA-256 was
  `829418e630598d03a6e7c70ecab3fa2e8a4b161617df99017fab6e9930b656b2`; after the forced
  collision it was
  `1543c71585f2ed3467327917aaaf4c474da85c61e158617894745372fd6648e2`.
  No exception was raised and `old_object_preserved=False`. This is the blocking immutable-object
  overwrite evidence; it is preserved rather than rewritten after remediation.
- F-02 expected one Principal-wide idempotency namespace. The Product Contract and implemented
  command scope include Project, so the review expectation did not control the architecture.
  The recorded outcome is
  `REVIEW_EXPECTATION_CONFLICT_RESOLVED_BY_FORMAL_PROJECT_SCOPED_CONTRACT`.

The formal upload semantics remain:

- same Principal + same Project + same key + same payload: replay one ImageAsset;
- same Principal + same Project + same key + changed payload: safe 409;
- same Principal + different Project + same key: independent 201/201 commands, assets, events,
  and records, with no cross-Project replay or payload-hash disclosure;
- different Principal + same key: independent owner scopes.

## Security Remediation Round 1 evidence

### No-overwrite publish and receipt boundary

- The local adapter now uses same-filesystem `os.link(staging, destination,
  follow_symlinks=False)`. An existing destination atomically returns a typed
  `StorageObjectAlreadyExistsError`; unsupported no-replace errors fail closed with no
  `os.replace`, rename-precheck, or process-lock fallback.
- The adapter verifies regular-file device/inode/size identity, fsyncs the destination directory,
  removes the staging name, fsyncs the staging directory, and then returns a
  `StoragePublishReceipt`. Collision and failed publication return no receipt.
- The receipt binds key, expected SHA-256, byte size, filesystem device, inode, link count, and
  `created_by_this_call=true`. Compensation requires the receipt, not a key string.
- `delete_uncommitted` reopens without following symlinks, verifies controlled-root containment,
  regular-file identity, link count, byte size, SHA-256, and the absence of the key from the
  database-referenced set, then repeats identity checks immediately before unlink.
- Collision is projected as retryable safe 503 `IMAGE_STORAGE_COLLISION`; the response contains
  no root, absolute path, random key, or operating-system traceback.

### Focused collision, concurrency, and compensation results

- `duplicate_storage_key_preserves_existing_object` now leaves the first object byte-identical,
  safely handles the second staging file, and produces no second formal object.
- Two concurrent publishers to the same key produce exactly one receipt and one typed collision;
  the final object is one complete input, never truncated or mixed.
- A forced storage collision at Service/API level preserves the existing object's SHA-256, returns
  safe 503, creates no asset, and makes no compensation call.
- A replacement publish followed by forced database failure deletes only the new receipt-proven
  object; the preceding current row, pointer, and bytes remain.
- Changed receipt identity and a database-referenced key both refuse cleanup without deleting the
  object.
- Forced compensation failure emits structured orphan-detectable state; the test then performs
  exact fixture cleanup.
- Project-scoped and Principal-scoped independence tests both return independent 201 results.
- Focused backend storage/ImageAsset unit result: 23 passed. Focused real PostgreSQL ImageAsset
  result: 8 passed. Pre/post focused business-table counts were all zero.

### Canonical and migration results after remediation

- Complete `make check`: Ruff and Ruff format passed; mypy checked 39 source files; 183 backend
  unit tests passed at 81% coverage; 38 real PostgreSQL integration tests passed; ESLint and
  TypeScript passed; 10 frontend files / 113 tests passed; the 89-module production build passed.
- Skip count was zero and xfail count was zero. Two expected Starlette multipart deprecation
  warnings did not affect the results.
- Development database `current`, script `heads`, and catalog were
  `5ed9906e7d33`; history was `a10d3d8dab38 -> 5ed9906e7d33`; `alembic check` found no upgrade
  operations.
- The focused isolated head/base/head and physical-constraint lifecycle passed. Post-run
  `creativedeploy_migration_test_*` databases and `creativedeploy_migration_owner_*` roles were
  both zero.
- The repository `.env` still points at stale port 5432. Its first migration commands failed
  authentication and remain `INVALID_ATTEMPT`; `.env` was not edited. Every PostgreSQL gate was
  fully rerun with a one-command `DATABASE_URL` derived from the active CreativeDeploy Compose
  container on port 55432.

## Post-remediation synthetic browser acceptance

This was a new isolated run, not a reuse of either historical browser session. A Pillow generator
created 1200×900 JPEG (51,055 bytes,
`14617191977c2fbbc94ef44cf41d67cc77936b0837db7d027fa7a20d6534d120`), 1024×1024 PNG
(10,993 bytes, `0e75f91b5d1dd3b73b774aed3f9d49eeceab0de35dd5ff277d681f632414107d`),
1280×960 WebP (20,686 bytes,
`f113fc9d007677413e43815595791997abc7a0e38c9370b74cf9363f72adfa72`), and a 42-byte
non-image `.jpg`. No external image or network source was used.

- Chain: Browser → Vite `13121` → one-shot confirmation-loss proxy `18122` → FastAPI `18121`
  → CreativeDeploy PostgreSQL `55432` → a new private temporary storage root.
- Project `1de4943e-034a-4935-acbd-a329de5384b8` began at DRAFT. The JPEG upload committed 201;
  the proxy converted only that response to 504. Retrying with the same UI key replayed version 1
  without a duplicate row or file and reached `IMAGE_UPLOADED`.
- Exact test-precondition transitions moved the project to `IMAGE_REVIEW_REQUIRED` before each
  replacement because no public image-quality transition exists. PNG became version 2 and WebP
  became version 3/current; JPEG and PNG rows and exact bytes remained as superseded history.
- All three private routes returned 200, exact content type/length, `accept-ranges: none`,
  `Cache-Control: private, no-store, max-age=0`, `nosniff`, and bytes matching the fixture
  SHA-256. The API projection exposed no storage key or object path.
- The 42-byte false JPEG returned controlled 422 and changed no asset, command, object, staging
  file, or current pointer.
- Direct Detail URL, refresh, Projects → Detail, browser back/forward, full API restart, and full
  Vite restart restored version 3, both historical versions, and a decoded 1280×960 preview.
- A second Principal saw an empty list and safe 404 for project, image list, and content.
- At 1440×900, 768×1024, and 390×844, document scroll width equaled viewport width; one main, one
  route H1, and one replacement action remained. Console warning/error count was zero. The only
  exceptional network statuses were the intentional 504 and intentional 422.
- Before cleanup there were exactly one project, three assets, seven state events, four command
  records including project creation, three database-referenced keys, three formal objects, and
  zero staging files. Exact reverse-lineage cleanup returned all four business tables and private
  storage to zero; migration fixture database/role counts, listeners, and the temporary root also
  returned to zero. The CreativeDeploy PostgreSQL container and named volume were retained.
  VisualEngineer was not operated.

## Synthetic browser acceptance continuation

### Program-generated fixtures

A fixed Pillow generator under the unique temporary root
`/tmp/creativedeploy-phase1e1-synthetic.TPgEUF` read no external image, used no network access,
and generated these static files:

| Fixture | Bytes | SHA-256 | Decoder evidence |
| --- | ---: | --- | --- |
| `synthetic-phase1e1.jpg` | 151,739 | `2267a9b0e02ab7a9fd43c76d0657fa7f3ce5bec5eab75cab611b41e29ecc3ce5` | JPEG, 1200×900, RGB, one frame |
| `synthetic-phase1e1.png` | 16,103 | `79c17313f7957678f8081c8eae7a0b4d3e4fa2fb09454b79a37f13128d9511e9` | PNG, 1024×1024, RGBA, one frame |
| `synthetic-phase1e1.webp` | 24,482 | `1e3a516ebf6e14d6c7b0e93fb8f1fb8ae55827293aca088a3878046f8acbafba` | WebP, 1280×960, RGB, one frame |
| `invalid-synthetic-phase1e1.jpg` | 66 | `69c1fdb66e950b6b0aa7ad537c51665aabdcf0810774b3b36165e057ddb0584d` | Program-generated non-image ASCII bytes |

Pillow reopened and fully decoded each valid fixture. Every valid fixture was non-animated,
below 20 MiB, within 768–8192 px per side, and below 40 MP. The temporary root, generator,
fixtures, proxy, report, and cleanup script were removed after evidence capture.

### Browser upload, retry, and private preview

- The isolated chain was Browser → Vite `13111` → one-shot local confirmation-loss proxy
  `18112` → FastAPI `18111` → CreativeDeploy PostgreSQL `55432` → a unique private local
  storage root. No repository `.env` or VisualEngineer resource was changed.
- The real browser created project `b60e5f78-66a7-45ee-beeb-f588fa4cea5a` titled
  `Synthetic browser acceptance TPgEUF` for Principal
  `phase1e1-synthetic-browser-TPgEUF`. Its initial state was `DRAFT`; the ImageAsset Manager
  showed the honest empty state, no delete control, and explicit no-AI/no-quality/no-legal-
  verification boundaries.
- The JPEG was selected through the real file chooser with `user_provided`,
  `private_project`, `primary_mvp_input`, and an explicit rights confirmation.
- FastAPI committed the JPEG and returned 201, while the one-shot proxy converted only that
  response to 504. The UI retained the selected input and displayed the safe uncertain-result
  retry message. PostgreSQL and storage already contained exactly one asset/object.
- The retry reused the same idempotency-key SHA-256
  `87d75794a41bf32ec8e08bfae8e6a062b1a626ba0646d875013bfbcabdd793a1`;
  the backend replayed the same asset `4e02a997-a222-4363-979a-2f9345dd4a02`.
  Counts remained one asset, one current asset, one object, two events, and two command records
  including project creation.
- The browser rendered the owner-scoped relative content route. Its response was JPEG,
  151,739 bytes, `X-Content-Type-Options: nosniff`, and
  `Cache-Control: private, no-store, max-age=0`; the returned bytes matched the fixture SHA-256.
  API projections exposed no storage key, disk path, public URL, or owner ID. A second temporary
  Principal received safe 404 for project, image list, and content.

### Replacement, rejection, and persistence

The current product has no public transition command that moves `IMAGE_UPLOADED` into a
replacement-allowed state. The test harness therefore made exact, owner-and-current-guarded
updates to `IMAGE_REVIEW_REQUIRED` before each browser replacement, and restored
`IMAGE_UPLOADED` afterward. These were test preconditions, not claimed product features.

- PNG created asset `0414e348-dc88-4205-afa3-65ad1dec9362`, version 2, superseding the JPEG.
  PostgreSQL recorded `RGBA` and `has_alpha=true`; the JPEG row and exact bytes remained.
- WebP created asset `51c4abd1-242f-466c-b94b-a537ab25ab8f`, version 3, superseding the PNG.
  It became the only current asset; versions 1 and 2 remained `superseded`.
- The expanded real-browser history showed both retained versions with private-original links.
  All three private content routes returned bytes matching their fixture SHA-256.
- The 66-byte false `.jpg` returned controlled 422/UI validation text. It created no asset,
  event, command record, formal object, or staging file and did not change the WebP current
  pointer or history.
- Refresh, direct Detail URL, Projects → Detail, browser back/forward, complete API stop/restart,
  and complete Vite stop/restart all restored version 3, two retained versions, metadata, and a
  decoded 1280×960 WebP preview. This excludes localStorage/base64 persistence.

### Responsive, focus, console, and network

- At 1440×900, 768×1024, and 390×844, document scroll width equaled viewport width. The
  ImageAsset Manager had no horizontal overflow.
- At every size, the file and source controls were visible at 48 px high, the replacement action
  was visible at 46 px high, the rights label was visible, and route H1 held focus.
- Preview alt text was `Private preview of synthetic-phase1e1.webp`. Loading/error/success UI did
  not obscure the steady-state controls.
- Final console warning/error count was zero. Network 504 was the intentional confirmation-loss
  injection, and 422 was the intentional invalid-file rejection; all other observed product,
  history, preview, and health requests completed with expected success statuses.
- Live physical Enter delivery is `UNVERIFIED` in this browser-control surface; DOM semantics,
  focus evidence, and the already-passing repeated-Enter automated coverage remain the supporting
  evidence. This does not block the current formal contract.

### Continuation invalid attempts and command ledger

No failed command below changed repository or business state unless the successful rerun is
explicitly described:

- `/opt/homebrew/bin/git` did not exist; every Git baseline command was fully rerun with
  `/usr/bin/git`.
- A non-canonical tracked diff hash omitted `--full-index`; the canonical full-index stream
  reproduced the manifest hash.
- Initial read-only SQL used obsolete guessed event/idempotency table or column names; the live
  catalog was inspected and all affected queries were fully rerun with
  `state_transition_events`, `command_idempotency_records`, `project_id`, and `principal_id`.
- Initial health probes used `/health/*`; current `/api/v1/health/live` and
  `/api/v1/health/ready` were then verified directly and through Vite.
- One DOM projection referenced an unavailable `HTMLImageElement` constructor; generic image
  properties were rerun successfully.
- One mobile full-page screenshot contained browser-tool tiling artifacts and was discarded;
  a normal viewport screenshot plus single-main/single-H1 DOM and exact overflow metrics replaced
  it.
- One read-only Python API projection had invalid f-string escaping; the corrected projection
  confirmed three relative content URLs and no `storage_key`.
- The first mechanical Manifest replacement truncated one `imageAssets.ts` SHA-256 line; immediate
  file/hash reconciliation caught it before final validation or staging. The Manifest was rebuilt
  from the current worktree and fully reconciled.

### Exact cleanup

Before cleanup, read-only proof bound the project, three asset IDs, owner, lineage, and three
relative storage keys to this synthetic seed. Other-project current references, other-project
lineage references, and other-Principal command references were all zero.

A row-count-asserting transaction deleted exactly four command records, four events, the three
assets in reverse lineage order, and the single project. All four business tables returned to
their pre-run count of zero. After database references were zero, exactly the three matching
private objects were removed and storage returned to zero regular files. The API, Vite, proxy,
and foreign-Principal probe listeners returned to zero; the unique temporary root was removed.
The CreativeDeploy PostgreSQL container and named volume were retained. VisualEngineer was not
operated.

## Final scope evidence

- Manifest:
  `docs/progress/phase-1e-1-imageasset-foundation-manifest.txt`
- Historical Revision
  `apps/api/migrations/versions/a10d3d8dab38_create_paintproject_persistence_.py`
  remained byte-identical to HEAD:
  `5bb485081ae076d9dda922d64c8e4aaa0b33e9eefa3287d4feb271be2371aaa7`.
- Development database: current/head `5ed9906e7d33`; `alembic check` reported no new
  upgrade operations.
- Development Catalog contains `paint_projects`, `state_transition_events`,
  `command_idempotency_records`, and `image_assets` plus `alembic_version`.
- `git diff --check` passed.
- `git diff --cached --quiet` passed; nothing is staged.
- No commit, branch, tag, push, dependency upgrade outside the two reviewed image-upload
  packages, or VisualEngineer change was made.

The companion manifest is generated last and therefore excludes only itself from its file
entries and scope-content hash. The final whole-worktree porcelain-v2 `-z` hash is reported
externally in the handoff because embedding it in a tracked candidate file would change the
hash being reported.

## Ready handoff

Security Remediation Round 1 and its new synthetic browser gate passed without a second Migration,
external provider, deletion, authentication, AI, or VisualEngineer operation. This candidate is
`PHASE_1E_1_REMEDIATION_IMPLEMENTED_READY_FOR_INDEPENDENT_REVIEW`, not approved, commit-ready,
sealed, production-ready, or closed. Open a fresh read-only security and product review focused on
F-01 no-overwrite publication, receipt-bound compensation, concurrent collision behavior,
Project-scoped idempotency, and the complete browser/cleanup evidence. The reviewer must not modify
the candidate. Only a strict independent PASS may authorize a later, separate Git sealing task.
Image quality assessment, AI, external storage, public URLs, deletion, and real authentication
remain unauthorized.
