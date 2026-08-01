"""Generate or verify the deterministic Phase 2B-2 unstaged Candidate manifest."""

from __future__ import annotations

import argparse
import hashlib
import subprocess
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = Path("docs/progress/phase-2b-2-candidate-manifest.txt")
BASELINE_HEAD = "511e42ecb2adccc55e75cb4d801181206b1b337a"
BASELINE_TREE = "05420278f8da5478be39832466fc60609c215313"


def _git(*arguments: str) -> bytes:
    return subprocess.run(
        ["git", "-C", str(REPOSITORY_ROOT), *arguments],
        check=True,
        stdout=subprocess.PIPE,
    ).stdout


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _status_entries(raw_status: bytes) -> list[tuple[str, str]]:
    chunks = raw_status.split(b"\0")
    entries: list[tuple[str, str]] = []
    index = 0
    while index < len(chunks) and chunks[index]:
        entry = chunks[index].decode("utf-8", errors="surrogateescape")
        status = entry[:2]
        path = entry[3:]
        if "R" in status or "C" in status:
            index += 1
            if index >= len(chunks) or not chunks[index]:
                raise SystemExit("candidate manifest: incomplete rename/copy status")
            path = chunks[index].decode("utf-8", errors="surrogateescape")
        entries.append((status, path))
        index += 1
    return entries


def _render() -> str:
    raw_status = _git("status", "--porcelain=v1", "-z", "--untracked-files=all")
    entries = _status_entries(raw_status)
    paths = {path for _, path in entries}
    if MANIFEST_PATH.as_posix() not in paths:
        entries.append(("??", MANIFEST_PATH.as_posix()))
        entries.sort(key=lambda item: item[1])

    payload_rows: list[str] = []
    staged_count = 0
    tracked_modified_count = 0
    untracked_count = 0
    for status, relative in sorted(entries, key=lambda item: item[1]):
        if status[0] not in {" ", "?"}:
            staged_count += 1
        if status == "??":
            untracked_count += 1
        else:
            tracked_modified_count += 1
        if relative == MANIFEST_PATH.as_posix():
            continue
        path = REPOSITORY_ROOT / relative
        if not path.is_file() or path.is_symlink():
            raise SystemExit(f"candidate manifest: unsupported leaf {relative}")
        payload = path.read_bytes()
        payload_rows.append(f"{status} | {len(payload)} | {_sha256(payload)} | {relative}")

    payload = "".join(f"{row}\n" for row in payload_rows).encode()
    binary_patch = _git("diff", "--binary", "--no-ext-diff", BASELINE_HEAD, "--")
    header = [
        "manifest_format: CreativeDeploy Phase 2B-2 Candidate v1",
        "generated_at: 2026-08-01",
        f"repository: {REPOSITORY_ROOT}",
        "baseline_branch: main",
        f"baseline_head: {BASELINE_HEAD}",
        f"baseline_tree: {BASELINE_TREE}",
        "baseline_commit_count: 23",
        "alembic_head: 2b1c4d5e6f70",
        f"total_git_status_entries_including_manifest: {len(entries)}",
        f"candidate_payload_entry_count_excluding_manifest: {len(payload_rows)}",
        f"tracked_modified_count: {tracked_modified_count}",
        f"untracked_leaf_count_including_manifest: {untracked_count}",
        f"staged_path_count: {staged_count}",
        f"manifest_file: {MANIFEST_PATH.as_posix()}",
        "manifest_self_hash_policy: excluded from payload entries to avoid recursive hashing; report manifest file SHA-256 externally",
        "scope_rule: exact git status --porcelain=v1 -z --untracked-files=all leaf paths, excluding only manifest_file",
        "columns: git_status | bytes | sha256 | repository-relative-path",
        "candidate_entries_payload_hash_rule: SHA-256 of every sorted row plus one LF",
        f"tracked_binary_patch_sha256: {_sha256(binary_patch)}",
        f"porcelain_v1_z_exact_byte_sha256: {_sha256(raw_status)}",
        f"candidate_entries_payload_sha256: {_sha256(payload)}",
    ]
    return "\n".join([*header, *payload_rows, ""])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true")
    arguments = parser.parse_args()
    expected = _render()
    path = REPOSITORY_ROOT / MANIFEST_PATH
    if arguments.verify:
        if not path.is_file() or path.read_text(encoding="utf-8") != expected:
            raise SystemExit("Phase 2B-2 candidate manifest verification: FAIL")
        print(f"Phase 2B-2 candidate manifest verification: PASS sha256={_sha256(expected.encode())}")
        return
    path.write_text(expected, encoding="utf-8")
    # Render again after the file exists so the porcelain hash includes its leaf.
    expected = _render()
    path.write_text(expected, encoding="utf-8")
    print(f"Phase 2B-2 candidate manifest generated sha256={_sha256(expected.encode())}")


if __name__ == "__main__":
    main()
