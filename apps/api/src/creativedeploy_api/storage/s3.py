"""Private S3-compatible ImageAsset storage without public or signed URLs."""

import base64
import hashlib
import io
import json
import os
import stat
import uuid
from pathlib import Path, PurePosixPath
from typing import Any, BinaryIO

import boto3  # type: ignore[import-untyped]
from botocore.client import Config  # type: ignore[import-untyped]
from botocore.exceptions import BotoCoreError, ClientError  # type: ignore[import-untyped]
from fastapi import UploadFile

from creativedeploy_api.storage.images import (
    FORMAT_EXTENSIONS,
    STORAGE_KEY_PATTERN,
    STREAM_CHUNK_BYTES,
    ImageStorageError,
    ImageUploadTooLargeError,
    StagedUpload,
    StorageCompensationRefusedError,
    StorageObjectAlreadyExistsError,
    StoragePublishReceipt,
    UnsafeStorageKeyError,
)


class S3ObjectStat:
    """Minimal stat-compatible metadata used by the provider-neutral service."""

    def __init__(self, *, byte_size: int) -> None:
        self.st_size = byte_size


class S3ImageStorageAdapter:
    """Server-only private S3 adapter; it never produces a browser-facing URL."""

    provider_name = "s3"

    def __init__(
        self,
        *,
        endpoint_url: str,
        region: str,
        bucket: str,
        access_key_id: str,
        secret_access_key: str,
        force_path_style: bool,
        staging_root: Path,
        create_bucket: bool,
        client: Any | None = None,
    ) -> None:
        self._bucket = bucket
        self._client = client or boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            region_name=region,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            config=Config(
                signature_version="s3v4",
                s3={"addressing_style": "path" if force_path_style else "virtual"},
                retries={"max_attempts": 3, "mode": "standard"},
            ),
        )
        raw_staging = staging_root.expanduser()
        if raw_staging.exists() and raw_staging.is_symlink():
            raise ImageStorageError("The S3 staging root cannot be a symlink.")
        raw_staging.mkdir(mode=0o700, parents=True, exist_ok=True)
        self._staging_root = raw_staging.resolve(strict=True)
        self._staging_root.chmod(0o700)
        self._ensure_bucket(create_bucket=create_bucket, region=region)
        self._assert_bucket_private()

    def _ensure_bucket(self, *, create_bucket: bool, region: str) -> None:
        try:
            self._client.head_bucket(Bucket=self._bucket)
            return
        except ClientError as error:
            code = str(error.response.get("Error", {}).get("Code", ""))
            if not create_bucket or code not in {"404", "NoSuchBucket", "NotFound"}:
                raise ImageStorageError("The configured private bucket is unavailable.") from error
        try:
            arguments: dict[str, object] = {"Bucket": self._bucket}
            if region != "us-east-1":
                arguments["CreateBucketConfiguration"] = {"LocationConstraint": region}
            self._client.create_bucket(**arguments)
            self._client.put_bucket_acl(Bucket=self._bucket, ACL="private")
        except (BotoCoreError, ClientError) as error:
            raise ImageStorageError("The private bucket could not be initialized.") from error

    def _assert_bucket_private(self) -> None:
        """Fail closed on group ACLs or any bucket policy."""
        try:
            acl = self._client.get_bucket_acl(Bucket=self._bucket)
            grants = acl.get("Grants", [])
            if not isinstance(grants, list):
                raise ImageStorageError("The bucket ACL response is invalid.")
            for grant in grants:
                if not isinstance(grant, dict):
                    raise ImageStorageError("The bucket ACL response is invalid.")
                grantee = grant.get("Grantee")
                if not isinstance(grantee, dict) or grantee.get("Type") != "CanonicalUser":
                    raise ImageStorageError("The configured S3 bucket is not private.")
            try:
                policy_response = self._client.get_bucket_policy(Bucket=self._bucket)
            except ClientError as error:
                code = str(error.response.get("Error", {}).get("Code", ""))
                if code not in {"NoSuchBucketPolicy", "NoSuchPolicy", "404"}:
                    raise
            else:
                policy = policy_response.get("Policy")
                if isinstance(policy, str) and json.loads(policy).get("Statement"):
                    raise ImageStorageError(
                        "Bucket policies are refused; use private credential policy only."
                    )
        except ImageStorageError:
            raise
        except (BotoCoreError, ClientError, ValueError, TypeError) as error:
            raise ImageStorageError("The private bucket policy could not be verified.") from error

    @staticmethod
    def _validate_key(key: str) -> str:
        if (
            "\\" in key
            or PurePosixPath(key).is_absolute()
            or ".." in PurePosixPath(key).parts
            or STORAGE_KEY_PATTERN.fullmatch(key) is None
        ):
            raise UnsafeStorageKeyError("The storage key is invalid.")
        return key

    async def stage_upload(self, upload: UploadFile, *, max_bytes: int) -> StagedUpload:
        staging_path = self._staging_root / f"{uuid.uuid4().hex}.tmp"
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(staging_path, flags, 0o600)
        total = 0
        digest = hashlib.sha256()
        try:
            with os.fdopen(descriptor, "wb", closefd=True) as stream:
                while True:
                    chunk = await upload.read(STREAM_CHUNK_BYTES)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > max_bytes:
                        raise ImageUploadTooLargeError("The upload exceeded the allowed size.")
                    digest.update(chunk)
                    stream.write(chunk)
                stream.flush()
                os.fsync(stream.fileno())
        except BaseException:
            staging_path.unlink(missing_ok=True)
            raise
        if total == 0:
            staging_path.unlink(missing_ok=True)
            raise ImageStorageError("The upload was empty.")
        return StagedUpload(path=staging_path, byte_size=total, sha256=digest.hexdigest())

    def put_from_temp(
        self,
        staged: StagedUpload,
        *,
        detected_format: str,
    ) -> StoragePublishReceipt:
        extension = FORMAT_EXTENSIONS.get(detected_format)
        if extension is None:
            raise ImageStorageError("The validated image format has no controlled extension.")
        resolved = staged.path.resolve(strict=True)
        try:
            resolved.relative_to(self._staging_root)
        except ValueError as error:
            raise ImageStorageError("The staged object escaped its configured root.") from error
        metadata = resolved.stat(follow_symlinks=False)
        if (
            staged.path.is_symlink()
            or not stat.S_ISREG(metadata.st_mode)
            or metadata.st_size != staged.byte_size
        ):
            raise ImageStorageError("The staged object identity changed before publish.")
        identifier = uuid.uuid4().hex
        key = self._validate_key(f"objects/{identifier[:2]}/{identifier}.{extension}")
        checksum_b64 = base64.b64encode(bytes.fromhex(staged.sha256)).decode("ascii")
        content_type = {
            "jpeg": "image/jpeg",
            "png": "image/png",
            "webp": "image/webp",
        }[detected_format]
        try:
            with resolved.open("rb") as source:
                response = self._client.put_object(
                    Bucket=self._bucket,
                    Key=key,
                    Body=source,
                    ContentLength=staged.byte_size,
                    ContentType=content_type,
                    ChecksumSHA256=checksum_b64,
                    Metadata={"sha256": staged.sha256},
                    IfNoneMatch="*",
                )
        except ClientError as error:
            code = str(error.response.get("Error", {}).get("Code", ""))
            status_code = error.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
            if code in {"PreconditionFailed", "ConditionalRequestConflict"} or status_code == 412:
                raise StorageObjectAlreadyExistsError(
                    "The immutable storage destination already exists."
                ) from error
            raise ImageStorageError("The private S3 object could not be published.") from error
        except (BotoCoreError, OSError) as error:
            raise ImageStorageError("The private S3 object could not be published.") from error
        head = self._head(key)
        if (
            int(head.get("ContentLength", -1)) != staged.byte_size
            or head.get("Metadata", {}).get("sha256") != staged.sha256
        ):
            raise ImageStorageError("The published S3 object identity could not be proven.")
        staged.path.unlink()
        return StoragePublishReceipt(
            key=key,
            byte_size=staged.byte_size,
            expected_sha256=staged.sha256,
            provider_name=self.provider_name,
            etag=str(response.get("ETag", "")).strip('"') or None,
            version_id=(
                response.get("VersionId") if isinstance(response.get("VersionId"), str) else None
            ),
        )

    def copy_verified_object(
        self,
        *,
        key: str,
        source: BinaryIO,
        byte_size: int,
        sha256: str,
        content_type: str,
    ) -> StoragePublishReceipt:
        """Idempotently copy one verified legacy object without exposing or deleting it."""
        self._validate_key(key)
        try:
            existing = self._client.head_object(Bucket=self._bucket, Key=key)
        except ClientError as error:
            code = str(error.response.get("Error", {}).get("Code", ""))
            status_code = error.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
            if code in {"404", "NoSuchKey", "NotFound"} or status_code == 404:
                existing = None
            else:
                raise ImageStorageError("The target S3 key could not be checked safely.") from error
        except BotoCoreError as error:
            raise ImageStorageError("The target S3 key could not be checked safely.") from error
        if existing is not None:
            if not self._copy_identity_matches(
                existing,
                byte_size=byte_size,
                sha256=sha256,
                content_type=content_type,
            ):
                raise StorageObjectAlreadyExistsError(
                    "The target key exists with different immutable content."
                )
            return StoragePublishReceipt(
                key=key,
                byte_size=byte_size,
                expected_sha256=sha256,
                provider_name=self.provider_name,
                etag=str(existing.get("ETag", "")).strip('"') or None,
                version_id=(
                    existing.get("VersionId")
                    if isinstance(existing.get("VersionId"), str)
                    else None
                ),
                created_by_this_call=False,
            )
        checksum_b64 = base64.b64encode(bytes.fromhex(sha256)).decode("ascii")
        try:
            response = self._client.put_object(
                Bucket=self._bucket,
                Key=key,
                Body=source,
                ContentLength=byte_size,
                ContentType=content_type,
                ChecksumSHA256=checksum_b64,
                Metadata={"sha256": sha256},
                IfNoneMatch="*",
            )
        except ClientError as error:
            code = str(error.response.get("Error", {}).get("Code", ""))
            status_code = error.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
            if code in {"PreconditionFailed", "ConditionalRequestConflict"} or status_code == 412:
                raise StorageObjectAlreadyExistsError(
                    "The target key changed during migration."
                ) from error
            raise ImageStorageError("The legacy object could not be copied to S3.") from error
        except BotoCoreError as error:
            raise ImageStorageError("The legacy object could not be copied to S3.") from error
        try:
            verified = self._head(key)
        except ImageStorageError as error:
            raise ImageStorageError(
                "The copied S3 object could not be verified; migration can be retried safely."
            ) from error
        if not self._copy_identity_matches(
            verified,
            byte_size=byte_size,
            sha256=sha256,
            content_type=content_type,
        ):
            raise ImageStorageError(
                "The copied S3 object failed integrity verification; the database was not updated."
            )
        return StoragePublishReceipt(
            key=key,
            byte_size=byte_size,
            expected_sha256=sha256,
            provider_name=self.provider_name,
            etag=str(verified.get("ETag", "")).strip('"') or None,
            version_id=(
                verified.get("VersionId")
                if isinstance(verified.get("VersionId"), str)
                else (
                    response.get("VersionId")
                    if isinstance(response.get("VersionId"), str)
                    else None
                )
            ),
        )

    @staticmethod
    def _copy_identity_matches(
        response: object,
        *,
        byte_size: int,
        sha256: str,
        content_type: str,
    ) -> bool:
        """Match only governed destination facts; an ETag is never a checksum."""
        if not isinstance(response, dict):
            return False
        size = response.get("ContentLength")
        metadata = response.get("Metadata")
        return (
            isinstance(size, int)
            and not isinstance(size, bool)
            and size == byte_size
            and isinstance(metadata, dict)
            and metadata.get("sha256") == sha256
            and response.get("ContentType") == content_type
        )

    def _head(self, key: str) -> dict[str, Any]:
        self._validate_key(key)
        try:
            response = self._client.head_object(Bucket=self._bucket, Key=key)
        except (BotoCoreError, ClientError) as error:
            raise ImageStorageError("The private S3 object is unavailable.") from error
        if not isinstance(response, dict):
            raise ImageStorageError("The private S3 metadata response is invalid.")
        return response

    def stat(self, key: str) -> S3ObjectStat:
        response = self._head(key)
        size = response.get("ContentLength")
        if not isinstance(size, int) or size < 0:
            raise ImageStorageError("The private S3 object size is invalid.")
        return S3ObjectStat(byte_size=size)

    def open_private(self, key: str) -> BinaryIO:
        self._validate_key(key)
        try:
            response = self._client.get_object(Bucket=self._bucket, Key=key)
            body = response["Body"]
            stream = io.BytesIO()
            try:
                while chunk := body.read(STREAM_CHUNK_BYTES):
                    stream.write(chunk)
            finally:
                body.close()
            stream.seek(0)
            return stream
        except (BotoCoreError, ClientError, KeyError, OSError) as error:
            raise ImageStorageError("The private S3 object could not be streamed.") from error

    def exists(self, key: str) -> bool:
        try:
            self._head(key)
        except ImageStorageError:
            return False
        return True

    def delete_uncommitted(
        self,
        receipt: StoragePublishReceipt,
        *,
        referenced_keys: set[str],
    ) -> None:
        if (
            not receipt.created_by_this_call
            or receipt.provider_name != self.provider_name
            or receipt.key in referenced_keys
        ):
            raise StorageCompensationRefusedError(
                "S3 compensation requires an unreferenced creation receipt."
            )
        head = self._head(receipt.key)
        etag = str(head.get("ETag", "")).strip('"') or None
        if (
            int(head.get("ContentLength", -1)) != receipt.byte_size
            or head.get("Metadata", {}).get("sha256") != receipt.expected_sha256
            or (receipt.etag is not None and etag != receipt.etag)
        ):
            raise StorageCompensationRefusedError(
                "The S3 object no longer matches its creation receipt."
            )
        arguments: dict[str, object] = {"Bucket": self._bucket, "Key": receipt.key}
        if receipt.version_id is not None:
            arguments["VersionId"] = receipt.version_id
        try:
            self._client.delete_object(**arguments)
        except (BotoCoreError, ClientError) as error:
            raise ImageStorageError("The exact uncommitted S3 object was not removed.") from error

    def delete_staged(self, staged: StagedUpload) -> None:
        resolved = staged.path.resolve(strict=False)
        try:
            resolved.relative_to(self._staging_root)
        except ValueError as error:
            raise ImageStorageError("The staged object escaped its configured root.") from error
        if staged.path.is_symlink():
            raise ImageStorageError("A staged symlink cannot be cleaned.")
        staged.path.unlink(missing_ok=True)

    def scan_orphans(self, *, referenced_keys: set[str]) -> tuple[str, ...]:
        keys: list[str] = []
        continuation: str | None = None
        try:
            while True:
                arguments: dict[str, object] = {
                    "Bucket": self._bucket,
                    "Prefix": "objects/",
                }
                if continuation is not None:
                    arguments["ContinuationToken"] = continuation
                response = self._client.list_objects_v2(**arguments)
                for item in response.get("Contents", []):
                    key = item.get("Key")
                    if (
                        isinstance(key, str)
                        and STORAGE_KEY_PATTERN.fullmatch(key)
                        and key not in referenced_keys
                    ):
                        keys.append(key)
                if not response.get("IsTruncated"):
                    break
                continuation_value = response.get("NextContinuationToken")
                if not isinstance(continuation_value, str):
                    raise ImageStorageError("S3 orphan scan pagination is invalid.")
                continuation = continuation_value
        except (BotoCoreError, ClientError) as error:
            raise ImageStorageError("The private S3 orphan scan failed.") from error
        return tuple(sorted(keys))

    def safe_cleanup_orphan(self, key: str, *, referenced_keys: set[str]) -> bool:
        """Manual exact cleanup only; no retention or automatic deletion policy."""
        self._validate_key(key)
        if key in referenced_keys:
            return False
        try:
            self._client.delete_object(Bucket=self._bucket, Key=key)
        except (BotoCoreError, ClientError) as error:
            raise ImageStorageError("The exact orphan could not be removed.") from error
        return True
