---
record_type: phase_1d_3_governance_reconciliation_candidate
record_status: NOT_INDEPENDENTLY_APPROVED
effective_status: CANDIDATE_ONLY
created_at: 2026-07-29T00:21:10+08:00
no_backdating: true
repository: CreativeDeploy
phase: Phase 1D-3 — React Router and Projects Pages
---

# Phase 1D-3 Governance Reconciliation Candidate

Current status:
`GOVERNANCE_RECONCILIATION_CANDIDATE_PENDING_INDEPENDENT_REVIEW`

This is a present-day candidate record. It is not an approval, closure, Git-sealing record, or
replacement for an independent read-only governance review.

## 1. Purpose

This record reconciles Phase 1D-3 governance status with the Git history that actually exists. It
does not rewrite, amend, replace, or reinterpret any Git object, and it does not change the
original phase sequence or Definition of Done.

Git objects verified when this candidate began:

| Object | Hash | Commit date | Parent | Tree | Subject |
| --- | --- | --- | --- | --- | --- |
| Commit 10 | `5965a8707a6ccb06d2f58d8655aabac9630e4abd` | `2026-07-28T16:21:16+08:00` | `6d2c3d8001c3737e2e441ee1c0df4179660f0c57` | `e9a05e8d8d741b8d4226729be08ccfb0e2783b83` | `feat(web): add PaintProject routes and project pages` |
| UX remediation / current HEAD | `2f99aaf8e1726761c2d89ac444af8380a1cedb79` | `2026-07-29T00:06:06+08:00` | `5965a8707a6ccb06d2f58d8655aabac9630e4abd` | `b465d64d12032eb2e63574a7110925257a00bf87` | `fix(web): align project home UX contract` |

The verified branch is `main`, and the verified commit count is `11`.

## 2. Process Exception

Commit 10 entered Git history without a formal prior repository approval record. At the same time,
the Phase 1D-3 candidate and current-status documents committed by Commit 10 still said
`NOT_APPROVED`, `NOT_CREATED`, or that no Commit 10 had been created.

No prior repository approval evidence was found. This is a process exception. The later review does not backdate approval.
Neither this reconciliation nor any later review may be described as authorization that existed
before Commit 10 was created.

## 3. Evidence Classification

### GIT_VERIFIED_FACT

The current repository directly proves:

- Commit 10 and the remediation commit exist with the hashes, parents, trees, subjects, and dates
  recorded in this file;
- Commit 10 added the Phase 1D-3 candidate while that candidate said `NOT_APPROVED` and
  `NOT_CREATED`;
- the remediation commit contains exactly six frontend/test files;
- the remediation commit message contains
  `Independent-review-verdict:
  PHASE_1D_3_FOCUSED_REMEDIATION_PASS_READY_FOR_SEALING` and
  `Candidate-manifest-sha256:
  7637b349ca8e99aea74f2ecc178af90a0f59f534984e0bb4110658832d5e2edc`;
- the remediation commit's parent is Commit 10;
- the sole Migration Revision remains `a10d3d8dab38`.

### OWNER_SUPPLIED_EXTERNAL_REVIEW_RECORD

The project owner supplied the following records for inclusion now:

- `NO_PRIOR_REPOSITORY_APPROVAL_EVIDENCE_FOUND`;
- retrospective verdict `PHASE_1D_3_REMEDIATION_REQUIRED`;
- retrospective findings F-01 and F-02;
- focused-review verdict
  `PHASE_1D_3_FOCUSED_REMEDIATION_PASS_READY_FOR_SEALING`;
- sealing verdict `PHASE_1D_3_UX_REMEDIATION_SEALED`;
- the focused review and sealing command-ledger details described by the owner.
- the governance implementation report's statement that the worktree was clean when governance
  reconciliation began.

These records were not pre-Commit-10 Git objects. They are being incorporated into the repository
only through this current candidate. They must not be used to infer or claim pre-commit
authorization. The retrospective review timestamp is `UNVERIFIED`: the owner-supplied task did not
provide an exact timestamp, so this record does not invent one.

The historical worktree statement is not reconstructible from the current repository and is not a
`GIT_VERIFIED_FACT`. It is not used to prove pre-Commit-10 approval, and it does not affect direct
verification of the current Candidate Scope or current Git status.

### CURRENT_GOVERNANCE_INFERENCE

Based on the Git facts and the owner-supplied external records:

- Phase 1D-3's technical UX remediation is implemented and sealed;
- Phase 1D-3 still requires independent review and sealing of this governance candidate before
  formal governance closure;
- Phase 1D-4 and Phase 1E-1 must remain unstarted.

These are current governance inferences, not historical facts about what was approved before
Commit 10.

## 4. Retrospective Review Outcome

Source classification: `OWNER_SUPPLIED_EXTERNAL_REVIEW_RECORD`.

- prior approval evidence: `NOT_FOUND`;
- record: `NO_PRIOR_REPOSITORY_APPROVAL_EVIDENCE_FOUND`;
- verdict: `PHASE_1D_3_REMEDIATION_REQUIRED`;
- F-01: the Empty Projects page exposed two sibling primary Create calls to action;
- F-02: Project Card fields and Updated-time formatting departed from the owner-approved UX
  contract;
- result: the retrospective review required remediation and did not grant approval.

The review occurred after Commit 10 entered history. It is not evidence of pre-Commit-10 approval.

## 5. Remediation

F-01 was remediated by enforcing one primary Create action in the empty Projects state. F-02 was
remediated by restoring the approved five-field card hierarchy and deterministic relative time
with an accessible exact Updated timestamp.

The remediation was independently reviewed and sealed. That statement combines the
owner-supplied focused-review and sealing records with the Git-verified remediation commit and its
trailers; it does not backdate approval.

- focused independent review verdict:
  `PHASE_1D_3_FOCUSED_REMEDIATION_PASS_READY_FOR_SEALING`;
- technical-remediation candidate manifest:
  `7637b349ca8e99aea74f2ecc178af90a0f59f534984e0bb4110658832d5e2edc`;
- sealing verdict: `PHASE_1D_3_UX_REMEDIATION_SEALED`;
- remediation commit: `2f99aaf8e1726761c2d89ac444af8380a1cedb79`;
- remediation parent / Commit 10:
  `5965a8707a6ccb06d2f58d8655aabac9630e4abd`.

The Git-verified six-file remediation scope is:

1. `apps/web/src/__tests__/ProjectCard.test.tsx`;
2. `apps/web/src/__tests__/ProjectsPage.test.tsx`;
3. `apps/web/src/__tests__/format.test.ts`;
4. `apps/web/src/components/ProjectCard.tsx`;
5. `apps/web/src/pages/ProjectsPage.tsx`;
6. `apps/web/src/utils/format.ts`.

## 6. Current Truth

- Commit 10 exists at `5965a8707a6ccb06d2f58d8655aabac9630e4abd`.
- The former current-state statement “Commit 10 was not created” is disproved by Git.
- The remediation commit exists at `2f99aaf8e1726761c2d89ac444af8380a1cedb79`.
- The Phase 1D-3 technical remediation is sealed.
- This governance reconciliation remains an unapproved candidate.
- Phase 1D-3 has not completed final governance closure.
- Phase 1D remains `IN_PROGRESS`.
- Phase 1D-4 remains **Integrated Product Review**; it has not been renamed, started, executed, or
  partially executed.
- Phase 1E-1 has not started.

## 7. Required Remaining Gates

1. A new independent Codex conversation must perform a focused, read-only review of this exact
   governance candidate.
2. Only after that review passes may a separate Git-sealing conversation seal the governance
   candidate.
3. After sealing, all current-status entry points must be reverified against the sealed Git object.
4. Only after those gates may Phase 1D-3 be marked formally closed.
5. After Phase 1D-3 governance closure is independently reviewed and sealed, Phase 1D-4 may begin.
6. Phase 1E-1 remains blocked by the Phase 1D Definition of Done and Phase 1D-4.

## 8. Explicit Non-Claims

This record does not claim:

- Commit 10 was approved before it was created;
- the historical process had no exception;
- the first retrospective review passed;
- this governance candidate is independently approved or sealed;
- Phase 1D-3 is formally closed;
- Phase 1D is complete;
- Phase 1D-4 has passed or started;
- Phase 1E-1 has started;
- image upload, image analysis, AI providers, RAG, Agent workflows, inventory, Polygon editing, or
  HumanApproval capability exists.

## 9. Approval Boundary

Current status:
`GOVERNANCE_RECONCILIATION_CANDIDATE_PENDING_INDEPENDENT_REVIEW`

The governance reconciliation itself remains an unapproved candidate. It must not be represented
as `APPROVED`, `CLOSED`, `COMPLETE`, `READY_FOR_PHASE_1E`, or `PHASE_1D_COMPLETE`.

## 10. Statement Reconciliation Inventory

Line references below identify the pre-reconciliation state at base HEAD
`2f99aaf8e1726761c2d89ac444af8380a1cedb79`.

| Statement | File/Lines | Historical or Current | Git Truth | Required Treatment |
| --- | --- | --- | --- | --- |
| Phase 1D-3 was an uncommitted candidate and no Commit 10 existed | `README.md:11-12,232` | stale current | Commit 10 and its remediation child exist | replace with current Git hashes and pending governance gates |
| Phase 1D-3 approval was `NOT_APPROVED`; Commit 10 was `NOT_CREATED` | `README.md:21-31` | stale current wording | technical commits exist; governance closure does not | distinguish existing commits from the unapproved governance candidate |
| Phase 1D-3 was an uncommitted candidate | `AGENTS.md:17-18,51` | stale current | Commit 10 and remediation are current baseline | update agent guardrails without inventing prior approval |
| Commit 10 had not been created | `docs/progress/phase-1d-paint-project-vertical-slice-plan.md:5-8,77-79` | stale current | Commit 10 is current history | record Commit 10, remediation, and remaining governance gates |
| Phase 1D-4 was not started | `docs/progress/phase-1d-paint-project-vertical-slice-plan.md:96` | current and true | no Phase 1D-4 implementation commit or current-status claim exists | retain and add Phase 1E-1 `NOT_STARTED` |
| Phase 1D-3 approval was `NOT_APPROVED`; Commit 10 was `NOT_CREATED` | `docs/progress/phase-1d-3-react-router-and-projects-pages-candidate.md:3-6` | historical snapshot committed by Commit 10 | Commit 10 exists; original candidate state remains evidence of the exception | preserve under an explicit historical-snapshot label |
| Commit 10 did not exist and Phase 1D-4 was next after review | `docs/progress/phase-1d-3-react-router-and-projects-pages-candidate.md:279-288` | historical snapshot | remediation exists; governance review/sealing still remain | preserve history and add a superseding current-status section |
| Phase 1D-2 was unapproved, Commit 9 was not created, and Phase 1D-3 was not started | `docs/progress/phase-1d-2-paintproject-persistence-and-api-candidate.md:3-7,60-61` | older Phase 1D-2 candidate snapshot | later Git history supersedes it | leave unchanged as a non-current historical candidate; do not expand scope |

## 11. Evidence-to-Claim Boundary

| Statement | Classification | Source | Repository-preexisting before this candidate | Allowed use |
| --- | --- | --- | --- | --- |
| Commit 10 exists with the recorded object data | `GIT_VERIFIED_FACT` | Git object `5965a8707a6ccb06d2f58d8655aabac9630e4abd` | yes | current history |
| Commit 10 carried `NOT_APPROVED` / `NOT_CREATED` text | `GIT_VERIFIED_FACT` | Commit 10 tree and diff | yes | prove status drift, not approval |
| No prior repository approval evidence was found | `OWNER_SUPPLIED_EXTERNAL_REVIEW_RECORD` | owner-supplied task; corroborated by current history scan | no | record the exception; never backdate |
| Retrospective verdict and F-01/F-02 | `OWNER_SUPPLIED_EXTERNAL_REVIEW_RECORD` | owner-supplied task | no | explain why remediation was required |
| Remediation commit and its parent/six-file scope | `GIT_VERIFIED_FACT` | Git object `2f99aaf8e1726761c2d89ac444af8380a1cedb79` | yes | identify sealed technical scope |
| Focused review and sealing verdicts | `OWNER_SUPPLIED_EXTERNAL_REVIEW_RECORD` | owner-supplied task; review trailer text is also present in Git | partially | establish later remediation outcome only |
| Phase 1D-3 awaits governance closure | `CURRENT_GOVERNANCE_INFERENCE` | combined classified evidence | no | control present next steps |

## Appendix A — Governance Candidate Manifest Protocol v1

This protocol freezes the representation of the current five-file governance candidate. It
provides reproducibility evidence only; it is not approval, governance closure, or Git sealing.

### A.1 Schema identity and fixed JSON Schema

The only valid `schema_version` is
`creativedeploy-governance-candidate-manifest-v1`. The following JSON Schema defines every allowed
key and value shape. The generator below additionally enforces the exact five paths and their
status/tracking pairs.

```json
{
  "$id": "urn:creativedeploy:governance-candidate-manifest:v1",
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "additionalProperties": false,
  "properties": {
    "base_head": {
      "pattern": "^[0-9a-f]{40}$",
      "type": "string"
    },
    "base_parent": {
      "pattern": "^[0-9a-f]{40}$",
      "type": "string"
    },
    "base_tree": {
      "pattern": "^[0-9a-f]{40}$",
      "type": "string"
    },
    "branch": {
      "const": "main"
    },
    "commit_count": {
      "const": 11
    },
    "files": {
      "items": {
        "additionalProperties": false,
        "properties": {
          "byte_size": {
            "minimum": 0,
            "type": "integer"
          },
          "path": {
            "enum": [
              "AGENTS.md",
              "README.md",
              "docs/progress/phase-1d-3-governance-reconciliation-candidate.md",
              "docs/progress/phase-1d-3-react-router-and-projects-pages-candidate.md",
              "docs/progress/phase-1d-paint-project-vertical-slice-plan.md"
            ]
          },
          "sha256": {
            "pattern": "^[0-9a-f]{64}$",
            "type": "string"
          },
          "status": {
            "enum": [
              "M",
              "??"
            ]
          },
          "tracking": {
            "enum": [
              "tracked",
              "untracked"
            ]
          }
        },
        "required": [
          "path",
          "status",
          "tracking",
          "byte_size",
          "sha256"
        ],
        "type": "object"
      },
      "maxItems": 5,
      "minItems": 5,
      "type": "array"
    },
    "schema_version": {
      "const": "creativedeploy-governance-candidate-manifest-v1"
    },
    "staged_count": {
      "const": 0
    },
    "status_porcelain_z_sha256": {
      "pattern": "^[0-9a-f]{64}$",
      "type": "string"
    },
    "tracked_diff_sha256": {
      "pattern": "^[0-9a-f]{64}$",
      "type": "string"
    }
  },
  "required": [
    "schema_version",
    "base_head",
    "base_parent",
    "base_tree",
    "branch",
    "commit_count",
    "staged_count",
    "tracked_diff_sha256",
    "status_porcelain_z_sha256",
    "files"
  ],
  "type": "object"
}
```

### A.2 Exact manifest object layout

The manifest has exactly one file-set key, `files`. The five objects below appear in ascending
Python string order by `path`. Each displayed `0` and hash placeholder is replaced by the
generator's value from the raw current bytes; the keys, paths, status values, tracking values, and
nesting are exact.

```json
{
  "schema_version": "creativedeploy-governance-candidate-manifest-v1",
  "base_head": "<40-char lowercase git hash>",
  "base_parent": "<40-char lowercase git hash>",
  "base_tree": "<40-char lowercase git hash>",
  "branch": "main",
  "commit_count": 11,
  "staged_count": 0,
  "tracked_diff_sha256": "<64-char lowercase sha256>",
  "status_porcelain_z_sha256": "<64-char lowercase sha256>",
  "files": [
    {
      "path": "AGENTS.md",
      "status": "M",
      "tracking": "tracked",
      "byte_size": 0,
      "sha256": "<64-char lowercase sha256>"
    },
    {
      "path": "README.md",
      "status": "M",
      "tracking": "tracked",
      "byte_size": 0,
      "sha256": "<64-char lowercase sha256>"
    },
    {
      "path": "docs/progress/phase-1d-3-governance-reconciliation-candidate.md",
      "status": "??",
      "tracking": "untracked",
      "byte_size": 0,
      "sha256": "<64-char lowercase sha256>"
    },
    {
      "path": "docs/progress/phase-1d-3-react-router-and-projects-pages-candidate.md",
      "status": "M",
      "tracking": "tracked",
      "byte_size": 0,
      "sha256": "<64-char lowercase sha256>"
    },
    {
      "path": "docs/progress/phase-1d-paint-project-vertical-slice-plan.md",
      "status": "M",
      "tracking": "tracked",
      "byte_size": 0,
      "sha256": "<64-char lowercase sha256>"
    }
  ]
}
```

There is no `created_at`, absolute path, temporary path, manifest path, separate tracked/untracked
file-set key, or `candidate_manifest_sha256` field. In particular, the manifest never hashes
itself.

### A.3 Raw byte sources and exact Git commands

`tracked_diff_sha256` is SHA-256 of the raw stdout bytes from exactly:

```bash
git diff --binary --full-index HEAD --
```

`status_porcelain_z_sha256` is SHA-256 of the raw stdout bytes from exactly:

```bash
git status --porcelain=v1 -z --untracked-files=all
```

The generator does not decode/re-encode, normalize line endings, strip, sort, or append bytes
before hashing either stream. It obtains the staged path count from:

```bash
git diff --cached --name-only -z HEAD --
```

Each `byte_size` is `len(path.read_bytes())`; each per-file `sha256` is
`hashlib.sha256(path.read_bytes()).hexdigest()`.

### A.4 Canonical serialization and candidate hash

The sole canonical serialization is:

```python
canonical_json_bytes = json.dumps(
    manifest,
    ensure_ascii=False,
    sort_keys=True,
    separators=(",", ":"),
).encode("utf-8")
candidate_manifest_sha256 = hashlib.sha256(canonical_json_bytes).hexdigest()
```

Canonical bytes have no indentation, pretty-printing, BOM, or trailing newline. The output file is
written in binary mode as exactly `canonical_json_bytes`.

### A.5 Versioned Python standard-library generator

Copy the code between the two markers exactly. It has no third-party imports, resolves the Git root
from the current directory, rejects a non-CreativeDeploy repository, rejects baseline drift,
rejects staged content and every non-` M`/`??` status (including deletion, rename, copy, conflict,
and staged `M `), rejects any path outside the exact five-file tuple, and exits nonzero on error.

<!-- BEGIN CREATIVDEPLOY_GOVERNANCE_MANIFEST_V1_GENERATOR -->
```python
#!/usr/bin/env python3
"""Generate CreativeDeploy Governance Candidate Manifest Protocol v1."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "creativedeploy-governance-candidate-manifest-v1"
EXPECTED_REPOSITORY_NAME = "CreativeDeploy"
EXPECTED_BASE_HEAD = "2f99aaf8e1726761c2d89ac444af8380a1cedb79"
EXPECTED_BASE_PARENT = "5965a8707a6ccb06d2f58d8655aabac9630e4abd"
EXPECTED_BASE_TREE = "b465d64d12032eb2e63574a7110925257a00bf87"
EXPECTED_BRANCH = "main"
EXPECTED_COMMIT_COUNT = 11
ALLOWED_PATHS = (
    "AGENTS.md",
    "README.md",
    "docs/progress/phase-1d-3-governance-reconciliation-candidate.md",
    "docs/progress/phase-1d-3-react-router-and-projects-pages-candidate.md",
    "docs/progress/phase-1d-paint-project-vertical-slice-plan.md",
)
HEX_40 = re.compile(r"^[0-9a-f]{40}$")


def run_git(root: Path, *args: str) -> bytes:
    completed = subprocess.run(
        ["git", *args],
        cwd=root,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if completed.returncode != 0:
        stderr = completed.stderr.decode("utf-8", errors="replace").rstrip()
        raise RuntimeError(f"git {' '.join(args)} failed ({completed.returncode}): {stderr}")
    return completed.stdout


def one_line(raw: bytes, label: str) -> str:
    try:
        value = raw.decode("ascii").strip()
    except UnicodeDecodeError as exc:
        raise RuntimeError(f"{label} is not ASCII") from exc
    if "\n" in value or "\r" in value or not value:
        raise RuntimeError(f"{label} is not one non-empty line")
    return value


def parse_status(raw: bytes) -> dict[str, dict[str, str]]:
    records = raw.split(b"\0")
    if not records or records[-1] != b"":
        raise RuntimeError("porcelain -z output lacks its required final NUL")
    parsed: dict[str, dict[str, str]] = {}
    for record in records[:-1]:
        if len(record) < 4 or record[2:3] != b" ":
            raise RuntimeError(f"malformed or multi-path porcelain record: {record!r}")
        try:
            xy = record[:2].decode("ascii")
            path = record[3:].decode("utf-8")
        except UnicodeDecodeError as exc:
            raise RuntimeError(f"non-UTF-8 porcelain record: {record!r}") from exc
        if path in parsed:
            raise RuntimeError(f"duplicate status path: {path}")
        if xy == " M":
            parsed[path] = {"status": "M", "tracking": "tracked"}
        elif xy == "??":
            parsed[path] = {"status": "??", "tracking": "untracked"}
        else:
            raise RuntimeError(
                f"rejected status {xy!r} for {path!r}; only unstaged ' M' and '??' are allowed"
            )
    return parsed


def require_hash(value: str, label: str) -> str:
    if HEX_40.fullmatch(value) is None:
        raise RuntimeError(f"{label} is not a 40-character lowercase Git hash: {value!r}")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", help="absolute /tmp path for canonical manifest JSON")
    args = parser.parse_args()

    start = Path.cwd()
    root_raw = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=start,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if root_raw.returncode != 0:
        raise RuntimeError("current directory is not inside a Git worktree")
    root = Path(one_line(root_raw.stdout, "Git root")).resolve()
    if root.name != EXPECTED_REPOSITORY_NAME:
        raise RuntimeError(f"refusing non-CreativeDeploy repository: {root}")
    if not (root / "README.md").read_bytes().startswith(b"# CreativeDeploy\n"):
        raise RuntimeError("repository identity check failed")

    output = Path(args.output).expanduser()
    if not output.is_absolute() or output.parent.resolve() != Path("/tmp").resolve():
        raise RuntimeError("output must be a direct absolute child of /tmp")
    if output.is_symlink():
        raise RuntimeError("refusing symlink output path")

    base_head = require_hash(one_line(run_git(root, "rev-parse", "HEAD"), "HEAD"), "HEAD")
    base_parent = require_hash(
        one_line(run_git(root, "rev-parse", "HEAD^"), "HEAD parent"), "HEAD parent"
    )
    base_tree = require_hash(
        one_line(run_git(root, "rev-parse", "HEAD^{tree}"), "HEAD tree"), "HEAD tree"
    )
    branch = one_line(run_git(root, "branch", "--show-current"), "branch")
    commit_count = int(one_line(run_git(root, "rev-list", "--count", "HEAD"), "commit count"))

    expected_baseline = (
        EXPECTED_BASE_HEAD,
        EXPECTED_BASE_PARENT,
        EXPECTED_BASE_TREE,
        EXPECTED_BRANCH,
        EXPECTED_COMMIT_COUNT,
    )
    actual_baseline = (base_head, base_parent, base_tree, branch, commit_count)
    if actual_baseline != expected_baseline:
        raise RuntimeError(
            f"baseline changed: expected {expected_baseline!r}, got {actual_baseline!r}"
        )

    staged_raw = run_git(root, "diff", "--cached", "--name-only", "-z", "HEAD", "--")
    staged_records = staged_raw.split(b"\0")
    if not staged_records or staged_records[-1] != b"":
        raise RuntimeError("staged path output lacks its required final NUL")
    staged_count = len(staged_records) - 1
    if staged_count != 0:
        raise RuntimeError(f"staged content is forbidden; staged path count={staged_count}")

    tracked_diff_raw = run_git(root, "diff", "--binary", "--full-index", "HEAD", "--")
    status_raw = run_git(
        root,
        "status",
        "--porcelain=v1",
        "-z",
        "--untracked-files=all",
    )
    status_entries = parse_status(status_raw)
    actual_paths = tuple(sorted(status_entries))
    if actual_paths != ALLOWED_PATHS:
        raise RuntimeError(
            f"candidate scope mismatch: expected {ALLOWED_PATHS!r}, got {actual_paths!r}"
        )

    files: list[dict[str, Any]] = []
    for relative_path in ALLOWED_PATHS:
        candidate_path = root / relative_path
        if candidate_path.is_symlink() or not candidate_path.is_file():
            raise RuntimeError(f"candidate is not a regular non-symlink file: {relative_path}")
        raw = candidate_path.read_bytes()
        files.append(
            {
                "path": relative_path,
                "status": status_entries[relative_path]["status"],
                "tracking": status_entries[relative_path]["tracking"],
                "byte_size": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
        )

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "base_head": base_head,
        "base_parent": base_parent,
        "base_tree": base_tree,
        "branch": branch,
        "commit_count": commit_count,
        "staged_count": staged_count,
        "tracked_diff_sha256": hashlib.sha256(tracked_diff_raw).hexdigest(),
        "status_porcelain_z_sha256": hashlib.sha256(status_raw).hexdigest(),
        "files": files,
    }
    canonical_json_bytes = json.dumps(
        manifest,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    candidate_manifest_sha256 = hashlib.sha256(canonical_json_bytes).hexdigest()
    output.write_bytes(canonical_json_bytes)

    print(f"schema_version={SCHEMA_VERSION}")
    print(f"manifest_path={output}")
    print(f"canonical_manifest_byte_size={len(canonical_json_bytes)}")
    print(f"candidate_manifest_sha256={candidate_manifest_sha256}")
    print(f"tracked_diff_sha256={manifest['tracked_diff_sha256']}")
    print(f"status_porcelain_z_sha256={manifest['status_porcelain_z_sha256']}")
    for item in files:
        print(
            "file "
            f"path={item['path']} "
            f"status={item['status']} "
            f"tracking={item['tracking']} "
            f"byte_size={item['byte_size']} "
            f"sha256={item['sha256']}"
        )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
```
<!-- END CREATIVDEPLOY_GOVERNANCE_MANIFEST_V1_GENERATOR -->

The allowed tuple is already in ascending Python string order. File SHA-256 values, byte sizes, raw
stream hashes, and the final manifest hash are deliberately not hardcoded.

### A.6 Exact extraction, execution, and two-run self-test

From the repository root, extract only the marked `python` fence into `/tmp`:

```bash
uv run --project apps/api python -c 'from pathlib import Path; p=Path("docs/progress/phase-1d-3-governance-reconciliation-candidate.md").read_text(encoding="utf-8"); a="<!-- BEGIN CREATIVDEPLOY_GOVERNANCE_MANIFEST_V1_GENERATOR -->\n"; b="\n<!-- END CREATIVDEPLOY_GOVERNANCE_MANIFEST_V1_GENERATOR -->"; block=p.split(a,1)[1].split(b,1)[0]; assert block.startswith("```python\n") and block.endswith("\n```"); Path("/tmp/creativedeploy-governance-manifest-v1.py").write_text(block[len("```python\n"):-len("\n```")],encoding="utf-8",newline="\n")'
```

Execute that extracted file twice:

```bash
uv run --project apps/api python /tmp/creativedeploy-governance-manifest-v1.py /tmp/creativedeploy-governance-candidate-v1-run1.json
uv run --project apps/api python /tmp/creativedeploy-governance-manifest-v1.py /tmp/creativedeploy-governance-candidate-v1-run2.json
```

Independently recompute both JSON hashes and confirm that neither file ends in newline:

```bash
uv run --project apps/api python -c 'import hashlib,pathlib; paths=(pathlib.Path("/tmp/creativedeploy-governance-candidate-v1-run1.json"),pathlib.Path("/tmp/creativedeploy-governance-candidate-v1-run2.json")); [(lambda b,p: print(f"{p} bytes={len(b)} sha256={hashlib.sha256(b).hexdigest()} trailing_newline={b.endswith(chr(10).encode())}"))(p.read_bytes(),p) for p in paths]'
```

Finally require byte-for-byte identity:

```bash
cmp /tmp/creativedeploy-governance-candidate-v1-run1.json /tmp/creativedeploy-governance-candidate-v1-run2.json
```

Success requires both generator runs and the independent hash command to report identical SHA-256
values, `trailing_newline=False` for both files, and `cmp` exit code `0`.
