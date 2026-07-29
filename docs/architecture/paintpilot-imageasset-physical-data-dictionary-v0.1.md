# PaintPilot ImageAsset Physical Data Dictionary Supplement v0.1

- Status: `IMPLEMENTED_PENDING_INDEPENDENT_REVIEW`
- Date: `2026-07-29`
- Phase: `1E-1 — ImageAsset Foundation`
- Supplements: `paintpilot-domain-data-dictionary-v0.1.md` version 0.1.3
- Physical Revision: `5ed9906e7d33`, parent `a10d3d8dab38`

This supplement freezes only the physical Phase 1E-1 subset. The logical Data Dictionary
remains authoritative for later entities. `ImageQualityAssessment`,
`normalized_analysis_copy`, region entities, plans, AI records, deletion, and production
storage are not introduced here.

## Logical-to-physical alignment

| Logical field | Phase 1E-1 physical interpretation |
| --- | --- |
| `ImageAsset.project_id` | `paint_project_id`; composite owner/project FK to `paint_projects` |
| `mime_type` | Split into declared `declared_content_type` and program-detected `detected_format` |
| `size_bytes` | `byte_size` |
| `uploaded_at` | `created_at` |
| `role` | Only `primary_mvp_input`; `normalized_analysis_copy` is deferred |
| Replacement semantics | `version`, `supersedes_image_asset_id`, `is_current`, `lifecycle_status` |
| Private file reference | `storage_provider` plus SENSITIVE `storage_key`; neither is exposed by API |
| Upload acceptance | `upload_validation_result/details`; explicitly not ImageQualityAssessment |
| Actor provenance | Stable actor ID, actor type, and non-authorizing display snapshot |

## `paint_projects` increment

| Column | PostgreSQL type | Null | Source | Mutation | Rule |
| --- | --- | --- | --- | --- | --- |
| `current_image_asset_id` | `UUID` | Yes | Program/database | Guarded | Composite FK `(current_image_asset_id,id,owner_principal_id)` to an ImageAsset with the same asset ID, project, and owner |

The migration also adds unique `(id, owner_principal_id)` to `paint_projects` so every
ImageAsset ownership reference is database-enforced.

## `image_assets`

| Column | PostgreSQL type | Null | Source | Mutation | Validation / classification |
| --- | --- | --- | --- | --- | --- |
| `id` | `UUID` | No | Program | Never | Primary key; INTERNAL |
| `paint_project_id` | `UUID` | No | Program | Never | Same-owner project FK; INTERNAL |
| `owner_principal_id` | `VARCHAR(128)` | No | PrincipalContext | Never | Trimmed stable owner; INTERNAL |
| `role` | `VARCHAR(64)` | No | Command/program | Never | `primary_mvp_input`; INTERNAL |
| `version` | `INTEGER` | No | Program | Never | >=1; unique per project/role |
| `supersedes_image_asset_id` | `UUID` | Yes | Program | Never | Same owner/project/role lineage FK |
| `is_current` | `BOOLEAN` | No | Program | Guarded | One current row per project/role |
| `lifecycle_status` | `VARCHAR(32)` | No | Program | Guarded | `current/superseded`; consistent with `is_current` |
| `storage_provider` | `VARCHAR(32)` | No | Server config | Never | Current value `local_filesystem`; SENSITIVE |
| `storage_key` | `VARCHAR(128)` | No | Storage adapter | Never | Unique controlled relative object key; SENSITIVE |
| `original_filename` | `VARCHAR(255)` | No | Upload metadata | Never | Basename only; no separator/control char; SENSITIVE |
| `declared_content_type` | `VARCHAR(64)` | No | Multipart metadata | Never | JPEG/PNG/WebP and must match detection; INTERNAL |
| `detected_format` | `VARCHAR(16)` | No | Decoder | Never | `jpeg/png/webp`; INTERNAL |
| `byte_size` | `INTEGER` | No | Program | Never | 1–20,971,520; INTERNAL |
| `width` | `INTEGER` | No | Decoder | Never | 768–8192; INTERNAL |
| `height` | `INTEGER` | No | Decoder | Never | 768–8192; INTERNAL |
| `pixel_count` | `INTEGER` | No | Program | Never | `width*height`, <=40,000,000; INTERNAL |
| `color_mode` | `VARCHAR(32)` | No | Decoder | Never | Non-empty decoder mode; INTERNAL |
| `has_alpha` | `BOOLEAN` | No | Decoder | Never | Program fact; INTERNAL |
| `exif_orientation` | `INTEGER` | Yes | Decoder | Never | 1–8 when present; INTERNAL |
| `sha256` | `VARCHAR(64)` | No | Program | Never | Exactly 64 lowercase hex; INTERNAL |
| `upload_validation_result` | `VARCHAR(64)` | No | Program | Never | `accepted`; not a quality decision |
| `upload_validation_details` | `JSONB` | No | Program | Never | JSON object with deterministic check facts only |
| `source_type` | `VARCHAR(64)` | No | User attestation | Never | Approved three-value source enum; INTERNAL |
| `rights_attestation_status` | `VARCHAR(32)` | No | User attestation | Versioned row | `pending/confirmed/rejected`; API creates `confirmed` |
| `rights_attestation_version` | `INTEGER` | No | Contract | Never | >=1; current command requires 1 |
| `intended_usage` | `JSONB` | No | User attestation | Versioned row | Non-empty subset of approved usage enum; API rejects duplicates |
| `rights_attested_by_principal_id` | `VARCHAR(128)` | Yes | PrincipalContext | Never | Required for confirmed/rejected; INTERNAL |
| `rights_attested_at` | `TIMESTAMPTZ` | Yes | Program | Never | Required for confirmed/rejected; INTERNAL |
| `created_by_actor_type` | `VARCHAR(32)` | No | Program | Never | `user` |
| `created_by_actor_id` | `VARCHAR(128)` | No | PrincipalContext | Never | Trimmed stable ID; INTERNAL |
| `created_by_actor_display_name_snapshot` | `VARCHAR(200)` | No | PrincipalContext | Never | Trimmed audit snapshot; never authorizes |
| `created_at` | `TIMESTAMPTZ` | No | Program/database | Never | Immutable creation time; INTERNAL |

## API-safe projection

The API may return version, lineage ID, lifecycle, display filename, content type/format,
byte and dimension facts, color/alpha/orientation facts, SHA-256, upload-check facts,
attestation fields, creation time, and an owner-authorized same-origin `content_url`.

It must not return `owner_principal_id`, storage provider/key, local path, attesting actor ID,
created-by actor fields, database constraint details, or exception text.

## Database invariants

- One current version is enforced by partial unique index
  `uq_image_assets_project_role_current`.
- `(project, role, version)` and `storage_key` are unique.
- Project ownership, current reference, and replacement lineage are composite-FK enforced.
- Delete behavior is `RESTRICT`; Phase 1E-1 has no delete command.
- JSON validation details must be an object. Intended usage must be a non-empty allowed array;
  uniqueness and canonical order are additionally enforced in the request schema.
- The migration supports `a10d3d8dab38 -> 5ed9906e7d33 -> a10d3d8dab38 ->
  5ed9906e7d33` without changing the historical parent Revision.

## Deferred fields and entities

- `normalized_from_asset_id` is deferred with `normalized_analysis_copy`.
- Formal quality scores, decisions, reasons, Policy version, and model call references remain
  in future `ImageQualityAssessment`.
- Retention periods, legal hold, deletion requests, encryption keys, backup tiers, and cloud
  object metadata require a production-storage ADR.
