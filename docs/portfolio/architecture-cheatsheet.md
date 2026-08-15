# Architecture interview cheat sheet

## Why repository-local RAG?

It keeps the corpus, versioning, access boundary, provenance and test fixtures in the same governed system as the product. It is a deliberate fit for small, reviewable domain knowledge; it is not a claim that this is already a web-scale retrieval platform.

## Why BYOK?

Provider ownership and access are explicit rather than hidden in a shared global key. The boundary uses encrypted credentials, grants and policy; demo mode does not ask evaluators for a credential.

## Why cited RAG?

A fluent answer is not sufficient where a user must inspect why a recommendation appeared. Citations are tied to the persisted retrieved context, so a source cannot be invented or borrowed from another run.

## Why a durable pre-egress claim?

In-process locking cannot explain concurrent retries or a process restart. A durable claim coordinates eligibility before a paid/external dispatch and makes accounting outcomes traceable.

## Why local-first demo?

It removes API-key, cost, private-data and public-infrastructure friction for an evaluator. Local-first is a complete Portfolio delivery choice, not a disguised public deployment.

## Why only Zhipu is live-verified?

The project makes a bounded factual claim: GLM-5V-Turbo and GLM-5.2 have independently completed proof. Additional providers require their own authorization, transport validation, accounting behavior and evidence; no generic “multi-provider live” claim is made.

## Why two product spaces?

They test whether the platform abstractions are reusable. PaintPilot stresses private images and human workflow; Arcana stresses question-aware context and immutable reflection data. Sharing governance without sharing product semantics is the point.

## Why not multi-agent?

Neither product needed autonomous delegation to solve its core user task. Adding agents would increase control and evaluation complexity without improving the demonstrated workflow.

## Why not public deployment by default?

Public exposure changes the threat model: managed identity, secrets, storage/IAM, abuse controls, retention, monitoring, incident response, domains and operational ownership all need real decisions. Those are outside this Portfolio release.

## How would this evolve at 10× usage?

First measure queueing, provider latency/outcomes, budget contention, retrieval quality and recovery time. Then isolate provider workers, introduce durable job orchestration and controlled rate limits, scale read paths/corpus indexing, add managed secret/identity/storage operations, and define explicit SLO/RPO/RTO ownership. None of those future steps are claimed as already implemented.
