"""Strict request-host and private API cache boundaries."""

from ipaddress import ip_address

from starlette.datastructures import Headers, MutableHeaders
from starlette.responses import PlainTextResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from creativedeploy_api.core.config import canonical_trusted_host


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
