# Phase 3B — Multimodal Paint Plan Foundation

Status: implementation contract for the first safe Phase 3B batch
Baseline: `638c46e5cd463009f465bf2e5373aa646eed14ad`
Authority: local implementation and validation only; no live Provider execution, push, or PR

## 1. Recommended contract

Phase 3B adds one project-level, revisioned Paint Plan workflow on top of the
Phase 3A invocation ledger. The offline fixture is the only executable Provider.
OpenAI is registered as the first real multimodal Provider contract, with the
single pinned model `gpt-5.4-mini-2026-03-17` and the single fixed endpoint
`https://api.openai.com/v1/responses`, but live execution is blocked by an
immutable code-level authorization boundary in this phase.

The executable business flow is:

1. resolve one exact, current, human-ready ImageSet fingerprint from server-owned
   `ImageAsset` rows;
2. resolve one exact, approved, non-stale RegionSet snapshot;
3. resolve an allowed Provider/model and, for project calls, an encrypted saved
   credential with an active project Grant;
4. estimate usage and cost before admission;
5. run the deterministic fixture through the existing Invocation, Attempt,
   reservation, usage, cost, event, and audit path;
6. validate the returned document against the strict Paint Plan schema and the
   exact RegionSet;
7. persist an immutable Paint Plan revision and its typed per-region instructions;
8. append human submit/approve/reject events against an exact revision.

There is no client-supplied artifact identity in the accepted generation
contract. The service builds canonical identities from database rows and rejects
any stale, missing, ineligible, mismatched, or rights-unconfirmed source.

## 2. FACT

- Phase 3A persists Provider, model, credential, Grant, policy, budget,
  Invocation, Attempt, reservation, usage, cost, event, and audit records.
- Its runtime is still fixture-specific: adapter types, invocation family,
  Provider/model resolution, and `FIXTURE_CREDITS` checks are not a live-ready
  polymorphic boundary.
- `ArtifactIdentity` exists, but Phase 3A accepts it from the caller and does not
  reconcile it with ImageAsset or RegionSet persistence.
- ImageSet is a derived view of the current role-bound ImageAssets plus the latest
  append-only readiness review. It is not a separately selectable table.
- ImageAssets already carry immutable ID, role, version, SHA-256, media type,
  byte length, dimensions, upload-validation, and rights-attestation facts.
- RegionSet is an immutable snapshot. Its `stable_region_key` is the durable
  semantic identifier for an instruction; `Region.id` and `RegionSet.id` bind the
  instruction to one exact geometry revision.
- The current quality boundary is deterministic upload validation plus explicit
  human ImageSet readiness. There is no separate automated quality score, so the
  API must not claim one.
- No physical Paint Plan model or API exists before this batch.

## 3. INFERENCE

- A browser-side join of ImageSet, RegionSet, AI policy, Grant, and budget cannot
  prove one atomic generation snapshot. The backend must expose a project-level
  Paint Plan workbench and repeat every readiness check under generation locks.
- A temporary credential cannot satisfy the existing active-Grant rule because
  it has no persistent `CredentialRecord` identity. Project Paint Plan generation
  therefore accepts saved credentials only. Temporary credentials remain
  projectless validation inputs; an ephemeral-Grant design is out of scope.
- `UserProviderPreference` is a default source, not an authorization rule.
  Explicit request-time Provider/model choices may differ from those defaults but
  must still pass model status, capability, project allowlist, credential Grant,
  and budget checks.
- Persisting a generated revision after an already-terminal Invocation is an
  intentional transaction boundary. If strict output validation or plan
  persistence fails, the Invocation remains a truthful audit record; retrying the
  same command does not make another Provider call.

## 4. Provider and model contract

### 4.1 Provider-neutral boundary

The application boundary separates:

- request preparation: canonical multimodal input and strict response schema;
- Provider adapter: Provider-specific headers, body, response, usage, and error
  normalization;
- transport: one fixed destination policy, redirect prohibition, bounded timeouts,
  response-size limits, and redacted diagnostics;
- orchestration: Phase 3A admission, dispatch, retry, terminalization, and audit.

Adapters never receive a caller-controlled URL. Provider error bodies, request
bodies, image bytes, and credentials are never persisted or logged.

This batch implements and tests the adapter/request/normalization contracts,
cost estimator, fixed endpoint policy, and an unconditionally blocked transport.
It does not connect the OpenAI adapter to Phase 3A dispatch, credential decryption,
private object reads, or live settlement. Those activation steps require a new
reviewed source change; they are not enabled by changing configuration.

### 4.2 OpenAI live-ready registration

- Provider key: `openai`
- API family: Responses API
- fixed origin: `https://api.openai.com`
- fixed path: `/v1/responses`
- model key: `gpt-5.4-mini`
- pinned upstream model ID: `gpt-5.4-mini-2026-03-17`
- required capabilities: text input, image input, strict structured output
- image detail: `high`
- structured response: JSON Schema with strict mode

Only the fixed HTTPS origin/path and default port are representable. Redirects,
proxy environment inheritance, arbitrary hosts, custom paths, userinfo, query
strings, fragments, and alternate ports are rejected. A future connected
transport must additionally pin resolved public addresses for the connection and
verify the connected peer; DNS or peer ambiguity fails closed.

### 4.3 Non-bypassable live gate

`LIVE_PROVIDER_EXECUTION_AUTHORIZED` is a source constant set to `False`. It has
no environment-variable override. Orchestration checks it before credential
decryption, dispatch persistence, or socket creation, and the only real-Provider
transport present in this phase refuses every execution unconditionally.

Consequently, registering a Provider, enabling a Provider row, saving a
credential, granting it to a project, changing a project policy, or setting any
environment variable cannot trigger a real request in Phase 3B. Future execution
requires a separately reviewed source change plus explicit authorization.

## 5. Governed multimodal input

The server-generated canonical input contains:

- project ID and owner predicate;
- current ImageSet fingerprint and readiness review ID;
- every included current ImageAsset: ID, role, version, SHA-256, declared media
  type, byte length, width, height, upload validation result, rights status,
  rights-attestation version, and intended usage;
- exact RegionSet ID, version, geometry fingerprint, source ImageSet fingerprint,
  and effective approved lifecycle;
- each Region ID, stable region key, kind, normalized label, z-index, opacity,
  notes, bounding box, and normalized vertices;
- prompt template ID/version/hash and Paint Plan schema version;
- bounded user intent/style notes after normalization.

Generation requires the derived ImageSet to be `ready`, every included image to
be current, accepted, object-verified, and rights-confirmed, and the RegionSet to
be current, effectively approved, and bound to that exact ImageSet fingerprint.
An `exclude` region is included as a protected constraint but must never produce a
paint instruction.

The fixture consumes canonical metadata only. A future live adapter may open the
same private stored objects immediately before request construction and encode
them in-memory; raw bytes and data URLs are never added to canonical payloads,
database rows, audit details, exceptions, or logs.

## 6. Paint Plan schema

Schema ID: `paint-plan.v1`

A valid plan contains:

- a concise title and bounded overall approach;
- a non-empty ordered instruction array with exactly one instruction for every
  `paint` Region and none for `exclude` Regions;
- each instruction bound to `region_id` and `stable_region_key`;
- target color, preparation, base-coat, layer, edge, lighting, and material
  guidance;
- bounded warnings and a confidence value in integer parts-per-million;
- bounded global safety notes.

Validation rejects unknown keys, missing fields, duplicate Region IDs or stable
keys, unknown Regions, excluded Regions, absent paint Regions, excessive list or
text lengths, invalid confidence bounds, and schema-version mismatch. Provider
output is parsed as data, never rendered as trusted HTML and never executed.

The schema, prompt, and fixture response are deterministic and versioned. A
schema or prompt change creates a new immutable version; it does not rewrite old
provenance.

## 7. Persistence and lifecycle

### 7.1 Immutable revision content and provenance

`paint_plans` stores one revision whose content and provenance are immutable:

- project/owner scope, lineage ID, monotonically increasing project version,
  and optional parent revision;
- revision kind: `generated`, `edited`, or `regenerated`;
- lifecycle: `generated`, `edited`, `under_review`, `approved`, `rejected`, or
  `superseded`;
- exact image and RegionSet provenance;
- Invocation, Provider, model, prompt, and schema provenance;
- normalized global content and a canonical SHA-256 content hash;
- actor and timestamp facts.

`paint_plan_region_instructions` stores typed immutable child instructions with
composite foreign keys to the exact Region/RegionSet/project/owner scope.

The source Invocation identifies the requesting user and request timestamp. A
`paint_plan_generation` Invocation's request-side identity, requester, project,
Provider/model/credential selection, capabilities, idempotency, confirmation,
budget, canonical `safe_payload`, and creation time cannot be updated after
insertion; only terminal settlement fields may advance. The API projects that
immutable requester/time and the exact generation-time image identities,
versions, hashes, media types, sizes, dimensions, and content handles rather
than substituting current ImageAssets.

`paint_plan_review_events` is append-only and binds submit, approve, and reject
to one exact Plan revision. The database permits only the explicit lifecycle
transitions below; every provenance, version, content, and actor column remains
immutable, and deletes are rejected.

### 7.2 Revision semantics

- Generate creates a `generated` revision.
- Edit creates a new `edited` revision and marks the previous current revision
  superseded in the same transaction.
- Submit appends an exact-revision submit event and yields `under_review`.
- Approve/reject appends an exact-revision decision.
- Regenerate creates a new `regenerated` revision and a new lineage with a new
  Invocation, links it to the prior current revision as parent, and supersedes
  that prior revision.
- Any edit or regeneration necessarily creates a different revision, so an old
  approval never applies to new content.
- If the current ImageSet fingerprint or RegionSet changes, historical Plan rows
  remain readable but are reported stale and never reported as currently
  approved.

At most one non-superseded current Plan exists per project. Optimistic expected
revision IDs and command idempotency keys are mandatory for mutations.

### 7.3 Permissions

- Project owner: preview, generate, edit, submit, regenerate, read history.
- Active reviewer: read workbench/history and approve or reject an exact
  `under_review` revision.
- Owner cannot approve their own submitted revision. UI affordances are derived
  from server-returned allowed actions; API authorization is authoritative.

## 8. API contract

Project-scoped routes:

- `GET /paint-projects/{project_id}/paint-plans/workbench`
- `POST /paint-projects/{project_id}/paint-plans/preview`
- `POST /paint-projects/{project_id}/paint-plans/generate`
- `GET /paint-projects/{project_id}/paint-plans`
- `GET /paint-projects/{project_id}/paint-plans/{plan_id}`
- `POST /paint-projects/{project_id}/paint-plans/{plan_id}/edits`
- `POST /paint-projects/{project_id}/paint-plans/{plan_id}/submit`
- `POST /paint-projects/{project_id}/paint-plans/{plan_id}/approve`
- `POST /paint-projects/{project_id}/paint-plans/{plan_id}/reject`
- `POST /paint-projects/{project_id}/paint-plans/{plan_id}/regenerate`

Every mutation requires an `Idempotency-Key`; a reused key with changed canonical
input fails closed. Same-input replay returns the same immutable Plan resource and
never repeats Provider execution, while current/stale/effective-lifecycle,
approval-validity, review, and allowed-action fields are re-projected against the
current governed source so an old snapshot cannot misrepresent current approval.
Safe errors expose stable categories and allowed recovery actions, never secrets,
Provider response bodies, private storage keys, raw prompts, or image bytes.

## 9. Usage, cost, and retry

Fixture invocations retain `FIXTURE_CREDITS` and the existing Phase 3A budget
ledger. The OpenAI model stores an immutable USD pricing snapshot. Preview
reports a conservative upper bound derived from normalized prompt limits, image
dimensions/detail rules, and maximum output tokens. Unknown usage or cost is
represented as unavailable, never zero.

A future live call must have a matching-currency user and project budget,
reservation, and dispatch record before egress. Retry remains bounded by the
existing Invocation/Attempt policy; ambiguous upstream outcomes are never
silently replayed. Output-schema failure is normalized and auditable, with retry
only when the existing retry policy explicitly permits it.

## 10. Frontend contract

Route: `/paintpilot/projects/:projectId/paint-plans`

The page is a project workbench, not a Provider console. It presents:

1. the current protected reference-image snapshot;
2. Region confirmation and excluded-area summary;
3. model and saved-credential selection;
4. preview/admission and generation;
5. structured per-region plan reading and editing;
6. submit, reviewer approval/rejection, and immutable history.

Provider/model IDs, Invocation/Attempt IDs, hashes, prompt/schema versions, and
usage details are progressively disclosed. All user-facing text is present in
`zh-CN` and `en-US`. The established image-first workbench, token system, error
patterns, route-local state, AbortController loading, exact response validators,
and 390 px responsive floor are retained.

## 11. PLAN

1. add the provider-neutral request/response/transport contracts and blocked live
   adapter with request-normalization tests;
2. add one additive Alembic revision for real-provider representability, prompt
   metadata, Paint Plan revisions/instructions/reviews, constraints, and seed data;
3. add strict schemas, repository/service/API dependencies, server-side governed
   source resolution, lifecycle, idempotency, and safe audit events;
4. extend the fixture adapter with deterministic multi-region `paint-plan.v1`
   output while preserving the Phase 3A invocation path;
5. add the project workbench/client/UI and bilingual content;
6. run focused backend, migration, no-network fixture, frontend, Ruff/mypy,
   whitespace, and diff-scoped secret checks before exactly one canonical check;
7. leave the local service running for desktop and 390 px user visual acceptance.

## 12. Validation evidence

- The first canonical attempt passed all 488 unit tests, then stopped at 62
  integration passes and four failures whose assertions still expected Alembic
  head `3a04fab2e7a5`.
- After those four head assertions were synchronized to `3b01a1c2d3e4`, the
  next focused failure showed that the current-head `BUSINESS_TABLES` contract
  still froze the complete Phase 3A schema.
- The remediation now separates the historical Phase 3A 39-table contract,
  the current Phase 3B 44-table contract, and this exact five-table delta:
  `provider_pricing_snapshots`, `prompt_template_definitions`, `paint_plans`,
  `paint_plan_region_instructions`, and `paint_plan_review_events`.
- Current-head exact table, CHECK, foreign-key, primary-key, unique, index,
  explicit-identifier, and ORM-to-Migration expectations were synchronized;
  the historical `3a04fab2e7a5` table inventory remains exactly 39 tables.
- Focused metadata validation passed: 63 direct unit tests and four migration
  integration nodes, with zero failures. Ruff, format, whitespace, and the
  48-file diff-scoped high-confidence secret scan also passed.
- The single authorized second canonical `make check ENV_FILE=.env.example`
  exited 0: 488 unit, 66 integration, and 201 frontend tests passed together
  with API/Web lint, format, type checks, and the Web build.
- This metadata remediation changed no migration, ORM, or other production
  code. Real-Provider execution remains source-gated OFF; no real key, live
  Provider network request, or real usage/cost occurred.
- Final focused backend, PostgreSQL integration, fixture no-network/E2E, and
  locale/idempotency/provenance validation subsequently passed. The current
  canonical result is `492` unit, `66` integration, and `203` Web tests, with
  API/Web lint, format, type checks, and the Web build passing.
- The final frontend mobile-overflow remediation passed its focused tests,
  lint, typecheck, and build checks. The localized v2 Fixture plan and the
  `en-US`/`zh-CN` locale contract are covered by that final evidence.
- `PHASE_3B_VISUAL_ACCEPTANCE_PASS`: the user formally accepted the final
  Paint Plan Workbench at Desktop and 390 px. This is visual acceptance only;
  it does not enable a real Provider.

## 13. UNKNOWN / intentionally deferred

- No live request, credential validation against OpenAI, DNS/peer behavior, real
  response compatibility, real usage, or real cost is evidenced in this phase.
- The connected OpenAI dispatch path is intentionally not wired. Live activation
  still requires reviewed orchestration for short-lived credential decryption,
  private image-byte loading, dispatch/timeout/cancellation semantics, normalized
  failure settlement, and peer-verifying egress before the source gate may change.
- No automated image-quality score exists; human readiness remains the declared
  quality gate.
- Temporary project credentials and ephemeral Grants are not defined.
- Connected-transport peer verification and operational egress policy require a
  separately authorized, independently reviewed activation batch.
- Desktop and 390 px user visual acceptance is complete
  (`PHASE_3B_VISUAL_ACCEPTANCE_PASS`). Candidate sealing remains a separate
  local Git-freeze step and does not authorize independent review or real
  Provider activation.
