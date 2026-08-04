# Phase 3A Architecture Remediation Candidate

## Verdict

`PHASE_3A_EXECUTION_SEMANTICS_REMEDIATION_READY_FOR_FINAL_REREVIEW`

This is the second local documentation-only remediation Candidate. It closes the latest seven Blocking Medium findings by contract while preserving the previously closed F-3A-01 through F-3A-06 security contracts. It is not an independent review PASS, implementation authorization, Provider integration, real-key test, Migration, production-readiness statement, push, or pull request. Implementation remains prohibited until one fresh independent Sol focused rereview passes.

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

This second remediation changes only BM-01 through BM-07: project Grant/admission linearization; First Slice currency; orphan reservation recovery; domain canonicalization/artifact/family/sentinel identity; one-active-Attempt state coupling; Credential/Registry lifecycle; and Migration dependency/deployment/downgrade gates.

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
| BM-01 — Grant/admission and lifecycle linearization | **CLOSED BY CONTRACT** | Sections 4.2 and 7; section 8, “Cross-contract consistency matrix” |
| BM-02 — First Slice currency and aggregation | **CLOSED BY CONTRACT** | Section 4.6, “First Slice currency” |
| BM-03 — Orphan BudgetReservation recovery | **CLOSED BY CONTRACT** | Sections 4.5–4.6, “Dispatch and crash recovery” |
| BM-04 — Artifact/domain canonicalization/family/sentinel | **CLOSED BY CONTRACT** | Section 4.5, “Domain canonicalization and artifacts” and “Idempotency and project scope”; Migration C in section 8 |
| BM-05 — One active Attempt and aggregate coupling | **CLOSED BY CONTRACT** | Section 4.5, “Attempt and aggregate state contract” |
| BM-06 — Credential lifecycle and Registry FKs | **CLOSED BY CONTRACT** | Sections 4.2 and 8, “Retention and deletion boundary” and “Grant, replacement, and ciphertext constraints” |
| BM-07 — Migration dependencies, rollout, and downgrade gates | **CLOSED BY CONTRACT** | Section 8, “Four additive migrations” |

## BM-01 Grant and linearization closure

Every project-scoped invocation now requires requesting-user ownership **and** one active Grant for the exact Credential/project pair; project owner or membership cannot replace the Grant, and no one may use another user's Credential merely through project access. Projectless use requires ownership but no Grant. Admission, Grant, Revoke, Replace, user deactivation, project archival, and membership/access mutation share one global resource order. Admission commit is the authorization linearization point, with exact winner semantics for deactivation, archival, membership removal, revoke, and replace.

## BM-02 currency closure

First Slice uses only the non-real unit `FIXTURE_CREDITS` across fixture Provider/model pricing, budgets, reservations, usage, cost, Attempt, and Invocation aggregation. Amounts are integer minor units; conversion, a second currency, and cross-currency fallback are prohibited. Currency mismatch is a structured Invocation failure rather than a sum. UI/audit must identify fixture credits as simulated use, not real expense.

## BM-03 reservation recovery closure

`BudgetReservation` now has the exact `reserved`, `dispatch_committed`, `settled`, `released`, and `reconciliation_required` states plus admission expiry and dispatch/settlement/release timestamps. Admission creates a 120-second `reserved` lease. A separate committed dispatch transaction precedes every Adapter call. Only an expired, provably never-dispatched reservation can be auto-released; dispatched uncertainty retains funds and requires verifiable or governed reconciliation. The Fake Provider follows the same state path and deterministically settles.

## BM-04 canonicalization closure

`phase3a-v1` freezes NFC strings, UTC RFC3339 microsecond timestamps, integer/fixed-scale numeric rules, finite-value checks, and versioned schema-before-JCS processing. Artifact identity requires immutable ID/version, SHA-256, media type, and byte length; First Slice rejects raw binary/multipart invocation. `invocation_family` is a three-value server enum. Migration C preflights and permanently forbids a zero-UUID `PaintProject.id`, while exact database checks bind the sentinel only to projectless requests.

## BM-05 Attempt state closure

Idempotency creates only a pending Invocation. Admission atomically creates one admitted Attempt and reserved Reservation, dispatch atomically moves Invocation/Attempt/Reservation together, and terminal reduction updates Attempt, Reservation, Invocation, event, usage, and cost facts in one transaction. A partial unique index prevents multiple active Attempts. Retry waits for definitive failure and re-admits under the original Invocation; `outcome_unknown`, cancellation, and First Slice fallback closure prevent races. `final_attempt_id` is same-Invocation, write-once, and success-only.

## BM-06 Credential and Registry closure

Credential status is exactly `active`, `revoked`, or `replaced`; revoked/replaced both require cryptographic erase and mutually exclusive lifecycle timestamps. Replacement is one-owner, one-Provider, non-self-referential, one-successor lineage from an active old Credential, and Grants do not transfer. Provider/Model/Capability registries are disabled/retired rather than physically deleted, every required registry FK is `ON DELETE RESTRICT`, and Attempts retain immutable Provider/model/adapter/capability snapshots.

## BM-07 Migration closure

The chain is exactly A(`2b1c4d5e6f70`) → B → C → D. Each Migration has a table-specific SQL downgrade gate inside the Migration; protected data causes a non-zero fail-closed result before destructive DDL and leaves schema unchanged. Migration D inserts only exact Fake/Fixture registry facts. Rollout runs A–D with the feature flag off, then compatible code and focused smoke, and permits fixture enablement only in development/test while staging/production remain off.

## Cross-contract consistency

The architecture now contains an explicit consistency matrix covering project Grant ownership, lifecycle lock ordering, idempotency replay, original-Invocation retry, one active Attempt, `outcome_unknown`, dispatched reservation retention, same-currency aggregation, cryptographic erase, Registry retirement, linear Migration dependency, and the Fake/Fixture-only First Slice boundary. No implementation-choice placeholder remains for BM-01 through BM-07.

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

Validation is limited to the exact two-path set, Markdown hygiene, local links, `git diff --check`, a diff-scoped high-confidence Secret scan, original six plus latest seven closure-matrix completeness, conflict-term checks, and final Git state. The task handoff records the executed results and the narrow remediation commit identity.

## Exact next action

Run one fresh independent Sol read-only focused rereview limited to BM-01 through BM-07 and the remediation delta from `504eaf8d7ba26e1e1f3bfa7bc863c6016ceb15c0` to the new Candidate HEAD. Reuse F-3A-01 and all previously passed Provider, Capability, fallback, API and frontend evidence. Do not reread the full repository or run product test suites.
