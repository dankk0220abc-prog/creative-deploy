"""Fail closed unless every executable action and container input is immutable."""

from __future__ import annotations

import re
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SHA256_REFERENCE = re.compile(r"^[^\s@]+:[^\s@]+@sha256:[0-9a-f]{64}$")
ACTION_REFERENCE = re.compile(r"^[^@\s]+@[0-9a-f]{40}$")


def read(path: str) -> str:
    return (REPOSITORY_ROOT / path).read_text(encoding="utf-8")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"immutable reference validation failed: {message}")


def main() -> None:
    workflow = read(".github/workflows/ci.yml")
    action_lines = re.findall(
        r"^\s*-\s+uses:\s+(\S+)\s+#\s+(v[0-9][^\s]*)\s*$",
        workflow,
        flags=re.MULTILINE,
    )
    all_uses = re.findall(r"^\s*-\s+uses:\s+(\S+)", workflow, flags=re.MULTILINE)
    require(
        action_lines and len(action_lines) == len(all_uses),
        "action version comments missing",
    )
    for reference, readable_version in action_lines:
        require(
            ACTION_REFERENCE.fullmatch(reference) is not None,
            f"mutable action {reference}",
        )
        require(
            readable_version.startswith("v"),
            f"invalid action version {readable_version}",
        )

    docker_references: list[str] = []
    for path in ("apps/api/Dockerfile", "apps/web/Dockerfile"):
        docker_references.extend(
            re.findall(
                r"^ARG\s+[A-Z0-9_]+_IMAGE=(\S+)$", read(path), flags=re.MULTILINE
            )
        )
    for path in ("compose.yaml", "compose.artifact-smoke.yaml"):
        docker_references.extend(
            re.findall(r"^\s+image:\s+(\S+)$", read(path), flags=re.MULTILINE)
        )
    docker_references.extend(
        re.findall(
            r"^\s+(zricethezav/gitleaks:\S+@sha256:[0-9a-f]{64})\s+\\$",
            read("scripts/secret_scan.sh"),
            flags=re.MULTILINE,
        )
    )
    docker_references.extend(
        re.findall(r"^\s+image:\s+(\S+)$", workflow, flags=re.MULTILINE)
    )
    require(
        len(docker_references) == 9, "unexpected executable container reference count"
    )
    for reference in docker_references:
        require(
            SHA256_REFERENCE.fullmatch(reference) is not None,
            f"mutable container reference {reference}",
        )

    print(
        "immutable reference validation: PASS "
        f"({len(action_lines)} actions, {len(docker_references)} container references)"
    )


if __name__ == "__main__":
    main()
