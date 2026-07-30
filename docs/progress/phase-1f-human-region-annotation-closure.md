# Phase 1F — Human-Governed Region Annotation and Review Closure

- `record_type`: `phase_1f_human_governed_region_annotation_and_review_closure`
- `phase`: `Phase 1F — Human-Governed Region Annotation and Review`
- `implementation_seal_commit`: `fdf1fd787b2cc0c5a4db3c1e72885df4fdf6ae1b`
- `final_independent_review_verdict`:
  `PHASE_1F_SNAPSHOT_TARGET_REMEDIATION_PASS_READY_FOR_SEALING`
- `candidate_manifest_sha256`:
  `9cb57f6a0d59976d814d9d5dd3a3ae0e8f1bfd1e67cbf3be18197161499c4fb4`
- `migration_revision`: `7f3a2b9c4d1e`
- `phase_status`: `CLOSED`
- `overall_project_progress`: `approximately_80_percent`
- `next_checkpoint`: `80_percent_overall_product_and_deployment_readiness_review`
- `next_phase`: `NOT_SELECTED`
- `next_phase_status`: `NOT_STARTED`
- `ai_integration`: `NOT_AUTHORIZED`

## Closure basis and timing

Phase 1F became `CLOSED` only after the exact 36-file candidate passed final independent review
and was sealed in the single implementation commit
`fdf1fd787b2cc0c5a4db3c1e72885df4fdf6ae1b`. This docs-only record is later than that seal. It
does not backdate approval, convert reviewer evidence into implementation evidence, or claim that
the candidate was approved before the independent verdict.

The seal preserves Revision `7f3a2b9c4d1e` as the sole child of `d4c8a1f7b2e9`. The Candidate
Manifest remains byte-identical at SHA-256
`9cb57f6a0d59976d814d9d5dd3a3ae0e8f1bfd1e67cbf3be18197161499c4fb4`.

## Preserved history

1. The initial Phase 1F implementation produced the human-governed Polygon, immutable RegionSet,
   exact-source lineage, append-only review, and SVG workbench candidate.
2. The first incorrect proxy request was classified as the environment-isolation
   `INVALID_ATTEMPT`. It is not counted as passing evidence and is not erased.
3. The independent reviewer's overly broad Docker Volume metadata query remains part of the review
   history. It is not repeated or rewritten as an authorized project-wide Docker inspection.
4. F-01 established that the UI could display historical v1 while an approval request actually
   targeted current v3. The original exact-target failure remains recorded.
5. F-02 established that the frontend incorrectly enforced a 4,096 total-vertex limit instead of
   the formal 8,192-vertex contract. The original boundary failure remains recorded.
6. The formal architecture decision introduced an exact historical-snapshot fork API with explicit
   current ID/version preconditions, `based_on` source lineage, and `supersedes` current lineage.
7. Historical read-only behavior and exact-target request/response/database identity were
   remediated without rewriting the earlier failures.
8. A final strict independent review returned
   `PHASE_1F_SNAPSHOT_TARGET_REMEDIATION_PASS_READY_FOR_SEALING`.
9. Phase 1F became `CLOSED` only after the implementation seal succeeded; passing tests,
   remediation, or the reviewer verdict alone did not close the phase.

## Phase-state matrix

| Phase | Current status | Seal or closure basis |
| --- | --- | --- |
| Phase 1D | `COMPLETE` | Previously closed Phase 1D records |
| Phase 1E-1 | `CLOSED` | Implementation seal `9b3b23ac3e1f056a73e3934d3da51b24aa7f671d` |
| Phase 1E-2 | `CLOSED` | Implementation seal `cc89aa246607f7c44b4639149a3b251b803d3a80` |
| Phase 1F | `CLOSED` | Final independent PASS plus implementation seal `fdf1fd787b2cc0c5a4db3c1e72885df4fdf6ae1b` |

## 80% checkpoint boundary

The project is recorded as approximately 80% complete. The next action is an overall product and
deployment readiness review, not an automatically selected product phase. The next product phase
is `NOT_SELECTED` and `NOT_STARTED`.

This checkpoint does not claim production readiness. AI remains `NOT_AUTHORIZED`; external object
storage remains `NOT_SELECTED`; public or signed URLs remain `NOT_AUTHORIZED`; deletion, real
authentication, light design, color design, and PaintPlan remain `NOT_IMPLEMENTED`. The configured
Demo Principal remains a development/test identity rather than a real multi-person approval
system.

No AI integration, external provider, production object storage, public URL, deletion capability,
real authentication, later product phase, push, tag, branch, or pull request is authorized or
created by this closure.
