# Phase 1E-1 — ImageAsset Foundation Implementation Plan

- Phase Status: `CLOSED`
- Phase 1D Status: `COMPLETE`
- Date: `2026-07-29`
- Baseline HEAD: `881a2735aeb47ae8edbbd4810eb19f52e46232ff`
- Implementation Seal Commit: `9b3b23ac3e1f056a73e3934d3da51b24aa7f671d`
- Commit Status: `SEALED`
- Git Staging Status: `NOT_STAGED`
- Independent Review Verdict: `PHASE_1E_1_PASS_READY_FOR_SEALING`
- Migration Revision: `5ed9906e7d33`
- Overall Project Checkpoint: `approximately_60_percent`
- AI Integration: `NOT_AUTHORIZED`
- External Object Storage: `NOT_SELECTED`
- Public / Signed URLs: `NOT_AUTHORIZED`
- Deletion: `NOT_IMPLEMENTED`
- Real Authentication: `NOT_IMPLEMENTED`
- Local Storage: development/test only
- Production Storage: `NOT_READY`
- Next Phase: `NEXT_PHASE_REQUIRES_60_PERCENT_CHECKPOINT_CONFIRMATION`
- Candidate Evidence:
  `docs/progress/phase-1e-1-imageasset-foundation-candidate.md`
- Closure Record:
  `docs/progress/phase-1e-1-imageasset-foundation-closure.md`

## Goal

Add the smallest real vertical slice that lets the configured human operator upload,
persist, privately preview, list, and formally replace one immutable
`primary_mvp_input` image with rights attestation and restart persistence.

## Requirement resolution matrix

| Requirement | Source | Existing decision | Missing detail | Implemented interpretation |
| --- | --- | --- | --- | --- |
| One MVP main image | Product Contract FR-002 | One immutable original; no fusion | Physical current/version representation | One `primary_mvp_input` slot, version rows, retained history |
| Upload states | Workflow state machine | First from DRAFT; replace from review/failure | Atomic current pointer update | Project lock, asset/event/current update, `IMAGE_UPLOADED` in one transaction |
| Immutable replacement | Data Dictionary | New entity, never overwrite | Same-project lineage constraints | Composite lineage FK plus one-current partial unique index |
| Owner isolation | Product Contract / ADR-0003 | Stable Principal and project-private | File authorization path | Owner predicate on project and asset; private content route; same safe 404 |
| Rights statement | Data Dictionary | User attestation, not legal verification | Version binding and command fields | Source, intended uses, confirmation/version, actor and timestamp stored per immutable row |
| File validation | Product Contract | JPEG/PNG/WebP, 20 MiB, 768–8192 | Pixel ceiling and deterministic evidence | 40 MP ceiling; signature/MIME/decoder/full-load/static-image checks |
| Quality boundary | FR-003 | Separate ImageQualityAssessment | Avoid false quality pass | Store only `upload_validation_*`; UI explicitly says no quality decision |
| Idempotency | Product Contract | `upload_image` is Project-scoped | File bytes and Project in command identity | Existing record; server scope includes Principal and Project; hash includes SHA-256 plus normalized declaration |
| Physical storage | Not previously selected | Private and provider-neutral | Local adapter and recovery | Port plus non-production local adapter; atomic no-replace publish, creation receipt, guarded compensation, orphan scan |
| Production behavior | Scope boundary | No provider selected | Fail-open risk | Explicit production startup rejection |
| UX | Existing Phase 1D detail page | Same-origin API and safe states | Upload/history/retry interactions | Accessible primary-slot manager with progress, retry key reuse, replacement wording |
| Deletion | Product Contract / task scope | Original retained | None | No delete API, service command, or control |

## Authorized implementation

1. Freeze ADR-0004 and the physical Data Dictionary supplement.
2. Add the `image_assets` ORM model and reviewed Alembic candidate
   `5ed9906e7d33`.
3. Add the current-image PaintProject reference with same-project/same-owner FK.
4. Add provider-neutral storage and the non-production local filesystem adapter.
5. Add deterministic file acceptance, request/stream limits, hashing, and safe display
   filename handling.
6. Add owner-scoped upload/list/detail/private-content routes.
7. Reuse command idempotency, state events, transaction timeouts, and safe error envelopes.
8. Add the primary-slot upload, preview, immutable history, and controlled replacement UI.
9. Add unit, real PostgreSQL/API, frontend, build, migration, restart, collision, receipt,
   compensation, concurrency, and browser evidence.
10. Produce a candidate manifest without staging, committing, pushing, tagging, or deleting.

## Explicit exclusions

- ImageQualityAssessment and any `pass/review/fail` policy;
- AI, model provider, AgentRun, RAG, segmentation, region or Polygon work;
- normalized analysis copies or multiple/fused main images;
- cloud object storage, public URLs, production deployment, or real authentication;
- update/delete, garbage collection, lifecycle expiration, or irreversible cleanup;
- CI, Redis, workers, inventory matching, HumanApproval, or plan generation.

## Acceptance gates

- Requirements and physical schema are internally consistent and all constraints have stable
  names.
- Historical Revision `a10d3d8dab38` remains byte-for-byte unchanged.
- New Revision performs real upgrade/downgrade/re-upgrade on isolated PostgreSQL and
  `alembic check` reports no diff.
- Valid JPEG/PNG/WebP succeed; corrupt, mismatched, unsupported, animated, over-byte,
  over-dimension, and over-pixel inputs fail closed.
- Same-key replay and conflict, Project-scoped independence, concurrent same-key arbitration,
  owner isolation, private content headers, restart persistence, replacement retention,
  no-overwrite collision, receipt-bound database compensation, referenced-object protection,
  storage failure, and zero residuals are proven.
- Frontend unit tests prove exact response validation, explicit attestation, progress,
  duplicate suppression, retry-key reuse, replacement state gating, private preview, retained
  history, and no destructive control.
- Real browser proves the local user journey at 1440×900, 768×1024, and 390×844 with real API,
  PostgreSQL, private files, confirmation-loss retry, replacement lineage, service restarts,
  other-owner 404, and exact cleanup.
- `make check` or the equivalent exact component commands pass from a cleanly understood
  environment.
- Final scope/manifest evidence includes tracked diff, untracked files, sizes, SHA-256,
  patch hash, porcelain hash, and confirmation that nothing is staged or committed.

## Candidate status semantics

The original private-photo browser attempt remains `INVALID_ATTEMPT` and was precisely cleaned.
A later complete real-browser rerun used only program-generated JPEG, PNG, WebP, and invalid
fixtures; upload, safe idempotent retry, immutable replacements, private preview, rejection,
restart persistence, three responsive viewports, and exact cleanup all passed. The formal result
was `PHASE_1E_1_IMPLEMENTED_READY_FOR_INDEPENDENT_REVIEW`.

Independent security review then found F-01: a forced storage-key collision through the former
`os.replace` publication changed an existing object's SHA-256. That review result was
`PHASE_1E_1_FAIL_REMEDIATION_REQUIRED`. F-02 asked for Principal-global behavior, but that
expectation conflicts with the Product Contract's Project-inclusive command scope. The formal
resolution is
`REVIEW_EXPECTATION_CONFLICT_RESOLVED_BY_FORMAL_PROJECT_SCOPED_CONTRACT`; the implementation and
contract remain Project-scoped.

## Formal Project-scoped upload idempotency

- Same Principal, same Project, same key, same normalized payload: replay the same ImageAsset.
- Same Principal, same Project, same key, changed normalized payload: safe 409 conflict.
- Same Principal, different Project, same key: two independent commands, each eligible for 201,
  with separate assets, events, and idempotency records and no cross-Project replay metadata.
- Different Principal, same key: independent owner scopes with no result reuse or observation.
- The key is a retry identity inside the server-owned business-command scope; it is not a
  Principal-global token.

## Security Remediation Round 1

- Publish uses an atomic same-filesystem hard-link create. An existing destination produces a
  typed collision and cannot be replaced; unsupported no-replace behavior fails closed.
- Only a successful publish returns a receipt containing the key, size, SHA-256, filesystem
  device, inode, and link-count evidence for the object created by that call.
- Compensation requires that receipt, verifies the controlled path, regular-file identity,
  size/SHA-256, single-link state, and current absence from every database storage-key reference,
  then rechecks identity immediately before unlink.
- Collision returns no receipt and never authorizes formal-object cleanup. Compensation refusal
  or failure is logged as detectable orphan state rather than deleting an unproven object.
- Direct collision, concurrent same-key publish, changed-receipt identity, referenced-object,
  storage-collision application mapping, database-failure replacement, and compensation-failure
  probes are mandatory regressions.

After the remediation, focused suites, the complete canonical gate, migration lifecycle, and a
new complete synthetic browser journey passed and all probe state was precisely cleaned. At that
historical point the formal result was
`PHASE_1E_1_REMEDIATION_IMPLEMENTED_READY_FOR_INDEPENDENT_REVIEW`; it did not yet mean approved,
commit-ready, production-ready, sealed, closed, or authorized for a later AI/image-quality phase.
A second independent review later returned `PHASE_1E_1_PASS_READY_FOR_SEALING`, and the exact
53-file implementation was sealed by `9b3b23ac3e1f056a73e3934d3da51b24aa7f671d`.
Phase 1E-1 is now `CLOSED` at the approximately 60% project checkpoint. No later formal phase was
defined, so the next state is `NEXT_PHASE_REQUIRES_60_PERCENT_CHECKPOINT_CONFIRMATION`.
