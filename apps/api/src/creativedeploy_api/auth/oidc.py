"""Provider-neutral OIDC Authorization Code plus PKCE client."""

import base64
import hashlib
import hmac
import math
import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import httpx
import jwt
from jwt import InvalidTokenError, PyJWK


class OidcProtocolError(RuntimeError):
    """An OIDC response failed the configured protocol or claim contract."""


class OidcProviderUnavailableError(RuntimeError):
    """Discovery, JWKS, or token exchange could not reach the provider."""


@dataclass(frozen=True, slots=True)
class OidcClaims:
    """Only the verified identity/profile claims consumed by the application."""

    issuer: str
    subject: str
    display_name: str
    email: str | None


def random_urlsafe(bytes_count: int = 32) -> str:
    """Return a high-entropy URL-safe value without padding."""
    return secrets.token_urlsafe(bytes_count)


def sha256_text(value: str) -> str:
    """Return the lowercase SHA-256 digest of one opaque value."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def pkce_challenge(verifier: str) -> str:
    """Return an RFC 7636 S256 code challenge."""
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


class OidcClient:
    """Strict confidential OIDC client with explicit discovery and JWKS validation."""

    def __init__(
        self,
        *,
        issuer: str,
        discovery_url: str,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        timeout_seconds: float,
        id_token_max_age_seconds: int = 300,
        clock_skew_seconds: int = 30,
        backchannel_base_url: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        time_provider: Callable[[], float] = time.time,
    ) -> None:
        if not 60 <= id_token_max_age_seconds <= 900:
            raise ValueError("OIDC ID token maximum age must be between 60 and 900 seconds.")
        if not 0 <= clock_skew_seconds <= 60:
            raise ValueError("OIDC clock skew must be between 0 and 60 seconds.")
        self.issuer = issuer
        self.discovery_url = discovery_url
        self.client_id = client_id
        self._client_secret = client_secret
        self.redirect_uri = redirect_uri
        self._timeout = timeout_seconds
        self._id_token_max_age_seconds = id_token_max_age_seconds
        self._clock_skew_seconds = clock_skew_seconds
        self._backchannel_base_url = backchannel_base_url
        self._transport = transport
        self._time_provider = time_provider

    def _validate_time_claims(self, claims: dict[str, Any], *, now: float) -> None:
        """Validate all NumericDate claims against one captured current time."""

        def numeric_date(name: str) -> float:
            value = claims.get(name)
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(float(value))
            ):
                raise OidcProtocolError("OIDC ID token validation failed.")
            return float(value)

        issued_at = numeric_date("iat")
        expires_at = numeric_date("exp")
        not_before = numeric_date("nbf") if "nbf" in claims else None
        skew = float(self._clock_skew_seconds)
        if (
            issued_at > now + skew
            or now - issued_at > self._id_token_max_age_seconds
            or expires_at <= now - skew
            or (not_before is not None and not_before > now + skew)
        ):
            raise OidcProtocolError("OIDC ID token validation failed.")

    def _backchannel_url(self, url: str) -> str:
        if self._backchannel_base_url is None:
            return url
        if url == self.issuer:
            return self._backchannel_base_url
        prefix = f"{self.issuer}/"
        if not url.startswith(prefix):
            raise OidcProtocolError("OIDC endpoint is outside the configured issuer.")
        return f"{self._backchannel_base_url}/{url.removeprefix(prefix)}"

    async def _get_json(self, url: str) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout,
                follow_redirects=False,
                transport=self._transport,
            ) as client:
                response = await client.get(url, headers={"Accept": "application/json"})
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise OidcProviderUnavailableError from error
        if not isinstance(payload, dict):
            raise OidcProtocolError("OIDC JSON response must be an object.")
        return payload

    async def discovery(self) -> dict[str, Any]:
        """Load and strictly validate the minimum discovery metadata."""
        metadata = await self._get_json(self._backchannel_url(self.discovery_url))
        if metadata.get("issuer") != self.issuer:
            raise OidcProtocolError("OIDC discovery issuer does not match configuration.")
        required_urls = ("authorization_endpoint", "token_endpoint", "jwks_uri")
        if any(not isinstance(metadata.get(name), str) for name in required_urls):
            raise OidcProtocolError("OIDC discovery is missing a required endpoint.")
        methods = metadata.get("code_challenge_methods_supported")
        if not isinstance(methods, list) or "S256" not in methods:
            raise OidcProtocolError("OIDC provider does not advertise PKCE S256.")
        return metadata

    async def authorization_url(
        self,
        *,
        state: str,
        nonce: str,
        code_challenge: str,
    ) -> str:
        """Build the exact browser authorization redirect."""
        metadata = await self.discovery()
        endpoint = metadata["authorization_endpoint"]
        assert isinstance(endpoint, str)
        query = urlencode(
            {
                "response_type": "code",
                "client_id": self.client_id,
                "redirect_uri": self.redirect_uri,
                "scope": "openid profile email",
                "state": state,
                "nonce": nonce,
                "code_challenge": code_challenge,
                "code_challenge_method": "S256",
            }
        )
        return f"{endpoint}?{query}"

    async def exchange_and_validate(
        self,
        *,
        code: str,
        code_verifier: str,
        expected_nonce: str,
    ) -> OidcClaims:
        """Exchange one code and validate signature plus all authorization claims."""
        metadata = await self.discovery()
        token_endpoint = metadata["token_endpoint"]
        assert isinstance(token_endpoint, str)
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout,
                follow_redirects=False,
                transport=self._transport,
            ) as client:
                response = await client.post(
                    self._backchannel_url(token_endpoint),
                    data={
                        "grant_type": "authorization_code",
                        "code": code,
                        "redirect_uri": self.redirect_uri,
                        "code_verifier": code_verifier,
                    },
                    auth=(self.client_id, self._client_secret),
                    headers={"Accept": "application/json"},
                )
                response.raise_for_status()
                token_payload = response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise OidcProviderUnavailableError from error
        if not isinstance(token_payload, dict):
            raise OidcProtocolError("OIDC token response must be an object.")
        id_token = token_payload.get("id_token")
        if not isinstance(id_token, str) or not id_token:
            raise OidcProtocolError("OIDC token response did not contain an ID token.")

        try:
            header = jwt.get_unverified_header(id_token)
        except InvalidTokenError as error:
            raise OidcProtocolError("OIDC ID token header is invalid.") from error
        if header.get("alg") != "RS256" or not isinstance(header.get("kid"), str):
            raise OidcProtocolError("OIDC ID token must use an identified RS256 key.")
        jwks_uri = metadata["jwks_uri"]
        assert isinstance(jwks_uri, str)
        jwks = await self._get_json(self._backchannel_url(jwks_uri))
        keys = jwks.get("keys")
        if not isinstance(keys, list):
            raise OidcProtocolError("OIDC JWKS did not contain keys.")
        matching = [
            key for key in keys if isinstance(key, dict) and key.get("kid") == header["kid"]
        ]
        if len(matching) != 1:
            raise OidcProtocolError("OIDC signing key could not be selected uniquely.")
        try:
            validation_time = float(self._time_provider())
            if not math.isfinite(validation_time):
                raise ValueError("OIDC validation clock was invalid.")
            signing_key = PyJWK.from_dict(matching[0]).key
            claims = jwt.decode(
                id_token,
                key=signing_key,
                algorithms=["RS256"],
                audience=self.client_id,
                issuer=self.issuer,
                options={
                    "require": ["iss", "sub", "aud", "exp", "iat", "nonce"],
                    "verify_signature": True,
                    "verify_exp": False,
                    "verify_nbf": False,
                    "verify_iat": False,
                    "verify_aud": True,
                    "verify_iss": True,
                },
            )
            self._validate_time_claims(claims, now=validation_time)
        except (InvalidTokenError, ValueError, TypeError) as error:
            raise OidcProtocolError("OIDC ID token validation failed.") from error
        nonce = claims.get("nonce")
        if not isinstance(nonce, str) or not hmac.compare_digest(nonce, expected_nonce):
            raise OidcProtocolError("OIDC nonce validation failed.")
        subject = claims.get("sub")
        if not isinstance(subject, str) or not 1 <= len(subject.strip()) <= 255:
            raise OidcProtocolError("OIDC subject is invalid.")
        if subject != subject.strip():
            raise OidcProtocolError("OIDC subject is not normalized.")
        name_claim = claims.get("name") or claims.get("preferred_username")
        if not isinstance(name_claim, str) or not 1 <= len(name_claim.strip()) <= 200:
            raise OidcProtocolError("OIDC display name is invalid.")
        display_name = name_claim.strip()
        email_claim = claims.get("email")
        email: str | None
        if email_claim is None:
            email = None
        elif (
            isinstance(email_claim, str)
            and 3 <= len(email_claim.strip()) <= 320
            and email_claim.strip() == email_claim
        ):
            email = email_claim.lower()
        else:
            raise OidcProtocolError("OIDC email claim is invalid.")
        return OidcClaims(
            issuer=self.issuer,
            subject=subject,
            display_name=display_name,
            email=email,
        )
