# ADR-0009 — Staging Operations and Production Hardening Boundary

Status: Candidate for independent review<br>
Date: 2026-08-01<br>
Baseline: `511e42ecb2adccc55e75cb4d801181206b1b337a`<br>
Schema revision: `2b1c4d5e6f70` (unchanged)

## Context

Phase 2B-1 established provider-neutral OIDC, private S3-compatible storage,
API-only object delivery, and separate PostgreSQL runtime/migrator roles. It did
not supply a TLS ingress, file-secret contract, dependency-complete readiness,
or a coordinated PostgreSQL/object backup and restore procedure.

Phase 2B-2 must prove those operational boundaries locally and in CI without
selecting a real cloud, identity provider, secret manager, certificate issuer,
domain, monitoring vendor, retention policy, or public deployment.

## Decision

1. Use one minimal Compose staging topology: a TLS-only public reverse proxy,
   production-built Web, API, one-shot migration and database-role jobs,
   PostgreSQL, private MinIO, and the repository-owned synthetic OIDC provider.
   PostgreSQL, MinIO, OIDC, and API are not published. The only host bindings are
   two configurable loopback ingress ports.
2. Keep `app` and `data` networks internal. API starts only after MinIO and OIDC
   are healthy and role provisioning, migration, and final grants complete.
   Web and TLS ingress then wait for API/Web health.
3. Terminate TLS at the outer proxy. HTTP redirects to the exact configured
   HTTPS origin. The outer proxy overwrites forwarded host/protocol facts, the
   API rejects `Forwarded`, and the application requires exact `PUBLIC_ORIGIN`,
   trusted Host, OIDC callback, and unsafe-request Origin agreement.
4. Use `Secure` `__Host-` session/CSRF cookies on the staging HTTPS path. The
   session cookie is HttpOnly; both use explicit SameSite. Emit HSTS only from
   the HTTPS proxy, never from the ordinary local HTTP artifact.
5. Accept each operational Secret from exactly one direct setting or one
   `*_FILE` setting. Staging mounts separate read-only files for the runtime
   database URL, migrator/admin material, OIDC secret, S3 access pair, TLS
   certificate, and TLS key. The application rejects missing, blank, symlinked,
   unstable, overlarge, executable, or group/world-writable secret files.
6. Emit allowlisted JSON operational logs with one end-to-end request ID. Log
   the normalized path but never query strings, request bodies, cookies,
   credentials, exception representations, or configuration values. Liveness
   proves process availability; readiness independently probes PostgreSQL,
   private storage, and identity metadata with bounded timeouts.
7. Require API quiescence before backup. Within a repeatable-read, read-only
   PostgreSQL transaction, export all fourteen business tables, deferred
   self/cyclic pointers, the schema catalog, Alembic revision, and referenced
   object inventory. Then copy each private object and verify size, SHA-256,
   content metadata, and database/object one-to-one correspondence. Publish the
   backup only by atomically renaming a complete partial directory with a
   manifest covering every file.
8. Restore only when both explicit temporary-restore consent is present and the
   target database name matches `^p2b2r_...$`. Validate format, every file hash,
   application version, Alembic revision, schema hash, and bucket freshness
   before mutation. Restore verified objects and database rows into a fresh
   environment, repair deferred pointers inside the database transaction, then
   re-export and byte-compare all governed data and re-verify every object.
   Exact completed retries are allowed; mismatched partial state fails closed.
9. Treat application rollback and data recovery separately. Roll application
   containers back to a previously reviewed immutable image while retaining the
   compatible schema. Never restore over an existing environment. When data
   recovery is required, restore a selected immutable backup into a new
   temporary stack, validate it, and promote only through a separately
   authorized cutover. This Phase supplies no destructive in-place restore.
10. Use one `RUN_ID` for project, credentials, database, bucket, labels, ports,
    temporary roots, and cleanup ownership. The canonical drill creates a
    source stack, takes a coordinated backup, removes it, restores into a new
    stack, verifies authorization/private bytes/history, tests exact retry and
    tamper refusal, and removes only those two attempts.

## Security and Failure Consequences

- A dependency failure makes readiness fail while liveness remains available.
- Migration failure prevents API startup. Secret and origin disagreement fail
  startup before serving traffic.
- A backup never represents unreferenced or missing private objects as success.
  Restore never accepts an unmanifested, missing, resized, or checksum-changed
  file.
- The local self-signed certificate and synthetic secrets live only below the
  attempt's temporary root. They are not certificate/provider selections.
- The measured local drill RPO is zero only because writes are quiesced. Its
  small synthetic RTO is evidence of the mechanism, not a production SLO.
- No log retention or automatic deletion policy is implemented. Operators may
  route structured stdout to a future selected platform under a separately
  approved policy.

## Rejected Alternatives

- Kubernetes, Terraform, or a cloud-specific framework for this local/CI proof.
- Trusting arbitrary proxy headers, wildcard hosts/origins, or relative OIDC
  callback derivation.
- A shared `.env` containing staging/production secrets or secrets in image
  layers, build arguments, frontend bundles, logs, or CI output.
- Database-only backup, live best-effort object copying, or destructive
  in-place restore.
- Public or signed object URLs, lifecycle/retention deletion, paid monitoring,
  real cloud/domain provisioning, and AI/OCR/Agent/RAG integration.

## Status Boundary

This decision is an uncommitted implementation Candidate. It is not independent
approval, Git sealing, a production-ready declaration, a real-provider
selection, or permission to deploy publicly.
