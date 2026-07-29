# Phase 1E-2 — Multi-Role ImageSet and Readiness Implementation Plan

- Phase Status: `IMPLEMENTED_PENDING_INDEPENDENT_REVIEW`
- Date: `2026-07-29`
- Branch: `main`
- Baseline HEAD: `7b0777c393af705637a1e63f7f25f1dc06f75c1e`
- Baseline Subject: `docs(progress): close phase 1e-1 image assets`
- Baseline Commit Count: `17`
- Phase 1E-1 Status: `CLOSED`
- Checkpoint Direction: `USER_CONFIRMED_FOR_PHASE_1E_2`
- Commit / Stage / Push / Tag: `NONE`
- Migration Revision: `d4c8a1f7b2e9`
- Parent Revision: `5ed9906e7d33`
- Candidate Verdict:
  `PHASE_1E_2_WORKFLOW_GATE_REMEDIATION_IMPLEMENTED_READY_FOR_INDEPENDENT_REVIEW`
- Original Independent Review: `CONTRACT_OR_ARCHITECTURE_DECISION_REQUIRED`
- Fresh Remediation Review: `NOT_YET_PERFORMED`
- Production Readiness: `NOT_READY`

## Goal

Extend the sealed single private planning image into an owner-scoped four-role ImageSet with
independent immutable role histories, deterministic prerequisites, explicit append-only human
READY / NOT READY records, staleness after changes, and a complete Project Detail workbench.

## Requirement resolution

| Requirement | Implemented interpretation |
| --- | --- |
| Required references | `primary_front`, `reference_back`, `reference_angle` |
| Optional reference | `reference_detail` |
| Phase 1E-1 compatibility | In-place `primary_mvp_input -> primary_front` migration; identity and pointer preserved |
| Immutable history | New row per upload, same-role lineage, one current per role |
| Readiness | Deterministic blockers plus explicit human `ready/not_ready` append |
| Staleness | Latest saved fingerprint compared with current deterministic fingerprint |
| Distinctness | Required-role SHA-256 values must be distinct before READY |
| Missing object | Object-availability check blocks READY and can stale a saved review |
| Concurrency | Owned Project row lock serializes upload and review snapshots |
| Retry safety | Principal/Project-scoped idempotency includes verdict, reason, and fingerprint |
| Owner isolation | Owner predicate, composite FKs, and safe indistinguishable 404 |
| UI | Four role cards, previews/history, checklist, add/replace, review form/history |
| Primary workflow gate | First upload only in `DRAFT`; replacement only in `IMAGE_REVIEW_REQUIRED` or `IMAGE_VALIDATION_FAILED` |
| Reference workflow gate | First upload/replacement in `DRAFT`, `IMAGE_UPLOADED`, `IMAGE_REVIEW_REQUIRED`, or `IMAGE_VALIDATION_FAILED`; never a workflow transition |
| Validated freeze | Every image role is immutable through this API in `IMAGE_VALIDATED` and later/other states |

## Workflow-gate remediation

The original independent review found F-01 and recorded a real HTTP 201 for a
`primary_front` replacement in `IMAGE_UPLOADED`. Project control retained ADR-0004's sealed
workflow boundary. The remediation replaces the shared editable-state set with one centralized,
testable role/current/operation/state policy:

- `primary_front` without a current asset: `DRAFT` only;
- `primary_front` replacement: `IMAGE_REVIEW_REQUIRED` or `IMAGE_VALIDATION_FAILED` only;
- every reference first upload/replacement: `DRAFT`, `IMAGE_UPLOADED`,
  `IMAGE_REVIEW_REQUIRED`, or `IMAGE_VALIDATION_FAILED`;
- every role: rejected in `IMAGE_VALIDATED` and fail-closed in every unspecified state.

The Service rejects known-new unauthorized commands before staging and repeats the decision under
the final Project lock before object publication. The UI mirrors, but does not replace, backend
authorization. Legal reference mutations preserve workflow state; any legal role mutation that
changes the ImageSet fingerprint makes a prior matching readiness review stale. Rejected
mutations leave assets, bytes, current pointer, workflow events, command records, reviews, and
fingerprint unchanged.

## Authorized implementation

1. Add ADR-0005 and the Phase 1E-2 physical data dictionary.
2. Add the sole child Revision `d4c8a1f7b2e9` without editing either historical revision.
3. Expand ImageAsset role vocabulary while preserving Phase 1E-1 storage and immutable version
   semantics.
4. Add one append-only `ImageSetReadinessReview` model/table with database-enforced snapshot
   ownership and roles.
5. Add derived ImageSet, checklist, fingerprint, staleness, history, and readiness services.
6. Add owner-scoped ImageSet and readiness-review routes.
7. Preserve Project-scoped command replay/conflict and use the Project lock for race safety.
8. Replace the single-slot detail control with the four-role workbench.
9. Add unit, PostgreSQL/API, migration-compatibility, concurrency, frontend, build, restart,
   browser, responsive, and cleanup evidence.
10. Produce a SHA-256 candidate manifest without staging, committing, pushing, tagging, or
    changing repository history.

## Explicit exclusions

- ImageQualityAssessment, scores, automatic viewpoint classification, segmentation, regions,
  Polygon Editor, or multi-image fusion;
- AI, models, AgentRun, RAG, inventory, citations, or plan generation;
- external/public storage, signed/public URLs, deletion, retention, production deployment, real
  authentication, or permission expansion;
- new workflow states or automatic workflow transitions from readiness;
- modification of Phase 1E-1 historical evidence or sealed migrations.

## Acceptance gates

- Exact baseline and historical revision hashes are verified before implementation.
- Existing Phase 1E-1 rows upgrade in place and remain listable, readable, and current.
- One head and one new revision only; isolated upgrade/downgrade/re-upgrade and metadata check
  pass; unsafe downgrade preserves Phase 1E-2 facts.
- PostgreSQL proves role, owner, snapshot, verdict, reason, version, append-only, and current-row
  constraints.
- API proves required/optional roles, deterministic blockers, READY, NOT READY, stale/reconfirm,
  missing object, duplicate bytes, strict validation, restart, owner-safe 404, idempotency, and
  upload/review race outcomes.
- Independent expected-value tests prove the complete primary first/replacement matrix and the
  parameterized reference-role matrix; direct API denials prove safe 409 and zero governed
  database/private-file side effects.
- Frontend proves exact response validation, four roles, required/optional labels, private
  previews, retained histories, blockers, review/retry controls, stale state, no delete, and no AI
  or quality claim.
- A real synthetic browser journey covers desktop, tablet, 390 px, keyboard/focus, replacement,
  stale/reconfirm, restart, owner isolation, responsive overflow, and exact cleanup.
- Canonical backend, integration, frontend, lint, format, typecheck, build, migration, and
  repository checks pass.
- Final Git scope proves no staged changes, commit, push, tag, remote, submodule, or out-of-scope
  mutation.

## Candidate status semantics

`PHASE_1E_2_WORKFLOW_GATE_REMEDIATION_IMPLEMENTED_READY_FOR_INDEPENDENT_REVIEW` means F-01 has
been implemented and its declared verification evidence is ready for a fresh read-only review.
It preserves the original review failure and real-201 evidence. It does not mean independently
approved, commit-ready, sealed, closed, production-ready, or authorized for a later phase.
