#!/usr/bin/env python3
"""Validate the declarative local production-style artifact boundary."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"artifact config validation failed: {message}")


def read_text(path: str) -> str:
    return (REPOSITORY_ROOT / path).read_text(encoding="utf-8")


def main() -> None:
    configuration = json.load(sys.stdin)
    services: dict[str, dict[str, Any]] = configuration["services"]

    require(set(services) == {"api", "migrate", "postgres", "web"}, "unexpected services")
    require("ports" not in services["api"], "API must not publish a host port")
    require("ports" not in services["postgres"], "PostgreSQL must not publish a host port")
    require(
        services["postgres"]["image"]
        == (
            "postgres:17.10-alpine3.24@"
            "sha256:742f40ea20b9ff2ff31db5458d127452988a2164df9e17441e191f3b72252193"
        ),
        "PostgreSQL image must be immutable",
    )
    require(services["api"]["read_only"] is True, "API root filesystem must be read-only")
    require(services["web"]["read_only"] is True, "web root filesystem must be read-only")
    require(services["migrate"]["read_only"] is True, "migration root filesystem must be read-only")
    require(
        services["migrate"]["build"]["target"] == "migration",
        "migration service must use the migration-only image target",
    )
    require(
        services["api"]["build"]["target"] == "runtime",
        "API service must use the production runtime target",
    )
    require(
        services["web"]["build"]["target"] == "runtime",
        "web service must use the production runtime target",
    )

    for service_name in ("api", "migrate", "postgres", "web"):
        labels = services[service_name]["labels"]
        require(
            labels["io.creativedeploy.runtime"] == "LOCAL_PRODUCTION_STYLE_SMOKE",
            f"{service_name} is missing the smoke label",
        )
        require(
            labels["io.creativedeploy.production"] == "NOT_REAL_PRODUCTION",
            f"{service_name} is missing the non-production label",
        )
        require(
            labels["io.creativedeploy.run-id"],
            f"{service_name} is missing the attempt run ID",
        )

    api_environment = services["api"]["environment"]
    require(api_environment["APP_ENV"] == "test", "smoke API must not use APP_ENV=production")
    require(
        api_environment["IMAGE_STORAGE_PROVIDER"] == "local_filesystem",
        "smoke storage contract changed",
    )
    require("*" not in api_environment["TRUSTED_HOSTS"], "trusted hosts must not be wildcarded")
    require(
        "DATABASE_URL" in api_environment and "postgres:5432" in api_environment["DATABASE_URL"],
        "smoke database URL must target the isolated Compose database",
    )

    web_ports = services["web"]["ports"]
    require(len(web_ports) == 1, "web must publish exactly one port")
    published = web_ports[0]
    require(published["host_ip"] == "127.0.0.1", "web port must be loopback-only")
    require(int(published["published"]) >= 0, "web port must be dynamic or explicit")
    require(int(published["target"]) == 8080, "web target port must be 8080")

    nginx = read_text("deploy/nginx.conf")
    security_headers = read_text("deploy/security-headers.conf")
    api_dockerfile = read_text("apps/api/Dockerfile")
    web_dockerfile = read_text("apps/web/Dockerfile")

    require("client_max_body_size 21037056;" in nginx, "upload ceiling is not exact")
    require("proxy_pass http://creativedeploy_api;" in nginx, "same-origin API proxy missing")
    require("try_files $uri $uri/ /index.html;" in nginx, "SPA fallback missing")
    require("autoindex off;" in nginx, "directory listing must be disabled")
    require("max-age=31536000, immutable" in nginx, "immutable asset caching missing")
    require("no-store, no-cache, must-revalidate" in nginx, "index no-store policy missing")
    require("server_name localhost 127.0.0.1;" in nginx, "expected host allowlist missing")
    require("Strict-Transport-Security" not in security_headers, "HSTS is invalid for HTTP smoke")
    require("'unsafe-eval'" not in security_headers, "CSP must not allow unsafe-eval")
    for header in (
        "Content-Security-Policy",
        "Permissions-Policy",
        "Referrer-Policy",
        "X-Content-Type-Options",
        "X-Frame-Options",
    ):
        require(header in security_headers, f"{header} missing")

    require("USER 10001:10001" in api_dockerfile, "API runtime user is not explicit")
    require("--no-dev --no-editable" in api_dockerfile, "API runtime dependency set is not minimal")
    require(
        "--no-default-groups --group migration --no-editable" in api_dockerfile,
        "migration dependency set is not minimal",
    )
    require("--no-proxy-headers" in api_dockerfile, "API must not trust arbitrary proxy headers")
    require("USER 101:101" in web_dockerfile, "web runtime user is not explicit")

    print("artifact config validation: PASS")


if __name__ == "__main__":
    main()
