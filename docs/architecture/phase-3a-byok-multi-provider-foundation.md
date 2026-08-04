# Phase 3A — BYOK Multi-Provider Multimodal Foundation

Status: architecture-freeze Candidate for focused independent review

Scope: Phase 3A design only; no Provider, credential, model call, migration, API, or UI is implemented by this document.

## 1. Purpose and boundary

Phase 3A defines a reusable, user-owned BYOK foundation for CreativeDeploy products. PaintPilot is the first product space; Arcana, RAG, embeddings, reranking, paint-plan generation, real paid Provider traffic, production KMS, billing, and public deployment are outside this phase.

The design supports a uniform control plane without asserting that Providers have identical semantics. It freezes ownership, authorization, credential handling, selection, audit, error, and data boundaries so a later implementation can add a fake Provider first and real adapters only under separate authorization.

Normative words in this document are intentional: **MUST** is required for implementation, **MUST NOT** is prohibited, and **MAY** is an explicitly optional future extension.

## 2. Current-state findings

### Facts

The following are verified from the Phase 3A incremental read set:

| Existing capability | Reuse decision |
| --- | --- |
| `UserAccount`, `ExternalIdentity`, opaque `AuthSession`, and OIDC Authorization Code + PKCE | Reuse `UserAccount.id` as the durable credential and preference owner. Do not key new records by mutable OIDC claims. |
| `PrincipalContext` and request-scoped `AsyncSession` / UUID request ID | Reuse as the API authentication and correlation boundary. |
| Owner/reviewer membership resolution in `SqlAlchemyIdentityRepository.resolve_project_access` | Reuse to authorize a PaintPilot project policy and project-scoped invocation visibility. Owner-only policy mutation is the initial rule. |
| Owner-scoped resource queries deliberately return the same 404 for missing and inaccessible project resources | Reuse this non-disclosure behavior for project-policy and project-invocation endpoints. |
| `CommandIdempotencyRecord` with scope + idempotency key + canonical payload hash | Reuse the pattern, not the existing command type, for state-changing credential, policy, and invocation commands. |
| Append-only `StateTransitionEvent` and immutable Image/Region history | Reuse the append-only audit discipline; do not overload PaintPilot workflow events for platform invocation audit. |
| `Settings` uses `SecretStr`; direct-or-`*_FILE` inputs are mutually exclusive; secret files reject symlinks, unsafe modes, multiline data, and unstable identity | Reuse this configuration convention for an encryption root-key provider abstraction. It is not a credential-store implementation. |
| Safe API error envelope (`error_code`, category, request ID, retryability, allowed actions, safe details), CSRF, structured allowlisted logs | Reuse and extend safely for Provider errors. Provider bodies, headers, and credentials are not safe details. |
| React/Vite shell has authenticated routes, bilingual `i18n` resources, focused API clients, controlled empty/error states, and mobile workbench layouts | Reuse these patterns; add settings as product workbench pages, not a marketing dashboard. |
| Alembic lineage is `a10d3d8dab38 → 5ed9906e7d33 → d4c8a1f7b2e9 → 7f3a2b9c4d1e → 2b1c4d5e6f70` | Phase 3A must be a new child revision after `2b1c4d5e6f70`; no historical migration may be changed. |

Focused tests already demonstrate secret-file refusal/redaction, OIDC secret non-disclosure, owner isolation, project-scoped idempotency, append-only facts, migrations, and bilingual UI parity. They are reusable test patterns, not evidence that BYOK is implemented.

### Inferences

1. `UserAccount.id` is the correct durable human ownership key because OIDC session resolution already returns it and external issuer/subject mapping is server-side.
2. Existing `PaintProject.owner_principal_id` is a historical principal string, whereas membership uses `user_accounts.id`. New platform records should use `owner_user_id` and project access must validate both current access and an explicit grant relation.
3. A separate platform audit stream is needed. Reusing `StateTransitionEvent` would conflate PaintPilot workflow transitions with a cross-product Provider attempt and create invalid state semantics.

### Unknowns and stop conditions

No encryption library, KMS integration, generic sensitive-column type, Provider adapter, Provider catalog, background worker, quota service, or platform settings route exists today. Key-management ownership, retention periods, exact billing currency source, Provider legal terms, and a production custom-Provider network egress design are unknown.

Implementation MUST stop before enabling saved credentials or real remote invocation if an envelope-key source, redaction proof, outbound URL safety gate, authorization model, budget enforcement, or audit retention decision is absent. A missing/expired model catalog is not permission to guess a replacement.

## 3. Product and platform boundaries

Platform objects are reusable across CreativeDeploy product spaces. `product_space_key` identifies the caller (initially `paintpilot`) and is not a disguised replacement for business aggregates.

The following remain PaintPilot-only and MUST NOT be renamed or generalized in this slice: `PaintProject`, its owner/member authorization semantics, `ImageAsset`, `ImageSetReadinessReview`, `RegionSet`, `Region`, `RegionVertex`, human readiness/review facts, and PaintPilot workflow states. A future Vision task may reference immutable `ImageAsset` IDs through an artifact-reference policy, but it does not own, mutate, or reinterpret image/region history.

## 4. Frozen domain model

All identifiers below are UUIDs unless named as a normalized string. Provider keys, capability keys, model IDs, and statuses are application-validated strings, not PostgreSQL enums, so a catalog can evolve without a database enum migration.

### 4.1 ProviderDefinition and CapabilityDefinition

`ProviderDefinition` is platform-owned registry data, never a credential container.

| Field / rule | Contract |
| --- | --- |
| `provider_key` | Stable normalized key; unique and never repurposed. Initial registry candidates: `zhipu`, `deepseek`, `doubao`, `qwen`, `openai_compatible_custom`; they are definitions only, not configured live integrations. |
| `display_name`, `adapter_type`, `enabled` | Stable UI value, adapter dispatch key, and server-controlled admission state. Disabling prevents new use without erasing audit. |
| `base_url_policy` | `provider_managed`, `allowlisted_custom`, or `not_applicable`; no user URL is accepted unless the adapter and egress gate explicitly support it. |
| `authentication_scheme` | Metadata such as `bearer_api_key` or a future declared scheme. Never includes a secret value. |
| `supported_capabilities`, `model_catalog_mode`, `allow_custom_model_id` | Declared baseline, catalog behavior (`bundled`, `remote_refresh`, `user_supplied`), and explicit custom-ID permission. |
| timeout/retry | Maximum allowed timeout and retry policy. Invocation request values may only narrow them. Retries are recorded attempts, never hidden adapter behavior. |

`CapabilityDefinition` defines the stable keys `text_generation`, `vision_understanding`, `structured_output`, `tool_calling`, `embedding`, `reranking`, `streaming`, `long_context`, and `image_generation`, with display labels and lifecycle status. A model's effective capability is a conservative intersection of Provider catalog facts, explicit user/model metadata, adapter support, and any successful runtime validation. Model-name heuristics are prohibited.

### 4.2 CredentialRecord and project grant

`CredentialRecord` is user-owned and has exactly two input modes:

| Mode | Contract |
| --- | --- |
| Temporary use | Raw key is accepted only in the HTTPS request body, kept in request-local memory, passed directly to the selected adapter, excluded from logs/traces/errors/audit/browser storage, and released when the request completes. It has no database row, no browser echo, and cannot be referenced by a later request. |
| Encrypted saved credential | Created only after an explicit user save confirmation. The service envelope-encrypts the plaintext before persistence; the API returns only a generated ID, alias, Provider, last four or a non-reversible fingerprint, status, timestamps, and validation summary. |

Persisted fields are `id`, `owner_user_id`, `provider_key`, `encrypted_payload`, `encryption_version`, `key_fingerprint`, `last_four`, `alias`, `status`, `created_at`, `updated_at`, `revoked_at`, `last_successful_validation_at`, and `revision`. `encrypted_payload` is opaque binary/ciphertext plus non-secret encryption metadata; it MUST NOT be JSON containing a plaintext key. `key_fingerprint` is a keyed, rotation-aware HMAC-style fingerprint of normalized key bytes, not an unsalted digest suitable for offline guessing. `last_four` is presentation-only and optional when a scheme has no meaningful suffix.

`CredentialProjectGrant` is a separate relation: `credential_id`, `paint_project_id`, `granted_by_owner_user_id`, `created_at`, `revoked_at`, and `revision`. It does not transfer ownership. A project may use a saved credential only when its owner still owns the credential, the credential is active, a live grant exists, the caller has authorized project access, and the project policy allows that credential. Initial Slice mutation is owner-only; reviewer use is not enabled merely by reviewer visibility.

Revoke is irreversible for use, not physical erasure: set `revoked_at`, `status=revoked`, increment revision, deny all future decryption/invocation, retain minimal non-secret audit facts, and remove active grants transactionally. Replace creates a new credential row and revokes the old row; it never overwrites ciphertext in place.

### 4.3 Encryption boundary

Define a replaceable server-side port:

```text
EnvelopeCipher.encrypt(plaintext, *, aad: CredentialAAD) -> EncryptedCredentialPayload
EnvelopeCipher.decrypt(payload, *, aad: CredentialAAD) -> SecretBytes
EnvelopeCipher.current_version() -> str
```

AAD MUST bind credential ID, owner user ID, provider key, and encryption version. The first implementation may use a test-only/local envelope-key provider injected from a strictly validated secret source; it MUST NOT choose, name, or hard-code a cloud KMS. The root/master key MUST come from a separately governed runtime secret source and MUST NOT sit in the same ordinary configuration/database field as ciphertext. Rotation writes new ciphertext with a new version; decryption supports only approved historical versions until every active row is rewrapped. Plaintext lifetime is limited to the narrow validation/invocation call and must not cross task queues, ORM reprs, exception messages, response snapshots, or log context.

### 4.4 ModelDefinition and selections

`ModelDefinition` stores Provider-scoped catalog facts, not a global database enum: `id`, `provider_key`, `model_id`, `display_name`, `catalog_source`, `catalog_fresh_at`, `status` (`active`, `disabled`, `unknown`, `unsupported`, `retired`), `context_window`, capability overrides, `supports_structured_output`, `supports_vision`, optional pricing metadata/currency/unit, raw-metadata reference only if redacted and size-bounded, and `revision`. Uniqueness is `(provider_key, model_id)`. A user-entered model ID is represented as a selection value plus `catalog_status=unknown`, not silently materialized as a trusted catalog model. Unknown or unsupported models cannot be invoked until adapter validation makes their required capability explicit.

`UserProviderPreference` has one row per user and stores nullable `default_provider_key`, `default_model_id`, `default_credential_id`, bounded timeout, streaming preference, cost-warning threshold/currency, `updated_at`, and `revision`. Null means inherit; it does not mean an arbitrary system choice.

`ProjectModelPolicy` has one row per PaintProject: allowed Provider/capability/credential sets represented by child allowlist tables, nullable default Provider/model/credential reference, a decimal per-invocation budget ceiling/currency, `allow_manual_model_id`, `allow_fallback` (default false), `require_paid_call_confirmation`, `updated_by_user_id`, `updated_at`, and `revision`. A project policy constrains rather than grants: it cannot make a non-owner credential owned by the project or override a revoked credential.

### 4.5 InvocationRequest, InvocationAttempt, and UsageAudit

An `InvocationRequest` represents what a human or product asked for. An `InvocationAttempt` represents one actual adapter attempt, including retry or explicitly confirmed fallback. A request has zero or more attempts; attempts are append-only once started.

Required request fields: `id`, `product_space_key`, nullable `paint_project_id`, `requested_by_user_id`, `requested_capabilities`, requested Provider/model/credential references or temporary-credential indicator, `request_id`, scope-specific idempotency key and payload hash, timeout, budget snapshot, confirmation snapshot, prompt/version reference, input/output artifact references, state, cancellation request time, created/updated timestamps, and revision.

Required attempt fields: `id`, `invocation_request_id`, `attempt_number`, resolved Provider/model/credential reference (never plaintext), adapter version, retry/fallback lineage, start/end timestamps, terminal status, normalized error category, Provider raw error code and request ID when safe, rate-limit metadata, latency, normalized usage, estimated/actual cost with currency or explicit `unknown`, cancellation outcome, and immutable artifact references. `attempt_number` is unique per request. The first Slice records contract-level attempts but performs only fake/fixture execution.

`UsageAudit` is a user/project-visible, append-only projection or table with a reference to the immutable request/attempt. It contains actor, product space, authorized project, Provider/model identifiers, credential alias/fingerprint reference (not payload), capability set, status, safe error code, usage/cost state, timestamps, request/correlation IDs, and redacted artifact/prompt references. It MUST NOT contain API keys, Authorization headers, connection strings, ungoverned complete private prompts, raw Provider request/response bodies, or unbounded error text.

## 5. Selection, validation, and fallback rules

Selection is resolved in this strict order:

1. one-time task selection;
2. Project Model Policy;
3. UserProviderPreference;
4. a system configuration default that is explicitly enabled for the product space.

At every layer, a concrete value overrides only the same value and is still constrained by all higher-scope allowlists, credential ownership/grants, Provider state, model catalog state, capability requirements, confirmation requirements, budget, and adapter policy. A higher precedence missing field inherits; an explicit deny never inherits around the denial.

Before an attempt, the resolver MUST return either a complete `ResolvedInvocationPlan` or a structured safe error. It MUST NOT:

- auto-switch credentials because a model/Provider changes;
- switch to another user's credential;
- fallback to any Provider by default;
- move from free/unknown cost to a paid model silently;
- invent a replacement for a retired, stale, missing, unknown, or unsupported model;
- attempt a Provider when required capabilities are not proven.

Fallback is disabled unless both Project Model Policy and the one-time invocation explicitly authorize it. Each cost-increasing or Provider-changing fallback requires human confirmation for the exact fallback target, credential reference, and budget snapshot. It produces a distinct `InvocationAttempt` with `fallback_decision=confirmed`; no adapter may conceal it as an internal retry. A retry retains the same resolved Provider, model, and credential and is bounded by policy.

## 6. Provider adapter contract and error model

The adapter boundary is intentionally minimal:

```text
validate_credential(secret, context) -> CredentialValidation
list_models(context) -> ProviderModelCatalog
resolve_capabilities(model, context) -> CapabilityResolution
invoke_text(plan, secret, input) -> InvocationResult
invoke_vision(plan, secret, input) -> InvocationResult
invoke_structured(plan, secret, input) -> InvocationResult
stream(plan, secret, input) -> StreamHandle
normalize_usage(raw) -> NormalizedUsage
normalize_error(raw) -> NormalizedProviderError
```

An adapter declares which operations it implements. Calling an absent operation yields `capability_not_supported`; adapters must not simulate structured output, vision, streaming, or tool calling when the Provider does not provide the required behavior. Raw Provider error code, request ID, rate-limit metadata, usage granularity, vision input constraints, streaming semantics, and structured-output caveats are retained as bounded safe metadata where their disclosure is safe; the original response body and headers are not treated as audit data.

The canonical error codes are `authentication_failed`, `permission_denied`, `model_not_found`, `capability_not_supported`, `invalid_request`, `rate_limited`, `timeout`, `provider_unavailable`, `safety_rejected`, `quota_exceeded`, `cost_limit_exceeded`, `malformed_response`, `cancelled`, and `unknown_provider_error`. API responses map these into the existing safe error envelope with controlled `allowed_actions`; raw Provider text, credential material, and request bodies never reach `safe_details`.

## 7. Security, network, cost, and audit controls

### Credential and access control

- Secrets never enter frontend source, `localStorage`, `sessionStorage`, ordinary plaintext database columns, response snapshots, logs, traces, screenshots, Git, CI, or normal error details.
- The browser posts a temporary key only to a same-origin protected endpoint; the UI clears its controlled field after completion and never reloads it. Saved-key views return aliases/fingerprint/last four only.
- Credential list/detail/update/revoke/replace queries filter by `owner_user_id` in the repository, not by a client-supplied user ID. Project access checks are additional, not substitutes for credential ownership.
- Revocation and replacement must lock/recheck the credential before the provider attempt is admitted. Cancellation/revocation races resolve fail-closed: an attempt not already handed to a fake/Provider adapter is cancelled; no new retry/fallback may start.
- Validation is rate-limited per owner, credential, source/session, and Provider; validation records a safe status/time only. The first Slice fake validation must have no remote network path.

### Custom Provider egress / SSRF gate

The custom OpenAI-compatible definition is catalog-only in the first Slice. Any future URL field is rejected unless a dedicated outbound policy validates HTTPS scheme, explicit port policy, no embedded credentials, no redirects, no loopback, link-local, unspecified, multicast, metadata-service, or RFC1918/private destination; DNS resolution and the connected peer must be checked to resist rebinding; proxies and alternate IP forms must be governed. This is a future implementation Gate, not a claim that Python URL parsing alone prevents SSRF.

### Budget and cost control

Admission checks project capability/policy, credential status/grant, Provider/model enabled state, confirmation requirement, and a conservative per-invocation budget before an adapter call. No price is fabricated: missing pricing or usage produces `cost_status=unknown`, and a policy that requires a known ceiling must reject it. Actual normalized usage/cost is recorded after the attempt; estimated cost and actual cost are distinct values with source/time. Budget rejection has no Provider side effect. Rate limit/quota errors remain visible as normalized safe results.

### Immutable and privacy-bounded audit

Audits are append-only at the request/attempt boundary. Redacted prompt and artifact references must be versioned, access-checked, and size-bounded. If a complete private input is needed later, it belongs in a separate authorized encrypted artifact design, not JSON audit metadata. Audit query visibility is limited to the owner and authorized project role; credential value is never revealed by audit access.

## 8. Database and migration plan

### Suggested tables

| Layer | Tables | Isolation, constraints, and indexes |
| --- | --- | --- |
| Platform registry | `provider_definitions`, `capability_definitions`, `provider_capability_definitions`, `model_definitions` | Unique Provider key, unique capability key, unique `(provider_key, model_id)`; catalog freshness/status indexes. Registry edits are privileged configuration, not end-user writes. |
| User-owned secrets | `credential_records`, `credential_project_grants`, `user_provider_preferences` | FK credential owner to `user_accounts`; unique active alias per `(owner_user_id, provider_key)` if aliases are user-visible; encrypted payload non-null only while active; index `(owner_user_id, status, updated_at desc)` and active grant `(paint_project_id, credential_id)`. |
| Project policy | `project_model_policies`, provider/capability/credential allowlist children | One policy per `paint_projects.id`; policy mutator and revision fields; composite FKs/queries prevent a grant or selected credential from escaping owner/project scope. |
| Invocation/audit | `invocation_requests`, `invocation_attempts`, `usage_audits` | Request idempotency unique by `(scope_key, idempotency_key)` or a Phase-3-specific `CommandIdempotencyRecord` integration; unique `(invocation_request_id, attempt_number)`; indexes for owner/project/time/status and audit pagination. |

All creation/replacement/policy mutation uses named check/unique/FK constraints and a `revision` column for optimistic updates. Rows carrying immutable audit facts do not expose UPDATE/DELETE repository commands. `encrypted_payload` should use a binary/large-object-safe ciphertext column plus explicit non-secret version fields; it must not use `JSONB` to serialize a secret. `Numeric` amounts require explicit currency and scale; unknown is represented by null cost plus status, never zero.

### Migration order and risk

1. Add registry, credential, preference, and policy tables after `2b1c4d5e6f70` with no backfill and no real secret data.
2. Add invocation request/attempt/audit tables and indexes; introduce no PaintProject workflow mutation.
3. Add repository/service/API/UI in a later implementation commit after migration contract review.
4. Only after fake-provider/security review, separately consider a real adapter and remote egress gate.

Downgrade must drop Phase-3 tables in reverse FK order only when they contain no protected history or under a separately approved data-retention plan. Once real encrypted credentials or audit histories exist, destructive downgrade is an operational risk and must stop rather than silently discard user data. This Candidate creates no migration.

## 9. API contract plan

All routes live under `/api/v1`, require the existing Principal/CSRF boundary, emit the existing safe error envelope, set `Cache-Control: no-store` for credential-bearing responses, and return stable code/label/status fields required by bilingual UI. List endpoints use bounded `limit`/`offset` or a documented cursor and deterministic ordering. State-changing commands require an idempotency key and payload hash scope; retries replay only a safe stored response.

| Surface | Minimum endpoints / authorization |
| --- | --- |
| Catalog | `GET /providers`, `GET /providers/{provider_key}/models`, `GET /capabilities`; authenticated read, enabled/status/capabilities only. |
| Credentials | `POST /credentials/validate-temporary`, `POST /credentials`, `GET /credentials`, `POST /credentials/{id}/validate`, `POST /credentials/{id}/replace`, `POST /credentials/{id}/revoke`; owner only, no secret in response. Temporary validation cannot persist by accident. |
| User defaults | `GET/PUT /me/provider-preferences`; current user only, revision/If-Match conflict semantics. |
| Project policy | `GET/PUT /paint-projects/{id}/ai-model-policy`; readable only to authorized project users, mutation initially owner-only. Credential grants are owner-only command endpoints and only reference the owner's credential IDs. |
| Invocation | `POST /invocations/preview`, `POST /invocations`, `GET /invocations/{id}`, `POST /invocations/{id}/cancel`; preview resolves permissions/capabilities/budget without Provider side effect and says whether human confirmation is required. Create is idempotent; status visibility is owner/project scoped. |
| Audit | `GET /usage-audit` plus project-scoped filter; pagination, safe aggregates, and no secrets/raw inputs. |

The first Slice does not expose a generic raw prompt endpoint for a real Provider. Its fake invocation accepts a fixture-safe, bounded contract payload and returns a synthetic result marked as such.

## 10. Frontend information architecture

The UI remains an authenticated, image-first operational workbench. It must not introduce glowing AI decoration, gradient-heavy cards, fake metrics, or marketing navigation. Human visual acceptance is required before key pages are considered complete.

### Platform pages

| Page | Entry and contents |
| --- | --- |
| Models & Providers | Account/workspace navigation; Provider cards list adapter/capabilities/catalog freshness/availability and model list with unknown/unsupported states. No raw endpoint editing in Slice 1. |
| Credentials | Account settings; list alias/Provider/last four/fingerprint/status/last validation, add temporary test, explicit save toggle, warning/confirmation, replace, revoke, and history-safe empty/error states. The secret input is `type=password`, unprefilled, never copied to URL/storage, cleared after submit, and has no reveal-after-save behavior. |
| Usage & Audit | Account/project-filtered timeline with Provider/model/capability/status/cost state, safe request ID, date/page filters, empty state, and no raw prompt/key data. |
| Knowledge Base | Reserved navigation/data contract only for Phase 3C; no page implementation in Slice 1. |

### PaintPilot project pages

`AI Model Policy` belongs beside project settings/access rather than inside the image/region editor. It surfaces allowed Providers/capabilities, selected model/credential alias, manual-ID rule, per-call budget, fallback default, and paid-call confirmation. Later `Vision Analysis Task`, `Paint Plan Draft`, and `Cost and Audit` are project workbench views, but only policy and safe synthetic audit are in the first Slice.

Form errors must map the stable server error code to bilingual copy while preserving field focus and user-entered non-secret selections. On narrow screens, secret fields and destructive actions remain single-column, controls have explicit labels, status does not rely on color alone, provider/model identifiers wrap without truncating the value needed for a decision, and confirmation text names the exact Provider/model/credential alias/budget.

## 11. First implementation Slice

The maximum-safe implementation batch is:

1. provider and capability registries with only a Fake/Fixture adapter;
2. model/catalog metadata and conservative capability resolution;
3. temporary credential request contract and an envelope-encryption interface backed by a test/local fixture seam, with no real KMS choice;
4. user defaults, owner-governed project policy, credential grant relation, and safe preview resolver;
5. invocation request/attempt/audit base persistence with fake only execution;
6. focused Provider/Model and Credential settings UI plus bilingual labels and safe empty/error/confirmation states;
7. focused authorization, redaction, idempotency, migration, catalog, cost-admission, and fake-provider tests.

It explicitly excludes real paid Provider calls, real API keys, auto fallback, RAG, embeddings, reranking, Paint Plan, Arcana, public deployment, production KMS, subscriptions, billing, background execution, and any PaintPilot workflow change.

Sol implementation is required for this batch because it combines cryptographic-boundary code, multi-table authorization/migration work, API and frontend contracts, and adversarial security tests. A separate independent Sol reviewer must PASS the focused Candidate before that implementation starts.

## 12. Test and evidence strategy

Focused implementation tests must prove at least:

- direct/file root-key configuration rejects ambiguity, unsafe files, and redacts values;
- temporary credentials are absent from ORM/audit/log/error/response/browser-storage paths after success and failure;
- saved ciphertext cannot be returned or decrypted across users, revoked credentials fail closed, and project grants cannot transfer ownership;
- owner/reviewer/missing-project access has non-disclosing responses; policy and invocation queries remain project scoped;
- a model without a proven required capability returns a structured error with zero fake-provider calls;
- preview/budget/confirmation rejection produces zero provider side effect; unknown cost stays unknown;
- retries and explicit fallback form distinct attempts; automatic credential/Provider/model escalation is rejected;
- custom Provider URLs are rejected before any resolver/adapter network call;
- Provider raw errors, Authorization headers, and fake secrets are redacted from logs/audits/error details;
- migration upgrade/downgrade/catalog constraints and revision conflicts behave as designed; and
- frontend contract parsing, bilingual keys, secret-input clearing, no storage persistence, destructive confirmation, narrow viewport behavior, and safe error states pass.

No real key, Provider endpoint, paid token, browser screenshot containing a key, or external Provider test belongs in Phase 3A evidence.

## 13. Risks and explicit non-goals

Principal-string versus internal-user-ID ownership must be reviewed carefully at every bridge to `PaintProject`. Envelope cryptography, KMS selection, DNS rebinding defenses, pricing accuracy, Provider terms, audit retention, cancellation after a remote request starts, and use of private image input each require later implementation/operations decisions. The ability to display a Provider definition is not evidence that it is configured, safe to call, or affordable.

This document does not authorize an AI feature, a Provider selection, a cloud KMS, an outbound network exception, a migration, a secret, a paid API request, a public deployment, Arcana, RAG, retrieval, model training, billing, or changes to PaintPilot business objects/workflow.
