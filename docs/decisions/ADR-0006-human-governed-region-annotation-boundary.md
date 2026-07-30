# ADR-0006 — Human-Governed Region Annotation and Review Boundary

- Status: `PROPOSED / IMPLEMENTED_PENDING_INDEPENDENT_REVIEW`
- Date: 2026-07-29
- Phase: `Phase 1F — Human-Governed Region Annotation and Review`
- Parent image boundary: ADR-0005 and sealed Revision `d4c8a1f7b2e9`
- Candidate Revision: `7f3a2b9c4d1e`

## Context

The sealed Phase 1E-2 boundary can derive a four-role private ImageSet and append a human
READY / NOT READY decision against its exact fingerprint. PaintPilot still needs a human-operated
way to identify paint and exclusion areas without introducing automated segmentation, semantic
recognition, image-quality scoring, color design, lighting, material selection, or PaintPlan
generation.

Phase 1F is deliberately independent from the PaintProject workflow state machine. A RegionSet
approval is an exact annotation review, not approval of the overall Project and not authority to
advance any PaintProject state.

## Decision

1. A RegionSet is one immutable, owner-scoped snapshot of human-authored simple Polygons.
   Every save and submit creates a new row; no RegionSet, Region, Vertex, or Review update/delete
   command exists.
2. A RegionSet binds the current Project, current human-READY ImageSet fingerprint, current
   `primary_front` ImageAsset ID, and its persisted dimensions. The server derives all source
   facts; clients cannot provide or override them.
3. Coordinates are normalized integers `x_ppm` and `y_ppm` in `0..1_000_000`. One Region contains
   one simple Polygon, without holes, curves, or MultiPolygon behavior.
4. Region kind is the controlled vocabulary `paint | exclude`. The human supplies the display
   label; NFKC/casefold/whitespace normalization creates a deterministic secondary label without
   replacing the display label.
5. Limits are centralized: 128 Regions per snapshot, 256 Vertices per Region, 8192 Vertices per
   snapshot, and exact shoelace double-area of at least `100_000_000` ppm-squared.
6. Geometry validation is deterministic integer/rational arithmetic. It rejects out-of-bounds
   coordinates, short or over-budget Polygons, zero-length edges, repeated Vertices,
   self-intersection, insufficient area, duplicate stable keys, and duplicate z-indexes. Region
   overlap is allowed and returned only as a deterministic warning.
7. Geometry fingerprints use fixed JSON canonicalization and SHA-256. Inputs include the Project,
   exact ImageSet fingerprint, exact source primary asset, RegionSet version, canonical Region
   order, labels, kinds, notes, opacity, z-order, stable keys, and sequenced ppm Vertices. Storage
   paths, object keys, time, random UI state, selection, zoom, pan, and undo history are excluded.
8. Persisted lifecycle vocabulary is `draft | submitted`; human Review rows derive
   `approved | changes_requested`, and later snapshots derive `superseded`. The schema retains the
   complete controlled vocabulary so every externally reported lifecycle is database-bounded.
9. Submit revalidates source readiness, source identity, fingerprint, geometry, non-empty labels,
   limits, and the presence of at least one `paint` Region. It seals a new immutable submitted
   snapshot rather than mutating the draft.
10. Review is append-only and accepts only an exact, current, non-stale submitted snapshot.
    `changes_requested` requires a non-empty human reason. The current configured Demo Principal
    may review in this local boundary, but it is not enterprise authentication or role separation.
11. Staleness is derived whenever the current ImageSet fingerprint differs, the current primary
    asset differs, or current ImageSet readiness is not READY. Historical snapshots and decisions
    remain readable and are never rewritten as invalid history.
12. Save, submit, and review require Project-scoped `Idempotency-Key` values. A PostgreSQL
    Project-row lock serializes version allocation and source mutation races. Exact replay returns
    the committed result; changed payload or stale base returns a safe structured 409.
13. Owner identity always comes from the server-side Principal Adapter. Missing and other-owner
    Project/RegionSet requests use the same non-disclosing 404 behavior.
14. The UI uses the existing private primary-content endpoint and an SVG overlay. It supports
    human draw/close/cancel, vertex drag/insert/delete, label/kind/z-order/visibility/opacity/notes,
    zoom/pan/fit, undo/redo, immutable save, submit, review, stale recovery, and history. PostgreSQL,
    not localStorage, is the persisted source of truth.
15. Historical recovery is an explicit snapshot-target command:
    `POST /api/v1/paint-projects/{project_id}/region-sets/{source_region_set_id}/drafts`, with a
    strict body containing `expected_current_region_set_id` and
    `expected_current_version`. The immutable source may be current, stale, superseded, submitted,
    approved, or changes-requested, but it must belong to the same Owner and Project.
16. The fork command locks the Project and rechecks the actual current snapshot and current READY
    ImageSet in the same transaction. A mismatch returns safe 409 with no RegionSet, Region,
    Vertex, Review, event, object, or completed-command side effect. Success allocates
    `actual_current.version + 1`, copies the source geometry exactly, binds current server-derived
    image facts, records `based_on_region_set_id = source_region_set_id`, and records
    `supersedes_region_set_id = actual_current_region_set_id`. Reviews are never copied.
17. Fork idempotency is Project-scoped. Exact same-key/same-payload replay returns the committed
    draft even after current has advanced; the same key with a changed source or expected-current
    payload returns safe conflict. Distinct concurrent keys against one expected current can
    commit at most one next version.
18. The frontend keeps `current` and `viewed` snapshot identities separate. Lifecycle commands
    target only the exact current snapshot; a historical detail is explicitly read-only and offers
    only exact fork or return-to-current. While an asynchronous historical detail is unresolved,
    all snapshot commands fail closed and no current-snapshot fallback is allowed.

## Database enforcement

Candidate Revision `7f3a2b9c4d1e`, with parent `d4c8a1f7b2e9`, adds exactly:

- `region_sets`;
- `regions`;
- `region_vertices`;
- `region_set_reviews`.

Composite foreign keys keep Owner, Project, source primary asset, RegionSet ancestry, Regions, and
Vertices in the same aggregate. Unique constraints protect Project version, Review version,
stable Region key, z-index, and Vertex sequence. Check constraints enforce controlled vocabulary,
coordinate/count/range/text rules. PostgreSQL triggers reject UPDATE and DELETE on all four
tables. Downgrade is allowed only when all four tables are empty.

Service validation remains responsible for geometric properties and cross-row count/fingerprint
consistency that cannot be fully expressed as ordinary constraints.

## Consequences

- Historical annotation and review evidence is retained even when the image source changes.
- RegionSet approval does not advance PaintProject and cannot authorize plan generation.
- Mobile users can inspect all data and reach basic editing controls, while high-precision
  editing remains more efficient on a larger viewport.
- There is no deletion API. Removing a Region from an unsaved edit creates a later snapshot and
  never deletes earlier evidence.
- Local private storage and the configured Demo Principal remain development/test-only.

## Explicitly outside this decision

- AI/LLM/vision/OCR/RAG/Agent/embedding providers;
- automated segmentation, subject recognition, semantic labels, quality scores, or suggestions;
- lighting, Cel Shading region advice, color, materials, inventory, or PaintPlan;
- external object storage, public/signed URLs, physical deletion, real authentication, or RBAC;
- any PaintProject state-machine change or automatic workflow transition.

## Review boundary

This ADR records the implementation candidate. It is not an independent approval, production
authorization, Git seal, or phase closure. A fresh read-only reviewer must verify the exact
candidate before any separate sealing task.
