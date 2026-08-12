# Arcana Core Proof Slice — local-first evidence

Status: implementation complete; user visual acceptance and a newly authorized canonical rerun remain.

## Identity

- Branch: `codex/arcana-core-proof-slice`
- Baseline: `de256778555896c04377ccee4f8730fdb4ca39e1`
- Candidate SHA: intentionally not created before user visual acceptance
- Migration: `4c01a2b3c4d5` (additive child of `3b01a1c2d3e4`)
- Deployment: local-first; no public deployment required

## Product and reuse map

```text
CreativeDeploy account / session / locale / CSRF / database / Provider provenance
├── PaintPilot — governed image-first paint planning
└── Arcana — private three-card reading and reflection Journal
```

Arcana reuses the platform identity, API security middleware, single SQLAlchemy Base, Alembic chain, bilingual resource system, and `fixture_local` provenance. It does not force Tarot through PaintPilot-specific ImageSet, RegionSet, Project Grant, or PaintPlan contracts.

## Domain

```text
TarotCardDefinition (78) ─┐
TarotSpreadDefinition (1) ├─> TarotReading ─> TarotReadingCard (exactly 3)
                          │        ├─> TarotInterpretationRevision (system/Fixture)
                          │        └─> TarotJournalEntry (user-authored)
                          └────────────> local private Share Preview projection
```

The saved draw is immutable. Journal updates do not replace cards or the system interpretation. Every Reading and Journal lookup is server-side owner scoped.

## Demonstrated slice

1. Open the CreativeDeploy product selector.
2. Choose Arcana and enter one question/focus.
3. Keep the fixed Past / Present / Future spread and draw once.
4. Inspect three distinct cards and their upright/reversed orientation.
5. Generate the deterministic, schema-valid local Fixture interpretation.
6. Add a personal interpretation and private notes; save to Journal.
7. Reopen the reading from history and open the private local share preview.

Real Provider request / network inference / API key / external cost: **ZERO**.

## Engineering evidence

- Deck seed integrity: 78 unique cards; 22 Major and 56 Minor; bilingual upright/reversed knowledge.
- Real PostgreSQL isolated-schema API E2E: passed (catalog, draw, no duplicate, no redraw, interpretation, Journal, history, share preview, owner isolation).
- API unit suite: 498 tests passed; full integration run reached 65 passed before two pre-existing image-set tests exposed a host/container clock-skew defect in their state-preparation helper.
- The helper now uses `GREATEST(now(), created_at)`; both affected PostgreSQL tests pass (2/2). The user-authorized canonical rerun allowance was already consumed, so no third canonical was run and no canonical PASS is claimed.
- Frontend suite: 204 tests passed after Arcana integration; post-fix Arcana flow, TypeScript, and production build also pass.
- Browser integration found and fixed the inherited OIDC `return_to` allowlist so `/arcana` remains same-origin and returns to Arcana after login; its focused backend OIDC suite passes (30/30) and focused frontend routes pass (17/17).
- Real local browser flow completed with synthetic `Arcana Visual Owner`: question, persisted three-card draw, deterministic interpretation, Journal save, history reopen, and private share preview.
- Responsive structural check: Reading, Journal history, and share preview each reported `innerWidth=390`, `documentWidth=390`, and no horizontal overflow. This is engineering evidence only, not user visual acceptance.
- Dedicated local database: `creativedeploy_arcana`, head `4c01a2b3c4d5`, 78 cards and one spread.
- Diff secret scan: passed across 38 changed files.

## Screenshot checklist for user acceptance

- CreativeDeploy product selector
- Arcana landing / question entry
- Three-card draw and orientation
- Structured interpretation
- Journal editor and saved state
- History and private share card
- 390px draw, interpretation, Journal, and actions

No screenshot or browser visual PASS is claimed in this evidence record.

## Known limitations

- Exactly one deck and one three-card spread.
- Fixture interpretation is deterministic and local; GLM-5.2 transport, live Zhipu verification, Shared RAG, and citations are future packages.
- Share preview is local presentation only; there is no public URL or hosting backend.
- Default historical local database retains the unmerged Phase 3C revision. Arcana validation uses a separate non-destructive local database so that evidence remains untouched.
