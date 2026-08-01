# PaintPilot Private Object Storage Contract v0.1

Status: Phase 2B-1 remediated Candidate for independent review<br>
Date: 2026-08-01<br>
Provider name: `s3`

## 1. Boundary

ImageAsset metadata remains in PostgreSQL. Object bytes live behind a provider-neutral
storage adapter. Browser clients never address S3 directly; they use the existing
authenticated and project-authorized content API.

The supported production provider value is `s3`. The existing
`local_filesystem` adapter remains development/test-only and is refused in production.

## 2. Required Configuration

- absolute S3-compatible endpoint
- region
- normalized private bucket name
- access key ID and secret access key
- address style choice
- private staging root

Production requires HTTPS, forbids `S3_ALLOW_INSECURE_HTTP`, and forbids application
startup bucket creation. Bucket provisioning and credential/IAM ownership remain an
operator responsibility.

Local/CI MinIO uses only synthetic credentials, a digest-pinned image, a loopback-only
Web endpoint, and an internal Docker network. MinIO itself is not published to the host.

## 3. Privacy Invariants

At adapter initialization:

- bucket access must succeed;
- every ACL grant must be a canonical-user grant;
- a public/group ACL is refused;
- any non-empty bucket policy is refused in this conservative v0.1 contract.

At object publication:

- key format is controlled by the adapter and rejects absolute paths, traversal,
  backslashes, and unknown extensions;
- the local staging directory is mode 0700 and files are exclusive mode 0600;
- staged file identity, size, and location are revalidated;
- `If-None-Match: *` prevents replacement of an existing immutable key;
- the request carries content type, content length, SHA-256 checksum, and SHA-256
  metadata;
- a subsequent HEAD must match expected size and SHA-256 metadata before success.

The adapter deliberately has no public URL, browser URL, or presign operation. API and
schema responses do not serialize bucket, endpoint, credential, internal key, ETag,
VersionId, or `X-Amz-*` data.

## 4. Database/Object Contract

Each ImageAsset retains:

- project ownership through its existing project relation;
- `storage_provider`;
- controlled `storage_key`;
- SHA-256;
- byte size;
- declared/detected content type/format and existing validation facts.

The existing quality, rights attestation, role, current/history, idempotency, workflow,
and immutable-replacement contracts remain authoritative.

Publication returns a provider-neutral receipt containing the exact key, size, checksum,
provider, and optional provider identity fields for server-side compensation only.
Database failure must not be returned as upload success. Compensation may act only on
the exact unreferenced receipt and refuses when object identity or database references
cannot be proven.

## 5. Reads and Denials

Object bytes are read only after API authentication and project Owner/reviewer
authorization. The API streams the body with controlled content headers and `no-store`.

- Owner and assigned reviewer: may read the project's object.
- Authenticated non-member: safe 404 indistinguishable from a missing project/object.
- Anonymous or expired/logged-out session: 401.

The bucket is inaccessible without S3 credentials; browser requests never receive those
credentials.

## 6. Legacy Copy Tool

`make image-storage-migrate` invokes the migration tool in dry-run mode by default.
It selects exact rows still marked `local_filesystem`, opens the controlled local key,
recomputes SHA-256 and size, and reports verification counts without database/object
mutation.

Execute mode is deliberately explicit:

```bash
CREATIVEDEPLOY_ENV_FILE=<complete-private-env-file> \
uv run --project apps/api \
python -m creativedeploy_api.tools.migrate_image_storage --execute [--limit N]
```

The tool:

1. copies to the same controlled key with conditional non-replacement;
2. treats an already-present exact size/checksum/content-type object as an idempotent
   resume;
3. after every write, performs a new destination HEAD and verifies existence, exact
   size, controlled SHA-256 metadata, and content type against the source facts;
4. updates only the exact matching asset row from `local_filesystem` to `s3`;
5. never deletes the source file.

An ordinary ETag is provider identity only and is never treated as a universal content
checksum. A destination HEAD failure or any size/checksum/type mismatch is an explicit
retryable copy failure before the database update. An already-present exact object may
resume; an already-present mismatch is never overwritten or accepted. If the row
changed concurrently or the database update fails, the original file remains and the
verified destination remains a clearly identifiable resume/reconciliation candidate;
the tool does not fabricate a migration success, delete uncertain data, or weaken the
conditional immutable-write contract.

## 7. Migration and Rollback

Alembic Revision `2b1c4d5e6f70` only widens the storage-provider constraint; it does not
copy objects or rewrite existing rows.

Downgrade to `7f3a2b9c4d1e` is allowed only when no S3 ImageAsset and no Phase 2B-1
governed identity fact exists. Otherwise SQLSTATE `55000` refuses the downgrade. There
is no automatic reverse copy or destructive deletion.

## 8. Excluded Capabilities

- public ACL or policy
- public URL or signed/presigned URL
- direct browser S3 upload/download
- retention, lifecycle, automatic cleanup, or destructive migration
- cross-region replication, production backup, legal hold, or disaster-recovery policy
- AI, OCR, Agent, RAG, or visual-model processing

These exclusions are security boundaries, not missing fallbacks.
