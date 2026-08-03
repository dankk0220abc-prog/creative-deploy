# Public Repository Hardening Candidate

Date: 2026-08-03

## Verdict

`PUBLIC_REPOSITORY_HARDENING_READY_FOR_FOCUSED_REVIEW`

This is an unstaged local documentation Candidate for a separate focused reviewer.
It does not create or enable a Ruleset, change GitHub settings, commit, push, tag,
pull request, or Release. It is not production-ready.

## Verified baseline

- Repository: `dankk0220abc-prog/creative-deploy`
- Branch / local `HEAD` / `origin/main` / GitHub `main`:
  `b4a56043f7a712e3127436f54ac8f4ca58e1ca9a`
- Entry worktree: clean; staged / modified / untracked: `0 / 0 / 0`
- Visibility / default branch / license: `PUBLIC` / `main` / `Apache-2.0`
- Latest successful Candidate CI: run `30806458934`, workflow `Candidate CI`,
  job/check `candidate`, completed successfully for the baseline commit
- The baseline `candidate` check is emitted by GitHub Actions app ID `15368`.

## Public repository alignment

`README.md` now describes the repository as public source under Apache-2.0, adds
the native Candidate CI badge and two existing synthetic product captures, removes
obsolete Private / local-Phase-2D / future-public-release statements, and links
readers to the preserved engineering history. It retains the implemented product
boundary and states the non-production, unimplemented, and unauthorized limits.

`CONTRIBUTING.md` is new because no contribution guide existed. It is deliberately
minimal: feature-branch pull requests, no direct `main` push, scope-matched checks,
the required `candidate` check, private security reporting, sensitive-material
prohibition, the current AI boundary, and Apache-2.0 contribution terms.

No historical evidence under `docs/progress/` was removed or rewritten.

## Current remote audit

- Metadata is public and unchanged: default branch `main`; Apache-2.0; description
  `A bilingual, browser-first platform for governed image review, region annotation,
  private storage, and reproducible delivery workflows.`; topics `docker`,
  `fastapi`, `image-annotation`, `oidc`, `postgresql`, `python`, `react`,
  `supply-chain-security`, `typescript`, and `workflow-automation`.
- Repository rulesets: `[]`; no repository Ruleset exists.
- Effective rules for `main`: `[]`; no inherited or repository rule is effective.
- Traditional `main` branch protection: absent (`404 Branch not protected`).
- Merge settings: squash, merge-commit, and rebase merging are enabled; auto-merge,
  automatic head-branch deletion, and update-branch are disabled.
- Dependency graph: available automatically for this public repository.
- Dependabot alerts: disabled (`GET /vulnerability-alerts` returned
  `404 Vulnerability alerts are disabled`).
- Dependabot security updates: disabled (`enabled: false`).
- Secret scanning and push protection: disabled. Listing secret-scanning alerts
  returned `404 Secret scanning is disabled`; the repository metadata reports both
  setting statuses as `disabled`.
- No Issue template or pull-request template exists under `.github`; only the
  existing Candidate CI workflow is present.

The read-only checks were authorized with repository-admin access. A direct
read-only `GET /secret-scanning/push-protection` is not a supported repository
settings endpoint and returned `404`; its setting status above comes from repository
metadata.

## Proposed active main Ruleset

Create one repository Ruleset after a separately authorized executor has rechecked
the current state. It targets the default branch, is active, and has no bypass
actors. Repository administration still permits the owner to edit or temporarily
disable the Ruleset; this Candidate does not grant a standing direct-push bypass.

- Name: `main-public-protection`
- Target: `branch`, condition `~DEFAULT_BRANCH` (currently `main`)
- Rules: restrict deletions; block non-fast-forward updates; require pull requests;
  require resolved review conversations; require the `candidate` check from GitHub
  Actions; require the branch to be up to date; require linear history
- Pull-request approval count: `0`; no CODEOWNERS, signed-commit, deployment,
  merge-queue, branch-lock, push-rule, or path-restriction requirement
- Merge method in the Ruleset: `squash` only, matching the proposed repository
  merge setting and preserving linear history

The status-check context and source are verified rather than inferred: the latest
successful check run is `candidate` from GitHub Actions app ID `15368`.

```json
{
  "name": "main-public-protection",
  "target": "branch",
  "enforcement": "active",
  "bypass_actors": [],
  "conditions": {
    "ref_name": {
      "include": ["~DEFAULT_BRANCH"],
      "exclude": []
    }
  },
  "rules": [
    { "type": "deletion" },
    { "type": "non_fast_forward" },
    {
      "type": "pull_request",
      "parameters": {
        "allowed_merge_methods": ["squash"],
        "dismiss_stale_reviews_on_push": false,
        "dismissal_restriction": {
          "enabled": false,
          "allowed_actors": []
        },
        "require_code_owner_review": false,
        "require_last_push_approval": false,
        "required_approving_review_count": 0,
        "required_review_thread_resolution": true
      }
    },
    {
      "type": "required_status_checks",
      "parameters": {
        "do_not_enforce_on_create": false,
        "required_status_checks": [
          {
            "context": "candidate",
            "integration_id": 15368
          }
        ],
        "strict_required_status_checks_policy": true
      }
    },
    { "type": "required_linear_history" }
  ]
}
```

The zero approval count is intentional for this personal repository: a mandatory
approval would prevent the owner from approving their own pull request. The
pull-request trail, resolved review conversations, strict Candidate CI, and linear
history remain enforced.

## Proposed merge settings

Apply these repository settings before creating the Ruleset so its squash-only
requirement is satisfiable:

```json
{
  "allow_squash_merge": true,
  "allow_merge_commit": false,
  "allow_rebase_merge": false,
  "allow_auto_merge": true,
  "delete_branch_on_merge": true,
  "allow_update_branch": true
}
```

This allows only squash merges and supports a linear, strict-CI pull-request flow.

## Security proposal

For this public repository, dependency graph is automatic and has no separate
repository mutation in this plan. Enable Dependabot alerts first, then enable
Dependabot security updates, secret scanning, and push protection. Do not add a
`dependabot.yml` version-update schedule, CodeQL workflow, or third-party security
App in this operation.

If GitHub returns `403`, `404`, or `422` for an enabling request, the executor must
record that feature as `NOT AVAILABLE` with the response and must not report it as
enabled. A separate authorization is needed for any scope expansion.

## Exact remote mutation plan for a separate executor

This sequence is **not to be run in this implementation task**.

1. After independent focused review and separately authorized sealing/publishing of
   this Candidate, re-read repository metadata, merge settings, rulesets, effective
   rules, `main` protection, security state, and the latest successful `candidate`
   check. Stop on any unreviewed drift, existing Ruleset, non-empty effective rule,
   unexpected protection, missing `candidate` check, or an app source other than
   GitHub Actions ID `15368`.
2. Enable Dependabot alerts. Then patch the supported security-and-analysis settings
   and verify every response before continuing.

   ```bash
   gh api --method PUT repos/dankk0220abc-prog/creative-deploy/vulnerability-alerts
   gh api --method PATCH repos/dankk0220abc-prog/creative-deploy --input - <<'JSON'
   {
     "security_and_analysis": {
       "dependabot_security_updates": { "status": "enabled" },
       "secret_scanning": { "status": "enabled" },
       "secret_scanning_push_protection": { "status": "enabled" }
     }
   }
   JSON
   ```

3. Apply the documented merge payload and verify it in repository metadata.

   ```bash
   gh api --method PATCH repos/dankk0220abc-prog/creative-deploy --input - <<'JSON'
   {
     "allow_squash_merge": true,
     "allow_merge_commit": false,
     "allow_rebase_merge": false,
     "allow_auto_merge": true,
     "delete_branch_on_merge": true,
     "allow_update_branch": true
   }
   JSON
   ```

4. Create exactly one active Ruleset with the payload in this record, then capture
   its returned ID and verify it and its effective rules for `main`.

   ```bash
   gh api --method POST repos/dankk0220abc-prog/creative-deploy/rulesets --input - <<'JSON'
   {
     "name": "main-public-protection",
     "target": "branch",
     "enforcement": "active",
     "bypass_actors": [],
     "conditions": {
       "ref_name": {
         "include": ["~DEFAULT_BRANCH"],
         "exclude": []
       }
     },
     "rules": [
       { "type": "deletion" },
       { "type": "non_fast_forward" },
       {
         "type": "pull_request",
         "parameters": {
           "allowed_merge_methods": ["squash"],
           "dismiss_stale_reviews_on_push": false,
           "dismissal_restriction": {
             "enabled": false,
             "allowed_actors": []
           },
           "require_code_owner_review": false,
           "require_last_push_approval": false,
           "required_approving_review_count": 0,
           "required_review_thread_resolution": true
         }
       },
       {
         "type": "required_status_checks",
         "parameters": {
           "do_not_enforce_on_create": false,
           "required_status_checks": [
             { "context": "candidate", "integration_id": 15368 }
           ],
           "strict_required_status_checks_policy": true
         }
       },
       { "type": "required_linear_history" }
     ]
   }
   JSON
   ```

5. Verify `GET /rulesets`, `GET /rules/branches/main`, repository merge fields,
   `GET /vulnerability-alerts`, `GET /automated-security-fixes`, repository
   `security_and_analysis`, and secret-scanning alert availability. Keep a
   traditional branch-protection `404` only if the Ruleset is the intended sole
   protection. Do not change description, topics, visibility, workflows, or
   security tooling beyond this plan.

## Focused validation

- README and CONTRIBUTING local links: PASS.
- README screenshot references: PASS; both existing PNG files are non-empty RGB
  `1440 x 974` images.
- Candidate CI badge: PASS; anonymous HTTPS request returned `200`.
- Markdown trailing-whitespace check: PASS for all three Candidate files.
- `git diff --check`: PASS.
- Candidate-sensitive scan: PASS; gitleaks scanned tracked plus untracked
  repository files and reported no leaks.
- Candidate CI workflow static read: PASS; workflow name is `Candidate CI` and
  its only job is `candidate`.
- Ruleset payload JSON structural sanity: PASS; verified the target, empty bypass
  list, five requested rules, strict `candidate` check from integration `15368`,
  zero approvals, resolved conversations, and squash-only merge method. This is
  a local structural check, not a live write-API acceptance test.

No Web tests or build, API tests, PostgreSQL/Alembic, Docker staging, TLS,
backup/restore, browser product flow, or full supply-chain gate was run; the
Candidate changes no product or workflow behavior.

## Candidate boundary

Modified paths are limited to `README.md`, `CONTRIBUTING.md`, and this record. No
application code, tests, migrations, Docker or Compose configuration, CI workflow,
screenshots, license, security policy, or private environment file is changed.
