"""Private S3 adapter tests without an external object-store dependency."""

import asyncio
import hashlib
import io
from pathlib import Path
from typing import Any

import pytest
from botocore.exceptions import ClientError
from fastapi import UploadFile

from creativedeploy_api.storage.images import STREAM_CHUNK_BYTES, ImageStorageError
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
    def __init__(self, payload: bytes, *, fail_on_read: int | None = None) -> None:
        self._stream = io.BytesIO(payload)
        self.fail_on_read = fail_on_read
        self.closed = False
        self.read_calls = 0
        self.requested_sizes: list[int] = []
        self.observed_chunks: list[bytes] = []

    def read(self, size: int = -1) -> bytes:
        self.read_calls += 1
        self.requested_sizes.append(size)
        if self.read_calls == self.fail_on_read:
            raise OSError("synthetic interrupted GET stream")
        chunk = self._stream.read(size)
        self.observed_chunks.append(chunk)
        return chunk

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
        self.get_calls: list[str] = []
        self.get_bodies: list[_Body] = []
        self.put_calls: list[str] = []
        self.delete_calls: list[str] = []
        self.fail_get = False
        self.fail_stream_on_read: int | None = None
        self.get_payload_override: bytes | None = None
        self.get_response_overrides: dict[str, object] = {}

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
        self.get_calls.append(key)
        if self.fail_get:
            raise _client_error("ServiceUnavailable", "GetObject", status=503)
        try:
            stored = self.objects[key]
        except KeyError as error:
            raise _client_error("NoSuchKey", "GetObject") from error
        payload = (
            stored["payload"] if self.get_payload_override is None else self.get_payload_override
        )
        body = _Body(payload, fail_on_read=self.fail_stream_on_read)
        self.get_bodies.append(body)
        response: dict[str, object] = {
            "Body": body,
            "ContentLength": stored["ContentLength"],
            "ContentType": stored["ContentType"],
            "Metadata": dict(stored["Metadata"]),
            "ETag": stored["ETag"],
        }
        response.update(self.get_response_overrides)
        return response

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


def _seed_object(
    client: FakePrivateS3,
    *,
    key: str,
    payload: bytes,
    checksum: str,
    content_type: str = "image/jpeg",
    etag: str = '"synthetic-etag"',
) -> None:
    client.objects[key] = {
        "payload": payload,
        "ContentLength": len(payload),
        "ContentType": content_type,
        "Metadata": {"sha256": checksum},
        "ETag": etag,
    }


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
    assert client.get_calls == [receipt.key]
    verification_body = client.get_bodies[0]
    assert b"".join(verification_body.observed_chunks) == payload
    assert hashlib.sha256(b"".join(verification_body.observed_chunks)).hexdigest() == (
        receipt.expected_sha256
    )
    assert verification_body.requested_sizes == [STREAM_CHUNK_BYTES, STREAM_CHUNK_BYTES]
    assert verification_body.closed is True
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
    client.get_payload_override = b"x" * len(payload)

    with pytest.raises(ImageStorageError, match="could not be byte-verified"):
        storage.put_from_temp(staged, detected_format="jpeg")

    assert staged.path.is_file()
    assert len(client.objects) == 1
    assert client.get_calls == list(client.objects)
    assert b"".join(client.get_bodies[0].observed_chunks) == b"x" * len(payload)
    assert client.get_bodies[0].closed is True
    assert client.delete_calls == []
    storage.delete_staged(staged)


def test_legacy_copy_is_idempotent_and_never_deletes_source(
    tmp_path: Path,
) -> None:
    client = FakePrivateS3()
    storage = _adapter(tmp_path, client)
    payload = b"l" * (STREAM_CHUNK_BYTES + 17)
    digest = hashlib.sha256(payload).hexdigest()
    source = io.BytesIO(payload)

    first = storage.copy_verified_object(
        key="objects/aa/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.jpg",
        source=source,
        byte_size=len(payload),
        sha256=digest,
        content_type="image/jpeg",
    )
    assert client.head_calls == [first.key]
    assert client.get_calls == [first.key]
    first_body = client.get_bodies[0]
    assert b"".join(first_body.observed_chunks) == payload
    assert hashlib.sha256(b"".join(first_body.observed_chunks)).hexdigest() == digest
    assert first_body.requested_sizes == [
        STREAM_CHUNK_BYTES,
        STREAM_CHUNK_BYTES,
        STREAM_CHUNK_BYTES,
    ]
    assert first_body.closed is True
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
    assert client.head_calls == [first.key, first.key]
    assert client.get_calls == [first.key, first.key]
    assert b"".join(client.get_bodies[1].observed_chunks) == payload
    assert client.get_bodies[1].closed is True
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
    client.get_response_overrides[field] = value

    with pytest.raises(ImageStorageError, match="could not be byte-verified"):
        storage.copy_verified_object(
            key=key,
            source=io.BytesIO(payload),
            byte_size=len(payload),
            sha256=digest,
            content_type="image/jpeg",
        )

    assert client.head_calls == [key]
    assert client.get_calls == [key]
    assert b"".join(client.get_bodies[0].observed_chunks) == payload
    assert client.get_bodies[0].closed is True
    assert client.put_calls == [key]
    assert client.delete_calls == []


def test_legacy_copy_rejects_post_write_get_failure_as_retryable(
    tmp_path: Path,
) -> None:
    client = FakePrivateS3()
    storage = _adapter(tmp_path, client)
    payload = b"legacy transient GET failure"
    digest = hashlib.sha256(payload).hexdigest()
    key = "objects/cc/cccccccccccccccccccccccccccccccc.jpg"
    client.fail_get = True

    with pytest.raises(ImageStorageError, match="retried safely"):
        storage.copy_verified_object(
            key=key,
            source=io.BytesIO(payload),
            byte_size=len(payload),
            sha256=digest,
            content_type="image/jpeg",
        )

    assert client.head_calls == [key]
    assert client.get_calls == [key]
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
    _seed_object(
        client,
        key=key,
        payload=payload,
        checksum=digest,
        etag='"not-a-content-checksum"',
    )

    receipt = storage.copy_verified_object(
        key=key,
        source=io.BytesIO(payload),
        byte_size=len(payload),
        sha256=digest,
        content_type="image/jpeg",
    )

    assert receipt.created_by_this_call is False
    assert client.head_calls == [key]
    assert client.get_calls == [key]
    body = client.get_bodies[0]
    assert b"".join(body.observed_chunks) == payload
    assert hashlib.sha256(b"".join(body.observed_chunks)).hexdigest() == digest
    assert body.closed is True
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
    _seed_object(client, key=key, payload=payload, checksum=digest)
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
    assert client.get_calls == [key]
    assert b"".join(client.get_bodies[0].observed_chunks) == payload
    assert client.get_bodies[0].closed is True
    assert client.put_calls == []
    assert client.delete_calls == []


def test_legacy_copy_reviewer_probe_rejects_same_facts_with_different_real_bytes(
    tmp_path: Path,
) -> None:
    client = FakePrivateS3()
    storage = _adapter(tmp_path, client)
    expected = b"expected-private-bytes"
    changed = b"x" * len(expected)
    digest = hashlib.sha256(expected).hexdigest()
    key = "objects/ff/ffffffffffffffffffffffffffffffff.jpg"
    _seed_object(
        client,
        key=key,
        payload=changed,
        checksum=digest,
        etag='"same-valid-looking-etag"',
    )

    with pytest.raises(ImageStorageError, match="different immutable content"):
        storage.copy_verified_object(
            key=key,
            source=io.BytesIO(expected),
            byte_size=len(expected),
            sha256=digest,
            content_type="image/jpeg",
        )

    body = client.get_bodies[0]
    observed = b"".join(body.observed_chunks)
    assert observed == changed
    assert hashlib.sha256(observed).hexdigest() != digest
    assert body.closed is True
    assert client.put_calls == []
    assert client.delete_calls == []
    assert client.objects[key]["payload"] == changed


def test_legacy_copy_rejects_forged_metadata_even_when_real_bytes_match(
    tmp_path: Path,
) -> None:
    client = FakePrivateS3()
    storage = _adapter(tmp_path, client)
    payload = b"real bytes with forged metadata"
    digest = hashlib.sha256(payload).hexdigest()
    key = "objects/ab/abababababababababababababababab.jpg"
    _seed_object(client, key=key, payload=payload, checksum="0" * 64)

    with pytest.raises(ImageStorageError, match="different immutable content"):
        storage.copy_verified_object(
            key=key,
            source=io.BytesIO(payload),
            byte_size=len(payload),
            sha256=digest,
            content_type="image/jpeg",
        )

    observed = b"".join(client.get_bodies[0].observed_chunks)
    assert hashlib.sha256(observed).hexdigest() == digest
    assert client.get_bodies[0].closed is True
    assert client.put_calls == []
    assert client.delete_calls == []


def test_legacy_copy_rejects_interrupted_existing_object_stream(
    tmp_path: Path,
) -> None:
    client = FakePrivateS3()
    storage = _adapter(tmp_path, client)
    payload = b"s" * (STREAM_CHUNK_BYTES + 5)
    digest = hashlib.sha256(payload).hexdigest()
    key = "objects/ac/acacacacacacacacacacacacacacacac.jpg"
    _seed_object(client, key=key, payload=payload, checksum=digest)
    client.fail_stream_on_read = 2

    with pytest.raises(ImageStorageError, match="retried safely"):
        storage.copy_verified_object(
            key=key,
            source=io.BytesIO(payload),
            byte_size=len(payload),
            sha256=digest,
            content_type="image/jpeg",
        )

    assert client.get_bodies[0].read_calls == 2
    assert client.get_bodies[0].closed is True
    assert client.put_calls == []
    assert client.delete_calls == []


def test_legacy_copy_rejects_actual_body_byte_count_mismatch(
    tmp_path: Path,
) -> None:
    client = FakePrivateS3()
    storage = _adapter(tmp_path, client)
    payload = b"expected complete private body"
    digest = hashlib.sha256(payload).hexdigest()
    key = "objects/ad/adadadadadadadadadadadadadadadad.jpg"
    _seed_object(client, key=key, payload=payload, checksum=digest)
    client.get_payload_override = payload[:-1]

    with pytest.raises(ImageStorageError, match="different immutable content"):
        storage.copy_verified_object(
            key=key,
            source=io.BytesIO(payload),
            byte_size=len(payload),
            sha256=digest,
            content_type="image/jpeg",
        )

    assert b"".join(client.get_bodies[0].observed_chunks) == payload[:-1]
    assert client.get_bodies[0].closed is True
    assert client.put_calls == []
    assert client.delete_calls == []
