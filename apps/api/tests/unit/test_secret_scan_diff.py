"""Adversarial shell-level tests for the diff-scoped secret scanner."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import textwrap
import uuid
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
SCANNER_SOURCE = REPOSITORY_ROOT / "scripts" / "secret_scan_diff.sh"
GITLEAKS_IMAGE = (
    "zricethezav/gitleaks:v8.30.1@sha256:"
    "c00b6bd0aeb3071cbcb79009cb16a60dd9e0a7c60e2be9ab65d25e6bc8abbb7f"
)


def _git(repository: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repository), *arguments],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _write_fake_docker(path: Path) -> None:
    path.write_text(
        textwrap.dedent(
            """\
            #!/usr/bin/env python3
            import json
            import os
            from pathlib import Path
            import sys


            arguments = sys.argv[1:]
            if arguments and arguments[0] == "rm":
                raise SystemExit(0)
            if not arguments or arguments[0] != "run":
                raise SystemExit(64)

            mounts = {}
            for index, argument in enumerate(arguments):
                if argument != "--volume":
                    continue
                host, container, _mode = arguments[index + 1].rsplit(":", 2)
                mounts[container] = Path(host)
            snapshot = mounts["/repo"]
            report_root = mounts["/report"]
            files = sorted(
                str(item.relative_to(snapshot)) for item in snapshot.rglob("*") if item.is_file()
            )
            payload = {"arguments": arguments, "files": files}
            Path(os.environ["FAKE_DOCKER_LOG"]).write_text(
                json.dumps(payload), encoding="utf-8"
            )

            if os.environ.get("FAKE_DOCKER_MODE") == "findings":
                marker = os.environ["FAKE_DOCKER_CANARY"]
                print(marker)
                print(marker, file=sys.stderr)
                report_root.joinpath("findings.json").write_text(
                    json.dumps(
                        [
                            {
                                "RuleID": "synthetic-marker",
                                "File": "/repo/changed.txt",
                                "StartLine": 7,
                                "Secret": marker,
                                "Match": marker,
                            }
                        ]
                    ),
                    encoding="utf-8",
                )
                raise SystemExit(1)
            raise SystemExit(0)
            """
        ),
        encoding="utf-8",
    )
    path.chmod(0o755)


def _make_repository(tmp_path: Path) -> tuple[Path, str, Path, Path]:
    repository = tmp_path / "repository"
    scripts = repository / "scripts"
    scripts.mkdir(parents=True)
    scanner = scripts / SCANNER_SOURCE.name
    shutil.copy2(SCANNER_SOURCE, scanner)
    scanner.chmod(0o755)
    (repository / "changed.txt").write_text("before\n", encoding="utf-8")
    (repository / "unchanged.txt").write_text("stable\n", encoding="utf-8")

    _git(repository, "init", "--quiet")
    _git(repository, "config", "user.email", "phase3b-validation@example.invalid")
    _git(repository, "config", "user.name", "Phase 3B Validation")
    _git(repository, "add", "--all")
    _git(repository, "commit", "--quiet", "-m", "baseline")
    base_commit = _git(repository, "rev-parse", "HEAD")

    binary_directory = tmp_path / "bin"
    binary_directory.mkdir()
    docker_log = tmp_path / "docker-log.json"
    _write_fake_docker(binary_directory / "docker")
    return repository, base_commit, binary_directory, docker_log


def _run_scanner(
    repository: Path,
    binary_directory: Path,
    docker_log: Path,
    *,
    base_sha: str | None,
    run_id: str = "phase3b_diff_test",
    docker_mode: str = "pass",
    canary: str = "unused",
) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment.update(
        {
            "PATH": f"{binary_directory}{os.pathsep}{environment['PATH']}",
            "RUN_ID": run_id,
            "FAKE_DOCKER_LOG": str(docker_log),
            "FAKE_DOCKER_MODE": docker_mode,
            "FAKE_DOCKER_CANARY": canary,
        }
    )
    if base_sha is None:
        environment.pop("BASE_SHA", None)
    else:
        environment["BASE_SHA"] = base_sha
    return subprocess.run(
        [str(repository / "scripts" / SCANNER_SOURCE.name)],
        cwd=repository,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def test_diff_scanner_copies_only_changed_and_untracked_regular_files(tmp_path: Path) -> None:
    repository, base_commit, binary_directory, docker_log = _make_repository(tmp_path)
    (repository / "changed.txt").write_text("after\n", encoding="utf-8")
    (repository / "untracked.txt").write_text("new\n", encoding="utf-8")

    result = _run_scanner(
        repository,
        binary_directory,
        docker_log,
        base_sha=base_commit,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith("DIFF_SECRET_SCAN_PASS files=2 base=")
    payload = json.loads(docker_log.read_text(encoding="utf-8"))
    assert payload["files"] == ["changed.txt", "untracked.txt"]
    arguments = payload["arguments"]
    assert "--pull=never" in arguments
    assert "--network" in arguments
    assert arguments[arguments.index("--network") + 1] == "none"
    assert "--redact" in arguments
    assert GITLEAKS_IMAGE in arguments


@pytest.mark.parametrize(
    ("base_sha", "run_id", "expected_error"),
    [
        (None, "phase3b_diff_test", "BASE_SHA is required"),
        ("not-a-commit", "phase3b_diff_test", "BASE_SHA must resolve to a commit"),
        ("BASE", "Not-A-Machine-Token", "RUN_ID must match"),
    ],
)
def test_diff_scanner_parameters_fail_closed(
    tmp_path: Path,
    base_sha: str | None,
    run_id: str,
    expected_error: str,
) -> None:
    repository, base_commit, binary_directory, docker_log = _make_repository(tmp_path)
    resolved_base = base_commit if base_sha == "BASE" else base_sha

    result = _run_scanner(
        repository,
        binary_directory,
        docker_log,
        base_sha=resolved_base,
        run_id=run_id,
    )

    assert result.returncode != 0
    assert expected_error in result.stderr
    assert not docker_log.exists()


@pytest.mark.parametrize("unsafe_kind", ["symlink", "special"])
def test_diff_scanner_rejects_symlink_and_special_files(
    tmp_path: Path,
    unsafe_kind: str,
) -> None:
    repository, base_commit, binary_directory, docker_log = _make_repository(tmp_path)
    unsafe_path = repository / f"unsafe-{unsafe_kind}"
    if unsafe_kind == "symlink":
        unsafe_path.symlink_to(repository / "unchanged.txt")
    else:
        os.mkfifo(unsafe_path)

    result = _run_scanner(
        repository,
        binary_directory,
        docker_log,
        base_sha=base_commit,
    )

    assert result.returncode != 0
    assert f"refused {unsafe_kind}" in result.stderr
    assert unsafe_path.name in result.stderr
    assert not docker_log.exists()


def test_diff_scanner_never_emits_scanner_body_or_synthetic_canary(tmp_path: Path) -> None:
    repository, base_commit, binary_directory, docker_log = _make_repository(tmp_path)
    canary = "synthetic_" + uuid.uuid4().hex + "_marker"
    (repository / "changed.txt").write_text(f"{canary}\n", encoding="utf-8")

    result = _run_scanner(
        repository,
        binary_directory,
        docker_log,
        base_sha=base_commit,
        docker_mode="findings",
        canary=canary,
    )

    assert result.returncode == 1
    assert canary not in result.stdout
    assert canary not in result.stderr
    assert result.stdout.strip() == (
        'SECRET_FINDING rule=synthetic-marker path="changed.txt" line=7'
    )
