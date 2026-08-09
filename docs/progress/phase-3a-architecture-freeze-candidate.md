# Phase 3A Final Contract-Gaps Remediation Candidate

## Verdict

`PHASE_3A_FINAL_CONTRACT_GAPS_REMEDIATION_READY_FOR_DELTA_REVIEW`

This is the final narrow local documentation-only remediation Candidate. It closes only the latest independently rereviewed Blocking Medium gaps BM-01 and BM-06 by contract, while preserving every previously closed finding and the F-3A-01 through F-3A-06 security contracts. It is not an independent review PASS, implementation authorization, Provider integration, real-key test, Migration, production-readiness statement, push, or pull request. Implementation remains prohibited until one fresh independent delta-only rereview passes.

## Repository and Candidate identity

| Item | Verified value |
| --- | --- |
| Repository root | `/Users/danke/Developer/CreativeDeploy` |
| Repository | `dankk0220abc-prog/creative-deploy` |
| Branch | `design/phase-3a-byok-provider-foundation-20260804` |
| Second remediation base HEAD | `504eaf8d7ba26e1e1f3bfa7bc863c6016ceb15c0` |
| Second remediation base tree | `90d70d970329f197201e57de2b3783e3b3010c66` |
| Base parent | `d18a6869dec41e6d882792e1236a28ac82f4bd58` |
| `main` / `origin/main` | `09a6dad97e67f3ebab3a3c331049eab2bb33b835` |
| Base subject | `docs(ai): close phase 3a security contracts` |
| Preflight worktree/index/untracked | clean |
| Preflight operation state | no merge, rebase, cherry-pick, revert, bisect, or sequencer state |
| Exact Candidate paths | `docs/architecture/phase-3a-byok-multi-provider-foundation.md`; `docs/progress/phase-3a-architecture-freeze-candidate.md` |

The preflight matched every governed identity and used no reset, clean, stash, rebase, amend, overwrite, or third-path operation. The new remediation commit SHA/tree are recorded after commit in the task handoff because a committed document cannot embed its own final object identity.

## Remediation scope

This final narrow remediation changes only BM-01 and BM-06: budget-policy participation in the unified lock order and Admission, and Project Model Policy capability-allowlist associations and their explicit `RESTRICT` foreign-key/migration contracts.

Previously passed Envelope Encryption, Provider/Model/Capability design, selection and fallback foundation, base API contract, frontend information architecture, First Slice Fake/Fixture-only boundary, and the future SSRF safe-transport Gate are reused without redesign or status inflation.

## Original focused finding closure matrix

The original F-3A-01 through F-3A-06 matrix is preserved:

| Finding | Status | Normative architecture section |
| --- | --- | --- |
| F-3A-01 — Envelope encryption | **CLOSED BY CONTRACT** | Sections 4.2–4.3 and 8, “Grant, replacement, and ciphertext constraints” |
| F-3A-02 — Admission, revoke, replace, decrypt, and handoff linearization | **CLOSED BY CONTRACT** | Section 7, “Credential and access control”; section 4.5 |
| F-3A-03 — Cumulative budget, reservation, retry, and cost reduction | **CLOSED BY CONTRACT** | Section 4.6; section 7, “Budget and cost control” |
| F-3A-04 — Invocation idempotency exact scope | **CLOSED BY CONTRACT** | Section 4.5 |
| F-3A-05 — Invocation/Attempt state machines and races | **CLOSED BY CONTRACT** | Section 4.5 |
| F-3A-06 — FK deletion, active grant, replacement lineage, and ciphertext retention | **CLOSED BY CONTRACT** | Section 8 |

The frozen AEAD/envelope, request-local secret, admission-before-handoff, cumulative budget, exact invocation scope, terminal-state, append-only ledger, replacement-lineage, and `RESTRICT` contracts remain intact. This rereview does not convert those contract closures into implementation evidence.

## Latest Rereview Closure Matrix

| Finding | Status | Normative architecture section |
| --- | --- | --- |
| BM-01 — Budget Policy lock ordering and Admission linearization | **CLOSED BY CONTRACT** | Section 7, “global resource order” and “Budget and cost control”; section 12, “Test and evidence strategy”; section 8, “Cross-contract consistency matrix” |
| BM-02 — First Slice currency and aggregation | **CLOSED BY CONTRACT** | Section 4.6, “First Slice currency” |
| BM-03 — Orphan BudgetReservation recovery | **CLOSED BY CONTRACT** | Sections 4.5–4.6, “Dispatch and crash recovery” |
| BM-04 — Artifact/domain canonicalization/family/sentinel | **CLOSED BY CONTRACT** | Section 4.5, “Domain canonicalization and artifacts” and “Idempotency and project scope”; Migration C in section 8 |
| BM-05 — One active Attempt and aggregate coupling | **CLOSED BY CONTRACT** | Section 4.5, “Attempt and aggregate state contract” |
| BM-06 — Project Capability allowlist FK | **CLOSED BY CONTRACT** | Sections 4.4 and 8, “Retention and deletion boundary” and “Four additive migrations”; section 12, “Test and evidence strategy” |
| BM-07 — Migration dependencies, rollout, and downgrade gates | **CLOSED BY CONTRACT** | Section 8, “Four additive migrations” |

## BM-01 Budget Policy lock closure

The unified global order now explicitly places `UserProviderPreference`, `ProjectModelPolicy`, `UserBudgetPolicy`, and `ProjectBudgetPolicy` before `UserBudgetCounter` and `ProjectBudgetCounter`. Admission locks and validates the current effective User then Project BudgetPolicy, resolves their current window/limit/revision and `FIXTURE_CREDITS` currency, then locks counters in user-before-project order before atomically creating the Reservation. Admission, Grant create/revoke, Credential revoke/replace, user deactivation, project archival, membership/access mutation, and both BudgetPolicy mutations use that order; no transaction may lock a Counter before its corresponding Policy. A display/candidate cache cannot admit: disabled/replaced/revised/window-changed/non-`FIXTURE_CREDITS` policy must be recalculated or fail. Policy-first mutation governs later Admission; Admission-first commit preserves only its committed Reservation, while retry/fallback re-admits under the new Policy. Tightening/disabling does not revoke an admitted Attempt but blocks a newly noncompliant retry/fallback. The pre-existing no-policy behavior remains the existing contract, not an implementation-selectable hidden default.

## BM-02 currency closure

First Slice uses only the non-real unit `FIXTURE_CREDITS` across fixture Provider/model pricing, budgets, reservations, usage, cost, Attempt, and Invocation aggregation. Amounts are integer minor units; conversion, a second currency, and cross-currency fallback are prohibited. Currency mismatch is a structured Invocation failure rather than a sum. UI/audit must identify fixture credits as simulated use, not real expense.

## BM-03 reservation recovery closure

`BudgetReservation` now has the exact `reserved`, `dispatch_committed`, `settled`, `released`, and `reconciliation_required` states plus admission expiry and dispatch/settlement/release timestamps. Admission creates a 120-second `reserved` lease. A separate committed dispatch transaction precedes every Adapter call. Only an expired, provably never-dispatched reservation can be auto-released; dispatched uncertainty retains funds and requires verifiable or governed reconciliation. The Fake Provider follows the same state path and deterministically settles.

## BM-04 canonicalization closure

`phase3a-v1` freezes NFC strings, UTC RFC3339 microsecond timestamps, integer/fixed-scale numeric rules, finite-value checks, and versioned schema-before-JCS processing. Artifact identity requires immutable ID/version, SHA-256, media type, and byte length; First Slice rejects raw binary/multipart invocation. `invocation_family` is a three-value server enum. Migration C preflights and permanently forbids a zero-UUID `PaintProject.id`, while exact database checks bind the sentinel only to projectless requests.

## BM-05 Attempt state closure

Idempotency creates only a pending Invocation. Admission atomically creates one admitted Attempt and reserved Reservation, dispatch atomically moves Invocation/Attempt/Reservation together, and terminal reduction updates Attempt, Reservation, Invocation, event, usage, and cost facts in one transaction. A partial unique index prevents multiple active Attempts. Retry waits for definitive failure and re-admits under the original Invocation; `outcome_unknown`, cancellation, and First Slice fallback closure prevent races. `final_attempt_id` is same-Invocation, write-once, and success-only.

## BM-06 Project Capability allowlist FK closure

`ProjectModelPolicyCapability` is an explicit association with `project_model_policy_id`, `capability_definition_id`, `created_at`, and `UNIQUE (project_model_policy_id, capability_definition_id)`. Both its FK to `ProjectModelPolicy` and its FK to `CapabilityDefinition` are individually frozen as `ON DELETE RESTRICT`. The FK matrix also individually names the Provider and Model associations and both sides of the optional Credential association; the latter references `CredentialRecord`, not a Registry object. Capability allowlisting only limits capability choice: it cannot grant Credential use, replace requesting-user ownership, or replace the active exact `CredentialGrant` required for a project-scoped call. Revoked/replaced Credentials cannot pass Policy admission. `CapabilityDefinition` is retire-only in First Slice, blocks new policy/invocation selection when retired, remains queryable for historical references, and cannot change historical Attempt/Audit meaning.

## BM-07 Migration closure

The chain is exactly A(`2b1c4d5e6f70`) → B → C → D. Migration C now explicitly creates `ProjectModelPolicy`, `ProjectModelPolicyProvider`, `ProjectModelPolicyModel`, `ProjectModelPolicyCapability`, and retained `ProjectModelPolicyCredential`, each with unique constraints, lookup indexes, and explicit `RESTRICT` FKs. Its in-migration downgrade SQL must fail closed before destructive DDL unless every listed policy/association, preference, budget policy/counter/reservation, Invocation/Attempt, Usage/Cost/Audit/Event table is empty; a capability association is therefore a direct downgrade blocker. Migration A cannot delete `CapabilityDefinition` while a later Policy association exists. Migration D inserts only exact Fake/Fixture registry facts. Rollout runs A–D with the feature flag off, then compatible code and focused smoke, and permits fixture enablement only in development/test while staging/production remain off.

## Cross-contract consistency

The architecture now explicitly cross-checks budget policy/counter lock order, User-before-Project Policy and Counter order, database-lock/revision Admission linearization, capability allowlist `RESTRICT` FKs, Credential Grant non-substitution, Registry retirement history, and Migration C association/downgrade coverage. No implementation-choice placeholder remains for BM-01 or BM-06.

## First Slice status and unchanged boundary

- This remains a document contract only.
- No production or test code was created or modified.
- No Migration was created or executed.
- Encryption was not implemented.
- A budget service, recovery scheduler, or background worker was not implemented.
- No Provider Adapter was implemented or connected.
- No real key was entered, saved, displayed, or tested.
- No real Provider was called and no fee was incurred.
- No independent PASS has been granted; implementation MUST NOT start.

## Evidence intentionally not repeated

This remediation did not reread the full repository, VisualEngineer, any sibling repository, Phase 2E evidence, browser flows, Docker, product tests, migrations, staging, backup/restore, supply-chain checks, or CI. It read only repository-required architecture baselines and the exact Phase 3A Candidate documents, then reused all previously passed Provider, Capability, selection, fallback, API, frontend, and First Slice evidence without upgrading their status.

## Documentation validation boundary

Validation is limited to the exact two-path set, Markdown hygiene, local links, `git diff --check`, a diff-scoped high-confidence Secret scan, BM-01/BM-06 closure-matrix completeness, lock-order and capability-association/FK/Migration-C term checks, and final Git state. The task handoff records the executed results and the narrow remediation commit identity.

## Exact next action

Run one final independent read-only delta review limited exclusively to BM-01, BM-06 and the remediation delta from `ff6363af4ac44d78116542fff29e3564fbd82769` to the new Candidate HEAD. Reuse every other Phase 3A architecture finding closure. Do not reread the full repository or run product test suites.
