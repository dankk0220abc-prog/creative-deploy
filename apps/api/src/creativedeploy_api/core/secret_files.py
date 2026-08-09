"""Fail-closed provider-neutral loading for mounted runtime secret files."""

from __future__ import annotations

import os
import stat
from pathlib import Path


class SecretFileError(ValueError):
    """A configured secret file could not be consumed safely."""


def read_secret_bytes_file(
    path: Path,
    *,
    setting_name: str,
    exact_size: int,
) -> bytes:
    """Read an exact-size binary secret with the established file safety checks."""
    candidate = path.expanduser()
    try:
        metadata = candidate.lstat()
    except OSError as error:
        raise SecretFileError(f"{setting_name}_FILE is unavailable.") from error
    mode = stat.S_IMODE(metadata.st_mode)
    if not stat.S_ISREG(metadata.st_mode) or candidate.is_symlink():
        raise SecretFileError(f"{setting_name}_FILE must be a regular non-symlink file.")
    if metadata.st_size != exact_size:
        raise SecretFileError(f"{setting_name}_FILE must contain exactly {exact_size} bytes.")
    if mode & 0o177 or mode & 0o077 or not mode & 0o400:
        raise SecretFileError(f"{setting_name}_FILE must have owner-only read permissions.")
    try:
        descriptor = os.open(candidate, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        try:
            opened = os.fstat(descriptor)
            if (
                not stat.S_ISREG(opened.st_mode)
                or opened.st_dev != metadata.st_dev
                or opened.st_ino != metadata.st_ino
                or stat.S_IMODE(opened.st_mode) != mode
            ):
                raise SecretFileError(f"{setting_name}_FILE identity changed while opening.")
            raw = os.read(descriptor, exact_size + 1)
            final = os.fstat(descriptor)
            if (
                final.st_dev != opened.st_dev
                or final.st_ino != opened.st_ino
                or final.st_size != exact_size
                or stat.S_IMODE(final.st_mode) != mode
            ):
                raise SecretFileError(f"{setting_name}_FILE identity changed while reading.")
        finally:
            os.close(descriptor)
    except SecretFileError:
        raise
    except OSError as error:
        raise SecretFileError(f"{setting_name}_FILE cannot be read.") from error
    if len(raw) != exact_size:
        raise SecretFileError(f"{setting_name}_FILE must contain exactly {exact_size} bytes.")
    return raw


def read_secret_file(path: Path, *, setting_name: str) -> str:
    """Read one small regular, non-writable secret file without leaking its value."""
    candidate = path.expanduser()
    try:
        metadata = candidate.lstat()
    except OSError as error:
        raise SecretFileError(f"{setting_name}_FILE is unavailable.") from error
    mode = stat.S_IMODE(metadata.st_mode)
    if not stat.S_ISREG(metadata.st_mode) or candidate.is_symlink():
        raise SecretFileError(f"{setting_name}_FILE must be a regular non-symlink file.")
    if metadata.st_size < 1 or metadata.st_size > 16_384:
        raise SecretFileError(f"{setting_name}_FILE has an invalid size.")
    if mode & 0o111 or mode & 0o022 or not mode & 0o444:
        raise SecretFileError(f"{setting_name}_FILE has unsafe permissions.")
    try:
        descriptor = os.open(candidate, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        try:
            opened = os.fstat(descriptor)
            if (
                not stat.S_ISREG(opened.st_mode)
                or opened.st_dev != metadata.st_dev
                or opened.st_ino != metadata.st_ino
            ):
                raise SecretFileError(f"{setting_name}_FILE identity changed while opening.")
            raw = os.read(descriptor, 16_385)
        finally:
            os.close(descriptor)
    except SecretFileError:
        raise
    except OSError as error:
        raise SecretFileError(f"{setting_name}_FILE cannot be read.") from error
    if len(raw) > 16_384:
        raise SecretFileError(f"{setting_name}_FILE has an invalid size.")
    try:
        value = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise SecretFileError(f"{setting_name}_FILE must contain UTF-8 text.") from error
    value = value.removesuffix("\r\n").removesuffix("\n")
    if not value or value != value.strip() or "\n" in value or "\r" in value or "\x00" in value:
        raise SecretFileError(f"{setting_name}_FILE must contain one non-blank normalized line.")
    return value
