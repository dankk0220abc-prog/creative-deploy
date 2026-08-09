"""Deterministic local Fixture Provider with no network-capable dependencies."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Literal

from creativedeploy_api.ai.constants import FIXTURE_CURRENCY, FIXTURE_PROVIDER_KEY
from creativedeploy_api.ai.encryption import SecretBytes


@dataclass(frozen=True, slots=True)
class FixtureValidation:
    valid: bool
    status: Literal["fixture_valid", "fixture_invalid"]
    message_code: str


@dataclass(frozen=True, slots=True)
class FixtureInvocationResult:
    output: dict[str, object]
    input_units: int
    output_units: int
    cost_minor_units: int
    currency: str = FIXTURE_CURRENCY


class FixtureProviderError(RuntimeError):
    def __init__(self, category: str) -> None:
        super().__init__("Fixture provider scenario failed.")
        self.category = category


class FixtureProviderAdapter:
    """Pure deterministic adapter; it never constructs HTTP/socket/proxy state."""

    provider_key = FIXTURE_PROVIDER_KEY
    adapter_version = "fixture-adapter-v1"

    def validate_credential(self, secret: SecretBytes) -> FixtureValidation:
        value = secret.value
        valid = value.startswith(b"fixture-sk-") and 20 <= len(value) <= 160
        return FixtureValidation(
            valid=valid,
            status="fixture_valid" if valid else "fixture_invalid",
            message_code="FIXTURE_CREDENTIAL_ACCEPTED" if valid else "FIXTURE_CREDENTIAL_REJECTED",
        )

    def invoke(
        self,
        payload: dict[str, object],
        secret: SecretBytes,
        *,
        scenario: str = "success",
    ) -> FixtureInvocationResult:
        if not self.validate_credential(secret).valid:
            raise FixtureProviderError("authentication_failed")
        if scenario != "success":
            allowed = {
                "authentication_failed",
                "invalid_request",
                "provider_unavailable",
                "rate_limited",
                "outcome_unknown",
            }
            raise FixtureProviderError(scenario if scenario in allowed else "invalid_request")
        encoded = repr(sorted(payload.items())).encode("utf-8")
        digest = hashlib.sha256(encoded).hexdigest()
        input_units = max(1, len(encoded) // 8)
        output_units = 12
        return FixtureInvocationResult(
            output={
                "fixture": True,
                "local_only": True,
                "result_id": f"fixture-{digest[:16]}",
                "summary": "Deterministic local fixture response",
            },
            input_units=input_units,
            output_units=output_units,
            cost_minor_units=input_units + output_units,
        )
