"""Provider-neutral multimodal contracts with a source-locked live egress gate.

Phase 3B deliberately contains no executable live transport.  The OpenAI
adapter can prepare and normalize data in unit tests, while every real-provider
transport call fails before credentials or network-capable state are touched.
"""

from __future__ import annotations

import base64
import hashlib
import json
import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final, Literal, Protocol
from urllib.parse import urlsplit

from creativedeploy_api.ai.encryption import SecretBytes

LIVE_PROVIDER_EXECUTION_AUTHORIZED: Final = False
OPENAI_RESPONSES_ORIGIN: Final = "https://api.openai.com"
OPENAI_RESPONSES_PATH: Final = "/v1/responses"
OPENAI_PINNED_MODEL: Final = "gpt-5.4-mini-2026-03-17"
OPENAI_ADAPTER_VERSION: Final = "openai-responses-paint-plan-v1"
OPENAI_INPUT_CENTS_PER_MILLION: Final = 75
OPENAI_OUTPUT_CENTS_PER_MILLION: Final = 450
OPENAI_HIGH_DETAIL_PATCH_BUDGET: Final = 1_536
OPENAI_MINI_PATCH_MULTIPLIER_NUMERATOR: Final = 162
OPENAI_MINI_PATCH_MULTIPLIER_DENOMINATOR: Final = 100
MAX_PROVIDER_RESPONSE_BYTES: Final = 2_000_000
MAX_IMAGE_ATTACHMENTS: Final = 16
MAX_IMAGE_BYTES: Final = 20_971_520
MAX_SYSTEM_PROMPT_BYTES: Final = 12_000
MAX_USER_INTENT_BYTES: Final = 1_200
MAX_STRUCTURED_CONTEXT_BYTES: Final = 200_000
MAX_RESPONSE_SCHEMA_BYTES: Final = 100_000
REQUEST_WRAPPER_BYTES_UPPER_BOUND: Final = 4_096
MAX_SAFE_PROVIDER_ERROR_MESSAGE_CHARS: Final = 240
_JSON_PARSE_FAILED: Final = object()
_SAFE_PROVIDER_ERROR_CODE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,63}")
_SAFE_STRUCTURED_VALIDATOR_CATEGORY = re.compile(r"[a-z][a-z0-9_]{0,63}")
_SAFE_STRUCTURED_OBJECT_KEY = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,63}")
_SAFE_STRUCTURED_JSON_TYPES: Final = frozenset(
    {
        "array<boolean>",
        "array<empty>",
        "array<integer>",
        "array<mixed>",
        "array<null>",
        "array<number>",
        "array<object>",
        "array<string>",
        "boolean",
        "integer",
        "missing",
        "null",
        "number",
        "object",
        "string",
        "unknown",
    }
)
_CREDENTIAL_LIKE_PROVIDER_ERROR_VALUE = re.compile(
    r"(?:sk-|key[-_:]|token[-_:]?)[A-Za-z0-9._-]{8,}|[A-Za-z0-9_-]{32,}",
    re.IGNORECASE,
)
_SENSITIVE_PROVIDER_ERROR_MARKERS: Final = (
    "authorization",
    "bearer ",
    "api key",
    "api-key",
    "api_key",
    "apikey",
    "credential",
    "client secret",
    "client_secret",
    "cookie",
    "ciphertext",
    "wrapped dek",
)

ProviderErrorCategory = Literal[
    "authentication_failed",
    "invalid_request",
    "provider_unavailable",
    "rate_limited",
    "response_too_large",
    "schema_invalid",
    "outcome_unknown",
    "live_execution_blocked",
]

StructuredFailureCategory = Literal[
    "JSON_PARSE_FAILED",
    "SCHEMA_VALIDATION_FAILED",
    "CITATION_VALIDATION_FAILED",
    "OUTPUT_LIMIT_REACHED_OR_CONFIRMED_TRUNCATION",
    "UNKNOWN_STRUCTURED_OUTPUT_FAILURE",
]
JsonParseStatus = Literal["not_attempted", "parsed", "failed"]
SchemaValidationStatus = Literal["not_attempted", "validated", "failed"]
CitationValidationStatus = Literal["not_attempted", "validated", "failed"]
FinishReason = Literal[
    "stop",
    "length",
    "tool_calls",
    "sensitive",
    "network_error",
    "model_context_window_exceeded",
]


def _safe_provider_error_code(value: object) -> str | None:
    if isinstance(value, bool):
        return None
    candidate = str(value) if isinstance(value, int) else value
    if not isinstance(candidate, str) or _SAFE_PROVIDER_ERROR_CODE.fullmatch(candidate) is None:
        return None
    return candidate


def _safe_provider_error_message(value: object) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    if any(not character.isprintable() and not character.isspace() for character in value):
        return None
    normalized = " ".join(value.split())
    if not normalized:
        return None
    lowered = normalized.casefold()
    if any(marker in lowered for marker in _SENSITIVE_PROVIDER_ERROR_MARKERS):
        return None
    if _CREDENTIAL_LIKE_PROVIDER_ERROR_VALUE.search(normalized) is not None:
        return None
    return normalized[:MAX_SAFE_PROVIDER_ERROR_MESSAGE_CHARS]


def _safe_structured_json_type(value: object) -> str | None:
    return value if isinstance(value, str) and value in _SAFE_STRUCTURED_JSON_TYPES else None


def _safe_structured_object_keys(value: object) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        return ()
    safe: list[str] = []
    for item in value:
        if (
            isinstance(item, str)
            and _SAFE_STRUCTURED_OBJECT_KEY.fullmatch(item) is not None
            and item not in safe
        ):
            safe.append(item)
        if len(safe) == 16:
            break
    return tuple(safe)


def structured_json_shape(value: object, *, missing: object | None = None) -> str:
    """Return a value-free JSON shape suitable for safe diagnostics."""

    if missing is not None and value is missing:
        return "missing"
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, str):
        return "string"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, Mapping):
        return "object"
    if isinstance(value, list):
        if not value:
            return "array<empty>"
        item_shapes = {structured_json_shape(item) for item in value}
        if len(item_shapes) != 1:
            return "array<mixed>"
        item_shape = next(iter(item_shapes))
        if item_shape in {"object", "string", "integer", "number", "boolean", "null"}:
            return f"array<{item_shape}>"
        return "array<mixed>"
    return "unknown"


class ProviderContractError(RuntimeError):
    """Safe adapter/transport failure with no raw Provider material."""

    def __init__(
        self,
        category: ProviderErrorCategory,
        *,
        retryable: bool = False,
        dispatch_certainty: Literal["not_dispatched", "dispatched", "unknown"] = "not_dispatched",
        provider_request_id_status: Literal["provided", "unavailable", "absent"] = "absent",
        provider_request_id: str | None = None,
        usage_measurement_status: Literal["measured", "unavailable"] = "unavailable",
        input_units: int | None = None,
        output_units: int | None = None,
        upstream_http_status: int | None = None,
        provider_error_code: object = None,
        provider_error_message: object = None,
        finish_reason: FinishReason | None = None,
        reasoning_tokens: int | None = None,
        output_content_bytes: int | None = None,
        output_content_characters: int | None = None,
        json_parse_status: JsonParseStatus = "not_attempted",
        schema_validation_status: SchemaValidationStatus = "not_attempted",
        citation_validation_status: CitationValidationStatus = "not_attempted",
        structured_failure_category: StructuredFailureCategory | None = None,
        structured_error_path: str | None = None,
        structured_expected_root_json_type: str | None = None,
        structured_received_root_json_type: str | None = None,
        structured_expected_json_type: str | None = None,
        structured_received_json_type: str | None = None,
        structured_received_item_count: int | None = None,
        structured_received_object_keys: tuple[str, ...] = (),
        structured_missing_required_keys: tuple[str, ...] = (),
        structured_unexpected_object_keys: tuple[str, ...] = (),
        structured_validator_error_category: str | None = None,
    ) -> None:
        super().__init__("The Provider operation could not be completed safely.")
        self.category = category
        self.retryable = retryable
        self.dispatch_certainty = dispatch_certainty
        self.provider_request_id_status = provider_request_id_status
        self.provider_request_id = provider_request_id
        self.usage_measurement_status = usage_measurement_status
        self.input_units = input_units
        self.output_units = output_units
        self.upstream_http_status = (
            upstream_http_status
            if isinstance(upstream_http_status, int)
            and not isinstance(upstream_http_status, bool)
            and 100 <= upstream_http_status <= 599
            else None
        )
        self.provider_error_code = _safe_provider_error_code(provider_error_code)
        self.provider_error_message = _safe_provider_error_message(provider_error_message)
        self.finish_reason = finish_reason
        self.reasoning_tokens = (
            reasoning_tokens
            if isinstance(reasoning_tokens, int)
            and not isinstance(reasoning_tokens, bool)
            and reasoning_tokens >= 0
            else None
        )
        self.output_content_bytes = (
            output_content_bytes
            if isinstance(output_content_bytes, int)
            and not isinstance(output_content_bytes, bool)
            and output_content_bytes >= 0
            else None
        )
        self.output_content_characters = (
            output_content_characters
            if isinstance(output_content_characters, int)
            and not isinstance(output_content_characters, bool)
            and output_content_characters >= 0
            else None
        )
        self.json_parse_status = json_parse_status
        self.schema_validation_status = schema_validation_status
        self.citation_validation_status = citation_validation_status
        self.structured_failure_category = structured_failure_category
        self.structured_error_path = (
            structured_error_path
            if isinstance(structured_error_path, str)
            and 1 <= len(structured_error_path) <= 240
            and structured_error_path.startswith("$")
            and all(
                character.isalnum() or character in "$._-[]" for character in structured_error_path
            )
            else None
        )
        self.structured_expected_json_type = _safe_structured_json_type(
            structured_expected_json_type
        )
        self.structured_received_json_type = _safe_structured_json_type(
            structured_received_json_type
        )
        self.structured_expected_root_json_type = _safe_structured_json_type(
            structured_expected_root_json_type
        )
        self.structured_received_root_json_type = _safe_structured_json_type(
            structured_received_root_json_type
        )
        self.structured_received_item_count = (
            structured_received_item_count
            if isinstance(structured_received_item_count, int)
            and not isinstance(structured_received_item_count, bool)
            and 0 <= structured_received_item_count <= 10_000
            else None
        )
        self.structured_received_object_keys = _safe_structured_object_keys(
            structured_received_object_keys
        )
        self.structured_missing_required_keys = _safe_structured_object_keys(
            structured_missing_required_keys
        )
        self.structured_unexpected_object_keys = _safe_structured_object_keys(
            structured_unexpected_object_keys
        )
        self.structured_validator_error_category = (
            structured_validator_error_category
            if isinstance(structured_validator_error_category, str)
            and _SAFE_STRUCTURED_VALIDATOR_CATEGORY.fullmatch(structured_validator_error_category)
            is not None
            else None
        )


class StructuredOutputValidationError(ValueError):
    """Local rejection carrying only safe structural diagnostics, never output values."""

    def __init__(
        self,
        category: Literal["SCHEMA_VALIDATION_FAILED", "CITATION_VALIDATION_FAILED"],
        *,
        path: str,
        expected_root_json_type: str | None = None,
        received_root_json_type: str | None = None,
        expected_json_type: str | None = None,
        received_json_type: str | None = None,
        received_item_count: int | None = None,
        received_object_keys: tuple[str, ...] = (),
        missing_required_keys: tuple[str, ...] = (),
        unexpected_object_keys: tuple[str, ...] = (),
        validator_error_category: str | None = None,
    ) -> None:
        super().__init__("The structured Provider output failed local validation.")
        self.category = category
        self.path = path
        self.expected_root_json_type = expected_root_json_type
        self.received_root_json_type = received_root_json_type
        self.expected_json_type = expected_json_type
        self.received_json_type = received_json_type
        self.received_item_count = received_item_count
        self.received_object_keys = received_object_keys
        self.missing_required_keys = missing_required_keys
        self.unexpected_object_keys = unexpected_object_keys
        self.validator_error_category = validator_error_category


class LiveProviderExecutionBlockedError(ProviderContractError):
    """The Phase 3B source authorization boundary rejected live execution."""

    def __init__(self) -> None:
        super().__init__("live_execution_blocked")


@dataclass(frozen=True, slots=True)
class ProviderEndpointPolicy:
    """One immutable Provider-managed destination; never caller supplied."""

    scheme: Literal["https"]
    host: str
    port: Literal[443]
    path: str

    @property
    def url(self) -> str:
        return f"{self.scheme}://{self.host}{self.path}"

    def validate(self) -> None:
        parsed = urlsplit(self.url)
        if (
            parsed.scheme != "https"
            or parsed.hostname != self.host
            or parsed.port not in (None, 443)
            or parsed.path != self.path
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
            or not self.path.startswith("/")
        ):
            raise ProviderContractError("invalid_request")


OPENAI_ENDPOINT_POLICY: Final = ProviderEndpointPolicy(
    scheme="https",
    host="api.openai.com",
    port=443,
    path=OPENAI_RESPONSES_PATH,
)


@dataclass(frozen=True, slots=True)
class PreparedImageAttachment:
    """In-memory governed image material with safe identity metadata."""

    image_asset_id: str
    role: str
    sha256: str
    media_type: Literal["image/jpeg", "image/png", "image/webp"]
    width: int
    height: int
    content: bytes

    def validate(self) -> None:
        if (
            not self.image_asset_id
            or not self.role
            or len(self.sha256) != 64
            or any(character not in "0123456789abcdef" for character in self.sha256)
            or not (1 <= len(self.content) <= MAX_IMAGE_BYTES)
            or not (1 <= self.width <= 8192 and 1 <= self.height <= 8192)
            or hashlib.sha256(self.content).hexdigest() != self.sha256
        ):
            raise ProviderContractError("invalid_request")


@dataclass(frozen=True, slots=True)
class GovernedMultimodalPrompt:
    """Separated reviewed instructions, user intent, and governed metadata."""

    system_prompt: str
    user_intent: str | None
    structured_context: Mapping[str, object]
    generation_locale: Literal["zh-CN", "en-US"] = "en-US"


@dataclass(frozen=True, slots=True, repr=False)
class PreparedProviderRequest:
    provider_key: str
    model_id: str
    adapter_version: str
    endpoint: ProviderEndpointPolicy
    body: Mapping[str, object]
    response_limit_bytes: int
    timeout_ms: int
    cancellation_mode: Literal["local_wait_only_after_dispatch"]

    def __repr__(self) -> str:
        return (
            "PreparedProviderRequest("
            f"provider_key={self.provider_key!r}, model_id={self.model_id!r}, "
            f"adapter_version={self.adapter_version!r}, endpoint={self.endpoint!r}, "
            "body=[REDACTED], "
            f"response_limit_bytes={self.response_limit_bytes!r}, "
            f"timeout_ms={self.timeout_ms!r}, cancellation_mode={self.cancellation_mode!r})"
        )


@dataclass(frozen=True, slots=True)
class ProviderWireResponse:
    """Bounded response supplied by a future authorized transport."""

    status_code: int
    body: Mapping[str, object]
    provider_request_id: str | None


@dataclass(frozen=True, slots=True)
class NormalizedProviderUsage:
    measurement_status: Literal["measured", "unavailable"]
    input_units: int | None
    output_units: int | None
    reasoning_tokens: int | None = None


@dataclass(frozen=True, slots=True)
class NormalizedProviderResult:
    output: Mapping[str, object]
    usage: NormalizedProviderUsage
    provider_request_id_status: Literal["provided", "unavailable"]
    provider_request_id: str | None
    finish_reason: FinishReason | None = None
    output_content_bytes: int | None = None
    output_content_characters: int | None = None
    json_parse_status: JsonParseStatus = "not_attempted"


def _safe_provider_request_id(value: str | None) -> str | None:
    if (
        value is None
        or not value
        or len(value) > 200
        or value != value.strip()
        or any(not character.isprintable() for character in value)
    ):
        return None
    return value


def _normalized_usage(response: Mapping[str, object]) -> NormalizedProviderUsage:
    usage = response.get("usage")
    if isinstance(usage, Mapping):
        input_units = _strict_positive_int(usage.get("input_tokens"))
        output_units = _strict_positive_int(usage.get("output_tokens"))
        if input_units is not None and output_units is not None:
            return NormalizedProviderUsage(
                measurement_status="measured",
                input_units=input_units,
                output_units=output_units,
            )
    return NormalizedProviderUsage(
        measurement_status="unavailable",
        input_units=None,
        output_units=None,
    )


@dataclass(frozen=True, slots=True)
class ProviderCostEstimate:
    measurement_status: Literal["estimated"]
    input_units_upper_bound: int
    output_units_upper_bound: int
    amount_minor_units_upper_bound: int
    currency: Literal["USD"] = "USD"


class MultimodalProviderAdapter(Protocol):
    provider_key: str
    adapter_version: str

    def prepare_request(
        self,
        *,
        prompt: GovernedMultimodalPrompt,
        images: Sequence[PreparedImageAttachment],
        response_schema: Mapping[str, object],
        max_output_tokens: int,
        timeout_ms: int = 30_000,
    ) -> PreparedProviderRequest: ...

    def normalize_response(self, response: ProviderWireResponse) -> NormalizedProviderResult: ...


class ProviderTransport(Protocol):
    async def execute(
        self,
        request: PreparedProviderRequest,
        credential: SecretBytes,
    ) -> ProviderWireResponse: ...


class BlockedLiveProviderTransport:
    """Only real-Provider transport injected in Phase 3B."""

    async def execute(
        self,
        request: PreparedProviderRequest,
        credential: SecretBytes,
    ) -> ProviderWireResponse:
        del request, credential
        raise LiveProviderExecutionBlockedError


def assert_live_provider_execution_authorized() -> None:
    """Require a future reviewed source change; no setting can alter this."""

    if LIVE_PROVIDER_EXECUTION_AUTHORIZED is not True:
        raise LiveProviderExecutionBlockedError


def _strict_positive_int(value: object) -> int | None:
    if type(value) is not int or value < 0:
        return None
    return value


def _output_text(response: Mapping[str, object]) -> str:
    output = response.get("output")
    if not isinstance(output, list):
        raise ProviderContractError("schema_invalid", dispatch_certainty="dispatched")
    text_values: list[str] = []
    for item in output:
        if not isinstance(item, Mapping) or item.get("type") != "message":
            continue
        content = item.get("content")
        if not isinstance(content, list):
            continue
        for part in content:
            if (
                isinstance(part, Mapping)
                and part.get("type") == "output_text"
                and isinstance(part.get("text"), str)
            ):
                text_values.append(part["text"])
    if len(text_values) != 1:
        raise ProviderContractError("schema_invalid", dispatch_certainty="dispatched")
    return text_values[0]


def _parse_output_json(response: Mapping[str, object]) -> object:
    """Parse untrusted output without retaining the raw decoder exception graph."""

    try:
        return json.loads(_output_text(response))
    except (json.JSONDecodeError, TypeError, ProviderContractError):
        return _JSON_PARSE_FAILED


def _canonical_json_bytes(value: Mapping[str, object]) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise ProviderContractError("invalid_request") from error


def _prompt_contract_units(
    prompt: GovernedMultimodalPrompt,
    response_schema: Mapping[str, object],
) -> tuple[int, str]:
    system_bytes = prompt.system_prompt.encode("utf-8")
    intent_bytes = b"" if prompt.user_intent is None else prompt.user_intent.encode("utf-8")
    context_bytes = _canonical_json_bytes(prompt.structured_context)
    schema_bytes = _canonical_json_bytes(response_schema)
    if (
        not prompt.system_prompt.strip()
        or len(system_bytes) > MAX_SYSTEM_PROMPT_BYTES
        or (
            prompt.user_intent is not None
            and (not prompt.user_intent.strip() or len(intent_bytes) > MAX_USER_INTENT_BYTES)
        )
        or not prompt.structured_context
        or prompt.generation_locale not in {"zh-CN", "en-US"}
        or len(context_bytes) > MAX_STRUCTURED_CONTEXT_BYTES
        or not response_schema
        or len(schema_bytes) > MAX_RESPONSE_SCHEMA_BYTES
    ):
        raise ProviderContractError("invalid_request")
    input_units_upper_bound = (
        len(system_bytes)
        + len(intent_bytes)
        + len(context_bytes)
        + len(schema_bytes)
        + REQUEST_WRAPPER_BYTES_UPPER_BOUND
    )
    return input_units_upper_bound, context_bytes.decode("utf-8")


class OpenAIResponsesAdapter:
    """Offline-testable OpenAI Responses request/normalization contract."""

    provider_key = "openai"
    adapter_version = OPENAI_ADAPTER_VERSION
    model_id = OPENAI_PINNED_MODEL
    endpoint = OPENAI_ENDPOINT_POLICY

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
            not (1 <= len(images) <= MAX_IMAGE_ATTACHMENTS)
            or not (1 <= max_output_tokens <= 16_384)
            or not (1 <= timeout_ms <= 120_000)
        ):
            raise ProviderContractError("invalid_request")
        user_content: list[dict[str, object]] = []
        if prompt.user_intent is not None:
            user_content.append({"type": "input_text", "text": prompt.user_intent})
        user_content.append(
            {
                "type": "input_text",
                "text": f"Governed project context JSON:\n{structured_context}",
            }
        )
        for image in images:
            image.validate()
            encoded = base64.b64encode(image.content).decode("ascii")
            user_content.append(
                {
                    "type": "input_image",
                    "detail": "high",
                    "image_url": f"data:{image.media_type};base64,{encoded}",
                }
            )
        body: dict[str, object] = {
            "model": self.model_id,
            "input": [
                {
                    "role": "developer",
                    "content": [
                        {"type": "input_text", "text": prompt.system_prompt},
                        {
                            "type": "input_text",
                            "text": (
                                "Generate all provider-authored Paint Plan content in "
                                f"{prompt.generation_locale}. Preserve user-authored "
                                "labels and notes."
                            ),
                        },
                    ],
                },
                {"role": "user", "content": user_content},
            ],
            "max_output_tokens": max_output_tokens,
            "store": False,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "paint_plan_v1",
                    "strict": True,
                    "schema": dict(response_schema),
                }
            },
        }
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
        request_id = _safe_provider_request_id(response.provider_request_id)
        usage = _normalized_usage(response.body)

        def dispatched_error(
            category: ProviderErrorCategory,
            *,
            retryable: bool = False,
        ) -> ProviderContractError:
            return ProviderContractError(
                category,
                retryable=retryable,
                dispatch_certainty="dispatched",
                provider_request_id_status=("provided" if request_id else "unavailable"),
                provider_request_id=request_id,
                usage_measurement_status=usage.measurement_status,
                input_units=usage.input_units,
                output_units=usage.output_units,
            )

        if response.status_code < 200 or response.status_code >= 300:
            if response.status_code in (401, 403):
                raise dispatched_error("authentication_failed")
            if response.status_code == 429:
                raise dispatched_error("rate_limited", retryable=True)
            if response.status_code >= 500:
                raise dispatched_error("provider_unavailable", retryable=True)
            raise dispatched_error("invalid_request")
        parsed = _parse_output_json(response.body)
        if parsed is _JSON_PARSE_FAILED:
            raise dispatched_error("schema_invalid")
        if not isinstance(parsed, dict):
            raise dispatched_error("schema_invalid")
        return NormalizedProviderResult(
            output=MappingProxyType(parsed),
            usage=usage,
            provider_request_id_status="provided" if request_id else "unavailable",
            provider_request_id=request_id,
        )

    def estimate_cost(
        self,
        *,
        prompt: GovernedMultimodalPrompt,
        images: Sequence[PreparedImageAttachment],
        response_schema: Mapping[str, object],
        max_output_tokens: int,
    ) -> ProviderCostEstimate:
        for image in images:
            image.validate()
        return self.estimate_cost_from_dimensions(
            prompt=prompt,
            image_dimensions=[(image.width, image.height) for image in images],
            response_schema=response_schema,
            max_output_tokens=max_output_tokens,
        )

    def estimate_cost_from_dimensions(
        self,
        *,
        prompt: GovernedMultimodalPrompt,
        image_dimensions: Sequence[tuple[int, int]],
        response_schema: Mapping[str, object],
        max_output_tokens: int,
    ) -> ProviderCostEstimate:
        """Estimate from governed metadata without opening private image bytes."""

        if not (1 <= len(image_dimensions) <= MAX_IMAGE_ATTACHMENTS) or not (
            1 <= max_output_tokens <= 16_384
        ):
            raise ProviderContractError("invalid_request")
        # One input unit per UTF-8 byte, including the exact response schema and a
        # bounded wire wrapper, is intentionally conservative before live tokenizer
        # and model-revision verification are authorized.
        prompt_units, _ = _prompt_contract_units(prompt, response_schema)
        image_units = 0
        for width, height in image_dimensions:
            if not (1 <= width <= 8192 and 1 <= height <= 8192):
                raise ProviderContractError("invalid_request")
            patches = math.ceil(width / 32) * math.ceil(height / 32)
            bounded_patches = min(patches, OPENAI_HIGH_DETAIL_PATCH_BUDGET)
            image_units += math.ceil(
                bounded_patches
                * OPENAI_MINI_PATCH_MULTIPLIER_NUMERATOR
                / OPENAI_MINI_PATCH_MULTIPLIER_DENOMINATOR
            )
        input_upper = prompt_units + image_units
        numerator = (
            input_upper * OPENAI_INPUT_CENTS_PER_MILLION
            + max_output_tokens * OPENAI_OUTPUT_CENTS_PER_MILLION
        )
        amount = max(1, math.ceil(numerator / 1_000_000))
        return ProviderCostEstimate(
            measurement_status="estimated",
            input_units_upper_bound=input_upper,
            output_units_upper_bound=max_output_tokens,
            amount_minor_units_upper_bound=amount,
        )
