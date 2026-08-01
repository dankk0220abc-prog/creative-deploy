#!/usr/bin/env python3
"""Validate the declarative Phase 2B-1 local production-style boundary."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_SERVICES = {
    "api",
    "migrate",
    "minio",
    "oidc",
    "postgres",
    "role_grant",
    "role_provision",
    "web",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"artifact config validation failed: {message}")


def read_text(path: str) -> str:
    return (REPOSITORY_ROOT / path).read_text(encoding="utf-8")


def database_user(database_url: str) -> str | None:
    return urlparse(database_url).username


def main() -> None:
    configuration = json.load(sys.stdin)
    services: dict[str, dict[str, Any]] = configuration["services"]

    require(set(services) == EXPECTED_SERVICES, "unexpected services")
    for service_name in EXPECTED_SERVICES - {"web"}:
        require(
            "ports" not in services[service_name],
            f"{service_name} must not publish a host port",
        )
    require(
        services["postgres"]["image"]
        == (
            "postgres:17.10-alpine3.24@"
            "sha256:742f40ea20b9ff2ff31db5458d127452988a2164df9e17441e191f3b72252193"
        ),
        "PostgreSQL image must be immutable",
    )
    require(
        services["minio"]["image"]
        == (
            "minio/minio:RELEASE.2025-09-07T16-13-09Z@"
            "sha256:14cea493d9a34af32f524e538b8346cf79f3321eff8e708c1e2960462bd8936e"
        ),
        "MinIO image must be immutable",
    )

    for service_name in (
        "api",
        "migrate",
        "oidc",
        "role_grant",
        "role_provision",
        "web",
    ):
        require(
            services[service_name]["read_only"] is True,
            f"{service_name} root filesystem must be read-only",
        )
        require(
            services[service_name]["cap_drop"] == ["ALL"],
            f"{service_name} must drop all capabilities",
        )
        require(
            "no-new-privileges:true" in services[service_name]["security_opt"],
            f"{service_name} must prevent privilege escalation",
        )

    require(
        services["migrate"]["build"]["target"] == "migration",
        "migration service must use the migration-only image target",
    )
    for service_name in ("api", "oidc", "role_grant", "role_provision"):
        require(
            services[service_name]["build"]["target"] == "runtime",
            f"{service_name} must use the production runtime target",
        )
    require(
        services["web"]["build"]["target"] == "runtime",
        "web service must use the production runtime target",
    )

    for service_name in EXPECTED_SERVICES:
        labels = services[service_name]["labels"]
        require(
            labels["io.creativedeploy.runtime"] == "LOCAL_PRODUCTION_STYLE_SMOKE",
            f"{service_name} is missing the smoke label",
        )
        require(
            labels["io.creativedeploy.production"] == "NOT_REAL_PRODUCTION",
            f"{service_name} is missing the non-production label",
        )
        require(labels["io.creativedeploy.run-id"], f"{service_name} has no run ID")
    for service_name in ("api", "minio", "oidc", "postgres", "web"):
        require(
            services[service_name]["restart"] == "unless-stopped",
            f"{service_name} must recover from a process exit",
        )
    for service_name in ("migrate", "role_grant", "role_provision"):
        require(
            "restart" not in services[service_name],
            f"{service_name} is a one-shot job and must not restart",
        )

    api_environment = services["api"]["environment"]
    require(api_environment["APP_ENV"] == "test", "smoke API must use APP_ENV=test")
    require(api_environment["IDENTITY_PROVIDER"] == "oidc", "OIDC must be selected")
    require(
        api_environment["OIDC_ID_TOKEN_MAX_AGE_SECONDS"] == "300",
        "OIDC ID token maximum age must stay explicitly bounded",
    )
    require(
        api_environment["OIDC_CLOCK_SKEW_SECONDS"] == "30",
        "OIDC clock skew must stay explicitly bounded",
    )
    require(
        api_environment["OIDC_BACKCHANNEL_BASE_URL"] == "http://oidc:8090",
        "OIDC backchannel must stay inside Compose",
    )
    require(api_environment["IMAGE_STORAGE_PROVIDER"] == "s3", "S3 must be selected")
    require(
        api_environment["S3_ENDPOINT_URL"] == "http://minio:9000",
        "S3 endpoint must stay inside Compose",
    )
    require(
        api_environment["S3_CREATE_BUCKET"] == "true",
        "isolated smoke must create its private bucket explicitly",
    )
    require("*" not in api_environment["TRUSTED_HOSTS"], "trusted hosts are wildcarded")
    runtime_user = database_user(api_environment["DATABASE_URL"])
    migrator_user = database_user(services["migrate"]["environment"]["DATABASE_URL"])
    admin_user = database_user(
        services["role_provision"]["environment"]["DATABASE_URL"]
    )
    require(runtime_user is not None, "runtime database user missing")
    require(migrator_user is not None, "migrator database user missing")
    require(admin_user is not None, "admin database user missing")
    require(
        len({runtime_user, migrator_user, admin_user}) == 3,
        "admin, migrator, and runtime database identities must differ",
    )
    require(
        services["role_provision"]["environment"]["DATABASE_RUNTIME_ROLE"]
        == runtime_user,
        "runtime role provision target does not match API URL",
    )
    require(
        services["role_provision"]["environment"]["DATABASE_MIGRATOR_ROLE"]
        == migrator_user,
        "migrator role provision target does not match Alembic URL",
    )
    require(
        services["role_grant"]["depends_on"]["migrate"]["condition"]
        == "service_completed_successfully",
        "runtime grants must run after migration",
    )
    require(
        services["api"]["depends_on"]["role_grant"]["condition"]
        == "service_completed_successfully",
        "API must wait for post-migration runtime grants",
    )

    web_ports = services["web"]["ports"]
    require(len(web_ports) == 1, "web must publish exactly one port")
    published = web_ports[0]
    require(published["host_ip"] == "127.0.0.1", "web port must be loopback-only")
    require(int(published["published"]) > 0, "web port must be explicit")
    require(int(published["target"]) == 8080, "web target port must be 8080")

    nginx = read_text("deploy/nginx.conf")
    security_headers = read_text("deploy/security-headers.conf")
    api_dockerfile = read_text("apps/api/Dockerfile")
    web_dockerfile = read_text("apps/web/Dockerfile")

    require("client_max_body_size 21037056;" in nginx, "upload ceiling is not exact")
    require("proxy_pass http://creativedeploy_api;" in nginx, "API proxy missing")
    require("proxy_pass http://paintpilot_local_oidc;" in nginx, "OIDC proxy missing")
    require("try_files $uri $uri/ /index.html;" in nginx, "SPA fallback missing")
    require("autoindex off;" in nginx, "directory listing must be disabled")
    require("max-age=31536000, immutable" in nginx, "asset caching missing")
    require("no-store, no-cache, must-revalidate" in nginx, "index no-store missing")
    require("server_name localhost 127.0.0.1;" in nginx, "host allowlist missing")
    require(
        "Strict-Transport-Security" not in security_headers,
        "HTTP smoke cannot use HSTS",
    )
    require("'unsafe-eval'" not in security_headers, "CSP allows unsafe-eval")
    for header in (
        "Content-Security-Policy",
        "Permissions-Policy",
        "Referrer-Policy",
        "X-Content-Type-Options",
        "X-Frame-Options",
    ):
        require(header in security_headers, f"{header} missing")

    require("USER 10001:10001" in api_dockerfile, "API user is not explicit")
    require(
        "--no-dev --no-editable" in api_dockerfile,
        "runtime dependencies are not minimal",
    )
    require(
        "--no-default-groups --group migration --no-editable" in api_dockerfile,
        "migration dependencies are not minimal",
    )
    require("--no-proxy-headers" in api_dockerfile, "API trusts proxy headers")
    require("USER 101:101" in web_dockerfile, "web user is not explicit")

    print("artifact config validation: PASS")


if __name__ == "__main__":
    main()
