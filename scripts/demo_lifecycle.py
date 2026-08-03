#!/usr/bin/env python3
"""Operate only the fixed, loopback Phase 2E synthetic Demo compose project."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import socket
import subprocess
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
COMPOSE_FILE = REPOSITORY_ROOT / "compose.demo.yaml"
ENV_FILE = REPOSITORY_ROOT / "demo" / "demo.env"
VALIDATOR = REPOSITORY_ROOT / "scripts" / "validate_demo_config.py"
PROJECT_NAME = "creativedeploy-phase2e-demo"
WEB_URL = "http://127.0.0.1:18173"
EXPECTED_DEMO_ENV_KEYS = {
    "DEMO_WEB_PORT",
    "DEMO_DATABASE_ADMIN_PASSWORD",
    "DEMO_DATABASE_MIGRATOR_PASSWORD",
    "DEMO_DATABASE_RUNTIME_PASSWORD",
    "DEMO_OIDC_CLIENT_ID",
    "DEMO_OIDC_CLIENT_SECRET",
    "DEMO_OIDC_USERS_JSON",
    "DEMO_SEED_SUBJECT",
    "DEMO_SEED_DISPLAY_NAME",
    "DEMO_SEED_EMAIL",
    "DEMO_S3_BUCKET",
    "DEMO_S3_ACCESS_KEY_ID",
    "DEMO_S3_SECRET_ACCESS_KEY",
}
DATABASE_PASSWORD_KEYS = {
    "DEMO_DATABASE_ADMIN_PASSWORD",
    "DEMO_DATABASE_MIGRATOR_PASSWORD",
    "DEMO_DATABASE_RUNTIME_PASSWORD",
}
DEMO_RESOURCE_LABELS = {
    "io.creativedeploy.runtime": "PHASE_2E_SYNTHETIC_DEMO",
    "io.creativedeploy.public-deployment": "NOT_DEPLOYED",
    "io.creativedeploy.dataset": "phase2e-synthetic-v1",
}
RUNTIME_RESOURCES = (
    (
        "volume",
        "phase2e_demo_postgres",
        f"{PROJECT_NAME}_phase2e_demo_postgres",
    ),
    (
        "volume",
        "phase2e_demo_minio",
        f"{PROJECT_NAME}_phase2e_demo_minio",
    ),
    ("network", "phase2e_demo", f"{PROJECT_NAME}_phase2e_demo"),
)


def _read_demo_environment() -> dict[str, str]:
    if not ENV_FILE.is_file():
        raise RuntimeError(
            "demo/demo.env is missing; restore the repository Demo configuration."
        )
    values: dict[str, str] = {}
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped != line or "=" not in stripped:
            raise RuntimeError("demo/demo.env contains an invalid configuration line.")
        key, value = stripped.split("=", 1)
        if key in values or key not in EXPECTED_DEMO_ENV_KEYS or not value:
            raise RuntimeError(
                "demo/demo.env must contain complete DEMO_* values only."
            )
        values[key] = value
    if set(values) != EXPECTED_DEMO_ENV_KEYS:
        raise RuntimeError(
            "demo/demo.env must contain exactly the approved synthetic Demo values."
        )
    if values.get("DEMO_WEB_PORT") != "18173":
        raise RuntimeError("demo/demo.env must retain the fixed loopback port 18173.")
    if any(
        re.fullmatch(r"[A-Za-z0-9._~-]+", values[key]) is None
        for key in DATABASE_PASSWORD_KEYS
    ):
        raise RuntimeError(
            "Demo database passwords must use URL-safe unreserved characters only."
        )
    return values


def _subprocess_environment() -> dict[str, str]:
    values = _read_demo_environment()
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("DEMO_") and not key.startswith("COMPOSE_")
    }
    environment.update(values)
    return environment


def _compose(*arguments: str) -> list[str]:
    return [
        "docker",
        "compose",
        "--project-name",
        PROJECT_NAME,
        "--env-file",
        str(ENV_FILE),
        "--file",
        str(COMPOSE_FILE),
        *arguments,
    ]


def _run(
    command: list[str],
    *,
    capture: bool = False,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=REPOSITORY_ROOT,
        env=_subprocess_environment(),
        check=False,
        capture_output=capture,
        text=True,
    )


def _require_tools() -> bool:
    missing = [
        tool for tool in ("docker", "curl", "python3") if shutil.which(tool) is None
    ]
    if missing:
        print(
            "DEMO_DIAGNOSTIC tool_missing: install "
            + ", ".join(missing)
            + " and retry.",
            file=sys.stderr,
        )
        return False
    compose_version = _run(["docker", "compose", "version"], capture=True)
    if compose_version.returncode != 0:
        print(
            "DEMO_DIAGNOSTIC docker_compose_unavailable: start Docker Desktop, then retry make demo-up.",
            file=sys.stderr,
        )
        return False
    return True


def _validate_config() -> bool:
    configured = _run(_compose("config", "--format", "json"), capture=True)
    if configured.returncode != 0:
        print(
            "DEMO_DIAGNOSTIC compose_config_failed: repair the tracked Demo configuration; "
            "do not substitute a private .env file.",
            file=sys.stderr,
        )
        if configured.stderr:
            print(configured.stderr.strip(), file=sys.stderr)
        return False
    verified = subprocess.run(
        [sys.executable, str(VALIDATOR)],
        cwd=REPOSITORY_ROOT,
        input=configured.stdout,
        check=False,
        capture_output=True,
        text=True,
    )
    if verified.returncode != 0:
        print(verified.stderr.strip(), file=sys.stderr)
        return False
    print(verified.stdout.strip())
    return True


def _resource_is_absent(kind: str, actual_name: str, stderr: str) -> bool:
    lowered = stderr.strip().lower()
    expected_name = actual_name.lower()
    if kind == "volume":
        return (
            f"no such volume: {expected_name}" in lowered
            or f"get {expected_name}: no such volume" in lowered
        )
    return (
        f"network {expected_name} not found" in lowered
        or f"no such network: {expected_name}" in lowered
    )


def _inspect_runtime_resource(kind: str, logical_name: str, actual_name: str) -> bool:
    inspected = _run(["docker", kind, "inspect", actual_name], capture=True)
    if inspected.returncode != 0:
        if _resource_is_absent(kind, actual_name, inspected.stderr):
            return True
        print(
            f"DEMO_DIAGNOSTIC {kind}_inspect_failed: could not prove the fixed Demo resource identity.",
            file=sys.stderr,
        )
        return False
    try:
        payload = json.loads(inspected.stdout)
    except json.JSONDecodeError:
        payload = None
    if (
        not isinstance(payload, list)
        or len(payload) != 1
        or not isinstance(payload[0], dict)
        or payload[0].get("Name") != actual_name
    ):
        print(
            f"DEMO_DIAGNOSTIC {kind}_inspect_invalid: fixed Demo resource identity was ambiguous.",
            file=sys.stderr,
        )
        return False
    labels = payload[0].get("Labels")
    expected_labels = {
        **DEMO_RESOURCE_LABELS,
        "com.docker.compose.project": PROJECT_NAME,
        f"com.docker.compose.{kind}": logical_name,
    }
    if not isinstance(labels, dict) or any(
        labels.get(key) != value for key, value in expected_labels.items()
    ):
        print(
            f"DEMO_DIAGNOSTIC {kind}_label_mismatch: refusing to operate on a resource "
            "without the exact Demo identity labels.",
            file=sys.stderr,
        )
        return False
    return True


def _validate_runtime_resources() -> bool:
    return all(
        _inspect_runtime_resource(kind, logical_name, actual_name)
        for kind, logical_name, actual_name in RUNTIME_RESOURCES
    )


def _service_is_running() -> bool:
    result = _run(_compose("ps", "--status", "running", "--services"), capture=True)
    return result.returncode == 0 and "web" in result.stdout.splitlines()


def _loopback_port_is_available() -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind(("127.0.0.1", 18173))
        except OSError:
            return False
    return True


def _curl(path: str) -> tuple[bool, str]:
    result = _run(
        [
            "curl",
            "--fail",
            "--silent",
            "--show-error",
            "--max-time",
            "5",
            f"{WEB_URL}{path}",
        ],
        capture=True,
    )
    return (
        result.returncode == 0,
        result.stdout if result.returncode == 0 else result.stderr,
    )


def status() -> int:
    if not _require_tools() or not _validate_config():
        return 2
    services = _run(_compose("ps", "--format", "json"), capture=True)
    if services.returncode != 0:
        print(
            "DEMO_DIAGNOSTIC compose_status_failed: run make demo-up after Docker Desktop is ready."
        )
        return 1
    try:
        parsed = json.loads(services.stdout or "[]")
        rows = parsed if isinstance(parsed, list) else [parsed]
    except json.JSONDecodeError:
        try:
            rows = [
                json.loads(line)
                for line in services.stdout.splitlines()
                if line.strip()
            ]
        except json.JSONDecodeError:
            rows = []
    states = ", ".join(
        f"{row.get('Service', 'unknown')}={row.get('State', 'unknown')}"
        for row in rows
        if isinstance(row, dict)
    )
    print(f"DEMO_STATUS services: {states or 'none'}")

    checks: list[tuple[str, bool, str]] = []
    live_ok, live = _curl("/health/live")
    checks.append(("web_liveness", live_ok, live))
    api_ok, api = _curl("/api/v1/health/live")
    checks.append(("api_liveness", api_ok, api))
    ready_ok, ready = _curl("/health/ready")
    if ready_ok:
        try:
            readiness = json.loads(ready)
            ready_ok = readiness.get("status") == "ok" and all(
                item.get("status") == "ok"
                for item in readiness.get("checks", {}).values()
                if isinstance(item, dict)
            )
        except json.JSONDecodeError:
            ready_ok = False
    checks.append(("api_readiness", ready_ok, ready))
    root_ok, root = _curl("/")
    checks.append(("web_access", root_ok and "PaintPilot" in root, root))
    uses_port_8000 = any(
        "8000" in str(row.get("Ports", "")) for row in rows if isinstance(row, dict)
    )
    checks.append(
        ("no_port_8000", not uses_port_8000, "Demo service exposed port 8000")
    )
    database = _run(
        _compose(
            "exec",
            "-T",
            "postgres",
            "pg_isready",
            "-U",
            "paintpilot_demo_admin",
            "-d",
            "paintpilot_phase2e_demo",
        ),
        capture=True,
    )
    checks.append(
        ("database", database.returncode == 0, database.stdout or database.stderr)
    )
    failed = False
    for name, passed, detail in checks:
        print(f"DEMO_STATUS {'PASS' if passed else 'FAIL'} {name}")
        if not passed:
            failed = True
            safe_detail = detail.strip().replace("\n", " ")[:240]
            if safe_detail:
                print(f"  detail: {safe_detail}")
    if failed:
        print(
            "DEMO_DIAGNOSTIC recovery: inspect only this Demo project with make demo-status; "
            "if its synthetic state is incomplete, run make demo-reset.",
            file=sys.stderr,
        )
        return 1
    return 0


def up() -> int:
    if (
        not _require_tools()
        or not _validate_config()
        or not _validate_runtime_resources()
    ):
        return 2
    if not _service_is_running() and not _loopback_port_is_available():
        print(
            "DEMO_DIAGNOSTIC port_conflict: 127.0.0.1:18173 is already in use. "
            "Stop the known owner or use it; do not kill an unknown process.",
            file=sys.stderr,
        )
        return 2
    started = _run(_compose("up", "--detach", "--build", "--wait"))
    if started.returncode != 0:
        print(
            "DEMO_DIAGNOSTIC startup_failed: run make demo-status for this scoped project. "
            "The Demo did not fall back to another database or port.",
            file=sys.stderr,
        )
        return started.returncode or 1
    result = status()
    if result == 0:
        print(f"DEMO_READY url={WEB_URL}/paintpilot/projects")
        print(
            "DEMO_ACCESS choose the single synthetic PaintPilot Demo Visitor in the local sign-in page."
        )
    return result


def down() -> int:
    if (
        not _require_tools()
        or not _validate_config()
        or not _validate_runtime_resources()
    ):
        return 2
    stopped = _run(_compose("down", "--remove-orphans"))
    if stopped.returncode == 0:
        print("DEMO_STOPPED persistent synthetic Demo volumes were preserved.")
    return stopped.returncode


def reset() -> int:
    if (
        not _require_tools()
        or not _validate_config()
        or not _validate_runtime_resources()
    ):
        return 2
    removed = _run(_compose("down", "--volumes"))
    if removed.returncode != 0:
        print(
            "DEMO_DIAGNOSTIC reset_stop_failed: no new stack was started and no alternate target was used.",
            file=sys.stderr,
        )
        return removed.returncode or 1
    print("DEMO_RESET scoped Demo volumes removed; recreating only synthetic data.")
    return up()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("up", "status", "down", "reset"))
    command = parser.parse_args().command
    return {"up": up, "status": status, "down": down, "reset": reset}[command]()


if __name__ == "__main__":
    raise SystemExit(main())
