"""Private local-filesystem ImageAsset storage adapter.

This adapter is deliberately marked NOT_FOR_PRODUCTION_OBJECT_STORAGE. It provides
the provider-neutral operations needed by Phase 1E-1 without selecting a cloud
object-storage provider.
"""

import errno
import hashlib
import os
import re
import stat
import uuid
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import BinaryIO, Protocol

from fastapi import UploadFile

STORAGE_KEY_PATTERN = re.compile(
    r"^objects/(?P<prefix>[0-9a-f]{2})/(?P<identifier>[0-9a-f]{32})"
    r"\.(?P<extension>jpg|png|webp)$"
)
FORMAT_EXTENSIONS = {"jpeg": "jpg", "png": "png", "webp": "webp"}
STREAM_CHUNK_BYTES = 64 * 1024


class ImageStorageError(RuntimeError):
    """A storage operation failed without exposing a local path."""


class ImageUploadTooLargeError(ImageStorageError):
    """The streamed file exceeded the configured maximum."""


class UnsafeStorageKeyError(ImageStorageError):
    """A caller supplied a key outside the controlled object-key grammar."""


class StorageObjectAlreadyExistsError(ImageStorageError):
    """An atomic publish found an existing immutable destination."""


class StorageCompensationRefusedError(ImageStorageError):
    """Receipt, object identity, or database references made deletion unsafe."""


@dataclass(frozen=True, slots=True)
class StagedUpload:
    """One exact temporary object created by this request."""

    path: Path
    byte_size: int
    sha256: str


@dataclass(frozen=True, slots=True)
class StoragePublishReceipt:
    """Proof that one call created one exact private immutable object."""

    key: str
    byte_size: int
    expected_sha256: str
    filesystem_device: int
    inode: int
    link_count: int
    created_by_this_call: bool = True


class ImageStoragePort(Protocol):
    """Provider-neutral image-storage operations required by the service."""

    async def stage_upload(self, upload: UploadFile, *, max_bytes: int) -> StagedUpload: ...

    def put_from_temp(
        self,
        staged: StagedUpload,
        *,
        detected_format: str,
    ) -> StoragePublishReceipt: ...

    def open_private(self, key: str) -> BinaryIO: ...

    def stat(self, key: str) -> os.stat_result: ...

    def exists(self, key: str) -> bool: ...

    def delete_uncommitted(
        self,
        receipt: StoragePublishReceipt,
        *,
        referenced_keys: set[str],
    ) -> None: ...

    def delete_staged(self, staged: StagedUpload) -> None: ...

    def safe_cleanup_orphan(self, key: str, *, referenced_keys: set[str]) -> bool: ...

    def scan_orphans(self, *, referenced_keys: set[str]) -> tuple[str, ...]: ...


class LocalFilesystemImageStorageAdapter:
    """Private development/test adapter; NOT_FOR_PRODUCTION_OBJECT_STORAGE."""

    provider_name = "local_filesystem"

    def __init__(self, root: Path) -> None:
        raw_root = root.expanduser()
        if raw_root.exists() and raw_root.is_symlink():
            raise ImageStorageError("The configured storage root cannot be a symlink.")
        raw_root.mkdir(mode=0o700, parents=True, exist_ok=True)
        self._root = raw_root.resolve(strict=True)
        self._staging_root = self._root / "staging"
        self._objects_root = self._root / "objects"
        for directory in (self._staging_root, self._objects_root):
            directory.mkdir(mode=0o700, exist_ok=True)
            if directory.is_symlink() or directory.resolve(strict=True).parent != self._root:
                raise ImageStorageError("A controlled storage directory is unsafe.")
            directory.chmod(0o700)

    @property
    def root(self) -> Path:
        """Expose the configured root for diagnostics/tests, never through the API."""
        return self._root

    def _assert_within(self, path: Path, parent: Path) -> None:
        try:
            path.relative_to(parent)
        except ValueError as error:
            raise ImageStorageError("A storage operation escaped its configured root.") from error

    def _object_path(self, key: str, *, must_exist: bool) -> Path:
        if (
            "\\" in key
            or PurePosixPath(key).is_absolute()
            or ".." in PurePosixPath(key).parts
            or STORAGE_KEY_PATTERN.fullmatch(key) is None
        ):
            raise UnsafeStorageKeyError("The storage key is invalid.")
        candidate = self._root.joinpath(*PurePosixPath(key).parts)
        resolved_parent = candidate.parent.resolve(strict=True)
        self._assert_within(resolved_parent, self._objects_root)
        if resolved_parent.is_symlink():
            raise ImageStorageError("The object directory is unsafe.")
        if must_exist:
            resolved = candidate.resolve(strict=True)
            self._assert_within(resolved, self._objects_root)
            if candidate.is_symlink():
                raise ImageStorageError("Symlink-backed objects are not readable.")
            return resolved
        return candidate

    def _fsync_directory(self, directory: Path) -> None:
        flags = os.O_RDONLY
        if hasattr(os, "O_DIRECTORY"):
            flags |= os.O_DIRECTORY
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(directory, flags)
        try:
            metadata = os.fstat(descriptor)
            if not stat.S_ISDIR(metadata.st_mode):
                raise ImageStorageError("A controlled storage directory is unsafe.")
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    def _regular_file_identity(self, path: Path) -> tuple[os.stat_result, str]:
        flags = os.O_RDONLY
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(path, flags)
        try:
            metadata = os.fstat(descriptor)
            if not stat.S_ISREG(metadata.st_mode):
                raise ImageStorageError("A storage object is not a regular file.")
            digest = hashlib.sha256()
            while chunk := os.read(descriptor, STREAM_CHUNK_BYTES):
                digest.update(chunk)
            return metadata, digest.hexdigest()
        finally:
            os.close(descriptor)

    def _new_object_identifier(self) -> str:
        """Return a random object identifier; isolated for deterministic collision tests."""
        return uuid.uuid4().hex

    async def stage_upload(self, upload: UploadFile, *, max_bytes: int) -> StagedUpload:
        """Stream one upload into a private, request-owned temporary object."""
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
        """Atomically publish without replacing any existing immutable destination."""
        extension = FORMAT_EXTENSIONS.get(detected_format)
        if extension is None:
            raise ImageStorageError("The validated image format has no controlled extension.")
        resolved_staged = staged.path.resolve(strict=True)
        self._assert_within(resolved_staged, self._staging_root)
        if staged.path.is_symlink() or not stat.S_ISREG(resolved_staged.stat().st_mode):
            raise ImageStorageError("The staged object is unsafe.")
        staged_metadata, staged_sha256 = self._regular_file_identity(resolved_staged)
        if staged_metadata.st_size != staged.byte_size or staged_sha256 != staged.sha256:
            raise ImageStorageError("The staged object identity changed before publish.")

        identifier = self._new_object_identifier()
        key = f"objects/{identifier[:2]}/{identifier}.{extension}"
        destination = self._root / key
        destination.parent.mkdir(mode=0o700, exist_ok=True)
        if destination.parent.is_symlink():
            raise ImageStorageError("The object directory is unsafe.")
        destination.parent.chmod(0o700)
        safe_destination = self._object_path(key, must_exist=False)
        try:
            os.link(
                resolved_staged,
                safe_destination,
                follow_symlinks=False,
            )
        except OSError as error:
            if error.errno == errno.EEXIST:
                raise StorageObjectAlreadyExistsError(
                    "The immutable storage destination already exists."
                ) from error
            raise ImageStorageError("Atomic no-replace storage publish is unavailable.") from error

        published_metadata = safe_destination.stat(follow_symlinks=False)
        if (
            not stat.S_ISREG(published_metadata.st_mode)
            or published_metadata.st_dev != staged_metadata.st_dev
            or published_metadata.st_ino != staged_metadata.st_ino
            or published_metadata.st_size != staged.byte_size
        ):
            raise ImageStorageError("The published object identity could not be proven.")
        self._fsync_directory(safe_destination.parent)
        staged.path.unlink()
        self._fsync_directory(self._staging_root)
        final_metadata = safe_destination.stat(follow_symlinks=False)
        if (
            not stat.S_ISREG(final_metadata.st_mode)
            or final_metadata.st_dev != published_metadata.st_dev
            or final_metadata.st_ino != published_metadata.st_ino
            or final_metadata.st_size != staged.byte_size
            or final_metadata.st_nlink != 1
        ):
            raise ImageStorageError("The published object identity could not be finalized.")
        return StoragePublishReceipt(
            key=key,
            byte_size=staged.byte_size,
            expected_sha256=staged.sha256,
            filesystem_device=final_metadata.st_dev,
            inode=final_metadata.st_ino,
            link_count=final_metadata.st_nlink,
        )

    def open_private(self, key: str) -> BinaryIO:
        """Open one exact private object without following symlinks."""
        path = self._object_path(key, must_exist=True)
        flags = os.O_RDONLY
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(path, flags)
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            os.close(descriptor)
            raise ImageStorageError("The stored object is not a regular file.")
        return os.fdopen(descriptor, "rb", closefd=True)

    def stat(self, key: str) -> os.stat_result:
        """Return metadata for one controlled private object."""
        path = self._object_path(key, must_exist=True)
        metadata = path.stat(follow_symlinks=False)
        if not stat.S_ISREG(metadata.st_mode):
            raise ImageStorageError("The stored object is not a regular file.")
        return metadata

    def exists(self, key: str) -> bool:
        """Return whether one controlled regular object exists."""
        try:
            self.stat(key)
        except (FileNotFoundError, ImageStorageError, OSError):
            return False
        return True

    def delete_uncommitted(
        self,
        receipt: StoragePublishReceipt,
        *,
        referenced_keys: set[str],
    ) -> None:
        """Delete only the still-identical, unreferenced object proven by a receipt."""
        if not receipt.created_by_this_call:
            raise StorageCompensationRefusedError(
                "Storage compensation requires a creation receipt."
            )
        if receipt.key in referenced_keys:
            raise StorageCompensationRefusedError(
                "A database reference prevents storage compensation."
            )
        path = self._object_path(receipt.key, must_exist=True)
        metadata, object_sha256 = self._regular_file_identity(path)
        if (
            metadata.st_dev != receipt.filesystem_device
            or metadata.st_ino != receipt.inode
            or metadata.st_nlink != receipt.link_count
            or metadata.st_size != receipt.byte_size
            or object_sha256 != receipt.expected_sha256
        ):
            raise StorageCompensationRefusedError(
                "The object identity no longer matches its creation receipt."
            )
        final_metadata = path.stat(follow_symlinks=False)
        if (
            not stat.S_ISREG(final_metadata.st_mode)
            or final_metadata.st_dev != receipt.filesystem_device
            or final_metadata.st_ino != receipt.inode
            or final_metadata.st_nlink != receipt.link_count
            or final_metadata.st_size != receipt.byte_size
        ):
            raise StorageCompensationRefusedError(
                "The object identity changed during compensation."
            )
        path.unlink()
        self._fsync_directory(path.parent)

    def delete_staged(self, staged: StagedUpload) -> None:
        """Delete only the exact staging file created by this request."""
        resolved = staged.path.resolve(strict=False)
        self._assert_within(resolved, self._staging_root)
        if staged.path.is_symlink():
            raise ImageStorageError("A staged symlink cannot be cleaned.")
        staged.path.unlink(missing_ok=True)

    def scan_orphans(self, *, referenced_keys: set[str]) -> tuple[str, ...]:
        """Detect unreferenced controlled objects without deleting anything."""
        keys: list[str] = []
        for path in self._objects_root.glob("*/*"):
            if path.is_symlink() or not path.is_file():
                continue
            key = path.relative_to(self._root).as_posix()
            if STORAGE_KEY_PATTERN.fullmatch(key) is not None and key not in referenced_keys:
                keys.append(key)
        return tuple(sorted(keys))

    def safe_cleanup_orphan(self, key: str, *, referenced_keys: set[str]) -> bool:
        """Delete a proven unreferenced controlled key; never guess ownership."""
        if key in referenced_keys:
            return False
        path = self._object_path(key, must_exist=True)
        path.unlink()
        return True
