"""Project-owned development/test OIDC provider with synthetic users only."""

import asyncio
import base64
import hmac
import html
import json
import secrets
import time
from dataclasses import dataclass
from typing import Annotated
from urllib.parse import urlencode, urlparse

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import Cookie, FastAPI, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from creativedeploy_api.auth.oidc import pkce_challenge, random_urlsafe, sha256_text


class SyntheticUser(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)

    subject: Annotated[str, Field(min_length=1, max_length=255)]
    name: Annotated[str, Field(min_length=1, max_length=200)]
    email: Annotated[str, Field(min_length=3, max_length=320)]


class LocalOidcSettings(BaseSettings):
    """Isolated settings; this provider refuses production explicitly."""

    model_config = SettingsConfigDict(
        env_prefix="LOCAL_OIDC_",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: str | None = Field(default=None, validation_alias="APP_ENV")
    issuer: str
    client_id: str
    client_secret: SecretStr
    redirect_uri: str
    users_json: str
    code_ttl_seconds: int = Field(default=120, ge=30, le=300)
    request_ttl_seconds: int = Field(default=300, ge=60, le=600)

    @model_validator(mode="after")
    def validate_boundary(self) -> "LocalOidcSettings":
        if self.app_env not in {"development", "test"}:
            raise ValueError("The project-owned OIDC provider is development/test only.")
        for field_name, value in (
            ("LOCAL_OIDC_ISSUER", self.issuer),
            ("LOCAL_OIDC_REDIRECT_URI", self.redirect_uri),
        ):
            parts = urlparse(value)
            if parts.scheme != "http" or not parts.netloc:
                raise ValueError(f"{field_name} must be an absolute local HTTP URL.")
            if parts.hostname not in {"127.0.0.1", "localhost"}:
                raise ValueError(f"{field_name} must use a loopback hostname.")
        try:
            users_payload = json.loads(self.users_json)
            users = [SyntheticUser.model_validate(item) for item in users_payload]
        except (TypeError, ValueError) as error:
            raise ValueError("LOCAL_OIDC_USERS_JSON must contain valid synthetic users.") from error
        if len(users) < 1 or len({user.subject for user in users}) != len(users):
            raise ValueError("Synthetic OIDC subjects must be non-empty and unique.")
        return self

    def users(self) -> tuple[SyntheticUser, ...]:
        payload = json.loads(self.users_json)
        return tuple(SyntheticUser.model_validate(item) for item in payload)


@dataclass(frozen=True, slots=True)
class PendingAuthorization:
    client_id: str
    redirect_uri: str
    state: str
    nonce: str
    code_challenge: str
    csrf_token_hash: str
    expires_at: float


@dataclass(frozen=True, slots=True)
class AuthorizationCode:
    client_id: str
    redirect_uri: str
    subject: str
    nonce: str
    code_challenge: str
    expires_at: float


def _integer_b64(value: int) -> str:
    size = (value.bit_length() + 7) // 8
    return base64.urlsafe_b64encode(value.to_bytes(size, "big")).rstrip(b"=").decode()


def create_local_oidc_app(
    settings: LocalOidcSettings | None = None,
) -> FastAPI:
    """Create one ephemeral signing-key provider for synthetic local identities."""
    resolved = settings or LocalOidcSettings.model_validate({})
    users = {user.subject: user for user in resolved.users()}
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_numbers = private_key.public_key().public_numbers()
    key_id = secrets.token_hex(12)
    pending: dict[str, PendingAuthorization] = {}
    codes: dict[str, AuthorizationCode] = {}
    lock = asyncio.Lock()

    app = FastAPI(
        title="PaintPilot Local OIDC Provider",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    @app.get("/.well-known/openid-configuration")
    async def discovery() -> JSONResponse:
        return JSONResponse(
            {
                "issuer": resolved.issuer,
                "authorization_endpoint": f"{resolved.issuer}/authorize",
                "token_endpoint": f"{resolved.issuer}/token",
                "jwks_uri": f"{resolved.issuer}/jwks",
                "response_types_supported": ["code"],
                "subject_types_supported": ["public"],
                "id_token_signing_alg_values_supported": ["RS256"],
                "scopes_supported": ["openid", "profile", "email"],
                "token_endpoint_auth_methods_supported": ["client_secret_basic"],
                "code_challenge_methods_supported": ["S256"],
            },
            headers={"Cache-Control": "no-store"},
        )

    @app.get("/jwks")
    async def jwks() -> JSONResponse:
        return JSONResponse(
            {
                "keys": [
                    {
                        "kty": "RSA",
                        "use": "sig",
                        "alg": "RS256",
                        "kid": key_id,
                        "n": _integer_b64(public_numbers.n),
                        "e": _integer_b64(public_numbers.e),
                    }
                ]
            },
            headers={"Cache-Control": "no-store"},
        )

    @app.get("/authorize", response_class=HTMLResponse)
    async def authorize(
        response_type: str,
        client_id: str,
        redirect_uri: str,
        scope: str,
        state: str,
        nonce: str,
        code_challenge: str,
        code_challenge_method: str,
    ) -> HTMLResponse:
        if (
            response_type != "code"
            or client_id != resolved.client_id
            or redirect_uri != resolved.redirect_uri
            or "openid" not in scope.split()
            or code_challenge_method != "S256"
            or not 32 <= len(state) <= 256
            or not 32 <= len(nonce) <= 256
            or len(code_challenge) != 43
        ):
            raise HTTPException(status_code=400, detail="invalid_request")
        request_id = random_urlsafe()
        csrf_token = random_urlsafe()
        async with lock:
            pending[sha256_text(request_id)] = PendingAuthorization(
                client_id=client_id,
                redirect_uri=redirect_uri,
                state=state,
                nonce=nonce,
                code_challenge=code_challenge,
                csrf_token_hash=sha256_text(csrf_token),
                expires_at=time.time() + resolved.request_ttl_seconds,
            )
        choices = "".join(
            (
                '<button type="submit" name="subject" '
                f'value="{html.escape(user.subject, quote=True)}">'
                f"{html.escape(user.name)} — {html.escape(user.email)}</button>"
            )
            for user in users.values()
        )
        page = (
            '<!doctype html><html><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            "<title>PaintPilot local sign in</title></head><body>"
            "<main><h1>PaintPilot local sign in</h1>"
            "<p>Synthetic development/test users only.</p>"
            '<form method="post" action="/authorize">'
            f'<input type="hidden" name="request_id" value="{html.escape(request_id)}">'
            f'<input type="hidden" name="csrf_token" value="{html.escape(csrf_token)}">'
            f"{choices}</form></main></body></html>"
        )
        response = HTMLResponse(page, headers={"Cache-Control": "no-store"})
        response.set_cookie(
            "paintpilot_local_oidc_csrf",
            csrf_token,
            max_age=resolved.request_ttl_seconds,
            httponly=True,
            secure=False,
            samesite="lax",
            path="/",
        )
        return response

    @app.post("/authorize")
    async def authorize_complete(
        request_id: Annotated[str, Form(min_length=32, max_length=256)],
        csrf_token: Annotated[str, Form(min_length=32, max_length=256)],
        subject: Annotated[str, Form(min_length=1, max_length=255)],
        csrf_cookie: Annotated[
            str | None,
            Cookie(alias="paintpilot_local_oidc_csrf"),
        ] = None,
    ) -> RedirectResponse:
        if (
            csrf_cookie is None
            or not hmac.compare_digest(csrf_cookie, csrf_token)
            or subject not in users
        ):
            raise HTTPException(status_code=400, detail="invalid_request")
        async with lock:
            authorization = pending.pop(sha256_text(request_id), None)
        if (
            authorization is None
            or authorization.expires_at <= time.time()
            or not hmac.compare_digest(
                authorization.csrf_token_hash,
                sha256_text(csrf_token),
            )
        ):
            raise HTTPException(status_code=400, detail="invalid_request")
        code = random_urlsafe(48)
        async with lock:
            codes[sha256_text(code)] = AuthorizationCode(
                client_id=authorization.client_id,
                redirect_uri=authorization.redirect_uri,
                subject=subject,
                nonce=authorization.nonce,
                code_challenge=authorization.code_challenge,
                expires_at=time.time() + resolved.code_ttl_seconds,
            )
        redirect = f"{authorization.redirect_uri}?" + urlencode(
            {"code": code, "state": authorization.state}
        )
        response = RedirectResponse(redirect, status_code=status.HTTP_303_SEE_OTHER)
        response.delete_cookie("paintpilot_local_oidc_csrf", path="/")
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.post("/token")
    async def token(
        request: Request,
        grant_type: Annotated[str, Form()],
        code: Annotated[str, Form(min_length=32, max_length=512)],
        redirect_uri: Annotated[str, Form()],
        code_verifier: Annotated[str, Form(min_length=43, max_length=128)],
    ) -> JSONResponse:
        authorization = request.headers.get("Authorization", "")
        try:
            scheme, encoded = authorization.split(" ", 1)
            decoded = base64.b64decode(encoded, validate=True).decode("utf-8")
            client_id, client_secret = decoded.split(":", 1)
        except (ValueError, UnicodeError):
            raise HTTPException(status_code=401, detail="invalid_client") from None
        if (
            scheme != "Basic"
            or not hmac.compare_digest(client_id, resolved.client_id)
            or not hmac.compare_digest(
                client_secret,
                resolved.client_secret.get_secret_value(),
            )
            or grant_type != "authorization_code"
        ):
            raise HTTPException(status_code=401, detail="invalid_client")
        async with lock:
            code_record = codes.pop(sha256_text(code), None)
        if (
            code_record is None
            or code_record.expires_at <= time.time()
            or redirect_uri != code_record.redirect_uri
            or client_id != code_record.client_id
            or not hmac.compare_digest(
                pkce_challenge(code_verifier),
                code_record.code_challenge,
            )
        ):
            raise HTTPException(status_code=400, detail="invalid_grant")
        user = users[code_record.subject]
        now = int(time.time())
        id_token = jwt.encode(
            {
                "iss": resolved.issuer,
                "sub": user.subject,
                "aud": resolved.client_id,
                "exp": now + 300,
                "iat": now,
                "nbf": now,
                "nonce": code_record.nonce,
                "name": user.name,
                "email": user.email.lower(),
            },
            private_key,
            algorithm="RS256",
            headers={"kid": key_id},
        )
        return JSONResponse(
            {
                "access_token": random_urlsafe(32),
                "token_type": "Bearer",
                "expires_in": 300,
                "id_token": id_token,
            },
            headers={
                "Cache-Control": "no-store",
                "Pragma": "no-cache",
            },
        )

    return app


app = create_local_oidc_app()
