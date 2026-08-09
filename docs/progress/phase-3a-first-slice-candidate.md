# Phase 3A Fixture Provider First Slice — Implementation Evidence

Status: `PHASE_3A_FIXTURE_PROVIDER_CANDIDATE_FROZEN_READY_FOR_INDEPENDENT_REVIEW`

This document records the interrupted local implementation candidate. It is not an approval, seal, production-readiness statement, or authorization for a real provider.

## Baseline and branch

- Repository: `/Users/danke/Developer/CreativeDeploy`
- Approved architecture branch: `design/phase-3a-byok-provider-foundation-20260804`
- Approved architecture commit: `29b427fd3c69acab6b9bac30e644786626608fe6`
- Approved architecture tree: `148db79249dc69e223a6e4730c34f01a248ad002`
- Approved architecture parent: `ff6363af4ac44d78116542fff29e3564fbd82769`
- Implementation branch: `feat/phase-3a-fixture-provider-foundation-20260805`
- Current HEAD remains the approved architecture commit. No implementation commit was created.

## Changed paths

- `.env.example`
- `Makefile`
- `apps/api/pyproject.toml`
- `apps/api/uv.lock`
- `apps/api/migrations/versions/3a01c7e9b4d2_add_phase3a_registries.py`
- `apps/api/migrations/versions/3a02d8f0c5e3_add_phase3a_credential_security.py`
- `apps/api/migrations/versions/3a03e9a1d6f4_add_phase3a_policies_invocations_ledgers.py`
- `apps/api/migrations/versions/3a04fab2e7a5_enable_phase3a_fixture_registry.py`
- `apps/api/src/creativedeploy_api/ai/__init__.py`
- `apps/api/src/creativedeploy_api/ai/canonicalization.py`
- `apps/api/src/creativedeploy_api/ai/constants.py`
- `apps/api/src/creativedeploy_api/ai/encryption.py`
- `apps/api/src/creativedeploy_api/ai/fixture_provider.py`
- `apps/api/src/creativedeploy_api/api/dependencies.py`
- `apps/api/src/creativedeploy_api/api/router.py`
- `apps/api/src/creativedeploy_api/api/routes/ai_foundation.py`
- `apps/api/src/creativedeploy_api/app_factory.py`
- `apps/api/src/creativedeploy_api/core/config.py`
- `apps/api/src/creativedeploy_api/core/secret_files.py`
- `apps/api/src/creativedeploy_api/db/models/__init__.py`
- `apps/api/src/creativedeploy_api/db/models/ai_foundation.py`
- `apps/api/src/creativedeploy_api/db/models/paint_project.py`
- `apps/api/src/creativedeploy_api/repositories/ai_foundation.py`
- `apps/api/src/creativedeploy_api/schemas/ai_foundation.py`
- `apps/api/src/creativedeploy_api/services/ai_foundation.py`
- `apps/api/tests/integration/test_image_set_readiness_api.py`
- `apps/api/tests/integration/test_initial_paint_project_migration.py`
- `apps/api/tests/unit/test_ai_foundation_routes.py`
- `apps/api/tests/unit/test_ai_foundation_security.py`
- `apps/api/tests/unit/test_database_metadata.py`
- `apps/api/tests/unit/test_paint_project_models.py`
- `apps/web/PRODUCT.md`
- `apps/web/src/__tests__/aiFoundationApi.test.ts`
- `apps/web/src/api/aiFoundation.ts`
- `apps/web/src/components/AppShell.tsx`
- `apps/web/src/i18n/resources.ts`
- `apps/web/src/index.css`
- `apps/web/src/pages/AIProjectPolicyPage.tsx`
- `apps/web/src/pages/AISettingsPage.tsx`
- `apps/web/src/pages/ProjectDetailPage.tsx`
- `apps/web/src/router/AppRoutes.tsx`
- `apps/web/src/vite-env.d.ts`
- `docs/progress/phase-3a-first-slice-candidate.md`

## Implemented capability

- Additive A/B/C/D migrations with revisions `3a01c7e9b4d2`, `3a02d8f0c5e3`, `3a03e9a1d6f4`, and `3a04fab2e7a5`.
- Fixture-only provider, two fixture models, three capabilities, credentials and project grants.
- AES-256-GCM envelope encryption with per-record DEKs, independent nonces/tags, stable AAD, key fingerprints, and a development/test-only 32-byte binary root-key file.
- User/project policy, `FIXTURE_CREDITS` budgets, counters and reservations.
- Canonicalized idempotency, invocation/attempt lifecycle, bounded retries, outcome-unknown handling, recovery support, write-once final attempts, and append-only event/usage/cost/audit relations.
- Feature-gated API and bilingual settings/project-policy UI. No real provider adapter or external network call was added.

## Security boundary

- The feature defaults off.
- Fixture root-key loading is rejected outside development/test and when a staging run identity is present.
- Temporary credentials are request-local and represented in persisted safe payloads only as a boolean.
- Revoked/replaced credentials erase all decryptable envelope fields.
- The fixture adapter imports no HTTP client and the unit test denies socket construction.
- No real credential, provider, billable operation, push, pull request, merge, tag, or deployment was used.

## Focused validation completed before stop

| Command | Exit | Result |
| --- | ---: | --- |
| `uv run ruff check src tests && uv run mypy src` | 0 | Ruff passed; mypy passed for 79 source files. |
| `pnpm typecheck && pnpm lint && pnpm test -- --run && pnpm build` | 0 | 15 files / 163 web tests passed; 131 modules built. |
| `POSTGRES_HOST=127.0.0.1 uv run pytest -q tests/integration/test_initial_paint_project_migration.py -k 'initial_paint_project_migration_round_trip_and_constraints or phase3a_'` | 0 | 4 passed, 14 deselected. |
| Earlier focused Phase 3A unit/security/metadata tests | 0 | 33 passed. |
| Earlier feature-gate route tests | 0 | 2 passed. |

The PostgreSQL integration group exercised migration round-trip and drift checking; downgrade refusal; fixture seed removal; temporary-credential non-persistence; encrypted saved-credential lifecycle; grants and policies; success, terminal failure, bounded retry, and outcome-unknown states; idempotent replay; admission rejection with zero additional adapter calls; and database rejection of mutation on all four append-only relations.

## Supply-chain stop evidence

- Command: `make supply-chain-check`
- Run ID: `local_20260805143519_c46c4efda342`
- Exit code: `1`
- First failing subgate: `secret-scan`
- Scanner output: approximately 3.68 MB scanned; 2 findings reported in redacted mode.
- Scanner report file: none was produced by the repository script; this document preserves the command-level evidence without exposing finding material.
- Remaining `audit-api`, `audit-web`, and `immutable-reference-check` prerequisites were not reached.
- Candidate production hash status: not applicable; no candidate commit exists.

The supply-chain target was not repeated. In accordance with the frozen stop condition, canonical validation, browser validation, secret-key generation, the Impeccable detector, diff-scoped secret scanning, and Candidate commit creation were not performed after this failure.

## Secret finding triage and remediation

- `SECRET-FINDING-01`: `generic-api-key`, `apps/web/src/__tests__/aiFoundationApi.test.ts`, original line 62, untracked/added content, classification `B — Test/Fixture Secret-like Value`.
- `SECRET-FINDING-02`: `generic-api-key`, `apps/web/src/__tests__/aiFoundationApi.test.ts`, original line 91, untracked/added content, classification `B — Test/Fixture Secret-like Value`.
- Root cause: two source literals used provider-key-like, high-entropy fixture forms even though the tests exercise only request-local transmission and response redaction behavior.
- Remediation: both literals now come from one runtime fixture generator with an explicitly non-real marker and a per-call runtime suffix. The assertions for request transmission, browser-storage non-persistence, response redaction, and ciphertext omission are unchanged.
- Scanner policy: unchanged. No allowlist, detector suppression, severity change, or scanner configuration change was used.
- External-secret assessment: no real external credential was identified. The involved test file is untracked and has no history on any local Git ref, so credential rotation is not applicable.
- Matching material is intentionally omitted from this evidence.
- Targeted scanner run `phase3a_targeted_20260808a`: 28 exact remediation, Credential, fixture-root-key, configuration, and documentation paths; exit `0`; findings `0`.
- Full repository Secret target run `phase3a_fullsecret_20260808a`: approximately 3.69 MB scanned; exit `0`; findings `0`.
- Affected-path validation: `apps/web/src/__tests__/aiFoundationApi.test.ts`; 1 file / 4 tests passed. No previously passed full Web group was repeated.

## Resumed supply-chain stop evidence

- Command: `RUN_ID=phase3a_supply_20260808a make supply-chain-check`
- Run ID: `phase3a_supply_20260808a`
- Overall result: `FAIL`; the command stopped during `audit-api`. The execution wrapper did not preserve the exact process exit code, so that numeric value is `NOT VERIFIED`; the missing completion and skipped prerequisites prohibit a PASS claim.
- `secret-scan`: `PASS`; approximately 3.69 MB scanned; findings `0`.
- `audit-api`: `FAIL/NOT VERIFIED`; `pip-audit` was invoked but emitted no completion summary or vulnerability detail before the target terminated. No package finding is asserted without evidence.
- `audit-web`: `NOT RUN` because the prerequisite chain stopped at `audit-api`.
- `immutable-reference-check`: `NOT RUN` because the prerequisite chain stopped at `audit-api`.
- The supply-chain target was not repeated. Canonical and browser gates were not entered.

## Audit-api diagnosis and resumed gate evidence

- Diagnostic authority: independently authorized narrow `audit-api` diagnosis after the prior run `phase3a_supply_20260808a`; no Phase 3A implementation file was changed.
- Aggregate command discovery: `supply-chain-check` declares ordered prerequisites `secret-scan audit-api audit-web immutable-reference-check`; `audit-api` executes exactly `uv run --project apps/api pip-audit --timeout 60`.
- Environment and lock semantics: the command selects `apps/api` and its existing `.venv`; `uv run` performs its normal project-environment synchronization unless `--no-sync` is supplied. The invoked target does not assert `--locked` or `--frozen`; the checked-in `apps/api/uv.lock` resolves `pip-audit` `2.10.1` and the local `creativedeploy-api` package as editable.
- First and only standalone `audit-api` invocation: exit `0`; `pip-audit` reported no known vulnerabilities. It skipped the local editable `creativedeploy-api` `0.1.0` because that package is not published on PyPI. No vulnerability, dependency/lock inconsistency, or audit-tool invocation failure was observed.
- Audit database behavior: `pip-audit` was invoked without an offline database option, so its advisory lookup may access its network vulnerability service. No secret-bearing environment value or scanner match was recorded; command output was captured only in memory with redaction.
- Resumed aggregate command: `RUN_ID=phase3a_supply_20260808b make supply-chain-check`; exit `0`. Secret scan reported no leaks; API and Web audits reported no known vulnerabilities; immutable reference validation passed (4 actions, 11 container references).
- Canonical command: `make check ENV_FILE=.env.example`; exit `2`. Configuration audit passed and resolved `local_postgres` at `127.0.0.1:55432`, database `creativedeploy`; the first failing gate was `ensure-db` because the resolved PostgreSQL endpoint was unavailable. No automatic retry or remediation was attempted.
- Browser settings flow: `NOT RUN`, because canonical validation did not pass. No temporary fixture root-key file or temporary browser/runtime resource was created, so no such cleanup was required.

## Browser and visual acceptance

- Browser main flow: `NOT RUN`.
- Desktop evidence: `NOT VERIFIED`.
- 390 px evidence: `NOT VERIFIED`.
- Chinese locale evidence: `NOT VERIFIED`.
- Console evidence: `NOT VERIFIED`.
- User visual acceptance: `NOT READY`; the required gate sequence stopped before browser work.

## Intentionally not repeated

- Phase 2E demo lifecycle
- Existing PaintPilot browser lifecycle
- Staging drill
- Backup/restore
- Full architecture review
- Any further supply-chain retry after the resumed `phase3a_supply_20260808a` failure

## Remaining unverified at conclusion

- Canonical remediation and a successful `make check ENV_FILE=.env.example` result
- One real-browser fixture settings flow with a dynamically generated and securely deleted 32-byte root key
- Impeccable changed-target detector
- Diff-scoped secret scan
- Local Candidate commit identity
- User-led visual acceptance
- Subsequent independent focused review

## Next action

Restore the resolved PostgreSQL service through separately authorized environment remediation, then rerun canonical validation once. Do not rerun aggregate supply-chain, create a Candidate commit, start browser validation, or begin independent review in this diagnostic scope.

## Canonical formatting remediation resume — 2026-08-08

- Authorized remediation scope: Ruff formatting only for `apps/api/src/creativedeploy_api/ai/canonicalization.py`; no business logic, string, canonicalization rule, hash, artifact identity, idempotency, Ruff configuration, or second implementation file was changed.
- Baseline preflight: repository, branch, HEAD/tree/parent, `main`, and `origin/main` matched the authorized identities. The actual dirty-path set exactly matched the documented 41-path set, the index was empty, and no merge, rebase, cherry-pick, revert, bisect, or sequencer state existed.
- Ruff formatting: exit `0`; exactly one file was reformatted. Pre-format SHA-256 was `7ee9e35903f99704d0f4f7597508a114a13b8bfb6dc0e0c02e0cb342ed38f627`; post-format SHA-256 was `3b72c5b5bef102d7017605bc1b364a5b53836a2192cb1d6a489d1b485b013207`.
- AST semantic equivalence: `PASS`. The repository Python 3.13.14 parsed both copies with `ast.parse`; `ast.dump(..., include_attributes=False)` outputs were byte-identical.
- Focused formatting validation: single-file `ruff format --check` exit `0`; single-file `ruff check` exit `0`; `git diff --check` exit `0`; dirty paths remained exactly 41; no unknown untracked path appeared; the index remained empty.
- Formatting evidence cleanup: the pre-format copy and AST dumps were held only in a repository-external `0700` temporary directory and were deleted after comparison; no matching temporary directory remained.
- Canonical command: `make check ENV_FILE=.env.example`; invoked exactly once in this resume; numeric exit code `2`.
- Canonical subgates before failure: configuration audit and PostgreSQL probe passed for `127.0.0.1:55432/creativedeploy`; `config-check` passed; `lint-api` passed; `format-check-api` passed with 116 files already formatted; `typecheck-api` passed for 79 source files.
- First deterministic canonical failure: `apps/api/tests/unit/test_paint_project_models.py::test_registered_models_and_metadata_contain_exactly_phase_1f_business_tables` at line 490. The asserted 14-model Phase 1F tuple did not equal `REGISTERED_MODELS`, whose right-hand side contained 25 additional models beginning with `ProviderDefinition`.
- `test-api` result at stop: 430 collected, 424 passed, 6 failed, 1 warning. The other observed failures were the exact database-identifier contract, ORM/migration identifier contract, every-table check-constraint requirement, PaintProject constraint-set contract, and the subprocess assertion that `REGISTERED_MODELS` has length 14.
- No automatic remediation of these new failures was attempted. The canonical command was not rerun, and later canonical prerequisites were not reached.
- Browser Settings Flow: `NOT RUN`, because canonical validation did not pass. Desktop, 390 px, `zh-CN`, `en-US`, console, request-audit, credential redaction, grant/policy, invocation, usage/audit, revoke/denial, and refresh behavior remain `NOT VERIFIED` in this resume.
- Fixture root-key cleanup: `NOT APPLICABLE`. No fixture root-key file, fake Credential, browser session, or temporary application service was created.
- Evidence reused and intentionally not repeated: the prior zero-finding Secret Scan, passing `audit-api`, passing `audit-web`, passing immutable-reference check, and aggregate supply-chain run `phase3a_supply_20260808b` exit `0`. `make supply-chain-check` was not rerun.
- User visual acceptance: `NOT READY`; the prerequisite canonical Gate failed before browser evidence could be produced.
- Resume verdict: `PHASE_3A_CANONICAL_GATE_FAILED_REMEDIATION_REQUIRED`.

## ORM and migration metadata contract remediation — 2026-08-08

- Baseline preflight: authoritative repository, implementation branch, HEAD/tree/parent,
  `main`, and `origin/main` matched the authorized identities. The initial actual dirty set exactly
  matched the documented 41-path set, the index was empty, and no merge, rebase, cherry-pick,
  revert, bisect, or sequencer state existed.
- Reproduced failure file: `apps/api/tests/unit/test_paint_project_models.py`; 36 passed and the
  exact six failures were the legacy-only 14-model registry assertion, legacy-only metadata
  identifier assertion, legacy-only ORM/migration identifier assertion, universal per-table
  CheckConstraint assertion, the PaintProject constraint set missing the Migration C zero-UUID
  check, and the import subprocess asserting 14 models.
- Semantic stop-condition review: the frozen 25 Phase 3A model names map one-to-one to the 25
  persistent tables created by Migrations A/B/C. ORM and migration definitions matched for 65
  foreign keys, 23 unique constraints, 25 primary keys, and 16 indexes. The Phase 3A check set
  matched after including Migration C's zero-UUID check on the legacy `paint_projects` table.
  No missing model, extra model, table mismatch, FK-target mismatch, ON DELETE mismatch, or
  frozen-schema semantic conflict was found. Migration D remains seed-only.
- Registry governance: `EXPECTED_PHASE_1F_MODELS` freezes the approved 14 models;
  `EXPECTED_PHASE_3A_MODELS` freezes the 25 additive models; the sets are disjoint; and the
  complete registry contract requires their exact 39-model union with no missing or unexpected
  entry.
- Identifier diagnosis: the three original InvocationRequest FK identifiers were 65, 70, and 76
  UTF-8 bytes. They were replaced only in the ORM and unpublished Migration C by
  `fk_invreq_requested_credential` (30 bytes),
  `fk_invreq_requested_model_definition` (36 bytes), and
  `fk_invreq_requested_provider_definition` (39 bytes). Source columns, target tables/columns,
  nullability, relationships, and `ON DELETE RESTRICT` are unchanged; ORM and migration names are
  byte-for-byte identical and collision-free.
- Identifier governance: the exact table/constraint/index contract now covers all 371 explicit
  identifiers, checks UTF-8 byte length against PostgreSQL's 63-byte limit, checks the approved
  ASCII pattern, and rejects collisions in each table-constraint namespace and the schema index
  namespace. The longest remaining explicit identifier is 62 bytes.
- CheckConstraint governance: `EXPECTED_CHECK_CONSTRAINTS_BY_TABLE` explicitly covers all 39
  registered tables. Approved business checks remain exact, Phase 3A credential lifecycle,
  `FIXTURE_CREDITS`, budget/reservation, Invocation/Attempt status, and zero-UUID checks are exact,
  and association/ledger tables with no business check are explicitly mapped to an empty set.
- ORM/migration metadata governance: a no-database recorder executes the upgrade declarations of
  A/B/C and compares exact Phase 3A table names, FK source/target/name/ON DELETE shapes, unique
  column/name shapes, index column/uniqueness/partial-predicate shapes, and normalized check SQL to
  ORM metadata. This includes the active Grant and active Attempt partial unique indexes,
  idempotency scope, replacement lineage, and every Project Model Policy association unique.
- Focused validation: the remediated original file passed 44 tests; the existing metadata file
  passed 19 tests; Ruff check passed for the three changed Python files; Ruff format check reported
  all three files formatted; mypy passed for the changed production ORM module; and
  `git diff --check` passed.
- Dirty Manifest: the existing tracked governance test is the authorized, documented 42nd dirty
  path. The existing Phase 1E-2 integration test is the authorized 43rd path for the later
  downgrade-refusal contract remediation; no unknown untracked path was created.
- Supply-chain evidence intentionally reused: aggregate run `phase3a_supply_20260808b` remains exit
  `0` with Secret scan, API audit, Web audit, and immutable-reference checks passed. The aggregate
  supply-chain target was not repeated because this remediation changes no dependency.
- Canonical and Browser Settings Flow evidence for this remediation follows below; no Candidate
  commit, push, pull request, real Provider call, or fifth migration was created.

### Canonical result after ORM and migration metadata remediation

- Command: `make check ENV_FILE=.env.example`; invoked exactly once after all focused metadata
  gates passed; exit `2`.
- Passed prerequisites: configuration audit, PostgreSQL probe at
  `127.0.0.1:55432/creativedeploy`, `config-check`, `lint-api`, `format-check-api` for 116 files,
  `typecheck-api` for 79 source files, and 432 unit tests. The unit group retained one external
  Starlette/httpx deprecation warning.
- Integration result: 54 passed, 2 failed, one warning. The first failure was
  `test_phase_1e_2_downgrade_refuses_to_discard_governed_facts[readiness_review-readiness review history would be lost]`.
  Its downgrade-refusal message assertion passed, but its subsequent legacy assertion expected
  `alembic_version=2b1c4d5e6f70`; the database correctly remained at the current Phase 3A head
  `3a04fab2e7a5`. The second parameterized `reference_asset` case failed on the same revision
  assertion.
- Stop handling: no automatic remediation or second canonical run was attempted. Browser Settings
  Flow, desktop/390px evidence, `zh-CN`/`en-US`, console/network review, and user visual acceptance
  remain `NOT RUN` / `NOT VERIFIED`.
- Temporary root-key cleanup: `NOT APPLICABLE`; no fixture root-key, fake Credential, browser
  session, or task-owned application resource was created.
- Remediation verdict: `PHASE_3A_CANONICAL_GATE_FAILED_REMEDIATION_REQUIRED`.

### Alembic downgrade-refusal contract remediation resume — 2026-08-08

- Baseline preflight matched the authorized repository, branch, HEAD/tree/parent, `main`, and
  `origin/main`; the empty index and no in-progress Git operation were also confirmed. The
  documented 42-path Candidate matched exactly before this remediation. The existing
  `apps/api/tests/integration/test_image_set_readiness_api.py` is the one authorized 43rd path;
  the post-change 43-path dirty manifest matches this document exactly, with no unknown path.
- Diagnosis: both parameterized cases of
  `test_phase_1e_2_downgrade_refuses_to_discard_governed_facts` made the expected downgrade
  attempt to `5ed9906e7d33`, failed nonzero with the expected Phase 1E-2 governed-fact refusal
  message, and retained the corresponding fact. The only failure was the obsolete assertion that
  `alembic_version` became `2b1c4d5e6f70`; live reproduction observed `3a04fab2e7a5` after each
  refusal. No partial downgrade or wrong-migration refusal was observed.
- Contract change: the test records a non-empty `revision_before_attempt` immediately before the
  dangerous downgrade, retains the nonzero-result and exact refusal-message assertions, then
  asserts `revision_after_attempt == revision_before_attempt` before checking the protected
  readiness-review or reference-asset fact. It does not bind the contract to a future-changing
  Alembic head SHA.
- Focused validation: an initial bare pytest invocation was `INVALID_ATTEMPT` because it omitted
  the repository's PostgreSQL environment and failed during fixture configuration before either
  test body. With the canonical integration environment, pre-change reproduction was `2 failed`
  only on the stale revision assertion. After the change, the focused parameterization was
  `2 passed, 9 deselected` (one external Starlette/httpx warning). Ruff check, Ruff format check,
  and `git diff --check` all passed for the changed Python test.
- Canonical gate: `make check ENV_FILE=.env.example` was invoked exactly once. Its captured
  output showed all API prerequisites, `432 passed` unit tests, the integration group proceeding
  past the remediated test, and the sequential Web lint/typecheck/test/build artifacts refreshed
  in this run; the 16-item Vitest cache recorded no failures and the Web build artifact refreshed.
  The executor output truncated before returning its numeric status, so exit `0` is `INFERRED`
  from Make's sequential completion rather than independently captured. No second canonical run
  was made.
- Browser Settings Flow: `NOT VERIFIED`. A repository-external 32-byte, mode-0400 fixture root
  key and a separate local OIDC client-secret file were generated under a mode-0700 temporary
  root. The first API startup omitted the local OIDC configuration and produced an expected
  local configuration failure; the corrected local OIDC/API startup returned the login redirect.
  The available in-app browser did not send a request to the local OIDC provider and rendered
  `identity_provider_unavailable`; no Chrome or external-browser session was available. Therefore
  no synthetic-user Project, Credential, Grant, Policy, Invocation, revoke/denial, locale,
  desktop, or 390px assertion was performed. The browser console contained no error or warning,
  and no real Provider request was made.
- Cleanup: all three temporary services were stopped. The temporary root key and local OIDC
  client-secret were individually removed with the empty 0700 temporary root; the shared
  PostgreSQL volume was retained.
- Supply-chain evidence intentionally reused: `phase3a_supply_20260808b` exit `0` remains the
  applicable aggregate Secret Scan/API audit/Web audit/immutable-reference evidence. It was not
  rerun because this remediation changed only an integration-test contract and evidence record.

## User visual acceptance — 2026-08-09

- Result: `PHASE_3A_VISUAL_ACCEPTANCE_PASS`.
- Desktop reviewed areas: Models & Providers; API Credentials; Project AI Settings; Usage & Audit.
- 390 px reviewed areas: compact authenticated header; 2x2 four-step journey; Models page;
  Credentials mobile order; Project AI Settings; Usage & Audit; progressive disclosure for test
  and environment details.
- Remaining low-value cosmetic preferences are non-blocking backlog. This manual acceptance does
  not claim that the UI is perfect.
- No screenshot or credential, temporary root-key, or temporary OIDC secret value is included in
  this evidence record.

## Final Candidate freeze execution — 2026-08-09

- Exact preflight: authoritative repository, implementation branch, HEAD/tree/parent, local
  `main`, `origin/main`, and GitHub `main` matched the authorized identities; the index was empty;
  no Git operation was active; and the actual 43-path dirty set exactly matched `Changed paths`.
- Evidence freshness: the four Migration files have not changed after their applicable focused
  metadata/integration validation. Dependency declarations, lockfiles, audit configuration,
  Secret scanner configuration, immutable-reference configuration, and supply-chain recipes have
  not changed after aggregate run `phase3a_supply_20260808b` passed with exit `0`.
- Final minimal hygiene: `git diff --check` passed; the 43-path manifest comparison passed; the
  pinned, redacted, network-disabled diff-scoped gitleaks scan covered all 43 paths, scanned about
  1.08 MB, found no leaks, and exited `0`; the four exact Phase 3A revisions and sole Alembic head
  `3a04fab2e7a5` were confirmed.
- Database readiness: `make ensure-db ENV_FILE=.env.example` exited `0` for the repository
  development PostgreSQL at `127.0.0.1:55432/creativedeploy`. The service was already available,
  so no `db-up`, configuration change, volume deletion, or data reset was performed.
- Final canonical command: `make check ENV_FILE=.env.example`; invoked exactly once in this final
  execution; numeric exit `0`.
- Final canonical sub-gates: configuration audit and PostgreSQL probe passed; API Ruff lint passed;
  all 116 API files were formatted; mypy passed for 79 source files; 432 API unit tests passed; the
  integration database reported `3a04fab2e7a5 (head)` and 56 integration tests passed; Web lint and
  typecheck passed; 15 Vitest files / 163 tests passed; and the Vite build completed with 131
  modules transformed.
- The only reported test warnings were the existing external Starlette/httpx deprecation warning;
  no canonical failure was present. Full supply-chain, focused Phase 3A suites, browser flows,
  architecture review, and visual review were intentionally not repeated.
- No real Provider, real API key, real model call, real model cost, push, pull request, independent
  review, deployment, or next-phase work was performed by this executor.

## Security/concurrency remediation metadata expectation resume — 2026-08-09

- Frozen Candidate baseline: `edb62dbe2ce20b4090eddff877583459f56ff39f`; this resume began from
  its unchanged tree with the uncommitted H-01 and BM-01 through BM-09 remediation present.
- Prior implementation evidence reused: H-01/BM-01 through BM-09 production remediation and the
  focused real-PostgreSQL concurrency group (`9 passed / 15 deselected`) had already passed. Those
  focused concurrency, membership-race, budget, cancellation/completion, recovery, catalog, and
  Migration D suites were intentionally not rerun here.
- Initial canonical diagnosis: the one preceding canonical run reached API unit tests and failed
  only because four exact metadata-contract assertions omitted
  `ck_invocation_requests_final_attempt_success_only` from their frozen expectation sets.
- Production-contract verification: the ORM and Migration C
  (`3a03e9a1d6f4_add_phase3a_policies_invocations_ledgers.py`) both declare the same 49-byte
  PostgreSQL `CheckConstraint` on `invocation_requests`:
  `final_attempt_id IS NULL OR status = 'succeeded'`. It matches the final-attempt success-only
  remediation and remains compatible with the existing final-attempt FK and write-once trigger.
  No production ORM, migration, service, repository, identity, route, encryption, frontend,
  dependency, or lockfile change was made by this metadata-expectation resume.
- Metadata-contract change: `apps/api/tests/unit/test_paint_project_models.py` now adds that
  identifier to the exact Phase 3A CheckConstraint contract and the exact
  `invocation_requests` table map, and updates the exact identifier cardinality from 371 to 372.
  Equality-based actual-metadata, ORM/Migration, identifier-limit, collision, 39-table, legacy-14,
  and Phase-3A-25 governance assertions remain unchanged.
- Focused metadata validation: the pre-change reproduction was exactly `4 failed, 40 passed`; after
  synchronization, `apps/api/.venv/bin/pytest -q apps/api/tests/unit/test_paint_project_models.py`
  passed `44 passed`. Ruff check, Ruff format check, and `git diff --check` passed.
- Supply-chain freshness: dependency declarations, lockfiles, Web dependencies, Secret scanner,
  supply-chain scripts/configuration, and immutable-reference configuration remain unchanged.
  Aggregate evidence `phase3a_supply_20260808b` is therefore reused; aggregate supply-chain was
  not rerun. A pinned, redacted, network-disabled diff-scoped gitleaks scan of the remediation
  paths found no leaks.
- Final canonical: after `make ensure-db ENV_FILE=.env.example` confirmed the existing repository
  PostgreSQL at `127.0.0.1:55432/creativedeploy`, the single authorized
  `make check ENV_FILE=.env.example` invocation exited `0`: 434 API unit tests passed, 62
  integration tests passed, and Web lint, typecheck, 15 Vitest files / 163 tests, and production
  build passed. The only warning was the existing external Starlette/httpx deprecation warning.
- Visual evidence reused: `PHASE_3A_VISUAL_ACCEPTANCE_PASS`; no frontend path changed and no
  browser or visual acceptance was repeated. No real Provider, key, external model call, or cost
  was used. Final independent focused re-review remains pending and is not claimed as passed.

## Final two-finding security remediation — 2026-08-09

- Previous Candidate: `fa75c2af643b537c0635e126f4f585c123c14f9b`. The final focused delta
  re-review left only BM-06 and BM-08 open; all other findings and their unchanged evidence remain
  closed and were not reinvestigated by this executor.
- BM-06: the locked `recover_expired_admissions()` decision now treats
  `InvocationAttempt.dispatched_at IS NOT NULL` as dispatch evidence. The real PostgreSQL recovery
  regression includes an expired `reserved` / `admitted` case with only `dispatched_at` present;
  it requires `reconciliation_required` / `outcome_unknown`, preserves both reserved counters,
  performs no Adapter dispatch, and proves a second recovery does not settle or decrement again.
  The same test retains the truly undispatched control and proves it still releases with
  `dispatch_not_started`.
- BM-06 focused command: the repository integration environment invoked
  `pytest apps/api/tests/integration/test_initial_paint_project_migration.py::test_phase3a_orphan_recovery_requires_proof_dispatch_never_started -m integration`;
  numeric exit `0`, `1 passed`, `0 failed`, `0 deselected`, no warning.
- BM-08: Migration D now executes a dedicated SQLSTATE `55000` preflight before every destructive
  seed `DELETE` when the fixture Provider owns any ModelDefinition outside the two exact seed
  model IDs. The regression proves the explicit preflight message was returned rather than a
  `ForeignKeyViolation`, and that the extra model, both seed models, fixture Provider, three seed
  Provider-capability rows, five seed Model-capability rows, and Alembic head remained intact.
- BM-08 focused command: the repository integration environment invoked the exact existing clean
  Migration D downgrade node plus
  `test_phase3a_fixture_seed_downgrade_refuses_non_seed_model_before_delete`; numeric exit `0`,
  `2 passed`, `0 failed`, `0 deselected`, no warning. The existing clean path still deletes the
  exact fixture seed set.
- Scoped hygiene: an initial zsh Ruff wrapper passed the three paths as one filename and exited
  `1` without inspecting or changing code. The corrected Ruff lint exited `0`; its first format
  check identified the modified integration test, Ruff formatted that one authorized file, and
  the final three-path Ruff lint and format check both exited `0`. Mypy on the changed production
  service exited `0`; `git diff --check` exited `0`. A first temporary-file scanner wrapper was
  rejected before Docker or gitleaks execution because of its cleanup operation. The final pinned,
  redacted, network-disabled gitleaks scan mounted only the three changed Python files, scanned
  about 335.56 KB, found no leaks, and exited `0`.
- Database readiness: `make ensure-db ENV_FILE=.env.example` exited `0` and confirmed the existing
  repository PostgreSQL at `127.0.0.1:55432/creativedeploy`; no `db-up`, reset, volume deletion, or
  configuration change was performed.
- Canonical: `make check ENV_FILE=.env.example` was invoked exactly once and exited `0`. Ruff
  passed; 116 Python files were formatted; mypy passed for 79 source files; 434 API unit tests
  passed; Alembic reported the single head `3a04fab2e7a5`; 63 integration tests passed; Web lint
  and typecheck passed; 15 Vitest files / 163 tests passed; and the Vite build transformed 131
  modules. The only test warning was the existing external Starlette/httpx deprecation warning.
- Supply-chain evidence `phase3a_supply_20260808b` remains applicable and was not rerun: no
  dependency declaration, lockfile, dependency, supply-chain configuration, Secret scanner
  configuration, or immutable-reference path changed. Visual evidence
  `PHASE_3A_VISUAL_ACCEPTANCE_PASS` remains applicable and was not repeated: no frontend path
  changed.
- No real Provider, real key, external model call, paid cost, architecture change, fifth Migration,
  push, pull request, merge, or independent re-review was performed. This record does not claim
  that BM-06 or BM-08 has passed the required new independent focused re-review.

## BM-06 locked-current-state remediation — 2026-08-09

- Previous Candidate: `bb0ab05bd4757ce43e886bbaa085e3715638e00b`. Its tree was
  `fa6f7f3331efc1fc5360a622b23787d7c1d22117` and its parent was
  `fa75c2af643b537c0635e126f4f585c123c14f9b`. The preceding independent two-finding
  re-review closed BM-08 and left only `BM-06-LOCK-001` open. H-01, BM-01 through BM-05,
  BM-07, BM-08, and BM-09 remain closed and were not reopened.
- Root-cause verification: before this remediation, candidate discovery first selected scalar
  Reservation IDs, but each candidate transaction then loaded the Reservation and Invocation as
  ORM entities before acquiring its approved row locks. The later default `SELECT ... FOR UPDATE`
  calls returned those same identity-map instances without guaranteeing scalar repopulation.
  A repository-environment probe using SQLAlchemy `2.0.51` observed the same identity and the
  pre-update scalar after the default lock query; the single
  `execution_options(populate_existing=True)` mechanism retained the identity and refreshed the
  scalar to the database value.
- Locked-current-state design: Phase A now returns only scalar lock and identity keys for the
  expired candidate. Phase B preserves the existing `User -> Project -> UserCounter ->
  ProjectCounter -> Invocation -> Attempt -> Reservation` lock order. Every mutable counter,
  Invocation, Attempt, and Reservation locking select explicitly uses `populate_existing=True`.
  Final expiry, relationship, state, status, dispatch-evidence, counter, and recovery decisions
  use only those lock-acquired instances. Usage, cost, and event existence queries remain after
  the locked parent rows; no new Session, global expunge, schema, Migration, or repository-helper
  change was required.
- Release-first race: a dedicated PostgreSQL transaction acquires the same ordered target locks,
  legally releases the Reservation, decrements both reserved counters once, terminalizes the
  Attempt and Invocation as `dispatch_not_started`, and holds the transaction open. Recovery runs
  in an independent Session and thread. A `threading.Event`, `Future`, distinct backend PIDs, and
  a third observer connection require `pg_stat_activity` plus `pg_blocking_pids()` to prove that
  recovery completed candidate discovery and is actually waiting on the holder's
  `user_accounts ... FOR UPDATE` query before the holder may commit. After handoff, recovery
  returns `0`, preserves the committed `released` state, does not add reconciliation, does not
  change either counter again, does not call the Adapter, and a second serial recovery remains
  idempotent.
- Dispatch-evidence-first race: the same deterministic lock-wait harness commits only a new
  `BudgetReservation.dispatch_committed_at` fact while the candidate discovery snapshot still
  lacks it. After lock handoff, recovery observes the committed evidence, selects the existing
  fail-closed `reconciliation_required` / `outcome_unknown` path, preserves both reserved
  counters, creates no usage or cost settlement, makes no Adapter call, and remains idempotent on
  the second serial recovery. This shape would take the clean-orphan release branch if the
  pre-lock Reservation scalar were still controlling the decision.
- Focused validation: the first direct pytest invocation exited `1` before any test body ran
  because the caller shell exposed only part of the PostgreSQL component set; it produced three
  setup errors and is not treated as product evidence. Reinvocation through the repository's
  isolated integration database environment selected
  `test_phase3a_recovery_refreshes_locked_current_state_after_lock_wait` and
  `test_phase3a_orphan_recovery_requires_proof_dispatch_never_started`; numeric exit `0`,
  `3 passed`, `0 failed`, `0 deselected`, and no warnings. The existing control continues to prove
  that `dispatched_at` alone is dispatch evidence, a truly undispatched orphan releases safely,
  only that release decrements counters, the second recovery is idempotent, and Adapter call count
  stays zero.
- Changed-Python gates: final Ruff check and Ruff format check both exited `0`; mypy passed all 79
  configured production source files; `git diff --check` passed. The pinned, redacted,
  network-disabled secret scan of the current repository tree scanned about 3.89 MB, found no
  leaks, and exited `0`; an exact remediation-manifest scan is performed again at Candidate
  freeze.
- Database readiness: `make ensure-db ENV_FILE=.env.example` exited `0` and confirmed
  `127.0.0.1:55432/creativedeploy`; the existing service was already available, so no `db-up`,
  reset, volume deletion, or configuration change was performed.
- Canonical: `make check ENV_FILE=.env.example` was invoked exactly once after the final focused
  and changed-file gates and exited `0`. Ruff and formatting passed for 116 files; mypy passed 79
  source files; 434 API unit tests passed; Alembic reported the sole head `3a04fab2e7a5`; 65 real
  PostgreSQL integration tests passed; Web lint and typecheck passed; 15 Vitest files / 163 tests
  passed; and the Vite build transformed 131 modules. The run reported the existing external
  Starlette/httpx deprecation warning and the existing Pydantic field-metadata warning; neither
  arose from this remediation.
- BM-08 evidence is reused as independently `PASS / CLOSED`; Migration D is byte-for-byte
  unchanged. Supply-chain run `phase3a_supply_20260808b` and visual verdict
  `PHASE_3A_VISUAL_ACCEPTANCE_PASS` remain applicable. No frontend, dependency declaration,
  lockfile, security/supply-chain configuration, Migration, ORM schema, architecture, real
  Provider, external call, paid cost, push, pull request, merge, or independent review occurred.
  This executor does not claim the required new BM-06 independent final re-review has passed.
