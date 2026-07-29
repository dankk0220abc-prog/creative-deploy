"""Real PostgreSQL, filesystem, and API integration for Phase 1E-1 ImageAssets."""

import asyncio
import concurrent.futures
import io
import logging
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import delete, select, update

from creativedeploy_api.app_factory import create_app
from creativedeploy_api.core.config import Settings
from creativedeploy_api.db.engine import create_database_engine
from creativedeploy_api.db.models import (
    CommandIdempotencyRecord,
    ImageAsset,
    PaintProject,
    StateTransitionEvent,
)
from creativedeploy_api.repositories.image_assets import SqlAlchemyImageAssetRepository
from creativedeploy_api.storage.images import (
    ImageStorageError,
    LocalFilesystemImageStorageAdapter,
    StoragePublishReceipt,
)

pytestmark = pytest.mark.integration


def _jpeg_bytes(color: str = "#c77838") -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (768, 768), color).save(output, format="JPEG", quality=90)
    return output.getvalue()


def _settings(principal_id: str, storage_root: Path) -> Settings:
    development = Settings()
    return Settings(
        app_env="test",
        database_url=development.database_url.get_secret_value(),
        database_lock_timeout_ms=3_000,
        database_statement_timeout_ms=5_000,
        paintpilot_demo_principal_id=principal_id,
        paintpilot_demo_principal_display_name="Phase 1E-1 Integration Owner",
        image_storage_root=storage_root,
        _env_file=None,
    )


async def _cleanup(settings: Settings, principal_id: str) -> None:
    engine = create_database_engine(settings)
    project_ids = select(PaintProject.id).where(PaintProject.owner_principal_id == principal_id)
    try:
        async with engine.begin() as connection:
            await connection.execute(
                delete(CommandIdempotencyRecord).where(
                    CommandIdempotencyRecord.principal_id == principal_id
                )
            )
            await connection.execute(
                update(PaintProject)
                .where(PaintProject.owner_principal_id == principal_id)
                .values(current_image_asset_id=None)
            )
            await connection.execute(
                delete(ImageAsset).where(ImageAsset.owner_principal_id == principal_id)
            )
            await connection.execute(
                delete(StateTransitionEvent).where(StateTransitionEvent.project_id.in_(project_ids))
            )
            await connection.execute(
                delete(PaintProject).where(PaintProject.owner_principal_id == principal_id)
            )
    finally:
        await engine.dispose()


@pytest.fixture
def image_integration_settings(tmp_path: Path) -> Iterator[Settings]:
    principal_id = f"phase1e1-integration-{uuid.uuid4().hex}"
    settings = _settings(principal_id, tmp_path / "private-images")
    asyncio.run(_cleanup(settings, principal_id))
    yield settings
    asyncio.run(_cleanup(settings, principal_id))


def _create_project(client: TestClient) -> dict[str, object]:
    response = client.post(
        "/api/v1/paint-projects",
        headers={"Idempotency-Key": str(uuid.uuid4())},
        json={"title": "Synthetic image project", "description": "No private photos."},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _upload(
    client: TestClient,
    project_id: str,
    *,
    image_bytes: bytes,
    idempotency_key: uuid.UUID,
    color_label: str = "primary.jpg",
    intended_usage: tuple[str, ...] = ("private_project",),
) -> object:
    data = {
        "role": "primary_front",
        "source_type": "user_photographed",
        "intended_usage": list(intended_usage),
        "rights_attestation_confirmed": "true",
        "rights_attestation_version": "1",
    }
    return client.post(
        f"/api/v1/paint-projects/{project_id}/images",
        headers={"Idempotency-Key": str(idempotency_key)},
        data=data,
        files={"file": (color_label, image_bytes, "image/jpeg")},
    )


async def _mark_image_validation_failed(settings: Settings, project_id: uuid.UUID) -> None:
    engine = create_database_engine(settings)
    now = datetime.now(UTC)
    try:
        async with engine.begin() as connection:
            project_status = (
                await connection.execute(
                    select(PaintProject.status)
                    .where(PaintProject.id == project_id)
                    .with_for_update()
                )
            ).scalar_one()
            assert project_status == "IMAGE_UPLOADED"
            await connection.execute(
                update(PaintProject)
                .where(PaintProject.id == project_id)
                .values(status="IMAGE_VALIDATION_FAILED", updated_at=now)
            )
            await connection.execute(
                StateTransitionEvent.__table__.insert().values(
                    id=uuid.uuid4(),
                    project_id=project_id,
                    from_state="IMAGE_UPLOADED",
                    to_state="IMAGE_VALIDATION_FAILED",
                    event="image_validation_failure",
                    actor_type="system",
                    actor_principal_id="deterministic_test_validator",
                    actor_display_name_snapshot=None,
                    reason="image_validation_failed",
                    correlation_id=uuid.uuid4(),
                    event_metadata={"schema_version": "test_fixture.v1"},
                    created_at=now,
                )
            )
    finally:
        await engine.dispose()


async def _mark_image_review_required(settings: Settings, project_id: uuid.UUID) -> None:
    engine = create_database_engine(settings)
    now = datetime.now(UTC)
    try:
        async with engine.begin() as connection:
            project_status = (
                await connection.execute(
                    select(PaintProject.status)
                    .where(PaintProject.id == project_id)
                    .with_for_update()
                )
            ).scalar_one()
            assert project_status == "IMAGE_UPLOADED"
            await connection.execute(
                update(PaintProject)
                .where(PaintProject.id == project_id)
                .values(status="IMAGE_REVIEW_REQUIRED", updated_at=now)
            )
            await connection.execute(
                StateTransitionEvent.__table__.insert().values(
                    id=uuid.uuid4(),
                    project_id=project_id,
                    from_state="IMAGE_UPLOADED",
                    to_state="IMAGE_REVIEW_REQUIRED",
                    event="image_validation_requires_review",
                    actor_type="system",
                    actor_principal_id="deterministic_test_validator",
                    actor_display_name_snapshot=None,
                    reason="image_validation_review_required",
                    correlation_id=uuid.uuid4(),
                    event_metadata={"schema_version": "test_fixture.v1"},
                    created_at=now,
                )
            )
    finally:
        await engine.dispose()


async def _asset_rows(
    settings: Settings,
    project_id: uuid.UUID,
) -> list[tuple[bool, str]]:
    engine = create_database_engine(settings)
    try:
        async with engine.connect() as connection:
            return [
                (bool(row.is_current), str(row.storage_key))
                for row in (
                    await connection.execute(
                        select(ImageAsset.is_current, ImageAsset.storage_key)
                        .where(ImageAsset.paint_project_id == project_id)
                        .order_by(ImageAsset.version)
                    )
                ).all()
            ]
    finally:
        await engine.dispose()


async def _project_status(settings: Settings, project_id: uuid.UUID) -> str:
    engine = create_database_engine(settings)
    try:
        async with engine.connect() as connection:
            return str(
                (
                    await connection.execute(
                        select(PaintProject.status).where(PaintProject.id == project_id)
                    )
                ).scalar_one()
            )
    finally:
        await engine.dispose()


def test_upload_replay_private_preview_replacement_owner_isolation_and_restart(
    image_integration_settings: Settings,
) -> None:
    settings = image_integration_settings
    first_bytes = _jpeg_bytes("#c77838")
    second_bytes = _jpeg_bytes("#254c6d")
    upload_key = uuid.uuid4()

    with TestClient(create_app(settings)) as client:
        project = _create_project(client)
        project_id = str(project["id"])

        first_response = _upload(
            client,
            project_id,
            image_bytes=first_bytes,
            idempotency_key=upload_key,
            color_label='primary "quoted".jpg',
        )
        assert first_response.status_code == 201, first_response.text
        first = first_response.json()
        assert first["version"] == 1
        assert first["is_current"] is True
        assert first["upload_validation_result"] == "accepted"
        assert first["rights_attestation_status"] == "confirmed"
        assert "storage_key" not in first
        assert "owner_principal_id" not in first

        replay = _upload(
            client,
            project_id,
            image_bytes=first_bytes,
            idempotency_key=upload_key,
            color_label='primary "quoted".jpg',
        )
        assert replay.status_code == 201
        assert replay.headers["Idempotent-Replayed"] == "true"
        assert replay.json() == first

        conflict = _upload(
            client,
            project_id,
            image_bytes=first_bytes,
            idempotency_key=upload_key,
            color_label='primary "quoted".jpg',
            intended_usage=("portfolio_demo",),
        )
        assert conflict.status_code == 409
        assert conflict.json()["error_code"] == "IDEMPOTENCY_KEY_REUSED"

        filename_conflict = _upload(
            client,
            project_id,
            image_bytes=first_bytes,
            idempotency_key=upload_key,
            color_label="renamed.jpg",
        )
        assert filename_conflict.status_code == 409
        assert filename_conflict.json()["error_code"] == "IDEMPOTENCY_KEY_REUSED"

        saved_project = client.get(f"/api/v1/paint-projects/{project_id}")
        assert saved_project.status_code == 200
        assert saved_project.json()["status"] == "IMAGE_UPLOADED"
        assert saved_project.json()["current_image_asset_id"] == first["id"]

        listing = client.get(f"/api/v1/paint-projects/{project_id}/images")
        assert listing.status_code == 200
        assert listing.json()["items"] == [first]
        detail = client.get(f"/api/v1/paint-projects/{project_id}/images/{first['id']}")
        assert detail.status_code == 200
        assert detail.json() == first

        preview = client.get(first["content_url"])
        assert preview.status_code == 200
        assert preview.content == first_bytes
        assert preview.headers["content-type"] == "image/jpeg"
        assert preview.headers["cache-control"] == "private, no-store, max-age=0"
        assert preview.headers["x-content-type-options"] == "nosniff"
        assert (
            preview.headers["content-disposition"]
            == "inline; filename*=UTF-8''paintpilot-image.jpg"
        )
        ranged = client.get(first["content_url"], headers={"Range": "bytes=0-10"})
        assert ranged.status_code == 416

        asyncio.run(
            _mark_image_review_required(
                settings,
                uuid.UUID(project_id),
            )
        )
        replacement = _upload(
            client,
            project_id,
            image_bytes=second_bytes,
            idempotency_key=uuid.uuid4(),
            color_label="image-set-replacement.jpg",
        )
        assert replacement.status_code == 201, replacement.text
        second = replacement.json()
        assert second["version"] == 2
        assert second["supersedes_image_asset_id"] == first["id"]
        assert second["is_current"] is True

        history = client.get(f"/api/v1/paint-projects/{project_id}/images").json()["items"]
        assert [item["version"] for item in history] == [2, 1]
        assert history[1]["lifecycle_status"] == "superseded"
        assert history[1]["is_current"] is False
        assert client.get(first["content_url"]).content == first_bytes
        assert client.get(second["content_url"]).content == second_bytes

    rows = asyncio.run(_asset_rows(settings, uuid.UUID(project_id)))
    assert len(rows) == 2
    assert sum(is_current for is_current, _storage_key in rows) == 1
    assert all(
        Path(settings.image_storage_root).joinpath(storage_key).is_file()
        for _is_current, storage_key in rows
    )

    other_settings = _settings(
        f"phase1e1-other-{uuid.uuid4().hex}",
        Path(settings.image_storage_root),
    )
    with TestClient(create_app(other_settings)) as other_client:
        assert other_client.get(f"/api/v1/paint-projects/{project_id}/images").status_code == 404
        assert (
            other_client.get(
                f"/api/v1/paint-projects/{project_id}/images/{first['id']}"
            ).status_code
            == 404
        )
        assert other_client.get(first["content_url"]).status_code == 404

    with TestClient(create_app(settings)) as restarted_client:
        persisted = restarted_client.get(f"/api/v1/paint-projects/{project_id}/images")
        assert persisted.status_code == 200
        assert len(persisted.json()["items"]) == 2
        assert restarted_client.get(second["content_url"]).content == second_bytes


def test_invalid_corrupt_unknown_and_oversized_uploads_leave_no_assets(
    image_integration_settings: Settings,
) -> None:
    settings = image_integration_settings
    with TestClient(create_app(settings)) as client:
        project = _create_project(client)
        project_id = str(project["id"])

        corrupt = _upload(
            client,
            project_id,
            image_bytes=b"\xff\xd8\xffcorrupt",
            idempotency_key=uuid.uuid4(),
        )
        assert corrupt.status_code == 422
        assert corrupt.json()["error_code"] == "REJECTED_CORRUPT"

        unknown = client.post(
            f"/api/v1/paint-projects/{project_id}/images",
            headers={"Idempotency-Key": str(uuid.uuid4())},
            data={
                "role": "primary_front",
                "source_type": "user_photographed",
                "intended_usage": "private_project",
                "rights_attestation_confirmed": "true",
                "rights_attestation_version": "1",
                "unexpected": "not allowed",
            },
            files={"file": ("primary.jpg", _jpeg_bytes(), "image/jpeg")},
        )
        assert unknown.status_code == 422

        oversized = _upload(
            client,
            project_id,
            image_bytes=b"\xff\xd8\xff" + b"x" * (20 * 1024 * 1024),
            idempotency_key=uuid.uuid4(),
        )
        assert oversized.status_code == 413

    assert asyncio.run(_asset_rows(settings, uuid.UUID(project_id))) == []
    objects_root = Path(settings.image_storage_root) / "objects"
    assert list(objects_root.glob("*/*")) == []


def test_concurrent_same_upload_command_creates_exactly_one_asset(
    image_integration_settings: Settings,
) -> None:
    settings = image_integration_settings
    image_bytes = _jpeg_bytes("#586c42")
    idempotency_key = uuid.uuid4()
    with TestClient(create_app(settings)) as setup_client:
        project_id = str(_create_project(setup_client)["id"])

    def concurrent_upload() -> tuple[int, str | None, dict[str, object]]:
        with TestClient(create_app(settings)) as client:
            response = _upload(
                client,
                project_id,
                image_bytes=image_bytes,
                idempotency_key=idempotency_key,
            )
            return (
                response.status_code,
                response.headers.get("Idempotent-Replayed"),
                response.json(),
            )

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        first_future = executor.submit(concurrent_upload)
        second_future = executor.submit(concurrent_upload)
        responses = [first_future.result(timeout=20), second_future.result(timeout=20)]

    assert [status for status, _replayed, _payload in responses] == [201, 201]
    assert sorted(replayed for _status, replayed, _payload in responses if replayed) == ["true"]
    assert responses[0][2] == responses[1][2]
    assert len(asyncio.run(_asset_rows(settings, uuid.UUID(project_id)))) == 1


def test_same_idempotency_key_different_project_is_independent(
    image_integration_settings: Settings,
) -> None:
    settings = image_integration_settings
    shared_key = uuid.uuid4()
    with TestClient(create_app(settings)) as client:
        first_project_id = str(_create_project(client)["id"])
        second_project_id = str(_create_project(client)["id"])
        first = _upload(
            client,
            first_project_id,
            image_bytes=_jpeg_bytes("#c77838"),
            idempotency_key=shared_key,
            color_label="first-project.jpg",
        )
        second = _upload(
            client,
            second_project_id,
            image_bytes=_jpeg_bytes("#254c6d"),
            idempotency_key=shared_key,
            color_label="second-project.jpg",
        )

    assert first.status_code == 201
    assert second.status_code == 201
    assert "Idempotent-Replayed" not in first.headers
    assert "Idempotent-Replayed" not in second.headers
    assert first.json()["id"] != second.json()["id"]
    assert first.json()["paint_project_id"] == first_project_id
    assert second.json()["paint_project_id"] == second_project_id
    assert "payload_hash" not in first.text
    assert "payload_hash" not in second.text
    assert len(asyncio.run(_asset_rows(settings, uuid.UUID(first_project_id)))) == 1
    assert len(asyncio.run(_asset_rows(settings, uuid.UUID(second_project_id)))) == 1


def test_same_idempotency_key_different_principal_is_independent(
    image_integration_settings: Settings,
) -> None:
    first_settings = image_integration_settings
    second_principal_id = f"phase1e1-independent-{uuid.uuid4().hex}"
    second_settings = _settings(
        second_principal_id,
        Path(first_settings.image_storage_root),
    )
    asyncio.run(_cleanup(second_settings, second_principal_id))
    shared_key = uuid.uuid4()
    try:
        with TestClient(create_app(first_settings)) as first_client:
            first_project_id = str(_create_project(first_client)["id"])
            first = _upload(
                first_client,
                first_project_id,
                image_bytes=_jpeg_bytes("#c77838"),
                idempotency_key=shared_key,
                color_label="first-principal.jpg",
            )
        with TestClient(create_app(second_settings)) as second_client:
            second_project_id = str(_create_project(second_client)["id"])
            second = _upload(
                second_client,
                second_project_id,
                image_bytes=_jpeg_bytes("#254c6d"),
                idempotency_key=shared_key,
                color_label="second-principal.jpg",
            )

        assert first.status_code == 201
        assert second.status_code == 201
        assert "Idempotent-Replayed" not in first.headers
        assert "Idempotent-Replayed" not in second.headers
        assert first.json()["id"] != second.json()["id"]
        assert first.json()["paint_project_id"] == first_project_id
        assert second.json()["paint_project_id"] == second_project_id
    finally:
        asyncio.run(_cleanup(second_settings, second_principal_id))


def test_forced_storage_key_collision_preserves_existing_object_and_skips_compensation(
    image_integration_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = image_integration_settings
    first_bytes = _jpeg_bytes("#c77838")
    second_bytes = _jpeg_bytes("#254c6d")
    with TestClient(create_app(settings)) as client:
        first_project_id = str(_create_project(client)["id"])
        second_project_id = str(_create_project(client)["id"])
        first = _upload(
            client,
            first_project_id,
            image_bytes=first_bytes,
            idempotency_key=uuid.uuid4(),
            color_label="existing.jpg",
        )
        assert first.status_code == 201

    first_rows = asyncio.run(_asset_rows(settings, uuid.UUID(first_project_id)))
    assert len(first_rows) == 1
    existing_key = first_rows[0][1]
    existing_path = Path(settings.image_storage_root) / existing_key
    existing_identifier = Path(existing_key).stem
    compensation_keys: list[str] = []
    original_delete = LocalFilesystemImageStorageAdapter.delete_uncommitted

    def forced_identifier(_storage: LocalFilesystemImageStorageAdapter) -> str:
        return existing_identifier

    def track_compensation(
        storage: LocalFilesystemImageStorageAdapter,
        receipt: StoragePublishReceipt,
        *,
        referenced_keys: set[str],
    ) -> None:
        compensation_keys.append(receipt.key)
        original_delete(storage, receipt, referenced_keys=referenced_keys)

    monkeypatch.setattr(
        LocalFilesystemImageStorageAdapter,
        "_new_object_identifier",
        forced_identifier,
    )
    monkeypatch.setattr(
        LocalFilesystemImageStorageAdapter,
        "delete_uncommitted",
        track_compensation,
    )
    with TestClient(create_app(settings)) as client:
        collision = _upload(
            client,
            second_project_id,
            image_bytes=second_bytes,
            idempotency_key=uuid.uuid4(),
            color_label="collision.jpg",
        )

    assert collision.status_code == 503
    assert collision.json()["error_code"] == "IMAGE_STORAGE_COLLISION"
    assert existing_key not in collision.text
    assert str(settings.image_storage_root) not in collision.text
    assert compensation_keys == []
    assert existing_path.read_bytes() == first_bytes
    assert asyncio.run(_asset_rows(settings, uuid.UUID(first_project_id))) == first_rows
    assert asyncio.run(_asset_rows(settings, uuid.UUID(second_project_id))) == []
    assert asyncio.run(_project_status(settings, uuid.UUID(second_project_id))) == "DRAFT"
    assert {
        path.relative_to(settings.image_storage_root).as_posix()
        for path in (Path(settings.image_storage_root) / "objects").glob("*/*")
    } == {existing_key}
    assert list((Path(settings.image_storage_root) / "staging").iterdir()) == []


def test_database_and_storage_failures_compensate_without_residual_assets(
    image_integration_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = image_integration_settings
    with TestClient(create_app(settings)) as setup_client:
        first_project_id = str(_create_project(setup_client)["id"])
        first_upload = _upload(
            setup_client,
            first_project_id,
            image_bytes=_jpeg_bytes("#c77838"),
            idempotency_key=uuid.uuid4(),
            color_label="existing.jpg",
        )
        assert first_upload.status_code == 201
    asyncio.run(_mark_image_validation_failed(settings, uuid.UUID(first_project_id)))
    first_rows = asyncio.run(_asset_rows(settings, uuid.UUID(first_project_id)))
    assert len(first_rows) == 1
    first_key = first_rows[0][1]
    first_path = Path(settings.image_storage_root) / first_key
    first_bytes = first_path.read_bytes()

    async def fail_flush(_repository: SqlAlchemyImageAssetRepository) -> None:
        raise RuntimeError("forced post-storage database failure")

    monkeypatch.setattr(SqlAlchemyImageAssetRepository, "flush", fail_flush)
    with TestClient(create_app(settings), raise_server_exceptions=False) as client:
        database_failure = _upload(
            client,
            first_project_id,
            image_bytes=_jpeg_bytes("#254c6d"),
            idempotency_key=uuid.uuid4(),
            color_label="failed-replacement.jpg",
        )
    assert database_failure.status_code == 500
    assert database_failure.json()["error_code"] == "INTERNAL_ERROR"
    assert asyncio.run(_asset_rows(settings, uuid.UUID(first_project_id))) == first_rows
    assert asyncio.run(_project_status(settings, uuid.UUID(first_project_id))) == (
        "IMAGE_VALIDATION_FAILED"
    )
    assert first_path.read_bytes() == first_bytes
    objects_root = Path(settings.image_storage_root) / "objects"
    assert {
        path.relative_to(settings.image_storage_root).as_posix()
        for path in objects_root.glob("*/*")
    } == {first_key}

    monkeypatch.undo()
    with TestClient(create_app(settings)) as setup_client:
        second_project_id = str(_create_project(setup_client)["id"])

    def fail_storage(
        _storage: LocalFilesystemImageStorageAdapter,
        _staged: object,
        *,
        detected_format: str,
    ) -> object:
        del detected_format
        raise ImageStorageError("forced storage failure")

    monkeypatch.setattr(
        LocalFilesystemImageStorageAdapter,
        "put_from_temp",
        fail_storage,
    )
    with TestClient(create_app(settings)) as client:
        storage_failure = _upload(
            client,
            second_project_id,
            image_bytes=_jpeg_bytes(),
            idempotency_key=uuid.uuid4(),
        )
    assert storage_failure.status_code == 503
    assert storage_failure.json()["error_code"] == "IMAGE_STORAGE_UNAVAILABLE"
    assert asyncio.run(_asset_rows(settings, uuid.UUID(second_project_id))) == []
    assert {
        path.relative_to(settings.image_storage_root).as_posix()
        for path in objects_root.glob("*/*")
    } == {first_key}


def test_compensation_failure_is_recorded_and_orphan_is_detectable(
    image_integration_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    settings = image_integration_settings
    with TestClient(create_app(settings)) as setup_client:
        project_id = str(_create_project(setup_client)["id"])

    async def fail_flush(_repository: SqlAlchemyImageAssetRepository) -> None:
        raise RuntimeError("forced post-storage database failure")

    def refuse_compensation(
        _storage: LocalFilesystemImageStorageAdapter,
        _receipt: StoragePublishReceipt,
        *,
        referenced_keys: set[str],
    ) -> None:
        del referenced_keys
        raise ImageStorageError("forced compensation refusal")

    monkeypatch.setattr(SqlAlchemyImageAssetRepository, "flush", fail_flush)
    monkeypatch.setattr(
        LocalFilesystemImageStorageAdapter,
        "delete_uncommitted",
        refuse_compensation,
    )
    with (
        caplog.at_level(
            logging.ERROR,
            logger="creativedeploy_api.services.image_assets",
        ),
        TestClient(create_app(settings), raise_server_exceptions=False) as client,
    ):
        response = _upload(
            client,
            project_id,
            image_bytes=_jpeg_bytes(),
            idempotency_key=uuid.uuid4(),
        )

    assert response.status_code == 500
    assert asyncio.run(_asset_rows(settings, uuid.UUID(project_id))) == []
    orphan_records = [
        record
        for record in caplog.records
        if getattr(record, "compensation_status", None) == "object_not_deleted"
    ]
    assert len(orphan_records) == 1
    assert orphan_records[0].orphan_detection_required is True
    storage = LocalFilesystemImageStorageAdapter(Path(settings.image_storage_root))
    orphans = storage.scan_orphans(referenced_keys=set())
    assert len(orphans) == 1
    assert storage.safe_cleanup_orphan(orphans[0], referenced_keys=set()) is True
    assert list((storage.root / "objects").glob("*/*")) == []
    assert list((storage.root / "staging").iterdir()) == []
