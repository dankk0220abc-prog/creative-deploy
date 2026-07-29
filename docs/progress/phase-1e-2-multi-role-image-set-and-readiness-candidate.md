# Phase 1E-2 — Multi-Role ImageSet and Readiness Candidate Evidence

- Phase Status: `IMPLEMENTED_PENDING_INDEPENDENT_REVIEW`
- Candidate Verdict:
  `PHASE_1E_2_WORKFLOW_GATE_REMEDIATION_IMPLEMENTED_READY_FOR_INDEPENDENT_REVIEW`
- Original Independent Review: `CONTRACT_OR_ARCHITECTURE_DECISION_REQUIRED`
- Fresh Remediation Review: `NOT_YET_PERFORMED`
- Date: `2026-07-29`
- Branch: `main`
- Baseline HEAD: `7b0777c393af705637a1e63f7f25f1dc06f75c1e`
- Baseline Subject: `docs(progress): close phase 1e-1 image assets`
- Baseline Commit Count: `17`
- Current Commit Count: `17`
- Migration Revision: `d4c8a1f7b2e9`
- Parent Revision: `5ed9906e7d33`
- Commit / Stage / Push / Tag: `NONE`
- AI / Image Quality / View Recognition: `NOT_IMPLEMENTED`
- External or Public Storage / URLs: `NOT_IMPLEMENTED`
- Deletion / Real Authentication: `NOT_IMPLEMENTED`
- Local Storage: development/test only
- Production Readiness: `NOT_READY`

## Candidate boundary

The candidate adds four human-declared image roles, immutable role histories, a deterministic
ImageSet checklist/fingerprint, and append-only human READY / NOT READY reviews. It preserves the
sealed Phase 1E-1 private-object and attestation boundary. A role label is not program proof of
the depicted viewpoint, and readiness is not image quality or legal verification.

The original independent review is not erased. Finding F-01 demonstrated a real HTTP 201
`primary_front` replacement from `IMAGE_UPLOADED` and returned
`CONTRACT_OR_ARCHITECTURE_DECISION_REQUIRED`. Project control retained the sealed ADR-0004
workflow gate. This focused remediation corrects the candidate; it is not a fresh independent
approval.

## Frozen decisions

- ADR:
  `docs/decisions/ADR-0005-multi-role-image-set-and-human-readiness-boundary.md`
- Physical data:
  `docs/architecture/paintpilot-image-set-readiness-physical-data-dictionary-v0.1.md`
- Plan:
  `docs/progress/phase-1e-2-multi-role-image-set-and-readiness-plan.md`
- Sole new Revision: `d4c8a1f7b2e9`
- Historical Revisions `a10d3d8dab38` and `5ed9906e7d33` remain unchanged.

## Implementation summary

- Four exact roles with front/back/angle required and detail optional.
- Phase 1E-1 legacy role mapped in place without changing asset identity, history, pointer, bytes,
  storage key, SHA-256, or attestation.
- One append-only readiness-review table with Project-local versions, human actor snapshot,
  canonical fingerprint, exact role asset references, composite owner/Project/role FKs, and
  mutation-rejecting trigger.
- Deterministic completeness, accepted-upload, attestation, required-content-distinctness, private
  object-availability, snapshot-current, blocker, and stale-reason computation.
- Project-locked, Project-scoped idempotent review creation and upload/review race safety.
- Owner-scoped ImageSet/readiness endpoints with strict schemas and safe error envelopes.
- One centralized pure role/current/operation/workflow mutation policy. Primary first upload is
  `DRAFT`-only; primary replacement is review-required/validation-failed-only; references remain
  editable in the four pre-validation states; `IMAGE_VALIDATED` freezes every role.
- Known-new denied commands fail before staging, and the final locked transaction repeats the
  authorization before publication. Safe 409 denial creates no object, asset, command, event,
  pointer, or readiness side effect.
- Four-role responsive workbench with private previews, per-role history, safe add/replace,
  accurate workflow lock explanations, checklist, READY / NOT READY form, retry-key reuse,
  review history, and stale reconfirmation.
- No delete API/control, public URL, AI, viewpoint recognition, quality score, or workflow
  expansion.

## Verification ledger

Invalid attempts remain evidence and are not rewritten as passes:

| Gate | Result |
| --- | --- |
| Baseline identity, clean worktree, DB health, phase state, historical migration hashes | `PASS` |
| First backend unit run | `INVALID_ATTEMPT` — exact four-table/model historical inventories needed the authorized Phase 1E-2 increment; complete rerun passed |
| First migration command using repository `.env` | `INVALID_ATTEMPT` — stale port 5432 authentication failed before schema writes |
| First isolated Phase 1E-2 migration round-trip | `INVALID_ATTEMPT` — naming-convention double prefix in one dropped historical check; corrected and complete round-trip rerun passed |
| First read-only development row-count probe | `INVALID_ATTEMPT` — shell/SQL quoting error; no write; corrected query proved zero rows |
| First frontend typecheck | `INVALID_ATTEMPT` — two historical test literals still used `primary_mvp_input`; corrected and complete rerun passed |
| First historical ImageAsset API integration run | `INVALID_ATTEMPT` — one old test expected replacement to remain blocked in `IMAGE_UPLOADED`; updated for the authorized per-role stale lifecycle and fully rerun |
| First Phase 1E-2 Web test run | `INVALID_ATTEMPT` — two assertions expected absence/wording that conflicted only with the explicit non-capability notice and safe 503 classification; narrowed and fully rerun |
| First focused legacy-migration test | `INVALID_ATTEMPT` — guessed Compose password failed authentication before schema creation; connection values were then derived from the running container |
| First post-test API format gate | `INVALID_ATTEMPT` — one new integration assertion required mechanical Ruff formatting; lint remained clean and full format gate was restarted |
| First browser listener start | `INVALID_ATTEMPT` — an earlier Vite child briefly occupied 5173, so the governed run bound 5174 and the orphan was terminated; no product data was affected |
| First browser upload/READY waits | `INVALID_ATTEMPT` — two evidence locators expected wording different from the rendered safe status; both commands had succeeded and fresh DOM snapshots verified their authoritative state |
| First final-manifest read-only command | `INVALID_ATTEMPT` — zsh reserves `status`; the child shell stopped before producing or writing a manifest and was rerun with a task-specific name |
| First remediation frontend fixture assertion | `INVALID_ATTEMPT` — an existing fixture already contained a primary asset; the test was corrected to use an explicit no-primary fixture and all focused tests reran |
| First remediation format check | `INVALID_ATTEMPT` — four touched Python files required mechanical Ruff formatting; formatting was applied and the affected/full gates were restarted |
| First remediation browser schema name | `INVALID_ATTEMPT` — the generated identifier exceeded PostgreSQL's limit and was truncated; no migration or business write ran, the ownership marker was verified, and only that exact empty schema/root were removed |
| First remediation Vite listener start | `INVALID_ATTEMPT` — the background process inherited terminal input and was suspended; it was terminated and restarted on the same isolated fixture with stdin detached |
| First remediation browser chooser call | `INVALID_ATTEMPT` — an unsupported client convenience method failed before opening a chooser or changing the form; the documented filechooser event flow was then used |
| First remediation direct-API form | `INVALID_ATTEMPT` — an incorrect intended-usage enum returned safe 422 before Service execution; a new key with `private_project` produced the required 409 |
| First remediation whole-schema dump hash | `INVALID_ATTEMPT` — PostgreSQL 17 dump output contains a per-run restrict key and is not a deterministic comparison; exact ordered governed-row SQL plus private-file hashes replaced it |
| First remediation complete `make check` | `INVALID_ATTEMPT` — the correct 55432 port was paired with a guessed password; 198 unit tests had passed, then every affected integration connection failed authentication before fixture/business writes; the active Compose values were derived read-only and the entire chain restarted |
| First remediation cleanup listener probe | `INVALID_ATTEMPT` — a duplicate lsof selector returned usage only; the corrected read-only listener probe ran before and after process cleanup |
| First final migration-hash command | `INVALID_ATTEMPT` — two descriptive historical filenames were guessed incorrectly and shasum performed no read for them; the annotation-aware inventory supplied the real paths and all three hashes were then verified |
| Backend unit suite | `PASS` — 198 tests, 79% coverage, zero skip/xfail, one upstream Starlette deprecation warning |
| Existing ImageAsset PostgreSQL/API suite | `PASS` — 8 tests |
| Phase 1E-2 PostgreSQL/API suite | `PASS` — 11 tests covering the complete role-aware matrix, zero-side-effect denials, readiness, constraints, idempotency/concurrency, upload/review race, compatibility, and fail-closed downgrade |
| Legacy Phase 1E-1 migration compatibility | `PASS` — in-place role map plus old list/ImageSet/private-content reads |
| Focused remediation tests | `PASS` — 15 policy/unit, 19 ImageAsset/ImageSet integration, and 13 ImageAssetManager frontend tests |
| Frontend suite | `PASS` — 10 files, 121 tests, zero skip/xfail |
| Frontend ESLint / TypeScript / production build | `PASS` |
| Backend Ruff / format / mypy | `PASS` |
| Full PostgreSQL integration suite | `PASS` — 49 tests, zero skip/xfail, one upstream Starlette deprecation warning |
| Migration current/heads/history/check and lifecycle | `PASS` — one head, no metadata diff, development head/parent/head, isolated compatibility and refusal probes |
| Complete repository `make check` | `PASS` — 198 unit, 49 PostgreSQL integration, 121 frontend tests, ESLint, TypeScript, and production build |
| Real synthetic browser acceptance and cleanup | `PASS` — real Vite/FastAPI/PostgreSQL/private storage, positive/negative workflow matrix, owner isolation, three viewports, zero residuals |
| Final manifest and exact Git scope | `PASS` — companion manifest includes every candidate file and excludes only itself from recursive hashing |

## Safety and compatibility evidence

- Direct database writes cannot cross owner, Project, or role snapshot boundaries.
- PostgreSQL rejects readiness update/delete and invalid verdict, reason, version, fingerprint,
  required snapshot, and role reference combinations.
- Required duplicate SHA-256 values and missing private objects block READY.
- Replacement retains previous rows and content; a prior matching review becomes stale.
- `primary_front` first/replacement and every reference role/state expectation comes from
  independent test constants rather than the production policy function.
- `IMAGE_UPLOADED` and `IMAGE_VALIDATED` direct primary requests, plus validated reference
  requests, return structured 409 before staging. Exact ordered Project/current/assets/events/
  commands/reviews hashes and private-file hashes remain equal before and after denial.
- Same review key replays only within the same Principal/Project/payload/fingerprint; same-key
  changed facts return 409; other Projects and owners are independent.
- Concurrent reviews receive deterministic Project-local versions. The upload/review race never
  returns an old snapshot as current after replacement.
- Other-owner ImageSet and review operations use the same non-disclosing 404.
- A real Phase 1E-1 row upgraded from `5ed9906e7d33` preserves the asset ID, Project, owner,
  version, current/lifecycle state, lineage, storage key, SHA-256, Project pointer, and bytes.
  Only `primary_mvp_input` becomes `primary_front`; legacy list, ImageSet, and private content
  remain readable.
- Downgrade from `d4c8a1f7b2e9` refuses both append-only review history and non-primary role
  history. Failed downgrade leaves the head and blocking facts intact.

## Real browser evidence

The remediation acceptance run used five 768×768 program-generated JPEG/PNG/WebP fixtures in an
ownership-marked isolated PostgreSQL schema and a dedicated temporary private-storage root. The
controlled SQL status assignments below were test-only negative-contract preparation, not a
normal user workflow or production-data mutation.

- Created one real persisted Project through Vite and the same-origin API.
- Uploaded the first `primary_front` in `DRAFT`; the existing transition produced
  `IMAGE_UPLOADED`. The UI then exposed an accurate workflow lock and no executable primary
  replacement control.
- A direct multipart primary replacement in `IMAGE_UPLOADED` returned structured 409. Exact
  governed-row hash
  `e0680c7a83718152a69461ca767e392daa4c9731ddd1fc9f7f660bf939ae9e21` and
  private-file hash
  `808e4db1842b77fc505fc20701f199f92e8c4b30ab056de453026ef62ead7f74` were
  identical before and after.
- Uploaded `reference_back`, `reference_angle`, and optional `reference_detail` through the UI
  while the Project remained `IMAGE_UPLOADED`; all four private previews decoded to 768×768.
- Appended READY version 1, then used controlled isolated-fixture SQL to prepare
  `IMAGE_REVIEW_REQUIRED`. The UI allowed primary replacement; version 1 and its old bytes
  remained, version 2 linked through `supersedes_image_asset_id`, workflow returned to
  `IMAGE_UPLOADED`, and readiness derived `stale`.
- Appended READY version 2, then used controlled isolated-fixture SQL to prepare
  `IMAGE_VALIDATED`. Every role showed the validation freeze and no replacement control.
  Direct primary/reference attempts returned structured 409. A deterministic ordered governed
  snapshot hash remained
  `36f3432c0ec6fb76caec6bb6181292dfbcdfaf24fe124dd601259ef74d7a18ee`
  before/after and private-file hash
  `67095443cb6cc80699af394ae884086f845eceb3621089b7c5c82d12f24591dc`
  remained unchanged; no rejected idempotency key had a command row and staging contained zero
  files.
- A second FastAPI process using another configured Principal returned the same safe Project 404.
- At 1440×900, 768×1024, and 390×844, inner/client/scroll widths matched the requested viewport
  with no horizontal overflow. All four previews were complete 768×768 images; the validated
  freeze remained present with zero replace buttons at tablet/mobile. Console warning/error
  count was zero and the real API/private-image traffic had no unexplained network failure.

Before cleanup the isolated fixture contained exactly one Project, five immutable assets, two
READY reviews, eight completed command records, three transition events, and five private
objects. The superseded and current primary bytes were both present, staging was empty, and four
rejected keys had zero command rows. Cleanup revalidated the marker token before removing only
the isolated schema and dedicated temporary fixture/storage/log root. The schema-prefix count
returned zero, ports 18002/18003/5175 had no listener, the fixture root was absent, and the same
healthy Compose PostgreSQL service retained named volume
`creativedeploy_creativedeploy_postgres_data`.

## Review handoff

Use a fresh independent GPT-5.6 Sol review at the highest available reasoning level. Review the
exact final manifest and production hashes read-only. Do not stage, commit, push, tag, close the
phase, or treat passing local gates as approval.
