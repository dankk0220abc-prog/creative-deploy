from __future__ import annotations

import runpy
import stat
from pathlib import Path
from typing import Any

from creativedeploy_api.core.secret_files import read_secret_file

REPOSITORY_ROOT = Path(__file__).resolve().parents[4]


def _script() -> dict[str, Any]:
    return runpy.run_path(str(REPOSITORY_ROOT / "scripts/prepare_staging_attempt.py"))


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
