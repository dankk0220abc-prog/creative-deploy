# PaintPilot RegionSet Physical Data Dictionary v0.1

- Status: `IMPLEMENTED_PENDING_INDEPENDENT_REVIEW`
- Phase: `Phase 1F — Human-Governed Region Annotation and Review`
- Candidate Revision: `7f3a2b9c4d1e`
- Parent Revision: `d4c8a1f7b2e9`
- Decision: ADR-0006

This supplement freezes only the Phase 1F physical annotation boundary. It does not change the
PaintProject workflow state machine or authorize automated region analysis.

## Shared limits

| Contract | Value |
| --- | ---: |
| Coordinate range | `0..1_000_000` ppm |
| Regions per RegionSet | `0..128` |
| Vertices per Region | `3..256` |
| Vertices per RegionSet | `0..8192` |
| Minimum exact double-area | `100_000_000` ppm-squared |
| Label | trimmed `1..80`, no `<`, `>`, or control characters |
| Notes/review reason | trimmed `1..1000` when present |
| Opacity | `100_000..1_000_000` ppm |
| z-index | `0..127`, unique per RegionSet |

## `region_sets`

One immutable full annotation snapshot.

| Column | Type | Null | Contract |
| --- | --- | --- | --- |
| `id` | UUID | No | Primary key |
| `owner_principal_id` | VARCHAR(128) | No | Server Principal; part of composite ownership FKs |
| `paint_project_id` | UUID | No | Same-owner PaintProject |
| `version` | INTEGER | No | Positive; unique per Project |
| `lifecycle` | VARCHAR(32) | No | `draft`, `submitted`, `approved`, `changes_requested`, or `superseded` |
| `source_primary_image_asset_id` | UUID | No | Same-owner/project current source ImageAsset |
| `source_primary_image_role` | VARCHAR(64) | No | Exactly `primary_front` |
| `source_image_set_fingerprint` | VARCHAR(64) | No | Lowercase SHA-256 |
| `source_image_width` / `source_image_height` | INTEGER | No | `1..8192` |
| `supersedes_region_set_id` | UUID | Yes | Same owner/project ancestry only |
| `based_on_region_set_id` | UUID | Yes | Same owner/project ancestry only |
| `region_count` | INTEGER | No | `0..128`; matches persisted children by Service |
| `total_vertex_count` | INTEGER | No | `0..8192`; matches persisted children by Service |
| `geometry_fingerprint` | VARCHAR(64) | No | Canonical lowercase SHA-256 |
| `created_by_actor_type` | VARCHAR(32) | No | Exactly `user` |
| `created_by_actor_id` | VARCHAR(128) | No | Trimmed server Principal snapshot |
| `created_by_actor_display_name_snapshot` | VARCHAR(200) | No | Trimmed server snapshot |
| `created_at` | TIMESTAMPTZ | No | Database `now()` |

Important keys:

- `uq_region_sets_project_version`;
- `uq_region_sets_project_owner_id`;
- owner/project FK to `paint_projects`;
- four-column source FK to `image_assets`;
- same-owner/project self-FKs for `supersedes` and `based_on`;
- append-only trigger rejecting UPDATE and DELETE.

## `regions`

One immutable human-labelled simple Polygon.

| Column | Type | Null | Contract |
| --- | --- | --- | --- |
| `id` | UUID | No | Primary key |
| `region_set_id` | UUID | No | Same owner/project RegionSet |
| `paint_project_id` | UUID | No | Denormalized for composite integrity |
| `owner_principal_id` | VARCHAR(128) | No | Denormalized for composite integrity |
| `stable_region_key` | UUID | No | Unique inside one RegionSet |
| `kind` | VARCHAR(16) | No | `paint` or `exclude` |
| `label` | VARCHAR(80) | No | Human display label |
| `normalized_label` | VARCHAR(80) | No | Deterministic NFKC/casefold/space normalization |
| `z_index` | INTEGER | No | `0..127`, unique inside one RegionSet |
| `opacity_ppm` | INTEGER | No | `100_000..1_000_000` |
| `notes` | VARCHAR(1000) | Yes | Human text only |
| `vertex_count` | INTEGER | No | `3..256` |
| `area_twice_ppm_squared` | BIGINT | No | Positive exact shoelace double-area |
| `bbox_min_x_ppm` / `bbox_min_y_ppm` | INTEGER | No | In bounds |
| `bbox_max_x_ppm` / `bbox_max_y_ppm` | INTEGER | No | In bounds and greater than min |
| `created_at` | TIMESTAMPTZ | No | Database `now()` |

Important keys:

- composite FK `(region_set_id, paint_project_id, owner_principal_id)`;
- unique `(region_set_id, stable_region_key)` and `(region_set_id, z_index)`;
- append-only trigger rejecting UPDATE and DELETE.

## `region_vertices`

One sequenced normalized integer point.

| Column | Type | Null | Contract |
| --- | --- | --- | --- |
| `region_id` | UUID | No | Region identity |
| `sequence` | INTEGER | No | `0..255`; primary-key component |
| `region_set_id` | UUID | No | Same RegionSet as parent Region |
| `x_ppm` / `y_ppm` | INTEGER | No | `0..1_000_000` |

Important keys:

- primary key `(region_id, sequence)`;
- composite FK `(region_id, region_set_id)` to the exact Region/RegionSet pair;
- append-only trigger rejecting UPDATE and DELETE.

The closing point is implicit: clients do not store the first Vertex again at the end.

## `region_set_reviews`

One append-only human decision against an exact submitted snapshot.

| Column | Type | Null | Contract |
| --- | --- | --- | --- |
| `id` | UUID | No | Primary key |
| `owner_principal_id` | VARCHAR(128) | No | Same owner as Project/RegionSet |
| `paint_project_id` | UUID | No | Same Project as RegionSet |
| `region_set_id` | UUID | No | Exact reviewed snapshot |
| `version` | INTEGER | No | Positive; unique per Project |
| `verdict` | VARCHAR(32) | No | `approved` or `changes_requested` |
| `reason` | VARCHAR(1000) | Yes | Required and nonblank for `changes_requested` |
| `actor_type` | VARCHAR(32) | No | Exactly `user` |
| `actor_id` | VARCHAR(128) | No | Server Principal snapshot |
| `actor_display_name_snapshot` | VARCHAR(200) | No | Server display snapshot |
| `created_at` | TIMESTAMPTZ | No | Database `now()` |

Important keys:

- composite owner/project/RegionSet FK;
- unique `(paint_project_id, version)` and unique `region_set_id`;
- append-only trigger rejecting UPDATE and DELETE.

The Review does not mutate the RegionSet. API responses derive effective lifecycle from the
immutable submitted row plus its immutable Review.

## Derived facts

`stale=true` when any of these is true:

- current ImageSet fingerprint differs from `source_image_set_fingerprint`;
- current `primary_front` ImageAsset differs from `source_primary_image_asset_id`;
- current ImageSet status is not READY.

`superseded` is also derived when a later immutable snapshot replaces the effective current
snapshot. Stored historical rows, Reviews, and geometry remain unchanged.

## Canonical geometry fingerprint

The SHA-256 input is compact, sorted-key UTF-8 JSON with schema marker
`paintpilot_region_geometry_fingerprint.v1`. It includes Project ID, ImageSet fingerprint,
source primary asset ID, RegionSet version, and every Region in `(z_index, stable_region_key)`
order with its human content and sequenced ppm Vertices.

It excludes paths, object keys, timestamps, UI selection, hover, visibility, viewport,
zoom/pan, undo/redo, and transient request state.

## Migration and rollback

Revision `7f3a2b9c4d1e` adds exactly these four tables and append-only trigger functions. It does
not alter the three historical revisions or existing ImageAsset bytes. Downgrade first verifies
all four tables are empty, then removes only Phase 1F objects. Non-empty downgrade fails closed.
