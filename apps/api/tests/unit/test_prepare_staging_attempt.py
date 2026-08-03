from __future__ import annotations

import argparse
import os
import runpy
import stat
from pathlib import Path
from typing import Any

import pytest

from creativedeploy_api.core.secret_files import read_secret_file

REPOSITORY_ROOT = Path(__file__).resolve().parents[4]


def _script() -> dict[str, Any]:
    return runpy.run_path(str(REPOSITORY_ROOT / "scripts/prepare_staging_attempt.py"))


def _arguments(secret_root: Path, backup_root: Path | None) -> argparse.Namespace:
    return argparse.Namespace(
        run_id="symlink_test",
        secret_root=secret_root,
        backup_root=backup_root,
        host="localhost",
        database_name="symlink_test",
        admin_user="symlink_test_admin",
        migrator_user="symlink_test_migrator",
        runtime_user="symlink_test_runtime",
    )


def test_generated_secret_is_container_readable_but_not_writable(tmp_path: Path) -> None:
    write_secret = _script()["_write_secret"]

    write_secret(tmp_path, "database_admin_url", "synthetic-value")

    secret = tmp_path / "database_admin_url"
    assert stat.S_IMODE(secret.stat().st_mode) == 0o444
    assert read_secret_file(secret, setting_name="DATABASE_URL") == "synthetic-value"


def test_generated_tls_files_use_compose_bind_read_permissions(
    tmp_path: Path, monkeypatch: Any
) -> None:
    script = _script()

    def fake_run(command: list[str], **_kwargs: Any) -> None:
        key_path = Path(command[command.index("-keyout") + 1])
        certificate_path = Path(command[command.index("-out") + 1])
        key_path.write_text("synthetic-key\n", encoding="utf-8")
        certificate_path.write_text("synthetic-certificate\n", encoding="utf-8")

    monkeypatch.setattr(script["subprocess"], "run", fake_run)

    script["_certificate"](tmp_path, "localhost")

    assert stat.S_IMODE((tmp_path / "tls_private_key.pem").stat().st_mode) == 0o444
    assert stat.S_IMODE((tmp_path / "tls_certificate.pem").stat().st_mode) == 0o444


@pytest.mark.parametrize("absolute_target", [False, True])
def test_temporary_path_refuses_dangling_leaf_symlink_without_creating_target(
    tmp_path: Path,
    absolute_target: bool,
) -> None:
    temporary_path = _script()["_temporary_path"]
    target = tmp_path / "missing-target"
    link = tmp_path / "candidate-link"
    link.symlink_to(target if absolute_target else target.name, target_is_directory=True)

    with pytest.raises(SystemExit, match="must not be a symbolic link"):
        temporary_path(link, description="staging backup")

    assert link.is_symlink()
    assert not target.exists()


def test_temporary_path_refuses_leaf_symlink_to_existing_directory_without_changes(
    tmp_path: Path,
) -> None:
    temporary_path = _script()["_temporary_path"]
    target = tmp_path / "existing-target"
    target.mkdir(mode=0o710)
    marker = target / "marker"
    marker.write_bytes(b"existing-target-bytes")
    target.chmod(0o710)
    before = target.stat()
    link = tmp_path / "candidate-link"
    link.symlink_to(target, target_is_directory=True)

    with pytest.raises(SystemExit, match="must not be a symbolic link"):
        temporary_path(link, description="staging secret")

    after = target.stat()
    assert link.is_symlink()
    assert marker.read_bytes() == b"existing-target-bytes"
    assert (after.st_ino, after.st_mtime_ns, stat.S_IMODE(after.st_mode)) == (
        before.st_ino,
        before.st_mtime_ns,
        0o710,
    )


def test_validate_symlink_failure_creates_no_staging_payload(tmp_path: Path) -> None:
    validate = _script()["_validate"]
    target = tmp_path / "missing-backup-target"
    backup_link = tmp_path / "backups"
    backup_link.symlink_to(target.name, target_is_directory=True)
    secret_root = tmp_path / "secrets"

    with pytest.raises(SystemExit, match="must not be a symbolic link"):
        validate(_arguments(secret_root, backup_link))

    assert backup_link.is_symlink()
    assert not target.exists()
    assert not secret_root.exists()
    assert list(tmp_path.iterdir()) == [backup_link]


def test_normal_roots_are_created_private_and_owned_by_attempt_user(
    tmp_path: Path,
) -> None:
    validate = _script()["_validate"]
    secret_root = tmp_path / "secrets"
    backup_root = tmp_path / "backups"

    assert validate(_arguments(secret_root, backup_root)) == secret_root

    for root in (secret_root, backup_root):
        root_stat = root.lstat()
        assert stat.S_ISDIR(root_stat.st_mode)
        assert not stat.S_ISLNK(root_stat.st_mode)
        assert root_stat.st_uid == os.geteuid()
        assert root_stat.st_gid == os.getegid()
        assert stat.S_IMODE(root_stat.st_mode) == 0o700


def test_private_root_verification_refuses_wrong_mode_without_repair(
    tmp_path: Path,
) -> None:
    verify_private_root = _script()["_verify_private_root"]
    root = tmp_path / "wrong-mode"
    root.mkdir(mode=0o750)
    root.chmod(0o750)

    with pytest.raises(SystemExit, match="ownership or permissions are invalid"):
        verify_private_root(root, description="staging backup")

    assert stat.S_IMODE(root.stat().st_mode) == 0o750


def test_private_root_verification_refuses_wrong_owner(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script = _script()
    root = tmp_path / "wrong-owner"
    root.mkdir(mode=0o700)
    expected_uid = os.geteuid()
    monkeypatch.setattr(script["os"], "geteuid", lambda: expected_uid + 1)

    with pytest.raises(SystemExit, match="ownership or permissions are invalid"):
        script["_verify_private_root"](root, description="staging secret")

    assert root.exists()
    assert root.stat().st_uid == expected_uid
    assert stat.S_IMODE(root.stat().st_mode) == 0o700


def test_parent_symlink_resolving_outside_temporary_roots_is_refused(
    tmp_path: Path,
) -> None:
    temporary_path = _script()["_temporary_path"]
    parent_link = tmp_path / "outside-parent"
    parent_link.symlink_to(REPOSITORY_ROOT, target_is_directory=True)
    candidate = parent_link / "must-not-exist"

    with pytest.raises(SystemExit, match="beneath a temporary root"):
        temporary_path(candidate, description="staging backup")

    assert parent_link.is_symlink()
    assert not (REPOSITORY_ROOT / "must-not-exist").exists()
