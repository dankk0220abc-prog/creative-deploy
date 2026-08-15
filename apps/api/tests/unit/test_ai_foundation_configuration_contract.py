"""Focused disabled-live-provider configuration and request-boundary contracts."""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from creativedeploy_api.ai.encryption import (
    CredentialAAD,
    CredentialCipher,
    FixtureRootKeyProvider,
)
from creativedeploy_api.ai.fixture_provider import FixtureProviderAdapter
from creativedeploy_api.api.dependencies import (
    get_ai_foundation_service,
    get_current_principal,
)
from creativedeploy_api.app_factory import create_app
from creativedeploy_api.core.config import Settings
from creativedeploy_api.core.principal import (
    AuthenticationMode,
    PrincipalContext,
    PrincipalType,
)
from creativedeploy_api.schemas.ai_foundation import (
    CredentialCreateRequest,
    CredentialGrantRead,
    CredentialGrantRequest,
    CredentialReplaceRequest,
    InvocationPreviewRequest,
    ProjectPolicyUpdate,
    TemporaryCredentialValidationRequest,
    UserPreferenceUpdate,
)
from creativedeploy_api.services.ai_foundation import (
    AIFoundationService,
    ZhipuCredentialFormatRejectedError,
    _assert_provider_credential_structure,
    _encrypted_payload,
)
from creativedeploy_api.services.zhipu_invocations import WP2_GOVERNED_LEDGER_CAP_FEN

USER_ID = uuid.UUID("3b100000-0000-4000-8000-000000000001")
PROVIDER_ID = uuid.UUID("3b100000-0000-4000-8000-000000000002")
MODEL_ID = uuid.UUID("3b100000-0000-4000-8000-000000000003")
CREDENTIAL_ID = uuid.UUID("3b100000-0000-4000-8000-000000000004")
PROJECT_ID = uuid.UUID("3b100000-0000-4000-8000-000000000005")
CAPABILITY_ID = uuid.UUID("3b100000-0000-4000-8000-000000000006")
STRUCTURED_CAPABILITY_ID = uuid.UUID("3b100000-0000-4000-8000-000000000007")


def test_wp2_governed_ledger_cap_is_one_and_a_half_rmb() -> None:
    assert WP2_GOVERNED_LEDGER_CAP_FEN == 150


def _principal() -> PrincipalContext:
    return PrincipalContext(
        principal_id="phase3b-owner",
        principal_type=PrincipalType.HUMAN,
        display_name="Phase 3B Owner",
        authentication_mode=AuthenticationMode.OIDC_AUTHORIZATION_CODE,
        user_id=USER_ID,
    )


def _non_secret_marker(label: str) -> str:
    return f"explicitly-not-a-provider-key-{label}-{uuid.uuid4().hex}"


def _preference_payload(*, currency: str = "USD") -> dict[str, object]:
    return {
        "enabled": True,
        "default_provider_definition_id": str(PROVIDER_ID),
        "default_model_definition_id": str(MODEL_ID),
        "default_credential_id": str(CREDENTIAL_ID),
        "timeout_ms": 30_000,
        "streaming_enabled": False,
        "cost_warning_minor_units": 100,
        "currency": currency,
        "budget_per_invocation_minor_units": 1_000,
        "budget_cumulative_minor_units": 10_000,
        "budget_window_seconds": 3_600,
        "expected_revision": 0,
    }


def _policy_payload() -> dict[str, object]:
    return {
        "enabled": True,
        "default_provider_definition_id": str(PROVIDER_ID),
        "default_model_definition_id": str(MODEL_ID),
        "default_credential_id": str(CREDENTIAL_ID),
        "provider_allowlist": [str(PROVIDER_ID)],
        "model_allowlist": [str(MODEL_ID)],
        "capability_allowlist": [str(CAPABILITY_ID), str(STRUCTURED_CAPABILITY_ID)],
        "credential_allowlist": [str(CREDENTIAL_ID)],
        "per_invocation_limit_minor_units": 1_000,
        "cumulative_limit_minor_units": 10_000,
        "budget_window_seconds": 3_600,
        "currency": "USD",
        "allow_unknown_cost": False,
        "allow_manual_model_id": False,
        "allow_fallback": False,
        "require_paid_call_confirmation": True,
        "expected_revision": 0,
    }


def test_request_models_parse_json_uuid_strings_and_preserve_fixture_currency_default() -> None:
    grant = CredentialGrantRequest.model_validate(
        {"project_id": str(PROJECT_ID), "expected_credential_revision": 1}
    )
    preference = UserPreferenceUpdate.model_validate(_preference_payload())
    legacy_preference = UserPreferenceUpdate.model_validate(
        {
            key: value
            for key, value in _preference_payload(currency="FIXTURE_CREDITS").items()
            if key != "currency"
        }
    )
    policy = ProjectPolicyUpdate.model_validate(_policy_payload())
    invocation = InvocationPreviewRequest.model_validate(
        {
            "product_space": "paintpilot",
            "project_id": str(PROJECT_ID),
            "invocation_family": "fixture_invocation",
            "provider_definition_id": str(PROVIDER_ID),
            "model_definition_id": str(MODEL_ID),
            "credential_id": str(CREDENTIAL_ID),
            "requested_capabilities": ["text_generation"],
            "artifacts": [
                {
                    "id": str(uuid.uuid4()),
                    "revision": 1,
                    "content_hash": "sha256:" + ("a" * 64),
                    "media_type": "image/png",
                    "byte_length": 8,
                }
            ],
            "payload": {
                "prompt_label": "schema-test",
                "fixture_input": "local",
                "scenario": "success",
            },
            "confirm_fixture_use": True,
        }
    )

    assert grant.project_id == PROJECT_ID
    assert preference.currency == "USD"
    assert legacy_preference.currency == "FIXTURE_CREDITS"
    assert policy.provider_allowlist == [PROVIDER_ID]
    assert invocation.project_id == PROJECT_ID
    assert invocation.artifacts[0].id.version == 4
    assert (
        TemporaryCredentialValidationRequest(
            provider_key="openai", credential=SecretStr(_non_secret_marker("temporary"))
        ).provider_key
        == "openai"
    )


@pytest.mark.parametrize(
    ("request_model", "payload"),
    [
        (
            TemporaryCredentialValidationRequest,
            {"provider_key": "openai", "credential": ""},
        ),
        (
            CredentialCreateRequest,
            {
                "provider_key": "openai",
                "alias": "OpenAI",
                "credential": "x" * 4097,
                "confirm_save": True,
            },
        ),
        (
            CredentialReplaceRequest,
            {
                "alias": "OpenAI",
                "credential": "",
                "expected_revision": 1,
                "confirm_replace": True,
            },
        ),
    ],
)
def test_credential_requests_reject_empty_or_excessive_secrets(
    request_model: type[
        TemporaryCredentialValidationRequest | CredentialCreateRequest | CredentialReplaceRequest
    ],
    payload: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        request_model.model_validate(payload)
    assert (
        CredentialCreateRequest(
            provider_key="openai",
            alias="OpenAI",
            credential=SecretStr(_non_secret_marker("saved")),
            confirm_save=True,
        ).provider_key
        == "openai"
    )


@pytest.mark.parametrize(
    "plaintext",
    [
        b"synthetic zhipu token",
        b"synthetic\tzhipu-token",
        b"synthetic-zhipu-token\r\n",
        b"Bearer synthetic-zhipu-token",
        "synthetic-zhipu-非ascii".encode(),
    ],
)
def test_zhipu_credential_structure_rejects_non_token_bytes_without_echo(
    plaintext: bytes,
) -> None:
    with pytest.raises(ZhipuCredentialFormatRejectedError) as captured:
        _assert_provider_credential_structure("zhipu", plaintext)

    assert plaintext.decode("utf-8", errors="replace") not in repr(captured.value)


def test_zhipu_credential_structure_accepts_whitespace_free_printable_ascii() -> None:
    _assert_provider_credential_structure("zhipu", b"synthetic-zhipu.token_+-~")


class _GrantRouteService:
    async def create_grant(self, **kwargs: Any) -> CredentialGrantRead:
        payload = cast(CredentialGrantRequest, kwargs["payload"])
        assert payload.project_id == PROJECT_ID
        return CredentialGrantRead(
            id=uuid.uuid4(),
            credential_id=cast(uuid.UUID, kwargs["credential_id"]),
            project_id=payload.project_id,
            active=True,
            created_at=datetime.now(UTC),
            revoked_at=None,
            revision=1,
        )


def test_grant_route_accepts_json_uuid_string(tmp_path: Path) -> None:
    key_file = tmp_path / "fixture-root.key"
    key_file.write_bytes(bytes(range(32)))
    key_file.chmod(0o400)
    settings = Settings(
        app_env="test",
        database_url="postgresql+psycopg://test:test@127.0.0.1:1/test",
        phase3a_fixture_enabled=True,
        credential_fixture_root_key_file=key_file,
        _env_file=None,
    )
    app = create_app(settings)
    app.dependency_overrides[get_current_principal] = _principal
    app.dependency_overrides[get_ai_foundation_service] = _GrantRouteService

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(
            f"/api/v1/ai/credentials/{CREDENTIAL_ID}/grants",
            headers={"Idempotency-Key": str(uuid.uuid4())},
            json={"project_id": str(PROJECT_ID), "expected_credential_revision": 1},
        )

    assert response.status_code == 201
    assert response.json()["project_id"] == str(PROJECT_ID)


class _Begin:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, *_args: object) -> None:
        return None


class _Session:
    def begin(self) -> _Begin:
        return _Begin()


def _openai_provider() -> object:
    return type(
        "Provider",
        (),
        {
            "id": PROVIDER_ID,
            "provider_key": "openai",
            "adapter_type": "openai_responses",
            "base_url_policy": "provider_managed",
            "enabled": False,
            "status": "disabled",
        },
    )()


def _fixture_provider() -> object:
    return type(
        "Provider",
        (),
        {
            "id": PROVIDER_ID,
            "provider_key": "fixture_local",
            "adapter_type": "fixture_local",
            "base_url_policy": "not_applicable",
            "enabled": True,
            "status": "active",
        },
    )()


def _zhipu_provider() -> object:
    return type(
        "Provider",
        (),
        {
            "id": PROVIDER_ID,
            "provider_key": "zhipu",
            "adapter_type": "zhipu_chat_completions",
            "base_url_policy": "provider_managed",
            "enabled": True,
            "status": "active",
        },
    )()


def _service(
    monkeypatch: pytest.MonkeyPatch,
    *,
    cipher: object,
    adapter: object,
    repository: object,
) -> AIFoundationService:
    service = AIFoundationService(
        cast(AsyncSession, _Session()),
        cast(CredentialCipher, cipher),
        cast(FixtureProviderAdapter, adapter),
    )
    service._repository = cast(Any, repository)

    async def no_replay(**_kwargs: object) -> None:
        return None

    monkeypatch.setattr(service, "_command_replay", no_replay)
    monkeypatch.setattr(service, "_complete_command", lambda **_kwargs: None)
    monkeypatch.setattr(service, "_audit", lambda **_kwargs: None)
    return service


def test_openai_temporary_validation_blocks_before_secret_access_or_adapter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cipher = Mock(spec=CredentialCipher)
    cipher.fingerprint.side_effect = AssertionError("secret fingerprint must not be read")
    cipher.decrypt.side_effect = AssertionError("credential must not be decrypted")
    adapter = Mock(spec=FixtureProviderAdapter)
    adapter.validate_credential.side_effect = AssertionError("live validation is not authorized")
    repository = type(
        "Repository",
        (),
        {
            "lock_active_user": AsyncMock(return_value=object()),
            "get_provider": AsyncMock(return_value=_openai_provider()),
        },
    )()
    service = _service(monkeypatch, cipher=cipher, adapter=adapter, repository=repository)
    payload = TemporaryCredentialValidationRequest(
        provider_key="openai", credential=SecretStr(_non_secret_marker("must-not-read"))
    )

    def forbid_secret_read(_secret: SecretStr) -> str:
        raise AssertionError("temporary live secret was read")

    monkeypatch.setattr(SecretStr, "get_secret_value", forbid_secret_read)
    response = asyncio.run(
        service.validate_temporary(
            payload=payload,
            principal=_principal(),
            idempotency_key=uuid.uuid4(),
            request_id=uuid.uuid4(),
        )
    )

    assert response.model_dump() == {
        "provider_key": "openai",
        "valid": False,
        "validation_status": "live_validation_not_authorized",
        "message_code": "LIVE_VALIDATION_NOT_AUTHORIZED",
        "fixture": False,
        "local_only": False,
        "persisted": False,
    }
    cipher.fingerprint.assert_not_called()
    cipher.decrypt.assert_not_called()
    adapter.validate_credential.assert_not_called()


def test_openai_saved_validation_blocks_before_decryption_or_adapter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime.now(UTC)
    record = type(
        "Credential",
        (),
        {
            "id": CREDENTIAL_ID,
            "owner_user_id": USER_ID,
            "provider_definition_id": PROVIDER_ID,
            "provider_key": "openai",
            "status": "active",
            "revision": 2,
            "last_validation_status": None,
            "last_successful_validation_at": now,
            "updated_at": now,
        },
    )()
    cipher = Mock(spec=CredentialCipher)
    cipher.decrypt.side_effect = AssertionError("saved live credential was decrypted")
    adapter = Mock(spec=FixtureProviderAdapter)
    adapter.validate_credential.side_effect = AssertionError("live validation is not authorized")
    repository = type(
        "Repository",
        (),
        {
            "lock_active_user": AsyncMock(return_value=object()),
            "get_owned_credential": AsyncMock(return_value=record),
            "get_provider": AsyncMock(return_value=_openai_provider()),
        },
    )()
    service = _service(monkeypatch, cipher=cipher, adapter=adapter, repository=repository)

    response = asyncio.run(
        service.validate_saved(
            credential_id=CREDENTIAL_ID,
            principal=_principal(),
            idempotency_key=uuid.uuid4(),
            request_id=uuid.uuid4(),
        )
    )

    assert response.validation_status == "live_validation_not_authorized"
    assert response.persisted is True
    assert record.last_validation_status == "live_validation_not_authorized"
    assert record.last_successful_validation_at is None
    assert record.revision == 3
    cipher.decrypt.assert_not_called()
    adapter.validate_credential.assert_not_called()


def test_disabled_openai_policy_resolves_to_live_authorization_required(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    policy = type(
        "Policy",
        (),
        {
            "id": uuid.uuid4(),
            "project_id": PROJECT_ID,
            "enabled": True,
            "default_provider_definition_id": PROVIDER_ID,
            "default_model_definition_id": MODEL_ID,
            "default_credential_id": CREDENTIAL_ID,
            "per_invocation_limit_minor_units": 1_000,
            "currency": "USD",
            "allow_unknown_cost": False,
            "allow_manual_model_id": False,
            "allow_fallback": False,
            "require_paid_call_confirmation": True,
            "revision": 1,
        },
    )()
    model = type(
        "Model",
        (),
        {
            "id": MODEL_ID,
            "provider_definition_id": PROVIDER_ID,
            "provider_key": "openai",
            "status": "disabled",
        },
    )()
    credential = type(
        "Credential",
        (),
        {
            "id": CREDENTIAL_ID,
            "provider_definition_id": PROVIDER_ID,
            "provider_key": "openai",
            "status": "active",
        },
    )()
    budget = type(
        "Budget",
        (),
        {"enabled": True, "cumulative_limit_minor_units": 10_000, "window_seconds": 3_600},
    )()
    repository = type(
        "Repository",
        (),
        {
            "get_project_policy": AsyncMock(return_value=policy),
            "get_project_budget_policy": AsyncMock(return_value=budget),
            "policy_allowlists": AsyncMock(
                return_value=(
                    [PROVIDER_ID],
                    [MODEL_ID],
                    [CAPABILITY_ID, STRUCTURED_CAPABILITY_ID],
                    [CREDENTIAL_ID],
                )
            ),
            "active_grant_credential_ids": AsyncMock(return_value=[CREDENTIAL_ID]),
            "get_provider_by_id": AsyncMock(return_value=_openai_provider()),
            "get_model": AsyncMock(return_value=model),
            "get_credential_by_id": AsyncMock(return_value=credential),
            "capability_ids_for_keys": AsyncMock(
                return_value=[CAPABILITY_ID, STRUCTURED_CAPABILITY_ID]
            ),
            "model_capability_keys": AsyncMock(
                return_value=["structured_output", "vision_understanding"]
            ),
        },
    )()
    service = _service(
        monkeypatch,
        cipher=Mock(spec=CredentialCipher),
        adapter=Mock(spec=FixtureProviderAdapter),
        repository=repository,
    )

    response = asyncio.run(service._project_policy_read(PROJECT_ID))

    assert response.currency == "USD"
    assert response.resolved_status == "live_authorization_required"
    repository.get_project_budget_policy.assert_awaited_once_with(PROJECT_ID, currency="USD")


def test_live_saved_selection_readiness_checks_every_offline_gate_without_secret_access(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime.now(UTC)
    model = type(
        "Model",
        (),
        {
            "id": MODEL_ID,
            "provider_definition_id": PROVIDER_ID,
            "provider_key": "openai",
            "status": "disabled",
        },
    )()
    credential = type(
        "Credential",
        (),
        {
            "id": CREDENTIAL_ID,
            "provider_definition_id": PROVIDER_ID,
            "provider_key": "openai",
            "status": "active",
            "last_validation_status": "provider_valid",
            "last_successful_validation_at": now,
        },
    )()
    preference = type(
        "Preference",
        (),
        {"enabled": True, "streaming_enabled": False},
    )()
    policy = type(
        "Policy",
        (),
        {
            "id": uuid.uuid4(),
            "enabled": True,
            "currency": "USD",
            "allow_unknown_cost": False,
            "allow_manual_model_id": False,
            "allow_fallback": False,
            "require_paid_call_confirmation": True,
            "per_invocation_limit_minor_units": 1_000,
        },
    )()
    budget = type(
        "Budget",
        (),
        {
            "enabled": True,
            "currency": "USD",
            "allow_unknown_cost": False,
            "per_invocation_limit_minor_units": 1_000,
            "cumulative_limit_minor_units": 10_000,
            "window_seconds": 3_600,
        },
    )()
    counter = type(
        "Counter",
        (),
        {
            "window_start": now,
            "window_end": now + timedelta(seconds=3_600),
            "limit_minor_units": 10_000,
            "committed_minor_units": 100,
            "reserved_minor_units": 50,
        },
    )()
    repository = type(
        "Repository",
        (),
        {
            "lock_active_user": AsyncMock(return_value=object()),
            "get_provider_by_id": AsyncMock(return_value=_openai_provider()),
            "get_model": AsyncMock(return_value=model),
            "get_owned_credential": AsyncMock(return_value=credential),
            "get_active_grant": AsyncMock(return_value=object()),
            "get_preference": AsyncMock(return_value=preference),
            "get_project_policy": AsyncMock(return_value=policy),
            "get_user_budget_policy": AsyncMock(return_value=budget),
            "get_project_budget_policy": AsyncMock(return_value=budget),
            "get_user_counter": AsyncMock(return_value=counter),
            "get_project_counter": AsyncMock(return_value=counter),
            "capability_ids_for_keys": AsyncMock(
                return_value=[CAPABILITY_ID, STRUCTURED_CAPABILITY_ID]
            ),
            "model_capability_keys": AsyncMock(
                return_value=["structured_output", "vision_understanding"]
            ),
            "policy_allowlists": AsyncMock(
                return_value=(
                    [PROVIDER_ID],
                    [MODEL_ID],
                    [CAPABILITY_ID, STRUCTURED_CAPABILITY_ID],
                    [CREDENTIAL_ID],
                )
            ),
        },
    )()
    cipher = Mock(spec=CredentialCipher)
    adapter = Mock(spec=FixtureProviderAdapter)
    service = _service(
        monkeypatch,
        cipher=cipher,
        adapter=adapter,
        repository=repository,
    )

    blockers = asyncio.run(
        service.live_saved_selection_blockers(
            user_id=USER_ID,
            project_id=PROJECT_ID,
            provider_definition_id=PROVIDER_ID,
            model_definition_id=MODEL_ID,
            credential_id=CREDENTIAL_ID,
            required_capability_keys=["vision_understanding", "structured_output"],
            estimate_minor_units=250,
        )
    )

    assert blockers == []
    cipher.decrypt.assert_not_called()
    adapter.invoke.assert_not_called()

    repository.get_active_grant.return_value = None
    credential.last_validation_status = "live_validation_not_authorized"
    credential.last_successful_validation_at = None
    repository.get_project_budget_policy.return_value = None
    repository.policy_allowlists.return_value = (
        [PROVIDER_ID],
        [MODEL_ID],
        [CAPABILITY_ID],
        [CREDENTIAL_ID],
    )
    blocked = asyncio.run(
        service.live_saved_selection_blockers(
            user_id=USER_ID,
            project_id=PROJECT_ID,
            provider_definition_id=PROVIDER_ID,
            model_definition_id=MODEL_ID,
            credential_id=CREDENTIAL_ID,
            required_capability_keys=["vision_understanding", "structured_output"],
            estimate_minor_units=250,
        )
    )

    assert "credential_grant_missing" in blocked
    assert "credential_live_validation_required" in blocked
    assert "project_budget_not_configured" in blocked
    assert "capability_not_allowlisted" in blocked


def test_user_preference_persists_consistent_openai_usd_budget_and_counter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model = type(
        "Model",
        (),
        {
            "id": MODEL_ID,
            "provider_definition_id": PROVIDER_ID,
            "provider_key": "openai",
            "status": "disabled",
        },
    )()
    credential = type(
        "Credential",
        (),
        {
            "id": CREDENTIAL_ID,
            "provider_definition_id": PROVIDER_ID,
            "provider_key": "openai",
            "status": "active",
        },
    )()
    stored: dict[str, object] = {}
    budget_currency_calls: list[str] = []
    counter_currency_calls: list[str] = []

    def add(record: object) -> None:
        stored[type(record).__name__] = record

    async def get_preference(*_args: object, **_kwargs: object) -> object | None:
        return stored.get("UserProviderPreference")

    async def get_budget(
        _repository: object,
        _user_id: uuid.UUID,
        *,
        currency: str,
        **_kwargs: object,
    ) -> object | None:
        budget_currency_calls.append(currency)
        return stored.get("UserBudgetPolicy")

    async def get_counter(
        _repository: object,
        _user_id: uuid.UUID,
        _now: datetime,
        *,
        currency: str,
        **_kwargs: object,
    ) -> None:
        counter_currency_calls.append(currency)
        return None

    repository = type(
        "Repository",
        (),
        {
            "lock_active_user": AsyncMock(return_value=object()),
            "get_provider_by_id": AsyncMock(return_value=_openai_provider()),
            "get_model": AsyncMock(return_value=model),
            "get_owned_credential": AsyncMock(return_value=credential),
            "get_preference": get_preference,
            "get_user_budget_policy": get_budget,
            "get_user_counter": get_counter,
            "add": Mock(side_effect=add),
            "flush": AsyncMock(return_value=None),
        },
    )()
    service = _service(
        monkeypatch,
        cipher=Mock(spec=CredentialCipher),
        adapter=Mock(spec=FixtureProviderAdapter),
        repository=repository,
    )

    response = asyncio.run(
        service.update_user_preference(
            payload=UserPreferenceUpdate.model_validate(_preference_payload()),
            principal=_principal(),
            idempotency_key=uuid.uuid4(),
            request_id=uuid.uuid4(),
        )
    )

    assert response.currency == "USD"
    assert response.enabled is True
    assert cast(Any, stored["UserBudgetPolicy"]).currency == "USD"
    assert cast(Any, stored["UserBudgetCounter"]).currency == "USD"
    assert budget_currency_calls == ["USD", "USD"]
    assert counter_currency_calls == ["USD"]


def test_invocation_read_projects_typed_provider_request_id_without_metadata_inference(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime.now(UTC)
    invocation_id = uuid.uuid4()
    attempt = type(
        "Attempt",
        (),
        {
            "id": uuid.uuid4(),
            "attempt_number": 1,
            "provider_key": "fixture_local",
            "model_id": "fixture-model-v1",
            "status": "succeeded",
            "dispatched_at": now,
            "terminal_at": now,
            "final_error_category": None,
            "provider_request_id_status": "provided",
            "provider_request_id": "fixture-request-001",
            "safe_provider_metadata": {},
        },
    )()
    invocation = type(
        "Invocation",
        (),
        {
            "id": invocation_id,
            "product_space": "paintpilot",
            "project_id": None,
            "invocation_family": "fixture_invocation",
            "canonical_request_payload_hash": "sha256:" + ("b" * 64),
            "status": "succeeded",
            "final_attempt_id": attempt.id,
            "final_error_category": None,
            "output_reference": {"fixture": True},
            "created_at": now,
            "updated_at": now,
        },
    )()
    repository = type(
        "Repository",
        (),
        {"list_attempts": AsyncMock(return_value=[attempt])},
    )()
    service = _service(
        monkeypatch,
        cipher=Mock(spec=CredentialCipher),
        adapter=Mock(spec=FixtureProviderAdapter),
        repository=repository,
    )

    response = asyncio.run(service._invocation_read(invocation))

    assert response.attempts[0].provider_request_id_status == "provided"
    assert response.attempts[0].provider_request_id == "fixture-request-001"
    assert response.attempts[0].safe_provider_metadata == {}


def test_openai_credential_create_encrypts_without_live_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cipher = CredentialCipher(FixtureRootKeyProvider(bytes(range(32))))
    secret = _non_secret_marker("create") + " internal space\t\r\n"
    adapter = Mock(spec=FixtureProviderAdapter)
    adapter.validate_credential.side_effect = AssertionError("live validation is not authorized")
    repository = type(
        "Repository",
        (),
        {
            "lock_active_user": AsyncMock(return_value=object()),
            "get_provider": AsyncMock(return_value=_openai_provider()),
            "add": Mock(),
            "flush": AsyncMock(return_value=None),
        },
    )()
    service = _service(monkeypatch, cipher=cipher, adapter=adapter, repository=repository)

    response = asyncio.run(
        service.create_credential(
            payload=CredentialCreateRequest(
                provider_key="openai",
                alias="OpenAI key",
                credential=SecretStr(secret),
                confirm_save=True,
            ),
            principal=_principal(),
            idempotency_key=uuid.uuid4(),
            request_id=uuid.uuid4(),
        )
    )

    stored = repository.add.call_args.args[0]
    assert not hasattr(stored, "last_four")
    assert stored.ciphertext is not None
    assert cipher.decrypt(
        _encrypted_payload(stored),
        aad=CredentialAAD(
            credential_id=stored.id,
            owner_user_id=stored.owner_user_id,
            provider_key=stored.provider_key,
            encryption_version=stored.encryption_version,
        ),
    ).value == secret.encode("utf-8")
    assert stored.last_validation_status == "live_validation_not_authorized"
    assert stored.last_successful_validation_at is None
    assert response.provider_key == "openai"
    assert response.last_validation_status == "live_validation_not_authorized"
    assert "last_four" not in response.model_dump(mode="json")
    assert secret not in response.model_dump_json()
    adapter.validate_credential.assert_not_called()


def test_zhipu_credential_create_rejects_whitespace_before_encryption(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cipher = Mock(spec=CredentialCipher)
    repository = Mock()
    service = _service(
        monkeypatch,
        cipher=cipher,
        adapter=Mock(spec=FixtureProviderAdapter),
        repository=repository,
    )

    with pytest.raises(ZhipuCredentialFormatRejectedError):
        asyncio.run(
            service.create_credential(
                payload=CredentialCreateRequest(
                    provider_key="zhipu",
                    alias="Malformed synthetic Zhipu key",
                    credential=SecretStr("synthetic zhipu token"),
                    confirm_save=True,
                ),
                principal=_principal(),
                idempotency_key=uuid.uuid4(),
                request_id=uuid.uuid4(),
            )
        )

    cipher.fingerprint.assert_not_called()
    cipher.encrypt.assert_not_called()


def test_fixture_credential_create_keeps_local_validation_semantics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cipher = CredentialCipher(FixtureRootKeyProvider(bytes(range(32))))
    repository = type(
        "Repository",
        (),
        {
            "lock_active_user": AsyncMock(return_value=object()),
            "get_provider": AsyncMock(return_value=_fixture_provider()),
            "add": Mock(),
            "flush": AsyncMock(return_value=None),
        },
    )()
    service = _service(
        monkeypatch,
        cipher=cipher,
        adapter=FixtureProviderAdapter(),
        repository=repository,
    )

    response = asyncio.run(
        service.create_credential(
            payload=CredentialCreateRequest(
                provider_key="fixture_local",
                alias="Fixture key",
                credential=SecretStr("fixture-sk-0123456789abcdef"),
                confirm_save=True,
            ),
            principal=_principal(),
            idempotency_key=uuid.uuid4(),
            request_id=uuid.uuid4(),
        )
    )

    stored = repository.add.call_args.args[0]
    assert stored.last_validation_status == "fixture_valid"
    assert stored.last_successful_validation_at is not None
    assert response.provider_key == "fixture_local"
    assert response.last_validation_status == "fixture_valid"


def test_openai_credential_replace_encrypts_without_live_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    old = type(
        "Credential",
        (),
        {
            "id": CREDENTIAL_ID,
            "owner_user_id": USER_ID,
            "provider_definition_id": PROVIDER_ID,
            "provider_key": "openai",
            "status": "active",
            "revision": 4,
        },
    )()
    cipher = CredentialCipher(FixtureRootKeyProvider(bytes(range(32))))
    secret = _non_secret_marker("replace") + " internal space\t\r\n"
    adapter = Mock(spec=FixtureProviderAdapter)
    adapter.validate_credential.side_effect = AssertionError("live validation is not authorized")
    repository = type(
        "Repository",
        (),
        {
            "lock_active_user": AsyncMock(return_value=object()),
            "get_owned_credential": AsyncMock(return_value=old),
            "get_provider": AsyncMock(return_value=_openai_provider()),
            "lock_credential_grants": AsyncMock(return_value=[]),
            "add": Mock(),
            "flush": AsyncMock(return_value=None),
        },
    )()
    service = _service(monkeypatch, cipher=cipher, adapter=adapter, repository=repository)

    response = asyncio.run(
        service.replace_credential(
            credential_id=CREDENTIAL_ID,
            payload=CredentialReplaceRequest(
                alias="Replacement OpenAI key",
                credential=SecretStr(secret),
                expected_revision=4,
                confirm_replace=True,
            ),
            principal=_principal(),
            idempotency_key=uuid.uuid4(),
            request_id=uuid.uuid4(),
        )
    )

    replacement = repository.add.call_args.args[0]
    assert not hasattr(replacement, "last_four")
    assert replacement.ciphertext is not None
    assert cipher.decrypt(
        _encrypted_payload(replacement),
        aad=CredentialAAD(
            credential_id=replacement.id,
            owner_user_id=replacement.owner_user_id,
            provider_key=replacement.provider_key,
            encryption_version=replacement.encryption_version,
        ),
    ).value == secret.encode("utf-8")
    assert replacement.replaces_credential_id == CREDENTIAL_ID
    assert replacement.last_validation_status == "live_validation_not_authorized"
    assert replacement.last_successful_validation_at is None
    assert old.status == "replaced"
    assert response.last_validation_status == "live_validation_not_authorized"
    assert "last_four" not in response.model_dump(mode="json")
    assert secret not in response.model_dump_json()
    adapter.validate_credential.assert_not_called()


def test_zhipu_credential_replace_rejects_whitespace_before_encryption(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    old = type(
        "Credential",
        (),
        {
            "id": CREDENTIAL_ID,
            "owner_user_id": USER_ID,
            "provider_definition_id": PROVIDER_ID,
            "provider_key": "zhipu",
            "status": "active",
            "revision": 4,
        },
    )()
    cipher = Mock(spec=CredentialCipher)
    cipher.fingerprint.return_value = "fixture-v1:synthetic-non-secret-fingerprint"
    repository = type(
        "Repository",
        (),
        {
            "lock_active_user": AsyncMock(return_value=object()),
            "get_owned_credential": AsyncMock(return_value=old),
            "get_provider": AsyncMock(return_value=_zhipu_provider()),
            "add": Mock(),
        },
    )()
    service = _service(
        monkeypatch,
        cipher=cipher,
        adapter=Mock(spec=FixtureProviderAdapter),
        repository=repository,
    )

    with pytest.raises(ZhipuCredentialFormatRejectedError):
        asyncio.run(
            service.replace_credential(
                credential_id=CREDENTIAL_ID,
                payload=CredentialReplaceRequest(
                    alias="Malformed synthetic replacement",
                    credential=SecretStr("synthetic\tzhipu-token"),
                    expected_revision=4,
                    confirm_replace=True,
                ),
                principal=_principal(),
                idempotency_key=uuid.uuid4(),
                request_id=uuid.uuid4(),
            )
        )

    cipher.encrypt.assert_not_called()
    repository.add.assert_not_called()
