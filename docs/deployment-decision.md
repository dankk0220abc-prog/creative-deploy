# Deployment decision: local-first Portfolio release

## Decision

`PUBLIC_DEPLOYMENT_NOT_REQUIRED_FOR_PORTFOLIO_COMPLETION`

The Portfolio release is complete when an evaluator can clone the repository, start the isolated synthetic Demo, understand the two product spaces, inspect the engineering evidence, and use the interview material without a Provider key or public account.

## Why this is the right current boundary

- The local Demo is repeatable, synthetic, loopback-only and explicit about Live OFF / Provider calls = 0.
- It avoids sharing private images, credentials or user data merely to make a link clickable.
- The repository already documents meaningful recovery and governance boundaries without implying that a public service is operated.

## What a public deployment could add

Cloudflare or another edge/platform could provide an HTTPS entrypoint, routing and protective controls. That potential value does not replace the decisions needed for managed OIDC, storage/IAM, secret management, provider billing limits, abuse prevention, observability, alerting, retention/deletion, incident response, data residency and ownership.

## Follow-up recommendation

Treat public deployment as a separately authorized product/operations phase. Start with a threat model, dedicated synthetic demo tenancy, managed identities/secrets/storage, budget and abuse controls, explicit retention, deployment verification, and an operator runbook. Do not expose the local Compose Demo or reuse its local OIDC profile in a cloud environment.
