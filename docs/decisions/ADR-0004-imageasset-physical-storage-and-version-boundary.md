# ADR-0004: ImageAsset Physical Storage and Version Boundary

- Status: `PROPOSED / IMPLEMENTED_PENDING_INDEPENDENT_REVIEW`
- Date: `2026-07-29`
- Phase: `1E-1 — ImageAsset Foundation`
- Supersedes: nothing
- Depends on: Product Contract 0.1.3, Data Dictionary 0.1.3, ADR-0001,
  ADR-0002, ADR-0003, and the approved workflow state machine

## Context

The logical Data Dictionary defines an immutable `ImageAsset`, but it does not freeze all
physical fields needed to safely persist a private file, replace the current main image,
authorize reads, recover from partial failure, or replay an uncertain upload command.
Phase 1E-1 must add that physical boundary without implementing ImageQualityAssessment,
AI analysis, public object access, deletion, or production storage.

The Product Contract permits exactly one original main image in the MVP flow. The logical
role `normalized_analysis_copy` is a future derivative and is not authorized in this phase.
The existing `CommandIdempotencyRecord` already includes `upload_image` in its command
contract and is reused rather than creating a parallel idempotency table.

## Decision

### Aggregate and version identity

- Phase 1E-1 implements only `role=primary_mvp_input`.
- Every accepted upload creates a new immutable `image_assets` row and a new private
  storage object. File bytes and attestation facts are never overwritten.
- Versions are positive and unique per `(paint_project_id, role)`.
- A replacement points to the immediately preceding version through
  `supersedes_image_asset_id`.
- Exactly one row per `(paint_project_id, role)` may be current. PostgreSQL enforces this
  through a partial unique index where `is_current`.
- `PaintProject.current_image_asset_id` is introduced with a composite Foreign Key that
  requires the referenced asset to belong to the same project and owner.
- Cross-owner, cross-project, and cross-role lineage is rejected by composite Foreign Keys.

### Owner and actor boundary

- Every metadata query predicates on both project ownership and image/project identity.
- Missing resources and other-owner resources use the same 404 boundary.
- Rights confirmation requires the configured human Principal. The stable Principal ID and
  display-name snapshot are stored for audit; the display snapshot never authorizes access.
- The system records user attestation only. `confirmed` means the user made the declaration;
  it is not a legal-rights verification.

### Upload validation boundary

- Accepted formats are static JPEG, PNG, and WebP.
- The declared media type must match signature and decoder-detected format.
- Files must be 1–20 MiB, each side must be 768–8192 px, and total pixels must not exceed
  40,000,000.
- Validation performs a full decoder load and rejects corrupt, truncated, unsupported, MIME
  mismatched, animated, decompression-bomb, and out-of-bounds files.
- Width, height, pixel count, format, color mode, alpha presence, EXIF orientation, byte size,
  and SHA-256 are computed by the program and stored.
- These checks are named `upload_validation_result/details`. They are transport and file
  acceptance checks, not the formal `ImageQualityAssessment` decision from FR-003.

### Private storage boundary

- Application code depends on an `ImageStoragePort`; the current adapter is
  `LocalFilesystemImageStorageAdapter`.
- Local storage is allowed only in explicit `development` or `test` environments.
  Production configuration fails closed because no production object-storage adapter has
  been selected.
- The root is server configuration, not request data. Object keys are random,
  normalized, relative keys with a controlled format; user filenames are display metadata
  only.
- Staging and object directories are private. Upload is streamed to a task-owned staging
  file, hashed, and fsynced. Formal publication creates a same-filesystem hard link at the
  destination: the destination must not exist, so a collision atomically fails without replacing
  bytes. The destination directory is fsynced before the staging name is removed.
- `EEXIST` is a typed storage collision. `EXDEV`, permission errors, and filesystems that cannot
  prove the no-replace primitive fail closed; there is no `rename`, `replace`, preflight
  `exists()`, or process-lock fallback.
- A successful publish returns a creation receipt containing the controlled key, expected
  SHA-256 and byte size, filesystem device/inode identity, and link-count evidence. A collision or
  failed publish returns no receipt.
- The API returns an authenticated same-origin content route, never a filesystem path,
  storage key, public URL, or signed public URL.
- Private responses use `Cache-Control: private, no-store`, `nosniff`, a controlled inline
  filename, exact content length, and no range support.

### Transaction, idempotency, and compensation

- The command hash covers normalized role, source, intended uses, declaration version,
  confirmation, and the complete file SHA-256.
- The server-owned upload command scope includes Principal and Project. Within the same
  Principal and Project, same key plus same command replays the stored 201 response and same key
  plus a different command returns 409.
- The same key in a different Project is an independent command; the same key for a different
  Principal is an independent owner scope. No result, payload-hash decision, asset, event, or
  record crosses either boundary.
- PostgreSQL arbitrates concurrent keys and locks the owned project/current image inside a
  finite transaction.
- The object is stored before the database transaction completes. A later database failure may
  request compensation only with the creation receipt produced by that call.
- Compensation reopens the controlled object without following symlinks, verifies regular-file
  device/inode, link count, size, and SHA-256 against the receipt, proves the key is absent from
  all current database references in a post-rollback transaction, and rechecks identity
  immediately before unlink. Any mismatch, database-verification failure, or reference refuses
  deletion and records detectable orphan/compensation state.
- A storage failure creates no database record. Staging cleanup runs on every outcome.
- Orphan scanning is read-only. A key string alone never proves creation ownership, and there is
  no broad directory deletion.

### Workflow boundary

- First upload is allowed only from `DRAFT`.
- Replacement is allowed only from `IMAGE_REVIEW_REQUIRED` or
  `IMAGE_VALIDATION_FAILED`.
- Success creates the immutable asset and `upload_image` audit event, updates the current
  reference, and moves the project to `IMAGE_UPLOADED` in one database transaction.
- Old image rows and bytes are retained. No delete API or UI exists.

## Consequences

- A second business Revision adds `image_assets`, the PaintProject current-image column, and
  their exact constraints. The historical Revision `a10d3d8dab38` remains unchanged.
- Local development now persists private files across application restarts.
- Database rollback cannot by itself roll back a filesystem move, so explicit compensation
  and orphan detection remain required and tested.
- A storage-key collision cannot modify, truncate, replace, or authorize deletion of the
  pre-existing immutable object, including under concurrent publishers.
- The application can display an authorized original and immutable history, but cannot claim
  image quality approval, AI interpretation, color fidelity, inventory matching, or legal
  verification.
- Production deployment remains blocked until a separately reviewed private object-storage,
  encryption, retention, backup, and access-control decision is accepted.

## Rejected Alternatives

- Storing image bytes in PostgreSQL: rejected for this phase because it conflates relational
  and object lifecycle concerns.
- Using the user filename as a key: rejected because of collision, traversal, disclosure, and
  overwrite risks.
- Public static-file hosting: rejected because assets are `project_private`.
- Updating the current row or replacing bytes in place: rejected because it destroys
  immutable history and breaks attestation binding.
- `os.replace`, preflight `exists()` plus rename, and a process-local collision lock: rejected
  because they overwrite or retain cross-process TOCTOU risk and cannot establish immutable
  no-overwrite behavior.
- Deleting the previous image on replacement: rejected because the Product Contract requires
  retained originals and review traceability.
- Introducing S3 or another cloud provider now: rejected because provider selection and
  production access policy are outside the authorized scope.

## Independent Review Boundary

This ADR records the implemented candidate decision. It is not an independent approval,
production authorization, or permission to commit. Any Git sealing requires a separate
read-only review of the migration, constraints, storage adapter, owner isolation,
compensation evidence, and browser behavior.
