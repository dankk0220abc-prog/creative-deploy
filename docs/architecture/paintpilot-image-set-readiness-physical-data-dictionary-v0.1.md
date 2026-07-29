# PaintPilot ImageSet Readiness Physical Data Dictionary Supplement v0.1

- Status: `IMPLEMENTED_PENDING_INDEPENDENT_REVIEW`
- Date: `2026-07-29`
- Phase: `1E-2 — Multi-Role ImageSet and Readiness`
- Supplements: the domain dictionary and Phase 1E-1 ImageAsset physical supplement
- Physical Revision: `d4c8a1f7b2e9`, parent `5ed9906e7d33`

This supplement freezes only the Phase 1E-2 role vocabulary, derived ImageSet projection, and
append-only human readiness-review record. It preserves the sealed private-storage, validation,
attestation, owner-isolation, and immutable-object boundary.

## `image_assets.role` increment

| Value | Required | Meaning | Deterministic claim |
| --- | --- | --- | --- |
| `primary_front` | Yes | User-declared main/front reference; compatibility successor of `primary_mvp_input` | None about actual viewpoint |
| `reference_back` | Yes | User-declared back reference | None about actual viewpoint |
| `reference_angle` | Yes | User-declared angle reference | None about actual viewpoint |
| `reference_detail` | No | User-declared optional detail reference | None about actual content |

All existing `image_assets` columns and constraints remain in force. Version uniqueness and the
one-current partial index remain per `(paint_project_id, role)`. The same-role lineage composite
Foreign Key now accepts the exact four values above. Existing `primary_mvp_input` rows map in
place to `primary_front`.

## Derived `ImageSet`

No `image_sets` table is added. The owner-scoped read projection contains:

| Field | Type | Source | Rule |
| --- | --- | --- | --- |
| `paint_project_id` | UUID | owned PaintProject | INTERNAL project identity |
| `image_set_fingerprint` | 64-char lowercase hex | Program | Canonical deterministic snapshot hash |
| `roles` | Four ordered role slots | Current and historical ImageAsset rows | Exact order: front, back, angle, detail |
| `checklist` | Object | Program | Deterministic facts and blocker codes only |
| `latest_review` | Review or null | Database | Newest Project-local version |
| `status` | enum | Program | `incomplete/ready/stale/not_ready` |
| `stale_reasons` | string array | Program | Role/fact changes; empty unless stale |

Each role slot exposes `role`, `required`, `missing`, `object_available`, `current`, and immutable
newest-first `history`. Storage provider, key, local path, owner ID, and internal attestation
actor IDs remain excluded from the ImageAsset API projection.

## Checklist fields

| Field | Deterministic rule |
| --- | --- |
| `required_roles_present` | Current front, back, and angle assets all exist |
| `deterministic_validation_accepted` | Every current formal asset has accepted upload validation |
| `rights_complete` | Every current formal asset has complete confirmed attestation facts |
| `content_distinct` | Required current assets exist and have three distinct SHA-256 values |
| `objects_available` | Every current formal private object passes identity/availability read |
| `snapshot_current` | Latest review fingerprint equals the current fingerprint |
| `can_mark_ready` | All non-snapshot prerequisites pass |
| `blockers` | Stable codes for failed non-snapshot prerequisites |

Blocker codes are `missing_required_roles`, `deterministic_validation_not_accepted`,
`rights_attestation_incomplete`, `duplicate_or_missing_required_content`, and
`private_object_unavailable`.

## `image_set_readiness_reviews`

| Column | PostgreSQL type | Null | Source | Mutation | Rule / classification |
| --- | --- | --- | --- | --- | --- |
| `id` | UUID | No | Program | Never | Primary key; INTERNAL |
| `owner_principal_id` | VARCHAR(128) | No | PrincipalContext | Never | Same-owner Project FK; INTERNAL |
| `paint_project_id` | UUID | No | Program | Never | Owner-scoped Project; INTERNAL |
| `version` | INTEGER | No | Program | Never | >=1; unique per Project |
| `verdict` | VARCHAR(32) | No | Human command | Never | `ready/not_ready` |
| `reason` | VARCHAR(1000) | Yes | Human command | Never | Required and non-blank for `not_ready` |
| `primary_front_image_asset_id` | UUID | Yes | Program snapshot | Never | Same owner/Project/`primary_front` composite FK |
| `primary_front_role` | VARCHAR(64) | Yes | Program discriminator | Never | Null with ID or exact `primary_front` |
| `reference_back_image_asset_id` | UUID | Yes | Program snapshot | Never | Same owner/Project/`reference_back` composite FK |
| `reference_back_role` | VARCHAR(64) | Yes | Program discriminator | Never | Null with ID or exact `reference_back` |
| `reference_angle_image_asset_id` | UUID | Yes | Program snapshot | Never | Same owner/Project/`reference_angle` composite FK |
| `reference_angle_role` | VARCHAR(64) | Yes | Program discriminator | Never | Null with ID or exact `reference_angle` |
| `reference_detail_image_asset_id` | UUID | Yes | Program snapshot | Never | Same owner/Project/`reference_detail` composite FK |
| `reference_detail_role` | VARCHAR(64) | Yes | Program discriminator | Never | Null with ID or exact `reference_detail` |
| `image_set_fingerprint` | VARCHAR(64) | No | Program | Never | Exactly 64 lowercase hex |
| `actor_type` | VARCHAR(32) | No | Program | Never | Exact `user` |
| `actor_id` | VARCHAR(128) | No | PrincipalContext | Never | Trimmed stable ID; INTERNAL |
| `actor_display_name_snapshot` | VARCHAR(200) | No | PrincipalContext | Never | Audit snapshot; never authorizes |
| `created_at` | TIMESTAMPTZ | No | Database | Never | Append timestamp |

## Database invariants

- Unique `(paint_project_id, version)` serializes the review history.
- Composite Project/owner Foreign Key prevents cross-owner review rows.
- Four composite asset Foreign Keys bind each non-null snapshot ID to the same Project, owner,
  and exact role.
- `ready` requires non-null front, back, and angle asset IDs.
- `not_ready` requires a normalized non-null reason.
- A trigger rejects every `UPDATE` and `DELETE` with SQLSTATE `55000`.
- There is no cascade-delete path and no API mutation/deletion route.
- The owner/project/created-at index supports newest-first history.

## Fingerprint v1

The canonical input is:

- version marker `paintpilot_image_set_fingerprint.v1`;
- Project UUID;
- the four roles in fixed order;
- for each role: current asset UUID or null, SHA-256 or null, upload-validation result or null,
  rights status/version or null, and object-availability boolean.

Canonical JSON uses sorted keys and compact separators before SHA-256. No timestamp, storage
path/key, filename, actor display name, or random value participates.

## API-safe projection

Review responses may return Project ID, version, verdict, human reason, role asset IDs,
fingerprint, actor type/ID/display snapshot, and created time. Access remains owner-scoped.
Storage internals, database URLs, exception text, and cross-owner existence are never returned.

## Migration lifecycle

- Upgrade: `5ed9906e7d33 -> d4c8a1f7b2e9`.
- Safe downgrade: only with no review rows and no non-primary role rows; maps `primary_front` back
  to `primary_mvp_input`.
- Unsafe downgrade: fails closed with SQLSTATE `55000`.
- Historical revisions `a10d3d8dab38` and `5ed9906e7d33` remain unchanged.

## Explicitly deferred

Image quality, viewpoint recognition, segmentation, regions, Polygon Editor, multi-image fusion,
AI/model calls, HumanApproval workflow entities, inventory, public URLs, deletion, production
object storage, real authentication, and production deployment remain unimplemented.
