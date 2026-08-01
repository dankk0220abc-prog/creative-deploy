# ADR-0008 — Governed Identity, Authorization, and Private Storage

Status: Candidate for independent review<br>
Date: 2026-07-31<br>
Candidate revision: `2b1c4d5e6f70`

## Context

The sealed PaintPilot domain workflow already had private local image storage and a
single configured development Principal. Phase 2A-1 supplied a production-built local
artifact, but deliberately rejected that Principal and local filesystem storage in
production. Phase 2B-1 is authorized to close the identity, project authorization,
private S3-compatible storage, and least-privilege database-role gaps without changing
the workflow state machine.

The system must remain provider-neutral, must not put bearer tokens in browser storage,
must not expose object-store addresses, and must not convert mutable profile claims into
authorization keys. Development and CI need a reproducible local provider and object
store, while production configuration must fail closed.

## Decision

1. Use OIDC Authorization Code with PKCE. The backend owns discovery, code exchange,
   signature and claim validation, callback consumption, and session creation. The
   browser receives only opaque cookies.
2. Identify one external Principal by the unique pair `(issuer, subject)` and map it to
   a stable internal `user_accounts.id`. Email and display name are profile snapshots,
   never authorization keys.
3. Store one-time OIDC flow state and opaque session hashes in PostgreSQL. Bind each
   flow to state, nonce, PKCE verifier, browser cookie, expiry, and one-time consumption.
   Rotate an existing session at login and revoke it at logout.
4. Use a double-submit CSRF token bound by a server-side hash for state-changing
   requests. Production cookies use the `__Host-` prefix, `Secure`, `HttpOnly` for the
   session, explicit `SameSite`, and path `/`.
5. Keep project ownership on the existing `paint_projects.owner_principal_id`.
   OIDC-created projects store the stable internal user ID. Add only explicit
   `reviewer` memberships for existing users; project creation grants ownership by
   construction and does not create a redundant Owner membership row.
6. The API is the authorization boundary. Owners can mutate their projects and manage
   reviewer membership. Reviewers can read assigned projects and private objects and
   can use only the already-existing human review operations. Denied project and object
   access preserves the product's safe 404 semantics.
7. Add an S3-compatible server-only adapter. It verifies a private ACL, refuses bucket
   policies, uses immutable conditional object writes, verifies size and SHA-256
   metadata, and returns provider-neutral receipts. It has no public-URL or presigned-URL
   method.
8. Keep browser image delivery on the authenticated project object-content API. The API
   streams the object and never serializes bucket, key, credential, endpoint, or signed
   query data.
9. Add a dry-run-by-default migration tool for legacy local objects. Execute mode copies,
   verifies checksum/size, conditionally updates the exact database row, supports
   idempotent resume, and never deletes the source file.
10. Add distinct PostgreSQL `migrator` and `runtime` roles. The migrator owns DDL; the
    runtime receives only schema usage plus table DML and sequence usage. The runtime
    receives no CREATE, ALTER, DROP, role, database, superuser, replication, or RLS
    bypass capability.
11. Production requires explicit `DATABASE_URL`, OIDC, HTTPS issuer/discovery/redirect,
    a confidential client secret, private S3 over HTTPS, and pre-created bucket
    configuration. Demo identity, local storage, insecure S3, application bucket
    creation, and OIDC backchannel rewriting are refused in production.
12. The repository-owned OIDC provider and digest-pinned MinIO exist only in the
    synthetic local/CI artifact profile. They are not deployment selections or real
    identity/storage accounts.

## Data and Migration

Revision `2b1c4d5e6f70`, child of `7f3a2b9c4d1e`, adds:

- `user_accounts`
- `external_identities`
- `project_memberships`
- `oidc_login_flows`
- `auth_sessions`

It widens the existing `image_assets.storage_provider` constraint from
`local_filesystem` to `local_filesystem | s3`; existing rows and storage keys are not
rewritten.

Downgrade is reversible only while no Phase 2B-1 governed fact or S3 reference exists.
If any user, identity, membership, flow, session, or S3-backed asset exists, downgrade
raises SQLSTATE `55000` rather than delete data. Operators must first make a separately
authorized, evidence-backed data disposition; this Phase supplies no deletion path.

## Threat and Security Notes

- State, nonce, PKCE, browser binding, callback one-time use, issuer, audience, RS256
  signature, expiry, not-before, issued-at, subject, and normalized profile claims are
  validated.
- `X-Principal`, client user IDs, emails, and client role claims are not trusted.
- Raw session tokens, CSRF tokens, access tokens, refresh tokens, OIDC client secrets,
  object credentials, and database passwords are not persisted in browser storage or
  emitted in application responses/log evidence.
- Revocation and membership removal are checked at the server on the next request;
  button visibility is only UX.
- S3 publication failure cannot be reported as upload success. Compensation is bound to
  the exact receipt and refuses to act when identity or database references cannot be
  proven.
- There is no public/signed URL, retention rule, automatic deletion, owner transfer,
  workflow-state change, AI, OCR, Agent, or RAG capability in this decision.

## Consequences

PaintPilot now has a provider-neutral production-capable identity and storage boundary,
but this Candidate is not production-ready. A real provider, secrets manager, domain/TLS
termination, bucket policy/IAM design, backup/restore, monitoring, retention decision,
and operations ownership still require separate selection and independent review.

The synthetic provider proves protocol behavior, not interoperability with a particular
enterprise IdP. MinIO proves the S3-compatible contract, not a managed-service
deployment.

## Rejected Alternatives

- Storing access/refresh tokens in `localStorage` or exposing them to React.
- Authorizing by email, display name, frontend-supplied role, or proxy headers.
- Encoding project roles into long-lived browser tokens.
- Returning S3, MinIO, public, or presigned object URLs.
- Falling back to Demo identity or local filesystem when production configuration is
  incomplete.
- Running migrations and the API as one PostgreSQL superuser.
- Deleting legacy local objects after copy or adding retention/cleanup policy.
- Changing the sealed PaintPilot workflow state machine in an infrastructure phase.
