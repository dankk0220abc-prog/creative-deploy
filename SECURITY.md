# Security policy

CreativeDeploy / PaintPilot is not production-ready and currently has no public
deployment. Report suspected vulnerabilities privately to the repository owner
through GitHub's private security reporting or another owner-approved private
channel. Do not open a public issue containing credentials, session material,
private image data, object keys, database URLs, stack traces, or reproduction data
from a real account.

## Supported state

Security fixes apply to the current `main` branch and must pass a focused review
before sealing. Historical phase snapshots and unsealed Candidates are evidence,
not supported releases. There is no published version or public security SLA.

## Sensitive-data rules

- Never commit `.env`, real OIDC client secrets, database credentials, object-store
  credentials, TLS private keys, signing keys, session cookies, tokens, or private
  user images.
- Use `.env.example` only for non-secret local examples and placeholders.
- Keep staging certificates, Secret files, backups, restore data, and browser
  profiles outside the repository in exact, owner-controlled paths.
- Preserve private API-only object delivery. Do not add public or signed image URLs.
- Redact filenames, IDs, account claims, request bodies, infrastructure addresses,
  and private content from reports unless the owner explicitly authorizes them.

## Operational boundaries

The repository includes a synthetic loopback-only staging topology and a
fresh-environment backup/restore drill. They do not select real providers, define
production retention or RPO/RTO, authorize destructive in-place restore, or prove
production readiness. Follow `docs/runbooks/staging-operations.md` and preserve all
fail-closed checks.

AI, OCR, Agent, RAG, automated image analysis, and automated Polygon generation
remain unauthorized and outside the security support boundary.
