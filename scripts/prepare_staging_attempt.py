#!/usr/bin/env python3
"""Create one isolated synthetic staging secret and local TLS bundle under /tmp."""

from __future__ import annotations

import argparse
import ipaddress
import os
import re
import secrets
import subprocess
from pathlib import Path
from urllib.parse import quote

RUN_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_]{0,39}$")
ROLE_PATTERN = re.compile(r"^[a-z][a-z0-9_]{2,62}$")
HOST_PATTERN = re.compile(
    r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)(?:\.(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?))*$"
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--secret-root", type=Path, required=True)
    parser.add_argument("--host", required=True)
    parser.add_argument("--database-name", required=True)
    parser.add_argument("--admin-user", required=True)
    parser.add_argument("--migrator-user", required=True)
    parser.add_argument("--runtime-user", required=True)
    return parser


def _write_secret(root: Path, name: str, value: str) -> None:
    path = root / name
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", closefd=True) as stream:
            stream.write(value)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        # Docker Compose implements file-backed secrets as bind mounts. On a
        # Linux CI runner the source owner is not the non-root container user,
        # so owner-only files are unreadable in the container. The 0700 parent
        # keeps the attempt private on the host; the bind source itself must be
        # read-only for every consuming container identity.
        path.chmod(0o444)
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def _validate(arguments: argparse.Namespace) -> Path:
    if RUN_ID_PATTERN.fullmatch(arguments.run_id) is None:
        raise SystemExit("run ID has an invalid format")
    for role in (arguments.admin_user, arguments.migrator_user, arguments.runtime_user):
        if ROLE_PATTERN.fullmatch(role) is None:
            raise SystemExit("database role has an invalid format")
    if (
        len({arguments.admin_user, arguments.migrator_user, arguments.runtime_user})
        != 3
    ):
        raise SystemExit("database roles must be distinct")
    if ROLE_PATTERN.fullmatch(arguments.database_name) is None:
        raise SystemExit("database name has an invalid format")
    host = arguments.host.lower().removesuffix(".")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        if HOST_PATTERN.fullmatch(host) is None or "*" in host:
            raise SystemExit("staging host must be one exact normalized host") from None
    arguments.host = host
    root = arguments.secret_root.expanduser().resolve(strict=False)
    temporary_roots = {
        Path("/tmp").resolve(strict=True),
        Path(os.environ.get("TMPDIR", "/tmp")).resolve(strict=True),
    }
    if not any(
        root.is_relative_to(temporary_root) for temporary_root in temporary_roots
    ):
        raise SystemExit("staging secrets must be created beneath a temporary root")
    if root.exists():
        raise SystemExit("staging secret root already exists")
    root.mkdir(mode=0o700, parents=True)
    return root


def _database_url(user: str, password: str, database: str) -> str:
    return (
        f"postgresql+psycopg://{quote(user, safe='')}:{quote(password, safe='')}"
        f"@postgres:5432/{quote(database, safe='')}"
    )


def _certificate(root: Path, host: str) -> None:
    try:
        ipaddress.ip_address(host)
    except ValueError:
        subject_alt_name = f"DNS:{host}"
    else:
        subject_alt_name = f"IP:{host}"
    config = root / ".openssl.cnf"
    config.write_text(
        """[req]
distinguished_name = subject
prompt = no
x509_extensions = extensions
[subject]
CN = STAGING_HOST
[extensions]
subjectAltName = STAGING_ALT_NAME
basicConstraints = critical,CA:FALSE
keyUsage = critical,digitalSignature,keyEncipherment
extendedKeyUsage = serverAuth
""".replace("STAGING_HOST", host).replace("STAGING_ALT_NAME", subject_alt_name),
        encoding="utf-8",
    )
    key_path = root / "tls_private_key.pem"
    certificate_path = root / "tls_certificate.pem"
    try:
        subprocess.run(
            [
                "openssl",
                "req",
                "-x509",
                "-newkey",
                "rsa:2048",
                "-sha256",
                "-nodes",
                "-days",
                "2",
                "-config",
                str(config),
                "-keyout",
                str(key_path),
                "-out",
                str(certificate_path),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        raise SystemExit("local staging certificate generation failed") from error
    finally:
        config.unlink(missing_ok=True)
    key_path.chmod(0o444)
    certificate_path.chmod(0o444)


def main() -> int:
    arguments = _parser().parse_args()
    root = _validate(arguments)
    admin_password = secrets.token_urlsafe(32)
    migrator_password = secrets.token_urlsafe(32)
    runtime_password = secrets.token_urlsafe(32)
    _write_secret(root, "postgres_admin_password", admin_password)
    _write_secret(
        root,
        "database_admin_url",
        _database_url(arguments.admin_user, admin_password, arguments.database_name),
    )
    _write_secret(root, "database_migrator_password", migrator_password)
    _write_secret(
        root,
        "database_migrator_url",
        _database_url(
            arguments.migrator_user, migrator_password, arguments.database_name
        ),
    )
    _write_secret(root, "database_runtime_password", runtime_password)
    _write_secret(
        root,
        "database_runtime_url",
        _database_url(
            arguments.runtime_user, runtime_password, arguments.database_name
        ),
    )
    _write_secret(root, "oidc_client_secret", secrets.token_urlsafe(32))
    _write_secret(root, "s3_access_key_id", f"p2b2{secrets.token_hex(8)}")
    _write_secret(root, "s3_secret_access_key", secrets.token_urlsafe(32))
    _write_secret(root, "backup_signing_key", secrets.token_urlsafe(48))
    _certificate(root, arguments.host)
    print("STAGING_SECRETS_READY files=12 secret_values_logged=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
