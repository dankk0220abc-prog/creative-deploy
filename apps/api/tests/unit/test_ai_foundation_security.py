"""Focused Phase 3A fixture crypto, canonicalization, and no-network tests."""

import os
import socket
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from creativedeploy_api.ai.canonicalization import (
    CanonicalizationError,
    canonical_timestamp,
    canonicalize_and_hash,
    fixed_decimal,
)
from creativedeploy_api.ai.encryption import (
    CredentialAAD,
    CredentialCipher,
    CredentialEncryptionError,
    EncryptedCredentialPayload,
    FixtureRootKeyProvider,
    SecretBytes,
)
from creativedeploy_api.ai.fixture_provider import FixtureProviderAdapter
from creativedeploy_api.core.config import Settings
from creativedeploy_api.core.secret_files import SecretFileError, read_secret_bytes_file


def _cipher(byte: int = 7) -> CredentialCipher:
    return CredentialCipher(FixtureRootKeyProvider(bytes([byte]) * 32))


def _aad() -> CredentialAAD:
    return CredentialAAD(
        credential_id=uuid.UUID("3a100000-0000-4000-8000-000000000001"),
        owner_user_id=uuid.UUID("3a100000-0000-4000-8000-000000000002"),
        provider_key="fixture_local",
    )


def test_envelope_round_trip_uses_independent_nonce_and_redacted_reprs() -> None:
    cipher = _cipher()
    plaintext = b"fixture-sk-0123456789abcdef"
    first = cipher.encrypt(plaintext, aad=_aad())
    second = cipher.encrypt(plaintext, aad=_aad())

    assert first.data_nonce != first.wrap_nonce
    assert first.data_nonce != second.data_nonce
    assert first.wrapped_dek != second.wrapped_dek
    assert cipher.decrypt(first, aad=_aad()).value == plaintext
    assert plaintext.decode() not in repr(first)
    assert plaintext.decode() not in repr(SecretBytes(plaintext))
    assert cipher.fingerprint(plaintext).startswith("fixture-v1:")


@pytest.mark.parametrize(
    "field",
    [
        "ciphertext",
        "data_nonce",
        "data_authentication_tag",
        "wrapped_dek",
        "wrap_nonce",
        "wrap_authentication_tag",
    ],
)
def test_envelope_tampering_fails_authenticated_decryption(field: str) -> None:
    cipher = _cipher()
    encrypted = cipher.encrypt(b"fixture-sk-0123456789abcdef", aad=_aad())
    values = {
        name: getattr(encrypted, name) for name in EncryptedCredentialPayload.__dataclass_fields__
    }
    original = values[field]
    assert isinstance(original, bytes)
    values[field] = bytes([original[0] ^ 1]) + original[1:]

    with pytest.raises(CredentialEncryptionError, match=r"authentication failed|metadata"):
        cipher.decrypt(EncryptedCredentialPayload(**values), aad=_aad())


def test_envelope_identity_and_root_key_swaps_fail() -> None:
    encrypted = _cipher().encrypt(b"fixture-sk-0123456789abcdef", aad=_aad())
    swapped_aad = CredentialAAD(
        credential_id=uuid.uuid4(),
        owner_user_id=_aad().owner_user_id,
        provider_key="fixture_local",
    )
    with pytest.raises(CredentialEncryptionError):
        _cipher().decrypt(encrypted, aad=swapped_aad)
    with pytest.raises(CredentialEncryptionError):
        _cipher(8).decrypt(encrypted, aad=_aad())


def test_binary_root_key_file_is_exact_owner_only_and_non_symlink(tmp_path: Path) -> None:
    key_file = tmp_path / "root.key"
    key_file.write_bytes(os.urandom(32))
    key_file.chmod(0o600)
    assert (
        read_secret_bytes_file(key_file, setting_name="CREDENTIAL_FIXTURE_ROOT_KEY", exact_size=32)
        == key_file.read_bytes()
    )

    key_file.chmod(0o640)
    with pytest.raises(SecretFileError, match="owner-only"):
        read_secret_bytes_file(key_file, setting_name="CREDENTIAL_FIXTURE_ROOT_KEY", exact_size=32)
    key_file.chmod(0o600)
    symlink = tmp_path / "linked.key"
    symlink.symlink_to(key_file)
    with pytest.raises(SecretFileError, match="non-symlink"):
        read_secret_bytes_file(symlink, setting_name="CREDENTIAL_FIXTURE_ROOT_KEY", exact_size=32)


def test_fixture_root_key_provider_rejects_staging_and_production(tmp_path: Path) -> None:
    key_file = tmp_path / "root.key"
    key_file.write_bytes(os.urandom(32))
    key_file.chmod(0o400)
    with pytest.raises(CredentialEncryptionError, match="unavailable"):
        FixtureRootKeyProvider.from_file(key_file, app_env="production", staging_run_id=None)
    with pytest.raises(CredentialEncryptionError, match="unavailable"):
        FixtureRootKeyProvider.from_file(key_file, app_env="test", staging_run_id="staging-proof")


def test_settings_flag_defaults_off_without_reading_a_root_key() -> None:
    settings = Settings(
        app_env="test",
        database_url="postgresql+psycopg://user:pass@localhost/database",
        _env_file=None,
    )
    assert settings.phase3a_fixture_enabled is False
    assert settings.phase3b_paint_plan_enabled is False
    assert settings.credential_fixture_root_key_file is None


def test_settings_rejects_enabled_fixture_without_key_or_in_production(
    tmp_path: Path,
) -> None:
    key_file = tmp_path / "root.key"
    key_file.write_bytes(os.urandom(32))
    key_file.chmod(0o400)
    with pytest.raises(ValueError, match="CREDENTIAL_FIXTURE_ROOT_KEY_FILE"):
        Settings(
            app_env="test",
            database_url="postgresql+psycopg://user:pass@localhost/database",
            phase3a_fixture_enabled=True,
            _env_file=None,
        )
    with pytest.raises(ValueError, match="development or test"):
        Settings(
            app_env="production",
            database_url="postgresql+psycopg://user:pass@localhost/database",
            identity_provider="oidc",
            image_storage_provider="s3",
            secure_cookies=True,
            require_csrf_origin=True,
            public_origin="https://localhost",
            phase3a_fixture_enabled=True,
            credential_fixture_root_key_file=key_file,
            _env_file=None,
        )


def test_settings_phase3b_gate_requires_offline_fixture_and_rejects_staging(
    tmp_path: Path,
) -> None:
    key_file = tmp_path / "root.key"
    key_file.write_bytes(os.urandom(32))
    key_file.chmod(0o400)
    common = {
        "app_env": "test",
        "database_url": "postgresql+psycopg://user:pass@localhost/database",
        "_env_file": None,
    }
    with pytest.raises(ValueError, match="requires the offline Phase 3A fixture gate"):
        Settings(**common, phase3b_paint_plan_enabled=True)
    with pytest.raises(ValueError, match="forbidden in staging-style runs"):
        Settings(
            **common,
            phase3a_fixture_enabled=True,
            phase3b_paint_plan_enabled=True,
            credential_fixture_root_key_file=key_file,
            staging_run_id="staging-proof",
        )

    settings = Settings(
        **common,
        phase3a_fixture_enabled=True,
        phase3b_paint_plan_enabled=True,
        credential_fixture_root_key_file=key_file,
    )
    assert settings.phase3b_paint_plan_enabled is True


def test_canonicalization_normalizes_unicode_time_decimal_and_key_order() -> None:
    first, first_hash = canonicalize_and_hash({"z": "e\u0301", "a": [3, True]})
    second, second_hash = canonicalize_and_hash({"a": [3, True], "z": "é"})
    assert first == second == '{"a":[3,true],"z":"é"}'.encode()
    assert first_hash == second_hash
    assert (
        canonical_timestamp(datetime(2026, 8, 5, 8, 30, tzinfo=UTC) + timedelta(hours=8))
        == "2026-08-05T16:30:00.000000Z"
    )
    assert fixed_decimal(Decimal("12.3400"), scale=4) == "12.3400"
    with pytest.raises(CanonicalizationError, match="floating-point"):
        canonicalize_and_hash({"unsafe": 0.1})


def test_fixture_adapter_succeeds_when_socket_construction_is_forbidden(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbid_socket(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("fixture adapter attempted network construction")

    monkeypatch.setattr(socket, "socket", forbid_socket)
    adapter = FixtureProviderAdapter()
    secret = SecretBytes(b"fixture-sk-0123456789abcdef")
    result = adapter.invoke(
        {"prompt_label": "unit", "fixture_input": "local", "scenario": "success"},
        secret,
    )
    assert result.output["fixture"] is True
    assert result.output["local_only"] is True
    assert result.currency == "FIXTURE_CREDITS"
