# Phase 3A — BYOK Multi-Provider Multimodal Foundation

Status: execution-semantics-remediated architecture-freeze Candidate pending final focused independent rereview

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

Persisted identity and lifecycle fields are `id`, `owner_user_id`, `provider_definition_id`, immutable `provider_key`, `key_fingerprint`, `alias`, `status`, `created_at`, `updated_at`, `revoked_at`, `replaced_at`, `replaces_credential_id`, `last_successful_validation_at`, and `revision`. `provider_definition_id` is the authoritative registry FK; `provider_key` is the immutable registry-key snapshot used by AAD and historical display. The encryption fields are the explicit logical fields in section 4.3; they MUST NOT be hidden inside JSON or a plaintext-capable ordinary domain field. `status` is exactly one of `active`, `revoked`, or `replaced`; cryptographic erase is a required invariant of the latter two states, not a fourth lifecycle state. `key_fingerprint` is a keyed, rotation-aware HMAC-style fingerprint of normalized key bytes, not an unsalted digest suitable for offline guessing. No plaintext credential prefix, suffix, or other fragment is persisted for presentation.

`CredentialGrant` (stored as `credential_project_grants`) is a separate relation: `credential_id`, `project_id`, `granted_by_user_id`, `created_at`, `revoked_at`, and `revision`. It does not transfer ownership. Authorization is frozen as follows:

- **Project-scoped invocation:** the saved credential MUST be owned by the requesting current user **and** have one active `CredentialGrant` that relates that exact credential to that exact `PaintProject`. The requesting user MUST also have current access to the non-archived project. Credential ownership, including project-owner identity, never substitutes for the grant. A reviewer, ordinary member, or project owner cannot use another user's credential merely because they have project membership or access. A temporary credential has no grantable `CredentialRecord`, so First Slice rejects it for project-scoped invocation.
- **Projectless invocation:** the requesting user MAY directly use their own active saved credential, or a request-local temporary credential, without a project grant. No user may use another user's credential.

Project policy constrains a grant but never creates one. First Slice grant mutation is credential-owner-only, and policy or reviewer visibility alone never grants use.

Revoke and replace are irreversible for the old credential. Both deny future admission, revoke active grants, and immediately cryptographically erase the old row by setting every ciphertext, wrapped-DEK, nonce, authentication-tag, algorithm, and encryption/AAD-version field to `NULL`. A revoked row has `revoked_at IS NOT NULL` and `replaced_at IS NULL`; a replaced row has `replaced_at IS NOT NULL` and `revoked_at IS NULL`. Minimal non-secret audit metadata and replacement lineage remain. Replace creates a new active encrypted row with `replaces_credential_id` pointing to the old row, never overwrites old ciphertext in place, and never transfers old grants.

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

The Project Model Policy allowlists are explicit association tables, never serialized Registry identifiers: `ProjectModelPolicyProvider`, `ProjectModelPolicyModel`, `ProjectModelPolicyCapability`, and, where the retained credential allowlist is implemented, `ProjectModelPolicyCredential`. Each has `project_model_policy_id`, its named target ID, and `created_at`, with `UNIQUE (project_model_policy_id, target_id)` and lookup indexes on both the policy and target sides. The Provider, Model, and Capability associations constrain only their respective registry choice; the Credential association references `CredentialRecord`, not a Registry object. A credential allowlist may narrow choices only when that Credential is owned by the requesting current user and, for a project-scoped call, has an active exact `CredentialGrant`; it never substitutes for the Grant, and a revoked or replaced Credential cannot pass policy admission.

`UserBudgetPolicy` has one active row per `(user_id, product_space, currency)` and stores the user's per-invocation ceiling, cumulative counter/window reference, `allow_unknown_cost` (default false), `unknown_cost_reservation_minor_units`, and `revision`. Project policy may only narrow these terms. A project invocation uses the stricter ceiling/unknown reservation across both policies; a no-project invocation still requires the user policy.

For First Slice, every pricing/currency field in these registry, preference, policy, and budget objects is either absent where optional or exactly `FIXTURE_CREDITS`; section 4.6 is normative. No ISO legal-tender value is accepted in this Slice.

### 4.5 InvocationRequest, canonical identity, InvocationAttempt, and UsageAudit

An `InvocationRequest` represents what a human or product asked for. An `InvocationAttempt` represents one actual adapter attempt, including a sequential retry or a future explicitly confirmed fallback. A request has zero or more attempts. Retry and fallback belong to the original invocation and never create a second invocation.

Required request fields include `id`, `requesting_user_id`, `product_space`, nullable `project_id`, non-null `project_scope_id`, `invocation_family`, `idempotency_key`, `canonicalization_version`, `canonical_request_payload_hash`, requested capabilities and Provider/model/credential references or temporary-credential indicator, `request_id`, timeout/total-elapsed ceiling, budget and confirmation snapshots, prompt/version reference, governed input/output artifact references, `status`, nullable `final_attempt_id`, `started_at`, `terminal_at`, `cancellation_requested_at`, `final_error_category`, `output_reference`, created/updated timestamps, and `revision`.

`invocation_family` is a server-controlled enum, not a client-defined namespace. First Slice allows exactly `fixture_credential_validation`, `fixture_model_catalog`, and `fixture_invocation`; an arbitrary client string is rejected before idempotency lookup or admission.

#### Domain canonicalization and artifacts

Before RFC 8785 JCS, every request uses `canonicalization_version=phase3a-v1` and the following versioned domain canonicalization:

- Strings are normalized to Unicode NFC. User text whose whitespace has business meaning is not automatically trimmed. Enum and identifier values are replaced by their server-owned canonical values.
- Timestamps must be timezone-aware, are converted to UTC, and are encoded as RFC 3339 with fixed microsecond precision (`YYYY-MM-DDTHH:MM:SS.ffffffZ`). Local-time strings and ambiguous timestamps are rejected.
- Binary floating-point values cannot enter the canonical payload. Money or fixture-credit amounts use integer minor units. Ratios and other domain decimals use a versioned fixed-scale decimal string. `NaN`, `Infinity`, and `-Infinity` are rejected.

Every artifact reference in the canonical request contains an immutable `artifact_id`, `artifact_revision` or other immutable version, SHA-256 content hash, `media_type`, and `byte_length`. Temporary URLs, local paths, mutable object keys, and database IDs without a content hash are invalid identities. Raw binary and multipart bodies never enter JCS. Binary content must first be stored as a governed artifact and then referenced by immutable identity. First Slice does not implement real binary invocation and therefore rejects raw binary/multipart invocation at the API boundary.

Payload identity is computed in exactly this order:

1. validate the versioned request schema;
2. apply `phase3a-v1` domain canonicalization;
3. produce RFC 8785 JCS bytes;
4. calculate SHA-256; and
5. persist both `canonicalization_version` and the lowercase `sha256:`-prefixed payload hash.

#### Idempotency and project scope

Invocation idempotency has exactly this database unique scope:

```text
(requesting_user_id,
 product_space,
 project_scope_id,
 invocation_family,
 idempotency_key)
```

`project_scope_id` is `NOT NULL`. A projectless invocation uses only the reserved all-zero UUID `00000000-0000-0000-0000-000000000000`, never SQL `NULL`. Migration C first queries `PaintProject.id` and fails if an existing project has that value, then adds a named database `CHECK` that permanently forbids the all-zero UUID as a `PaintProject.id`. A second named `CHECK` requires a project-scoped request to have `project_scope_id = project_id` for a real non-zero project ID and a projectless request to have `project_id IS NULL` with the exact sentinel. No other combination is valid.

Same scope/key/hash returns the original invocation; same scope/key with a different hash returns a structured idempotency conflict; a different user, product space, project scope, or invocation family cannot collide. The idempotency transaction creates only `InvocationRequest(status=pending)`. It creates no `InvocationAttempt` and no `BudgetReservation`. Replay returns the original invocation and never duplicates either child object. This scope belongs to the Phase 3A invocation table and cannot fall back to the older command scope.

#### Attempt and aggregate state contract

Required attempt fields include `id`, `invocation_id`, `attempt_number`, resolved `provider_definition_id`/`model_definition_id`, immutable `provider_key`/`model_id`/adapter-version/capability snapshots, immutable saved `credential_id` and `credential_encryption_version_snapshot` or a projectless temporary-credential indicator (never plaintext), retry/fallback lineage, `currency`, `status`, dispatch and terminal timestamps, cancellation request, final error category, output reference, safe Provider request/error metadata, latency, cancellation outcome, and `revision`. Usage and cost are append-only ledger facts described in section 4.6, not mutable attempt truth. `attempt_number` is unique per invocation. Once admitted, an attempt never changes credential, Provider, model, adapter version, capability snapshot, or currency because a default, grant, policy, registry lifecycle, or replacement later changes.

The frozen states are:

- `InvocationStatus`: `pending`, `admitted`, `running`, `succeeded`, `failed`, `cancelled`, `outcome_unknown`.
- `AttemptStatus`: `created`, `admitted`, `running`, `succeeded`, `failed`, `cancelled`, `outcome_unknown`.

A partial unique index enforces at most one active attempt:

```text
UNIQUE (invocation_id)
WHERE status IN ('created', 'admitted', 'running')
```

First Slice forbids parallel attempts and Provider racing. `created` is included in the invariant, but First Slice admission publishes a new attempt directly as `admitted` in its single transaction; it never commits a free-standing `created` attempt.

Attempt admission is one transaction that follows the global lock order in section 7, acquiring the invocation only at position 8 after all applicable earlier resources. It confirms the invocation is not terminal or cancelled and has no active attempt; re-runs User, project access, Credential, Grant, Policy, capability, and Budget admission; creates `Attempt(status=admitted)` and `BudgetReservation(state=reserved)`; updates the invocation from `pending`, or from the non-terminal `running` retry-ready condition after a prior terminal failure, to `admitted`; appends the admission event; and commits. A committed `pending` invocation can never have an admitted attempt.

Dispatch uses a separate short transaction: lock the invocation, attempt, and reservation in global order; revalidate no cancellation, `Invocation=admitted`, `Attempt=admitted`, and `Reservation=reserved`; change both invocation and attempt to `running`; change the reservation to `dispatch_committed`; write `dispatch_committed_at`; append the dispatch event; and commit. The Adapter may be called only after that commit succeeds.

Terminal reduction is also one transaction and follows the same global order, locking applicable user/project counters before the invocation, active attempt, and reservation. It writes the attempt's terminal status and write-once terminal fields; settles, releases, or marks the reservation for reconciliation; appends usage/cost/event facts; and reduces the invocation. A failed terminal attempt with retry capacity leaves the invocation non-terminal in the `running` retry-ready condition with no active attempt; the next attempt must pass a fresh admission. A successful attempt sets `final_attempt_id` and `Invocation=succeeded`. An uncertain dispatched attempt yields `outcome_unknown`. When all allowed attempts have deterministically failed, the invocation yields `failed`.

`InvocationRequest.final_attempt_id` is nullable and can be set from `NULL` exactly once, only in the successful terminal transaction. A composite FK `(invocation_id, final_attempt_id)` references an attempt belonging to that invocation. First Slice allows only one successful attempt; database/service guards reject another success or any later change of `final_attempt_id`.

The legal attempt transitions are `created → admitted|cancelled|failed`, `admitted → running|cancelled|failed`, and `running → succeeded|failed|cancelled|outcome_unknown`. The legal invocation transitions include `pending → admitted|cancelled|failed`, `admitted → running|cancelled|failed`, `running → admitted` only for a sequential re-admitted retry after the prior attempt is terminal failed, and `running → succeeded|failed|cancelled|outcome_unknown`. Execution-terminal states never return active. `outcome_unknown` may receive append-only reconciliation facts but cannot auto-retry or silently rewrite displayed state history.

Retry is allowed only after the prior attempt is definitively terminal `failed`, reuses the original invocation, and performs a fresh admission. A fallback also waits for a definitively terminal prior attempt; First Slice keeps fallback disabled. Cancellation forbids a new attempt. Every invocation has at most one active attempt at every instant.

Cancel is idempotent and uses row-lock/CAS arbitration. An already cancelled invocation returns its original state; another terminal state returns `already_terminal`. If cancel wins against an active attempt, the same transaction records cancellation and releases only a reservation that is safe to release under section 4.6. A late success after cancel cannot set `final_attempt_id` or change terminal output. If success commits first, cancel returns `already_terminal`.

Started invocation/attempt identities cannot be deleted or rewritten. Terminal fields are write-once. Audit, event, usage, and cost ledgers are append-only; any summary cost field is a rebuildable cache, never the audit source. A late Provider response appends `late_result_received`, and late usage appends a deduplicated reconciliation ledger fact; neither overwrites terminal state, output, or timestamp.

`UsageAudit` is a user/project-visible, append-only projection or table with a reference to the immutable invocation/attempt. It contains actor, product space, authorized project, Provider/model/capability snapshots, credential alias/fingerprint reference (not payload), status, safe error code, fixture usage/cost state, timestamps, request/correlation IDs, and immutable redacted artifact/prompt references. It MUST NOT contain API keys, Authorization headers, connection strings, ungoverned complete private prompts, raw Provider request/response bodies, or unbounded error text.

### 4.6 Budget, reservation, retry, recovery, and cost ledger

#### First Slice currency

First Slice permits exactly one non-real fixture measurement unit: `FIXTURE_CREDITS`. Every First Slice Provider/model pricing fact, budget policy/counter, reservation, usage, cost ledger entry, attempt, and invocation aggregate uses that exact currency. Amounts are integer minor units. There is no exchange-rate conversion, second currency, or cross-currency fallback. The Fake Provider may emit deterministic fixture cost, but UI and audit MUST label `FIXTURE_CREDITS` as simulated usage rather than real model expense.

An invocation aggregates only attempts with the same currency. If any attempt currency differs, reduction fails structurally with `currency_mismatch`; it records no summed total and transitions the invocation to a structured failure. Real Providers, legal-tender currency, multiple currencies, and exchange conversion remain prohibited until a separate future security/cost contract authorizes them.

#### Admission and reservation

Admission enforces three simultaneous constraints: the invocation ceiling, the requesting user's cumulative budget, and the project's cumulative budget when a project exists. An active `UserBudgetPolicy` and matching counter are required for every attempt; a project invocation additionally requires its active project policy and counter. Missing policy/counter fails admission. The effective per-invocation ceiling is the lower of the user and applicable project ceilings captured in the invocation snapshot. Both cumulative budgets MUST pass; there is no either/or selection.

Every cumulative budget counter contains `currency`, `window_start`, `window_end`, `limit_minor_units`, `committed_minor_units`, `reserved_minor_units`, and `revision`, with non-negative checks and `committed + reserved <= limit` enforced at reservation time. Counters are unique by governed subject, currency, and window. In First Slice every currency equals `FIXTURE_CREDITS`.

Each attempt owns exactly one `BudgetReservation` with at least `reservation_id`, `invocation_id`, `attempt_id`, `currency`, `reserved_amount`, `state`, `created_at`, `admission_expires_at`, `dispatch_committed_at`, `settled_at`, `released_at`, and `revision`. States are exactly `reserved`, `dispatch_committed`, `settled`, `released`, and `reconciliation_required`. The admission transaction creates it as `reserved` with `admission_expires_at = created_at + 120 seconds`, increases each applicable reserved counter, and creates no Provider side effect. It follows section 7's global resource order, including the fixed user-counter-before-project-counter order.

Known fixture-cost reservation is conservatively derived from the requested usage ceiling and approved fixture pricing snapshot. Unknown cost MUST NOT be treated as zero. It is denied by default and is allowed only when every applicable policy explicitly enables it, preview names the uncertainty, the user confirms it, and the stricter non-zero fixture-credit reservation is held. Its audit source is `unknown_reserved`.

#### Dispatch and crash recovery

The dispatch transaction in section 4.5 is the only path from `reserved` to `dispatch_committed`. No Adapter call may start while a reservation remains `reserved`.

Automatic orphan recovery may release a reservation only when every condition is true: `state=reserved`; `admission_expires_at` has passed; the attempt is still `admitted`; `dispatch_committed_at IS NULL`; no `provider_request_id` exists; no usage/cost receipt exists; and there is no running or terminal event. In one row-locking transaction that follows the global order (applicable counter, invocation, attempt, reservation), the recovery worker revalidates every condition, marks the attempt `failed` with `dispatch_not_started`, reduces the invocation, changes the reservation to `released`, decrements the reserved counter, and appends an immutable recovery event. First Slice exposes this as a governed, explicitly invoked one-shot recovery operation, not a resident background queue or scheduler.

Once `dispatch_committed` has committed, process timeout or crash can never auto-release the reservation. Until uncertainty is classified it remains `dispatch_committed`; if outcome cannot be proved, one transaction sets the attempt/invocation to `outcome_unknown` and the reservation to `reconciliation_required`. It may settle or release only from verifiable usage/cost, verifiable proof that the Provider did not execute, or a governed manual reconciliation event. The Fake Provider deterministically completes settlement, but uses the same dispatch and reservation state contract.

#### Retry and settlement

Retry remains bounded:

- `max_attempts` is an integer from 1 through 3, inclusive.
- `total_elapsed_time_limit_ms` is explicit and from 1 through the First Slice hard maximum of 120,000 ms. Each attempt timeout is capped by Provider policy, per-attempt limit, and remaining total time.
- First Slice retryable categories are exactly `rate_limited`, `provider_unavailable`, and `connection_failure_before_dispatch`; adding a category requires a later contract change and tests.
- `authentication_failed`, `permission_denied`, `invalid_request`, `safety_rejected`, `quota_exceeded`, and `cost_limit_exceeded` are never retryable.
- `Retry-After` is honored only when valid and within the remaining elapsed ceiling; cancellation and `outcome_unknown` both forbid a new attempt.
- Retry retains Provider/model/credential intent, is separate from fallback, and performs fresh admission and a fresh reservation after the prior attempt is definitively failed.

Every attempt records usage/cost through an append-only ledger. Invocation fixture-credit total is the sum of all same-currency sequential attempt ledger facts. Settlement locks the reservation and applicable counters, converts actual cost from reserved to committed, and releases only the unused amount. Actual cost is never truncated if it exceeds a reservation; the full amount is appended and committed, the breach is audited, and further attempts are blocked. Duplicate or late receipts are deduplicated by unique `(provider_key, provider_receipt_id)` when available, otherwise by `(attempt_id, source, canonical_sequence)`. Late receipts and corrections append reconciliation/correction entries instead of updating prior facts. Ordinary users have no ledger mutation operation.

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

Fallback is closed throughout First Slice. A later separately authorized contract may enable it only when both Project Model Policy and the one-time invocation explicitly authorize it. Any future cost-increasing or Provider-changing fallback requires human confirmation for the exact fallback target, credential reference, currency, and budget snapshot; it must wait for the prior attempt to be definitively terminal and then create a sequential `InvocationAttempt` with `fallback_decision=confirmed`. No adapter may conceal fallback as an internal retry. A retry retains the same resolved Provider, model, credential, and `FIXTURE_CREDITS` currency and is bounded by policy.

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

All transactions involving Admission, Grant, Revoke, Replace, user deactivation, project archival, or project membership/access mutation obey one global resource order. A transaction skips absent resource classes but never reverses the remaining order:

1. requesting or affected `UserAccount` rows; multiple users by ascending UUID;
2. `PaintProject` rows; multiple projects by ascending UUID;
3. project membership/access rows;
4. `CredentialRecord` rows; multiple credentials by ascending UUID;
5. `CredentialGrant` rows;
6. policy/preference rows in this fixed internal order: `UserProviderPreference`, `ProjectModelPolicy`, `UserBudgetPolicy`, then `ProjectBudgetPolicy`;
7. `BudgetCounter` rows in this fixed internal order: `UserBudgetCounter`, then `ProjectBudgetCounter`;
8. `InvocationRequest`;
9. `InvocationAttempt`;
10. `BudgetReservation`.

No transaction may hold a later resource and then acquire an earlier resource or acquire same-class rows in a different UUID or stable composite-key order. In particular, no transaction may lock a `BudgetCounter` before its corresponding `UserBudgetPolicy` or `ProjectBudgetPolicy`. Grant create/revoke, credential revoke/replace, user deactivation, project archival, membership/access mutation, `UserBudgetPolicy` mutation, `ProjectBudgetPolicy` mutation, and admission must discover and revalidate their affected identities before acquiring locks; if the locked set changes, they fail/retry the transaction rather than extending it out of order.

Saved-credential attempt admission uses that order and performs the following final checks while locks remain held:

1. the requesting `UserAccount` remains active;
2. for project-scoped invocation, the `PaintProject` is not archived, current membership/owner access is valid, `CredentialRecord.owner_user_id` equals the requesting user, and one active Grant relates that exact Credential to that exact project;
3. for projectless invocation, the active Credential is owned by the requesting user and no Grant is required;
4. the Credential remains `active`, has not been revoked or replaced, and still satisfies Provider/model/capability policy and confirmation;
5. locks the current effective `UserBudgetPolicy` and then current effective `ProjectBudgetPolicy`, verifies both are enabled/current and have `FIXTURE_CREDITS`, and resolves their current windows, limits, and revisions; a disabled/replaced/revised policy, changed window, or non-`FIXTURE_CREDITS` currency requires recalculation or a structured admission failure, never use of a stale cache;
6. only after those policy locks and resolution, locks `UserBudgetCounter` and then `ProjectBudgetCounter`, reads their current window/limit state, and verifies the exact selection and `FIXTURE_CREDITS` reservation remain admissible under every applicable policy and counter; and
7. applies the existing no-policy contract exactly as already defined; an implementation may not invent a hidden default when a required policy is absent.

Only after all checks pass does admission atomically create the single `Attempt(status=admitted)` and `Reservation(state=reserved)` while updating the locked counters. While the authorization locks still hold, a saved credential may be unwrapped/decrypted into narrow request-local secret memory. Admission commit is the authorization and budget linearization point. Commit failure destroys plaintext/DEK and creates no Adapter side effect. The separate dispatch transaction in section 4.5 must then commit `Attempt/Invocation=running` and `Reservation=dispatch_committed`; only that later commit permits Adapter handoff. If dispatch fails or cancellation wins first, request-local secret material is destroyed without an Adapter call.

Decryption MUST occur after the final user, project, membership, ownership-and-Grant, revoke/replacement, policy, and budget checks. Caches may select candidates but are never final authority. A temporary credential has no grantable row and is therefore projectless-only in First Slice; it follows the same active-user, preference/policy, confirmation, invocation, and budget transaction and the same post-dispatch-commit handoff rule.

The global order fixes lifecycle races:

- User deactivation committing first makes every new admission fail. Admission committing first permits only that already admitted attempt to continue; every later retry/fallback attempt must re-admit and fail.
- Project archival committing first makes every new project-scoped admission fail. Admission committing first permits that attempt to continue, but archival forbids any new retry or fallback attempt.
- Membership/access revocation committing first makes new admission fail. Admission committing first permits the current attempt to continue; every new attempt rechecks access and fails.
- Revoke committing before admission makes admission fail. Admission committing first permits only that admitted attempt to continue with its request-local secret; every new attempt fails.
- Replacement committing first prevents selection of the old credential. Admission committing first remains bound to its immutable credential/encryption-version snapshot; replacement affects every later admission.
- A User or Project BudgetPolicy mutation committing first makes every later admission lock and use the new policy/window/limit. Admission committing first retains its already committed Reservation; later retry/fallback admission re-locks policy and counters and must satisfy the new policy.
- Disabling or tightening a User or Project BudgetPolicy does not revoke an already admitted Attempt, but blocks every retry/fallback admission that does not meet the new terms.

Grant mutation follows the same order and verifies an active credential owner, a non-archived project, the owner's current project access, exact credential/project identity, and revision before creating or revoking the grant. Membership mutation, project archival, user deactivation, and either BudgetPolicy mutation lock and revalidate every affected row in global order; none may use membership or owner status as a substitute for a project Grant. Policy caches may serve only display or candidate resolution; final admission always reads and locks the current database rows.

Revoke is one transaction in global order: verify the active owner and affected grants, set `status=revoked`, set `revoked_at` while keeping `replaced_at=NULL`, increment revision, revoke every active grant, set all envelope fields to `NULL`, append the audit event, and commit. After commit, every new admission fails.

Replace is one transaction in global order: verify the active owner and affected grants; complete encryption for a pre-generated new credential ID; insert the new active row with `replaces_credential_id` pointing to the old credential; mark the old row `replaced`, set only `replaced_at`, keep `revoked_at=NULL`, cryptographically erase its envelope, revoke its grants, append immutable create/replace audit events, and commit. Failure rolls back both rows and events. Old grants are never copied; granting the new credential is a separate explicit command.

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

First Slice forbids physical deletion of `ProviderDefinition`, `ModelDefinition`, `CapabilityDefinition`, `UserAccount`, `PaintProject`, `CredentialRecord`, `InvocationRequest`, `InvocationAttempt`, and every audit/event/usage/cost ledger row. Registry lifecycle is only `disabled` or `retired`; retirement prevents new admission without changing historical display. In particular, a `CapabilityDefinition` is never physically deleted in First Slice: it may only be disabled/retired, remains queryable when referenced by Project Policy, Provider/Model Capability, Attempt snapshot, or Audit, blocks new policy selection and new Invocation use after retirement, and cannot alter historical Invocation or Attempt semantics. Other supported lifecycle actions are user deactivation, project archival, and credential revoke/replace plus cryptographic erase. A future separately designed purge after an approved retention period is outside First Slice.

The FK deletion policy is frozen:

| Child reference | Delete action |
| --- | --- |
| `CredentialRecord.provider_definition_id → ProviderDefinition` | `ON DELETE RESTRICT` |
| `ModelDefinition.provider_definition_id → ProviderDefinition` | `ON DELETE RESTRICT` |
| `ProviderCapability.provider_definition_id → ProviderDefinition` | `ON DELETE RESTRICT` |
| `ProviderCapability.capability_definition_id → CapabilityDefinition` | `ON DELETE RESTRICT` |
| `ModelCapability.model_definition_id → ModelDefinition` | `ON DELETE RESTRICT` |
| `ModelCapability.capability_definition_id → CapabilityDefinition` | `ON DELETE RESTRICT` |
| `UserProviderPreference` Provider/model references | `ON DELETE RESTRICT` |
| `ProjectModelPolicyProvider.project_model_policy_id → ProjectModelPolicy` | `ON DELETE RESTRICT` |
| `ProjectModelPolicyProvider.provider_definition_id → ProviderDefinition` | `ON DELETE RESTRICT` |
| `ProjectModelPolicyModel.project_model_policy_id → ProjectModelPolicy` | `ON DELETE RESTRICT` |
| `ProjectModelPolicyModel.model_definition_id → ModelDefinition` | `ON DELETE RESTRICT` |
| `ProjectModelPolicyCapability.project_model_policy_id → ProjectModelPolicy` | `ON DELETE RESTRICT` |
| `ProjectModelPolicyCapability.capability_definition_id → CapabilityDefinition` | `ON DELETE RESTRICT` |
| `ProjectModelPolicyCredential.project_model_policy_id → ProjectModelPolicy` | `ON DELETE RESTRICT` |
| `ProjectModelPolicyCredential.credential_record_id → CredentialRecord` | `ON DELETE RESTRICT` |
| `InvocationAttempt.provider_definition_id → ProviderDefinition` | `ON DELETE RESTRICT` |
| `InvocationAttempt.model_definition_id → ModelDefinition` | `ON DELETE RESTRICT` |
| every usage/cost/audit Provider/model/capability reference | `ON DELETE RESTRICT` |
| `CredentialRecord.owner_user_id → UserAccount` | `ON DELETE RESTRICT` |
| `CredentialGrant.credential_id → CredentialRecord` | `ON DELETE RESTRICT` |
| `CredentialGrant.project_id → PaintProject` | `ON DELETE RESTRICT` |
| `CredentialGrant.granted_by_user_id → UserAccount` | `ON DELETE RESTRICT` |
| `UserProviderPreference.user_id → UserAccount` | `ON DELETE RESTRICT` |
| `ProjectModelPolicy.project_id → PaintProject` | `ON DELETE RESTRICT` |
| `UserBudgetPolicy.user_id → UserAccount` | `ON DELETE RESTRICT` |
| project budget policy/counter `project_id → PaintProject` | `ON DELETE RESTRICT` |
| `BudgetReservation.invocation_id/attempt_id → InvocationRequest/InvocationAttempt` | `ON DELETE RESTRICT` |
| `InvocationRequest.requesting_user_id → UserAccount` | `ON DELETE RESTRICT` |
| nullable `InvocationRequest.project_id → PaintProject` | `ON DELETE RESTRICT` |
| `InvocationAttempt.invocation_id → InvocationRequest` | `ON DELETE RESTRICT` |
| every audit/event/usage/cost parent reference | `ON DELETE RESTRICT` |

Every `InvocationAttempt` also stores immutable `provider_key`, `model_id`, `adapter_version`, and capability snapshots. Registry disablement or retirement cannot alter historical Attempt or audit display. Snapshots support history but never replace authorization or registry FKs.

User deactivation is one governed fail-closed workflow: deny new sessions and invocations, revoke and cryptographically erase all user credentials, revoke their active grants, disable their preferences, and retain the `UserAccount`, invocations, and audits. Project archival blocks new invocation, disables its model policy, revokes that project's active credential grants, and retains the project, user-owned credentials, invocations, and audits.

### Grant, replacement, and ciphertext constraints

`CredentialGrant` has a partial unique index:

```text
UNIQUE (credential_id, project_id)
WHERE revoked_at IS NULL
```

Grant/revoke operations follow section 7's global order, revalidate the required `revision`, and increment it. `CredentialRecord.replaces_credential_id` is a nullable self-FK with `ON DELETE RESTRICT`; a unique constraint permits at most one new credential to reference an old credential; a named check forbids self-reference. Replacement locks the old row and requires it to be active. A database constraint trigger plus the service transaction verifies that old and new rows have the same `owner_user_id` and `provider_definition_id`/`provider_key`; the unique constraint and lock close concurrent replacement. Grants are not copied.

Named database checks enforce exactly three lifecycle states and their timestamps/envelopes:

- `active`: `revoked_at IS NULL`, `replaced_at IS NULL`, and every envelope field is non-null. `replaces_credential_id` may be null or reference the one old credential this active row replaced.
- `revoked`: `revoked_at IS NOT NULL`, `replaced_at IS NULL`, and every envelope field is null.
- `replaced`: `replaced_at IS NOT NULL`, `revoked_at IS NULL`, and every envelope field is null.

For active rows, `data_algorithm='AES-256-GCM'`, data nonce/tag lengths are 12/16 bytes, fixture `wrap_algorithm='AES-256-GCM'` requires wrap nonce/tag lengths 12/16 bytes, and ciphertext/wrapped DEK are non-empty. Any other status, mixed timestamp combination, partial envelope, or unrecognized algorithm/version fails closed. Revoke and replace satisfy cryptographic-erase checks in the same transaction and retain only bounded non-secret metadata, lineage, revision, and audit facts. No decryptable old ciphertext remains.

### Four additive migrations

Phase 3A uses exactly one linear four-revision chain. Implementers generate the actual revision IDs, but dependencies are immutable:

```text
Migration A.down_revision = 2b1c4d5e6f70
Migration B.down_revision = revision_A
Migration C.down_revision = revision_B
Migration D.down_revision = revision_C
```

It MUST NOT use a single giant migration, a branch, or an alternate parent dependency.

1. **Migration A — Registries:** add `ProviderDefinition`, `CapabilityDefinition`, `ModelDefinition`, association tables, lifecycle status, named constraints/indexes, and `RESTRICT` registry FKs. It contains no credentials or network enablement. Its downgrade executes SQL inside the migration and proceeds only when every registry and association table is empty and no Provider/Model/Capability record exists.
2. **Migration B — Credential security:** add `CredentialRecord`, every explicit envelope field, `CredentialGrant`, the three lifecycle states, replacement lineage, active-grant partial unique index, state/ciphertext checks, registry FKs, and all `RESTRICT` relationships. Its in-migration downgrade SQL requires `CredentialRecord=0` and `CredentialGrant=0`, with no active/revoked/replaced credential or historical replacement lineage.
3. **Migration C — Policies, budget, invocation, and ledgers:** add `UserProviderPreference`, `ProjectModelPolicy`, `ProjectModelPolicyProvider`, `ProjectModelPolicyModel`, `ProjectModelPolicyCapability`, and the retained `ProjectModelPolicyCredential` association when credential allowlisting is implemented; each association has explicit unique constraints, lookup indexes, and `ON DELETE RESTRICT` FKs with no orphan rows. It also adds user/project budget policies/counters/reservations, `InvocationRequest`, `InvocationAttempt`, the single-active-attempt index, exact idempotency/canonicalization/sentinel constraints, and append-only audit/event/usage/cost ledgers. Before adding the `PaintProject.id` zero-UUID check, upgrade SQL proves no existing project uses the sentinel. Downgrade SQL requires `ProjectModelPolicy`, `ProjectModelPolicyProvider`, `ProjectModelPolicyModel`, `ProjectModelPolicyCapability`, retained `ProjectModelPolicyCredential` when present, `UserProviderPreference`, `UserBudgetPolicy`, `ProjectBudgetPolicy`, `BudgetCounter`, `BudgetReservation`, `InvocationRequest`, `InvocationAttempt`, every usage/cost ledger, and every AI audit/event table to be empty; any row fails closed before destructive DDL and leaves the schema unchanged. It also confirms no remaining row references Migration A or B objects; Migration A may not delete `CapabilityDefinition` while any later Policy association remains.
4. **Migration D — Fake Fixture enablement:** insert only exact Fake Provider, Fixture Model, and Capability rows. It inserts no Credential, secret, Invocation, usage, or cost record, and the feature flag defaults off. Downgrade SQL first checks whether any Credential, Policy, Attempt, Usage, Cost, or Audit row references those exact fixture identities; any reference fails closed, otherwise only the exact fixture rows are deleted.

All downgrade gates are SQL executed by the migration itself, not application-only checks. A protected-data result exits non-zero before destructive DDL and leaves schema/data unchanged. Each revision requires independent upgrade/downgrade verification. Destructive retention handling requires a future separately approved purge design.

Schema/application rollout order is frozen:

1. with the Phase 3A feature flag off, execute Migration A;
2. execute Migration B;
3. execute Migration C;
4. execute Migration D;
5. deploy application code that understands the new schema but keeps Phase 3A off by default;
6. run schema/import/focused smoke checks;
7. enable the Fake Fixture flag only in `development`/`test`; and
8. keep `staging`/`production` disabled.

All four migrations are additive. The old application must continue to ignore the new tables throughout migration. They do not backfill invented credentials/invocations/audit, alter existing PaintPilot semantics, or generalize `PaintProject`, `ImageSet`, or `RegionSet` into an AI object. This architecture Candidate creates no migration.

### Cross-contract consistency matrix

| Invariant | Frozen contract |
| --- | --- |
| Project-scoped Credential | Requesting-user ownership **and** an active exact project Grant are always required; ownership/access never replaces Grant. |
| Projectless Credential | Requesting user may use only their own saved/request-local credential; no project Grant is required. |
| Lifecycle linearization | Admission, Grant, Revoke, Replace, user deactivation, project archival, and membership mutation share section 7's global lock order and commit-defined race outcomes. |
| Budget policy/counter order | `UserBudgetPolicy` precedes `ProjectBudgetPolicy`, and `UserBudgetCounter` precedes `ProjectBudgetCounter`, in the one global lock order. |
| Budget-policy linearization | Admission locks current Policy rows before counters; Policy mutation and Admission linearize through database locks/revisions, so stale cache cannot admit. |
| Idempotency replay | Replay returns the original pending-or-later invocation and never creates another Attempt or Reservation. |
| Retry identity | Retry stays under the original invocation, waits for definitive failure, and performs fresh Admission/reservation. |
| Active Attempt | The partial unique index and service transaction allow at most one `created`/`admitted`/`running` Attempt per invocation. |
| Uncertain outcome | `outcome_unknown` blocks automatic retry; dispatched budget remains held for governed reconciliation. |
| Reservation release | A `dispatch_committed` Reservation is never released merely because a process timed out or crashed. |
| Currency reduction | First Slice uses only `FIXTURE_CREDITS`; an Invocation aggregates only same-currency Attempts and fails on mismatch. |
| Credential lifecycle | `revoked` and `replaced` both require cryptographic erase; there is no separate lifecycle state for erase. |
| Registry lifecycle | Provider/Model/Capability definitions are disabled/retired, never physically deleted; all historical FKs are `RESTRICT`. |
| Project capability allowlist | `ProjectModelPolicyCapability` references `CapabilityDefinition` with `ON DELETE RESTRICT`; it limits capability choice only and never grants Credential use. |
| Project-scoped Credential authorization | An active exact Grant remains necessary even when a Project Policy credential allowlist contains the Credential. |
| Registry retirement history | Registry retirement blocks new selection without changing historical Attempt or Audit facts. |
| Migration lineage | A → B → C → D is linear, additive, SQL-gated on downgrade, and deployed with the feature flag off. |
| Migration C policy associations | Migration C creates every Project Policy association/FK, and its downgrade SQL covers every Policy association. |
| First Slice boundary | Fake/Fixture-only: no real Provider, real key, real fee, fallback, binary invocation, resident background task, or outbound Provider network call. |

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

The first Slice does not expose a generic raw prompt endpoint for a real Provider. Its fake invocation accepts a fixture-safe, bounded JSON contract payload, rejects raw binary/multipart invocation, and returns a synthetic result marked as such.

## 10. Frontend information architecture

The UI remains an authenticated, image-first operational workbench. It must not introduce glowing AI decoration, gradient-heavy cards, fake metrics, or marketing navigation. Human visual acceptance is required before key pages are considered complete.

### Platform pages

| Page | Entry and contents |
| --- | --- |
| Models & Providers | Account/workspace navigation; Provider cards list adapter/capabilities/catalog freshness/availability and model list with unknown/unsupported states. No raw endpoint editing in Slice 1. |
| Credentials | Account settings; list alias/Provider/last four/fingerprint/status/last validation, add temporary test, explicit save toggle, warning/confirmation, replace, revoke, and history-safe empty/error states. The secret input is `type=password`, unprefilled, never copied to URL/storage, cleared after submit, and has no reveal-after-save behavior. |
| Usage & Audit | Account/project-filtered timeline with Provider/model/capability/status/cost state, safe request ID, date/page filters, empty state, and no raw prompt/key data. First Slice labels `FIXTURE_CREDITS` as simulated usage, never real expense. |
| Knowledge Base | Reserved navigation/data contract only for Phase 3C; no page implementation in Slice 1. |

### PaintPilot project pages

`AI Model Policy` belongs beside project settings/access rather than inside the image/region editor. It surfaces allowed Providers/capabilities, selected model/credential alias, manual-ID rule, per-call budget, fallback default, and paid-call confirmation. Later `Vision Analysis Task`, `Paint Plan Draft`, and `Cost and Audit` are project workbench views, but only policy and safe synthetic audit are in the first Slice.

Form errors must map the stable server error code to bilingual copy while preserving field focus and user-entered non-secret selections. On narrow screens, secret fields and destructive actions remain single-column, controls have explicit labels, status does not rely on color alone, provider/model identifiers wrap without truncating the value needed for a decision, and confirmation text names the exact Provider/model/credential alias/budget.

## 11. First implementation Slice

The maximum-safe implementation batch is:

1. provider and capability registries with only a Fake/Fixture adapter;
2. model/catalog metadata and conservative capability resolution;
3. projectless temporary credential handling plus saved-credential persistence using the frozen AEAD/envelope contract and a development/test file-only fixture key provider, with no real KMS choice;
4. user defaults, owner-governed project policy, credential grant relation, cumulative budget counters/reservations, and safe preview resolver;
5. invocation request/attempt/reservation/audit/usage/cost persistence with domain canonicalization, exact idempotency, one-active-Attempt, dispatch/recovery, `FIXTURE_CREDITS`, and fake-only execution contracts;
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
- owner/reviewer/member/missing-project access has non-disclosing responses; project-scoped use requires requesting-user ownership and an exact active Grant, while policy/invocation queries remain project scoped;
- real PostgreSQL concurrency proves Admission/Grant/Revoke/Replace/user-deactivation/project-archival/membership linearization, retry re-admission, grant revision conflicts, global lock order, and zero Adapter calls on failed/rolled-back admission or dispatch;
- unified lock-order tests prove `UserBudgetPolicy` then `ProjectBudgetPolicy`, followed by `UserBudgetCounter` then `ProjectBudgetCounter`, for concurrent Admission and with no policy/counter reverse order;
- real PostgreSQL concurrency proves both UserBudgetPolicy-mutation/Admission and ProjectBudgetPolicy-mutation/Admission races, rejects stale-policy-revision cache admission, preserves an already committed Reservation when Admission wins, and re-evaluates new retry/fallback admission under a Policy mutation that wins first;
- a model without a proven required capability returns a structured error with zero fake-provider calls;
- concurrent reservations cannot overspend invocation/user/project limits; expired never-dispatched reservations recover safely; dispatched uncertainty retains funds; unknown price is rejected unless explicitly confirmed with a non-zero reservation; sequential retry and late receipts reconcile into the append-only `FIXTURE_CREDITS` total;
- exact invocation idempotency distinguishes user/product/project/family scope, rejects payload conflicts and cross-project replay, uses `phase3a-v1` canonicalization and immutable Artifact identity, protects the zero-UUID sentinel, and never duplicates Attempt/Reservation on replay;
- the database prevents more than one active Attempt; every legal and illegal aggregate transition plus cancel/completion/late-result races preserves one immutable terminal outcome and same-Invocation `final_attempt_id`;
- retries form distinct sequential attempts; First Slice fallback creation is rejected; post-dispatch uncertainty does not auto-retry; automatic credential/Provider/model escalation is rejected;
- custom Provider URLs are rejected before any resolver/adapter network call;
- Provider raw errors, Authorization headers, and fake secrets are redacted from logs/audits/error details;
- all four linearly dependent migrations independently upgrade/downgrade, enforce Registry `RESTRICT`, grant/lineage/envelope/sentinel constraints, and refuse destructive downgrade through in-migration SQL when protected history exists;
- `ProjectModelPolicyCapability` rejects duplicate policy/capability pairs, rejects physical CapabilityDefinition deletion while referenced, rejects retired capability selection for a new Policy or Invocation, preserves historical Attempt snapshots after retirement, verifies ProjectModelPolicy deletion/physical-deletion `RESTRICT` behavior, fails Migration C downgrade when a capability association exists, and proves that a capability allowlist never substitutes for a CredentialGrant; and
- frontend contract parsing, bilingual keys, secret-input clearing, no storage persistence, destructive confirmation, narrow viewport behavior, and safe error states pass.

No real key, Provider endpoint, paid token, browser screenshot containing a key, or external Provider test belongs in Phase 3A evidence.

## 13. Risks and explicit non-goals

Principal-string versus internal-user-ID ownership must be reviewed carefully at every bridge to `PaintProject`. Production KMS selection/operations, audited implementation of the mandatory safe transport, real-Provider pricing accuracy and terms, exact audit-retention duration, and use of private image input require later approvals. The frozen encryption, admission, budget, idempotency, state, and deletion contracts in this document MUST NOT be weakened while making those later choices. The ability to display a Provider definition is not evidence that it is configured, safe to call, or affordable.

This document does not authorize an AI feature, a Provider selection, a cloud KMS, an outbound network exception, a migration, a secret, a paid API request, a public deployment, Arcana, RAG, retrieval, model training, billing, or changes to PaintPilot business objects/workflow.
