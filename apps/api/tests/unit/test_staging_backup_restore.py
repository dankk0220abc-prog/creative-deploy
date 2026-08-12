from __future__ import annotations

import hashlib
import json
import os
import stat
from pathlib import Path
from typing import Any

import pytest

from creativedeploy_api.tools import staging_backup_restore as operations

SIGNING_KEY = "-".join(("synthetic", "signing", "key", "material", "for", "tests", "only"))
SIGNING_KEY_ID = "synthetic-key-v1"
OBJECT_KEY = "objects/aa/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.jpg"
OBJECT_BYTES = b"correct-object-bytes"


class RevisionResult:
    def __init__(self, revision: str) -> None:
        self.revision = revision

    def fetchone(self) -> dict[str, str]:
        return {"version_num": self.revision}


class RevisionConnection:
    def __init__(self, revision: str) -> None:
        self.revision = revision

    def execute(self, _statement: str) -> RevisionResult:
        return RevisionResult(self.revision)


def test_current_arcana_revision_is_accepted() -> None:
    connection = RevisionConnection("4c01a2b3c4d5")

    assert operations._alembic_revision(connection) == operations.EXPECTED_ALEMBIC_REVISION  # type: ignore[arg-type]


def test_unsupported_revision_fails_closed() -> None:
    connection = RevisionConnection("unsupported_revision")

    with pytest.raises(operations.OperationsError, match="revision is not supported"):
        operations._alembic_revision(connection)  # type: ignore[arg-type]


def test_phase3b_tables_extend_the_authoritative_full_recovery_inventory() -> None:
    assert len(operations.LEGACY_TABLES) == 14
    assert len(operations.PHASE3A_TABLES) == 25
    assert operations.PHASE3B_TABLES == (
        "provider_pricing_snapshots",
        "prompt_template_definitions",
        "paint_plans",
        "paint_plan_region_instructions",
        "paint_plan_review_events",
    )
    assert len(operations.TABLES) == 44
    assert (
        *operations.LEGACY_TABLES,
        *operations.PHASE3A_TABLES,
        *operations.PHASE3B_TABLES,
    ) == operations.TABLES
    assert set(operations.MIGRATION_SEED_FINGERPRINTS) <= set(operations.TABLES)


def test_exact_phase3b_migration_seed_state_is_a_supported_fresh_restore_target(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    counts = {table: 0 for table in operations.TABLES}
    for table, (count, _fingerprint) in operations.MIGRATION_SEED_FINGERPRINTS.items():
        counts[table] = count
    monkeypatch.setattr(
        operations,
        "_table_rows_fingerprint",
        lambda _connection, table: operations.MIGRATION_SEED_FINGERPRINTS[table][1],
    )

    assert operations._is_migration_seed_only(object(), counts) is True  # type: ignore[arg-type]


def test_legacy_39_table_seed_state_is_not_a_valid_phase3b_restore_target(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    counts = {table: 0 for table in operations.TABLES}
    legacy_counts = {
        "provider_definitions": 1,
        "capability_definitions": 3,
        "model_definitions": 2,
        "provider_capabilities": 3,
        "model_capabilities": 5,
    }
    counts.update(legacy_counts)
    monkeypatch.setattr(operations, "_table_rows_fingerprint", lambda *_: "unused")

    assert operations._is_migration_seed_only(object(), counts) is False  # type: ignore[arg-type]


def test_backup_root_requires_exact_attempt_owner_and_mode(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    os.chown(tmp_path, os.geteuid(), os.getegid())
    tmp_path.chmod(0o700)
    monkeypatch.setenv("BACKUP_ROOT", str(tmp_path))
    assert operations._backup_root() == tmp_path.resolve()

    tmp_path.chmod(0o750)
    with pytest.raises(operations.OperationsError, match="ownership or permissions"):
        operations._backup_root()

    tmp_path.chmod(0o700)
    monkeypatch.setattr(operations.os, "geteuid", lambda: os.getuid() + 1)
    with pytest.raises(operations.OperationsError, match="ownership or permissions"):
        operations._backup_root()


def test_backup_root_refuses_a_symlink(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    target = tmp_path / "target"
    target.mkdir(mode=0o700)
    link = tmp_path / "backup-link"
    link.symlink_to(target, target_is_directory=True)
    monkeypatch.setenv("BACKUP_ROOT", str(link))

    with pytest.raises(operations.OperationsError, match="private directory"):
        operations._backup_root()


def test_backup_enforces_private_file_creation_permissions(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    output = tmp_path / "manifest.json"

    def fake_backup(_backup_id: str, *, dry_run: bool) -> None:
        assert dry_run is False
        output.write_text("{}\n", encoding="utf-8")

    monkeypatch.setattr(operations, "_backup", fake_backup)
    original_umask = os.umask(0o022)
    try:
        operations.backup("backup", dry_run=False)
        observed_umask = os.umask(original_umask)
    finally:
        os.umask(original_umask)

    assert observed_umask == 0o022
    assert stat.S_IMODE(output.stat().st_mode) == 0o600


def configure_signing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    key: str = SIGNING_KEY,
    key_id: str = SIGNING_KEY_ID,
) -> Path:
    path = tmp_path / "backup_signing_key"
    path.write_text(f"{key}\n", encoding="utf-8")
    path.chmod(0o600)
    monkeypatch.setenv("BACKUP_SIGNING_KEY_FILE", str(path))
    monkeypatch.setenv("BACKUP_SIGNING_KEY_ID", key_id)
    return path


def write_signed_manifest(
    root: Path,
    signing: operations.BackupSigningConfig,
    *,
    backup_id: str = "backup",
) -> dict[str, Any]:
    root.mkdir()
    facts = root / "facts.json"
    facts.write_text("{}\n", encoding="utf-8")
    object_checksum = hashlib.sha256(OBJECT_BYTES).hexdigest()
    manifest: dict[str, Any] = {
        "format": operations.BACKUP_FORMAT,
        "manifest_version": operations.MANIFEST_VERSION,
        "created_at": "2026-08-01T00:00:00+00:00",
        "backup_id": backup_id,
        "run_id": "synthetic_test",
        "source_commit": "511e42ecb2adccc55e75cb4d801181206b1b337a",
        "application_version": "0.1.0",
        "alembic_revision": operations.EXPECTED_ALEMBIC_REVISION,
        "database_name": "p2b2s_synthetic_test",
        "schema_sha256": "a" * 64,
        "table_counts": {table: 0 for table in operations.TABLES},
        "object_count": 1,
        "objects": [
            {
                "key": OBJECT_KEY,
                "byte_size": len(OBJECT_BYTES),
                "sha256": object_checksum,
                "content_type": "image/jpeg",
            }
        ],
        "files": [
            {
                "path": "facts.json",
                "byte_size": facts.stat().st_size,
                "sha256": hashlib.sha256(facts.read_bytes()).hexdigest(),
            }
        ],
        "authenticity": {
            "algorithm": operations.MANIFEST_SIGNATURE_ALGORITHM,
            "canonicalization": operations.MANIFEST_CANONICALIZATION,
            "key_id": signing.key_id,
            "signature_file": operations.MANIFEST_SIGNATURE_PATH,
        },
    }
    (root / operations.MANIFEST_PATH).write_text(
        json.dumps(manifest, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    operations._write_detached_manifest_signature(root, manifest, signing)
    return manifest


def test_manifest_signature_accepts_valid_canonical_content(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    configure_signing(monkeypatch, tmp_path)
    signing = operations._backup_signing_config()
    root = tmp_path / "backup"
    manifest = write_signed_manifest(root, signing)

    assert operations._read_manifest(root) == manifest


def test_manifest_revision_matches_backup_and_restore_contract(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    configure_signing(monkeypatch, tmp_path)
    signing = operations._backup_signing_config()
    root = tmp_path / "backup"
    manifest = write_signed_manifest(root, signing)

    assert manifest["alembic_revision"] == operations.EXPECTED_ALEMBIC_REVISION
    assert (
        operations._read_manifest(root)["alembic_revision"] == operations.EXPECTED_ALEMBIC_REVISION
    )

    manifest["alembic_revision"] = "unsupported_revision"
    (root / operations.MANIFEST_PATH).write_text(
        json.dumps(manifest, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    operations._write_detached_manifest_signature(root, manifest, signing)
    with pytest.raises(operations.OperationsError, match="revision is not supported"):
        operations._read_manifest(root)


def test_manifest_rejects_legacy_39_table_inventory(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    configure_signing(monkeypatch, tmp_path)
    signing = operations._backup_signing_config()
    root = tmp_path / "backup"
    manifest = write_signed_manifest(root, signing)
    for table in operations.PHASE3B_TABLES:
        manifest["table_counts"].pop(table)
    (root / operations.MANIFEST_PATH).write_text(
        json.dumps(manifest, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    operations._write_detached_manifest_signature(root, manifest, signing)

    with pytest.raises(operations.OperationsError, match="table counts are invalid"):
        operations._read_manifest(root)


def test_manifest_canonicalization_ignores_json_order_and_whitespace(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    configure_signing(monkeypatch, tmp_path)
    signing = operations._backup_signing_config()
    root = tmp_path / "backup"
    manifest = write_signed_manifest(root, signing)
    reordered = dict(reversed(tuple(manifest.items())))
    (root / operations.MANIFEST_PATH).write_text(
        json.dumps(reordered, ensure_ascii=True, indent=4) + "\n",
        encoding="utf-8",
    )

    assert operations._read_manifest(root) == reordered


@pytest.mark.parametrize(
    ("target", "replacement"),
    [
        ("source_commit", "tampered"),
        ("files_sha256", "b" * 64),
        ("objects_sha256", "c" * 64),
        ("alembic_revision", "tamperedrevision"),
    ],
)
def test_manifest_tampering_fails_authenticity_before_file_validation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    target: str,
    replacement: str,
) -> None:
    configure_signing(monkeypatch, tmp_path)
    signing = operations._backup_signing_config()
    root = tmp_path / "backup"
    manifest = write_signed_manifest(root, signing)
    if target == "files_sha256":
        manifest["files"][0]["sha256"] = replacement
    elif target == "objects_sha256":
        manifest["objects"][0]["sha256"] = replacement
    else:
        manifest[target] = replacement
    (root / operations.MANIFEST_PATH).write_text(
        json.dumps(manifest, sort_keys=True), encoding="utf-8"
    )

    with pytest.raises(operations.OperationsError, match="authenticity"):
        operations._read_manifest(root)


def test_missing_or_tampered_detached_signature_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    configure_signing(monkeypatch, tmp_path)
    signing = operations._backup_signing_config()
    root = tmp_path / "backup"
    manifest = write_signed_manifest(root, signing)
    signature_path = root / operations.MANIFEST_SIGNATURE_PATH
    signature_path.unlink()
    with pytest.raises(operations.OperationsError, match="signature"):
        operations._read_manifest(root)

    operations._write_detached_manifest_signature(root, manifest, signing)
    signature = json.loads(signature_path.read_text(encoding="utf-8"))
    signature["manifest_hmac_sha256"] = "0" * 64
    signature_path.write_text(json.dumps(signature), encoding="utf-8")
    with pytest.raises(operations.OperationsError, match="authenticity"):
        operations._read_manifest(root)


def test_wrong_signing_key_or_key_id_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    key_path = configure_signing(monkeypatch, tmp_path)
    signing = operations._backup_signing_config()
    root = tmp_path / "backup"
    write_signed_manifest(root, signing)

    key_path.write_text(f"{'x' * 48}\n", encoding="utf-8")
    with pytest.raises(operations.OperationsError, match="authenticity"):
        operations._read_manifest(root)

    key_path.write_text(f"{SIGNING_KEY}\n", encoding="utf-8")
    monkeypatch.setenv("BACKUP_SIGNING_KEY_ID", "different-key-v2")
    with pytest.raises(operations.OperationsError, match="signing identity"):
        operations._read_manifest(root)


def test_signing_key_secret_negative_matrix(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("BACKUP_SIGNING_KEY_FILE", raising=False)
    monkeypatch.delenv("BACKUP_SIGNING_KEY_ID", raising=False)
    with pytest.raises(operations.OperationsError, match="KEY_ID"):
        operations._backup_signing_config()

    monkeypatch.setenv("BACKUP_SIGNING_KEY_ID", SIGNING_KEY_ID)
    with pytest.raises(operations.OperationsError, match="KEY_FILE"):
        operations._backup_signing_config()

    path = configure_signing(monkeypatch, tmp_path, key="short")
    with pytest.raises(operations.OperationsError, match="too short"):
        operations._backup_signing_config()

    path.write_text("\n", encoding="utf-8")
    with pytest.raises(operations.OperationsError, match="unavailable or invalid"):
        operations._backup_signing_config()

    path.write_text("first\nsecond\n", encoding="utf-8")
    with pytest.raises(operations.OperationsError, match="unavailable or invalid"):
        operations._backup_signing_config()

    path.write_text(f"{SIGNING_KEY}\n", encoding="utf-8")
    path.chmod(0o622)
    with pytest.raises(operations.OperationsError, match="unavailable or invalid"):
        operations._backup_signing_config()

    path.chmod(0o600)
    symlink = tmp_path / "signing-link"
    symlink.symlink_to(path)
    monkeypatch.setenv("BACKUP_SIGNING_KEY_FILE", str(symlink))
    with pytest.raises(operations.OperationsError, match="unavailable or invalid"):
        operations._backup_signing_config()


def test_signature_failure_precedes_database_and_object_storage(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    configure_signing(monkeypatch, tmp_path)
    signing = operations._backup_signing_config()
    root = tmp_path / "backup"
    manifest = write_signed_manifest(root, signing)
    manifest["created_at"] = "tampered"
    (root / operations.MANIFEST_PATH).write_text(
        json.dumps(manifest, sort_keys=True), encoding="utf-8"
    )
    monkeypatch.setenv("OPERATIONS_QUIESCED", "true")
    monkeypatch.setenv("RESTORE_TEMPORARY", "true")
    monkeypatch.setenv("BACKUP_ROOT", str(tmp_path))
    external_calls: list[str] = []
    monkeypatch.setattr(
        operations,
        "_database_connection",
        lambda _: external_calls.append("database"),
    )
    monkeypatch.setattr(
        operations,
        "_s3_client",
        lambda _: external_calls.append("storage"),
    )

    with pytest.raises(operations.OperationsError, match="authenticity"):
        operations.restore("backup", dry_run=False)

    assert external_calls == []


def test_signature_failure_output_does_not_disclose_secret_or_signature(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_signing(monkeypatch, tmp_path)
    signing = operations._backup_signing_config()
    root = tmp_path / "backup"
    write_signed_manifest(root, signing)
    signature_path = root / operations.MANIFEST_SIGNATURE_PATH
    signature = json.loads(signature_path.read_text(encoding="utf-8"))
    raw_signature = signature["manifest_hmac_sha256"]
    signature["manifest_hmac_sha256"] = "0" * 64
    signature_path.write_text(json.dumps(signature), encoding="utf-8")
    monkeypatch.setenv("OPERATIONS_QUIESCED", "true")
    monkeypatch.setenv("RESTORE_TEMPORARY", "true")
    monkeypatch.setenv("BACKUP_ROOT", str(tmp_path))

    assert operations.main(["restore", "--backup-id", "backup", "--dry-run"]) == 2
    output = capsys.readouterr().out
    assert SIGNING_KEY not in output
    assert raw_signature not in output
    assert "authenticity verification failed" in output


class FakeBody:
    def __init__(self, payload: bytes, *, fail_on_read: int | None = None) -> None:
        self.payload = payload
        self.fail_on_read = fail_on_read
        self.offset = 0
        self.read_calls = 0
        self.closed = False

    def read(self, _: int) -> bytes:
        self.read_calls += 1
        if self.fail_on_read == self.read_calls:
            raise OSError("synthetic interrupted stream")
        if self.offset >= len(self.payload):
            return b""
        end = min(self.offset + 3, len(self.payload))
        chunk = self.payload[self.offset : end]
        self.offset = end
        return chunk

    def close(self) -> None:
        self.closed = True


class FakeS3Client:
    def __init__(self) -> None:
        self.objects: dict[str, dict[str, Any]] = {}
        self.get_calls: list[str] = []
        self.put_calls: list[str] = []
        self.bodies: list[FakeBody] = []
        self.fail_get = False
        self.fail_stream_on_read: int | None = None
        self.reported_size: int | None = None
        self.reported_content_type: str | None = None

    def list_objects_v2(self, **_: object) -> dict[str, object]:
        return {
            "Contents": [
                {"Key": key, "Size": len(item["bytes"])}
                for key, item in sorted(self.objects.items())
            ],
            "IsTruncated": False,
        }

    def get_object(self, *, Bucket: str, Key: str) -> dict[str, object]:
        del Bucket
        self.get_calls.append(Key)
        if self.fail_get:
            raise OSError("synthetic GET failure")
        item = self.objects[Key]
        body = FakeBody(item["bytes"], fail_on_read=self.fail_stream_on_read)
        self.bodies.append(body)
        return {
            "Body": body,
            "ContentLength": (
                len(item["bytes"]) if self.reported_size is None else self.reported_size
            ),
            "ContentType": self.reported_content_type or item["content_type"],
            "Metadata": dict(item["metadata"]),
        }

    def put_object(self, **arguments: object) -> None:
        key = str(arguments["Key"])
        self.put_calls.append(key)
        body = arguments["Body"]
        assert hasattr(body, "read")
        payload = body.read()
        assert isinstance(payload, bytes)
        self.objects[key] = {
            "bytes": payload,
            "content_type": arguments["ContentType"],
            "metadata": dict(arguments["Metadata"]),
        }


def object_inventory(payload: bytes = OBJECT_BYTES) -> dict[str, dict[str, object]]:
    return {
        OBJECT_KEY: {
            "key": OBJECT_KEY,
            "byte_size": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
            "content_type": "image/jpeg",
        }
    }


def write_backup_object(root: Path, payload: bytes = OBJECT_BYTES) -> Path:
    path = root / "objects" / OBJECT_KEY
    path.parent.mkdir(parents=True)
    path.write_bytes(payload)
    return path


def seed_existing_object(
    client: FakeS3Client,
    payload: bytes = OBJECT_BYTES,
    *,
    metadata_checksum: str | None = None,
) -> None:
    client.objects[OBJECT_KEY] = {
        "bytes": payload,
        "content_type": "image/jpeg",
        "metadata": {
            "sha256": metadata_checksum or hashlib.sha256(OBJECT_BYTES).hexdigest(),
        },
    }


def test_new_restore_object_is_put_then_get_and_byte_hashed(tmp_path: Path) -> None:
    client = FakeS3Client()
    inventory = object_inventory()
    write_backup_object(tmp_path)

    operations._restore_objects(client, "bucket", tmp_path, inventory)

    assert client.put_calls == [OBJECT_KEY]
    assert client.get_calls == [OBJECT_KEY]
    assert client.bodies[0].read_calls > 2
    assert client.bodies[0].closed is True


def test_exact_retry_reads_and_hashes_matching_existing_bytes(tmp_path: Path) -> None:
    client = FakeS3Client()
    seed_existing_object(client)

    operations._restore_objects(client, "bucket", tmp_path, object_inventory())

    assert client.put_calls == []
    assert client.get_calls == [OBJECT_KEY]
    assert client.bodies[0].read_calls > 2


def test_same_size_and_forged_metadata_cannot_hide_different_bytes(tmp_path: Path) -> None:
    client = FakeS3Client()
    changed = b"x" * len(OBJECT_BYTES)
    seed_existing_object(
        client,
        changed,
        metadata_checksum=hashlib.sha256(OBJECT_BYTES).hexdigest(),
    )

    with pytest.raises(operations.OperationsError, match="byte checksum"):
        operations._restore_objects(client, "bucket", tmp_path, object_inventory())

    assert client.put_calls == []
    assert client.objects[OBJECT_KEY]["bytes"] == changed
    assert client.bodies[0].read_calls > 2


@pytest.mark.parametrize(
    ("failure", "message"),
    [
        ("get", "could not be read"),
        ("stream", "could not be read"),
        ("content_type", "response fact"),
        ("size", "response fact"),
    ],
)
def test_object_get_stream_and_response_fact_failures_are_safe(
    tmp_path: Path,
    failure: str,
    message: str,
) -> None:
    client = FakeS3Client()
    seed_existing_object(client)
    if failure == "get":
        client.fail_get = True
    elif failure == "stream":
        client.fail_stream_on_read = 2
    elif failure == "content_type":
        client.reported_content_type = "application/octet-stream"
    else:
        client.reported_size = len(OBJECT_BYTES) + 1

    with pytest.raises(operations.OperationsError, match=message):
        operations._restore_objects(client, "bucket", tmp_path, object_inventory())

    assert client.put_calls == []
    assert client.objects[OBJECT_KEY]["bytes"] == OBJECT_BYTES


def test_new_object_can_resume_safely_after_later_database_failure(tmp_path: Path) -> None:
    client = FakeS3Client()
    inventory = object_inventory()
    source = write_backup_object(tmp_path)
    operations._restore_objects(client, "bucket", tmp_path, inventory)

    operations._restore_objects(client, "bucket", tmp_path, inventory)

    assert client.put_calls == [OBJECT_KEY]
    assert client.get_calls == [OBJECT_KEY, OBJECT_KEY]
    assert source.read_bytes() == OBJECT_BYTES


def test_final_verification_re_reads_and_rejects_modified_object(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = FakeS3Client()
    changed = b"x" * len(OBJECT_BYTES)
    seed_existing_object(
        client,
        changed,
        metadata_checksum=hashlib.sha256(OBJECT_BYTES).hexdigest(),
    )
    inventory = object_inventory()
    monkeypatch.setattr(operations, "_database_object_inventory", lambda _: inventory)

    with pytest.raises(operations.OperationsError, match="byte checksum"):
        operations._verify_restored_objects(object(), client, "bucket", inventory)

    assert client.get_calls == [OBJECT_KEY]


class DryRunConnection:
    def __enter__(self) -> DryRunConnection:
        return self

    def __exit__(self, *_: object) -> None:
        return None


class DryRunSettings:
    @classmethod
    def model_validate(cls, _: object) -> object:
        return object()


class RestoreTransaction:
    def __init__(self) -> None:
        self.committed = False
        self.rolled_back = False

    def __enter__(self) -> RestoreTransaction:
        return self

    def __exit__(self, exception_type: object, *_: object) -> None:
        self.committed = exception_type is None
        self.rolled_back = exception_type is not None


class RestoreConnection(DryRunConnection):
    def __init__(self) -> None:
        self.transaction_state = RestoreTransaction()

    def commit(self) -> None:
        return None

    def transaction(self) -> RestoreTransaction:
        return self.transaction_state


def test_final_object_failure_rolls_back_database_restore_transaction(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    configure_signing(monkeypatch, tmp_path)
    signing = operations._backup_signing_config()
    root = tmp_path / "backup"
    manifest = write_signed_manifest(root, signing)
    connection = RestoreConnection()
    database_writes: list[str] = []
    monkeypatch.setenv("OPERATIONS_QUIESCED", "true")
    monkeypatch.setenv("RESTORE_TEMPORARY", "true")
    monkeypatch.setenv("BACKUP_ROOT", str(tmp_path))
    monkeypatch.setattr(operations, "Settings", DryRunSettings)
    monkeypatch.setattr(operations, "_s3_client", lambda _: (FakeS3Client(), "bucket"))
    monkeypatch.setattr(operations, "_database_connection", lambda _: connection)
    monkeypatch.setattr(
        operations,
        "_validate_restore_preconditions",
        lambda *_: object_inventory(),
    )
    monkeypatch.setattr(
        operations,
        "_table_counts",
        lambda _: {table: 0 for table in operations.TABLES},
    )
    monkeypatch.setattr(operations, "_list_s3_objects", lambda *_: {})
    monkeypatch.setattr(operations, "_restore_objects", lambda *_: None)
    monkeypatch.setattr(
        operations,
        "_restore_table",
        lambda *_, **__: database_writes.append("table"),
    )
    monkeypatch.setattr(
        operations,
        "_restore_paint_plan_history",
        lambda *_: database_writes.append("paint-plan-history"),
    )
    monkeypatch.setattr(
        operations,
        "_restore_pointers",
        lambda *_: database_writes.append("pointers"),
    )
    monkeypatch.setattr(operations, "_database_matches_backup", lambda *_: True)
    monkeypatch.setattr(
        operations,
        "_verify_restored_objects",
        lambda *_: (_ for _ in ()).throw(operations.OperationsError("final GET failed")),
    )

    with pytest.raises(operations.OperationsError, match="final GET failed"):
        operations.restore(str(manifest["backup_id"]), dry_run=False)

    assert database_writes
    assert connection.transaction_state.rolled_back
    assert not connection.transaction_state.committed


def test_restore_dry_run_has_zero_database_or_object_writes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    configure_signing(monkeypatch, tmp_path)
    signing = operations._backup_signing_config()
    root = tmp_path / "backup"
    manifest = write_signed_manifest(root, signing)
    client = FakeS3Client()
    monkeypatch.setenv("OPERATIONS_QUIESCED", "true")
    monkeypatch.setenv("RESTORE_TEMPORARY", "true")
    monkeypatch.setenv("BACKUP_ROOT", str(tmp_path))
    monkeypatch.setattr(operations, "Settings", DryRunSettings)
    monkeypatch.setattr(operations, "_s3_client", lambda _: (client, "bucket"))
    monkeypatch.setattr(operations, "_database_connection", lambda _: DryRunConnection())
    monkeypatch.setattr(
        operations,
        "_validate_restore_preconditions",
        lambda *_: object_inventory(),
    )
    monkeypatch.setattr(
        operations,
        "_table_counts",
        lambda _: {table: 0 for table in operations.TABLES},
    )
    monkeypatch.setattr(operations, "_database_name", lambda _: "p2b2r_dry_run")

    operations.restore(str(manifest["backup_id"]), dry_run=True)

    assert client.put_calls == []
    assert client.get_calls == []
