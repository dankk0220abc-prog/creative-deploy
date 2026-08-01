"""Strict host, origin, correlation, and private API cache boundaries."""

import logging
import uuid
from ipaddress import ip_address
from time import perf_counter_ns
from urllib.parse import urlparse

from starlette.datastructures import Headers, MutableHeaders
from starlette.responses import PlainTextResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from creativedeploy_api.core.config import canonical_trusted_host

logger = logging.getLogger(__name__)
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})


def _request_host(value: str) -> str:
    candidate = value.strip()
    if not candidate or candidate != value or "," in candidate:
        raise ValueError("invalid host")
    if candidate.startswith("["):
        closing = candidate.find("]")
        if closing < 0:
            raise ValueError("invalid host")
        host = candidate[1:closing]
        suffix = candidate[closing + 1 :]
        if suffix:
            if not suffix.startswith(":") or not suffix[1:].isdigit():
                raise ValueError("invalid host")
            port = int(suffix[1:])
            if not 1 <= port <= 65_535:
                raise ValueError("invalid host")
        try:
            return ip_address(host).compressed.lower()
        except ValueError as error:
            raise ValueError("invalid host") from error
    if candidate.count(":") == 1:
        host, port_text = candidate.rsplit(":", 1)
        if not port_text.isdigit() or not 1 <= int(port_text) <= 65_535:
            raise ValueError("invalid host")
        candidate = host
    return canonical_trusted_host(candidate)


class ExactTrustedHostMiddleware:
    """Accept only canonical equivalents of explicitly configured exact hosts."""

    def __init__(self, app: ASGIApp, allowed_hosts: list[str]) -> None:
        self.app = app
        self.allowed_hosts = frozenset(allowed_hosts)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return
        headers = Headers(scope=scope)
        host_values = headers.getlist("host")
        forwarded_values = headers.getlist("x-forwarded-host")
        try:
            if len(host_values) != 1:
                raise ValueError("invalid host")
            host = _request_host(host_values[0])
            if host not in self.allowed_hosts:
                raise ValueError("invalid host")
            if forwarded_values and (
                len(forwarded_values) != 1 or _request_host(forwarded_values[0]) != host
            ):
                raise ValueError("invalid forwarded host")
        except ValueError:
            response = PlainTextResponse(
                "Invalid host header",
                status_code=400,
                headers={"Cache-Control": "no-store"},
            )
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)


def _canonical_authority(value: str, *, scheme: str) -> str:
    if not value or value != value.strip() or "," in value or "/" in value:
        raise ValueError("invalid authority")
    parsed = urlparse(f"//{value}")
    if parsed.hostname is None or parsed.username is not None or parsed.password is not None:
        raise ValueError("invalid authority")
    host = canonical_trusted_host(parsed.hostname)
    try:
        port = parsed.port
    except ValueError as error:
        raise ValueError("invalid authority") from error
    default_port = 443 if scheme == "https" else 80
    if port is None or port == default_port:
        return f"[{host}]" if ":" in host else host
    return f"[{host}]:{port}" if ":" in host else f"{host}:{port}"


class ExactPublicOriginMiddleware:
    """Enforce one configured authority and one exact CSRF origin at the API edge."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        public_origin: str,
        require_csrf_origin: bool,
    ) -> None:
        self.app = app
        self.public_origin = public_origin
        parsed = urlparse(public_origin)
        self.scheme = parsed.scheme
        self.authority = _canonical_authority(parsed.netloc, scheme=parsed.scheme)
        self.require_csrf_origin = require_csrf_origin

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return
        headers = Headers(scope=scope)
        try:
            if headers.getlist("forwarded"):
                raise ValueError("Forwarded is not accepted")
            host_values = headers.getlist("host")
            if len(host_values) != 1 or (
                _canonical_authority(host_values[0], scheme=self.scheme) != self.authority
            ):
                raise ValueError("Host does not match PUBLIC_ORIGIN")
            forwarded_hosts = headers.getlist("x-forwarded-host")
            if forwarded_hosts and (
                len(forwarded_hosts) != 1
                or _canonical_authority(forwarded_hosts[0], scheme=self.scheme) != self.authority
            ):
                raise ValueError("forwarded host does not match PUBLIC_ORIGIN")
            forwarded_protocols = headers.getlist("x-forwarded-proto")
            if forwarded_protocols and (
                len(forwarded_protocols) != 1 or forwarded_protocols[0] != self.scheme
            ):
                raise ValueError("forwarded protocol does not match PUBLIC_ORIGIN")
            if (
                self.require_csrf_origin
                and scope["type"] == "http"
                and scope["method"] not in SAFE_METHODS
                and scope["path"].startswith("/api/")
            ):
                origins = headers.getlist("origin")
                if len(origins) != 1 or origins[0] != self.public_origin:
                    raise ValueError("unsafe API request origin mismatch")
        except ValueError:
            response = PlainTextResponse(
                "Invalid request origin",
                status_code=400,
                headers={"Cache-Control": "no-store"},
            )
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)


class RequestCorrelationMiddleware:
    """Bind every response and structured request log to one UUID correlation ID."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = Headers(scope=scope)
        inbound_values = headers.getlist("x-request-id")
        request_id: uuid.UUID
        try:
            if len(inbound_values) != 1:
                raise ValueError
            request_id = uuid.UUID(inbound_values[0])
        except (ValueError, AttributeError):
            request_id = uuid.uuid4()
        scope.setdefault("state", {})["request_id"] = request_id
        started_at = perf_counter_ns()
        status_code = 500

        async def send_with_correlation(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = int(message["status"])
                response_headers = MutableHeaders(scope=message)
                response_headers["x-request-id"] = str(request_id)
            await send(message)

        try:
            await self.app(scope, receive, send_with_correlation)
        finally:
            duration_ms = max((perf_counter_ns() - started_at) / 1_000_000, 0.0)
            logger.info(
                "HTTP request completed",
                extra={
                    "event": "http_request_completed",
                    "request_id": str(request_id),
                    "method": scope["method"],
                    "path": scope["path"],
                    "status_code": status_code,
                    "duration_ms": round(duration_ms, 2),
                },
            )


class PrivateApiNoStoreMiddleware:
    """Add no-store to every API response without weakening stricter values."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not scope["path"].startswith("/api/"):
            await self.app(scope, receive, send)
            return

        async def send_with_no_store(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                existing = headers.get("cache-control", "")
                if "no-store" not in existing.lower():
                    headers["cache-control"] = "no-store"
            await send(message)

        await self.app(scope, receive, send_with_no_store)
