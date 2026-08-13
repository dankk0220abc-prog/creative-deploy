"""Offline-only exact contract tests for the governed Zhipu adapter."""

import asyncio
import hashlib
import json
import uuid
from types import SimpleNamespace

import httpx
import pytest

from creativedeploy_api.ai.encryption import SecretBytes
from creativedeploy_api.ai.provider_transport import (
    MAX_SAFE_PROVIDER_ERROR_MESSAGE_CHARS,
    GovernedMultimodalPrompt,
    NormalizedProviderUsage,
    PreparedImageAttachment,
    ProviderContractError,
    ProviderWireResponse,
)
from creativedeploy_api.ai.zhipu_provider import (
    ZHIPU_API_ORIGIN,
    ZHIPU_ARCANA_MAX_OUTPUT_TOKENS,
    ZHIPU_ARCANA_REASONING_EFFORT,
    ZHIPU_CHAT_COMPLETIONS_PATH,
    ZHIPU_GLM_5V_TURBO_MODEL,
    ZHIPU_GLM_52_MODEL,
    ZHIPU_TEXT_ADAPTER_VERSION,
    ZHIPU_VISION_ADAPTER_VERSION,
    ZhipuChatAdapter,
    ZhipuHTTPTransport,
    ZhipuLiveExecutionBlockedError,
)
from creativedeploy_api.services.zhipu_invocations import (
    ZhipuUsageReconciliationService,
    _provider_diagnostic_metadata,
)


def _prompt() -> GovernedMultimodalPrompt:
    return GovernedMultimodalPrompt(
        system_prompt="Use only the governed local context.",
        user_intent="Keep the result concise.",
        structured_context={
            "retrieved_context": {
                "source_id": "paint-preparation-v1",
                "chunk_id": "surface-preparation",
            }
        },
        generation_locale="en-US",
    )


def _schema() -> dict[str, object]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {"schema_version": {"type": "string"}},
        "required": ["schema_version"],
    }


def _image() -> PreparedImageAttachment:
    content = b"bounded-governed-private-image"
    return PreparedImageAttachment(
        image_asset_id="00000000-0000-4000-8000-000000000001",
        role="primary_front",
        sha256=hashlib.sha256(content).hexdigest(),
        media_type="image/png",
        width=320,
        height=240,
        content=content,
    )


def test_text_request_uses_exact_model_endpoint_and_native_json_mode() -> None:
    request = ZhipuChatAdapter(ZHIPU_GLM_52_MODEL).prepare_request(
        prompt=_prompt(),
        images=[],
        response_schema=_schema(),
        max_output_tokens=800,
    )

    assert request.endpoint.url == f"{ZHIPU_API_ORIGIN}{ZHIPU_CHAT_COMPLETIONS_PATH}"
    assert request.model_id == ZHIPU_GLM_52_MODEL
    assert request.adapter_version == ZHIPU_TEXT_ADAPTER_VERSION == "zhipu-chat-arcana-v3"
    assert request.body["model"] == ZHIPU_GLM_52_MODEL
    assert request.body["stream"] is False
    assert request.body["response_format"] == {"type": "json_object"}
    assert request.body["thinking"] == {"type": "enabled"}
    assert request.body["reasoning_effort"] == ZHIPU_ARCANA_REASONING_EFFORT
    assert request.body["do_sample"] is False
    assert "temperature" not in request.body
    assert "top_p" not in request.body
    assert "bounded-governed-private-image" not in repr(request)
    assert "body=[REDACTED]" in repr(request)


def test_vision_request_uses_transient_data_uri_without_unsupported_json_mode() -> None:
    request = ZhipuChatAdapter(ZHIPU_GLM_5V_TURBO_MODEL).prepare_request(
        prompt=_prompt(),
        images=[_image()],
        response_schema=_schema(),
        max_output_tokens=1_200,
    )

    assert request.model_id == ZHIPU_GLM_5V_TURBO_MODEL
    assert request.adapter_version == ZHIPU_VISION_ADAPTER_VERSION == ("zhipu-chat-paint-plan-v2")
    assert "response_format" not in request.body
    assert request.body["thinking"] == {"type": "enabled"}
    assert request.body["do_sample"] is False
    assert "reasoning_effort" not in request.body
    assert "temperature" not in request.body
    assert "top_p" not in request.body
    messages = request.body["messages"]
    assert isinstance(messages, list)
    content = messages[1]["content"]
    assert content[1]["image_url"]["url"].startswith("data:image/png;base64,")
    assert request.cancellation_mode == "local_wait_only_after_dispatch"


def test_normalization_requires_exact_model_stop_json_and_measured_usage() -> None:
    result = ZhipuChatAdapter(ZHIPU_GLM_52_MODEL).normalize_response(
        ProviderWireResponse(
            status_code=200,
            body={
                "id": "zhipu-safe-request-id",
                "model": ZHIPU_GLM_52_MODEL,
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"content": '{"schema_version":"tarot-reading.v2"}'},
                    }
                ],
                "usage": {"prompt_tokens": 100, "completion_tokens": 50},
            },
            provider_request_id=None,
        )
    )

    assert dict(result.output) == {"schema_version": "tarot-reading.v2"}
    assert result.usage.input_units == 100
    assert result.usage.output_units == 50
    assert result.usage.reasoning_tokens is None
    assert result.provider_request_id == "zhipu-safe-request-id"
    assert result.finish_reason == "stop"
    assert result.json_parse_status == "parsed"
    assert result.output_content_bytes == 37


@pytest.mark.parametrize(
    ("body_update", "category"),
    [
        ({"model": ZHIPU_GLM_5V_TURBO_MODEL}, "schema_invalid"),
        (
            {"choices": [{"finish_reason": "length", "message": {"content": "{}"}}]},
            "schema_invalid",
        ),
        (
            {"choices": [{"finish_reason": "stop", "message": {"content": "not-json"}}]},
            "schema_invalid",
        ),
    ],
)
def test_normalization_rejects_model_finish_or_json_drift(
    body_update: dict[str, object], category: str
) -> None:
    body: dict[str, object] = {
        "model": ZHIPU_GLM_52_MODEL,
        "choices": [{"finish_reason": "stop", "message": {"content": "{}"}}],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1},
    }
    body.update(body_update)
    with pytest.raises(ProviderContractError) as error:
        ZhipuChatAdapter(ZHIPU_GLM_52_MODEL).normalize_response(
            ProviderWireResponse(status_code=200, body=body, provider_request_id=None)
        )
    assert error.value.category == category
    assert error.value.dispatch_certainty == "dispatched"


def test_output_limit_finish_reason_is_confirmed_without_persisting_raw_content() -> None:
    raw_content = '{"schema_version":"tarot-reading.v2"'
    with pytest.raises(ProviderContractError) as captured:
        ZhipuChatAdapter(ZHIPU_GLM_52_MODEL).normalize_response(
            ProviderWireResponse(
                status_code=200,
                body={
                    "model": ZHIPU_GLM_52_MODEL,
                    "choices": [{"finish_reason": "length", "message": {"content": raw_content}}],
                    "usage": {
                        "prompt_tokens": 2_419,
                        "completion_tokens": 3_500,
                        "completion_tokens_details": {"reasoning_tokens": 1_250},
                    },
                },
                provider_request_id="safe-length-id",
            )
        )

    error = captured.value
    metadata = _provider_diagnostic_metadata(error)
    assert error.category == "schema_invalid"
    assert metadata["finish_reason"] == "length"
    assert metadata["structured_failure_category"] == "OUTPUT_LIMIT_REACHED_OR_CONFIRMED_TRUNCATION"
    assert metadata["json_parse_status"] == "not_attempted"
    assert metadata["reasoning_tokens"] == 1_250
    assert metadata["output_content_characters"] == len(raw_content)
    assert raw_content not in repr(metadata)


def test_truncated_json_without_finish_metadata_is_not_confirmed_as_output_limit() -> None:
    with pytest.raises(ProviderContractError) as captured:
        ZhipuChatAdapter(ZHIPU_GLM_52_MODEL).normalize_response(
            ProviderWireResponse(
                status_code=200,
                body={
                    "model": ZHIPU_GLM_52_MODEL,
                    "choices": [{"message": {"content": '{"incomplete":'}}],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 20},
                },
                provider_request_id=None,
            )
        )

    metadata = _provider_diagnostic_metadata(captured.value)
    assert metadata["structured_failure_category"] == "UNKNOWN_STRUCTURED_OUTPUT_FAILURE"
    assert metadata["json_parse_status"] == "not_attempted"
    assert metadata.get("finish_reason") is None


def test_stop_with_invalid_json_is_json_parse_failed() -> None:
    with pytest.raises(ProviderContractError) as captured:
        ZhipuChatAdapter(ZHIPU_GLM_52_MODEL).normalize_response(
            ProviderWireResponse(
                status_code=200,
                body={
                    "model": ZHIPU_GLM_52_MODEL,
                    "choices": [{"finish_reason": "stop", "message": {"content": "not-json"}}],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 20},
                },
                provider_request_id=None,
            )
        )

    metadata = _provider_diagnostic_metadata(captured.value)
    assert metadata["finish_reason"] == "stop"
    assert metadata["json_parse_status"] == "failed"
    assert metadata["structured_failure_category"] == "JSON_PARSE_FAILED"


def test_stop_with_root_array_is_schema_failure_with_value_free_shape_metadata() -> None:
    raw_value = "private generated value must not persist"
    content = json.dumps([{"title": raw_value}])
    with pytest.raises(ProviderContractError) as captured:
        ZhipuChatAdapter(ZHIPU_GLM_5V_TURBO_MODEL).normalize_response(
            ProviderWireResponse(
                status_code=200,
                body={
                    "model": ZHIPU_GLM_5V_TURBO_MODEL,
                    "choices": [{"finish_reason": "stop", "message": {"content": content}}],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 20},
                },
                provider_request_id="safe-root-array-id",
            )
        )

    metadata = _provider_diagnostic_metadata(captured.value)
    assert metadata["finish_reason"] == "stop"
    assert metadata["json_parse_status"] == "parsed"
    assert metadata["structured_failure_category"] == "SCHEMA_VALIDATION_FAILED"
    assert metadata["structured_error_path"] == "$"
    assert metadata["structured_expected_root_json_type"] == "object"
    assert metadata["structured_received_root_json_type"] == "array<object>"
    assert metadata["structured_expected_json_type"] == "object"
    assert metadata["structured_received_json_type"] == "array<object>"
    assert metadata["structured_received_item_count"] == 1
    assert "OUTPUT_LIMIT" not in repr(metadata)
    assert raw_value not in repr(metadata)


def test_realistic_json_larger_than_old_output_envelope_parses() -> None:
    large_value = "bounded reflective content " * 700
    content = json.dumps({"schema_version": "tarot-reading.v2", "summary": large_value})
    assert len(content) > 14_000

    result = ZhipuChatAdapter(ZHIPU_GLM_52_MODEL).normalize_response(
        ProviderWireResponse(
            status_code=200,
            body={
                "model": ZHIPU_GLM_52_MODEL,
                "choices": [{"finish_reason": "stop", "message": {"content": content}}],
                "usage": {
                    "prompt_tokens": 2_000,
                    "completion_tokens": 4_500,
                    "completion_tokens_details": {"reasoning_tokens": 0},
                },
            },
            provider_request_id=None,
        )
    )

    assert result.output["summary"] == large_value
    assert result.usage.reasoning_tokens == 0
    assert result.output_content_bytes == len(content.encode())


def test_reasoning_content_is_never_copied_into_safe_metadata() -> None:
    reasoning_content = "private chain of thought must never persist"
    result = ZhipuChatAdapter(ZHIPU_GLM_52_MODEL).normalize_response(
        ProviderWireResponse(
            status_code=200,
            body={
                "model": ZHIPU_GLM_52_MODEL,
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"content": "{}", "reasoning_content": reasoning_content},
                    }
                ],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            },
            provider_request_id=None,
        )
    )

    assert reasoning_content not in repr(result)


def test_structured_shape_metadata_is_allowlisted_and_contains_no_output_values() -> None:
    marker = "private-output-value-must-not-persist"
    error = ProviderContractError(
        "schema_invalid",
        structured_expected_root_json_type="object",
        structured_received_root_json_type="object",
        structured_expected_json_type="array<string>",
        structured_received_json_type="array<object>",
        structured_received_item_count=1,
        structured_received_object_keys=("headline", marker),
        structured_missing_required_keys=("summary", marker),
        structured_unexpected_object_keys=("result", marker),
        structured_validator_error_category="string_type",
    )

    metadata = _provider_diagnostic_metadata(error)

    assert metadata["structured_expected_json_type"] == "array<string>"
    assert metadata["structured_received_json_type"] == "array<object>"
    assert metadata["structured_expected_root_json_type"] == "object"
    assert metadata["structured_received_root_json_type"] == "object"
    assert metadata["structured_received_item_count"] == 1
    assert metadata["structured_received_object_keys"] == ["headline"]
    assert metadata["structured_missing_required_keys"] == ["summary"]
    assert metadata["structured_unexpected_object_keys"] == ["result"]
    assert metadata["structured_validator_error_category"] == "string_type"
    assert marker not in repr(metadata)


def test_arcana_request_uses_exact_recomputed_output_ceiling() -> None:
    adapter = ZhipuChatAdapter(ZHIPU_GLM_52_MODEL)
    request = adapter.prepare_request(
        prompt=_prompt(),
        images=[],
        response_schema=_schema(),
        max_output_tokens=ZHIPU_ARCANA_MAX_OUTPUT_TOKENS,
    )
    estimate = adapter.estimate_cost(
        prompt=_prompt(),
        images=[],
        response_schema=_schema(),
        max_output_tokens=ZHIPU_ARCANA_MAX_OUTPUT_TOKENS,
    )
    old_ceiling_estimate = adapter.estimate_cost(
        prompt=_prompt(),
        images=[],
        response_schema=_schema(),
        max_output_tokens=3_500,
    )

    assert request.body["max_tokens"] == 8_192
    assert estimate == 27
    assert old_ceiling_estimate == 14


def test_measured_usage_reconciliation_settles_without_rewriting_terminal_evidence() -> None:
    invocation_id = uuid.uuid4()
    attempt_id = uuid.uuid4()
    user_id = uuid.uuid4()
    provider_id = uuid.uuid4()
    model_id = uuid.uuid4()
    credential_id = uuid.uuid4()
    pricing_id = uuid.uuid4()
    invocation = SimpleNamespace(
        id=invocation_id,
        requesting_user_id=user_id,
        status="failed",
        final_error_category="schema_invalid",
        budget_snapshot={"pricing_snapshot_id": str(pricing_id)},
        product_space="arcana",
        project_id=None,
        request_id=uuid.uuid4(),
    )
    attempt = SimpleNamespace(
        id=attempt_id,
        invocation_id=invocation_id,
        status="failed",
        final_error_category="schema_invalid",
        provider_key="zhipu",
        model_id=ZHIPU_GLM_52_MODEL,
        provider_definition_id=provider_id,
        model_definition_id=model_id,
        credential_id=credential_id,
    )
    reservation = SimpleNamespace(
        invocation_id=invocation_id,
        user_counter_id=uuid.uuid4(),
        project_counter_id=None,
        currency="CNY",
        reserved_amount=21,
        state="reconciliation_required",
        settled_at=None,
        revision=1,
    )
    usage = SimpleNamespace(
        measurement_status="measured",
        input_units=2_419,
        output_units=3_500,
        safe_metadata={},
    )
    user_counter = SimpleNamespace(
        committed_minor_units=0,
        reserved_minor_units=63,
        revision=1,
    )
    pricing = SimpleNamespace(
        provider_definition_id=provider_id,
        model_definition_id=model_id,
        provider_key="zhipu",
        model_id=ZHIPU_GLM_52_MODEL,
        currency="CNY",
        unit_basis="per_million_tokens",
        input_minor_units_per_million=800,
        output_minor_units_per_million=2_800,
    )

    class Transaction:
        async def __aenter__(self) -> None:
            return None

        async def __aexit__(self, *_args: object) -> None:
            return None

    class Session:
        def __init__(self) -> None:
            self.scalar_results = iter((usage, None))
            self.added: tuple[object, ...] = ()

        def begin(self) -> Transaction:
            return Transaction()

        async def scalar(self, _statement: object) -> object:
            return next(self.scalar_results)

        async def get(self, _model: object, identity: uuid.UUID) -> object:
            assert identity == pricing_id
            return pricing

        def add_all(self, values: tuple[object, ...]) -> None:
            self.added = values

    class Repository:
        async def get_invocation(self, *_args: object, **_kwargs: object) -> object:
            return invocation

        async def get_attempt(self, *_args: object, **_kwargs: object) -> object:
            return attempt

        async def get_reservation(self, *_args: object, **_kwargs: object) -> object:
            return reservation

        async def get_user_counter_by_id(self, *_args: object, **_kwargs: object) -> object:
            return user_counter

        async def get_project_counter_by_id(self, *_args: object, **_kwargs: object) -> None:
            return None

    session = Session()
    service = ZhipuUsageReconciliationService(session)  # type: ignore[arg-type]
    service._repository = Repository()  # type: ignore[assignment]
    result = asyncio.run(
        service.reconcile(
            invocation_id=invocation_id,
            attempt_id=attempt_id,
        )
    )

    assert result.measured_cost_minor_units == 12
    assert result.reservation_before_minor_units == 21
    assert result.committed_after_minor_units == 12
    assert result.reserved_after_minor_units == 42
    assert reservation.state == "settled"
    assert user_counter.committed_minor_units == 12
    assert user_counter.reserved_minor_units == 42
    assert invocation.status == "failed"
    assert attempt.status == "failed"
    assert len(session.added) == 3


@pytest.mark.parametrize(
    ("status", "body", "category", "retryable"),
    [
        (401, {"error": {"code": "1000"}}, "authentication_failed", False),
        (401, {"error": {"code": "1002"}}, "authentication_failed", False),
        (401, {"error": {"code": "1005"}}, "authentication_failed", False),
        (429, {"error": {"code": "1301"}}, "rate_limited", True),
        (503, {"error": {"code": "1234"}}, "provider_unavailable", True),
    ],
)
def test_provider_errors_are_safe_and_classified(
    status: int, body: dict[str, object], category: str, retryable: bool
) -> None:
    with pytest.raises(ProviderContractError) as error:
        ZhipuChatAdapter(ZHIPU_GLM_52_MODEL).normalize_response(
            ProviderWireResponse(
                status_code=status,
                body=body,
                provider_request_id="zhipu-safe-error-id",
            )
        )
    assert error.value.category == category
    assert error.value.retryable is retryable
    assert error.value.upstream_http_status == status
    assert "1002" not in str(error.value)
    assert body not in error.value.args


def _mock_provider_error(
    *,
    status: int,
    body: dict[str, object],
    headers: dict[str, str] | None = None,
) -> ProviderContractError:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, headers=headers, json=body)

    request = ZhipuChatAdapter(ZHIPU_GLM_52_MODEL).prepare_request(
        prompt=_prompt(), images=[], response_schema=_schema(), max_output_tokens=10
    )
    wire_response = asyncio.run(
        ZhipuHTTPTransport(httpx.MockTransport(handler)).execute(
            request,
            SecretBytes(b"synthetic-test-credential"),
            live_gate_enabled=True,
        )
    )
    with pytest.raises(ProviderContractError) as captured:
        ZhipuChatAdapter(ZHIPU_GLM_52_MODEL).normalize_response(wire_response)
    return captured.value


def test_mock_transport_auth_failure_retains_allowlisted_diagnostics() -> None:
    error = _mock_provider_error(
        status=401,
        body={"error": {"code": "1003", "message": "API authentication failed."}},
        headers={"x-request-id": "zhipu-safe-request-id"},
    )

    metadata = _provider_diagnostic_metadata(error)

    assert error.category == "authentication_failed"
    assert metadata == {
        "upstream_http_status": 401,
        "provider_error_code": "1003",
        "provider_error_message": "API authentication failed.",
        "provider_request_id_status": "provided",
        "provider_request_id": "zhipu-safe-request-id",
        "json_parse_status": "not_attempted",
        "schema_validation_status": "not_attempted",
        "citation_validation_status": "not_attempted",
    }


def test_mock_transport_auth_failure_without_business_code_does_not_fabricate_one() -> None:
    error = _mock_provider_error(
        status=401,
        body={"error": {"message": "Authentication failed."}},
    )

    metadata = _provider_diagnostic_metadata(error)

    assert error.category == "authentication_failed"
    assert metadata["upstream_http_status"] == 401
    assert "provider_error_code" not in metadata
    assert metadata["provider_request_id_status"] == "unavailable"
    assert metadata["json_parse_status"] == "not_attempted"


def test_mock_transport_rejects_secret_bearing_provider_error_content() -> None:
    secret = "secret-that-must-not-appear"
    error = _mock_provider_error(
        status=401,
        body={
            "error": {
                "code": "1002",
                "message": f"Authorization: Bearer {secret}",
                "api_key": secret,
            },
            "request": {"authorization": f"Bearer {secret}"},
        },
    )

    metadata = _provider_diagnostic_metadata(error)

    assert metadata["provider_error_code"] == "1002"
    assert "provider_error_message" not in metadata
    assert secret not in repr(error.__dict__)
    assert secret not in repr(metadata)


def test_mock_transport_bounds_long_untrusted_provider_message() -> None:
    error = _mock_provider_error(
        status=400,
        body={"error": {"code": "1210", "message": "bounded safe detail " * 40}},
    )

    message = _provider_diagnostic_metadata(error)["provider_error_message"]

    assert isinstance(message, str)
    assert len(message) == MAX_SAFE_PROVIDER_ERROR_MESSAGE_CHARS
    assert "\n" not in message


def test_costs_use_cny_fen_and_measured_vision_tiers() -> None:
    text = ZhipuChatAdapter(ZHIPU_GLM_52_MODEL)
    vision = ZhipuChatAdapter(ZHIPU_GLM_5V_TURBO_MODEL)

    assert (
        text.estimate_cost(
            prompt=_prompt(), images=[], response_schema=_schema(), max_output_tokens=100
        )
        >= 1
    )
    low_tier = vision.measured_cost(
        NormalizedProviderUsage(measurement_status="measured", input_units=31_999, output_units=100)
    )
    high_tier = vision.measured_cost(
        NormalizedProviderUsage(measurement_status="measured", input_units=32_000, output_units=100)
    )
    assert low_tier == 17
    assert high_tier == 23


def test_transport_gate_blocks_before_network_or_secret_use() -> None:
    calls = 0

    async def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={})

    request = ZhipuChatAdapter(ZHIPU_GLM_52_MODEL).prepare_request(
        prompt=_prompt(), images=[], response_schema=_schema(), max_output_tokens=10
    )
    with pytest.raises(ZhipuLiveExecutionBlockedError) as error:
        asyncio.run(
            ZhipuHTTPTransport(httpx.MockTransport(handler)).execute(
                request,
                SecretBytes(b"secret-that-must-not-appear"),
                live_gate_enabled=False,
            )
        )
    assert calls == 0
    assert error.value.dispatch_certainty == "not_dispatched"
    assert "secret-that-must-not-appear" not in repr(error.value.__dict__)


def test_transport_sends_one_fixed_request_and_does_not_expose_authorization() -> None:
    seen: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["authorization"] = request.headers.get("authorization")
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            headers={"x-request-id": "zhipu-transport-id"},
            json={
                "model": ZHIPU_GLM_52_MODEL,
                "choices": [{"finish_reason": "stop", "message": {"content": "{}"}}],
            },
        )

    request = ZhipuChatAdapter(ZHIPU_GLM_52_MODEL).prepare_request(
        prompt=_prompt(), images=[], response_schema=_schema(), max_output_tokens=10
    )
    response = asyncio.run(
        ZhipuHTTPTransport(httpx.MockTransport(handler)).execute(
            request,
            SecretBytes(b"secret-that-must-not-appear"),
            live_gate_enabled=True,
        )
    )

    assert seen["url"] == f"{ZHIPU_API_ORIGIN}{ZHIPU_CHAT_COMPLETIONS_PATH}"
    assert seen["authorization"] == "Bearer secret-that-must-not-appear"
    assert seen["body"] == dict(request.body)
    assert response.provider_request_id == "zhipu-transport-id"
    assert "secret-that-must-not-appear" not in repr(response)


def test_transport_failure_has_no_secret_bearing_exception_chain() -> None:
    secret = "secret-that-must-not-appear"

    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("safe synthetic failure", request=request)

    request = ZhipuChatAdapter(ZHIPU_GLM_52_MODEL).prepare_request(
        prompt=_prompt(), images=[], response_schema=_schema(), max_output_tokens=10
    )
    with pytest.raises(ProviderContractError) as error:
        asyncio.run(
            ZhipuHTTPTransport(httpx.MockTransport(handler)).execute(
                request, SecretBytes(secret.encode()), live_gate_enabled=True
            )
        )
    assert error.value.category == "outcome_unknown"
    assert error.value.dispatch_certainty == "unknown"
    assert error.value.__cause__ is None
    assert error.value.__context__ is None
    assert _provider_diagnostic_metadata(error.value) == {
        "provider_request_id_status": "absent",
        "json_parse_status": "not_attempted",
        "schema_validation_status": "not_attempted",
        "citation_validation_status": "not_attempted",
    }
    assert secret not in repr(error.value.__dict__)
