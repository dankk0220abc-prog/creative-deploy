# CreativeDeploy

[![Candidate CI](https://github.com/dankk0220abc-prog/creative-deploy/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/dankk0220abc-prog/creative-deploy/actions/workflows/ci.yml)

PaintPilot is CreativeDeploy's bilingual, image-first workbench for human-governed
repaint planning. It brings private reference images, immutable image history,
reviewer membership, deterministic readiness checks, human-authored Polygon
regions, and append-only review decisions into one workspace.

## Product tour

![PaintPilot Polygon workspace in English](docs/screenshots/paintpilot-region-workspace-en.png)

![PaintPilot Polygon workspace in Simplified Chinese](docs/screenshots/paintpilot-region-workspace-zh-cn.png)

These synthetic, non-stitched captures show the Polygon editor, an approved
immutable snapshot, and append-only history in the two supported interface
locales. They contain no private project asset or account. The UI supports English
(`en-US`) and Simplified Chinese (`zh-CN`) without translating user-entered titles,
filenames, IDs, UUIDs, hashes, or raw enum values.

## Implemented product boundary

- Create, list, reopen, and inspect server-persisted planning-only PaintProjects.
- Maintain four private immutable image roles with version history, deterministic
  file checks, human rights attestation, and append-only readiness review.
- Grant and revoke reviewer membership through server-authorized Owner controls.
- Draw and edit human-authored Polygon regions, save immutable RegionSet snapshots,
  submit exact snapshots, browse history, and record append-only human review.
- Recover explicitly from loading, empty, validation, network, storage, conflict,
  and unavailable states without substituting sample records.

AI, OCR, Agent workflows, RAG, automated image analysis, segmentation, generated
regions, paint inventory, and PaintPlan generation are not implemented or
authorized.

## Architecture

```mermaid
flowchart LR
  browser["React and Vite Web"] -->|"same-origin /api"| api["FastAPI application"]
  api -->|"opaque OIDC session and membership"| identity["Provider-neutral OIDC"]
  api -->|"governed records"| database["PostgreSQL"]
  api -->|"private API streaming only"| storage["S3-compatible object storage"]
```

The Web never receives storage credentials or public object URLs. The API owns
authorization, workflow enforcement, idempotency, persistence, and private-object
delivery. PostgreSQL and object storage remain independent durable boundaries.

## Local start

Prerequisites are Node.js 24, Corepack with pnpm 11.14.0, Python 3.13 with `uv`,
Docker Desktop, and Docker Compose. From the repository root:

```bash
make bootstrap
make db-up
make api
make web
```

`make bootstrap` creates `.env` from `.env.example` only when `.env` is absent; it
does not overwrite a private environment file. Open `http://127.0.0.1:5173`. The
development Web uses same-origin `/api` requests through the Vite proxy.

## Authentication, storage, staging, and recovery

- Local development may use the explicit configured Demo Principal and private
  local-file adapter. Both are rejected for production.
- The implemented governed boundary uses provider-neutral OIDC Authorization Code
  + PKCE, opaque HttpOnly sessions, server-side Owner/reviewer membership, and
  private S3-compatible object access through the API only.
- The repository's staging topology is synthetic and loopback-only. It is evidence
  for a deployment boundary, not a real environment or provider selection.
- Backup is quiesced and manifest-bound. Restore targets a fresh isolated
  environment; the repository does not provide destructive in-place promotion.

See the [security policy](SECURITY.md),
[local production-style operations](docs/runbooks/local-production-style.md), and
[staging and backup/restore operations](docs/runbooks/staging-operations.md).

## Quality and CI

The GitHub Actions [Candidate CI](.github/workflows/ci.yml) workflow runs on pull
requests and on `main`. It installs locked dependencies and exercises the
repository's configured checks, migration checks, artifact checks, staging drill,
and supply-chain check. Run focused local checks that match your change; common
Web checks are:

```bash
make lint-web
make typecheck-web
make test-web
make build-web
git diff --check
```

## Public source status and limitations

CreativeDeploy is a public-source repository, and the public source release is
complete under Apache-2.0. That status does not make the project production-ready.

A real identity provider, managed storage and IAM, secret management, production
domain and certificate automation, monitoring, retention, RPO/RTO, and operational
ownership have not been completed. There is no public production deployment. See
the engineering record for historical implementation and review evidence.

## Security and contributing

Read [SECURITY.md](SECURITY.md) before reporting a vulnerability, and follow
[CONTRIBUTING.md](CONTRIBUTING.md) for changes. Do not place credentials, real
customer material, or private environment files in issues, pull requests, or the
repository.

## License

Licensed under the [Apache License 2.0](LICENSE).

## Engineering history

Historical phase plans, Candidate records, focused reviews, and closure evidence
are preserved in [docs/progress/](docs/progress/). They document engineering
history and do not expand the current product or production boundary.
