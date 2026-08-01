# Staging Operations Runbook

This runbook operates a synthetic, loopback-only staging-style environment. It
does not deploy publicly and is not a production provider selection.

## Preconditions and Ownership

- Run from `/Users/danke/Developer/CreativeDeploy` with Docker Desktop, uv,
  OpenSSL, curl, Node/Corepack, and pnpm available.
- Choose a fresh `RUN_ID` matching `^[a-z0-9][a-z0-9_]{0,39}$` and two unused
  loopback ports. Never reuse another live attempt's ID or resources.
- Keep certificate/secret/backup roots in a private external path such as
  `/tmp`. Never place them below Git or print their contents.
- The local certificate is self-signed and synthetic. A real deployment mounts
  files supplied by its selected certificate automation without changing the
  container contract.

Example local attempt:

```bash
export RUN_ID=staging_20260801_a1
export STAGING_HTTP_PORT=18081
export STAGING_HTTPS_PORT=18443
export STAGING_SECRET_ROOT=/tmp/creativedeploy-phase2b2-${RUN_ID}-secrets
export STAGING_BACKUP_ROOT=/tmp/creativedeploy-phase2b2-${RUN_ID}-backups
```

## Prepare, Validate, Deploy

```bash
make staging-secrets
make staging-config
make staging-build
make staging-up
```

`staging-secrets` creates twelve independent synthetic files with private
permissions and never prints their values. `staging-config` fails unless only
the two loopback ingress ports are published, data/app networks are internal,
runtime services are non-root/read-only/capability-dropped, all secrets use
files, and migration/role ordering is intact.

Deployment order is PostgreSQL → role provision → migration → role grant → API
with MinIO/OIDC ready → Web → TLS proxy. A migration or grant failure prevents
API service. The application container uses a production Uvicorn command with
no reload or development server.

Verify without bypassing the generated CA:

```bash
curl --head "http://localhost:${STAGING_HTTP_PORT}/paintpilot/projects/example"
curl --cacert "${STAGING_SECRET_ROOT}/tls_certificate.pem" \
  "https://localhost:${STAGING_HTTPS_PORT}/health/ready"
```

Expected: exact 308 HTTPS redirect; HTTPS 200 with database, storage, and
identity checks all `ok`; HSTS only on HTTPS; one `X-Request-ID`; SPA deep links
serve the production build. PostgreSQL, MinIO, OIDC, and API have no host port.

## Isolated Local Browser Trust

The synthetic self-signed localhost leaf is not system-trusted. When a real
browser acceptance run is authorized, trust only that attempt's certificate in
one dedicated browser process/profile. Do not modify macOS Keychain/system CA
trust and do not use `--ignore-certificate-errors`.

For Chrome on macOS, compute the current leaf's public-key pin without reading
or printing its private key:

```bash
export BROWSER_PROFILE_ROOT=/tmp/creativedeploy-phase2b2-${RUN_ID}-chrome-profile
mkdir -m 700 "${BROWSER_PROFILE_ROOT}"
CERTIFICATE_SPKI=$(openssl x509 \
  -in "${STAGING_SECRET_ROOT}/tls_certificate.pem" -pubkey -noout | \
  openssl pkey -pubin -outform der | \
  openssl dgst -sha256 -binary | openssl base64)

"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --user-data-dir="${BROWSER_PROFILE_ROOT}" \
  --ignore-certificate-errors-spki-list="${CERTIFICATE_SPKI}" \
  --use-mock-keychain --disable-extensions
```

The allowlist applies only to that Chrome process and only to the exact public
key. Use a fresh profile and certificate for every run. Verify browser Security
state `secure`, the exact localhost certificate, and absence of a warning page;
an SPKI flag is not itself PASS evidence. After the run, close the exact browser
process, verify its debug/listening ports and profile-owned child processes are
gone, then remove the exact profile, certificate/key, Secret, backup, and
evidence roots. Never log the private key, Cookie/token values, or Secret file
contents.

## URL and Certificate Contract

For a real hostname, configure one exact `STAGING_HOST`/port and mount a matching
certificate/key. API settings require all of these to agree:

- `PUBLIC_ORIGIN=https://<exact-authority>`
- `TRUSTED_HOSTS` containing exactly the host, never `*`
- `OIDC_ISSUER` and discovery configuration for the selected provider
- `OIDC_REDIRECT_URI=${PUBLIC_ORIGIN}/api/v1/auth/callback`
- browser `Origin` equal to `PUBLIC_ORIGIN` on unsafe API requests
- `SECURE_COOKIES=true` and `REQUIRE_CSRF_ORIGIN=true`

Do not accept `Forwarded`, wildcard origin/host, alternate callback paths, or a
certificate whose private key was copied into Git/image/build arguments.

## Secret Injection and Rotation

The API supports exactly one direct value or one file for `DATABASE_URL`,
`OIDC_CLIENT_SECRET`, `S3_ACCESS_KEY_ID`, and `S3_SECRET_ACCESS_KEY`. Staging
uses only the file form. Empty, multiline, symlinked, unstable, executable,
overlarge, or group/world-writable files fail startup.

Provider-neutral rotation procedure:

1. Create new versioned files outside Git with owner-only permissions.
2. Validate the new database/provider credential out of band without printing
   it. Keep the old version active.
3. Update the deployment secret-file reference atomically.
4. Recreate the affected one-shot job or service; never bake the value into an
   image or pass it as a build argument.
5. Require readiness and a synthetic login/private-object check.
6. Revoke the old credential only after the new service is healthy and rollback
   ownership is clear.

TLS rotation recreates only `tls_proxy`; runtime DB/OIDC/S3 rotation recreates
API and the relevant provider/job. Secret values must not enter command logs,
health output, configuration audit, browser state, or structured logs.

Backup operations additionally require `BACKUP_SIGNING_KEY_FILE` and one exact
`BACKUP_SIGNING_KEY_ID`. The signing key is mounted only into the on-demand
operations container; it is never copied into the backup, manifest, database,
image, or evidence. Rotate it manually by retaining the old key ID/key while
old backups remain restorable, creating a new owner-only key file and distinct
key ID, validating a new signed backup/temporary restore, and only then retiring
the old key under the operator's backup-lifetime policy. Missing, blank,
multiline, shorter-than-32-byte, symlinked, executable, or group/world-writable
signing key files fail closed. This phase does not select a Secret Manager.

## Coordinated Backup

Use a new immutable backup ID. The Make target stops API first, performs a
dry-run, takes the backup, and restarts API even when the operation fails:

```bash
BACKUP_ID=before_release_20260801_a1 make staging-backup
```

The backup contains schema/version facts, all fourteen business tables,
deferred pointers, database counts, application/Alembic/source revisions,
object inventory, verified private object bytes/size/SHA-256/content metadata,
and a manifest covering every file. The complete governed manifest is
canonicalized as UTF-8 JSON with ASCII escaping, recursively sorted object keys,
compact separators, and no insignificant whitespace. An independent signing
key protects that canonical form with HMAC-SHA-256 in detached
`manifest.hmac.json`; key ID, algorithm, and canonicalization identity are
covered by the signed manifest. It is published only after completion. The
backup does not contain PostgreSQL role passwords, TLS/OIDC/S3 secrets, or the
backup signing key.

Application writes are unavailable during the measured quiesce. This gives the
local drill a synthetic RPO of zero; production RPO/RTO and snapshot/storage
selection remain an operator decision.

## Temporary Restore and Recovery Drill

Restore never targets the source stack. Create a fresh attempt whose database
prefix is exactly `p2b2r` and whose backup root is the read-only selected source
location. Then:

```bash
STAGING_DATABASE_PREFIX=p2b2r \
BACKUP_ID=before_release_20260801_a1 \
make staging-restore
```

The command requires `RESTORE_TEMPORARY=true` internally, stops API, and first
verifies the detached signature before opening a database or object-store
client. Only then does it validate every file/object checksum, schema,
application and Alembic version, target name, and freshness. Every existing
destination object is read with a real streaming GET and locally hashed; HEAD,
ETag, size, content type, and metadata alone are never accepted as identity.
Every new PUT is independently re-GETed and byte-hashed before database
references commit, and the final verification re-GETs every restored object.
Failure rolls back database changes without overwriting or deleting the
existing object or source backup. Repeating the command is allowed only when
target data and real object bytes are already an exact match.

The canonical self-cleaning proof is:

```bash
RUN_ID=staging_drill_20260801_a1 make staging-drill
```

It creates synthetic Owner, Reviewer, Project, membership, workflow/history,
and private image facts; backs up; removes the source; restores into a fresh
`p2b2r_` environment; verifies identity, permissions, private bytes and history;
proves exact retry, signed-Manifest tamper refusal, and rejection of a target
object whose size/content type/metadata checksum match while its real bytes do
not; checks logs for secrets/query strings; and removes both attempts. It never
restores over a non-temporary database.

## Deploy and Rollback

Before deployment, require an immutable reviewed image set, successful staging
config/drill, verified backup, exact config/secret versions, migration
compatibility, and an operator-owned rollback point.

Deploy in the same order as `staging-up`. For application rollback, stop new
traffic, select the previously reviewed immutable API/Web/proxy image set,
recreate services without changing data, and require readiness/login/private
object smoke before restoring traffic. The current schema revision is unchanged
in Phase 2B-2.

If data recovery is needed, do not downgrade or restore in place. Keep source
and backup untouched, restore into a new isolated environment using the
procedure above, verify it, and request separate cutover authorization. This
runbook supplies no destructive promotion, retention, or backup deletion.

## Fault Diagnosis

| Symptom | Expected safe state | Operator action |
|---|---|---|
| Missing/invalid secret | service fails startup | repair the external file/reference; never add a fallback |
| Migration/grant fails | API never starts | inspect the one-shot JSON-safe/error output; fix and rerun exact job |
| PostgreSQL unavailable | readiness 503, liveness 200 | restore DB connectivity; do not route new work |
| MinIO/object failure | readiness 503, liveness 200; upload/read fails safe | repair private storage and verify inventory/checksum |
| OIDC unavailable | readiness 503; login fails explicitly | restore provider/discovery; never fall back to Demo identity |
| Wrong Host/Origin/forwarding | request 400 | correct proxy/origin contract; never widen to wildcard |
| Missing/wrong signing key, key ID, or signature | backup/restore exit 2 before storage/database access | select the exact authorized key version; never weaken or self-sign the manifest |
| Backup object mismatch | backup exit 2, no published partial | reconcile source database/object facts without deleting either |
| Restore mismatch/tamper/byte mismatch | restore exit 2 without success; database transaction rolls back | preserve evidence and existing bytes, select a valid immutable backup/new target |

Logs are structured stdout for future routing. No paid platform or retention
policy is selected here. Use request ID, event, safe normalized path, status,
duration, and dependency error code; never add bodies, query strings, cookies,
tokens, URLs containing credentials, or exception representations.

## Exact Cleanup

```bash
make staging-down
```

This removes only `creativedeploy-phase2b2-${RUN_ID}` containers, networks,
volumes, and local attempt images. After confirming the exact paths are owned by
that attempt, remove its external synthetic secret/backup roots. Never kill an
unknown port owner, prune global Docker state, delete an unowned database, or
remove another attempt's backup.

## Production Gaps

Independent review and Git sealing are still required. Real IdP/client, managed
PostgreSQL/S3/IAM, certificate automation, DNS/domain, secret provider,
deployment owner, backup store, production RPO/RTO, monitoring/on-call,
retention/legal policy, and cutover/incident authority remain unselected. No
public deployment, real secret/data, paid service, public/signed URL, retention
deletion, AI, OCR, Agent, or RAG is authorized.
