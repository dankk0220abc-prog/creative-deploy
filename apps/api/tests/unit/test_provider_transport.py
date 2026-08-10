"""Offline-only tests for the Phase 3B Provider contract."""

import asyncio
import hashlib

import pytest

from creativedeploy_api.ai.encryption import SecretBytes
from creativedeploy_api.ai.provider_transport import (
    LIVE_PROVIDER_EXECUTION_AUTHORIZED,
    OPENAI_PINNED_MODEL,
    BlockedLiveProviderTransport,
    GovernedMultimodalPrompt,
    LiveProviderExecutionBlockedError,
    OpenAIResponsesAdapter,
    PreparedImageAttachment,
    ProviderContractError,
    ProviderWireResponse,
    assert_live_provider_execution_authorized,
)


def _image() -> PreparedImageAttachment:
    content = b"not-a-real-image-provider-contract-test"
    return PreparedImageAttachment(
        image_asset_id="00000000-0000-4000-8000-000000000001",
        role="primary_front",
        sha256=hashlib.sha256(content).hexdigest(),
        media_type="image/png",
        width=2048,
        height=2048,
        content=content,
    )


def _schema() -> dict[str, object]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {"schema_version": {"type": "string"}},
        "required": ["schema_version"],
    }


def _prompt() -> GovernedMultimodalPrompt:
    return GovernedMultimodalPrompt(
        system_prompt="Use only the governed source and return the strict schema.",
        user_intent="Preserve the approved silhouette.",
        structured_context={
            "image_set_fingerprint": "a" * 64,
            "regions": [{"id": "region-1", "kind": "paint"}],
        },
        generation_locale="zh-CN",
    )


def test_openai_request_is_pinned_strict_and_non_persistent() -> None:
    request = OpenAIResponsesAdapter().prepare_request(
        prompt=_prompt(),
        images=[_image()],
        response_schema=_schema(),
        max_output_tokens=1200,
    )

    assert request.endpoint.url == "https://api.openai.com/v1/responses"
    assert request.model_id == OPENAI_PINNED_MODEL
    assert request.body["store"] is False
    assert request.body["model"] == OPENAI_PINNED_MODEL
    assert request.body["input"][0]["role"] == "developer"
    assert request.body["input"][0]["content"][0]["text"] == _prompt().system_prompt
    assert request.body["input"][0]["content"][1]["text"].startswith(
        "Generate all provider-authored Paint Plan content in zh-CN."
    )
    assert request.body["input"][1]["role"] == "user"
    assert request.body["input"][1]["content"][0]["text"] == _prompt().user_intent
    assert request.timeout_ms == 30_000
    assert request.cancellation_mode == "local_wait_only_after_dispatch"
    assert request.body["text"] == {
        "format": {
            "type": "json_schema",
            "name": "paint_plan_v1",
            "strict": True,
            "schema": _schema(),
        }
    }
    assert "url" not in request.body


def test_live_transport_is_source_locked_before_credential_use() -> None:
    assert LIVE_PROVIDER_EXECUTION_AUTHORIZED is False
    with pytest.raises(LiveProviderExecutionBlockedError) as gate:
        assert_live_provider_execution_authorized()
    assert gate.value.dispatch_certainty == "not_dispatched"

    request = OpenAIResponsesAdapter().prepare_request(
        prompt=_prompt(),
        images=[_image()],
        response_schema=_schema(),
        max_output_tokens=1,
    )
    with pytest.raises(LiveProviderExecutionBlockedError):
        asyncio.run(
            BlockedLiveProviderTransport().execute(
                request,
                SecretBytes(b"synthetic-never-real-provider-secret"),
            )
        )


def test_response_normalization_returns_only_parsed_output_and_usage() -> None:
    result = OpenAIResponsesAdapter().normalize_response(
        ProviderWireResponse(
            status_code=200,
            body={
                "output": [
                    {
                        "type": "message",
                        "content": [
                            {
                                "type": "output_text",
                                "text": '{"schema_version":"paint-plan.v1"}',
                            }
                        ],
                    }
                ],
                "usage": {"input_tokens": 101, "output_tokens": 202},
                "untrusted_extra": "not-projected",
            },
            provider_request_id="req_safe_123",
        )
    )

    assert dict(result.output) == {"schema_version": "paint-plan.v1"}
    assert result.usage.input_units == 101
    assert result.usage.output_units == 202
    assert result.provider_request_id == "req_safe_123"


def test_response_normalization_rejects_malformed_or_duplicate_text_parts() -> None:
    adapter = OpenAIResponsesAdapter()
    with pytest.raises(ProviderContractError) as error:
        adapter.normalize_response(
            ProviderWireResponse(
                status_code=200,
                body={
                    "output": [
                        {
                            "type": "message",
                            "content": [
                                {"type": "output_text", "text": "{}"},
                                {"type": "output_text", "text": "{}"},
                            ],
                        }
                    ]
                },
                provider_request_id=None,
            )
        )
    assert error.value.category == "schema_invalid"
    assert error.value.dispatch_certainty == "dispatched"


@pytest.mark.parametrize(
    ("status_code", "category", "retryable"),
    [
        (401, "authentication_failed", False),
        (429, "rate_limited", True),
        (503, "provider_unavailable", True),
        (400, "invalid_request", False),
    ],
)
def test_http_response_errors_preserve_safe_dispatch_usage_and_request_id(
    status_code: int,
    category: str,
    retryable: bool,
) -> None:
    with pytest.raises(ProviderContractError) as error:
        OpenAIResponsesAdapter().normalize_response(
            ProviderWireResponse(
                status_code=status_code,
                body={"usage": {"input_tokens": 17, "output_tokens": 3}},
                provider_request_id="req_safe_error_123",
            )
        )

    assert error.value.category == category
    assert error.value.retryable is retryable
    assert error.value.dispatch_certainty == "dispatched"
    assert error.value.provider_request_id_status == "provided"
    assert error.value.provider_request_id == "req_safe_error_123"
    assert error.value.usage_measurement_status == "measured"
    assert error.value.input_units == 17
    assert error.value.output_units == 3


def test_malformed_success_discards_raw_output_but_preserves_safe_accounting() -> None:
    raw_marker = "raw-provider-material-must-not-escape"
    with pytest.raises(ProviderContractError) as error:
        OpenAIResponsesAdapter().normalize_response(
            ProviderWireResponse(
                status_code=200,
                body={
                    "output": [
                        {
                            "type": "message",
                            "content": [{"type": "output_text", "text": raw_marker}],
                        }
                    ],
                    "usage": {"input_tokens": 29, "output_tokens": 11},
                },
                provider_request_id="req_safe_schema_123",
            )
        )

    assert error.value.category == "schema_invalid"
    assert error.value.dispatch_certainty == "dispatched"
    assert error.value.provider_request_id == "req_safe_schema_123"
    assert error.value.input_units == 29
    assert error.value.output_units == 11
    assert raw_marker not in str(error.value)
    assert raw_marker not in repr(error.value.__dict__)
    assert error.value.__cause__ is None
    assert error.value.__context__ is None


def test_cost_estimate_is_conservative_nonzero_usd_upper_bound() -> None:
    estimate = OpenAIResponsesAdapter().estimate_cost(
        prompt=GovernedMultimodalPrompt(
            system_prompt="x" * 3_000,
            user_intent="bounded intent",
            structured_context={"regions": [{"id": "region-1"}]},
        ),
        images=[_image(), _image()],
        response_schema=_schema(),
        max_output_tokens=4_000,
    )

    assert estimate.currency == "USD"
    assert estimate.measurement_status == "estimated"
    assert estimate.input_units_upper_bound > 1_000
    assert estimate.output_units_upper_bound == 4_000
    assert estimate.amount_minor_units_upper_bound >= 1


def test_prompt_contract_rejects_oversized_structured_context_before_dispatch() -> None:
    oversized = GovernedMultimodalPrompt(
        system_prompt="reviewed system prompt",
        user_intent=None,
        structured_context={"regions": "x" * 200_001},
    )
    adapter = OpenAIResponsesAdapter()

    with pytest.raises(ProviderContractError) as prepared:
        adapter.prepare_request(
            prompt=oversized,
            images=[_image()],
            response_schema=_schema(),
            max_output_tokens=1,
        )
    with pytest.raises(ProviderContractError) as estimated:
        adapter.estimate_cost_from_dimensions(
            prompt=oversized,
            image_dimensions=[(2048, 2048)],
            response_schema=_schema(),
            max_output_tokens=1,
        )

    assert prepared.value.dispatch_certainty == "not_dispatched"
    assert estimated.value.dispatch_certainty == "not_dispatched"
