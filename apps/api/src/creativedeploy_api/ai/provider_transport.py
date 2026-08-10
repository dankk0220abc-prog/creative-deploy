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
_JSON_PARSE_FAILED: Final = object()

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


@dataclass(frozen=True, slots=True)
class PreparedProviderRequest:
    provider_key: str
    model_id: str
    adapter_version: str
    endpoint: ProviderEndpointPolicy
    body: Mapping[str, object]
    response_limit_bytes: int
    timeout_ms: int
    cancellation_mode: Literal["local_wait_only_after_dispatch"]


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


@dataclass(frozen=True, slots=True)
class NormalizedProviderResult:
    output: Mapping[str, object]
    usage: NormalizedProviderUsage
    provider_request_id_status: Literal["provided", "unavailable"]
    provider_request_id: str | None


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
