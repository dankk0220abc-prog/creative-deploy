# ADR-0005: Multi-Role ImageSet and Human Readiness Boundary

- Status: `PROPOSED / IMPLEMENTED_PENDING_INDEPENDENT_REVIEW`
- Date: `2026-07-29`
- Phase: `1E-2 — Multi-Role ImageSet and Readiness`
- Supersedes: nothing
- Extends: ADR-0004 role vocabulary only; it does not supersede the ADR-0004 workflow gate
- Preserves: ADR-0004 workflow, storage, immutability, owner, attestation, validation, and
  production boundaries
- Depends on: Product Contract 0.1.3, the approved workflow state machine, ADR-0001 through
  ADR-0004, and the sealed Phase 1E-1 implementation

## Context

The user confirmed the approximately 60% checkpoint direction and authorized Phase 1E-2. The
planning workspace now needs separately identified reference views and an explicit human
readiness record before later human-guided region work. Phase 1E-1 already provides immutable
private bytes, owner-scoped access, deterministic upload acceptance, rights attestation,
replacement history, and safe Project-scoped command replay.

This phase must extend that foundation without claiming that a file actually depicts a front,
back, angle, or detail view. Role selection is a human declaration. It must not become image
quality assessment, AI interpretation, multi-image fusion, public access, deletion, production
storage, or real authentication.

The first independent Phase 1E-2 review returned
`CONTRACT_OR_ARCHITECTURE_DECISION_REQUIRED`. Finding F-01 demonstrated a real HTTP 201
`primary_front` replacement while the Project was already in `IMAGE_UPLOADED`. That evidence is
retained: the original candidate incorrectly applied one shared editable-state set to every
role. Project control chose to preserve the sealed ADR-0004 workflow boundary and remediate the
Phase 1E-2 candidate; this ADR does not reinterpret the unauthorized 201 as valid behavior.

## Decision

### Formal role vocabulary and compatibility

- `primary_front`, `reference_back`, and `reference_angle` are required roles.
- `reference_detail` is optional.
- The API accepts only those exact four values. Unknown values fail validation.
- Every role retains the Phase 1E-1 immutable version-chain rules and one-current partial
  uniqueness.
- Revision `d4c8a1f7b2e9` maps existing `primary_mvp_input` values to `primary_front` in place.
  It does not create replacement assets or alter IDs, versions, lineage, storage keys, bytes,
  hashes, attestation, or `paint_projects.current_image_asset_id`.
- The legacy current-image pointer continues to identify the current `primary_front`. Uploads to
  reference roles do not change that pointer or add new workflow states.
- Uploading a role is a user classification, not deterministic view recognition.

### Role-aware mutation policy

The backend Service is the final authority. Its pure policy evaluates the declared role, whether
that role already has a current asset, the resulting first-upload/replacement operation, and the
current PaintProject workflow state. The UI mirrors this matrix but cannot grant authorization.

| Role | Operation | Allowed workflow states | Explicitly frozen |
| --- | --- | --- | --- |
| `primary_front` | first upload | `DRAFT` only | every other state |
| `primary_front` | replacement | `IMAGE_REVIEW_REQUIRED`, `IMAGE_VALIDATION_FAILED` | `DRAFT`, `IMAGE_UPLOADED`, `IMAGE_VALIDATED`, and every other state |
| `reference_back`, `reference_angle`, `reference_detail` | first upload or replacement | `DRAFT`, `IMAGE_UPLOADED`, `IMAGE_REVIEW_REQUIRED`, `IMAGE_VALIDATION_FAILED` | `IMAGE_VALIDATED` and every later/other state |

A successful first `primary_front` upload uses the existing
`DRAFT -> IMAGE_UPLOADED` transition. A legal primary replacement from review-required or
validation-failed also returns the Project to `IMAGE_UPLOADED` through the existing upload
transition. Reference mutations never change PaintProject workflow state and never create a
state-transition event. `IMAGE_VALIDATED` freezes every image role.

Known-new denied commands fail closed with the existing safe structured 409 before private bytes
are staged. The final locked write transaction re-evaluates the same policy before publication,
so a race cannot use a stale preflight decision. A denial creates no staging or formal object,
ImageAsset/version/lineage row, command result, transition event, current-pointer change, or
readiness-review change. An already completed same-key upload may still replay its immutable
result under the sealed idempotency contract.

### Derived ImageSet

`ImageSet` is an owner-scoped read model derived from current and historical `image_assets` plus
the latest readiness review. It is not a mutable aggregate row and has no separate `image_sets`
table.

For each formal role, the response reports required/optional status, missing status, private
object availability, the current asset, and retained newest-first history. It also reports a
deterministic checklist and one of:

- `incomplete`: no current human review matches the set and prerequisites may be missing;
- `ready`: latest review is `ready` and its fingerprint matches the current set;
- `not_ready`: latest review is `not_ready` and its fingerprint matches the current set;
- `stale`: a saved review exists but its fingerprint no longer matches current facts.

### Deterministic readiness facts

The program computes only:

- presence of all three required current roles;
- `upload_validation_result=accepted` for every current formal asset;
- complete confirmed rights-attestation facts for every current formal asset;
- distinct SHA-256 values across the required current roles;
- availability and identity-consistent readability of every current private object;
- whether the latest human review fingerprint matches the current fingerprint.

The `paintpilot_image_set_fingerprint.v1` SHA-256 covers the Project ID and the ordered formal
role snapshot: role, current asset ID or absence, SHA-256, upload result, rights status/version,
and private-object availability. It excludes time, filesystem paths, storage keys, random values,
and display-only text. Canonical JSON ordering makes the same facts produce the same fingerprint.

These checks can block `READY`; they do not decide image quality, view correctness, legal rights,
or fitness for painting.

### Append-only human reviews

- `image_set_readiness_reviews` stores immutable, owner-scoped `ready` or `not_ready` decisions.
- Every row has a positive Project-local version, current fingerprint, exact role asset snapshot,
  stable human actor ID, display-name snapshot, and creation timestamp.
- `NOT READY` requires a normalized non-empty reason of at most 1,000 characters.
- `READY` requires all three required role references and all deterministic prerequisites.
- Composite Foreign Keys require every stored asset reference to match the review's Project,
  owner, and formal role.
- A PostgreSQL trigger rejects `UPDATE` and `DELETE`; the application exposes create and list,
  never mutation or deletion.
- Replacing any role or changing a fingerprint input preserves the old review as history and
  derives `stale`; the user must append a new review to reconfirm.

### Concurrency and idempotency

- Upload and readiness commands lock the owned PaintProject row, serializing role-current changes
  with readiness snapshot creation.
- `review_image_set_readiness` reuses the sealed command-idempotency table.
- Scope is Principal plus Project. Same Project/key/payload/fingerprint replays the same 201
  result; changed verdict, reason, or fingerprint returns safe 409.
- The same key in another Project or for another Principal is independent.
- Project-local review versions are allocated while holding the Project lock.
- A concurrent upload/review outcome can record the old snapshot or the new snapshot, but it
  cannot report an old snapshot as current after the replacement commits.

### API and UI

- `GET /api/v1/paint-projects/{project_id}/image-set` returns the derived set.
- `POST /api/v1/paint-projects/{project_id}/image-set/readiness-reviews` appends a decision.
- `GET /api/v1/paint-projects/{project_id}/image-set/readiness-reviews` returns newest-first
  immutable history.
- All routes use the same owner-safe 404 boundary and same-origin private content URLs.
- The Project Detail workbench exposes four labeled role cards, required/optional state,
  preview and retained history, role/workflow-aware add/replace actions and lock explanations,
  checklist blockers, READY / NOT READY controls, stale state, and review history.
- There is no delete, AI, automated angle classification, quality score, legal verification,
  public URL, or production-storage control.

## Migration and downgrade boundary

Revision `d4c8a1f7b2e9` is the sole Phase 1E-2 revision and has parent `5ed9906e7d33`.
Historical revisions remain byte-for-byte unchanged.

Downgrade is allowed only when no readiness-review rows and no non-primary role assets exist.
When safe, `primary_front` maps back to `primary_mvp_input`. If downgrade would discard Phase
1E-2 facts, PostgreSQL raises `55000` and preserves them.

## Consequences

- One Project can retain independent immutable histories for four declared roles.
- The role-aware gate preserves the sealed primary workflow while allowing references to evolve
  only in the four pre-validation states.
- Readiness is explicit and auditable without inventing an AI or quality conclusion.
- Existing Phase 1E-1 assets remain addressable and readable after migration.
- Staleness is derived from the changed fingerprint after any legal role replacement and cannot
  rewrite historical human decisions; rejected mutations leave the fingerprint unchanged.
- The current workflow state machine remains unchanged; readiness does not imply region analysis,
  plan approval, or production readiness.
- Production remains blocked on real authentication and a separately approved production
  private-object-storage decision.

## Rejected alternatives

- Reusing one current slot for all reference images: loses role and lineage integrity.
- Overwriting a readiness row after replacement: destroys the historical decision context.
- Treating asset timestamps or filenames as fingerprint inputs: creates irrelevant staleness.
- Trusting only application checks for snapshot roles: permits invalid cross-role rows through
  direct database writes.
- Claiming that a user-selected role proves image viewpoint: exceeds deterministic evidence.
- Adding an `ImageQualityAssessment`, AI provider, fusion pipeline, delete API, or workflow
  transition: outside the authorized phase.

## Independent review boundary

This ADR records the remediated candidate decision and preserves the original F-01/real-201
evidence. The remediation has not yet received a fresh independent review. It is not an
independent approval, production authorization, Git-sealing permission, or authorization for a
later phase.
