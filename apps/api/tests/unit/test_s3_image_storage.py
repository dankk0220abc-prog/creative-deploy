"""Private S3 adapter tests without an external object-store dependency."""

import asyncio
import hashlib
import io
from pathlib import Path
from typing import Any

import pytest
from botocore.exceptions import ClientError
from fastapi import UploadFile

from creativedeploy_api.storage.images import ImageStorageError
from creativedeploy_api.storage.s3 import S3ImageStorageAdapter


def _client_error(code: str, operation: str, *, status: int = 404) -> ClientError:
    return ClientError(
        {
            "Error": {"Code": code, "Message": code},
            "ResponseMetadata": {"HTTPStatusCode": status},
        },
        operation,
    )


class _Body:
    def __init__(self, payload: bytes) -> None:
        self._stream = io.BytesIO(payload)
        self.closed = False

    def read(self, size: int = -1) -> bytes:
        return self._stream.read(size)

    def close(self) -> None:
        self.closed = True
        self._stream.close()


class FakePrivateS3:
    """Small stateful fake that models only the calls made by the adapter."""

    def __init__(
        self,
        *,
        grants: list[dict[str, Any]] | None = None,
        policy: str | None = None,
    ) -> None:
        self.grants = grants or [{"Grantee": {"Type": "CanonicalUser"}}]
        self.policy = policy
        self.objects: dict[str, dict[str, Any]] = {}
        self.head_calls: list[str] = []
        self.put_calls: list[str] = []
        self.delete_calls: list[str] = []

    def head_bucket(self, **_kwargs: object) -> dict[str, object]:
        return {}

    def get_bucket_acl(self, **_kwargs: object) -> dict[str, object]:
        return {"Grants": self.grants}

    def get_bucket_policy(self, **_kwargs: object) -> dict[str, str]:
        if self.policy is None:
            raise _client_error("NoSuchBucketPolicy", "GetBucketPolicy")
        return {"Policy": self.policy}

    def put_object(self, **kwargs: Any) -> dict[str, str]:
        key = str(kwargs["Key"])
        self.put_calls.append(key)
        if key in self.objects:
            raise _client_error("PreconditionFailed", "PutObject", status=412)
        body = kwargs["Body"]
        payload = body.read() if hasattr(body, "read") else bytes(body)
        self.objects[key] = {
            "payload": payload,
            "ContentLength": len(payload),
            "ContentType": kwargs["ContentType"],
            "Metadata": dict(kwargs["Metadata"]),
            "ETag": '"synthetic-etag"',
        }
        return {"ETag": '"synthetic-etag"'}

    def head_object(self, **kwargs: Any) -> dict[str, Any]:
        key = str(kwargs["Key"])
        self.head_calls.append(key)
        try:
            stored = self.objects[key]
        except KeyError as error:
            raise _client_error("NoSuchKey", "HeadObject") from error
        return {
            "ContentLength": stored["ContentLength"],
            "ContentType": stored["ContentType"],
            "Metadata": dict(stored["Metadata"]),
            "ETag": stored["ETag"],
        }

    def get_object(self, **kwargs: Any) -> dict[str, object]:
        key = str(kwargs["Key"])
        try:
            payload = self.objects[key]["payload"]
        except KeyError as error:
            raise _client_error("NoSuchKey", "GetObject") from error
        return {"Body": _Body(payload)}

    def delete_object(self, **kwargs: Any) -> dict[str, object]:
        key = str(kwargs["Key"])
        self.delete_calls.append(key)
        del self.objects[key]
        return {}

    def list_objects_v2(self, **_kwargs: object) -> dict[str, object]:
        return {
            "Contents": [{"Key": key} for key in sorted(self.objects)],
            "IsTruncated": False,
        }


def _adapter(tmp_path: Path, client: FakePrivateS3) -> S3ImageStorageAdapter:
    return S3ImageStorageAdapter(
        endpoint_url="http://s3.example.test",
        region="us-east-1",
        bucket="private-paintpilot",
        access_key_id="synthetic-access",
        secret_access_key="synthetic-secret",
        force_path_style=True,
        staging_root=tmp_path / "staging",
        create_bucket=False,
        client=client,
    )


def test_s3_upload_is_private_verified_and_streamed_without_provider_url(
    tmp_path: Path,
) -> None:
    client = FakePrivateS3()
    storage = _adapter(tmp_path, client)
    payload = b"synthetic private image bytes"
    staged = asyncio.run(
        storage.stage_upload(
            UploadFile(filename="private.jpg", file=io.BytesIO(payload)),
            max_bytes=len(payload),
        )
    )

    receipt = storage.put_from_temp(staged, detected_format="jpeg")

    assert receipt.provider_name == "s3"
    assert receipt.key.startswith("objects/")
    assert receipt.expected_sha256 == hashlib.sha256(payload).hexdigest()
    assert staged.path.exists() is False
    assert client.objects[receipt.key]["Metadata"] == {
        "sha256": hashlib.sha256(payload).hexdigest()
    }
    assert client.objects[receipt.key]["ContentType"] == "image/jpeg"
    with storage.open_private(receipt.key) as stream:
        assert stream.read() == payload
    assert storage.scan_orphans(referenced_keys=set()) == (receipt.key,)
    assert storage.scan_orphans(referenced_keys={receipt.key}) == ()
    assert not hasattr(storage, "public_url")
    assert not hasattr(storage, "signed_url")
    assert not hasattr(storage, "presigned_url")


@pytest.mark.parametrize(
    ("client", "message"),
    [
        (
            FakePrivateS3(
                grants=[
                    {
                        "Grantee": {
                            "Type": "Group",
                            "URI": "http://acs.amazonaws.com/groups/global/AllUsers",
                        }
                    }
                ]
            ),
            "not private",
        ),
        (
            FakePrivateS3(policy='{"Statement":[{"Effect":"Allow","Principal":"*"}]}'),
            "policies are refused",
        ),
    ],
)
def test_s3_adapter_fails_closed_on_public_acl_or_bucket_policy(
    tmp_path: Path,
    client: FakePrivateS3,
    message: str,
) -> None:
    with pytest.raises(ImageStorageError, match=message):
        _adapter(tmp_path, client)


def test_s3_publish_identity_failure_is_not_reported_as_success(
    tmp_path: Path,
) -> None:
    client = FakePrivateS3()
    storage = _adapter(tmp_path, client)
    payload = b"synthetic image"
    staged = asyncio.run(
        storage.stage_upload(
            UploadFile(filename="private.jpg", file=io.BytesIO(payload)),
            max_bytes=len(payload),
        )
    )
    original_head = client.head_object

    def changed_head(**kwargs: Any) -> dict[str, Any]:
        result = original_head(**kwargs)
        result["Metadata"] = {"sha256": "0" * 64}
        return result

    client.head_object = changed_head  # type: ignore[method-assign]

    with pytest.raises(ImageStorageError, match="identity could not be proven"):
        storage.put_from_temp(staged, detected_format="jpeg")

    assert staged.path.is_file()
    assert len(client.objects) == 1
    storage.delete_staged(staged)


def test_legacy_copy_is_idempotent_and_never_deletes_source(
    tmp_path: Path,
) -> None:
    client = FakePrivateS3()
    storage = _adapter(tmp_path, client)
    payload = b"legacy private bytes"
    digest = hashlib.sha256(payload).hexdigest()
    source = io.BytesIO(payload)

    first = storage.copy_verified_object(
        key="objects/aa/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.jpg",
        source=source,
        byte_size=len(payload),
        sha256=digest,
        content_type="image/jpeg",
    )
    assert client.head_calls == [first.key, first.key]
    second = storage.copy_verified_object(
        key=first.key,
        source=io.BytesIO(payload),
        byte_size=len(payload),
        sha256=digest,
        content_type="image/jpeg",
    )

    assert first.created_by_this_call is True
    assert second.created_by_this_call is False
    assert source.closed is False
    assert client.objects[first.key]["payload"] == payload
    assert client.head_calls == [first.key, first.key, first.key]
    assert client.put_calls == [first.key]
    assert client.delete_calls == []


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("ContentLength", 1),
        ("Metadata", {"sha256": "0" * 64}),
        ("ContentType", "application/octet-stream"),
    ],
)
def test_legacy_copy_rejects_post_write_destination_fact_mismatch(
    tmp_path: Path,
    field: str,
    value: object,
) -> None:
    client = FakePrivateS3()
    storage = _adapter(tmp_path, client)
    payload = b"legacy post-write verification"
    digest = hashlib.sha256(payload).hexdigest()
    key = "objects/bb/bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb.jpg"
    original_head = client.head_object

    def changed_post_write_head(**kwargs: Any) -> dict[str, Any]:
        response = original_head(**kwargs)
        response[field] = value
        return response

    client.head_object = changed_post_write_head  # type: ignore[method-assign]

    with pytest.raises(ImageStorageError, match="failed integrity verification"):
        storage.copy_verified_object(
            key=key,
            source=io.BytesIO(payload),
            byte_size=len(payload),
            sha256=digest,
            content_type="image/jpeg",
        )

    assert client.head_calls == [key, key]
    assert client.put_calls == [key]
    assert client.delete_calls == []


def test_legacy_copy_rejects_post_write_head_failure_as_retryable(
    tmp_path: Path,
) -> None:
    client = FakePrivateS3()
    storage = _adapter(tmp_path, client)
    payload = b"legacy transient head failure"
    digest = hashlib.sha256(payload).hexdigest()
    key = "objects/cc/cccccccccccccccccccccccccccccccc.jpg"
    original_head = client.head_object
    attempts = 0

    def failing_post_write_head(**kwargs: Any) -> dict[str, Any]:
        nonlocal attempts
        attempts += 1
        if attempts == 2:
            raise _client_error("ServiceUnavailable", "HeadObject", status=503)
        return original_head(**kwargs)

    client.head_object = failing_post_write_head  # type: ignore[method-assign]

    with pytest.raises(ImageStorageError, match="retried safely"):
        storage.copy_verified_object(
            key=key,
            source=io.BytesIO(payload),
            byte_size=len(payload),
            sha256=digest,
            content_type="image/jpeg",
        )

    assert attempts == 2
    assert client.put_calls == [key]
    assert client.delete_calls == []


def test_legacy_copy_existing_exact_object_is_verified_without_using_etag_as_hash(
    tmp_path: Path,
) -> None:
    client = FakePrivateS3()
    storage = _adapter(tmp_path, client)
    payload = b"legacy idempotent exact object"
    digest = hashlib.sha256(payload).hexdigest()
    key = "objects/dd/dddddddddddddddddddddddddddddddd.jpg"
    client.objects[key] = {
        "payload": payload,
        "ContentLength": len(payload),
        "ContentType": "image/jpeg",
        "Metadata": {"sha256": digest},
        "ETag": '"not-a-content-checksum"',
    }

    receipt = storage.copy_verified_object(
        key=key,
        source=io.BytesIO(payload),
        byte_size=len(payload),
        sha256=digest,
        content_type="image/jpeg",
    )

    assert receipt.created_by_this_call is False
    assert client.head_calls == [key]
    assert client.put_calls == []


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("ContentLength", 1),
        ("Metadata", {"sha256": "f" * 64}),
        ("ContentType", "image/png"),
    ],
)
def test_legacy_copy_existing_mismatched_object_is_never_overwritten(
    tmp_path: Path,
    field: str,
    value: object,
) -> None:
    client = FakePrivateS3()
    storage = _adapter(tmp_path, client)
    payload = b"legacy immutable mismatch"
    digest = hashlib.sha256(payload).hexdigest()
    key = "objects/ee/eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee.jpg"
    client.objects[key] = {
        "payload": payload,
        "ContentLength": len(payload),
        "ContentType": "image/jpeg",
        "Metadata": {"sha256": digest},
        "ETag": '"synthetic-etag"',
    }
    client.objects[key][field] = value

    with pytest.raises(ImageStorageError, match="different immutable content"):
        storage.copy_verified_object(
            key=key,
            source=io.BytesIO(payload),
            byte_size=len(payload),
            sha256=digest,
            content_type="image/jpeg",
        )

    assert client.head_calls == [key]
    assert client.put_calls == []
    assert client.delete_calls == []
