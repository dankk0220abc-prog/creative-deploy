# Evidence index

This is a short, recruiter-readable index of verified engineering evidence. It intentionally omits credentials, request bodies, private images, personal data, raw provider payloads, and local secret paths.

## Git and GitHub

| Evidence | Verifiable reference |
| --- | --- |
| WP1 merged baseline | protected-main history before WP2 |
| WP2 reviewed feature SHA | `a4865ffc23a5f9cb8f50043c2e24a34586c91fe1` |
| WP2 pull request | [#5](https://github.com/dankk0220abc-prog/creative-deploy/pull/5) |
| WP2 squash/main commit | `5a63594a98cc964d41e16087344679556d697f19` |
| WP2 closure token | `ZHIPU_WP2_CLOSED` |

## Candidate CI

| Run | Evidence |
| --- | --- |
| PR exact-head Candidate CI | `31819219600` |
| main push Candidate CI | `31886211557` — event `push`, branch `main`, attempt `1`, SHA `5a63594a98cc964d41e16087344679556d697f19`, conclusion `success` |

## Schema and recovery

- Final Alembic head: `6a01b2c3d4e6`.
- The synthetic staging drill validates 50 tables and 3 objects, exact retry, checksum refusal, byte-mismatch refusal, and manifest/HMAC tamper refusal.
- Recovery operates against controlled isolated targets; it is evidence for a recovery boundary, not authorization for destructive promotion or a public deployment.

## Independent high-risk review

`ZHIPU_WP2_INDEPENDENT_SOL_REVIEW_PASS_READY_FOR_INTEGRATION_AUTHORIZATION` records project independent high-risk review evidence. It is not a claim of GitHub human approval and does not turn future changes into pre-approved work.

## Provider proof and local demo boundary

| Product | Independently completed proof | Portfolio default |
| --- | --- | --- |
| PaintPilot | Zhipu GLM-5V-Turbo | local/Fixture, Live OFF, Provider calls = 0 |
| Arcana | Zhipu GLM-5.2 | local/Fixture, Live OFF, Provider calls = 0 |

Only these Zhipu paths are claimed as live validated. There is no multi-provider live benchmark, no public production deployment, and no invitation to publish credentials or private images.

## Residual dependency triage — 2026-08-15

The repository currently reports 11 open Dependabot alerts. The High alerts are transitive lockfile dependencies: `js-yaml` through ESLint and `brace-expansion` through ESLint/TypeScript-ESLint; the High `undici` alert is through jsdom/Vitest. `pnpm why` identifies each path under the Web package’s development dependencies, not a direct production application dependency. Fixes are available, but no alert is claimed fixed by WP3 and no lockfile update is included in this documentation-only release. Medium alerts (`undici`, `postcss`) are likewise retained as residuals.
