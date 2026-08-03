#!/usr/bin/env python3
"""Fail closed when the fixed Phase 2E local Demo compose contract drifts."""

from __future__ import annotations

import json
import sys
from collections.abc import Mapping
from typing import Any

EXPECTED_SERVICES = {
    "postgres",
    "minio",
    "oidc",
    "role_provision",
    "migrate",
    "role_grant",
    "seed",
    "api",
    "web",
}
EXPECTED_VOLUMES = {"phase2e_demo_postgres", "phase2e_demo_minio"}
REQUIRED_LABELS = {
    "io.creativedeploy.runtime": "PHASE_2E_SYNTHETIC_DEMO",
    "io.creativedeploy.public-deployment": "NOT_DEPLOYED",
    "io.creativedeploy.dataset": "phase2e-synthetic-v1",
}


def _environment(service: Mapping[str, Any]) -> Mapping[str, str]:
    value = service.get("environment", {})
    if not isinstance(value, Mapping):
        return {}
    return {str(key): str(item) for key, item in value.items()}


def _port_is_loopback_demo(port: object) -> bool:
    if isinstance(port, Mapping):
        return (
            str(port.get("host_ip", "")) == "127.0.0.1"
            and str(port.get("published", "")) == "18173"
            and str(port.get("target", "")) == "8080"
            and str(port.get("protocol", "tcp")) == "tcp"
        )
    return str(port) in {"127.0.0.1:18173:8080", "127.0.0.1:18173:8080/tcp"}


def _has_command_port(service: Mapping[str, Any], port: str) -> bool:
    command = service.get("command", [])
    if isinstance(command, str):
        return port in command.split()
    if isinstance(command, list):
        return port in {str(item) for item in command}
    return False


def _depends_on(service: Mapping[str, Any], name: str, condition: str) -> bool:
    depends = service.get("depends_on", {})
    if not isinstance(depends, Mapping):
        return False
    dependency = depends.get(name)
    return isinstance(dependency, Mapping) and dependency.get("condition") == condition


def validate(config: Mapping[str, Any]) -> list[str]:
    failures: list[str] = []
    services = config.get("services")
    if not isinstance(services, Mapping):
        return ["compose config has no services mapping"]
    actual_services = {str(name) for name in services}
    if actual_services != EXPECTED_SERVICES:
        failures.append("service set must be exactly the Phase 2E Demo services")
    volumes = config.get("volumes")
    if not isinstance(volumes, Mapping) or {str(name) for name in volumes} != EXPECTED_VOLUMES:
        failures.append("volume set must be exactly the two Phase 2E Demo volumes")

    for name in EXPECTED_SERVICES & actual_services:
        service = services[name]
        if not isinstance(service, Mapping):
            failures.append(f"{name} service must be a mapping")
            continue
        labels = service.get("labels", {})
        if not isinstance(labels, Mapping) or any(
            labels.get(key) != value for key, value in REQUIRED_LABELS.items()
        ):
            failures.append(f"{name} must retain all Phase 2E isolation labels")
        ports = service.get("ports", [])
        if name == "web":
            if not isinstance(ports, list) or len(ports) != 1 or not _port_is_loopback_demo(ports[0]):
                failures.append("web must publish only 127.0.0.1:18173 to internal 8080")
        elif ports:
            failures.append(f"{name} must not publish a host port")

    api = services.get("api")
    oidc = services.get("oidc")
    seed = services.get("seed")
    web = services.get("web")
    if isinstance(api, Mapping):
        api_build = api.get("build", {})
        if not isinstance(api_build, Mapping) or api_build.get("target") != "demo-runtime":
            failures.append("api must use the dedicated Demo runtime without port 8000")
        if not _has_command_port(api, "18080") or _has_command_port(api, "8000"):
            failures.append("api must use internal port 18080 and must not use port 8000")
        if _environment(api).get("PAINTPILOT_DEMO_READ_ONLY", "").lower() != "true":
            failures.append("api must enable the synthetic Demo read-only boundary")
        if not _depends_on(api, "seed", "service_completed_successfully"):
            failures.append("api must wait for the one-shot synthetic seed")
    if isinstance(oidc, Mapping):
        oidc_build = oidc.get("build", {})
        if not isinstance(oidc_build, Mapping) or oidc_build.get("target") != "demo-runtime":
            failures.append("oidc must use the dedicated Demo runtime without port 8000")
        if not _has_command_port(oidc, "18090"):
            failures.append("oidc must use internal port 18090")
    if isinstance(seed, Mapping):
        if _environment(seed).get("PAINTPILOT_DEMO_SEED_ENABLED", "").lower() != "true":
            failures.append("seed must require explicit synthetic Demo authorization")
        if not _depends_on(seed, "role_grant", "service_completed_successfully"):
            failures.append("seed must wait for runtime database grants")
    if isinstance(web, Mapping):
        build = web.get("build", {})
        if not isinstance(build, Mapping) or build.get("target") != "demo-runtime":
            failures.append("web must use the dedicated Demo proxy runtime")
        args = build.get("args", {}) if isinstance(build, Mapping) else {}
        if not isinstance(args, Mapping) or args.get("VITE_RUNTIME_PROFILE") != "public-demo":
            failures.append("web must build with the public-demo identifier")
        if not _depends_on(web, "api", "service_healthy"):
            failures.append("web must wait for API health")

    serialized = json.dumps(config, sort_keys=True)
    if '"8000"' in serialized or ":8000" in serialized:
        failures.append("the Demo compose configuration must not contain port 8000")
    return failures


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError as error:
        print(f"DEMO_CONFIG_INVALID: invalid compose JSON ({error.msg}).", file=sys.stderr)
        return 2
    if not isinstance(payload, Mapping):
        print("DEMO_CONFIG_INVALID: compose JSON must be an object.", file=sys.stderr)
        return 2
    failures = validate(payload)
    if failures:
        for failure in failures:
            print(f"DEMO_CONFIG_INVALID: {failure}", file=sys.stderr)
        return 2
    print("DEMO_CONFIG_VALID: isolated services, volumes, ports, and seed guards accepted.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
