# Interview stories

Use these as talking points, not scripts. Each evidence reference is a place to navigate in the repository, not a claim of a public production deployment.

## 1. Why one platform instead of two projects?

**Question:** Why are PaintPilot and Arcana in the same repository?

**60 seconds:** They are intentionally different product domains, but both need identity, bilingual UI, durable history, provider governance, citations, auditability and local-first delivery. I shared those platform boundaries while keeping PaintPilot image workflow contracts separate from Arcana reading contracts. That let me validate reuse without flattening product meaning.

**Deep dive:** Start with the shared Web/API/security/database foundations, then contrast PaintPilot’s private images, ImageSet/RegionSet and human approvals with Arcana’s immutable draw and separate Journal. Explain that the extraction target was governance infrastructure, not a generic “AI product” schema.

**Trade-off:** A single codebase creates coupling pressure; explicit product modules and contracts prevent PaintPilot concepts leaking into Arcana.

**Evidence:** [architecture](../architecture.md), [Arcana case study](../case-studies/arcana.md).

**Likely follow-up:** What would you extract first if a third product arrived? What remains product-specific?

## 2. Private images and provenance in PaintPilot

**Question:** How did you stop a visually useful workflow from becoming a privacy or trust problem?

**60 seconds:** I treated private images and citations as governed resources. Images stay behind API authorization, and citations must bind to the retrieved context persisted for the exact plan. A valid-looking source/chunk pair is not enough.

**Deep dive:** Walk from ownership/project policy through ImageSet readiness, region-version selection, retrieval bundle, schema validation and human approval. Describe forged-pair, valid-subset, pair-splicing and malformed-snapshot regressions.

**Trade-off:** This is more work than attaching URLs to generated text, but it creates an inspectable review surface.

**Evidence:** [PaintPilot case study](../case-studies/paintpilot.md), [workflow contracts](../architecture/paintpilot-workflow-state-machine-v0.1.md).

**Likely follow-up:** Why not make images public signed URLs? What is a citation allowed to prove?

## 3. Arcana: generic tarot to question-aware RAG V2

**Question:** What product failure changed the Arcana architecture?

**60 seconds:** Feedback showed the first result only explained cards and did not answer the question. I changed the unit of retrieval from “card meaning” to question plus domain, temporal frame, card orientation and position, then added deterministic cross-card signals before compact cited synthesis.

**Deep dive:** Use the September/love regression example. Explain why a Future card yields a tendency rather than a guarantee and why deterministic local analysis makes the system inspectable.

**Trade-off:** More explicit analysis constrains generic model freedom, but produces more relevant and falsifiable output.

**Evidence:** [Arcana case study](../case-studies/arcana.md), `apps/api/tests/unit/test_arcana_question_aware_rag.py`.

**Likely follow-up:** Why repository-local RAG? How do you update corpus content safely?

## 4. Provider accounting, concurrency and fail-closed behavior

**Question:** What happens around a provider call besides sending HTTP?

**60 seconds:** Authorization, policy, budget reservation, durable resource claim and dispatch marker happen before dispatch; response validation, accounting and audit happen afterward. That is needed to distinguish a definite provider response from genuinely ambiguous transport state and to keep retries/concurrency from spending twice.

**Deep dive:** Follow the invocation diagram. Explain why `outcome_unknown` remains honest when dispatch certainty is unknown and why safe diagnostics exclude credential/raw payload content.

**Trade-off:** More lifecycle states and testing than a simple SDK call, in exchange for explainable cost and failure handling.

**Evidence:** [governed invocation flow](../architecture.md#governed-provider-invocation-flow), [evidence index](../evidence-index.md).

**Likely follow-up:** What metrics would you add? How would you reconcile an upstream outage?

## 5. DR: stale assumptions exposed by a full drill

**Question:** Describe a recovery issue that was not visible in ordinary tests.

**60 seconds:** A staging drill made stale migration assumptions visible. The correction kept the fail-closed verifier intact and aligned only the direct expectation with the actual Alembic head; the drill then verified a fresh isolated restore, exact retry and tamper/byte-mismatch refusal.

**Deep dive:** Describe why in-place restore is not the safe default, why relationship/count checks matter, and why HMAC protects a manifest beyond ordinary metadata checks.

**Trade-off:** Isolated recovery takes more setup but avoids treating a test database as a disposable production target.

**Evidence:** [staging operations](../runbooks/staging-operations.md), [evidence index](../evidence-index.md).

**Likely follow-up:** What would change for a real RPO/RTO commitment? Which step needs operator authorization?
