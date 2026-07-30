# Phase 1F — Human-Governed Region Annotation and Review Implementation Plan

- Status:
  `PHASE_1F_SNAPSHOT_TARGET_REMEDIATION_IMPLEMENTED_READY_FOR_INDEPENDENT_REVIEW`
- Candidate verdict target:
  `PHASE_1F_SNAPSHOT_TARGET_REMEDIATION_IMPLEMENTED_READY_FOR_INDEPENDENT_REVIEW`
- Current environment-isolated continuation verdict:
  `PHASE_1F_SNAPSHOT_TARGET_REMEDIATION_IMPLEMENTED_READY_FOR_INDEPENDENT_REVIEW`
- Historical implementation-conversation verdict: `PHASE_1F_IMPLEMENTATION_FAILED`
- Historical incident classification: `ENVIRONMENT_ISOLATION_INVALID_ATTEMPT`
- Historical process deviation: one unsuccessful supplemental-browser Create request reached the
  unrelated port-8000 service because the Vite proxy variable name was wrong; it remains recorded
  as historical evidence and is not counted as evidence for the isolated continuation
- Baseline branch: `main`
- Baseline HEAD: `91f3135041c16c8e600d963c1341cb1af1db1458`
- Baseline tree: `35302def051a10b018e02556068485ae1d40a338`
- Baseline commit count: `19`
- Corrected continuation scope: 14 modified tracked + 22 untracked = 36 paths including
  Manifest, 35 paths excluding Manifest
- Parent Revision: `d4c8a1f7b2e9`
- Candidate Revision: `7f3a2b9c4d1e`
- Overall checkpoint remains: `approximately_70_percent`

## Governance boundary

This is an implementation candidate, not independent approval, production readiness, a Git seal,
or Phase 1F closure. The implementation conversation must not stage, commit, push, tag, or create
a PR. A fresh read-only reviewer must evaluate the frozen candidate, followed only after PASS by
a third independent Git-sealing task.

The historical implementation conversation did not reach the target verdict because its
no-VisualEngineer-operation condition could not be asserted. The later controller-authorized
continuation started from the corrected 35-path candidate baseline and used an explicit
`CREATIVEDEPLOY_API_PROXY_TARGET` with a not-port-8000 guard, new API/Vite/audit-proxy ports, an
isolated PostgreSQL schema, isolated private storage, and program-generated fixtures. It performed
no VisualEngineer request, check, log, container, database, or file operation. Its complete
browser journey and exact cleanup passed. This continuation does not erase or relabel the
historical deviation; it supplies new, independently isolated evidence.

Phase 1D remains `COMPLETE`; Phase 1E-1 and Phase 1E-2 remain `CLOSED`. Phase 1F does not alter
their migrations, data contracts, or review history.

## Authorized capability

1. Freeze ADR-0006 and the RegionSet physical data dictionary.
2. Add one child Alembic Revision with RegionSet, Region, Vertex, and Review persistence.
3. Implement deterministic ppm conversion, simple-Polygon validation, summaries, overlap warnings,
   and canonical SHA-256 geometry fingerprints.
4. Implement owner-scoped Repository/Service/API for workbench bootstrap, immutable draft save,
   history/detail, immutable submit, append-only review, and review history.
5. Bind every snapshot to server-derived current READY ImageSet and primary-image facts.
6. Derive stale state after fingerprint, primary source, or readiness changes.
7. Enforce Project-scoped idempotency, optimistic base versions, PostgreSQL locking, unique version
   allocation, and safe 409 conflicts.
8. Add the `/paintpilot/projects/:projectId/regions` SVG workspace and Project Detail entry.
9. Cover automated geometry, database, API, browser contract, accessibility, and responsive gates.
10. Run a program-generated real-browser journey through Vite, FastAPI, PostgreSQL, and private
    local storage, then exactly clean its isolated runtime state.
11. Freeze candidate evidence and a reproducible manifest without changing Git history.
12. Add the architecture-decided exact historical-fork endpoint, current-snapshot optimistic
    precondition, exact-source geometry copy, current-image rebinding, and serialized
    Project-scoped idempotency.
13. Separate frontend `current` and `viewed` snapshot targets, make history explicitly read-only,
    fail closed while historical detail is unresolved, and expose only exact fork or
    return-to-current from history.

## Explicit exclusions

- AI, LLM, vision, OCR, RAG, Agent, embedding, auto-segmentation, auto-labeling, or suggestions;
- image-quality scoring, automated viewpoint recognition, or rights verification;
- lighting, color, Cel Shading advice, materials, inventory, or PaintPlan;
- PaintProject workflow-state changes or automatic transitions;
- external storage, public/signed URLs, deletion, real authentication, or RBAC;
- VisualEngineer files, containers, ports, volumes, databases, or processes.

## Acceptance matrix

| Area | Acceptance |
| --- | --- |
| Migration | One child Revision; catalog/round-trip/check pass; historical hashes unchanged |
| Data | Composite Owner/Project/source/ancestry FKs, structural constraints, append-only triggers |
| Geometry | Bounds, counts, repeats, zero edges, area, self-intersection, bbox, overlap warning |
| Versioning | Save and submit create new immutable snapshots; later snapshots derive superseded |
| Snapshot target | Historical fork copies exact source geometry but supersedes exact current |
| Source binding | Exact READY ImageSet fingerprint, current primary ID, dimensions; server owned |
| Stale | Fingerprint/primary/readiness changes preserve history and disable submit/review |
| Review | Current submitted only; approved or reasoned changes requested; append-only |
| Owner | Missing and other-owner use the same safe 404 |
| Idempotency | Exact replay succeeds; changed payload/key scope conflicts safely |
| Concurrency | One winner per base; source mutation races cannot validate an old source as current |
| UI | Human SVG draw/edit, history, stale recovery, responsive, no prohibited wording/features |
| Browser | Program-generated images; restart, conflict, approval, stale, owner 404, three viewports |
| Cleanup | Isolated schema/storage/listeners removed; public business counts restored |

## Candidate handoff

The candidate evidence file records the exact command ledger and browser observations. The
manifest records every candidate path, status, byte size, and SHA-256 plus aggregate patch and
porcelain hashes. The candidate is ready for a fresh independent focused read-only review, but is
not independently approved, ready for sealing, Git-sealed, commit-ready, production-ready, or
phase-closed. Neither document authorizes committing the work.
