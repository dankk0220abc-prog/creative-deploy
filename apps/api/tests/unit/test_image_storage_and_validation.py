"""Deterministic image validation and private local storage contract tests."""

import asyncio
import concurrent.futures
import errno
import hashlib
import io
import os
import threading
from pathlib import Path

import pytest
from fastapi import UploadFile
from PIL import Image
from pydantic import ValidationError

from creativedeploy_api.core.config import Settings
from creativedeploy_api.services.image_validation import (
    DeterministicImageValidationError,
    ImageValidationLimits,
    safe_original_filename,
    validate_image_file,
)
from creativedeploy_api.storage.images import (
    ImageStorageError,
    ImageUploadTooLargeError,
    LocalFilesystemImageStorageAdapter,
    StagedUpload,
    StorageCompensationRefusedError,
    StorageObjectAlreadyExistsError,
    StoragePublishReceipt,
    UnsafeStorageKeyError,
)

LIMITS = ImageValidationLimits(
    max_bytes=20 * 1024 * 1024,
    min_side_px=768,
    max_side_px=8192,
    max_pixels=40_000_000,
)


def _image_bytes(format_name: str, *, size: tuple[int, int] = (768, 768)) -> bytes:
    output = io.BytesIO()
    Image.new("RGBA" if format_name == "PNG" else "RGB", size, "#c77838").save(
        output,
        format=format_name,
    )
    return output.getvalue()


@pytest.mark.parametrize(
    ("format_name", "content_type", "detected_format", "has_alpha"),
    [
        ("JPEG", "image/jpeg", "jpeg", False),
        ("PNG", "image/png", "png", True),
        ("WEBP", "image/webp", "webp", False),
    ],
)
def test_real_decoder_accepts_only_allowed_complete_static_images(
    tmp_path: Path,
    format_name: str,
    content_type: str,
    detected_format: str,
    has_alpha: bool,
) -> None:
    path = tmp_path / "fixture.bin"
    path.write_bytes(_image_bytes(format_name))

    result = validate_image_file(
        path,
        declared_content_type=content_type,
        byte_size=path.stat().st_size,
        limits=LIMITS,
    )

    assert result.detected_format == detected_format
    assert result.width == 768
    assert result.height == 768
    assert result.pixel_count == 768 * 768
    assert result.has_alpha is has_alpha
    assert result.validation_details == {
        "validation_contract": "phase_1e_1_upload_validation.v1",
        "signature_verified": True,
        "declared_content_type_verified": True,
        "decoder_verified": True,
        "fully_decoded": True,
        "animated": False,
    }


@pytest.mark.parametrize(
    ("payload", "content_type", "expected_code"),
    [
        (b"not an image", "image/jpeg", "rejected_unsupported_format"),
        (_image_bytes("JPEG"), "image/png", "rejected_content_type_mismatch"),
        (_image_bytes("JPEG")[:-20], "image/jpeg", "rejected_corrupt"),
        (_image_bytes("PNG", size=(767, 768)), "image/png", "rejected_dimensions"),
    ],
)
def test_signature_mime_dimensions_and_corruption_fail_closed(
    tmp_path: Path,
    payload: bytes,
    content_type: str,
    expected_code: str,
) -> None:
    path = tmp_path / "fixture.bin"
    path.write_bytes(payload)

    with pytest.raises(DeterministicImageValidationError) as captured:
        validate_image_file(
            path,
            declared_content_type=content_type,
            byte_size=len(payload),
            limits=LIMITS,
        )

    assert captured.value.code == expected_code
    assert str(tmp_path) not in captured.value.safe_message


def test_pixel_limit_is_checked_before_full_decode(tmp_path: Path) -> None:
    path = tmp_path / "fixture.png"
    path.write_bytes(_image_bytes("PNG"))
    limits = ImageValidationLimits(
        max_bytes=LIMITS.max_bytes,
        min_side_px=LIMITS.min_side_px,
        max_side_px=LIMITS.max_side_px,
        max_pixels=500_000,
    )

    with pytest.raises(
        DeterministicImageValidationError,
        match="more pixels",
    ) as captured:
        validate_image_file(
            path,
            declared_content_type="image/png",
            byte_size=path.stat().st_size,
            limits=limits,
        )

    assert captured.value.code == "rejected_pixel_limit"


def test_animated_webp_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "animated.webp"
    first = Image.new("RGB", (768, 768), "#c77838")
    second = Image.new("RGB", (768, 768), "#254c6d")
    first.save(
        path,
        format="WEBP",
        save_all=True,
        append_images=[second],
        duration=100,
        loop=0,
    )

    with pytest.raises(DeterministicImageValidationError) as captured:
        validate_image_file(
            path,
            declared_content_type="image/webp",
            byte_size=path.stat().st_size,
            limits=LIMITS,
        )

    assert captured.value.code == "rejected_unsupported_format"


def test_storage_streams_hashes_atomically_opens_and_detects_orphan(
    tmp_path: Path,
) -> None:
    storage = LocalFilesystemImageStorageAdapter(tmp_path / "private")
    payload = _image_bytes("JPEG")
    upload = UploadFile(
        filename="../../private/photo.jpeg",
        file=io.BytesIO(payload),
        headers={"content-type": "image/jpeg"},
    )

    staged = asyncio.run(storage.stage_upload(upload, max_bytes=len(payload)))
    assert staged.sha256
    assert staged.byte_size == len(payload)
    assert staged.path.parent.name == "staging"
    assert staged.path.stat().st_mode & 0o777 == 0o600

    stored = storage.put_from_temp(staged, detected_format="jpeg")
    assert stored.key.startswith("objects/")
    assert stored.created_by_this_call is True
    assert stored.expected_sha256 == hashlib.sha256(payload).hexdigest()
    assert stored.byte_size == len(payload)
    assert stored.inode > 0
    assert stored.link_count == 1
    assert storage.exists(stored.key)
    with storage.open_private(stored.key) as stream:
        assert stream.read() == payload
    assert storage.scan_orphans(referenced_keys=set()) == (stored.key,)
    assert storage.scan_orphans(referenced_keys={stored.key}) == ()
    assert storage.safe_cleanup_orphan(stored.key, referenced_keys={stored.key}) is False
    assert storage.safe_cleanup_orphan(stored.key, referenced_keys=set()) is True
    assert not storage.exists(stored.key)


def test_duplicate_storage_key_preserves_existing_object(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage = LocalFilesystemImageStorageAdapter(tmp_path / "private")
    identifier = "a" * 32
    monkeypatch.setattr(storage, "_new_object_identifier", lambda: identifier)
    first_payload = _image_bytes("JPEG")
    second_payload = first_payload + b"different collision payload"
    first_staged = asyncio.run(
        storage.stage_upload(
            UploadFile(filename="first.jpg", file=io.BytesIO(first_payload)),
            max_bytes=len(first_payload),
        )
    )
    first_receipt = storage.put_from_temp(first_staged, detected_format="jpeg")
    first_sha256 = hashlib.sha256(first_payload).hexdigest()
    second_staged = asyncio.run(
        storage.stage_upload(
            UploadFile(filename="second.jpg", file=io.BytesIO(second_payload)),
            max_bytes=len(second_payload),
        )
    )

    with pytest.raises(StorageObjectAlreadyExistsError):
        storage.put_from_temp(second_staged, detected_format="jpeg")

    assert second_staged.path.is_file()
    storage.delete_staged(second_staged)
    with storage.open_private(first_receipt.key) as stream:
        stored_bytes = stream.read()
    assert stored_bytes == first_payload
    assert hashlib.sha256(stored_bytes).hexdigest() == first_sha256
    assert storage.scan_orphans(referenced_keys=set()) == (first_receipt.key,)
    assert list((storage.root / "staging").iterdir()) == []


def test_concurrent_same_key_publish_has_one_receipt_and_one_complete_object(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage = LocalFilesystemImageStorageAdapter(tmp_path / "private")
    identifier = "b" * 32
    monkeypatch.setattr(storage, "_new_object_identifier", lambda: identifier)
    payloads = (_image_bytes("JPEG"), _image_bytes("JPEG", size=(769, 768)))
    staged_uploads = tuple(
        asyncio.run(
            storage.stage_upload(
                UploadFile(filename=f"candidate-{index}.jpg", file=io.BytesIO(payload)),
                max_bytes=len(payload),
            )
        )
        for index, payload in enumerate(payloads)
    )
    barrier = threading.Barrier(2)

    def publish(staged: StagedUpload) -> StoragePublishReceipt:
        barrier.wait(timeout=5)
        return storage.put_from_temp(staged, detected_format="jpeg")

    receipts: list[StoragePublishReceipt] = []
    collisions = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(publish, staged) for staged in staged_uploads]
        for future in futures:
            try:
                receipts.append(future.result(timeout=10))
            except StorageObjectAlreadyExistsError:
                collisions += 1

    assert len(receipts) == 1
    assert collisions == 1
    with storage.open_private(receipts[0].key) as stream:
        final_payload = stream.read()
    assert final_payload in payloads
    assert hashlib.sha256(final_payload).hexdigest() == receipts[0].expected_sha256
    for staged in staged_uploads:
        if staged.path.exists():
            storage.delete_staged(staged)
    assert list((storage.root / "staging").iterdir()) == []


def test_delete_uncommitted_refuses_changed_receipt_identity(
    tmp_path: Path,
) -> None:
    storage = LocalFilesystemImageStorageAdapter(tmp_path / "private")
    payload = _image_bytes("JPEG")
    staged = asyncio.run(
        storage.stage_upload(
            UploadFile(filename="original.jpg", file=io.BytesIO(payload)),
            max_bytes=len(payload),
        )
    )
    receipt = storage.put_from_temp(staged, detected_format="jpeg")
    object_path = storage.root / receipt.key
    replacement_path = object_path.with_suffix(".replacement")
    replacement_payload = b"replacement identity probe"
    replacement_path.write_bytes(replacement_payload)
    os.replace(replacement_path, object_path)

    with pytest.raises(StorageCompensationRefusedError):
        storage.delete_uncommitted(receipt, referenced_keys=set())

    assert object_path.read_bytes() == replacement_payload
    assert storage.safe_cleanup_orphan(receipt.key, referenced_keys=set()) is True


def test_delete_uncommitted_refuses_database_referenced_object(
    tmp_path: Path,
) -> None:
    storage = LocalFilesystemImageStorageAdapter(tmp_path / "private")
    payload = _image_bytes("JPEG")
    staged = asyncio.run(
        storage.stage_upload(
            UploadFile(filename="referenced.jpg", file=io.BytesIO(payload)),
            max_bytes=len(payload),
        )
    )
    receipt = storage.put_from_temp(staged, detected_format="jpeg")

    with pytest.raises(StorageCompensationRefusedError, match="database reference"):
        storage.delete_uncommitted(receipt, referenced_keys={receipt.key})

    with storage.open_private(receipt.key) as stream:
        assert stream.read() == payload
    assert storage.safe_cleanup_orphan(receipt.key, referenced_keys=set()) is True


def test_atomic_no_replace_publish_fails_closed_when_link_is_unsupported(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage = LocalFilesystemImageStorageAdapter(tmp_path / "private")
    payload = _image_bytes("JPEG")
    staged = asyncio.run(
        storage.stage_upload(
            UploadFile(filename="unsupported.jpg", file=io.BytesIO(payload)),
            max_bytes=len(payload),
        )
    )

    def unsupported_link(*_args: object, **_kwargs: object) -> None:
        raise OSError(errno.EXDEV, "forced cross-device link")

    monkeypatch.setattr(os, "link", unsupported_link)
    with pytest.raises(ImageStorageError, match="no-replace"):
        storage.put_from_temp(staged, detected_format="jpeg")

    assert staged.path.is_file()
    assert list((storage.root / "objects").glob("*/*")) == []
    storage.delete_staged(staged)


def test_storage_stops_stream_at_limit_and_removes_exact_staging_file(
    tmp_path: Path,
) -> None:
    storage = LocalFilesystemImageStorageAdapter(tmp_path / "private")
    upload = UploadFile(filename="large.jpg", file=io.BytesIO(b"x" * 65))

    with pytest.raises(ImageUploadTooLargeError):
        asyncio.run(storage.stage_upload(upload, max_bytes=64))

    assert list((storage.root / "staging").iterdir()) == []


def test_storage_rejects_traversal_absolute_keys_and_symlink_objects(
    tmp_path: Path,
) -> None:
    storage = LocalFilesystemImageStorageAdapter(tmp_path / "private")

    for key in ("../outside.jpg", "/objects/aa/" + "a" * 32 + ".jpg", "objects\\bad"):
        with pytest.raises(UnsafeStorageKeyError):
            storage.open_private(key)

    identifier = "a" * 32
    object_directory = storage.root / "objects" / "aa"
    object_directory.mkdir()
    outside = tmp_path / "outside.jpg"
    outside.write_bytes(b"outside")
    symlink = object_directory / f"{identifier}.jpg"
    os.symlink(outside, symlink)
    with pytest.raises(ImageStorageError):
        storage.open_private(f"objects/aa/{identifier}.jpg")


def test_original_filename_is_display_only_and_never_a_storage_key() -> None:
    assert safe_original_filename("../../secret/photo.jpg") == "photo.jpg"
    assert safe_original_filename(r"C:\private\photo.png") == "photo.png"
    assert safe_original_filename("\x00") == "upload"
    assert safe_original_filename(None) == "upload"


def test_production_local_storage_configuration_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="Production requires the OIDC"):
        Settings(
            app_env="production",
            database_url="postgresql+psycopg://test:test@127.0.0.1:1/test",
            paintpilot_demo_principal_id="owner",
            paintpilot_demo_principal_display_name="Owner",
            image_storage_root=tmp_path,
            _env_file=None,
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("image_upload_max_bytes", 20 * 1024 * 1024 + 1),
        ("image_min_side_px", 767),
        ("image_max_side_px", 8193),
        ("image_max_pixels", 40_000_001),
    ],
)
def test_runtime_configuration_cannot_loosen_database_upload_limits(
    field: str,
    value: int,
) -> None:
    with pytest.raises(ValidationError):
        Settings(
            app_env="test",
            database_url="postgresql+psycopg://test:test@127.0.0.1:1/test",
            paintpilot_demo_principal_id="owner",
            paintpilot_demo_principal_display_name="Owner",
            _env_file=None,
            **{field: value},
        )
