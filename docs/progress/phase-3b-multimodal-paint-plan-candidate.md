# Phase 3B Multimodal Paint Plan — Staging DR Remediation Candidate

Status: `PENDING_ONE_TINY_INDEPENDENT_STAGING_DR_REREVIEW`

This is a local remediation freeze, not an independent rereview PASS, merge,
release, deployment, or authorization to activate a real Provider.

## Baseline and scope

- Repository: `/Users/danke/Developer/CreativeDeploy`
- Branch: `codex/phase-3b-multimodal-paint-plan`
- Approved baseline: `638c46e5cd463009f465bf2e5373aa646eed14ad`
- Alembic single head: `3b01a1c2d3e4`
- Original frozen Candidate: `d98ee7f4ec2826c38f1f9efd5674610494f03ee3`
  (50 paths; aggregate SHA-256
  `480c51aaf871db5d1b29c46e2deaa4a9d265745ae632e90aaa8c575c8bbbabff`)
- Candidate paths are limited to the approved Phase 3B implementation, Paint
  Plan UX/mobile remediation, locale contract, focused tests, and this Phase
  3B evidence. The exact path and SHA-256 record is
  `docs/progress/phase-3b-candidate-manifest.txt`.

## Independent review boundary and remediation

Independent review passed every other Phase 3B boundary and left one open
finding: staging backup/restore still required Alembic `3a04fab2e7a5` and the
39-table Phase 3A inventory. This remediation advances the exact symmetric
backup/manifest/restore contract to `3b01a1c2d3e4` and all 44 persistent
application tables, including:

- `provider_pricing_snapshots`;
- `prompt_template_definitions`;
- `paint_plans`;
- `paint_plan_region_instructions`; and
- `paint_plan_review_events`.

The synthetic staging fixture restored two linked Paint Plan revisions, four
region instructions, two review events, the deterministic prompt and disabled
pricing snapshots, three private image objects, and their project,
readiness/Region, Invocation/Attempt, Provider/Model, prompt/pricing, lineage,
and review relationships. Exact-retry and object/manifest/checksum tamper
refusals also passed.

Fresh remediation gates:

- focused backup/restore tests: 32 passed;
- `make staging-drill ENV_FILE=.env.example`: PASS at Alembic
  `3b01a1c2d3e4`, 44 tables, and three objects;
- changed-Python Ruff and format checks, API mypy, shell syntax, whitespace,
  and six-path diff secret scan: PASS; and
- the one authorized `make check ENV_FILE=.env.example`: exit 0, with 495
  unit, 66 PostgreSQL integration, and 203 Web tests passing.

The following prior evidence remains reusable and was not reopened:

- focused backend PASS;
- PostgreSQL integration PASS;
- fixture no-network/E2E PASS;
- locale, idempotency, and provenance focused PASS;
- final frontend mobile-overflow remediation: focused tests, lint, typecheck,
  and build PASS;
- high-confidence secret scan PASS; and
- `PHASE_3B_VISUAL_ACCEPTANCE_PASS`: user acceptance of the Paint Plan
  Workbench on Desktop and at 390 px.

The frontend is unchanged, so the existing user
`PHASE_3B_VISUAL_ACCEPTANCE_PASS` remains valid.

## Provider boundary

Real Provider execution is source-gated OFF. This candidate used no real key,
no real Provider network call, and no billable call. No real-provider
activation, push, pull request, independent review, or deployment is included.

## Result

The remediation commit identity, exact paths, aggregate SHA-256, full Candidate
identity, and clean Git state are recorded after the single local commit is
created. One new independent Sol reviewer must inspect only the staging DR
delta; no final independent rereview PASS is claimed here.
