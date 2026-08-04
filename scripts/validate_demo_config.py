#!/usr/bin/env python3
"""Fail closed when the fixed Phase 2E local Demo compose contract drifts."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PROJECT_NAME = "creativedeploy-phase2e-demo"
DATABASE_HOST = "postgres"
DATABASE_PORT = 5432
DATABASE_NAME = "paintpilot_phase2e_demo"
DATABASE_DRIVER = "postgresql+psycopg"

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
EXPECTED_NETWORKS = {"phase2e_demo"}
REQUIRED_LABELS = {
    "io.creativedeploy.runtime": "PHASE_2E_SYNTHETIC_DEMO",
    "io.creativedeploy.public-deployment": "NOT_DEPLOYED",
    "io.creativedeploy.dataset": "phase2e-synthetic-v1",
}
EXPECTED_DATABASE_USERS = {
    "role_provision": "paintpilot_demo_admin",
    "migrate": "paintpilot_demo_migrator",
    "role_grant": "paintpilot_demo_admin",
    "seed": "paintpilot_demo_runtime",
    "api": "paintpilot_demo_runtime",
}
EXPECTED_SERVICE_COMMANDS: dict[str, list[str] | None] = {
    "postgres": None,
    "minio": ["server", "/data", "--console-address", ":9001"],
    "oidc": [
        "python",
        "-m",
        "uvicorn",
        "creativedeploy_api.local_oidc:app",
        "--host",
        "0.0.0.0",
        "--port",
        "18090",
        "--no-server-header",
        "--no-proxy-headers",
    ],
    "role_provision": [
        "python",
        "-m",
        "creativedeploy_api.tools.provision_database_roles",
    ],
    "migrate": None,
    "role_grant": ["python", "-m", "creativedeploy_api.tools.provision_database_roles"],
    "seed": ["python", "-m", "creativedeploy_api.tools.seed_demo"],
    "api": [
        "python",
        "-m",
        "uvicorn",
        "creativedeploy_api.main:app",
        "--host",
        "0.0.0.0",
        "--port",
        "18080",
        "--no-server-header",
        "--no-proxy-headers",
        "--no-access-log",
    ],
    "web": None,
}
EXPECTED_SERVICE_IMAGES: dict[str, str | None] = {
    "postgres": (
        "postgres:17.10-alpine3.24@"
        "sha256:742f40ea20b9ff2ff31db5458d127452988a2164df9e17441e191f3b72252193"
    ),
    "minio": (
        "minio/minio:RELEASE.2025-09-07T16-13-09Z@"
        "sha256:14cea493d9a34af32f524e538b8346cf79f3321eff8e708c1e2960462bd8936e"
    ),
    "oidc": None,
    "role_provision": None,
    "migrate": None,
    "role_grant": None,
    "seed": None,
    "api": None,
    "web": None,
}
API_DEMO_BUILD = {
    "context": str(REPOSITORY_ROOT),
    "dockerfile": "apps/api/Dockerfile",
    "target": "demo-runtime",
}
EXPECTED_SERVICE_BUILDS: dict[str, dict[str, Any] | None] = {
    "postgres": None,
    "minio": None,
    "oidc": API_DEMO_BUILD,
    "role_provision": API_DEMO_BUILD,
    "migrate": {
        "context": str(REPOSITORY_ROOT),
        "dockerfile": "apps/api/Dockerfile",
        "target": "migration",
    },
    "role_grant": API_DEMO_BUILD,
    "seed": API_DEMO_BUILD,
    "api": API_DEMO_BUILD,
    "web": {
        "context": str(REPOSITORY_ROOT),
        "dockerfile": "apps/web/Dockerfile",
        "target": "demo-runtime",
        "args": {"VITE_RUNTIME_PROFILE": "public-demo"},
    },
}
FORBIDDEN_DATABASE_TARGET_KEYS = {
    "DATABASE_HOST",
    "DATABASE_PORT",
    "DATABASE_NAME",
    "DATABASE_USER",
    "DATABASE_USERNAME",
    "DB_HOST",
    "DB_PORT",
    "DB_NAME",
    "DB_USER",
    "DB_USERNAME",
    "PGHOST",
    "PGHOSTADDR",
    "PGPORT",
    "PGDATABASE",
    "PGUSER",
    "PGSERVICE",
    "PGSERVICEFILE",
}


def _parse_yaml_event_node(
    events: list[Any], index: int, yaml_module: Any, anchors: dict[str, dict[str, Any]]
) -> tuple[dict[str, Any], int]:
    if index >= len(events):
        raise ValueError("unexpected end of YAML event stream")
    event = events[index]
    if isinstance(event, yaml_module.events.ScalarEvent):
        node = {
            "kind": "scalar",
            "value": event.value,
            "tag": event.tag,
            "anchor": event.anchor,
        }
        if event.anchor is not None:
            anchors[event.anchor] = node
        return node, index + 1
    if isinstance(event, yaml_module.events.AliasEvent):
        return {"kind": "alias", "anchor": event.anchor}, index + 1
    if isinstance(event, yaml_module.events.SequenceStartEvent):
        node = {"kind": "sequence", "items": [], "anchor": event.anchor}
        if event.anchor is not None:
            anchors[event.anchor] = node
        index += 1
        while index < len(events) and not isinstance(
            events[index], yaml_module.events.SequenceEndEvent
        ):
            child, index = _parse_yaml_event_node(events, index, yaml_module, anchors)
            node["items"].append(child)
        if index >= len(events):
            raise ValueError("unterminated YAML sequence")
        return node, index + 1
    if isinstance(event, yaml_module.events.MappingStartEvent):
        node = {"kind": "mapping", "pairs": [], "anchor": event.anchor}
        if event.anchor is not None:
            anchors[event.anchor] = node
        index += 1
        while index < len(events) and not isinstance(
            events[index], yaml_module.events.MappingEndEvent
        ):
            key, index = _parse_yaml_event_node(events, index, yaml_module, anchors)
            value, index = _parse_yaml_event_node(events, index, yaml_module, anchors)
            node["pairs"].append((key, value))
        if index >= len(events):
            raise ValueError("unterminated YAML mapping")
        return node, index + 1
    raise ValueError("unexpected YAML node event")


def _resolved_yaml_node(
    node: dict[str, Any], anchors: Mapping[str, dict[str, Any]]
) -> dict[str, Any] | None:
    if node.get("kind") != "alias":
        return node
    anchor = node.get("anchor")
    return anchors.get(anchor) if isinstance(anchor, str) else None


def validate_source(source: str) -> list[str]:
    """Validate the literal source-level Compose project identity."""
    try:
        import yaml
    except ModuleNotFoundError:
        return ["the locked safe YAML parser is unavailable"]

    try:
        events = list(yaml.parse(source, Loader=yaml.SafeLoader))
        if (
            len(events) < 5
            or not isinstance(events[0], yaml.events.StreamStartEvent)
            or not isinstance(events[1], yaml.events.DocumentStartEvent)
        ):
            raise ValueError("invalid YAML document boundary")
        anchors: dict[str, dict[str, Any]] = {}
        root, index = _parse_yaml_event_node(events, 2, yaml, anchors)
        if (
            index + 2 != len(events)
            or not isinstance(events[index], yaml.events.DocumentEndEvent)
            or not isinstance(events[index + 1], yaml.events.StreamEndEvent)
        ):
            raise ValueError("the Compose source must contain exactly one document")
    except (ValueError, yaml.YAMLError) as error:
        return [f"compose source YAML is invalid ({error})"]

    if root.get("kind") != "mapping":
        return ["compose source must be a top-level mapping"]

    name_entries: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for key, value in root["pairs"]:
        if key.get("value") == "<<" or key.get("tag") == "tag:yaml.org,2002:merge":
            return ["compose source must not contain YAML merge keys"]
        resolved_key = _resolved_yaml_node(key, anchors)
        if resolved_key is None:
            return ["compose source contains an unresolved top-level alias"]
        if resolved_key.get("kind") != "scalar":
            return ["compose source top-level keys must be explicit scalars"]
        if resolved_key.get("value") == "name":
            name_entries.append((key, value))

    if len(name_entries) != 1:
        return ["compose source must define exactly one explicit top-level name"]
    key, value = name_entries[0]
    if key.get("kind") != "scalar" or key.get("anchor") is not None:
        return ["compose source top-level name key must be explicit"]
    if (
        value.get("kind") != "scalar"
        or value.get("anchor") is not None
        or value.get("tag") not in (None, "tag:yaml.org,2002:str")
        or value.get("value") != PROJECT_NAME
    ):
        return [
            "compose source top-level name must be the fixed literal Phase 2E Demo project name"
        ]
    return []


def validate_source_file(path: Path) -> list[str]:
    try:
        source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        return [f"compose source could not be read safely ({error})"]
    return validate_source(source)


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


def _expected_resource_labels(kind: str, logical_name: str) -> dict[str, str]:
    return {
        **REQUIRED_LABELS,
        "com.docker.compose.project": PROJECT_NAME,
        f"com.docker.compose.{kind}": logical_name,
    }


def _validate_resources(
    config: Mapping[str, Any],
    *,
    kind: str,
    expected_names: set[str],
) -> list[str]:
    failures: list[str] = []
    resources = config.get(f"{kind}s")
    if not isinstance(resources, Mapping):
        return [f"{kind} definitions must be a mapping"]
    actual_names = {str(name) for name in resources}
    if actual_names != expected_names:
        failures.append(f"{kind} set must be exactly the approved Phase 2E Demo set")
    for logical_name in expected_names & actual_names:
        resource = resources[logical_name]
        if not isinstance(resource, Mapping):
            failures.append(f"{kind} {logical_name} must be a mapping")
            continue
        expected_actual_name = f"{PROJECT_NAME}_{logical_name}"
        if resource.get("name") != expected_actual_name:
            failures.append(
                f"{kind} {logical_name} must retain its fixed rendered name"
            )
        if resource.get("external", False) is not False:
            failures.append(f"{kind} {logical_name} must not be external")
        labels = resource.get("labels")
        if labels != _expected_resource_labels(kind, logical_name):
            failures.append(
                f"{kind} {logical_name} must retain its exact Demo identity labels"
            )
    return failures


def _validate_service_networks(name: str, service: Mapping[str, Any]) -> list[str]:
    failures: list[str] = []
    networks = service.get("networks")
    if (
        not isinstance(networks, Mapping)
        or {str(item) for item in networks} != EXPECTED_NETWORKS
    ):
        failures.append(f"{name} must join only the approved Phase 2E Demo network")
    if service.get("network_mode") not in (None, ""):
        failures.append(f"{name} must not set network_mode")
    return failures


def _validate_service_volumes(name: str, service: Mapping[str, Any]) -> list[str]:
    expected = {
        "postgres": ("phase2e_demo_postgres", "/var/lib/postgresql/data"),
        "minio": ("phase2e_demo_minio", "/data"),
    }.get(name)
    volumes = service.get("volumes", [])
    if volumes is None:
        volumes = []
    if not isinstance(volumes, list):
        return [f"{name} volumes must be a list"]
    if expected is None:
        return [] if not volumes else [f"{name} must not mount a volume or bind path"]
    if len(volumes) != 1 or not isinstance(volumes[0], Mapping):
        return [f"{name} must mount exactly its approved Demo volume"]
    mount = volumes[0]
    if (
        mount.get("type") != "volume"
        or mount.get("source") != expected[0]
        or mount.get("target") != expected[1]
    ):
        return [f"{name} must mount only its approved named Demo volume"]
    return []


def _validate_database_url(
    service_name: str, raw_url: str, expected_user: str
) -> list[str]:
    failure = (
        f"{service_name} DATABASE_URL must target only the fixed internal Demo database"
    )
    if (
        not raw_url
        or raw_url.strip() != raw_url
        or any(char.isspace() for char in raw_url)
    ):
        return [failure]
    try:
        parsed = urlsplit(raw_url)
        port = parsed.port
    except ValueError:
        return [failure]
    if (
        parsed.scheme != DATABASE_DRIVER
        or parsed.hostname != DATABASE_HOST
        or port != DATABASE_PORT
        or parsed.path != f"/{DATABASE_NAME}"
        or parsed.username != expected_user
        or not parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.netloc.count("@") != 1
    ):
        return [failure]
    return []


def _validate_database_targets(services: Mapping[str, Any]) -> list[str]:
    failures: list[str] = []
    for name, raw_service in services.items():
        if not isinstance(raw_service, Mapping):
            continue
        service_name = str(name)
        environment = _environment(raw_service)
        suspicious_keys = {
            key
            for key in environment
            if key in FORBIDDEN_DATABASE_TARGET_KEYS
            or (key != "DATABASE_URL" and key.endswith(("DATABASE_URL", "DB_URL")))
        }
        if suspicious_keys:
            failures.append(
                f"{service_name} must not define alternate database target settings"
            )
        if (
            service_name not in EXPECTED_DATABASE_USERS
            and "DATABASE_URL" in environment
        ):
            failures.append(f"{service_name} must not define a DATABASE_URL")

    for service_name, expected_user in EXPECTED_DATABASE_USERS.items():
        raw_service = services.get(service_name)
        if not isinstance(raw_service, Mapping):
            continue
        environment = _environment(raw_service)
        raw_url = environment.get("DATABASE_URL")
        if raw_url is None:
            failures.append(f"{service_name} must define DATABASE_URL")
        else:
            failures.extend(
                _validate_database_url(service_name, raw_url, expected_user)
            )

    postgres = services.get("postgres")
    if isinstance(postgres, Mapping):
        environment = _environment(postgres)
        if environment.get("POSTGRES_DB") != DATABASE_NAME:
            failures.append("postgres must create only the fixed Demo database")
        if environment.get("POSTGRES_USER") != "paintpilot_demo_admin":
            failures.append("postgres must use only the fixed Demo admin role")
        if not environment.get("POSTGRES_PASSWORD"):
            failures.append("postgres must define its synthetic Demo password")

    for service_name in ("role_provision", "role_grant"):
        raw_service = services.get(service_name)
        if not isinstance(raw_service, Mapping):
            continue
        environment = _environment(raw_service)
        if environment.get("DATABASE_MIGRATOR_ROLE") != "paintpilot_demo_migrator":
            failures.append(f"{service_name} must retain the fixed Demo migrator role")
        if environment.get("DATABASE_RUNTIME_ROLE") != "paintpilot_demo_runtime":
            failures.append(f"{service_name} must retain the fixed Demo runtime role")

    return failures


def _validate_service_execution_identities(
    services: Mapping[str, Any], actual_services: set[str]
) -> list[str]:
    failures: list[str] = []
    for name in EXPECTED_SERVICES & actual_services:
        raw_service = services[name]
        if not isinstance(raw_service, Mapping):
            continue
        if raw_service.get("command") != EXPECTED_SERVICE_COMMANDS[name]:
            failures.append(f"{name} must retain its exact approved command identity")
        if raw_service.get("entrypoint") is not None:
            failures.append(f"{name} must not override its entrypoint")
        if raw_service.get("image") != EXPECTED_SERVICE_IMAGES[name]:
            failures.append(f"{name} must retain its exact approved image identity")
        if raw_service.get("build") != EXPECTED_SERVICE_BUILDS[name]:
            failures.append(f"{name} must retain its exact approved build identity")
        if raw_service.get("profiles") is not None:
            failures.append(f"{name} must not change its approved profile membership")
    return failures


def validate(config: Mapping[str, Any]) -> list[str]:
    failures: list[str] = []
    services = config.get("services")
    if not isinstance(services, Mapping):
        return ["compose config has no services mapping"]
    actual_services = {str(name) for name in services}
    if actual_services != EXPECTED_SERVICES:
        failures.append("service set must be exactly the Phase 2E Demo services")

    failures.extend(_validate_service_execution_identities(services, actual_services))

    if config.get("name") != PROJECT_NAME:
        failures.append(
            "compose project name must be exactly the fixed Phase 2E Demo project"
        )

    failures.extend(
        _validate_resources(config, kind="volume", expected_names=EXPECTED_VOLUMES)
    )
    failures.extend(
        _validate_resources(config, kind="network", expected_names=EXPECTED_NETWORKS)
    )

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
        failures.extend(_validate_service_networks(name, service))
        failures.extend(_validate_service_volumes(name, service))
        ports = service.get("ports", [])
        if name == "web":
            if (
                not isinstance(ports, list)
                or len(ports) != 1
                or not _port_is_loopback_demo(ports[0])
            ):
                failures.append(
                    "web must publish only 127.0.0.1:18173 to internal 8080"
                )
        elif ports:
            failures.append(f"{name} must not publish a host port")

    failures.extend(_validate_database_targets(services))

    api = services.get("api")
    oidc = services.get("oidc")
    role_provision = services.get("role_provision")
    migrate = services.get("migrate")
    role_grant = services.get("role_grant")
    seed = services.get("seed")
    web = services.get("web")
    if isinstance(api, Mapping):
        api_build = api.get("build", {})
        if (
            not isinstance(api_build, Mapping)
            or api_build.get("target") != "demo-runtime"
        ):
            failures.append("api must use the dedicated Demo runtime without port 8000")
        if not _has_command_port(api, "18080") or _has_command_port(api, "8000"):
            failures.append(
                "api must use internal port 18080 and must not use port 8000"
            )
        if _environment(api).get("PAINTPILOT_DEMO_READ_ONLY", "").lower() != "true":
            failures.append("api must enable the synthetic Demo read-only boundary")
        if not _depends_on(api, "seed", "service_completed_successfully"):
            failures.append("api must wait for the one-shot synthetic seed")
    if isinstance(oidc, Mapping):
        oidc_build = oidc.get("build", {})
        if (
            not isinstance(oidc_build, Mapping)
            or oidc_build.get("target") != "demo-runtime"
        ):
            failures.append(
                "oidc must use the dedicated Demo runtime without port 8000"
            )
        if not _has_command_port(oidc, "18090"):
            failures.append("oidc must use internal port 18090")
    if isinstance(role_provision, Mapping) and not _depends_on(
        role_provision, "postgres", "service_healthy"
    ):
        failures.append("role_provision must wait for the fixed Demo postgres service")
    if isinstance(migrate, Mapping) and not _depends_on(
        migrate, "role_provision", "service_completed_successfully"
    ):
        failures.append("migrate must wait for Demo role provisioning")
    if isinstance(role_grant, Mapping) and not _depends_on(
        role_grant, "migrate", "service_completed_successfully"
    ):
        failures.append("role_grant must wait for the Demo migration")
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
        if (
            not isinstance(args, Mapping)
            or args.get("VITE_RUNTIME_PROFILE") != "public-demo"
        ):
            failures.append("web must build with the public-demo identifier")
        if not _depends_on(web, "api", "service_healthy"):
            failures.append("web must wait for API health")

    serialized = json.dumps(config, sort_keys=True)
    if '"8000"' in serialized or ":8000" in serialized:
        failures.append("the Demo compose configuration must not contain port 8000")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-compose", type=Path)
    arguments = parser.parse_args()
    if arguments.source_compose is not None:
        source_failures = validate_source_file(arguments.source_compose)
        if source_failures:
            for failure in source_failures:
                print(f"DEMO_SOURCE_CONFIG_INVALID: {failure}", file=sys.stderr)
            return 2
        print("DEMO_SOURCE_CONFIG_VALID: fixed literal source project name accepted.")
        return 0

    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        message = (
            error.msg if isinstance(error, json.JSONDecodeError) else "invalid encoding"
        )
        print(
            f"DEMO_CONFIG_INVALID: invalid compose JSON ({message}).", file=sys.stderr
        )
        return 2
    if not isinstance(payload, Mapping):
        print("DEMO_CONFIG_INVALID: compose JSON must be an object.", file=sys.stderr)
        return 2
    failures = validate(payload)
    if failures:
        for failure in failures:
            print(f"DEMO_CONFIG_INVALID: {failure}", file=sys.stderr)
        return 2
    print(
        "DEMO_CONFIG_VALID: fixed project, resources, network, services, and database targets accepted."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
