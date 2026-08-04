# Phase 3A Architecture Freeze Candidate

## Verdict

`PHASE_3A_BYOK_PROVIDER_ARCHITECTURE_FREEZE_READY_FOR_FOCUSED_REVIEW`

This is a local documentation Candidate only. It freezes a Phase 3A BYOK multi-provider foundation design for independent focused review. It is not implementation, a Provider integration, a real-key test, a migration, approval for Arcana/RAG, production readiness, a push, or a pull request.

## Repository and baseline identity

| Item | Verified value |
| --- | --- |
| Repository root | `/Users/danke/Developer/CreativeDeploy` |
| Repository | `dankk0220abc-prog/creative-deploy` |
| Start branch | `main` |
| Required and local HEAD | `09a6dad97e67f3ebab3a3c331049eab2bb33b835` |
| Required and local tree | `957bfa9d1d6178e0c5a0f101c829eea1f1831acf` |
| Subject | `feat(demo): add public demo and interview baseline` |
| `origin/main` / remote ref / GitHub main | each resolved to `09a6dad97e67f3ebab3a3c331049eab2bb33b835` before branch creation |
| Preflight worktree/index/untracked | clean |
| Preflight operation state | no merge, rebase, cherry-pick, revert, or bisect state |
| Candidate branch | `design/phase-3a-byok-provider-foundation-20260804` |

The preflight was fail-closed and did not use reset, clean, stash, rebase, or overwrite operations.

## Incremental investigation

Read paths were limited to the direct Phase 3A dependency chain:

- `apps/api/src/creativedeploy_api/core/{config.py,secret_files.py,logging.py,principal.py}`
- `apps/api/src/creativedeploy_api/api/{dependencies.py,error_handlers.py,router.py}` and `api/routes/paint_projects.py`
- `apps/api/src/creativedeploy_api/{auth,services,repositories,schemas,db/models}` identity, PaintProject, idempotency, state-event, and error surfaces
- `apps/api/migrations/versions/` revision declarations and `apps/api/pyproject.toml`
- focused existing test names in `apps/api/tests/{unit,integration}` for configuration/redaction, OIDC, ownership, idempotency, and migration coverage
- `apps/web/src/{components/AppShell.tsx,router/AppRoutes.tsx,api/paintProjects.ts,auth/AuthContext.tsx,i18n/resources.ts}` and `apps/web/package.json`
- `AGENTS.md`, `CONTRIBUTING.md`, `Makefile`, and document path/tooling discovery.

### Facts, inferences, and unknowns

Facts: the repository has durable internal users/OIDC mapping, opaque sessions/CSRF, project owner/reviewer access, bounded safe API errors, correlation IDs, idempotency records, immutable business-event patterns, `SecretStr` and hardened file-secret inputs, structured allowlisted logs, bilingual authenticated routes, and Alembic head `2b1c4d5e6f70`.

Inferences: new credential ownership must use `UserAccount.id`; Phase 3A audit must be separate from PaintPilot state transitions; project policy constrains user-owned credentials and cannot convert them into project property.

Unknowns: no generic encrypted field/KMS adapter, AI Provider adapter/catalog, cost/quota service, custom-provider SSRF defense, or approved audit-retention/production key-management decision exists in the read set.

## Reusable platform capabilities and PaintPilot boundaries

The Candidate reuses current identity, authorization, secret-file, logging, error-envelope, idempotency, audit-discipline, i18n, and focused-test patterns. It retains `PaintProject`, `ImageAsset`, `ImageSetReadinessReview`, `RegionSet`, `Region`, `RegionVertex`, and human review/workflow semantics as PaintPilot-specific objects. No current business object is renamed into a false generic platform type.

## Frozen decisions

The paired architecture document freezes:

- registry-only `ProviderDefinition` and `CapabilityDefinition`, with no Provider key in the registry;
- temporary request-lifetime keys versus explicit encrypted saved `CredentialRecord` rows;
- a user-owned credential plus separate, revocable project grant; no ownership transfer;
- dynamic Provider-scoped model metadata, unknown/unsupported states, and non-enum model IDs;
- user defaults and restrictive project policy with selection order task → project → user → explicit system default;
- no automatic Provider/credential/model fallback and no fabricated replacement for a stale/retired/unknown model;
- a small adapter contract that preserves Provider differences and normalized safe errors;
- separate invocation request, actual attempts, and bounded immutable usage audit;
- envelope-encryption port without choosing a real cloud KMS; and
- future custom Provider egress as a separate SSRF gate, not an implied safe capability.

## Next implementation boundary and recommended model use

After independent PASS, one maximum-safe Sol implementation batch may add only the registry, fake/fixture adapter, temporary-key contract, encryption interface/test seam, user defaults, owner-governed policy/grants, fake invocation/audit models, focused settings UI, and focused tests. It must not enable a real Provider, consume a real key, create costs, make an outbound custom Provider request, add fallback, RAG, embedding/reranking, Paint Plan, Arcana, public deployment, production KMS, subscriptions, or billing.

The recommended model upgrade point is the first implementation batch: use Sol for the cryptographic/authorization/migration/API/UI boundary and again for an independent focused review. Do not delegate a real Provider adapter to a lower-assurance implementation pass.

## Evidence intentionally not repeated

This task did not reread Phase 2E demo lifecycle, public hardening, the full README, full CI/security/supply-chain evidence, unrelated PaintPilot region business details, VisualEngineer, browser flows, Docker, product tests, migrations, staging, backup/restore, or full CI. Existing evidence was not reclassified or restated as new Phase 3A implementation evidence.

## Documentation Candidate

The task handoff records the resulting branch, commit SHA, tree, parent, exact two paths, and clean worktree state. A committed file cannot safely contain its own final commit SHA/tree because adding those values changes both; this Candidate records the immutable parent and exact intended path set.

| Item | Value |
| --- | --- |
| Branch | `design/phase-3a-byok-provider-foundation-20260804` |
| Commit SHA / tree | Recorded after commit in the task handoff |
| Parent | `09a6dad97e67f3ebab3a3c331049eab2bb33b835` |
| Exact paths | `docs/architecture/phase-3a-byok-multi-provider-foundation.md`; `docs/progress/phase-3a-architecture-freeze-candidate.md` |
| Post-commit worktree | Must be clean; verified in the task handoff |

## Exact next action

Run one independent Sol focused review of the Phase 3A architecture Candidate, limited to Credential security, user/project isolation, SSRF, cost control, Provider abstraction, audit correctness and Migration risk. Do not reread the full repository or run product test suites. After PASS, start one maximum-safe implementation batch with Sol.
