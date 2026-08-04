# Phase 3A — BYOK Multi-Provider Multimodal Foundation

Status: security-contract-remediated architecture-freeze Candidate pending focused independent rereview

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

No encryption library, KMS integration, generic sensitive-column type, Provider adapter, Provider catalog, background worker, quota service, or platform settings route exists today. Production key-management ownership, retention duration, exact billing currency source, Provider legal terms, and the operations/allowlist ownership for a future real-Provider safe transport are unknown. Sections 4.3, 4.5, 4.6, 7, and 8 nevertheless freeze the First Slice implementation contracts and fail-closed boundaries rather than deferring those choices to implementation.

Implementation MUST stop before enabling saved credentials or real remote invocation if an envelope-key source, redaction proof, outbound URL safety gate, authorization model, budget enforcement, or audit retention decision is absent. A missing/expired model catalog is not permission to guess a replacement.

## 3. Product and platform boundaries

Platform objects are reusable across CreativeDeploy product spaces. `product_space` identifies the caller (initially `paintpilot`) and is not a disguised replacement for business aggregates.

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
| Temporary use | Raw key is accepted only in the HTTPS request body, kept in request-local memory, passed directly to the selected adapter after admission commits, excluded from logs/traces/errors/audit/browser storage, and destroyed when the synchronous request completes. It has no database row, no browser echo, and cannot be referenced by a later request. |
| Encrypted saved credential | Created only after explicit user save confirmation. The service completes the envelope-encryption contract in section 4.3 before persistence; the API returns only a generated ID, alias, Provider, last four or a non-reversible fingerprint, status, timestamps, and validation summary. |

Persisted identity and lifecycle fields are `id`, `owner_user_id`, `provider_key`, `key_fingerprint`, `last_four`, `alias`, `status`, `created_at`, `updated_at`, `revoked_at`, `replaced_at`, `replaces_credential_id`, `last_successful_validation_at`, and `revision`. The encryption fields are the explicit logical fields in section 4.3; they MUST NOT be hidden inside JSON or a plaintext-capable ordinary domain field. `status` is one of `active`, `revoked`, `replaced`, or `erased`. `key_fingerprint` is a keyed, rotation-aware HMAC-style fingerprint of normalized key bytes, not an unsalted digest suitable for offline guessing. `last_four` is presentation-only and optional when a scheme has no meaningful suffix.

`CredentialGrant` (stored as `credential_project_grants`) is a separate relation: `credential_id`, `project_id`, `granted_by_user_id`, `created_at`, `revoked_at`, and `revision`. It does not transfer ownership. A project may use a saved credential only when its owner still owns the credential, the credential is active, a live grant exists, the caller has current authorized project access, and the project policy allows that credential. First Slice mutation is owner-only; reviewer visibility alone does not grant use.

Revoke and replace are irreversible for the old credential. Both deny future admission, revoke active grants, and immediately cryptographically erase the old row by setting every ciphertext, wrapped-DEK, nonce, authentication-tag, algorithm, and encryption/AAD-version field to `NULL`. Minimal non-secret audit metadata and replacement lineage remain. Replace creates a new encrypted row and never overwrites the old ciphertext in place or transfers old grants.

### 4.3 Encryption boundary

Every saved credential uses a distinct envelope. The implementation MUST:

1. pre-generate the credential UUID;
2. obtain an independent 256-bit DEK from a CSPRNG;
3. obtain an independent, never-reused 96-bit data nonce from a CSPRNG;
4. encrypt the API key with `AES-256-GCM`, retaining and verifying its authentication tag;
5. wrap the DEK through the replaceable key-encryption port below using a distinct, never-reused 96-bit CSPRNG nonce and authenticated encryption; and
6. persist the complete envelope only after both authenticated operations succeed.

AES-CBC, ECB, encryption without authentication, nonce reuse, a shared DEK between credentials, and custom cryptographic constructions are prohibited. The database/domain contract exposes these logical fields:

| Field | Contract |
| --- | --- |
| `encryption_version` | Approved envelope/KEK version used to select decryption behavior; non-empty while active. |
| `data_algorithm` | Exactly `AES-256-GCM` in Phase 3A. |
| `ciphertext` | Encrypted API-key bytes, never plaintext or JSON. |
| `data_nonce` | Exactly 12 bytes and unique for every encryption under a DEK. |
| `data_authentication_tag` | Exactly 16 bytes and always verified before plaintext is returned. |
| `wrapped_dek` | Authenticated encrypted representation of the per-row DEK. |
| `wrap_algorithm` | Approved wrapping algorithm identifier; the fixture implementation uses `AES-256-GCM`. |
| `wrap_nonce` | Independent from `data_nonce`, exactly 12 bytes for the fixture wrapping algorithm, and never reused under a KEK. |
| `wrap_authentication_tag` | Exactly 16 bytes for fixture `AES-256-GCM` wrapping and always verified. |
| `aad_version` | Canonical AAD encoding version, initially `credential-aad-v1`. |

A standard library MAY return ciphertext and tag as one blob internally, but the domain and database contract still treats them as the two logical components above and validates both lengths. Enabling a future wrapping algorithm with different nonce/tag lengths requires an additive constraint update before use; it does not require replacing the credential business table.

`credential-aad-v1` is a stable length-prefixed binary tuple encoding: every variable-width item is encoded as a 32-bit unsigned big-endian byte length followed by its bytes; UUIDs use their fixed 16-byte representation; strings are normalized UTF-8 values. The data AAD tuple is, in order, `creativedeploy`, `credential-aad-v1`, `credential-secret`, `credential_id`, `owner_user_id`, `provider_key`, and `encryption_version`. The wrap AAD tuple uses the same encoding and identities with purpose `credential-dek`. Alias, last four, fingerprint, timestamps, and other mutable presentation metadata MUST NOT be required AAD fields.

The service reconstructs AAD from immutable columns, rejects any unsupported algorithm/version before decryption, verifies the wrap tag before releasing a DEK, and verifies the data tag before releasing the API key. Exchanging ciphertext, wrapped DEK, nonce/tag, encryption metadata, or immutable identity between credentials MUST fail authentication; no failure may fall back to plaintext, an old credential, another KEK, or another credential.

Define replaceable server-side ports:

```text
EnvelopeCipher.encrypt(plaintext, *, aad: CredentialAAD) -> EncryptedCredentialPayload
EnvelopeCipher.decrypt(payload, *, aad: CredentialAAD) -> SecretBytes
EnvelopeCipher.current_version() -> str

KeyEncryptionService.wrap_dek(dek, *, aad: CredentialWrapAAD) -> WrappedDEK
KeyEncryptionService.unwrap_dek(payload, *, aad: CredentialWrapAAD) -> SecretDEK
```

The KEK/master key is separated from database ciphertext. A future KMS replaces `KeyEncryptionService` without changing the credential table. First Slice may use only a fixture root-key provider in `development` or `test`, with the key supplied through a dedicated `CREDENTIAL_FIXTURE_ROOT_KEY_FILE` path setting. Direct plaintext environment-variable input and default keys are forbidden. Provisioning MUST generate this key independently from every other application secret as 32 CSPRNG bytes. The referenced file MUST be a regular, non-symlink file with owner-only permissions, stable identity during read, and exactly 32 bytes; missing files, wrong length or permissions, symlinks, unsafe sources, and read errors fail startup closed. `production` and `staging` MUST reject the fixture provider even if the file is present. The key and its bytes MUST NOT enter Git, CI logs, fixture output, exceptions, or browser-visible data.

Saved-credential creation is atomic:

1. pre-generate `credential_id` and canonical data/wrap AAD;
2. generate the DEK and both independent nonces, then complete data AEAD and DEK wrapping outside any database row;
3. only after every cryptographic operation succeeds, insert the active row in one database transaction;
4. require every active encryption field to be non-null and satisfy the algorithm-specific length checks; and
5. on encryption failure create no row; on database rollback destroy request-local plaintext and DEK and leave no partial record.

Plaintext and DEKs live only in narrow request-local secret buffers. Ordinary domain objects MUST redact or omit them from `repr`, serialization, copying, exception context, snapshots, logs, and task payloads. Rotation writes a new authenticated envelope under an approved version; decryption supports only explicitly approved historical versions until active rows are rewrapped.

### 4.4 ModelDefinition and selections

`ModelDefinition` stores Provider-scoped catalog facts, not a global database enum: `id`, `provider_key`, `model_id`, `display_name`, `catalog_source`, `catalog_fresh_at`, `status` (`active`, `disabled`, `unknown`, `unsupported`, `retired`), `context_window`, capability overrides, `supports_structured_output`, `supports_vision`, optional pricing metadata/currency/unit, raw-metadata reference only if redacted and size-bounded, and `revision`. Uniqueness is `(provider_key, model_id)`. A user-entered model ID is represented as a selection value plus `catalog_status=unknown`, not silently materialized as a trusted catalog model. Unknown or unsupported models cannot be invoked until adapter validation makes their required capability explicit.

`UserProviderPreference` has one row per user and stores `enabled`, nullable `default_provider_key`, `default_model_id`, `default_credential_id`, bounded timeout, streaming preference, cost-warning threshold/currency, `updated_at`, and `revision`. Null means inherit; it does not mean an arbitrary system choice.

`ProjectModelPolicy` has one row per PaintProject: `enabled`, allowed Provider/capability/credential sets represented by child allowlist tables, nullable default Provider/model/credential reference, per-invocation budget ceiling/currency, cumulative project budget-policy reference, `allow_unknown_cost` (default false), a non-zero `unknown_cost_reservation_minor_units` when that exception is enabled, `allow_manual_model_id`, `allow_fallback` (default false), `require_paid_call_confirmation`, `updated_by_user_id`, `updated_at`, and `revision`. A project policy constrains rather than grants: it cannot make a non-owner credential owned by the project or override a revoked credential. User and project cumulative budget policies are independent constraints and must both admit an attempt.

`UserBudgetPolicy` has one active row per `(user_id, product_space, currency)` and stores the user's per-invocation ceiling, cumulative counter/window reference, `allow_unknown_cost` (default false), `unknown_cost_reservation_minor_units`, and `revision`. Project policy may only narrow these terms. A project invocation uses the stricter ceiling/unknown reservation across both policies; a no-project invocation still requires the user policy.

### 4.5 InvocationRequest, InvocationAttempt, and UsageAudit

An `InvocationRequest` represents what a human or product asked for. An `InvocationAttempt` represents one actual adapter attempt, including retry or explicitly confirmed fallback. A request has zero or more attempts. Retry and fallback create attempts beneath the original request; neither creates another invocation.

Required request fields include `id`, `requesting_user_id`, `product_space`, nullable `project_id`, non-null `project_scope_id`, `invocation_family`, `idempotency_key`, `canonical_request_payload_hash`, requested capabilities and Provider/model/credential references or temporary-credential indicator, `request_id`, timeout/total-elapsed ceiling, budget and confirmation snapshots, prompt/version reference, input/output artifact references, `status`, `started_at`, `terminal_at`, `cancellation_requested_at`, `final_error_category`, `output_reference`, created/updated timestamps, and `revision`.

Invocation idempotency has exactly this database unique scope:

```text
(requesting_user_id,
 product_space,
 project_scope_id,
 invocation_family,
 idempotency_key)
```

`project_scope_id` is `NOT NULL`. A no-project invocation uses the reserved all-zero UUID `00000000-0000-0000-0000-000000000000`, never SQL `NULL`; a database check requires `project_id IS NULL` exactly when the sentinel is used and otherwise requires `project_scope_id = project_id`. The request payload is UTF-8 JSON canonicalized with RFC 8785 JSON Canonicalization Scheme and hashed with SHA-256; the stored value is lowercase hexadecimal with a fixed `sha256:` prefix. Same scope/key/hash returns the original invocation; same scope/key with a different hash returns a structured idempotency conflict; different user, product space, project, or invocation family cannot collide. The scope belongs to the Phase 3A invocation table and cannot fall back to the older command scope. Cross-project replay is therefore rejected by construction.

Required attempt fields include `id`, `invocation_id`, `attempt_number`, resolved Provider/model, immutable saved `credential_id` and `credential_encryption_version_snapshot` or a temporary-credential indicator (never plaintext), adapter version, retry/fallback lineage, `status`, `started_at`, `terminal_at`, `cancellation_requested_at`, `final_error_category`, `output_reference`, Provider raw error code and request ID when safe, rate-limit metadata, latency, cancellation outcome, and `revision`. Usage and cost are append-only ledger facts described in section 4.6, not mutable attempt truth. `attempt_number` is unique per invocation. Once admitted, an attempt never changes to a different credential because a default, grant, policy, or replacement later changes.

The frozen states are:

- `InvocationStatus`: `pending`, `admitted`, `running`, `succeeded`, `failed`, `cancelled`, `outcome_unknown`.
- `AttemptStatus`: `created`, `admitted`, `running`, `succeeded`, `failed`, `cancelled`, `outcome_unknown`.

The only legal invocation transitions are `pending → admitted|cancelled|failed`, `admitted → running|cancelled|failed`, and `running → succeeded|failed|cancelled|outcome_unknown`. The only legal attempt transitions are `created → admitted|cancelled|failed`, `admitted → running|cancelled|failed`, and `running → succeeded|failed|cancelled|outcome_unknown`. `succeeded`, `failed`, `cancelled`, and `outcome_unknown` are execution-terminal; none may transition back to an active state. `outcome_unknown` may receive later reconciliation events but its displayed result and state history are not silently rewritten.

Every state update runs in a transaction that locks the row with `SELECT ... FOR UPDATE`, revalidates the caller-supplied `revision`, and increments it. The attempt admission transaction writes `created → admitted` together with credential authorization and budget reservation. After that commit, a separate guarded `admitted → running` transition must succeed before dispatch. If cancellation wins before `running` commits, there is no adapter call. For cancellation versus completion, the first transaction that commits a legal terminal transition wins. Completion first makes cancellation return `already_terminal`; cancellation first prevents a later success. A late Provider response appends `late_result_received`, and any late usage appends a deduplicated reconciliation ledger entry; neither overwrites the terminal status, output, or timestamp.

Started invocation/attempt identities cannot be deleted or rewritten. Terminal fields are write-once. Audit, event, usage, and cost ledgers are append-only; any summary cost field is a rebuildable cache, never the audit source. Invocation reduction is deterministic: an attempt selected as the final successful result yields `succeeded`; a user cancellation that wins yields `cancelled`; with no success, any `outcome_unknown` yields `outcome_unknown`; otherwise, after all allowed attempts have deterministically failed, the invocation yields `failed`.

`UsageAudit` is a user/project-visible, append-only projection or table with a reference to the immutable invocation/attempt. It contains actor, product space, authorized project, Provider/model identifiers, credential alias/fingerprint reference (not payload), capability set, status, safe error code, usage/cost state, timestamps, request/correlation IDs, and redacted artifact/prompt references. It MUST NOT contain API keys, Authorization headers, connection strings, ungoverned complete private prompts, raw Provider request/response bodies, or unbounded error text.

### 4.6 Budget, reservation, retry, and cost ledger

Admission enforces three simultaneous constraints: the invocation ceiling, the requesting user's cumulative budget, and the project's cumulative budget when a project exists. An active `UserBudgetPolicy` and matching counter are required for every attempt; a project invocation additionally requires its active project policy and counter. Missing policy/counter fails admission. The effective per-invocation ceiling is the lower of the user and applicable project ceilings captured in the invocation snapshot. Both cumulative budgets MUST pass; the stricter remaining amount is effective. There is no either/or selection.

Every cumulative budget counter contains `currency`, `window_start`, `window_end`, `limit_minor_units`, `committed_minor_units`, `reserved_minor_units`, and `revision`, with non-negative checks and `committed + reserved <= limit` enforced at reservation time. Counters are unique by governed subject, currency, and window. Phase 3A performs no implicit currency conversion: the invocation pricing/reservation currency must match every applicable counter, otherwise admission fails.

Each attempt owns one `BudgetReservation`. In the same admission transaction that authorizes the credential and creates the attempt, the service locks the invocation aggregate, then the user counter, then the project counter when present with `SELECT ... FOR UPDATE`; revalidates each revision; calculates `committed + reserved + requested_reservation`; and checks the invocation's uncommitted remainder and both cumulative remainders. Only if every check passes does it create the reservation and increase each applicable `reserved_minor_units`. Any failure creates neither an admitted attempt nor a Provider side effect. The fixed lock order prevents concurrent admissions from overspending or deadlocking each other.

Known-cost reservation is conservatively derived from the requested usage ceiling and approved pricing snapshot. Unknown pricing MUST NOT be treated as zero. It is denied by default and is allowed only when every applicable user/project policy explicitly sets `allow_unknown_cost=true`, the preview names the uncertainty and the user confirms it, and the higher (stricter) applicable `unknown_cost_reservation_minor_units` value is non-zero and reserved. Its audit cost source is `unknown_reserved`.

Retry is constrained as follows:

- `max_attempts` is an integer from 1 through 3, inclusive.
- `total_elapsed_time_limit_ms` is explicit and from 1 through the First Slice platform hard maximum of 120,000 ms. Each attempt timeout is capped by Provider policy, the configured per-attempt limit, and the remaining total time.
- First Slice retryable categories are exactly `rate_limited`, `provider_unavailable`, and `connection_failure_before_dispatch`; adding a category requires a later contract change and tests.
- `authentication_failed`, `permission_denied`, `invalid_request`, `safety_rejected`, `quota_exceeded`, and `cost_limit_exceeded` are never retryable.
- `Retry-After` is honored only when valid and within the remaining elapsed ceiling; cancellation forbids a new attempt.
- Retry retains Provider/model/credential intent, is separate from fallback, and executes a fresh authorization, revocation/grant/policy check and fresh budget reservation every time. It cannot reuse a revoked saved credential.

If a timeout or connection loss occurs after request dispatch and the platform cannot prove that the Provider did not execute, the attempt becomes `outcome_unknown`. Automatic retry is forbidden unless that Provider exposes a verified idempotency protocol bound to this attempt. The reservation deterministically moves to `pending_reconciliation`; its full reserved amount remains in `reserved_minor_units` and is not released until a deduplicated receipt or separately governed reconciliation event settles it.

Every attempt records usage/cost through an append-only ledger. Invocation total cost is the sum of all retry and fallback attempt ledger facts. Settlement locks the reservation and applicable counters, converts actual cost from reserved to committed, and releases only the unused amount. Actual cost is never truncated if it exceeds a reservation; the full amount is appended and committed, the budget breach is audited, and further attempts are blocked. Duplicate or late receipts are deduplicated by unique `(provider_key, provider_receipt_id)` when available, otherwise by `(attempt_id, source, canonical_sequence)`. Late receipts and corrections append reconciliation/correction entries instead of updating prior facts. Ordinary users have no ledger mutation operation.

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
- Validation is rate-limited per owner, credential, source/session, and Provider; validation records a safe status/time only. First Slice fake validation has no remote network path.

Every saved-credential Provider attempt uses one admission transaction:

1. begin a database transaction and lock the selected `CredentialRecord` with `SELECT ... FOR UPDATE`;
2. lock relevant rows with `SELECT ... FOR UPDATE` in this order—active `CredentialGrant`, `ProjectModelPolicy`, invocation aggregate, user budget counter, then project budget counter—and revalidate each revision;
3. verify the requesting user, current membership, credential ownership or explicit active grant, `status=active`, absence of revoke/replacement, Provider/model/capability policy, required confirmation, and final budget reservation;
4. create the `InvocationAttempt` and its `BudgetReservation` in this transaction;
5. while all checks and locks remain valid, unwrap and decrypt the credential into request-local secret memory;
6. commit the admission transaction; this commit is the authorization linearization point; and
7. only after a successful commit hand the secret to the Adapter. Commit failure destroys request-local plaintext and DEK and makes no Adapter call.

Decryption MUST occur after the final permission, membership, grant, revoke/replacement, policy, and budget checks. Caches may help select candidates but are never the final authorization source. A temporary credential has no row to lock, but it follows the same membership/policy/confirmation/budget transaction and is handed off only after commit.

The lock order defines race behavior. If revoke acquires the credential lock before admission commits, admission fails. If admission commits first, that specific attempt may continue using its request-local secret; the later revoke blocks every new admission. If replacement commits first, the old credential cannot be selected. An admitted attempt remains bound to its immutable `credential_id` and encryption-version snapshot even if user defaults change. Each retry performs a new admission and reservation and cannot reuse a now-revoked saved credential.

Revoke is one transaction: lock the credential, verify the owner and active status, set `status=revoked`, `revoked_at`, and the next revision, revoke every active grant, set all encryption/ciphertext/wrapped-DEK/nonce/tag/algorithm/version fields to `NULL`, append the audit event, and commit. After commit, every new admission fails.

Replace is one transaction: lock the old credential, verify owner and active status, complete all encryption for a new pre-generated credential ID, insert the new active row with `replaces_credential_id`, mark the old row `replaced`, set revoke/replace timestamps, cryptographically erase its envelope fields, revoke its active grants, append create/replace/revoke audit events, and commit. Failure rolls back both rows and audit events. Old grants are never copied; future grant of the new credential is an explicit user command.

### Temporary-key implementation clarification

Within one synchronous request, retry against the same Provider may reuse the request-local temporary key buffer, but every retry still performs fresh authorization and budget admission. First Slice MUST NOT carry a temporary key across a queue, background task, process, later request, or persisted retry record. Reverse proxies and request logging MUST disable request-body capture for these routes. Validation/debug instrumentation may record only allowlisted field names and a redacted-present/absent state, never the key or raw request body.

### Custom Provider egress / SSRF gate

The custom OpenAI-compatible definition is catalog-only in First Slice. First Slice rejects every custom Provider URL and has no real Provider egress. Before any real network Provider operation is enabled, credential validation, model catalog, and invocation MUST all use one reviewed safe-transport component that enforces:

- URL canonicalization before policy evaluation, including IDNA/punycode host normalization;
- parsing every recognized unusual IPv4 spelling and IPv4-mapped IPv6 form into one canonical numeric address before policy evaluation, with ambiguous/unrecognized forms rejected;
- complete CNAME-chain and DNS-answer validation against prohibited loopback, link-local, unspecified, multicast, metadata-service, RFC1918/private, and other policy-denied destinations;
- validation of both resolved IPs and the actual connected peer IP to resist DNS rebinding;
- full revalidation for every redirect rather than inherited trust;
- ignoring/disabling system environment proxies; any future explicit proxy configuration requires its own reviewed safe-transport policy and cannot bypass destination validation;
- HTTPS and port allowlists/policy, no embedded credentials, bounded connect/read/total timeouts, maximum response-body size, and bounded connection-pool concurrency.

This safe transport is a mandatory future Gate, not a claim that URL parsing or the First Slice fixture implements network safety.

### Budget and cost control

Section 4.6 is the normative budget contract. Admission checks policy, pricing source, confirmation, all three budget layers, and atomic reservation before an Adapter call. Missing pricing is never zero; unknown-cost use requires its explicit exception and non-zero reservation. Budget rejection has zero Provider side effect. Estimated, reserved, actual, and reconciled cost remain distinct append-only facts.

### Immutable and privacy-bounded audit

Audits are append-only at the invocation/attempt boundary. Redacted prompt and artifact references must be versioned, access-checked, and size-bounded. If a complete private input is needed later, it belongs in a separate authorized encrypted artifact design, not JSON audit metadata. Audit query visibility is limited to the owner and authorized project role; credential value is never revealed by audit access.

## 8. Database and migration plan

### Retention and deletion boundary

First Slice forbids physical deletion of `UserAccount`, `PaintProject`, `CredentialRecord`, `InvocationRequest`, `InvocationAttempt`, and every audit/event/usage/cost ledger row. Supported lifecycle actions are user deactivation, project archival, credential revoke plus cryptographic erase, and a future separately designed purge after an approved retention period. That purge is not part of First Slice.

The FK deletion policy is frozen:

| Child reference | Delete action |
| --- | --- |
| `CredentialRecord.owner_user_id → UserAccount` | `ON DELETE RESTRICT` |
| `CredentialGrant.credential_id → CredentialRecord` | `ON DELETE RESTRICT` |
| `CredentialGrant.project_id → PaintProject` | `ON DELETE RESTRICT` |
| `CredentialGrant.granted_by_user_id → UserAccount` | `ON DELETE RESTRICT` |
| `UserProviderPreference.user_id → UserAccount` | `ON DELETE RESTRICT` |
| `ProjectModelPolicy.project_id → PaintProject` | `ON DELETE RESTRICT` |
| `UserBudgetPolicy.user_id → UserAccount` | `ON DELETE RESTRICT` |
| project budget policy/counter `project_id → PaintProject` | `ON DELETE RESTRICT` |
| `BudgetReservation.attempt_id → InvocationAttempt` | `ON DELETE RESTRICT` |
| `InvocationRequest.requesting_user_id → UserAccount` | `ON DELETE RESTRICT` |
| nullable `InvocationRequest.project_id → PaintProject` | `ON DELETE RESTRICT` |
| `InvocationAttempt.invocation_id → InvocationRequest` | `ON DELETE RESTRICT` |
| every audit/event/usage/cost parent reference | `ON DELETE RESTRICT` |

Audit rows retain bounded actor/project/Provider snapshot columns for historical readability, but snapshots never replace the authorization FKs.

User deactivation is one governed fail-closed workflow: deny new sessions and invocations, revoke and cryptographically erase all user credentials, revoke their active grants, disable their preferences, and retain the `UserAccount`, invocations, and audits. Project archival blocks new invocation, disables its model policy, revokes that project's active credential grants, and retains the project, user-owned credentials, invocations, and audits.

### Grant, replacement, and ciphertext constraints

`CredentialGrant` has a partial unique index:

```text
UNIQUE (credential_id, project_id)
WHERE revoked_at IS NULL
```

Grant/revoke operations lock the grant identity with `SELECT ... FOR UPDATE`, revalidate the required `revision`, and increment it. `CredentialRecord.replaces_credential_id` is a nullable self-FK with `ON DELETE RESTRICT`, a unique constraint (one old credential can have at most one replacement), and a check forbidding self-reference. Replacement locks the old row and requires it to be active. A database constraint trigger plus the service transaction verifies that old and new rows have the same `owner_user_id` and `provider_key`; the unique constraint and lock close concurrent replacement. Grants are not copied.

Named database checks enforce the envelope lifecycle. For `status=active`, `encryption_version`, `data_algorithm`, `ciphertext`, `data_nonce`, `data_authentication_tag`, `wrapped_dek`, `wrap_algorithm`, `wrap_nonce`, `wrap_authentication_tag`, and `aad_version` are all non-null; `data_algorithm='AES-256-GCM'`, data nonce/tag lengths are 12/16 bytes, and fixture `wrap_algorithm='AES-256-GCM'` requires wrap nonce/tag lengths 12/16 bytes. Ciphertext and wrapped DEK are non-empty. For `status IN ('revoked','replaced','erased')`, every one of those envelope fields is `NULL`. An unrecognized algorithm/version fails closed.

Revoke and replace immediately satisfy the erased-state check in the same transaction. They retain only credential ID, owner, Provider, alias, keyed fingerprint/last four, creation/revoke/replace timestamps, replacement lineage, revision, and security-audit metadata. No decryptable old ciphertext remains.

### Four additive migrations

Phase 3A uses at least four independently testable child revisions after `2b1c4d5e6f70`; it MUST NOT use a single giant migration:

1. **Migration A — Registries:** add `ProviderDefinition`, `CapabilityDefinition`, `ModelDefinition`, join tables, named constraints/indexes, and fixture-safe definition structure. It contains no credentials or network enablement.
2. **Migration B — Credential security:** add `CredentialRecord` and every explicit encryption field, `CredentialGrant`, statuses/revisions, active-grant partial unique index, envelope lifecycle/length checks, replacement self-FK/unique/check/constraint trigger, and `ON DELETE RESTRICT` FKs.
3. **Migration C — Policies, budget, and invocation:** add `UserProviderPreference`, `ProjectModelPolicy` plus allowlists, user/project budget policy/counter/reservation tables, `InvocationRequest`, `InvocationAttempt`, the exact idempotency scope/check/unique constraint, and append-only audit/event/usage/cost ledgers.
4. **Migration D — Fixture enablement:** insert only Fake Provider definitions and fixture model/capability facts behind an application feature flag that defaults off. Enable it only after application compatibility verification.

All four migrations are additive, do not backfill invented credentials/invocations/audit, and do not change existing PaintPilot table semantics or generalize `PaintProject`, `ImageSet`, or `RegionSet` into an AI object. Each revision requires its own upgrade and downgrade verification. A downgrade first checks for protected credentials, invocations, reservations, or audit/usage/cost history and fails closed when any exist; destructive retention handling requires a future separately approved purge design. This architecture Candidate creates no migration.

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
3. temporary credential handling plus saved-credential persistence using the frozen AEAD/envelope contract and a development/test file-only fixture key provider, with no real KMS choice;
4. user defaults, owner-governed project policy, credential grant relation, cumulative budget counters/reservations, and safe preview resolver;
5. invocation request/attempt/audit/usage/cost persistence with exact idempotency, state-machine, and fake-only execution contracts;
6. focused Provider/Model and Credential settings UI plus bilingual labels and safe empty/error/confirmation states;
7. focused encryption-integrity, authorization/race, budget/retry, idempotency, state-machine, migration, redaction, catalog, cost-admission, and fake-provider tests.

It explicitly excludes real paid Provider calls, real API keys, auto fallback, RAG, embeddings, reranking, Paint Plan, Arcana, public deployment, production KMS, subscriptions, billing, background execution, and any PaintPilot workflow change.

Sol implementation is required for this batch because it combines cryptographic-boundary code, multi-table authorization/migration work, API and frontend contracts, and adversarial security tests. A separate independent Sol reviewer must PASS the focused Candidate before that implementation starts.

## 12. Test and evidence strategy

Focused implementation tests must prove at least:

- the fixture root-key provider is file-only, development/test-only, exactly 32 bytes, rejects missing/unsafe/symlink/wrong-mode/wrong-length files and production/staging, and redacts values;
- temporary credentials are absent from ORM/audit/log/error/response/browser-storage paths after success and failure;
- data and wrap AEAD detect swapped credential identity, ciphertext, DEK, nonce/tag, and metadata; encryption/database failure leaves no partial active credential;
- saved ciphertext cannot be returned or decrypted across users; revoke/replace erase every envelope field, block new admission, preserve only allowed metadata, and never transfer grants;
- owner/reviewer/missing-project access has non-disclosing responses; policy and invocation queries remain project scoped;
- real PostgreSQL concurrency proves admission/revoke/replace linearization, retry re-admission, grant revision conflicts, and zero Adapter calls on failed/rolled-back admission;
- a model without a proven required capability returns a structured error with zero fake-provider calls;
- concurrent reservations cannot overspend invocation/user/project limits; unknown price is rejected unless explicitly confirmed with a non-zero reservation; retries/fallback and late receipts all reconcile into the append-only total;
- exact invocation idempotency distinguishes user/product/project/family scope, rejects payload conflicts and cross-project replay, and keeps retry/fallback under one invocation;
- every legal and illegal state transition plus cancel/completion/late-result races preserve one immutable terminal outcome;
- retries and explicit fallback form distinct attempts; post-dispatch uncertainty does not auto-retry; automatic credential/Provider/model escalation is rejected;
- custom Provider URLs are rejected before any resolver/adapter network call;
- Provider raw errors, Authorization headers, and fake secrets are redacted from logs/audits/error details;
- all four migrations independently upgrade/downgrade, enforce `RESTRICT`, grant/lineage/envelope constraints, and refuse destructive downgrade with protected history; and
- frontend contract parsing, bilingual keys, secret-input clearing, no storage persistence, destructive confirmation, narrow viewport behavior, and safe error states pass.

No real key, Provider endpoint, paid token, browser screenshot containing a key, or external Provider test belongs in Phase 3A evidence.

## 13. Risks and explicit non-goals

Principal-string versus internal-user-ID ownership must be reviewed carefully at every bridge to `PaintProject`. Production KMS selection/operations, audited implementation of the mandatory safe transport, real-Provider pricing accuracy and terms, exact audit-retention duration, and use of private image input require later approvals. The frozen encryption, admission, budget, idempotency, state, and deletion contracts in this document MUST NOT be weakened while making those later choices. The ability to display a Provider definition is not evidence that it is configured, safe to call, or affordable.

This document does not authorize an AI feature, a Provider selection, a cloud KMS, an outbound network exception, a migration, a secret, a paid API request, a public deployment, Arcana, RAG, retrieval, model training, billing, or changes to PaintPilot business objects/workflow.
