# CreativeDeploy architecture

[首页](../README.md) · [Evidence index](evidence-index.md)

CreativeDeploy deliberately shares a governance platform while keeping PaintPilot and Arcana as separate product domains. The shared layer owns identity, authorization, provider policy, accounting, audit, retrieval provenance, persistence, and recovery boundaries; it does not force Arcana through PaintPilot image-domain contracts.

```mermaid
flowchart TB
  browser["Browser"] --> web["Bilingual Web\nReact + Vite"]
  web --> api["FastAPI API"]
  api --> governance["Platform governance"]
  governance --> auth["Auth / Project policy"]
  governance --> registry["Provider registry / encrypted BYOK"]
  governance --> ledger["Invocation / accounting / audit"]
  governance --> rag["RAG / citation / provenance"]
  api --> paint["PaintPilot"]
  paint --> images["Private images\nImageSet / RegionSet"]
  paint --> plan["Structured Paint Plan\nhuman review / approval"]
  plan --> glm5v["GLM-5V-Turbo\nlive proof completed"]
  api --> arcana["Arcana"]
  arcana --> deck["78-card local knowledge"]
  arcana --> analysis["Question analysis\nposition-aware retrieval\ncross-card signals"]
  analysis --> glm52["GLM-5.2\nlive proof completed"]
  api --> durable["PostgreSQL + private object storage"]
```

## Product boundaries

**PaintPilot** treats source images, roles, region geometry, knowledge, generated plans, and human decisions as versioned workflow facts. Private objects remain private, and a plan cannot claim a citation that is not bound to real, accessible retrieved context.

**Arcana** persists the draw as immutable facts: three ordered cards, their positions and orientations. A user-owned Journal is separate from the system interpretation. The retrieval/synthesis path is question-aware, compact, citation-backed, and schema-governed; a future tendency is not represented as a guaranteed outcome.

## Governed Provider invocation flow

```mermaid
sequenceDiagram
  participant U as Authorized user
  participant P as API / policy
  participant L as Durable ledger
  participant V as Provider
  participant R as Result store

  U->>P: requested invocation
  P->>P: authorization and project policy
  P->>L: reserve budget
  L->>L: durable resource claim
  L->>L: dispatch marker
  L->>V: permitted dispatch
  V-->>P: provider response
  P->>P: validate schema and citation/provenance
  P->>R: persist result or safe failure
  P->>L: accounting and audit outcome
```

The order matters: policy, reservation, durable claim, and dispatch state make egress/accounting outcomes explainable under retries and concurrency. Safe metadata may preserve narrow diagnostic facts; raw credentials, private images, and raw provider payloads are not public evidence.

## Local-first demonstration boundary

The Portfolio path runs with synthetic/Fixture data, isolated local services, **Live OFF**, and **Provider calls = 0**. It demonstrates the same product surfaces without asking an evaluator to supply a key or expose personal images. A public deployment would introduce a different set of identity, storage, secret-management, operational, and incident-response responsibilities; it is intentionally not implied by this repository.
