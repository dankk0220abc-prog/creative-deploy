"""Consistent PostgreSQL and private-S3 staging backup/restore operations.

The API must be quiesced before either operation. Restore additionally refuses
any database whose name is not an isolated Phase 2B-2 restore attempt.
"""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import hmac
import io
import json
import os
import re
import shutil
import stat
import tempfile
import uuid
from collections.abc import Sequence
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import boto3  # type: ignore[import-untyped]
import psycopg
from botocore.client import Config  # type: ignore[import-untyped]
from botocore.exceptions import BotoCoreError, ClientError  # type: ignore[import-untyped]
from psycopg import sql
from psycopg.rows import dict_row
from sqlalchemy.engine import make_url

from creativedeploy_api.core.config import Settings
from creativedeploy_api.core.secret_files import SecretFileError, read_secret_file
from creativedeploy_api.storage.images import STORAGE_KEY_PATTERN

BACKUP_FORMAT = "creativedeploy-staging-backup-v1"
EXPECTED_ALEMBIC_REVISION = "5a01b2c3d4e5"
MANIFEST_VERSION = 1
MANIFEST_SIGNATURE_FORMAT = "creativedeploy-manifest-signature-v1"
MANIFEST_SIGNATURE_ALGORITHM = "HMAC-SHA-256"
MANIFEST_CANONICALIZATION = "json-sort-keys-compact-ascii-v1"
MANIFEST_PATH = "manifest.json"
MANIFEST_SIGNATURE_PATH = "manifest.hmac.json"
MANIFEST_CONTROL_PATHS = frozenset({MANIFEST_PATH, MANIFEST_SIGNATURE_PATH})
MINIMUM_SIGNING_KEY_BYTES = 32
BACKUP_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
SIGNING_KEY_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,63}$")
RESTORE_DATABASE_PATTERN = re.compile(r"^p2b2r_[a-z0-9][a-z0-9_]{0,39}$")
LEGACY_TABLES = (
    "user_accounts",
    "external_identities",
    "paint_projects",
    "project_memberships",
    "oidc_login_flows",
    "auth_sessions",
    "state_transition_events",
    "command_idempotency_records",
    "image_assets",
    "image_set_readiness_reviews",
    "region_sets",
    "regions",
    "region_vertices",
    "region_set_reviews",
)
PHASE3A_TABLES = (
    "provider_definitions",
    "capability_definitions",
    "model_definitions",
    "provider_capabilities",
    "model_capabilities",
    "credential_records",
    "credential_project_grants",
    "user_provider_preferences",
    "project_model_policies",
    "project_model_policy_providers",
    "project_model_policy_models",
    "project_model_policy_capabilities",
    "project_model_policy_credentials",
    "user_budget_policies",
    "project_budget_policies",
    "user_budget_counters",
    "project_budget_counters",
    "invocation_requests",
    "invocation_attempts",
    "budget_reservations",
    "ai_invocation_events",
    "ai_usage_ledger",
    "ai_cost_ledger",
    "ai_audit_events",
    "ai_command_idempotency_records",
)
PHASE3B_TABLES = (
    "provider_pricing_snapshots",
    "prompt_template_definitions",
    "paint_plans",
    "paint_plan_region_instructions",
    "paint_plan_review_events",
)
TABLES = (*LEGACY_TABLES, *PHASE3A_TABLES, *PHASE3B_TABLES)

# Migration D creates deterministic reference rows in every fresh head database.
# A restore may replace only this exact seed-only state; any other partial state
# remains unsupported. The fingerprints cover complete to_jsonb rows ordered by
# primary key, not merely identifiers or row counts.
MIGRATION_SEED_FINGERPRINTS: dict[str, tuple[int, str]] = {
    "provider_definitions": (
        3,
        "a532cf375498338ac7e2d1e5d4a35167045d5ec7f40bca627a63f5bd5dbe4557",
    ),
    "capability_definitions": (
        3,
        "e640acaa636c6e413e316782e9452c8802b8c6bee9091018205674f57dfd15e8",
    ),
    "model_definitions": (
        5,
        "824f5fc6e1046e7b237cfab840f35ceb03cf6f736e5acc13a6b955255779df5c",
    ),
    "provider_capabilities": (
        9,
        "176dc5392f198890969d10712fcdaf16efddc30b35c1bdc7f7b843e47b55e4cc",
    ),
    "model_capabilities": (
        13,
        "f6944cfd3d8f75acdf77598aa362295bb910ad937663dacd9baa91593099918d",
    ),
    "provider_pricing_snapshots": (
        3,
        "bcabf48b69027fdf222f601967b348bef6bee9c3a64870d26557a7a41f8fa99b",
    ),
    "prompt_template_definitions": (
        1,
        "4a1e148603126350c0eab5f990423036c0c39c6bec505f704ed95580294c3672",
    ),
}
DEFERRED_COLUMNS: dict[str, tuple[str, ...]] = {
    "paint_projects": ("current_image_asset_id",),
    "image_assets": ("supersedes_image_asset_id",),
    "region_sets": ("supersedes_region_set_id", "based_on_region_set_id"),
    "credential_records": ("replaces_credential_id",),
    "invocation_requests": ("final_attempt_id",),
    "invocation_attempts": ("retry_of_attempt_id",),
}
ORDER_COLUMNS: dict[str, tuple[str, ...]] = {
    "image_assets": ("paint_project_id", "role", "version", "id"),
    "region_sets": ("paint_project_id", "version", "id"),
    "regions": ("region_set_id", "z_index", "id"),
    "region_vertices": ("region_set_id", "region_id", "sequence"),
    "paint_plans": ("paint_project_id", "version", "id"),
    "paint_plan_region_instructions": ("paint_plan_id", "sequence", "id"),
    "paint_plan_review_events": ("paint_plan_id", "created_at", "id"),
}


class OperationsError(RuntimeError):
    """An operation failed without including secret material."""


@dataclass(frozen=True, slots=True)
class BackupSigningConfig:
    """One provider-neutral manifest signing identity and secret key."""

    key_id: str
    key: bytes


def _required_flag(name: str) -> None:
    if os.environ.get(name) != "true":
        raise OperationsError(f"{name}=true is required.")


def _backup_signing_config() -> BackupSigningConfig:
    key_id = os.environ.get("BACKUP_SIGNING_KEY_ID")
    if (
        key_id is None
        or key_id != key_id.strip()
        or SIGNING_KEY_ID_PATTERN.fullmatch(key_id) is None
    ):
        raise OperationsError("BACKUP_SIGNING_KEY_ID is missing or invalid.")
    raw_path = os.environ.get("BACKUP_SIGNING_KEY_FILE")
    if raw_path is None or raw_path != raw_path.strip() or not raw_path:
        raise OperationsError("BACKUP_SIGNING_KEY_FILE is missing or invalid.")
    try:
        value = read_secret_file(Path(raw_path), setting_name="BACKUP_SIGNING_KEY")
    except SecretFileError as error:
        raise OperationsError("The backup signing key file is unavailable or invalid.") from error
    key = value.encode("utf-8")
    if len(key) < MINIMUM_SIGNING_KEY_BYTES:
        raise OperationsError("The backup signing key is too short.")
    return BackupSigningConfig(key_id=key_id, key=key)


def _backup_root() -> Path:
    raw_root = Path(os.environ.get("BACKUP_ROOT", "/backups"))
    try:
        if raw_root.is_symlink():
            raise OperationsError("BACKUP_ROOT must be an existing private directory.")
        root = raw_root.resolve(strict=True)
        root_stat = root.stat()
    except OSError as error:
        raise OperationsError("BACKUP_ROOT must be an existing private directory.") from error
    if not root.is_dir():
        raise OperationsError("BACKUP_ROOT must be an existing private directory.")
    if (
        root_stat.st_uid != os.geteuid()
        or root_stat.st_gid != os.getegid()
        or stat.S_IMODE(root_stat.st_mode) != 0o700
    ):
        raise OperationsError("BACKUP_ROOT ownership or permissions are invalid.")
    return root


def _backup_path(backup_id: str) -> Path:
    if BACKUP_ID_PATTERN.fullmatch(backup_id) is None:
        raise OperationsError("backup ID has an invalid format.")
    return _backup_root() / backup_id


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(64 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_manifest_bytes(manifest: dict[str, Any]) -> bytes:
    """Return the one stable byte representation covered by the detached HMAC."""
    return json.dumps(
        manifest,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _manifest_hmac(manifest: dict[str, Any], signing: BackupSigningConfig) -> str:
    return hmac.new(
        signing.key,
        _canonical_manifest_bytes(manifest),
        hashlib.sha256,
    ).hexdigest()


def _strict_json_object(path: Path, *, description: str) -> dict[str, Any]:
    def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate key")
            result[key] = value
        return result

    try:
        payload = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=reject_duplicate_keys,
        )
    except (OSError, ValueError) as error:
        raise OperationsError(f"{description} is unavailable or invalid.") from error
    if not isinstance(payload, dict):
        raise OperationsError(f"{description} is unavailable or invalid.")
    return payload


def _write_detached_manifest_signature(
    root: Path,
    manifest: dict[str, Any],
    signing: BackupSigningConfig,
) -> None:
    _write_json(
        root / MANIFEST_SIGNATURE_PATH,
        {
            "format": MANIFEST_SIGNATURE_FORMAT,
            "algorithm": MANIFEST_SIGNATURE_ALGORITHM,
            "canonicalization": MANIFEST_CANONICALIZATION,
            "key_id": signing.key_id,
            "manifest_hmac_sha256": _manifest_hmac(manifest, signing),
        },
    )


def _verify_detached_manifest_signature(
    root: Path,
    manifest: dict[str, Any],
    signing: BackupSigningConfig,
) -> None:
    signature = _strict_json_object(
        root / MANIFEST_SIGNATURE_PATH,
        description="Backup manifest signature",
    )
    authenticity = manifest.get("authenticity")
    expected_authenticity = {
        "algorithm": MANIFEST_SIGNATURE_ALGORITHM,
        "canonicalization": MANIFEST_CANONICALIZATION,
        "key_id": signing.key_id,
        "signature_file": MANIFEST_SIGNATURE_PATH,
    }
    if authenticity != expected_authenticity:
        raise OperationsError("Backup manifest signing identity is invalid.")
    if set(signature) != {
        "format",
        "algorithm",
        "canonicalization",
        "key_id",
        "manifest_hmac_sha256",
    }:
        raise OperationsError("Backup manifest signature structure is invalid.")
    if (
        signature.get("format") != MANIFEST_SIGNATURE_FORMAT
        or signature.get("algorithm") != MANIFEST_SIGNATURE_ALGORITHM
        or signature.get("canonicalization") != MANIFEST_CANONICALIZATION
        or signature.get("key_id") != signing.key_id
    ):
        raise OperationsError("Backup manifest signature identity is invalid.")
    supplied = signature.get("manifest_hmac_sha256")
    if not isinstance(supplied, str) or re.fullmatch(r"[0-9a-f]{64}", supplied) is None:
        raise OperationsError("Backup manifest signature value is invalid.")
    expected = _manifest_hmac(manifest, signing)
    if not hmac.compare_digest(supplied, expected):
        raise OperationsError("Backup manifest authenticity verification failed.")


def _database_connection(settings: Settings) -> psycopg.Connection[dict[str, Any]]:
    sqlalchemy_url = make_url(settings.require_database_url().get_secret_value())
    connection_url = sqlalchemy_url.set(drivername="postgresql").render_as_string(
        hide_password=False
    )
    return psycopg.connect(connection_url, row_factory=dict_row)


def _s3_client(settings: Settings) -> tuple[Any, str]:
    endpoint, region, bucket, access_key, secret_key, _ = settings.require_s3_image_storage()
    client = boto3.client(
        "s3",
        endpoint_url=endpoint,
        region_name=region,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "path" if settings.s3_force_path_style else "virtual"},
            retries={"max_attempts": 3, "mode": "standard"},
        ),
    )
    return client, bucket


def _database_name(connection: psycopg.Connection[dict[str, Any]]) -> str:
    row = connection.execute("SELECT current_database() AS name").fetchone()
    if row is None or not isinstance(row["name"], str):
        raise OperationsError("The selected PostgreSQL database could not be identified.")
    return row["name"]


def _alembic_revision(connection: psycopg.Connection[dict[str, Any]]) -> str:
    row = connection.execute("SELECT version_num FROM alembic_version").fetchone()
    if row is None or row["version_num"] != EXPECTED_ALEMBIC_REVISION:
        raise OperationsError("The PostgreSQL Alembic revision is not supported.")
    return str(row["version_num"])


def _table_columns(connection: psycopg.Connection[dict[str, Any]], table: str) -> tuple[str, ...]:
    rows = connection.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = %s
        ORDER BY ordinal_position
        """,
        (table,),
    ).fetchall()
    columns = tuple(str(row["column_name"]) for row in rows)
    if not columns:
        raise OperationsError(f"Required table {table} is missing.")
    return tuple(column for column in columns if column not in DEFERRED_COLUMNS.get(table, ()))


def _primary_key_columns(
    connection: psycopg.Connection[dict[str, Any]], table: str
) -> tuple[str, ...]:
    rows = connection.execute(
        """
        SELECT a.attname AS column_name
        FROM pg_index i
        JOIN pg_class c ON c.oid = i.indrelid
        JOIN pg_namespace n ON n.oid = c.relnamespace
        JOIN unnest(i.indkey) WITH ORDINALITY AS key(attnum, ordinal) ON true
        JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum = key.attnum
        WHERE n.nspname = 'public' AND c.relname = %s AND i.indisprimary
        ORDER BY key.ordinal
        """,
        (table,),
    ).fetchall()
    return tuple(str(row["column_name"]) for row in rows)


def _schema_snapshot(connection: psycopg.Connection[dict[str, Any]]) -> dict[str, object]:
    columns = connection.execute(
        """
        SELECT table_name, column_name, ordinal_position, data_type, udt_name,
               is_nullable, column_default
        FROM information_schema.columns
        WHERE table_schema = 'public'
        ORDER BY table_name, ordinal_position
        """
    ).fetchall()
    constraints = connection.execute(
        """
        SELECT c.relname AS table_name, con.conname AS constraint_name,
               con.contype AS constraint_type, pg_get_constraintdef(con.oid) AS definition
        FROM pg_constraint con
        JOIN pg_class c ON c.oid = con.conrelid
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public'
        ORDER BY c.relname, con.conname
        """
    ).fetchall()
    indexes = connection.execute(
        """
        SELECT tablename AS table_name, indexname AS index_name, indexdef AS definition
        FROM pg_indexes
        WHERE schemaname = 'public'
        ORDER BY tablename, indexname
        """
    ).fetchall()
    return {
        "alembic_revision": _alembic_revision(connection),
        "columns": [dict(row) for row in columns],
        "constraints": [dict(row) for row in constraints],
        "indexes": [dict(row) for row in indexes],
    }


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _export_table(
    connection: psycopg.Connection[dict[str, Any]], table: str, destination: Path
) -> int:
    columns = _table_columns(connection, table)
    order_columns = ORDER_COLUMNS.get(table) or _primary_key_columns(connection, table)
    deferred_columns = frozenset(DEFERRED_COLUMNS.get(table, ()))
    selected_columns = [
        sql.SQL("NULL AS {}").format(sql.Identifier(column))
        if column in deferred_columns
        else sql.Identifier(column)
        for column in columns
    ]
    select = sql.SQL("SELECT {} FROM {} ORDER BY {}").format(
        sql.SQL(", ").join(selected_columns),
        sql.Identifier(table),
        sql.SQL(", ").join(sql.Identifier(column) for column in order_columns),
    )
    copy_statement = sql.SQL(
        "COPY ({}) TO STDOUT WITH (FORMAT CSV, HEADER TRUE, FORCE_QUOTE *)"
    ).format(select)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with (
        destination.open("wb") as stream,
        connection.cursor().copy(copy_statement) as copy,
    ):
        for block in copy:
            stream.write(bytes(block))
    row = connection.execute(
        sql.SQL("SELECT count(*) AS count FROM {}").format(sql.Identifier(table))
    ).fetchone()
    return int(row["count"] if row is not None else 0)


def _pointer_snapshot(connection: psycopg.Connection[dict[str, Any]]) -> dict[str, object]:
    pointers: dict[str, object] = {}
    for table, pointer_columns in DEFERRED_COLUMNS.items():
        primary_keys = _primary_key_columns(connection, table)
        selected = (*primary_keys, *pointer_columns)
        query = sql.SQL("SELECT {} FROM {} ORDER BY {}").format(
            sql.SQL(", ").join(sql.Identifier(column) for column in selected),
            sql.Identifier(table),
            sql.SQL(", ").join(sql.Identifier(column) for column in primary_keys),
        )
        rows = connection.execute(query).fetchall()
        pointers[table] = [
            {column: None if row[column] is None else str(row[column]) for column in selected}
            for row in rows
            if any(row[column] is not None for column in pointer_columns)
        ]
    return pointers


def _database_object_inventory(
    connection: psycopg.Connection[dict[str, Any]],
) -> dict[str, dict[str, object]]:
    rows = connection.execute(
        """
        SELECT storage_key, byte_size, sha256, declared_content_type
        FROM image_assets
        WHERE storage_provider = 's3'
        ORDER BY storage_key
        """
    ).fetchall()
    inventory: dict[str, dict[str, object]] = {}
    for row in rows:
        key = str(row["storage_key"])
        if key in inventory or STORAGE_KEY_PATTERN.fullmatch(key) is None:
            raise OperationsError("The database contains an invalid or duplicate object key.")
        inventory[key] = {
            "key": key,
            "byte_size": int(row["byte_size"]),
            "sha256": str(row["sha256"]),
            "content_type": str(row["declared_content_type"]),
        }
    return inventory


def _list_s3_objects(client: Any, bucket: str) -> dict[str, int]:
    found: dict[str, int] = {}
    continuation: str | None = None
    while True:
        arguments: dict[str, object] = {"Bucket": bucket, "Prefix": "objects/"}
        if continuation is not None:
            arguments["ContinuationToken"] = continuation
        response = client.list_objects_v2(**arguments)
        for item in response.get("Contents", []):
            key = item.get("Key")
            size = item.get("Size")
            if not isinstance(key, str) or not isinstance(size, int):
                raise OperationsError("Object storage returned invalid inventory metadata.")
            found[key] = size
        if not response.get("IsTruncated"):
            return found
        continuation = response.get("NextContinuationToken")
        if not isinstance(continuation, str):
            raise OperationsError("Object inventory pagination is invalid.")


def _stream_and_verify_object(
    client: Any,
    bucket: str,
    item: dict[str, object],
    *,
    destination: Path | None = None,
) -> None:
    """GET and stream one object while independently verifying governed facts."""
    key = item.get("key")
    byte_size = item.get("byte_size")
    checksum = item.get("sha256")
    content_type = item.get("content_type")
    if (
        not isinstance(key, str)
        or STORAGE_KEY_PATTERN.fullmatch(key) is None
        or isinstance(byte_size, bool)
        or not isinstance(byte_size, int)
        or byte_size < 0
        or not isinstance(checksum, str)
        or re.fullmatch(r"[0-9a-f]{64}", checksum) is None
        or not isinstance(content_type, str)
        or not content_type
    ):
        raise OperationsError("A private object inventory fact is invalid.")
    body: Any | None = None
    stream: Any | None = None
    try:
        response = client.get_object(Bucket=bucket, Key=key)
        body = response.get("Body")
        if body is None or not hasattr(body, "read"):
            raise OperationsError("A private object response body is invalid.")
        metadata = response.get("Metadata")
        if (
            response.get("ContentLength") != byte_size
            or response.get("ContentType") != content_type
            or not isinstance(metadata, dict)
            or metadata.get("sha256") != checksum
        ):
            raise OperationsError("A private object response fact does not match the backup.")
        if destination is not None:
            destination.parent.mkdir(parents=True, exist_ok=True)
            stream = destination.open("xb")
        digest = hashlib.sha256()
        observed_size = 0
        while True:
            chunk = body.read(64 * 1024)
            if not chunk:
                break
            if not isinstance(chunk, bytes):
                raise OperationsError("A private object stream returned invalid bytes.")
            observed_size += len(chunk)
            if observed_size > byte_size:
                raise OperationsError("A private object stream exceeded its expected size.")
            digest.update(chunk)
            if stream is not None:
                stream.write(chunk)
        if observed_size != byte_size or digest.hexdigest() != checksum:
            raise OperationsError("A private object byte checksum does not match the backup.")
    except OperationsError:
        raise
    except Exception as error:
        raise OperationsError("A private object could not be read and verified.") from error
    finally:
        if stream is not None:
            stream.close()
        if body is not None:
            with suppress(Exception):
                body.close()


def _download_objects(
    client: Any,
    bucket: str,
    inventory: dict[str, dict[str, object]],
    destination: Path,
) -> None:
    listed = _list_s3_objects(client, bucket)
    if set(listed) != set(inventory):
        raise OperationsError("Database references and private object inventory do not match.")
    for key, item in inventory.items():
        if listed[key] != item["byte_size"]:
            raise OperationsError("A private object size does not match its database reference.")
        object_path = destination / "objects" / key
        _stream_and_verify_object(
            client,
            bucket,
            item,
            destination=object_path,
        )


def _manifest_files(root: Path) -> list[dict[str, object]]:
    files: list[dict[str, object]] = []
    for path in sorted(candidate for candidate in root.rglob("*") if candidate.is_file()):
        relative = path.relative_to(root).as_posix()
        if relative in MANIFEST_CONTROL_PATHS:
            continue
        files.append({"path": relative, "byte_size": path.stat().st_size, "sha256": _sha256(path)})
    return files


def _verify_manifest_files(root: Path, manifest: dict[str, Any]) -> None:
    expected = manifest.get("files")
    if not isinstance(expected, list):
        raise OperationsError("Backup manifest file inventory is invalid.")
    actual_paths: set[str] = set()
    for item in expected:
        if not isinstance(item, dict):
            raise OperationsError("Backup manifest file entry is invalid.")
        relative = item.get("path")
        if (
            not isinstance(relative, str)
            or relative.startswith("/")
            or ".." in Path(relative).parts
        ):
            raise OperationsError("Backup manifest contains an unsafe path.")
        path = root / relative
        if (
            not path.is_file()
            or path.is_symlink()
            or path.stat().st_size != item.get("byte_size")
            or _sha256(path) != item.get("sha256")
        ):
            raise OperationsError("Backup file size or checksum validation failed.")
        actual_paths.add(relative)
    disk_paths = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path.relative_to(root).as_posix() not in MANIFEST_CONTROL_PATHS
    }
    if actual_paths != disk_paths:
        raise OperationsError("Backup directory contains an unmanifested or missing file.")


def _read_manifest(root: Path) -> dict[str, Any]:
    payload = _strict_json_object(
        root / MANIFEST_PATH,
        description="Backup manifest",
    )
    signing = _backup_signing_config()
    _verify_detached_manifest_signature(root, payload, signing)
    if (
        payload.get("format") != BACKUP_FORMAT
        or payload.get("manifest_version") != MANIFEST_VERSION
    ):
        raise OperationsError("Backup format is not supported.")
    if payload.get("alembic_revision") != EXPECTED_ALEMBIC_REVISION:
        raise OperationsError("Backup Alembic revision is not supported.")
    _manifest_table_counts(payload)
    _verify_manifest_files(root, payload)
    return payload


def _manifest_table_counts(manifest: dict[str, Any]) -> dict[str, int]:
    payload = manifest.get("table_counts")
    if not isinstance(payload, dict) or set(payload) != set(TABLES):
        raise OperationsError("Backup table counts are invalid.")
    counts: dict[str, int] = {}
    for table in TABLES:
        value = payload[table]
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise OperationsError("Backup table counts are invalid.")
        counts[table] = value
    return counts


def _write_database_snapshot(
    connection: psycopg.Connection[dict[str, Any]], root: Path
) -> tuple[dict[str, int], dict[str, object]]:
    schema = _schema_snapshot(connection)
    _write_json(root / "schema.json", schema)
    table_counts: dict[str, int] = {}
    for table in TABLES:
        table_counts[table] = _export_table(connection, table, root / "tables" / f"{table}.csv")
    _write_json(root / "pointers.json", _pointer_snapshot(connection))
    return table_counts, schema


def _backup(backup_id: str, *, dry_run: bool) -> None:
    _required_flag("OPERATIONS_QUIESCED")
    signing = _backup_signing_config()
    settings = Settings.model_validate({})
    client, bucket = _s3_client(settings)
    destination = _backup_path(backup_id)
    with _database_connection(settings) as connection:
        database_name = _database_name(connection)
        revision = _alembic_revision(connection)
        inventory = _database_object_inventory(connection)
        listed = _list_s3_objects(client, bucket)
        if set(listed) != set(inventory):
            raise OperationsError("Database references and private object inventory do not match.")
        if dry_run:
            print(
                "BACKUP_DRY_RUN_OK"
                f" database={database_name} alembic={revision}"
                f" objects={len(inventory)} secret_values_logged=0"
            )
            return
        if destination.exists():
            raise OperationsError("The requested backup ID already exists.")
        partial = destination.with_name(f".{destination.name}.partial-{uuid.uuid4().hex}")
        partial.mkdir(mode=0o700)
        try:
            connection.commit()
            connection.execute(
                "BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY DEFERRABLE"
            )
            table_counts, schema = _write_database_snapshot(connection, partial)
            database_inventory = _database_object_inventory(connection)
            connection.execute("COMMIT")
            _write_json(partial / "objects.json", list(database_inventory.values()))
            _download_objects(client, bucket, database_inventory, partial)
            manifest = {
                "format": BACKUP_FORMAT,
                "manifest_version": MANIFEST_VERSION,
                "created_at": datetime.now(UTC).isoformat(),
                "backup_id": backup_id,
                "run_id": os.environ.get("STAGING_RUN_ID", "unknown"),
                "source_commit": os.environ.get("SOURCE_GIT_COMMIT", "unknown"),
                "application_version": settings.app_version,
                "alembic_revision": revision,
                "database_name": database_name,
                "schema_sha256": hashlib.sha256(
                    json.dumps(schema, sort_keys=True, separators=(",", ":")).encode()
                ).hexdigest(),
                "table_counts": table_counts,
                "object_count": len(database_inventory),
                "objects": list(database_inventory.values()),
                "files": _manifest_files(partial),
                "authenticity": {
                    "algorithm": MANIFEST_SIGNATURE_ALGORITHM,
                    "canonicalization": MANIFEST_CANONICALIZATION,
                    "key_id": signing.key_id,
                    "signature_file": MANIFEST_SIGNATURE_PATH,
                },
            }
            _write_json(partial / MANIFEST_PATH, manifest)
            _write_detached_manifest_signature(partial, manifest, signing)
            partial.rename(destination)
        except BaseException:
            shutil.rmtree(partial, ignore_errors=True)
            raise
    print(
        f"BACKUP_COMPLETE backup_id={backup_id} tables={len(TABLES)}"
        f" objects={len(inventory)} secret_values_logged=0"
    )


def backup(backup_id: str, *, dry_run: bool) -> None:
    previous_umask = os.umask(0o077)
    try:
        _backup(backup_id, dry_run=dry_run)
    finally:
        os.umask(previous_umask)


def _parse_object_inventory(payload: object) -> dict[str, dict[str, object]]:
    if not isinstance(payload, list):
        raise OperationsError("Backup object inventory is invalid.")
    inventory: dict[str, dict[str, object]] = {}
    for item in payload:
        if not isinstance(item, dict) or not isinstance(item.get("key"), str):
            raise OperationsError("Backup object inventory entry is invalid.")
        key = item["key"]
        if STORAGE_KEY_PATTERN.fullmatch(key) is None or key in inventory:
            raise OperationsError("Backup object key is invalid or duplicated.")
        inventory[key] = item
    return inventory


def _load_object_inventory(root: Path) -> dict[str, dict[str, object]]:
    try:
        payload = json.loads((root / "objects.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise OperationsError("Backup object inventory is invalid.") from error
    return _parse_object_inventory(payload)


def _validate_restore_preconditions(
    connection: psycopg.Connection[dict[str, Any]],
    root: Path,
    manifest: dict[str, Any],
    settings: Settings,
) -> dict[str, dict[str, object]]:
    _required_flag("RESTORE_TEMPORARY")
    database_name = _database_name(connection)
    if RESTORE_DATABASE_PATTERN.fullmatch(database_name) is None:
        raise OperationsError("Restore refuses a non-temporary database name.")
    if _alembic_revision(connection) != manifest["alembic_revision"]:
        raise OperationsError("Restore target Alembic revision does not match backup.")
    current_schema = _schema_snapshot(connection)
    schema_hash = hashlib.sha256(
        json.dumps(current_schema, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    if schema_hash != manifest.get("schema_sha256"):
        raise OperationsError("Restore target schema does not match backup.")
    if settings.app_version != manifest.get("application_version"):
        raise OperationsError("Restore target application version does not match backup.")
    inventory = _load_object_inventory(root)
    signed_inventory = _parse_object_inventory(manifest.get("objects"))
    if inventory != signed_inventory:
        raise OperationsError("Signed and stored object inventories do not match.")
    return inventory


def _table_counts(connection: psycopg.Connection[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for table in TABLES:
        row = connection.execute(
            sql.SQL("SELECT count(*) AS count FROM {}").format(sql.Identifier(table))
        ).fetchone()
        counts[table] = int(row["count"] if row is not None else 0)
    return counts


def _table_rows_fingerprint(connection: psycopg.Connection[dict[str, Any]], table: str) -> str:
    rows = connection.execute(
        sql.SQL("SELECT to_jsonb(value) AS value FROM {} AS value ORDER BY id").format(
            sql.Identifier(table)
        )
    ).fetchall()
    payload = json.dumps(
        [row["value"] for row in rows],
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _is_migration_seed_only(
    connection: psycopg.Connection[dict[str, Any]], counts: dict[str, int]
) -> bool:
    seed_tables = frozenset(MIGRATION_SEED_FINGERPRINTS)
    if any(counts[table] != 0 for table in TABLES if table not in seed_tables):
        return False
    for table, (expected_count, expected_fingerprint) in MIGRATION_SEED_FINGERPRINTS.items():
        if counts[table] != expected_count:
            return False
        if _table_rows_fingerprint(connection, table) != expected_fingerprint:
            return False
    return True


def _restore_objects(
    client: Any,
    bucket: str,
    root: Path,
    inventory: dict[str, dict[str, object]],
) -> None:
    existing = _list_s3_objects(client, bucket)
    unexpected = set(existing) - set(inventory)
    if unexpected:
        raise OperationsError("Restore target bucket is not fresh.")
    for key, item in inventory.items():
        source = root / "objects" / key
        raw_byte_size = item["byte_size"]
        if isinstance(raw_byte_size, bool) or not isinstance(raw_byte_size, int):
            raise OperationsError("Backup object size is invalid.")
        byte_size = raw_byte_size
        checksum = str(item["sha256"])
        if key in existing:
            _stream_and_verify_object(client, bucket, item)
            continue
        checksum_b64 = base64.b64encode(bytes.fromhex(checksum)).decode("ascii")
        try:
            with source.open("rb") as stream:
                client.put_object(
                    Bucket=bucket,
                    Key=key,
                    Body=stream,
                    ContentLength=byte_size,
                    ContentType=str(item["content_type"]),
                    ChecksumSHA256=checksum_b64,
                    Metadata={"sha256": checksum},
                    IfNoneMatch="*",
                )
        except (BotoCoreError, ClientError, OSError) as error:
            raise OperationsError("A private object could not be restored safely.") from error
        _stream_and_verify_object(client, bucket, item)


def _restore_table(
    connection: psycopg.Connection[dict[str, Any]],
    table: str,
    source: Path,
    *,
    preserve_existing: bool = False,
) -> None:
    with source.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.reader(stream)
        try:
            columns = next(reader)
        except StopIteration as error:
            raise OperationsError(f"Backup table {table} has no CSV header.") from error
    if tuple(columns) != _table_columns(connection, table):
        raise OperationsError(f"Backup table {table} columns do not match the target.")
    if preserve_existing and table in MIGRATION_SEED_FINGERPRINTS:
        # A seed-only target has already been verified row-for-row by
        # _is_migration_seed_only. These migration-owned rows are immutable, so
        # retain them without requiring CREATE TEMP or another elevated grant.
        # The transaction's final backup comparison still fails closed if the
        # signed source differs from those deterministic rows.
        return
    statement = sql.SQL("COPY {} ({}) FROM STDIN WITH (FORMAT CSV, HEADER TRUE)").format(
        sql.Identifier(table),
        sql.SQL(", ").join(sql.Identifier(column) for column in columns),
    )
    with source.open("rb") as stream, connection.cursor().copy(statement) as copy:
        while chunk := stream.read(64 * 1024):
            copy.write(chunk)


def _mark_copy_csv_nulls(payload: str, sentinel: str) -> str:
    """Make unquoted empty COPY CSV fields visible to Python's CSV parser."""
    output: list[str] = []
    field_start = True
    in_quotes = False
    index = 0
    while index < len(payload):
        character = payload[index]
        if in_quotes:
            output.append(character)
            if character == '"':
                if index + 1 < len(payload) and payload[index + 1] == '"':
                    output.append('"')
                    index += 2
                    continue
                in_quotes = False
            index += 1
            continue
        if field_start and character in {",", "\r", "\n"}:
            output.append(sentinel)
        output.append(character)
        if character == '"' and field_start:
            in_quotes = True
            field_start = False
        elif character == ",":
            field_start = True
        elif character in {"\r", "\n"}:
            field_start = True
            if character == "\r" and index + 1 < len(payload) and payload[index + 1] == "\n":
                output.append("\n")
                index += 1
        else:
            field_start = False
        index += 1
    if field_start and payload.endswith(","):
        output.append(sentinel)
    return "".join(output)


def _read_restore_rows(
    connection: psycopg.Connection[dict[str, Any]], table: str, source: Path
) -> tuple[tuple[str, ...], list[dict[str, str | None]]]:
    try:
        with source.open("r", encoding="utf-8", newline="") as stream:
            payload = stream.read()
    except OSError as error:
        raise OperationsError(f"Backup table {table} could not be read.") from error
    sentinel = f"__creativedeploy_copy_null_{uuid.uuid4().hex}__"
    while sentinel in payload:
        sentinel = f"__creativedeploy_copy_null_{uuid.uuid4().hex}__"
    reader = csv.DictReader(io.StringIO(_mark_copy_csv_nulls(payload, sentinel), newline=""))
    columns = tuple(reader.fieldnames or ())
    if columns != _table_columns(connection, table):
        raise OperationsError(f"Backup table {table} columns do not match the target.")
    rows: list[dict[str, str | None]] = []
    for raw_row in reader:
        if None in raw_row or set(raw_row) != set(columns):
            raise OperationsError(f"Backup table {table} has an invalid CSV row.")
        rows.append(
            {column: None if raw_row[column] == sentinel else raw_row[column] for column in columns}
        )
    return columns, rows


def _insert_restore_row(
    connection: psycopg.Connection[dict[str, Any]],
    table: str,
    columns: tuple[str, ...],
    row: dict[str, str | None],
    *,
    overrides: dict[str, str] | None = None,
) -> None:
    values = [
        overrides[column] if overrides is not None and column in overrides else row[column]
        for column in columns
    ]
    connection.execute(
        sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
            sql.Identifier(table),
            sql.SQL(", ").join(sql.Identifier(column) for column in columns),
            sql.SQL(", ").join(sql.Placeholder() for _ in columns),
        ),
        values,
    )


def _set_paint_plan_lifecycle_constraints(
    connection: psycopg.Connection[dict[str, Any]], state: str
) -> None:
    if state not in {"IMMEDIATE", "DEFERRED"}:
        raise OperationsError("Paint Plan restore constraint state is invalid.")
    connection.execute(
        sql.SQL(
            "SET CONSTRAINTS paint_plans_verify_review_lifecycle, "
            "paint_plan_reviews_verify_lifecycle {}"
        ).format(sql.SQL(state))
    )


def _restore_paint_plan_history(connection: psycopg.Connection[dict[str, Any]], root: Path) -> None:
    plan_columns, plans = _read_restore_rows(
        connection,
        "paint_plans",
        root / "tables" / "paint_plans.csv",
    )
    review_columns, reviews = _read_restore_rows(
        connection,
        "paint_plan_review_events",
        root / "tables" / "paint_plan_review_events.csv",
    )
    reviews_by_plan: dict[str, list[dict[str, str | None]]] = {}
    for review in reviews:
        plan_id = review["paint_plan_id"]
        if plan_id is None:
            raise OperationsError("Backup Paint Plan review is missing its revision.")
        reviews_by_plan.setdefault(plan_id, []).append(review)
    restored_review_ids: set[str] = set()
    for plan in sorted(
        plans,
        key=lambda row: (
            str(row["paint_project_id"]),
            int(str(row["version"])),
            str(row["id"]),
        ),
    ):
        plan_id = plan["id"]
        revision_kind = plan["revision_kind"]
        final_lifecycle = plan["lifecycle"]
        if plan_id is None or revision_kind is None or final_lifecycle is None:
            raise OperationsError("Backup Paint Plan revision state is incomplete.")
        initial_lifecycle = "edited" if revision_kind == "edited" else "generated"
        _insert_restore_row(
            connection,
            "paint_plans",
            plan_columns,
            plan,
            overrides={"lifecycle": initial_lifecycle},
        )
        current_lifecycle = initial_lifecycle
        events = sorted(
            reviews_by_plan.get(plan_id, []),
            key=lambda row: (
                0 if row["action"] == "submit" else 1,
                str(row["created_at"]),
                str(row["id"]),
            ),
        )
        for event in events:
            action = event["action"]
            next_lifecycle = {
                "submit": "under_review",
                "approve": "approved",
                "reject": "rejected",
            }.get(action or "")
            event_id = event["id"]
            if next_lifecycle is None or event_id is None:
                raise OperationsError("Backup Paint Plan review action is invalid.")
            _insert_restore_row(
                connection,
                "paint_plan_review_events",
                review_columns,
                event,
            )
            restored_review_ids.add(event_id)
            connection.execute(
                "UPDATE paint_plans SET lifecycle = %s WHERE id = %s",
                (next_lifecycle, plan_id),
            )
            _set_paint_plan_lifecycle_constraints(connection, "IMMEDIATE")
            _set_paint_plan_lifecycle_constraints(connection, "DEFERRED")
            current_lifecycle = next_lifecycle
        if final_lifecycle == "superseded":
            connection.execute(
                "UPDATE paint_plans SET lifecycle = 'superseded' WHERE id = %s",
                (plan_id,),
            )
        elif current_lifecycle != final_lifecycle:
            raise OperationsError("Backup Paint Plan lifecycle and review history do not match.")
    expected_review_ids = {str(review["id"]) for review in reviews if review["id"] is not None}
    if restored_review_ids != expected_review_ids:
        raise OperationsError("Backup Paint Plan review history is incomplete.")


def _restore_pointers(connection: psycopg.Connection[dict[str, Any]], root: Path) -> None:
    try:
        payload = json.loads((root / "pointers.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise OperationsError("Backup pointer inventory is invalid.") from error
    if not isinstance(payload, dict) or set(payload) != set(DEFERRED_COLUMNS):
        raise OperationsError("Backup pointer inventory is incomplete.")
    for table, pointer_columns in DEFERRED_COLUMNS.items():
        rows = payload[table]
        primary_keys = _primary_key_columns(connection, table)
        if not isinstance(rows, list):
            raise OperationsError("Backup pointer rows are invalid.")
        for row in rows:
            if not isinstance(row, dict) or set(row) != set((*primary_keys, *pointer_columns)):
                raise OperationsError("Backup pointer row is invalid.")
            statement = sql.SQL("UPDATE {} SET {} WHERE {}").format(
                sql.Identifier(table),
                sql.SQL(", ").join(
                    sql.SQL("{} = %s").format(sql.Identifier(column)) for column in pointer_columns
                ),
                sql.SQL(" AND ").join(
                    sql.SQL("{} = %s").format(sql.Identifier(column)) for column in primary_keys
                ),
            )
            values = [row[column] for column in pointer_columns]
            values.extend(row[column] for column in primary_keys)
            result = connection.execute(statement, values)
            if result.rowcount != 1:
                raise OperationsError("A deferred database reference could not be restored.")


def _database_matches_backup(connection: psycopg.Connection[dict[str, Any]], root: Path) -> bool:
    with tempfile.TemporaryDirectory(prefix="creativedeploy-restore-verify-") as temporary:
        temporary_root = Path(temporary)
        for table in TABLES:
            _export_table(connection, table, temporary_root / "tables" / f"{table}.csv")
        _write_json(temporary_root / "pointers.json", _pointer_snapshot(connection))
        for relative in [*(f"tables/{table}.csv" for table in TABLES), "pointers.json"]:
            if _sha256(temporary_root / relative) != _sha256(root / relative):
                return False
    return True


def _verify_restored_objects(
    connection: psycopg.Connection[dict[str, Any]],
    client: Any,
    bucket: str,
    inventory: dict[str, dict[str, object]],
) -> None:
    database_inventory = _database_object_inventory(connection)
    if database_inventory != inventory:
        raise OperationsError("Restored database references do not match object inventory.")
    listed = _list_s3_objects(client, bucket)
    if set(listed) != set(inventory):
        raise OperationsError("Restored private object inventory is not one-to-one.")
    for key, item in inventory.items():
        if listed[key] != item["byte_size"]:
            raise OperationsError("Restored private object verification failed.")
        _stream_and_verify_object(client, bucket, item)


def restore(backup_id: str, *, dry_run: bool) -> None:
    _required_flag("OPERATIONS_QUIESCED")
    root = _backup_path(backup_id)
    if not root.is_dir() or root.is_symlink():
        raise OperationsError("Backup directory is unavailable.")
    manifest = _read_manifest(root)
    if manifest.get("backup_id") != backup_id:
        raise OperationsError("Backup manifest identifier does not match the selected backup.")
    settings = Settings.model_validate({})
    client, bucket = _s3_client(settings)
    with _database_connection(settings) as connection:
        inventory = _validate_restore_preconditions(connection, root, manifest, settings)
        counts = _table_counts(connection)
        expected_counts = _manifest_table_counts(manifest)
        all_empty = all(count == 0 for count in counts.values())
        seed_only = not all_empty and _is_migration_seed_only(connection, counts)
        already_complete = counts == expected_counts
        exact_retry = (
            not all_empty
            and not seed_only
            and already_complete
            and _database_matches_backup(connection, root)
        )
        if not all_empty and not seed_only and not exact_retry:
            raise OperationsError("Restore target database is neither fresh nor an exact retry.")
        existing = _list_s3_objects(client, bucket)
        if set(existing) - set(inventory):
            raise OperationsError("Restore target bucket is not fresh.")
        if dry_run:
            for key in existing:
                _stream_and_verify_object(client, bucket, inventory[key])
            print(
                "RESTORE_DRY_RUN_OK"
                f" database={_database_name(connection)} alembic={manifest['alembic_revision']}"
                f" objects={len(inventory)} secret_values_logged=0"
            )
            return
        connection.commit()
        _restore_objects(client, bucket, root, inventory)
        if all_empty or seed_only:
            with connection.transaction():
                for table in TABLES:
                    if table == PHASE3B_TABLES[0]:
                        # Paint Plan provenance is enforced before insert and
                        # requires the invocation's deferred final-attempt
                        # pointer. Every pointer target is present once the
                        # legacy and Phase 3A tables have been restored.
                        _restore_pointers(connection, root)
                    if table == "paint_plans":
                        _restore_paint_plan_history(connection, root)
                    elif table != "paint_plan_review_events":
                        _restore_table(
                            connection,
                            table,
                            root / "tables" / f"{table}.csv",
                            preserve_existing=seed_only,
                        )
                if not _database_matches_backup(connection, root):
                    raise OperationsError("Restored PostgreSQL data does not match the backup.")
                _verify_restored_objects(connection, client, bucket, inventory)
        else:
            if not _database_matches_backup(connection, root):
                raise OperationsError("Restored PostgreSQL data does not match the backup.")
            _verify_restored_objects(connection, client, bucket, inventory)
    print(
        f"RESTORE_COMPLETE backup_id={backup_id} tables={len(TABLES)}"
        f" objects={len(inventory)} secret_values_logged=0"
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("backup", "restore"):
        command = subparsers.add_parser(name)
        command.add_argument("--backup-id", required=True)
        command.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        if arguments.command == "backup":
            backup(arguments.backup_id, dry_run=arguments.dry_run)
        else:
            restore(arguments.backup_id, dry_run=arguments.dry_run)
    except OperationsError as error:
        print(f"OPERATIONS_FAILED reason={error} secret_values_logged=0")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
