# Phase 3A Architecture Remediation Candidate

## Verdict

`PHASE_3A_BYOK_PROVIDER_ARCHITECTURE_REMEDIATION_READY_FOR_FOCUSED_REREVIEW`

This is a local documentation-only remediation Candidate. It closes six focused security findings by contract; it is not an independent review PASS, implementation authorization, Provider integration, real-key test, migration, production-readiness statement, push, or pull request. Implementation remains prohibited until one fresh independent Sol focused rereview passes.

## Repository and Candidate identity

| Item | Verified value |
| --- | --- |
| Repository root | `/Users/danke/Developer/CreativeDeploy` |
| Repository | `dankk0220abc-prog/creative-deploy` |
| Branch | `design/phase-3a-byok-provider-foundation-20260804` |
| Remediation base HEAD | `d18a6869dec41e6d882792e1236a28ac82f4bd58` |
| Remediation base tree | `b6e89725ca5c50fe422e684044746872a40e2a51` |
| Base parent / `main` / `origin/main` | `09a6dad97e67f3ebab3a3c331049eab2bb33b835` |
| Base subject | `docs(ai): freeze phase 3a provider foundation` |
| Preflight worktree/index/untracked | clean |
| Preflight operation state | no merge, rebase, cherry-pick, revert, bisect, or sequencer state |
| Exact Candidate paths | `docs/architecture/phase-3a-byok-multi-provider-foundation.md`; `docs/progress/phase-3a-architecture-freeze-candidate.md` |

The preflight matched every governed identity and used no reset, clean, stash, rebase, amend, or overwrite operation. The remediation commit SHA/tree are intentionally recorded after commit in the task handoff because a committed document cannot embed its own final object identity.

## Remediation scope

Only the following six focused findings and two non-blocking implementation clarifications changed. Previously passed Provider Registry, Model/Capability model, selection inheritance, fallback default-off, First Slice non-network SSRF boundary, base API contract, frontend information architecture, and First Slice non-goals remain reused without replanning.

## Finding closure matrix

| Finding | Status | Normative architecture section |
| --- | --- | --- |
| F-3A-01 — Envelope encryption | **CLOSED BY CONTRACT** | Sections 4.2–4.3 and 8, “Grant, replacement, and ciphertext constraints” |
| F-3A-02 — Admission, revoke, replace, decrypt, and handoff linearization | **CLOSED BY CONTRACT** | Section 7, “Credential and access control”; section 4.5 |
| F-3A-03 — Cumulative budget, reservation, retry, and cost reduction | **CLOSED BY CONTRACT** | Section 4.6; section 7, “Budget and cost control” |
| F-3A-04 — Invocation idempotency exact scope | **CLOSED BY CONTRACT** | Section 4.5 |
| F-3A-05 — Invocation/Attempt state machines and races | **CLOSED BY CONTRACT** | Section 4.5 |
| F-3A-06 — FK deletion, active grant, replacement lineage, and ciphertext retention | **CLOSED BY CONTRACT** | Section 8 |

### F-3A-01 closure

Each saved credential now has a CSPRNG-generated 256-bit DEK, AES-256-GCM data encryption, independent 96-bit nonces, verified logical tags, canonical versioned AAD, authenticated DEK wrapping through a replaceable key service, a development/test-only file-secret fixture key, and an atomic no-partial-row save contract. Plaintext and DEKs are request-local and excluded from ordinary domain serialization, errors, logs, fixtures, CI, Git, and browser data.

### F-3A-02 closure

Credential, grant, policy, invocation, and budget checks now converge in one admission transaction. Its commit is the authorization linearization point, and Adapter handoff occurs only afterward. Lock ordering fixes revoke/replace races; each retry re-admits; revoke and replace atomically erase the old envelope, revoke grants, and append audit facts.

### F-3A-03 closure

Per-invocation, user-window, and project-window budgets must all pass under fixed-order row locks and revision checks before an attempt exists. Unknown pricing is denied by default and never treated as zero. Retry categories, attempt/time bounds, post-dispatch `outcome_unknown`, reservation settlement, duplicate/late receipt identities, and append-only retry/fallback cost aggregation are fixed.

### F-3A-04 closure

Invocation uniqueness is exactly `(requesting_user_id, product_space, project_scope_id, invocation_family, idempotency_key)`, with a non-null all-zero UUID sentinel for no-project scope and a canonical payload hash. Replay semantics and payload conflict behavior are deterministic; retry/fallback create attempts under the original invocation.

### F-3A-05 closure

Invocation and Attempt states, legal transitions, terminal immutability, revision/row-lock updates, cancel-versus-completion winner, late-result handling, append-only ledgers, and deterministic final invocation reduction are now explicit.

### F-3A-06 closure

First Slice forbids physical deletion of core identity/project/credential/invocation/audit objects. FKs use `ON DELETE RESTRICT`; user deactivation and project archival retain history; active grants have a partial unique index; replacement lineage has self-FK/uniqueness/owner+Provider enforcement; revoked/replaced rows retain audit metadata but no decryptable envelope fields.

## Migration plan

The architecture requires four additive revisions after `2b1c4d5e6f70`: A for registries, B for credential security, C for policies/budget/invocation/ledgers, and D for default-off Fake Provider fixture enablement. Each needs independent upgrade/downgrade validation; downgrade fails closed when protected data exists. No legacy PaintPilot table semantics or business-object names change.

## Non-blocking implementation clarifications

A temporary key may be reused only by same-Provider retries within one synchronous request, while every retry repeats authorization and budget admission. It cannot cross a queue, background job, process, or later request; request-body capture is disabled and instrumentation records only field names/redacted presence.

Before any real Provider network enablement, one shared safe transport must cover URL/IDNA/IP canonicalization, CNAME/DNS and connected-peer validation, redirect revalidation, proxy bypass prevention, port policy, timeouts, body limits, and pool limits for validation, catalog, and invocation. First Slice still rejects custom Provider URLs and real egress.

## First Slice status and unchanged boundary

- First Slice remains Fake/Fixture-only.
- No code or Migration was created or modified.
- No real key was entered, saved, or displayed.
- No real Provider was connected or called.
- No cost was incurred.
- No independent PASS has been granted; implementation MUST NOT start.

## Evidence intentionally not repeated

This remediation did not reread the full repository, VisualEngineer, sibling repositories, Phase 2E evidence, browser flows, Docker, product tests, migrations, staging, backup/restore, supply-chain checks, or CI. It reused all previously passed Provider, Capability, selection, fallback, API, frontend, and First Slice evidence without upgrading their status.

## Documentation validation boundary

Validation is limited to the exact two-path set, Markdown hygiene, local links, `git diff --check`, a diff-scoped high-confidence Secret scan, closure-matrix completeness, and final Git state. The task handoff records the executed results and the narrow remediation commit identity.

## Exact next action

Run one fresh independent Sol read-only focused rereview limited to F-3A-01 through F-3A-06 and the remediation delta from `d18a6869dec41e6d882792e1236a28ac82f4bd58` to the new Candidate HEAD. Reuse all previously passed Provider, Capability, fallback, API and frontend evidence. Do not reread the full repository or run product test suites.
