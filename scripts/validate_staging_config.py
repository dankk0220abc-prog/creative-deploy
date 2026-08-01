#!/usr/bin/env python3
"""Validate the exact Phase 2B-2 synthetic staging deployment contract."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_SERVICES = {
    "api",
    "migrate",
    "minio",
    "oidc",
    "operations",
    "postgres",
    "role_grant",
    "role_provision",
    "tls_proxy",
    "web",
}
SECRET_ENVIRONMENT_NAMES = {
    "DATABASE_URL",
    "OIDC_CLIENT_SECRET",
    "S3_ACCESS_KEY_ID",
    "S3_SECRET_ACCESS_KEY",
    "DATABASE_MIGRATOR_PASSWORD",
    "DATABASE_RUNTIME_PASSWORD",
    "BACKUP_SIGNING_KEY",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"staging config validation failed: {message}")


def read(path: str) -> str:
    return (REPOSITORY_ROOT / path).read_text(encoding="utf-8")


def main() -> None:
    configuration = json.load(sys.stdin)
    services: dict[str, dict[str, Any]] = configuration["services"]
    require(set(services) == EXPECTED_SERVICES, "unexpected service topology")
    for service_name in EXPECTED_SERVICES - {"tls_proxy"}:
        require(
            "ports" not in services[service_name],
            f"{service_name} publishes a host port",
        )
    ports = services["tls_proxy"].get("ports", [])
    require(len(ports) == 2, "TLS proxy must publish exactly HTTP and HTTPS")
    require(
        {int(item["target"]) for item in ports} == {8080, 8443},
        "TLS proxy targets must be 8080 and 8443",
    )
    require(
        all(item.get("host_ip") == "127.0.0.1" for item in ports),
        "local staging ports must be loopback-only",
    )

    for service_name in (
        "api",
        "migrate",
        "oidc",
        "operations",
        "role_grant",
        "role_provision",
        "tls_proxy",
        "web",
    ):
        service = services[service_name]
        require(
            service.get("read_only") is True,
            f"{service_name} root filesystem is writable",
        )
        require(
            service.get("cap_drop") == ["ALL"],
            f"{service_name} does not drop capabilities",
        )
        require(
            "no-new-privileges:true" in service.get("security_opt", []),
            f"{service_name} permits privilege escalation",
        )

    require(
        services["migrate"]["build"]["target"] == "migration",
        "migrator image target is wrong",
    )
    require(
        services["api"]["build"]["target"] == "runtime", "API image target is wrong"
    )
    require(
        services["web"]["build"]["target"] == "staging-runtime",
        "Web staging target is wrong",
    )
    require(
        services["tls_proxy"]["build"]["target"] == "tls-proxy", "TLS target is wrong"
    )
    require(
        services["role_grant"]["depends_on"]["migrate"]["condition"]
        == "service_completed_successfully",
        "runtime grants must follow migration",
    )
    require(
        services["api"]["depends_on"]["role_grant"]["condition"]
        == "service_completed_successfully",
        "API must follow migration and grants",
    )
    require(
        services["web"]["depends_on"]["api"]["condition"] == "service_healthy",
        "Web must wait for API readiness",
    )
    require(
        services["tls_proxy"]["depends_on"]["web"]["condition"] == "service_healthy",
        "TLS proxy must wait for Web",
    )

    runtime_environment = services["api"]["environment"]
    for name in SECRET_ENVIRONMENT_NAMES:
        require(name not in runtime_environment, f"API directly contains {name}")
    for name in (
        "DATABASE_URL_FILE",
        "OIDC_CLIENT_SECRET_FILE",
        "S3_ACCESS_KEY_ID_FILE",
        "S3_SECRET_ACCESS_KEY_FILE",
    ):
        require(
            str(runtime_environment.get(name, "")).startswith("/run/secrets/"),
            f"{name} is not file-backed",
        )
    public_origin = runtime_environment.get("PUBLIC_ORIGIN")
    require(
        isinstance(public_origin, str) and public_origin.startswith("https://"),
        "PUBLIC_ORIGIN is not HTTPS",
    )
    require("*" not in public_origin, "PUBLIC_ORIGIN contains a wildcard")
    require(
        runtime_environment.get("SECURE_COOKIES") == "true",
        "secure cookies are disabled",
    )
    require(
        runtime_environment.get("REQUIRE_CSRF_ORIGIN") == "true",
        "CSRF origin is disabled",
    )
    require(
        runtime_environment.get("OIDC_REDIRECT_URI")
        == f"{public_origin}/api/v1/auth/callback",
        "OIDC callback does not exactly match PUBLIC_ORIGIN",
    )
    require(
        runtime_environment.get("CREATIVEDEPLOY_ENV_FILE") == "/dev/null",
        "staging reads a normal env file",
    )
    require(
        "BACKUP_SIGNING_KEY_FILE" not in runtime_environment,
        "API receives the operations-only backup signing key",
    )
    operations_environment = services["operations"]["environment"]
    require(
        operations_environment.get("BACKUP_SIGNING_KEY_FILE")
        == "/run/secrets/backup_signing_key",
        "operations signing key is not file-backed",
    )
    signing_key_id = operations_environment.get("BACKUP_SIGNING_KEY_ID")
    require(
        isinstance(signing_key_id, str)
        and signing_key_id
        and "*" not in signing_key_id,
        "operations signing key ID is missing or invalid",
    )

    networks = configuration.get("networks", {})
    require(
        networks.get("app", {}).get("internal") is True, "app network is not private"
    )
    require(
        networks.get("data", {}).get("internal") is True, "data network is not private"
    )
    require(
        set(services["postgres"]["networks"]) == {"data"},
        "PostgreSQL network scope is too broad",
    )
    require(
        set(services["minio"]["networks"]) == {"data"},
        "MinIO network scope is too broad",
    )
    require(
        set(services["api"]["networks"]) == {"app", "data"},
        "API network scope is wrong",
    )

    tls_template = read("deploy/tls-proxy.conf.template")
    web_template = read("deploy/staging-web.conf.template")
    base_config = read("deploy/staging-nginx-base.conf")
    require("listen 8443 ssl" in tls_template, "TLS listener is missing")
    require("return 308 https://" in tls_template, "HTTP to HTTPS redirect is missing")
    require(
        "Strict-Transport-Security" in tls_template,
        "HSTS is missing from HTTPS ingress",
    )
    require(
        "ssl_protocols TLSv1.2 TLSv1.3" in tls_template, "TLS protocol floor is missing"
    )
    require(
        "server_name _" in tls_template and "return 400" in tls_template,
        "unknown Host refusal is missing",
    )
    require(
        "proxy_set_header X-Forwarded-Proto https" in tls_template,
        "ingress forwarded scheme is not fixed",
    )
    require(
        "Strict-Transport-Security" not in web_template, "internal HTTP Web emits HSTS"
    )
    require(
        "try_files $uri $uri/ /index.html" in web_template,
        "SPA deep-link fallback is missing",
    )
    require(
        "$request_uri" not in base_config,
        "structured access logs may include query secrets",
    )
    require(
        '"path":"$uri"' in base_config, "structured safe-path access log is missing"
    )

    print("staging config validation: PASS")


if __name__ == "__main__":
    main()
