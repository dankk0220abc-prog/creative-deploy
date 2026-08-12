"""Protocol-level tests for the provider-neutral OIDC client."""

import asyncio
import json
from datetime import UTC, datetime
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm
from pydantic import ValidationError

from creativedeploy_api.auth.oidc import (
    OidcClient,
    OidcProtocolError,
    pkce_challenge,
    sha256_text,
)
from creativedeploy_api.core.config import Settings
from creativedeploy_api.services.identity import validated_return_to

ISSUER = "https://identity.example.test"
CLIENT_ID = "paintpilot-test-client"
CLIENT_SECRET = "synthetic-unit-secret"
REDIRECT_URI = "https://paintpilot.example.test/api/v1/auth/callback"
KID = "unit-signing-key"


@pytest.mark.parametrize(
    ("candidate", "expected"),
    [
        ("/paintpilot/projects", "/paintpilot/projects"),
        ("/arcana", "/arcana"),
        ("/arcana/readings/reading-id", "/arcana/readings/reading-id"),
        ("//arcana.example.test", "/paintpilot/projects"),
        ("/unknown", "/paintpilot/projects"),
    ],
)
def test_return_to_allows_only_supported_same_origin_product_routes(
    candidate: str,
    expected: str,
) -> None:
    assert validated_return_to(candidate) == expected


def _jwk(private_key: rsa.RSAPrivateKey, *, kid: str = KID) -> dict[str, Any]:
    payload = json.loads(RSAAlgorithm.to_jwk(private_key.public_key()))
    payload.update({"kid": kid, "use": "sig", "alg": "RS256"})
    return payload


def _token(
    private_key: rsa.RSAPrivateKey,
    *,
    now: int,
    issuer: str = ISSUER,
    audience: str = CLIENT_ID,
    nonce: str = "expected-nonce",
    expires_at: int | None = None,
    not_before: int | None = None,
    issued_at: Any = None,
    include_issued_at: bool = True,
    kid: str = KID,
) -> str:
    claims: dict[str, Any] = {
        "iss": issuer,
        "sub": "stable-subject",
        "aud": audience,
        "exp": expires_at if expires_at is not None else now + 300,
        "nonce": nonce,
        "name": "Synthetic Reviewer",
        "email": "REVIEWER@EXAMPLE.TEST",
    }
    if include_issued_at:
        claims["iat"] = now if issued_at is None else issued_at
    if not_before is not None:
        claims["nbf"] = not_before
    return jwt.encode(
        claims,
        private_key,
        algorithm="RS256",
        headers={"kid": kid},
    )


def _client_with_token(
    token: str,
    *,
    public_key: rsa.RSAPrivateKey,
    discovery_issuer: str = ISSUER,
    pkce_methods: list[str] | None = None,
    id_token_max_age_seconds: int = 300,
    clock_skew_seconds: int = 30,
    current_time: int | None = None,
) -> tuple[OidcClient, list[httpx.Request]]:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/.well-known/openid-configuration":
            return httpx.Response(
                200,
                json={
                    "issuer": discovery_issuer,
                    "authorization_endpoint": f"{ISSUER}/authorize",
                    "token_endpoint": f"{ISSUER}/token",
                    "jwks_uri": f"{ISSUER}/jwks",
                    "code_challenge_methods_supported": (
                        pkce_methods if pkce_methods is not None else ["S256"]
                    ),
                },
            )
        if request.url.path == "/token":
            return httpx.Response(200, json={"id_token": token})
        if request.url.path == "/jwks":
            return httpx.Response(200, json={"keys": [_jwk(public_key)]})
        return httpx.Response(404)

    client_kwargs: dict[str, Any] = {}
    if current_time is not None:
        client_kwargs["time_provider"] = lambda: float(current_time)
    return (
        OidcClient(
            issuer=ISSUER,
            discovery_url=f"{ISSUER}/.well-known/openid-configuration",
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            redirect_uri=REDIRECT_URI,
            timeout_seconds=1,
            id_token_max_age_seconds=id_token_max_age_seconds,
            clock_skew_seconds=clock_skew_seconds,
            transport=httpx.MockTransport(handler),
            **client_kwargs,
        ),
        requests,
    )


def test_pkce_and_authorization_redirect_bind_all_required_values() -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    now = int(datetime.now(UTC).timestamp())
    client, _ = _client_with_token(_token(private_key, now=now), public_key=private_key)

    authorization_url = asyncio.run(
        client.authorization_url(
            state="opaque-state",
            nonce="opaque-nonce",
            code_challenge=pkce_challenge("verifier"),
        )
    )
    query = parse_qs(urlparse(authorization_url).query)

    assert query == {
        "response_type": ["code"],
        "client_id": [CLIENT_ID],
        "redirect_uri": [REDIRECT_URI],
        "scope": ["openid profile email"],
        "state": ["opaque-state"],
        "nonce": ["opaque-nonce"],
        "code_challenge": [pkce_challenge("verifier")],
        "code_challenge_method": ["S256"],
    }
    assert pkce_challenge("verifier") == "iMnq5o6zALKXGivsnlom_0F5_WYda32GHkxlV7mq7hQ"
    assert sha256_text("opaque-state") == (
        "9092e69f5d988789c2e84fa61df3ded5217031ee6707982b9920685de7e7d75f"
    )


@pytest.mark.parametrize(
    ("claim_override", "override_value"),
    [
        ("issuer", "https://wrong-issuer.example.test"),
        ("audience", "wrong-client"),
        ("expires_at", 1),
        ("not_before", 4_102_444_800),
        ("nonce", "wrong-nonce"),
    ],
)
def test_exchange_rejects_untrusted_or_time_invalid_claims(
    claim_override: str,
    override_value: str | int,
) -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    now = int(datetime.now(UTC).timestamp())
    overrides = {claim_override: override_value}
    token = _token(private_key, now=now, **overrides)
    client, _ = _client_with_token(token, public_key=private_key)

    with pytest.raises(OidcProtocolError, match=r"validation failed|nonce validation failed"):
        asyncio.run(
            client.exchange_and_validate(
                code="one-time-code",
                code_verifier="verifier",
                expected_nonce="expected-nonce",
            )
        )


def test_exchange_rejects_invalid_signature_and_does_not_expose_secret(
    caplog: pytest.LogCaptureFixture,
) -> None:
    trusted_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    attacker_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    now = int(datetime.now(UTC).timestamp())
    attacker_token = _token(attacker_key, now=now)
    client, requests = _client_with_token(
        attacker_token,
        public_key=trusted_key,
    )

    with pytest.raises(OidcProtocolError) as captured:
        asyncio.run(
            client.exchange_and_validate(
                code="one-time-code",
                code_verifier="verifier",
                expected_nonce="expected-nonce",
            )
        )

    assert CLIENT_SECRET not in str(captured.value)
    token_request = next(request for request in requests if request.url.path == "/token")
    assert CLIENT_SECRET not in caplog.text
    assert attacker_token not in caplog.text
    assert token_request.headers["authorization"].startswith("Basic ")
    assert CLIENT_SECRET.encode() not in token_request.content


def test_exchange_rejects_exp_unexpired_id_token_with_stale_iat() -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    now = 2_000_000_000
    token = _token(private_key, now=now - 3_600, expires_at=now + 300)
    client, _ = _client_with_token(
        token,
        public_key=private_key,
        current_time=now,
    )

    with pytest.raises(OidcProtocolError, match="validation failed"):
        asyncio.run(
            client.exchange_and_validate(
                code="one-time-code",
                code_verifier="verifier",
                expected_nonce="expected-nonce",
            )
        )


@pytest.mark.parametrize(
    ("issued_at", "include_issued_at"),
    [
        (None, False),
        ("not-a-numeric-date", True),
        ([2_000_000_000], True),
    ],
)
def test_exchange_rejects_missing_or_non_numeric_iat(
    issued_at: Any,
    include_issued_at: bool,
) -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    now = 2_000_000_000
    token = _token(
        private_key,
        now=now,
        issued_at=issued_at,
        include_issued_at=include_issued_at,
    )
    client, _ = _client_with_token(token, public_key=private_key, current_time=now)

    with pytest.raises(OidcProtocolError, match="OIDC ID token validation failed"):
        asyncio.run(
            client.exchange_and_validate(
                code="one-time-code",
                code_verifier="verifier",
                expected_nonce="expected-nonce",
            )
        )


@pytest.mark.parametrize("issued_at", [2_000_000_031, 1_999_999_699])
def test_exchange_rejects_iat_beyond_future_skew_or_maximum_age(
    issued_at: int,
) -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    now = 2_000_000_000
    token = _token(private_key, now=now, issued_at=issued_at)
    client, _ = _client_with_token(token, public_key=private_key, current_time=now)

    with pytest.raises(OidcProtocolError, match="OIDC ID token validation failed"):
        asyncio.run(
            client.exchange_and_validate(
                code="one-time-code",
                code_verifier="verifier",
                expected_nonce="expected-nonce",
            )
        )


@pytest.mark.parametrize("issued_at", [1_999_999_700, 2_000_000_030, 2_000_000_000])
def test_exchange_accepts_fresh_and_exact_iat_age_or_clock_skew_boundaries(
    issued_at: int,
) -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    now = 2_000_000_000
    token = _token(private_key, now=now, issued_at=issued_at)
    client, _ = _client_with_token(token, public_key=private_key, current_time=now)

    claims = asyncio.run(
        client.exchange_and_validate(
            code="one-time-code",
            code_verifier="verifier",
            expected_nonce="expected-nonce",
        )
    )

    assert claims.subject == "stable-subject"


@pytest.mark.parametrize("maximum_age", [None, "", -1, 0, 901])
def test_oidc_id_token_maximum_age_cannot_be_disabled_or_unbounded(
    maximum_age: object,
) -> None:
    with pytest.raises(ValidationError):
        Settings(
            app_env="production",
            database_url="postgresql+psycopg://test:test@127.0.0.1:1/test",
            identity_provider="oidc",
            image_storage_provider="s3",
            oidc_id_token_max_age_seconds=maximum_age,
            _env_file=None,
        )


def test_oidc_time_boundaries_have_safe_documented_defaults() -> None:
    settings = Settings(
        app_env="test",
        database_url="postgresql+psycopg://test:test@127.0.0.1:1/test",
        paintpilot_demo_principal_id="owner",
        paintpilot_demo_principal_display_name="Owner",
        _env_file=None,
    )

    assert settings.oidc_id_token_max_age_seconds == 300
    assert settings.oidc_clock_skew_seconds == 30


def test_exchange_returns_only_normalized_verified_profile_claims() -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    now = int(datetime.now(UTC).timestamp())
    client, requests = _client_with_token(
        _token(private_key, now=now),
        public_key=private_key,
    )

    claims = asyncio.run(
        client.exchange_and_validate(
            code="one-time-code",
            code_verifier="verifier",
            expected_nonce="expected-nonce",
        )
    )

    assert claims.issuer == ISSUER
    assert claims.subject == "stable-subject"
    assert claims.display_name == "Synthetic Reviewer"
    assert claims.email == "reviewer@example.test"
    token_request = next(request for request in requests if request.url.path == "/token")
    form = parse_qs(token_request.content.decode())
    assert form == {
        "grant_type": ["authorization_code"],
        "code": ["one-time-code"],
        "redirect_uri": [REDIRECT_URI],
        "code_verifier": ["verifier"],
    }


@pytest.mark.parametrize(
    ("discovery_issuer", "pkce_methods"),
    [
        ("https://wrong-issuer.example.test", ["S256"]),
        (ISSUER, ["plain"]),
    ],
)
def test_discovery_fails_closed_on_issuer_or_pkce_mismatch(
    discovery_issuer: str,
    pkce_methods: list[str],
) -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    now = int(datetime.now(UTC).timestamp())
    client, _ = _client_with_token(
        _token(private_key, now=now),
        public_key=private_key,
        discovery_issuer=discovery_issuer,
        pkce_methods=pkce_methods,
    )

    with pytest.raises(OidcProtocolError):
        asyncio.run(client.discovery())
