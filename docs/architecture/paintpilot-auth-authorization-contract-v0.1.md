# PaintPilot Authentication and Authorization Contract v0.1

Status: Phase 2B-1 remediated Candidate for independent review<br>
Date: 2026-08-01<br>
Applies to: OIDC identity, browser sessions, CSRF, Owner/reviewer access

## 1. Identity Boundary

The stable internal authorization identity is `user_accounts.id` (UUID). One external
identity is uniquely keyed by normalized, validated OIDC `issuer + subject`.

`email`, `display_name`, `email_snapshot`, and `display_name_snapshot` are mutable
profile facts. They are never project ownership, reviewer assignment, session lookup,
or authorization keys.

The application does not accept `X-Principal`, frontend user IDs, email addresses, or
client-supplied role claims as authentication.

## 2. OIDC Protocol

Required flow: Authorization Code with S256 PKCE.

Login:

1. `GET /api/v1/auth/login?return_to=<local-path>` validates the return path.
2. The backend loads provider discovery, requires the configured issuer and S256 support,
   generates state/nonce/verifier/challenge/browser binding, stores only controlled
   flow data in PostgreSQL, and redirects to the provider.
3. A short-lived HttpOnly browser-binding cookie accompanies the redirect.

Callback:

1. `GET /api/v1/auth/callback` requires code, state, and the matching browser binding.
2. The backend atomically consumes an unexpired, unused state; replay is rejected.
3. Code exchange uses the stored verifier and configured confidential-client secret.
4. ID-token verification requires the discovered JWKS, RS256, exact issuer, client
   audience, valid signature, `exp`, `nbf` when present, bounded `iat`, exact nonce,
   non-empty subject, and normalized profile claims.
5. `(issuer, subject)` is resolved concurrently to one internal user. A previous browser
   session is revoked and a new opaque session/CSRF pair is created.

ID-token time validation captures the current time once for the complete operation.
`iat` is required and must be a finite numeric timestamp (booleans and non-numeric
values are refused). The token may be at most the configured clock skew in the future,
and `now - iat` may not exceed the configured maximum token age. `exp` remains required;
`nbf`, when present, is checked against the same captured time and skew. These checks do
not replace issuer, audience, signature, nonce, or subject validation. Every validation
failure uses the same non-sensitive authentication error and does not log the token,
signature, client secret, or full claims.

Provider discovery, issuer metadata, and token validation fail closed. The login page
shows an explicit provider-unavailable or sign-in-failed state and offers retry; it does
not substitute a Demo Principal.

## 3. Browser Session and CSRF

- The session token is opaque and random; PostgreSQL stores only SHA-256.
- The CSRF token is random; PostgreSQL stores only SHA-256.
- Session status: `GET /api/v1/auth/session`.
- Logout: `POST /api/v1/auth/logout`, protected by CSRF, revokes the server session and
  expires both cookies.
- Expired, revoked, missing, or unknown sessions are anonymous immediately.
- Login rotates any prior session to prevent fixation.
- State-changing API requests must send the CSRF cookie value in `X-CSRF-Token`; the
  server verifies cookie/header equality and the session-bound hash.
- Browser code does not persist access tokens, refresh tokens, session tokens, or roles
  in `localStorage`.

Cookie policy:

| Environment | Session | CSRF | Flow |
|---|---|---|---|
| production | `__Host-paintpilot_session`, Secure, HttpOnly, SameSite=Lax | `__Host-paintpilot_csrf`, Secure, readable, SameSite=Strict | `__Host-paintpilot_oidc_flow`, Secure, HttpOnly, SameSite=Lax |
| local/test | loopback-safe names, HttpOnly session/flow | loopback-safe readable CSRF | short-lived browser binding |

All cookies use path `/`; production has no Domain attribute.

## 4. Project Roles

Roles are computed per request from server-side facts:

- `owner`: the authenticated internal user ID equals the project's owner ID.
- `reviewer`: one active `project_memberships` row exists for the project and user.

The only membership role is `reviewer`. The unique key
`(paint_project_id, user_id)` makes repeated/concurrent assignment converge on one row.
Only an Owner can list assignable users, list memberships, assign, or remove a reviewer.
The reviewer must already have an OIDC-created internal user.

## 5. Capability Matrix

| Capability | Owner | Assigned reviewer | Authenticated non-member | Anonymous |
|---|---:|---:|---:|---:|
| list own/assigned projects | yes | yes | empty | 401 |
| read project and private images | yes | yes | safe 404 | 401 |
| create project | yes | no | no | 401 |
| upload/replace/fork/save/submit | yes | no | safe 404 | 401 |
| existing human review actions | yes, as previously allowed | yes, as previously allowed | safe 404 | 401 |
| manage reviewer membership | yes | safe 404 | safe 404 | 401 |

This Phase does not change any workflow-state predicate. Role checks compose with the
existing service policy; they do not bypass it.

## 6. Non-Disclosure Semantics

- Authenticated users without project membership receive the product's uniform safe 404
  for project, membership, image metadata/content, and region resources.
- Object existence, storage provider, bucket, key, endpoint, credential, and checksum
  implementation details are not exposed by denial responses.
- Anonymous API access receives 401 and does not initiate object-store access.
- Membership removal is effective on the next API request, including from an already
  authenticated session.

## 7. Production Configuration

Production startup requires:

- `IDENTITY_PROVIDER=oidc`
- absolute HTTPS issuer, discovery endpoint, and redirect URI
- client ID and client secret
- explicit database URL
- exact trusted hosts

OIDC ID-token freshness has repository defaults and fail-closed bounds:

- `OIDC_ID_TOKEN_MAX_AGE_SECONDS=300`, allowed range `60..900` seconds;
- `OIDC_CLOCK_SKEW_SECONDS=30`, allowed range `0..60` seconds.

Empty, negative, non-numeric, or out-of-range values are configuration errors. The
production-style artifact profile pins the exact documented `300`/`30` policy rather
than inheriting a hostile process environment.

Production refuses Demo identity, HTTP issuer/redirect/discovery, local backchannel
rewriting, missing client configuration, and local filesystem storage.

The repository-owned local OIDC provider is permitted only for synthetic development,
tests, browser acceptance, and CI. It is not a production identity selection.

## 8. Audit and Residual Risk

The database preserves stable identity, membership assignment actor/time, login-flow
consumption, and session revocation/expiry. It does not store provider access or refresh
tokens.

Independent review must still assess provider interoperability, key rotation/cache
behavior, clock-skew policy, session revocation operations, real secret management, and
production incident response before deployment.
