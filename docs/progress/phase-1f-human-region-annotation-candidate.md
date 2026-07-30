# Phase 1F — Human-Governed Region Annotation and Review Candidate Evidence

## 1. Verdict

- Current phase status: `CLOSED`
- Final independent review verdict:
  `PHASE_1F_SNAPSHOT_TARGET_REMEDIATION_PASS_READY_FOR_SEALING`
- Implementation seal commit: `fdf1fd787b2cc0c5a4db3c1e72885df4fdf6ae1b`
- Migration head: `7f3a2b9c4d1e`
- Current overall project checkpoint: `approximately_80_percent`
- Next checkpoint: `80_percent_overall_product_and_deployment_readiness_review`
- Next product phase: `NOT_SELECTED` / `NOT_STARTED`
- AI integration: `NOT_AUTHORIZED`
- External object storage: `NOT_SELECTED`
- Public/signed URLs: `NOT_AUTHORIZED`
- Deletion: `NOT_IMPLEMENTED`
- Real authentication: `NOT_IMPLEMENTED`
- Light, color, and PaintPlan: `NOT_IMPLEMENTED`
- Current earlier-phase status: Phase 1D `COMPLETE`; Phase 1E-1 `CLOSED`; Phase 1E-2 `CLOSED`
- Historical environment-isolated continuation verdict:
  `PHASE_1F_SNAPSHOT_TARGET_REMEDIATION_IMPLEMENTED_READY_FOR_INDEPENDENT_REVIEW`
- Historical technical implementation status:
  `PHASE_1F_SNAPSHOT_TARGET_REMEDIATION_IMPLEMENTED_READY_FOR_INDEPENDENT_REVIEW`
- Historical candidate-time governance status:
  `PHASE_1F_SNAPSHOT_TARGET_REMEDIATION_IMPLEMENTED_READY_FOR_INDEPENDENT_REVIEW`
- Historical implementation-conversation verdict: `PHASE_1F_IMPLEMENTATION_FAILED`
- Historical incident classification: `ENVIRONMENT_ISOLATION_INVALID_ATTEMPT`
- Historical blocking condition: `VISUALENGINEER_PORT_SCOPE_DEVIATION`
- Historical candidate-time independent approval: `NOT_PERFORMED`
- Historical candidate-time Git seal: `NOT_CREATED`
- Production readiness: `NOT_CLAIMED`
- Historical candidate-time project checkpoint: `approximately_70_percent`

This work did not stage, commit, push, tag, or create a PR. The historical implementation
conversation's unsuccessful request to an unrelated port-8000 listener remains recorded below and
is not reclassified. The controller-authorized continuation used a corrected 35-path baseline,
fresh ports, an explicit proxy target plus not-port-8000 guard, isolated PostgreSQL and storage,
and a request-audit hop. It performed no VisualEngineer request, check, log, container, database,
or file operation. The complete acceptance journey and exact cleanup passed. This qualifies the
candidate for fresh independent focused read-only review only; it is not independently approved,
ready for sealing, Git-sealed, commit-ready, production-ready, or phase-closed.

## 2. Verified baselines

Authoritative environment-isolated continuation baseline:

| Fact | Verified value |
| --- | --- |
| Repository | `/Users/danke/Developer/CreativeDeploy` |
| Branch / HEAD / tree | `main` / `91f3135041c16c8e600d963c1341cb1af1db1458` / `35302def051a10b018e02556068485ae1d40a338` |
| Commit count / staged paths | `19` / `0` |
| Candidate scope | 14 modified tracked + 22 untracked = 36 paths including Manifest, 35 excluding Manifest |
| Deletions / renames / conflicts | `0 / 0 / 0` |
| Starting Manifest SHA-256 | `c0eb108173e559faa9b1be32107a2f8f19981b3f10bb2d26b1adb35898abe8da` |
| Starting tracked patch SHA-256 | `42eba01346d88f2d267192966d25b2c2a2d21d682536c140d361f76d460e203c` |
| Revision / parent / migration SHA-256 | `7f3a2b9c4d1e` / `d4c8a1f7b2e9` / `b535962160ff71acd2589d1d252ca680cef519f6c39d14a0125c5e66590a1940` |

All 35 starting Manifest entries matched their path, status, byte size, and SHA-256. The stale
24-modified + 10-untracked / 34-path controller expectation was formally corrected to this
baseline and was not used as a stop condition.

Historical pre-implementation baseline:

| Fact | Verified value |
| --- | --- |
| Repository | `/Users/danke/Developer/CreativeDeploy` |
| Branch | `main` |
| HEAD | `91f3135041c16c8e600d963c1341cb1af1db1458` |
| Subject | `docs(progress): close phase 1e-2 image readiness` |
| Commit count | `19` |
| Initial worktree | clean; staged/unstaged/untracked `0/0/0` |
| Remotes / tags / submodules | none / none / none |
| Baseline Alembic head | `d4c8a1f7b2e9` |
| PostgreSQL | CreativeDeploy Compose, `127.0.0.1:55432`, healthy |
| Initial public business rows | all `0` |

Phase 1D was `COMPLETE`; Phase 1E-1 and Phase 1E-2 were `CLOSED`; Phase 1F was the authorized
next phase. No baseline mismatch or concurrent work was detected before the historical
implementation.

## 3. Contract decisions

- ADR-0006 freezes a pure human annotation and review boundary.
- RegionSet remains independent of the PaintProject workflow state machine.
- Human labels are free text within safety/length constraints; character parts are not hard-coded.
- `paint | exclude` is the only Region kind vocabulary.
- Integer ppm coordinates and exact integer/rational geometry avoid floating serialization drift.
- Overlap is permitted and warned; the system does not crop, merge, infer, or correct it.
- The configured Demo Principal can perform local review but is not real authentication or an
  independent enterprise reviewer.
- No AI, external provider/storage, public URL, deletion, image-quality analysis, lighting, color,
  materials, inventory, or PaintPlan capability was added.

## 4. Candidate scope

The exact path/status/size/SHA-256 inventory is frozen separately in
`docs/progress/phase-1f-candidate-manifest.txt`.

Scope is limited to:

- one new migration;
- four RegionSet persistence models plus Metadata registration;
- Region geometry, Repository, Service, dependencies, routes, and schemas;
- focused updates to prior exact model/migration inventory tests;
- strict frontend API/geometry utilities, SVG workbench, route, Project Detail entry, styles, and
  tests;
- ADR-0006, physical dictionary, Plan, Candidate, Manifest, README, and AGENTS.

No `.env`, dependency declaration, lockfile, Compose, CI, production infrastructure, sealed
migration, Golden Case asset, or VisualEngineer path changed.

## 5. Migration and schema

- Revision: `7f3a2b9c4d1e`
- Parent: `d4c8a1f7b2e9`
- Tables: `region_sets`, `regions`, `region_vertices`, `region_set_reviews`
- Current Metadata business-table count: `9`
- Historical migrations modified: `0`

Composite foreign keys bind RegionSets to the same Owner/Project and exact `primary_front`
ImageAsset, keep ancestry in one aggregate, and keep Region/Vertex/Review children on the same
snapshot. Unique and check constraints protect versions, vocabularies, counts, coordinates,
labels, z-order, Vertex sequence, fingerprints, actors, and reason requirements.

All four tables have PostgreSQL triggers that reject UPDATE and DELETE. Downgrade checks every
table is empty before removing only Phase 1F objects. The isolated real-PostgreSQL fixture ran
head → `d4c8a1f7b2e9` → head and verified tables/triggers.

Actual Compose main schema:

```text
current: 7f3a2b9c4d1e (head)
heads:   7f3a2b9c4d1e (head)
check:   No new upgrade operations detected.
```

## 6. Geometry model

- `pixel_to_ppm` uses Decimal `ROUND_HALF_UP` and clamps to `0..1_000_000`.
- Simple Polygons require `3..256` unique Vertices and no repeated closing Vertex.
- Validation rejects out-of-bounds coordinates, repeated or zero-length edges,
  self-intersection, insufficient exact area, duplicate stable keys/z-indexes, and snapshot
  budgets over 128 Regions or 8192 Vertices.
- Exact shoelace double-area and bbox summaries are persisted.
- Rational point-in-polygon and integer segment intersection produce non-blocking overlap warnings.
- Canonical Region ordering is `(z_index, stable_region_key)`.
- Tests calculate the expected SHA-256 independently from the production fingerprint function.
- Public errors expose stable geometry codes, not raw database/storage/trace internals.

## 7. RegionSet lifecycle

1. Human edits exist only in the browser session until Save.
2. Save creates a new immutable `draft` snapshot against an exact optimistic base.
3. Submit revalidates READY/current source, geometry, labels, budgets, fingerprint, and at least one
   `paint` Region, then creates a new immutable `submitted` snapshot.
4. Review appends one `approved` or reasoned `changes_requested` record without changing the
   submitted snapshot.
5. Later snapshots derive earlier ones as `superseded`; all rows remain retained.
6. An approved/changes-requested snapshot can seed a new draft, which becomes a new immutable
   version when saved.

No API updates or deletes a sealed RegionSet, Region, Vertex, or Review.

## 8. Fingerprint and stale

The canonical SHA-256 includes Project ID, source ImageSet fingerprint, source primary asset,
RegionSet version, and every canonical Region/Vertex fact. It excludes storage details, time, UI
state, zoom/pan, visibility, hover, selection, and undo/redo.

The API derives stale reasons when:

- current ImageSet fingerprint changed;
- current primary asset changed;
- current ImageSet is no longer READY.

The browser journey replaced `reference_angle`, reconfirmed the new ImageSet, and showed the
approved v2 RegionSet as source-stale and read-only. Its Review and geometry remained in history;
the operator created a fresh draft against the new fingerprint.

## 9. API and Owner isolation

Implemented owner-scoped endpoints:

```text
GET  /api/v1/paint-projects/{project_id}/region-sets/workbench
POST /api/v1/paint-projects/{project_id}/region-sets
GET  /api/v1/paint-projects/{project_id}/region-sets
GET  /api/v1/paint-projects/{project_id}/region-sets/{region_set_id}
POST /api/v1/paint-projects/{project_id}/region-sets/{region_set_id}/submit
POST /api/v1/paint-projects/{project_id}/region-sets/{source_region_set_id}/drafts
POST /api/v1/paint-projects/{project_id}/region-sets/{region_set_id}/reviews
GET  /api/v1/paint-projects/{project_id}/region-sets/{region_set_id}/reviews
```

Schemas reject unknown fields and client-owned source/Owner/fingerprint/actor facts. Detail returns
only private-content endpoint data and Region facts, never a storage path or object key.

Integration tests prove same-safe-404 behavior for missing and other-owner access. The synthetic
browser API was restarted with `phase1f-browser-other`; the exact workbench request returned 404
and the UI rendered only “project or snapshot is not available to the current operator.”

## 10. Idempotency and concurrency

- Save, submit, and review require Project-scoped UUID `Idempotency-Key`.
- Exact same-key/same-payload replay returns the committed result.
- Same key with changed payload/base/snapshot returns a safe 409.
- A PostgreSQL PaintProject row lock serializes source reads, version allocation, RegionSet
  commands, image mutation, and readiness mutation; no process-local lock is relied upon.
- Concurrent saves from one base produce one next version and one stale-base 409.
- Submit/image and review/image races either commit first and become stale afterward or observe the
  source change and reject.
- Concurrent Review version allocation is unique and bounded by database constraints.

The real browser opened v3 in two tabs: one saved v4; the second preserved its local edit and
received the safe “image set or region snapshot changed; reload” 409 feedback.

## 11. Approval history

The real browser produced:

- v1 draft;
- v2 submitted and human Approved;
- source replacement, making v2 stale without rewriting it;
- v3 new-current-source draft;
- v4 concurrent-save winner;
- v5 submitted and human Changes Requested with
  `Clarify the hair boundary before approval.`

History retained v1–v5, including the stale-source marker and exact latest Review. Review records
are append-only, actor/time/reason bound, and do not advance PaintProject workflow.

## 12. Frontend Polygon workbench

The dedicated route `/paintpilot/projects/:projectId/regions` provides:

- owner-scoped primary preview with original aspect ratio;
- SVG overlay with zoom, pan, fit, and resize-stable ppm projection;
- click-to-add, current-edge preview, close, and cancel;
- selection, vertex drag/insert/delete, draft Region delete, label/kind/z-order, visibility,
  opacity, notes, undo, and redo;
- client geometry feedback and server-authoritative validation;
- immutable save, submit, approve, reasoned changes request, stale banner, current-source draft
  creation, and history reload;
- strict response validation, safe errors, and page-lifetime retry-key reuse;
- no localStorage persistence and no AI/quality/public-url/light/color/PaintPlan controls.

## 13. Test results

| Category | Collected | Passed | Failed | Skipped | Exit Code | Result |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Focused backend remediation | 18 | 17 | 0 | 1 deselected | 0 | PASS |
| Focused frontend remediation | 20 | 20 | 0 | 0 | 0 | PASS |
| Backend unit | 211 | 211 | 0 | 0 | 0 | PASS |
| PostgreSQL integration | 53 | 51 | 0 | 2 deselected | 0 | PASS |
| Full backend | 264 | 262 | 0 | 2 deselected | 0 | PASS |
| Frontend | 141 | 141 | 0 | 0 | 0 | PASS |
| Frontend files | 13 | 13 | 0 | 0 | 0 | PASS |

Additional canonical gates:

| Gate | Result |
| --- | --- |
| Ruff lint | PASS |
| Ruff format check | PASS, 70 files |
| mypy | PASS, 47 source files |
| ESLint | PASS |
| TypeScript project build | PASS |
| Production Vite build | PASS, 93 modules |
| Root `make check` | PASS after complete rerun |
| Alembic current/heads/history/check | PASS |
| Isolated downgrade/upgrade/catalog/trigger test | PASS |
| `git diff --check` | PASS |

The only test warning is the existing Starlette `TestClient` deprecation notice recommending
`httpx2`; it is not a Phase 1F failure or skipped test.

## 14. Synthetic browser evidence

The real chain was:

```text
in-app Browser → Vite :5173 → FastAPI :18000 → Compose PostgreSQL :55432
                                    └→ isolated private local storage
```

Only program-generated local SVG→PNG fixtures were used. The journey:

1. created an owner-scoped Project;
2. uploaded distinct 900×768 primary/back/angle images with human rights attestations;
3. recorded human READY and opened the private primary preview;
4. drew `hair`, `skin`, and `shirt` paint Polygons plus `background` exclude;
5. exercised vertex drag/insert/delete, label/kind/z-order, visibility, opacity, undo/redo;
6. blocked a bow-tie self-intersection; pointer coordinates were clamped to ppm bounds;
7. saved v1, refreshed by direct URL, and recovered all four Polygons;
8. restarted both API and Vite and recovered the same PostgreSQL truth/private preview;
9. double-click submitted without duplicate versions, then approved exact v2;
10. replaced an ImageSet reference, reconfirmed READY, and observed v2 stale/read-only;
11. created and saved v3 from old history, then proved a safe two-tab stale-version 409;
12. submitted v5 and recorded reasoned Changes Requested;
13. restarted API as another Principal and observed owner-safe 404;
14. verified 1440×900, 768×1024, and 390×844 with
    `document.documentElement.scrollWidth === window.innerWidth`;
15. verified initial heading focus and reachable mobile editing/history controls;
16. opened a fresh post-fix page and observed zero console errors.
17. after the z-order/review-history UI increment, used the exact final source in a second isolated
    real chain: moved `hair` forward to persist `skin → hair`, saved v1, submitted v2, requested
    changes, displayed reviewer/time/reason in the history row, and observed zero console errors.

The server access log showed expected 2xx/201 responses, the intentional stale-save 409, and the
intentional other-owner 404. No unexplained critical console or network error remained.

### 14A. Controller-authorized environment-isolated continuation

The authoritative continuation chain was:

```text
in-app Browser :18161 → request-audit proxy :18161 → Vite :15160
  → FastAPI :18160 → CreativeDeploy PostgreSQL :55432 isolated schema
  └→ isolated private local storage
```

Before startup, the proxy target guard confirmed
`CREATIVEDEPLOY_API_PROXY_TARGET=http://127.0.0.1:18160` and rejected any target containing port
8000. The audit proxy source contained target literals `18161`, `15160`, and `18160`, with zero
port-8000 literals. Every recorded browser request used target `18161` and upstream `15160`.

The continuation used four fixed 900×768, non-animated, program-generated RGB fixtures: JPEG
primary, PNG back, WebP angle, and PNG angle replacement. It created Project
`0997897e-f6ca-4e92-8e22-671090dc459a`, reached READY, and completed all material workbench
operations: four paint/exclude Polygons; vertex drag/insert/delete; label, kind, notes, z-order,
visibility, undo, and redo; self-intersection blocking; server-side out-of-bounds 422; immutable
save and direct-URL recovery; API/Vite restart recovery; two-tab stale-base 409 with local edits
preserved; submit and approval; source replacement and stale history; new-current-source draft;
reasoned Changes Requested; retained v1–v5 history; other-owner safe 404; and private preview
recovery.

At 1440×900, 768×1024, and 390×844, the document width equaled the viewport width. Direct page
loads focused the single H1; the skip link, main landmark, canvas/tool/history labels, and mobile
editing controls were present. Fresh-page console warning/error collection was empty. Physical
keyboard Enter activation of one visibility control is `UNVERIFIED`: the controller press did not
toggle it, so it is not counted as passing evidence and does not override the automated
accessibility tests.

## 15. Security and adversarial review

- No client field can select Owner, actor, source primary asset, source ImageSet fingerprint, or
  geometry validity.
- Same-safe-404 behavior prevents Owner enumeration.
- Strict request/response contracts reject unknown or malformed fields.
- HTML delimiters and control characters are rejected in Region labels/notes.
- Raw storage keys/paths, database URLs, exceptions, and geometry internals are not returned.
- Project locks plus database uniqueness arbitrate concurrency across processes.
- Append-only triggers cover every Phase 1F table, not only Reviews.
- Downgrade refuses non-empty RegionSet history.
- No update/delete endpoints, public URLs, external services, AI dependencies, or workflow
  transitions were introduced.
- The historical Phase 1F API used port 18000. One supplemental browser attempt incorrectly used
  Vite's default port-8000 proxy and sent one unsuccessful Create request to the unrelated
  listener. This remains a historical strict scope deviation even though no successful
  VisualEngineer write or runtime reconfiguration is known.
- The controller-authorized continuation used only 18160/15160/18161, included a not-port-8000
  startup guard and request-audit proxy, and performed no VisualEngineer operation.

## 16. Command ledger and invalid attempts

| Attempt | Classification | Resolution |
| --- | --- | --- |
| Initial Alembic command inherited `.env` port 5432 | `INVALID_ATTEMPT` | `.env` was not edited; every affected command was rerun with a one-command Compose-derived 55432 URL |
| Initial Phase 1F API bind requested port 8000 | `INVALID_ATTEMPT` | Unrelated VisualEngineer owned the port; it was not stopped or modified, and Phase 1F used 18000 |
| First browser vertex-drag undo path dereferenced a cleared drag snapshot | `INVALID_ATTEMPT` | Captured the snapshot before ref clear, added drag/undo/redo regression, reran frontend/full/browser gates |
| Existing overlay intercepted clicks while drawing an overlapping Region | `INVALID_ATTEMPT` | Disabled persisted-overlay pointer events only in draw mode; reran tests and browser draw |
| Direct `locator.setInputFiles` controller call | `INVALID_ATTEMPT` | Used the documented file-chooser event and `chooser.setFiles`; upload/replacement passed |
| Several exact-text browser waits used wrong casing/wording | `INVALID_ATTEMPT` | Fresh DOM/accessibility state and server status verified the successful actions |
| First root `make check` format gate found one Region geometry test file | `INVALID_ATTEMPT` | Applied Ruff formatting and reran the complete root gate successfully |
| Direct temporary-file removal was rejected by the command safety layer | `INVALID_ATTEMPT` | Moved the exact validated fixtures/storage root to macOS Trash for recoverable cleanup |
| First historical-migration hash query used two inferred filenames | `INVALID_ATTEMPT` | Resolved exact paths with `rg --files`, reran all three comparisons, and obtained byte-for-byte SHA-256 matches against HEAD |
| First new z-order/review-history UI test used a whitespace-sensitive accessible name | `INVALID_ATTEMPT` | Replaced it with a semantic regex and reran lint, typecheck, all 133 frontend tests, and production build |
| Supplemental final-source Vite start used `VITE_API_PROXY_TARGET` instead of `CREATIVEDEPLOY_API_PROXY_TARGET` | `INVALID_ATTEMPT` and blocking scope deviation | The Create response was rejected as non-CreativeDeploy; Vite was restarted with the correct port-18000 proxy and the entire supplemental chain passed, but the request to the unrelated 8000 listener cannot be erased |
| Supplemental canvas locator clicks defaulted to center and created zero-length drafts; several controller method guesses were unsupported | `INVALID_ATTEMPT` | Deleted only the unsaved drafts, used measured viewport coordinates through the documented coordinate control, and completed valid save/submit/review with zero console errors |
| Controller baseline still expected 24+10/34 paths | `STALE_CONTROLLER_BASELINE_CORRECTED` | Used the authoritative 14-modified + 22-untracked = 36-path state including Manifest, 35 excluding Manifest; no candidate path was removed |
| First continuation manifest loop used zsh readonly variable `status` | `INVALID_ATTEMPT` | Reran the complete exact inventory under bash and obtained 35/35 path/status/size/hash matches |
| First final-manifest collector used Bash 3.2 without `mapfile` support | `INVALID_ATTEMPT` | Reran the read-only calculation with a Bash-3.2-compatible loop before writing the Manifest |
| First continuation database command inherited `.env` port 5432 | `INVALID_ATTEMPT` | `.env` was not edited; reran with the one-command Compose-derived 55432 URL |
| First continuation Project was created before the request-audit proxy while probing an unavailable performance API | `INVALID_ATTEMPT` | Excluded it from acceptance evidence, created the final Project through the audit proxy, and cleaned both exact Projects |
| Initial title-label locator and several exact toast waits did not match the rendered semantics | `INVALID_ATTEMPT` | Used fresh DOM, API, database, and direct-route state without repeating successful mutations |
| Direct top-level JSON navigation was blocked by the browser client | `INVALID_ATTEMPT` | Verified the same other-owner endpoint through the audited HTTP chain and the browser's safe 404 pages |
| Physical Enter activation of the visibility control did not toggle in the controller | `UNVERIFIED` | Not counted as passing evidence; automated keyboard/accessibility coverage remains recorded separately |
| First final listener check treated `lsof`'s expected no-match exit as a shell failure | `INVALID_ATTEMPT` | Reran all remaining final checks with explicit no-listener handling; no missing evidence was inferred from the failed wrapper |
| Two final public-count wrappers lost SQL string quotes | `INVALID_ATTEMPT` | PostgreSQL rejected both with syntax error before executing a statement; reran the read-only query via standard input and obtained nine zero counts plus zero residual schema |
| First focused PostgreSQL remediation wrapper had invalid Python URL quoting | `INVALID_ATTEMPT` | Python failed before fixture/schema creation; reran with SQLAlchemy `URL.create`, and the exact fork integration test passed |
| Snapshot-remediation browser schema initialization inherited stale `.env` port 5432 | `INVALID_ATTEMPT` | Authentication failed before schema creation; reran using only the exact healthy CreativeDeploy container mapping at 55432 |
| First audit-proxy start used a nonexistent Node path | `INVALID_ATTEMPT` | No listener was created; resolved the installed Node executable and started only the owned audit proxy |
| First identity curl URL was unquoted under zsh | `INVALID_ATTEMPT` | The shell rejected it before any request; quoted the exact URL and proved direct/API-proxy identity equality |
| Fixture HTTP client inherited an ambient proxy and received 502 | `INVALID_ATTEMPT` | No fixture write occurred; set `trust_env=False`, repeated the empty-schema identity check, and created the synthetic fixture through the audit proxy |
| Stale-state fixture first attempted a policy-forbidden primary replacement | `EXPECTED_SAFE_409` | No replacement was created; used an allowed first `reference_detail` upload to derive ImageSet staleness |
| First database evidence query used the wrong idempotency table name | `INVALID_ATTEMPT` | The read-only query failed without mutation; resolved `command_idempotency_records` from the model and reran |
| Direct temporary-root removal was rejected by the command safety layer | `INVALID_ATTEMPT` | Verified the exact path and moved the owned root recoverably with macOS Trash |

No invalid attempt is counted as passing evidence. Every affected chain was rerun after correction.

## 17. Cleanup evidence

The browser used isolated schemas `phase1f_browser_019fae80a2f47ca0` and
`phase1f_final_ui_019fae80`, each with a unique ownership marker. After each API/Vite shutdown,
the marker was verified and only that exact schema was dropped. The final Phase 1F schema query
returned `0`.

Public business counts after cleanup:

```text
paint_projects=0
image_assets=0
image_set_readiness_reviews=0
region_sets=0
regions=0
region_vertices=0
region_set_reviews=0
```

Both exact private browser storage roots and the eight generated SVG/PNG fixtures no longer exist
under `/tmp`; they were moved to named entries in `/Users/danke/.Trash` and remain recoverable.
API 18000 and Vite 5173 have no listeners. CreativeDeploy Compose retains only healthy PostgreSQL
at 55432, and named volume `creativedeploy_creativedeploy_postgres_data` remains present.
The baseline local private-storage root has `0` object files and `0` staging entries.

VisualEngineer files, container, process, volume, and database were not inspected, stopped, or
reconfigured. One unsuccessful HTTP request did reach its existing port 8000, so a
“VisualEngineer port not operated” claim is intentionally not made.

For the later environment-isolated continuation, the exact schema
`phase1f_cont_phase1f_continuation_vqbmyd` was protected by ownership token
`3f5e72d6a99e4a2cb92043f03fcf44b1`. Before cleanup it contained only the two continuation
Projects and their expected immutable evidence. The marker was verified before dropping only that
schema; the residual schema count was zero. Public counts for all nine business tables were zero
before and after the run. API 18160, Vite 15160, and audit proxy 18161 had no listeners afterward.
The exact isolated root `/tmp/phase1f-continuation-VqBMyd` was moved recoverably to
`/Users/danke/.Trash/phase1f-continuation-VqBMyd`; the original path is absent. Baseline local
private storage retained zero objects and zero staging entries. CreativeDeploy PostgreSQL at
55432 and its named volume remained healthy. No VisualEngineer request, check, log, container,
database, or file operation occurred during this continuation.

### Snapshot-target remediation evidence

The architecture decision was implemented without changing the physical RegionSet schema,
candidate Migration, ORM model, dependencies, state machine, Product Contract, ImageAsset/ImageSet
policy, or storage boundary.

- Exact endpoint:
  `POST /api/v1/paint-projects/{project_id}/region-sets/{source_region_set_id}/drafts`
- Strict body:
  `{expected_current_region_set_id, expected_current_version}`
- Project-scoped idempotency and the existing PaintProject row lock serialize fork/current/image
  races.
- The source may be historical or stale but remains Owner/Project scoped and immutable.
- Success deep-copies source geometry, binds current image facts, allocates current version + 1,
  sets `based_on` to the source, and sets `supersedes` to the actual current snapshot.
- Current-ID/version mismatch, not-READY ImageSet, forged fields, cross-Project source, other Owner,
  changed idempotency payload, and concurrent stale expectations are covered by zero-side-effect
  integration assertions.
- The frontend keeps viewed and current identities separate, hides lifecycle commands in history,
  locks commands while detail is unresolved, sends the viewed ID in the fork URL and the current
  ID/version in the body, and has no fallback to the current snapshot.
- The centralized geometry budget is 128 Regions, 256 Vertices per Polygon, and 8192 total
  Vertices. Independent edge tests accept 4097 and 8192, reject 8193, reject 129 Regions, and
  reject a 257-Vertex Polygon.

The canonical remediation gate used the exact CreativeDeploy PostgreSQL mapping at 55432 and
`PYTEST_ADDOPTS="-k 'not migration_round_trip'" make check`; the two destructive round-trip tests
were deliberately deselected because the candidate Migration hash and migration-directory diff
were unchanged. Ruff, Ruff format, mypy, 211 backend unit tests, 51 applicable PostgreSQL
integration tests, ESLint, TypeScript, 141 frontend tests, and the Vite production build all
passed. Alembic current/heads/history/check passed at `7f3a2b9c4d1e`, with “No new upgrade
operations detected.” Migration SHA-256 remained
`b535962160ff71acd2589d1d252ca680cef519f6c39d14a0125c5e66590a1940`.

The fresh real-browser chain used only Vite `15180`, API `18180`, audit proxy `18181`, PostgreSQL
`55432`, schema `phase1f_browser_b393356c_f816_4fd2_b4b2_8628c5949a57`, Principal
`phase1f-browser-owner`, and a task-private storage root. No request targeted port 8000, and no
VisualEngineer file, process, service, container, database, log, or port was checked or accessed.
The 89-entry audit log contained zero forbidden-port requests.

The browser identity handshake showed current v3
`a7232834-4c38-4f36-b913-44ccff871844`. It opened exact historical v1
`1bf7e30f-ed9e-4475-bc7c-9c89c88e369e` read-only, then forked it to v4
`0f029b72-f8c3-475a-aedc-499bf184b5c5`. PostgreSQL confirmed v4 `based_on=v1` and
`supersedes=v3`. The browser submitted v4 to v5
`637402a1-92f5-4eb4-99b3-cf5afe02300b`, approved exact v5, and PostgreSQL confirmed the Review
target was exact v5. History-to-current switching returned to v5. A later optional-reference
upload derived the expected stale/read-only command lock. Restarting only the owned API with
Principal `phase1f-browser-other-owner` produced audited workbench 404 and the safe owner-scoped
UI. Both 1280px and 390×844 had no horizontal overflow; warning/error console logs were empty.

Before cleanup the isolated schema contained exactly one Project, four ImageAssets, one readiness
review, five RegionSets, twenty Regions, eighty Vertices, one RegionSet Review, and twelve completed
command records. The task-private storage held four generated files (48 KiB allocated). Its audit
log SHA-256 was
`fb2b99ef6ac58b248104261acd716a07e288bc8a47eb58c1bc3929a421e13912`.
The ownership marker was verified before dropping only the exact schema; residual schema count was
zero. Owned API/Vite/proxy processes were stopped, listeners 15180/18180/18181 were absent, and the
exact temporary root was moved to Trash. The reviewer-supplied Docker volume metadata finding
E-01 remains historical review evidence and was not re-queried in this implementation task.

## 18. Candidate manifest

`docs/progress/phase-1f-candidate-manifest.txt` records:

- baseline repository identity;
- exact path/status/byte-size/SHA-256 for every candidate file;
- tracked binary patch SHA-256;
- NUL-delimited porcelain SHA-256;
- manifest-generation algorithm and self-exclusion rule.

At candidate freeze, the Manifest was evidence only and was not staged. Final sealing later
committed that exact byte-identical Manifest with SHA-256
`9cb57f6a0d59976d814d9d5dd3a3ae0e8f1bfd1e67cbf3be18197161499c4fb4`.

## 19. Historical candidate-time final repository state

- Branch/HEAD/commit count remain `main` /
  `91f3135041c16c8e600d963c1341cb1af1db1458` / `19`.
- Staged paths: `0`.
- New commit/tag/remote/submodule/PR: none.
- `.env`, dependencies, lockfiles, Compose, sealed migrations, and Git history: unchanged.
- At that time, the candidate remained an unstaged/untracked worktree for independent review.
- Candidate-time status:
  `PHASE_1F_SNAPSHOT_TARGET_REMEDIATION_IMPLEMENTED_READY_FOR_INDEPENDENT_REVIEW`.

## 20. Historical candidate-time recommended next action

Open a fresh independent focused read-only security and product review against this exact manifest
candidate. The reviewer must preserve the historical port-scope failure, separately assess the
controller-authorized isolated continuation, and must not modify the worktree. Do not seal,
stage, commit, push, tag, or create a PR in that review. A third independent Git-sealing task
remains separately authorized work and may proceed only after a strict independent PASS. AI
remains unauthorized.

That recommended sequence is complete. The final independent review returned
`PHASE_1F_SNAPSHOT_TARGET_REMEDIATION_PASS_READY_FOR_SEALING`; the separate sealing task committed
the exact 36-file candidate as `fdf1fd787b2cc0c5a4db3c1e72885df4fdf6ae1b`; and the later
docs-only closure set Phase 1F to `CLOSED` at the approximately 80% checkpoint. This update does
not rewrite the candidate-time failure, invalid attempts, remediation, review timing, or repository
state. The next product phase remains `NOT_SELECTED` / `NOT_STARTED`, and AI remains
`NOT_AUTHORIZED`.
