"""Ordering, failure, and resume tests for the non-destructive legacy copy tool."""

import asyncio
import hashlib
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from creativedeploy_api.storage.images import (
    ImageStorageError,
    LocalFilesystemImageStorageAdapter,
    StoragePublishReceipt,
)
from creativedeploy_api.tools import migrate_image_storage


class _ScalarResult:
    def __init__(self, values: list[object]) -> None:
        self._values = values

    def scalars(self) -> "_ScalarResult":
        return self

    def all(self) -> list[object]:
        return self._values


class _UpdateResult:
    def __init__(self, value: object | None) -> None:
        self._value = value

    def scalar_one_or_none(self) -> object | None:
        return self._value


class _Transaction:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, *_args: object) -> None:
        return None


class _DatabaseFacts:
    def __init__(self, asset: object, events: list[str]) -> None:
        self.asset = asset
        self.events = events
        self.storage_provider = "local_filesystem"
        self.update_calls = 0
        self.fail_next_update = False


class _Session:
    def __init__(self, *, mode: str, database: _DatabaseFacts) -> None:
        self._mode = mode
        self._database = database

    async def __aenter__(self) -> "_Session":
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None

    def begin(self) -> _Transaction:
        return _Transaction()

    async def execute(self, _statement: object) -> _ScalarResult | _UpdateResult:
        if self._mode == "select":
            values = (
                [self._database.asset]
                if self._database.storage_provider == "local_filesystem"
                else []
            )
            return _ScalarResult(values)
        self._database.events.append("database_update")
        self._database.update_calls += 1
        if self._database.fail_next_update:
            self._database.fail_next_update = False
            raise RuntimeError("synthetic database update failure")
        self._database.storage_provider = "s3"
        return _UpdateResult(self._database.asset.id)  # type: ignore[attr-defined]


class _SessionFactory:
    def __init__(self, database: _DatabaseFacts) -> None:
        self._database = database
        self._calls = 0

    def __call__(self) -> _Session:
        self._calls += 1
        return _Session(
            mode="select" if self._calls == 1 else "update",
            database=self._database,
        )


class _Engine:
    def __init__(self) -> None:
        self.disposed = False

    async def dispose(self) -> None:
        self.disposed = True


class _ByteVerifiedDestination:
    def __init__(self, events: list[str]) -> None:
        self.events = events
        self.object_exists = False
        self.copy_calls = 0
        self.put_calls = 0
        self.fail_copy = False

    def copy_verified_object(
        self,
        *,
        key: str,
        source: object,
        byte_size: int,
        sha256: str,
        content_type: str,
    ) -> StoragePublishReceipt:
        del source, content_type
        self.copy_calls += 1
        if self.fail_copy:
            raise ImageStorageError("synthetic post-write verification failure")
        created = not self.object_exists
        if created:
            self.put_calls += 1
            self.object_exists = True
            self.events.extend(("destination_put", "destination_post_write_get_hash"))
        else:
            self.events.append("destination_existing_get_hash")
        return StoragePublishReceipt(
            key=key,
            byte_size=byte_size,
            expected_sha256=sha256,
            provider_name="s3",
            created_by_this_call=created,
        )


def _install_fakes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> tuple[Path, _DatabaseFacts, _ByteVerifiedDestination, list[str]]:
    payload = b"synthetic legacy migration bytes"
    digest = hashlib.sha256(payload).hexdigest()
    key = "objects/aa/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.jpg"
    source = LocalFilesystemImageStorageAdapter(tmp_path / "legacy-private")
    source_path = source.root / key
    source_path.parent.mkdir(mode=0o700)
    source_path.write_bytes(payload)
    asset = SimpleNamespace(
        id=uuid4(),
        storage_key=key,
        sha256=digest,
        byte_size=len(payload),
        declared_content_type="image/jpeg",
    )
    events: list[str] = []
    database = _DatabaseFacts(asset, events)
    destination = _ByteVerifiedDestination(events)
    engine = _Engine()
    settings = SimpleNamespace(
        image_storage_root=source.root,
        s3_force_path_style=True,
        s3_create_bucket=False,
        require_s3_image_storage=lambda: (
            "http://s3.example.test",
            "us-east-1",
            "private-paintpilot",
            "synthetic-access",
            "synthetic-secret",
            tmp_path / "staging",
        ),
    )

    class _SettingsFactory:
        @classmethod
        def model_validate(cls, _values: dict[str, object]) -> object:
            return settings

    monkeypatch.setattr(migrate_image_storage, "Settings", _SettingsFactory)
    monkeypatch.setattr(
        migrate_image_storage,
        "LocalFilesystemImageStorageAdapter",
        lambda _root: source,
    )
    monkeypatch.setattr(
        migrate_image_storage,
        "S3ImageStorageAdapter",
        lambda **_kwargs: destination,
    )
    monkeypatch.setattr(migrate_image_storage, "create_database_engine", lambda _settings: engine)
    monkeypatch.setattr(
        migrate_image_storage,
        "create_database_session_factory",
        lambda _engine: _SessionFactory(database),
    )
    return source_path, database, destination, events


def test_dry_run_reads_and_verifies_source_without_object_or_database_write(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source_path, database, destination, events = _install_fakes(monkeypatch, tmp_path)

    assert asyncio.run(migrate_image_storage.migrate(execute=False, limit=None)) == 0

    assert source_path.is_file()
    assert destination.copy_calls == 0
    assert database.update_calls == 0
    assert database.storage_provider == "local_filesystem"
    assert events == []
    assert "verified=1 updated=0 source_deleted=0" in capsys.readouterr().out


def test_real_destination_byte_verification_failure_leaves_database_and_source_unchanged(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source_path, database, destination, events = _install_fakes(monkeypatch, tmp_path)
    destination.fail_copy = True

    with pytest.raises(ImageStorageError, match="verification failure"):
        asyncio.run(migrate_image_storage.migrate(execute=True, limit=None))

    assert source_path.is_file()
    assert database.storage_provider == "local_filesystem"
    assert database.update_calls == 0
    assert events == []


def test_database_failure_keeps_verified_target_resumable_and_never_deletes_source(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source_path, database, destination, events = _install_fakes(monkeypatch, tmp_path)
    database.fail_next_update = True

    with pytest.raises(RuntimeError, match="database update failure"):
        asyncio.run(migrate_image_storage.migrate(execute=True, limit=None))

    assert events == [
        "destination_put",
        "destination_post_write_get_hash",
        "database_update",
    ]
    assert source_path.is_file()
    assert destination.object_exists is True
    assert database.storage_provider == "local_filesystem"

    events.clear()
    assert asyncio.run(migrate_image_storage.migrate(execute=True, limit=None)) == 0

    assert events == ["destination_existing_get_hash", "database_update"]
    assert destination.put_calls == 1
    assert database.storage_provider == "s3"
    assert source_path.is_file()
    assert "verified=1 updated=1 source_deleted=0" in capsys.readouterr().out
