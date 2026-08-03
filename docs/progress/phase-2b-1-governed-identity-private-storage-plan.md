# Phase 2B-1 — Governed Identity, Authorization, and Private Storage Plan

Status: IMPLEMENTED_PENDING_INDEPENDENT_REVIEW<br>
Date: 2026-07-31<br>
Repository: `<repository-root>`

## Verified Baseline

- Branch: `main`
- HEAD: `771b53914f51245d6c62c569e40ddd061ae7ec6e`
- Tree: `26f395ef6c217bc7f5f997309c12893618ce5634`
- Commit count: `22`
- Worktree at implementation start: clean
- Alembic head: `7f3a2b9c4d1e`
- Current development data contract: nine business tables plus `alembic_version`
- Current storage contract: private local filesystem, development/test only

The actual baseline matched the supplied expectation. The similarly named Documents
checkout was not used; implementation used the authoritative Developer repository.
Phase 2A-1 was not reopened or re-reviewed.

## Objective

Deliver one maximum safe implementation batch containing provider-neutral OIDC,
server-side Owner/reviewer authorization, private S3-compatible object storage, distinct
database roles, real local/CI smoke, frontend closure, migration, tests, and evidence.
Leave an unstaged and uncommitted Candidate for a new independent reviewer.

## Facts

- Existing ownership was a Principal string on PaintProject and all authorization was
  owner-scoped.
- Existing ImageAsset metadata already recorded provider, key, size, checksum, content
  type/format, rights, role, history, and project linkage.
- Existing storage used a provider-neutral service boundary and safe publication receipt,
  but only a local adapter existed.
- Existing artifact ran production-built Web/API with PostgreSQL but deliberately refused
  Demo identity and local storage in production.
- The user-owned `.env` contained a partial legacy PostgreSQL group and was not suitable
  for the active Compose database. It was preserved unchanged.

## Inferences

- Stable internal user IDs can replace OIDC project-owner strings without rewriting
  sealed historical data because only newly OIDC-created projects use them in this Phase.
- Owner is best derived from the existing project owner field; adding redundant Owner
  membership rows would create two authorization sources.
- Reviewer permission must compose with existing workflow rules, not create a new
  workflow role transition.
- S3 support can reuse ImageAsset metadata and receipts; only the allowed provider
  vocabulary and adapter are required.

## Unknowns Reserved for Independent Review or Production Selection

- Real enterprise IdP, tenant/client ownership, key rotation, and claims mapping.
- Real S3-compatible provider, bucket/IAM ownership, TLS/domain, secret manager,
  backup/restore, monitoring, retention, and incident ownership.
- Independent reproduction of the Candidate and its hashes.

## Workstreams

1. Add OIDC discovery/code exchange/PKCE/claims validation and a synthetic local provider.
2. Add internal users, external identities, one-time login flows, opaque sessions, and
   CSRF.
3. Add project reviewer membership and server-side authorization across project, image,
   readiness, and region operations without changing workflow state.
4. Add private S3 storage, API-only streaming, exact failure handling, and non-destructive
   legacy copy.
5. Add migrator/runtime role provisioning and production-style Compose separation.
6. Add login/session/logout, access states, reviewer management, and role-appropriate UI.
7. Add focused, canonical, migration, artifact, supply-chain, isolation, and real-browser
   evidence with unique RUN_ID cleanup.
8. Freeze an unstaged Candidate manifest and hand off to an independent reviewer.

## Stop Conditions

Stop rather than expand scope if completion requires a paid account, real secret, public
or signed URL, destructive deletion, retention policy, irreversible migration, major
workflow-state change, weakened Owner/reviewer isolation, unowned cleanup, external
Candidate mutation, or unverifiable core auth/storage/browser closure.

None of those stop conditions was reached.

## Completion Boundary

Implementation completion is
`PHASE_2B_1_IMPLEMENTED_READY_FOR_INDEPENDENT_REVIEW`. It is not independent
approval, Git sealing, a production-ready claim, Phase 2B-2 authorization, or AI/OCR/
Agent/RAG authorization.
