"""Bounded readiness probes for private storage and the selected identity provider."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from time import perf_counter_ns
from typing import Literal

from creativedeploy_api.auth.oidc import (
    OidcClient,
    OidcProtocolError,
    OidcProviderUnavailableError,
)
from creativedeploy_api.storage.images import ImageStorageError, ImageStoragePort

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class RuntimeDependencyHealthResult:
    status: Literal["ok", "error"]
    latency_ms: float | None
    error_code: Literal["STORAGE_UNAVAILABLE", "IDENTITY_PROVIDER_UNAVAILABLE"] | None


class StorageHealthService:
    def __init__(self, storage: ImageStoragePort, *, timeout_seconds: float) -> None:
        self._storage = storage
        self._timeout_seconds = timeout_seconds

    async def check(self) -> RuntimeDependencyHealthResult:
        started_at = perf_counter_ns()
        try:
            async with asyncio.timeout(self._timeout_seconds):
                await asyncio.to_thread(self._storage.probe)
        except (TimeoutError, OSError, ImageStorageError) as error:
            logger.warning(
                "Private storage readiness failed",
                extra={"event": "storage_readiness_failed", "error_type": type(error).__name__},
            )
            return RuntimeDependencyHealthResult(
                status="error",
                latency_ms=None,
                error_code="STORAGE_UNAVAILABLE",
            )
        latency_ms = max((perf_counter_ns() - started_at) / 1_000_000, 0.0)
        return RuntimeDependencyHealthResult("ok", round(latency_ms, 2), None)


class IdentityHealthService:
    def __init__(self, oidc_client: OidcClient | None, *, timeout_seconds: float) -> None:
        self._oidc_client = oidc_client
        self._timeout_seconds = timeout_seconds

    async def check(self) -> RuntimeDependencyHealthResult:
        if self._oidc_client is None:
            return RuntimeDependencyHealthResult("ok", 0.0, None)
        started_at = perf_counter_ns()
        try:
            async with asyncio.timeout(self._timeout_seconds):
                await self._oidc_client.discovery()
        except (TimeoutError, OidcProtocolError, OidcProviderUnavailableError) as error:
            logger.warning(
                "Identity provider readiness failed",
                extra={"event": "identity_readiness_failed", "error_type": type(error).__name__},
            )
            return RuntimeDependencyHealthResult(
                status="error",
                latency_ms=None,
                error_code="IDENTITY_PROVIDER_UNAVAILABLE",
            )
        latency_ms = max((perf_counter_ns() - started_at) / 1_000_000, 0.0)
        return RuntimeDependencyHealthResult("ok", round(latency_ms, 2), None)
