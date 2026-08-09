"""AES-256-GCM envelope encryption for saved fixture credentials."""

from __future__ import annotations

import hashlib
import hmac
import os
import struct
import uuid
from dataclasses import dataclass
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from creativedeploy_api.core.secret_files import read_secret_bytes_file

DATA_ALGORITHM = "AES-256-GCM"
WRAP_ALGORITHM = "AES-256-GCM"
AAD_VERSION = "credential-aad-v1"
ENCRYPTION_VERSION = "fixture-root-v1"
NONCE_SIZE = 12
TAG_SIZE = 16
DEK_SIZE = 32


class CredentialEncryptionError(ValueError):
    """The credential envelope could not be safely created or opened."""


@dataclass(frozen=True, slots=True, repr=False)
class SecretBytes:
    """A deliberately non-representable request-local secret buffer."""

    value: bytes

    def __repr__(self) -> str:
        return "SecretBytes([REDACTED])"


@dataclass(frozen=True, slots=True)
class CredentialAAD:
    credential_id: uuid.UUID
    owner_user_id: uuid.UUID
    provider_key: str
    encryption_version: str = ENCRYPTION_VERSION


@dataclass(frozen=True, slots=True, repr=False)
class EncryptedCredentialPayload:
    encryption_version: str
    data_algorithm: str
    ciphertext: bytes
    data_nonce: bytes
    data_authentication_tag: bytes
    wrapped_dek: bytes
    wrap_algorithm: str
    wrap_nonce: bytes
    wrap_authentication_tag: bytes
    aad_version: str

    def __repr__(self) -> str:
        return "EncryptedCredentialPayload([REDACTED])"


def _part(value: bytes) -> bytes:
    return struct.pack(">I", len(value)) + value


def _aad(identity: CredentialAAD, *, purpose: str) -> bytes:
    return b"".join(
        (
            _part(b"creativedeploy"),
            _part(AAD_VERSION.encode()),
            _part(purpose.encode()),
            identity.credential_id.bytes,
            identity.owner_user_id.bytes,
            _part(identity.provider_key.encode("utf-8")),
            _part(identity.encryption_version.encode("utf-8")),
        )
    )


class FixtureRootKeyProvider:
    """Development/test-only file provider for an exact 256-bit root key."""

    def __init__(self, root_key: bytes) -> None:
        if len(root_key) != DEK_SIZE:
            raise CredentialEncryptionError("Fixture root key has an invalid length.")
        self._root_key = root_key

    @classmethod
    def from_file(
        cls, path: Path, *, app_env: str, staging_run_id: str | None
    ) -> FixtureRootKeyProvider:
        if app_env not in {"development", "test"} or staging_run_id is not None:
            raise CredentialEncryptionError(
                "The fixture root key provider is unavailable in this environment."
            )
        return cls(
            read_secret_bytes_file(
                path,
                setting_name="CREDENTIAL_FIXTURE_ROOT_KEY",
                exact_size=DEK_SIZE,
            )
        )

    def key(self) -> bytes:
        return self._root_key


class CredentialCipher:
    """Versioned data-encryption and authenticated DEK-wrapping boundary."""

    def __init__(self, key_provider: FixtureRootKeyProvider) -> None:
        self._key_provider = key_provider

    def current_version(self) -> str:
        return ENCRYPTION_VERSION

    def fingerprint(self, plaintext: bytes) -> str:
        digest = hmac.new(
            self._key_provider.key(),
            b"creativedeploy\0credential-fingerprint-v1\0" + plaintext,
            hashlib.sha256,
        ).hexdigest()
        return f"fixture-v1:{digest}"

    def encrypt(self, plaintext: bytes, *, aad: CredentialAAD) -> EncryptedCredentialPayload:
        if not plaintext:
            raise CredentialEncryptionError("Credential value is empty.")
        dek = os.urandom(DEK_SIZE)
        data_nonce = os.urandom(NONCE_SIZE)
        wrap_nonce = os.urandom(NONCE_SIZE)
        if data_nonce == wrap_nonce:
            wrap_nonce = os.urandom(NONCE_SIZE)
        encrypted = AESGCM(dek).encrypt(
            data_nonce, plaintext, _aad(aad, purpose="credential-secret")
        )
        wrapped = AESGCM(self._key_provider.key()).encrypt(
            wrap_nonce,
            dek,
            _aad(aad, purpose="credential-dek"),
        )
        return EncryptedCredentialPayload(
            encryption_version=ENCRYPTION_VERSION,
            data_algorithm=DATA_ALGORITHM,
            ciphertext=encrypted[:-TAG_SIZE],
            data_nonce=data_nonce,
            data_authentication_tag=encrypted[-TAG_SIZE:],
            wrapped_dek=wrapped[:-TAG_SIZE],
            wrap_algorithm=WRAP_ALGORITHM,
            wrap_nonce=wrap_nonce,
            wrap_authentication_tag=wrapped[-TAG_SIZE:],
            aad_version=AAD_VERSION,
        )

    def decrypt(
        self,
        payload: EncryptedCredentialPayload,
        *,
        aad: CredentialAAD,
    ) -> SecretBytes:
        if (
            payload.encryption_version != ENCRYPTION_VERSION
            or payload.data_algorithm != DATA_ALGORITHM
            or payload.wrap_algorithm != WRAP_ALGORITHM
            or payload.aad_version != AAD_VERSION
            or len(payload.data_nonce) != NONCE_SIZE
            or len(payload.data_authentication_tag) != TAG_SIZE
            or len(payload.wrap_nonce) != NONCE_SIZE
            or len(payload.wrap_authentication_tag) != TAG_SIZE
            or not payload.ciphertext
            or not payload.wrapped_dek
        ):
            raise CredentialEncryptionError("Credential envelope metadata is invalid.")
        try:
            dek = AESGCM(self._key_provider.key()).decrypt(
                payload.wrap_nonce,
                payload.wrapped_dek + payload.wrap_authentication_tag,
                _aad(aad, purpose="credential-dek"),
            )
            if len(dek) != DEK_SIZE:
                raise CredentialEncryptionError("Credential DEK has an invalid length.")
            plaintext = AESGCM(dek).decrypt(
                payload.data_nonce,
                payload.ciphertext + payload.data_authentication_tag,
                _aad(aad, purpose="credential-secret"),
            )
        except (InvalidTag, ValueError) as error:
            raise CredentialEncryptionError("Credential envelope authentication failed.") from error
        return SecretBytes(plaintext)
