# Phase 2A-1 — Local Production Spine and UX Truth Plan

Status: IMPLEMENTED_PENDING_INDEPENDENT_REVIEW<br>
Baseline: `main` at `f0563dc1c5800f9d1ec35efaac77d169ab08c6da`<br>
Baseline tree: `6a3a4b6d8ca2a73f4e62c4948f39239535e9949b`<br>
Expected progress after independent review and Git sealing: approximately 85–86%

## Objective

Close the known UX-truth and Polygon-rendering gaps and add a repeatable local
production-style build, proxy, smoke, configuration, and CI spine. This phase
does not claim production readiness or authorize a later product phase.

## In Scope

- Region document-title state, Projects navigation state, current product copy,
  mobile guidance, and actionable upload-validation feedback.
- Human-authored paint/exclude Polygon projection over the private primary
  image, including selected state, zoom, fit, resize, current, and historical
  views.
- Locked multi-stage API and Web artifacts, non-root runtime users, a
  production server, same-origin NGINX proxy, SPA fallback, cache policy,
  security headers, host restrictions, health/readiness, and request limits.
- A clearly labelled `LOCAL_PRODUCTION_STYLE_SMOKE` /
  `NOT_REAL_PRODUCTION` profile with isolated database and local storage.
- A single local database configuration source, drift detection, production
  fail-closed behavior, a single CI workflow, reproducible secret and
  vulnerability scans, evidence, and a frozen Candidate manifest.

## Out of Scope

- OIDC/OAuth, User/Membership/Role models, real reviewer separation, external
  object storage, public or signed URLs, real domain/TLS, deletion/retention,
  external cloud SDKs, AI/LLM/OCR/Agent/RAG/Embedding, automatic segmentation,
  Light/Color/PaintPlan, migrations, or ORM changes.
- Git staging, commit, push, tag, PR creation, independent approval, or Git
  sealing.
- Any operation in VisualEngineer.

## Workstreams

1. Re-verify the sealed Git, migration, phase, and PostgreSQL baseline.
2. Correct UX truth and add focused frontend coverage.
3. Close the Polygon visual coordinate and presentation path without changing
   the RegionSet contract.
4. Make local configuration precedence explicit and reject drift, partial
   settings, unsafe production adapters, and wildcard hosts.
5. Build the API, Web/NGINX, Compose smoke, security headers, and deterministic
   artifact validation.
6. Add one lockfile-driven CI workflow and supply-chain gates.
7. Run focused, full, migration, artifact, and real-browser validation.
8. Clean only Phase 2A-1-owned synthetic resources, freeze the Candidate, and
   hand it to a fresh read-only reviewer.

## Stop Conditions

Stop without expanding scope if the baseline changes, a migration or contract
change is required, a normal browser still shows a real unresolved blank
Polygon canvas, production fail-closed must be weakened, an unexplained secret
enters an artifact, cleanup cannot be proven, or external auth/storage/AI is
required.

## Completion Boundary

Implementation completion means all gates and exact cleanup pass, staged files
remain zero, and Candidate evidence and hashes are frozen. It is not approval,
sealing, production deployment, or authorization for auth, storage, or AI.
