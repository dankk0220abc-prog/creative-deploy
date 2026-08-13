"""Fixed-egress Zhipu/BigModel adapters and live HTTP transport."""

from __future__ import annotations

import base64
import json
import math
from collections.abc import Mapping, Sequence
from types import MappingProxyType
from typing import Final, Literal

import httpx

from creativedeploy_api.ai.encryption import SecretBytes
from creativedeploy_api.ai.provider_transport import (
    MAX_IMAGE_ATTACHMENTS,
    MAX_PROVIDER_RESPONSE_BYTES,
    FinishReason,
    GovernedMultimodalPrompt,
    NormalizedProviderResult,
    NormalizedProviderUsage,
    PreparedImageAttachment,
    PreparedProviderRequest,
    ProviderContractError,
    ProviderEndpointPolicy,
    ProviderErrorCategory,
    ProviderWireResponse,
    _prompt_contract_units,
    _safe_provider_request_id,
    _strict_positive_int,
    structured_json_shape,
)

ZHIPU_PROVIDER_KEY: Final = "zhipu"
ZHIPU_API_ORIGIN: Final = "https://open.bigmodel.cn"
ZHIPU_CHAT_COMPLETIONS_PATH: Final = "/api/paas/v4/chat/completions"
ZHIPU_GLM_52_MODEL: Final = "glm-5.2"
ZHIPU_GLM_5V_TURBO_MODEL: Final = "glm-5v-turbo"
ZHIPU_TEXT_ADAPTER_VERSION: Final = "zhipu-chat-arcana-v3"
ZHIPU_VISION_ADAPTER_VERSION: Final = "zhipu-chat-paint-plan-v2"
ZHIPU_GLM_52_INPUT_FEN_PER_MILLION: Final = 800
ZHIPU_GLM_52_OUTPUT_FEN_PER_MILLION: Final = 2_800
ZHIPU_GLM_5V_LOW_INPUT_FEN_PER_MILLION: Final = 500
ZHIPU_GLM_5V_LOW_OUTPUT_FEN_PER_MILLION: Final = 2_200
ZHIPU_GLM_5V_HIGH_INPUT_FEN_PER_MILLION: Final = 700
ZHIPU_GLM_5V_HIGH_OUTPUT_FEN_PER_MILLION: Final = 2_600
ZHIPU_GLM_5V_HIGH_TIER_THRESHOLD: Final = 32_000
MAX_ZHIPU_REQUEST_BYTES: Final = 25_000_000
ZHIPU_ARCANA_MAX_OUTPUT_TOKENS: Final = 8_192
ZHIPU_ARCANA_REASONING_EFFORT: Final = "high"
_SAFE_FINISH_REASONS: Final = frozenset(
    {
        "stop",
        "length",
        "tool_calls",
        "sensitive",
        "network_error",
        "model_context_window_exceeded",
    }
)

ZHIPU_ENDPOINT_POLICY: Final = ProviderEndpointPolicy(
    scheme="https",
    host="open.bigmodel.cn",
    port=443,
    path=ZHIPU_CHAT_COMPLETIONS_PATH,
)


class ZhipuLiveExecutionBlockedError(ProviderContractError):
    def __init__(self) -> None:
        super().__init__("live_execution_blocked")


def assert_zhipu_live_execution_authorized(enabled: bool) -> None:
    """Fail before decryption or networking unless the explicit runtime gate is on."""

    if enabled is not True:
        raise ZhipuLiveExecutionBlockedError


def _zhipu_usage(body: Mapping[str, object]) -> NormalizedProviderUsage:
    usage = body.get("usage")
    if isinstance(usage, Mapping):
        input_units = _strict_positive_int(usage.get("prompt_tokens"))
        output_units = _strict_positive_int(usage.get("completion_tokens"))
        completion_details = usage.get("completion_tokens_details")
        reasoning_tokens = (
            _strict_nonnegative_int(completion_details.get("reasoning_tokens"))
            if isinstance(completion_details, Mapping)
            else None
        )
        if input_units is not None and output_units is not None:
            return NormalizedProviderUsage(
                measurement_status="measured",
                input_units=input_units,
                output_units=output_units,
                reasoning_tokens=reasoning_tokens,
            )
    return NormalizedProviderUsage(
        measurement_status="unavailable",
        input_units=None,
        output_units=None,
        reasoning_tokens=None,
    )


def _strict_nonnegative_int(value: object) -> int | None:
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    return None


def _business_error_code(body: Mapping[str, object]) -> int | None:
    error = body.get("error")
    if not isinstance(error, Mapping):
        return None
    value = error.get("code")
    if isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 2_147_483_647:
        return value
    if (
        isinstance(value, str)
        and 1 <= len(value) <= 10
        and value.isascii()
        and value.isdigit()
        and int(value) <= 2_147_483_647
    ):
        return int(value)
    return None


def _provider_error_message(body: Mapping[str, object]) -> object:
    error = body.get("error")
    return error.get("message") if isinstance(error, Mapping) else None


def _mapped_error(
    status_code: int, body: Mapping[str, object]
) -> tuple[ProviderErrorCategory, bool]:
    code = _business_error_code(body)
    if status_code in {401, 403} or code in {1000, 1001, 1002, 1003, 1004, 1005}:
        return "authentication_failed", False
    if status_code == 429 or code in {1301, 1302, 1303, 1304, 1305}:
        return "rate_limited", True
    if status_code >= 500:
        return "provider_unavailable", True
    return "invalid_request", False


def _safe_finish_reason(value: object) -> FinishReason | None:
    return value if isinstance(value, str) and value in _SAFE_FINISH_REASONS else None  # type: ignore[return-value]


def _choice_completion(
    body: Mapping[str, object],
) -> tuple[FinishReason | None, str | None]:
    choices = body.get("choices")
    if not isinstance(choices, list) or len(choices) != 1:
        return None, None
    choice = choices[0]
    if not isinstance(choice, Mapping):
        return None, None
    finish_reason = _safe_finish_reason(choice.get("finish_reason"))
    message = choice.get("message")
    if not isinstance(message, Mapping):
        return finish_reason, None
    content = message.get("content")
    return finish_reason, content if isinstance(content, str) and content else None


class ZhipuChatAdapter:
    """Offline-testable adapter for exact approved text or vision models."""

    provider_key = ZHIPU_PROVIDER_KEY
    endpoint = ZHIPU_ENDPOINT_POLICY

    def __init__(self, model_id: Literal["glm-5.2", "glm-5v-turbo"]) -> None:
        self.model_id = model_id
        self.adapter_version = (
            ZHIPU_TEXT_ADAPTER_VERSION
            if model_id == ZHIPU_GLM_52_MODEL
            else ZHIPU_VISION_ADAPTER_VERSION
        )

    @property
    def vision(self) -> bool:
        return self.model_id == ZHIPU_GLM_5V_TURBO_MODEL

    def prepare_request(
        self,
        *,
        prompt: GovernedMultimodalPrompt,
        images: Sequence[PreparedImageAttachment],
        response_schema: Mapping[str, object],
        max_output_tokens: int,
        timeout_ms: int = 30_000,
    ) -> PreparedProviderRequest:
        self.endpoint.validate()
        _, structured_context = _prompt_contract_units(prompt, response_schema)
        if (
            (self.vision and not 1 <= len(images) <= MAX_IMAGE_ATTACHMENTS)
            or (not self.vision and len(images) != 0)
            or not 1 <= max_output_tokens <= 16_384
            or not 1 <= timeout_ms <= 120_000
        ):
            raise ProviderContractError("invalid_request")
        schema_text = json.dumps(
            response_schema, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        text = (
            "Return exactly one JSON object and nothing else: no Markdown fence, no prose before "
            "or after the object, and no reasoning content inside the object. It must conform to "
            "this exact local schema; the application will reject missing, extra, malformed, or "
            "unsupported citation fields.\n"
            f"Schema:\n{schema_text}\nGoverned context:\n{structured_context}"
        )
        if prompt.user_intent is not None:
            text = f"User intent:\n{prompt.user_intent}\n{text}"
        if self.vision:
            user_content: object = [{"type": "text", "text": text}]
            assert isinstance(user_content, list)
            for image in images:
                image.validate()
                encoded = base64.b64encode(image.content).decode("ascii")
                user_content.append(
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{image.media_type};base64,{encoded}"},
                    }
                )
        else:
            user_content = text
        body: dict[str, object] = {
            "model": self.model_id,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        f"{prompt.system_prompt}\nGenerate provider-authored content in "
                        f"{prompt.generation_locale}. Never cite a source or chunk that is absent "
                        "from the governed retrieved context."
                    ),
                },
                {"role": "user", "content": user_content},
            ],
            "stream": False,
            "max_tokens": max_output_tokens,
        }
        if self.vision:
            body["thinking"] = {"type": "enabled"}
            body["do_sample"] = False
        else:
            body["response_format"] = {"type": "json_object"}
            body["thinking"] = {"type": "enabled"}
            body["reasoning_effort"] = ZHIPU_ARCANA_REASONING_EFFORT
            body["do_sample"] = False
        try:
            request_size = len(
                json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            )
        except (TypeError, ValueError) as error:
            raise ProviderContractError("invalid_request") from error
        if request_size > MAX_ZHIPU_REQUEST_BYTES:
            raise ProviderContractError("invalid_request")
        return PreparedProviderRequest(
            provider_key=self.provider_key,
            model_id=self.model_id,
            adapter_version=self.adapter_version,
            endpoint=self.endpoint,
            body=MappingProxyType(body),
            response_limit_bytes=MAX_PROVIDER_RESPONSE_BYTES,
            timeout_ms=timeout_ms,
            cancellation_mode="local_wait_only_after_dispatch",
        )

    def normalize_response(self, response: ProviderWireResponse) -> NormalizedProviderResult:
        body = response.body
        request_id = _safe_provider_request_id(response.provider_request_id)
        if request_id is None:
            candidate = body.get("request_id") or body.get("id")
            request_id = _safe_provider_request_id(
                candidate if isinstance(candidate, str) else None
            )
        usage = _zhipu_usage(body)
        business_error_code = _business_error_code(body)
        finish_reason, content = _choice_completion(body)
        output_content_bytes = None if content is None else len(content.encode("utf-8"))
        output_content_characters = None if content is None else len(content)

        def error(
            category: ProviderErrorCategory,
            *,
            retryable: bool = False,
            json_parse_status: Literal["not_attempted", "parsed", "failed"] = "not_attempted",
            structured_failure_category: Literal[
                "JSON_PARSE_FAILED",
                "SCHEMA_VALIDATION_FAILED",
                "CITATION_VALIDATION_FAILED",
                "OUTPUT_LIMIT_REACHED_OR_CONFIRMED_TRUNCATION",
                "UNKNOWN_STRUCTURED_OUTPUT_FAILURE",
            ]
            | None = None,
            structured_error_path: str | None = None,
            structured_expected_root_json_type: str | None = None,
            structured_received_root_json_type: str | None = None,
            structured_expected_json_type: str | None = None,
            structured_received_json_type: str | None = None,
            structured_received_item_count: int | None = None,
        ) -> ProviderContractError:
            return ProviderContractError(
                category,
                retryable=retryable,
                dispatch_certainty="dispatched",
                provider_request_id_status="provided" if request_id else "unavailable",
                provider_request_id=request_id,
                usage_measurement_status=usage.measurement_status,
                input_units=usage.input_units,
                output_units=usage.output_units,
                upstream_http_status=response.status_code,
                provider_error_code=business_error_code,
                provider_error_message=_provider_error_message(body),
                finish_reason=finish_reason,
                reasoning_tokens=usage.reasoning_tokens,
                output_content_bytes=output_content_bytes,
                output_content_characters=output_content_characters,
                json_parse_status=json_parse_status,
                structured_failure_category=structured_failure_category,
                structured_error_path=structured_error_path,
                structured_expected_root_json_type=structured_expected_root_json_type,
                structured_received_root_json_type=structured_received_root_json_type,
                structured_expected_json_type=structured_expected_json_type,
                structured_received_json_type=structured_received_json_type,
                structured_received_item_count=structured_received_item_count,
            )

        if not 200 <= response.status_code < 300 or business_error_code is not None:
            category, retryable = _mapped_error(response.status_code, body)
            raise error(category, retryable=retryable)
        if body.get("model") != self.model_id:
            raise error(
                "schema_invalid",
                structured_failure_category="UNKNOWN_STRUCTURED_OUTPUT_FAILURE",
                structured_error_path="$.model",
            )
        if finish_reason != "stop":
            raise error(
                "schema_invalid",
                structured_failure_category=(
                    "OUTPUT_LIMIT_REACHED_OR_CONFIRMED_TRUNCATION"
                    if finish_reason == "length"
                    else "UNKNOWN_STRUCTURED_OUTPUT_FAILURE"
                ),
                structured_error_path="$.choices[0].finish_reason",
            )
        if content is None or output_content_bytes is None:
            raise error(
                "schema_invalid",
                structured_failure_category="UNKNOWN_STRUCTURED_OUTPUT_FAILURE",
                structured_error_path="$.choices[0].message.content",
            )
        if output_content_bytes > MAX_PROVIDER_RESPONSE_BYTES:
            raise error("response_too_large")
        try:
            parsed = json.loads(content)
        except (json.JSONDecodeError, TypeError, ValueError):
            raise error(
                "schema_invalid",
                json_parse_status="failed",
                structured_failure_category="JSON_PARSE_FAILED",
                structured_error_path="$",
            ) from None
        if not isinstance(parsed, dict):
            raise error(
                "schema_invalid",
                json_parse_status="parsed",
                structured_failure_category="SCHEMA_VALIDATION_FAILED",
                structured_error_path="$",
                structured_expected_root_json_type="object",
                structured_received_root_json_type=structured_json_shape(parsed),
                structured_expected_json_type="object",
                structured_received_json_type=structured_json_shape(parsed),
                structured_received_item_count=(len(parsed) if isinstance(parsed, list) else None),
            )
        return NormalizedProviderResult(
            output=MappingProxyType(parsed),
            usage=usage,
            provider_request_id_status="provided" if request_id else "unavailable",
            provider_request_id=request_id,
            finish_reason=finish_reason,
            output_content_bytes=output_content_bytes,
            output_content_characters=output_content_characters,
            json_parse_status="parsed",
        )

    def estimate_cost(
        self,
        *,
        prompt: GovernedMultimodalPrompt,
        images: Sequence[PreparedImageAttachment],
        response_schema: Mapping[str, object],
        max_output_tokens: int,
    ) -> int:
        input_units, _ = _prompt_contract_units(prompt, response_schema)
        if self.vision:
            if not images:
                raise ProviderContractError("invalid_request")
            for image in images:
                image.validate()
                input_units += math.ceil(len(image.content) / 3)
            input_rate = ZHIPU_GLM_5V_HIGH_INPUT_FEN_PER_MILLION
            output_rate = ZHIPU_GLM_5V_HIGH_OUTPUT_FEN_PER_MILLION
        else:
            if images:
                raise ProviderContractError("invalid_request")
            input_rate = ZHIPU_GLM_52_INPUT_FEN_PER_MILLION
            output_rate = ZHIPU_GLM_52_OUTPUT_FEN_PER_MILLION
        return max(
            1,
            math.ceil((input_units * input_rate + max_output_tokens * output_rate) / 1_000_000),
        )

    def estimate_cost_from_metadata(
        self,
        *,
        prompt: GovernedMultimodalPrompt,
        image_byte_lengths: Sequence[int],
        response_schema: Mapping[str, object],
        max_output_tokens: int,
    ) -> int:
        input_units, _ = _prompt_contract_units(prompt, response_schema)
        if self.vision:
            if not 1 <= len(image_byte_lengths) <= MAX_IMAGE_ATTACHMENTS or any(
                value < 1 for value in image_byte_lengths
            ):
                raise ProviderContractError("invalid_request")
            input_units += sum(math.ceil(value / 3) for value in image_byte_lengths)
            input_rate = ZHIPU_GLM_5V_HIGH_INPUT_FEN_PER_MILLION
            output_rate = ZHIPU_GLM_5V_HIGH_OUTPUT_FEN_PER_MILLION
        else:
            if image_byte_lengths:
                raise ProviderContractError("invalid_request")
            input_rate = ZHIPU_GLM_52_INPUT_FEN_PER_MILLION
            output_rate = ZHIPU_GLM_52_OUTPUT_FEN_PER_MILLION
        return max(
            1,
            math.ceil((input_units * input_rate + max_output_tokens * output_rate) / 1_000_000),
        )

    def measured_cost(self, usage: NormalizedProviderUsage) -> int | None:
        if (
            usage.measurement_status != "measured"
            or usage.input_units is None
            or usage.output_units is None
        ):
            return None
        if self.vision:
            high = usage.input_units >= ZHIPU_GLM_5V_HIGH_TIER_THRESHOLD
            input_rate = (
                ZHIPU_GLM_5V_HIGH_INPUT_FEN_PER_MILLION
                if high
                else ZHIPU_GLM_5V_LOW_INPUT_FEN_PER_MILLION
            )
            output_rate = (
                ZHIPU_GLM_5V_HIGH_OUTPUT_FEN_PER_MILLION
                if high
                else ZHIPU_GLM_5V_LOW_OUTPUT_FEN_PER_MILLION
            )
        else:
            input_rate = ZHIPU_GLM_52_INPUT_FEN_PER_MILLION
            output_rate = ZHIPU_GLM_52_OUTPUT_FEN_PER_MILLION
        return math.ceil(
            (usage.input_units * input_rate + usage.output_units * output_rate) / 1_000_000
        )


class ZhipuHTTPTransport:
    """Non-streaming fixed-destination transport with redirects and env proxies off."""

    def __init__(self, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._transport = transport

    async def execute(
        self,
        request: PreparedProviderRequest,
        credential: SecretBytes,
        *,
        live_gate_enabled: bool,
    ) -> ProviderWireResponse:
        assert_zhipu_live_execution_authorized(live_gate_enabled)
        request.endpoint.validate()
        if (
            request.provider_key != ZHIPU_PROVIDER_KEY
            or request.endpoint != ZHIPU_ENDPOINT_POLICY
            or request.model_id not in {ZHIPU_GLM_52_MODEL, ZHIPU_GLM_5V_TURBO_MODEL}
            or not credential.value
        ):
            raise ProviderContractError("invalid_request")
        credential_decode_failed = False
        try:
            authorization_value = credential.value.decode("ascii")
        except UnicodeDecodeError:
            credential_decode_failed = True
            authorization_value = ""
        if credential_decode_failed:
            raise ProviderContractError("invalid_request")
        timeout_failed = False
        transport_failed = False
        try:
            timeout = httpx.Timeout(request.timeout_ms / 1000)
            async with httpx.AsyncClient(
                timeout=timeout,
                follow_redirects=False,
                trust_env=False,
                transport=self._transport,
            ) as client:
                response = await client.post(
                    request.endpoint.url,
                    headers={
                        "Accept": "application/json",
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {authorization_value}",
                    },
                    json=dict(request.body),
                )
                raw = await response.aread()
        except httpx.TimeoutException:
            timeout_failed = True
            raw = b""
            response = None
        except httpx.HTTPError:
            transport_failed = True
            raw = b""
            response = None
        if timeout_failed or transport_failed:
            raise ProviderContractError("outcome_unknown", dispatch_certainty="unknown")
        assert response is not None
        if len(raw) > request.response_limit_bytes:
            raise ProviderContractError("response_too_large", dispatch_certainty="dispatched")
        try:
            payload = response.json()
        except ValueError as error:
            raise ProviderContractError(
                "schema_invalid", dispatch_certainty="dispatched"
            ) from error
        if not isinstance(payload, dict):
            raise ProviderContractError("schema_invalid", dispatch_certainty="dispatched")
        header_request_id = response.headers.get("x-request-id")
        return ProviderWireResponse(
            status_code=response.status_code,
            body=payload,
            provider_request_id=header_request_id,
        )
