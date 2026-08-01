# Phase 2B-2 — Staging Operations and Production Hardening Plan

Status: IMPLEMENTED_READY_FOR_INDEPENDENT_REVIEW<br>
Date: 2026-08-01<br>
Repository: `/Users/danke/Developer/CreativeDeploy`

## Verified Baseline

- Branch: `main`
- HEAD: `511e42ecb2adccc55e75cb4d801181206b1b337a`
- Tree: `05420278f8da5478be39832466fc60609c215313`
- Commit count: `23`
- Authorized Candidate takeover: 21 tracked modified, 17 untracked, staged 0
- Alembic head: `2b1c4d5e6f70`
- Existing production artifact gate: PASS at baseline
- Existing staging capability: none beyond the HTTP-only local artifact

The expected sealed baseline matched exactly. The existing 38-path Candidate
was explicitly accepted, snapshotted, and found wholly attributable to Phase
2B-2. Work used the authoritative Developer repository; the similarly named
Documents checkout was not used. Phase 2B-1 was not reopened or re-reviewed.

## Objective

Deliver one safe uncommitted Candidate containing a provider-neutral local/CI
staging topology, TLS and exact URL contract, file-secret injection, complete
readiness, secret-safe observability, coordinated PostgreSQL/private-object
backup and temporary restore, deploy/rollback procedures, canonical CI and
browser evidence, and exact attempt cleanup.

## Workstreams

1. Build a loopback-only TLS proxy, production Web/API, migration job,
   PostgreSQL, private MinIO, synthetic OIDC, internal networks, health checks,
   and ordered role/migration startup.
2. Enforce exact origin/host/callback/CSRF/proxy facts, secure cookies, HSTS on
   HTTPS only, deep-link routing, and provider-neutral certificate files.
3. Add strict direct-or-file Secret loading and distinct read-only mounts for
   every runtime, migrator, OIDC, S3, and TLS credential.
4. Add bounded database/storage/identity readiness, JSON logs, request
   correlation, safe startup/shutdown events, and fault diagnosis.
5. Add quiesced consistent backup, complete manifests, checksummed private
   objects, temporary-only verified restore, dry-run, and exact retries.
6. Prove the chain using unit/integration/Web/migration/artifact/supply-chain
   gates, real HTTPS browser actions, restart/failure recovery, and a complete
   source-to-new-environment recovery drill.
7. Freeze a deterministic unstaged manifest and hand the Candidate to a new
   independent reviewer without staging or committing it.

## Stop Conditions

Stop instead of expanding scope if work requires a real/paid account, real
secret or domain, public deployment, non-temporary destructive restore,
irreversible migration, public/signed URL, retention deletion, AI capability,
or an unprovable database/object consistency boundary.

The initial in-app browser reached a stop condition at
`ERR_CERT_AUTHORITY_INVALID`. Explicit continuation authorization permitted a
fresh dedicated Chrome process/profile to trust only the current synthetic
certificate's SPKI. The complete real HTTPS journey then passed. Certificate
validation was never globally disabled, and macOS Keychain/system trust was
not modified.

## Completion Boundary

Implementation is complete at
`PHASE_2B_2_IMPLEMENTED_READY_FOR_INDEPENDENT_REVIEW`. This is not independent
approval, Git sealing, production readiness, or authorization for another
phase. The exact unstaged Candidate must next be reviewed by a fresh independent
security/operations reviewer.
