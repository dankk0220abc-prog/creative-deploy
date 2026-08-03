"""Focused negative tests for the fail-closed Phase 2E Demo reset guard."""

from __future__ import annotations

import importlib.util
import json
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest


def _load_script(name: str) -> Any:
    script_path = Path(__file__).resolve().parents[4] / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load focused script {name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


demo_lifecycle = _load_script("demo_lifecycle")
validate_demo_config = _load_script("validate_demo_config")

DEMO_LABELS = {
    "io.creativedeploy.runtime": "PHASE_2E_SYNTHETIC_DEMO",
    "io.creativedeploy.public-deployment": "NOT_DEPLOYED",
    "io.creativedeploy.dataset": "phase2e-synthetic-v1",
}
PROJECT_NAME = "creativedeploy-phase2e-demo"
NETWORK_NAME = "phase2e_demo"


def _resource_labels(kind: str, logical_name: str) -> dict[str, str]:
    return {
        **DEMO_LABELS,
        "com.docker.compose.project": PROJECT_NAME,
        f"com.docker.compose.{kind}": logical_name,
    }


def _database_url(user: str) -> str:
    return (
        f"postgresql+psycopg://{user}:synthetic-test-password@postgres:5432/paintpilot_phase2e_demo"
    )


def _service(**values: Any) -> dict[str, Any]:
    return {"labels": dict(DEMO_LABELS), "networks": {NETWORK_NAME: None}, **values}


def _valid_config() -> dict[str, Any]:
    role_environment = {
        "DATABASE_URL": _database_url("paintpilot_demo_admin"),
        "DATABASE_MIGRATOR_ROLE": "paintpilot_demo_migrator",
        "DATABASE_MIGRATOR_PASSWORD": "synthetic-test-password",
        "DATABASE_RUNTIME_ROLE": "paintpilot_demo_runtime",
        "DATABASE_RUNTIME_PASSWORD": "synthetic-test-password",
    }
    role_command = ["python", "-m", "creativedeploy_api.tools.provision_database_roles"]
    return {
        "name": PROJECT_NAME,
        "services": {
            "postgres": _service(
                environment={
                    "POSTGRES_USER": "paintpilot_demo_admin",
                    "POSTGRES_PASSWORD": "synthetic-test-password",
                    "POSTGRES_DB": "paintpilot_phase2e_demo",
                },
                volumes=[
                    {
                        "type": "volume",
                        "source": "phase2e_demo_postgres",
                        "target": "/var/lib/postgresql/data",
                    }
                ],
            ),
            "minio": _service(
                volumes=[{"type": "volume", "source": "phase2e_demo_minio", "target": "/data"}]
            ),
            "oidc": _service(
                build={"target": "demo-runtime"},
                command=["python", "-m", "uvicorn", "module:app", "--port", "18090"],
            ),
            "role_provision": _service(
                command=role_command,
                environment=dict(role_environment),
                depends_on={"postgres": {"condition": "service_healthy"}},
            ),
            "migrate": _service(
                environment={"DATABASE_URL": _database_url("paintpilot_demo_migrator")},
                depends_on={"role_provision": {"condition": "service_completed_successfully"}},
            ),
            "role_grant": _service(
                command=role_command,
                environment=dict(role_environment),
                depends_on={"migrate": {"condition": "service_completed_successfully"}},
            ),
            "seed": _service(
                command=["python", "-m", "creativedeploy_api.tools.seed_demo"],
                environment={
                    "DATABASE_URL": _database_url("paintpilot_demo_runtime"),
                    "PAINTPILOT_DEMO_SEED_ENABLED": "true",
                },
                depends_on={"role_grant": {"condition": "service_completed_successfully"}},
            ),
            "api": _service(
                build={"target": "demo-runtime"},
                command=[
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
                environment={
                    "DATABASE_URL": _database_url("paintpilot_demo_runtime"),
                    "PAINTPILOT_DEMO_READ_ONLY": "true",
                },
                depends_on={"seed": {"condition": "service_completed_successfully"}},
            ),
            "web": _service(
                build={"target": "demo-runtime", "args": {"VITE_RUNTIME_PROFILE": "public-demo"}},
                ports=[
                    {
                        "host_ip": "127.0.0.1",
                        "published": "18173",
                        "target": 8080,
                        "protocol": "tcp",
                    }
                ],
                depends_on={"api": {"condition": "service_healthy"}},
            ),
        },
        "volumes": {
            logical_name: {
                "name": f"{PROJECT_NAME}_{logical_name}",
                "labels": _resource_labels("volume", logical_name),
            }
            for logical_name in ("phase2e_demo_postgres", "phase2e_demo_minio")
        },
        "networks": {
            NETWORK_NAME: {
                "name": f"{PROJECT_NAME}_{NETWORK_NAME}",
                "labels": _resource_labels("network", NETWORK_NAME),
            }
        },
    }


def _failures_after(mutator: Callable[[dict[str, Any]], None]) -> list[str]:
    config = _valid_config()
    mutator(config)
    return validate_demo_config.validate(config)


def test_correct_config_is_accepted() -> None:
    assert validate_demo_config.validate(_valid_config()) == []


def test_project_name_drift_is_rejected() -> None:
    assert _failures_after(lambda config: config.update(name="not-the-demo"))


def test_rendered_volume_name_drift_is_rejected() -> None:
    def mutate(config: dict[str, Any]) -> None:
        config["volumes"]["phase2e_demo_postgres"]["name"] = "production-data"

    assert _failures_after(mutate)


@pytest.mark.parametrize("replacement", [None, "wrong"])
def test_volume_label_missing_or_wrong_is_rejected(replacement: str | None) -> None:
    def mutate(config: dict[str, Any]) -> None:
        labels = config["volumes"]["phase2e_demo_postgres"]["labels"]
        if replacement is None:
            labels.pop("io.creativedeploy.runtime")
        else:
            labels["io.creativedeploy.runtime"] = replacement

    assert _failures_after(mutate)


def test_external_volume_is_rejected() -> None:
    def mutate(config: dict[str, Any]) -> None:
        config["volumes"]["phase2e_demo_postgres"]["external"] = True

    assert _failures_after(mutate)


def test_extra_volume_is_rejected() -> None:
    def mutate(config: dict[str, Any]) -> None:
        config["volumes"]["unexpected"] = {}

    assert _failures_after(mutate)


def test_rendered_network_name_drift_is_rejected() -> None:
    def mutate(config: dict[str, Any]) -> None:
        config["networks"][NETWORK_NAME]["name"] = "shared-network"

    assert _failures_after(mutate)


@pytest.mark.parametrize("replacement", [None, "wrong"])
def test_network_label_missing_or_wrong_is_rejected(replacement: str | None) -> None:
    def mutate(config: dict[str, Any]) -> None:
        labels = config["networks"][NETWORK_NAME]["labels"]
        if replacement is None:
            labels.pop("io.creativedeploy.runtime")
        else:
            labels["io.creativedeploy.runtime"] = replacement

    assert _failures_after(mutate)


def test_external_network_is_rejected() -> None:
    def mutate(config: dict[str, Any]) -> None:
        config["networks"][NETWORK_NAME]["external"] = True

    assert _failures_after(mutate)


def test_extra_top_level_network_is_rejected() -> None:
    def mutate(config: dict[str, Any]) -> None:
        config["networks"]["shared"] = {}

    assert _failures_after(mutate)


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("@postgres:", "@database.example.invalid:"),
        (":5432/", ":5433/"),
        ("/paintpilot_phase2e_demo", "/production"),
        ("paintpilot_demo_runtime:", "other_user:"),
    ],
    ids=("external-host", "wrong-port", "wrong-database", "wrong-username"),
)
def test_database_target_identity_drift_is_rejected(old: str, new: str) -> None:
    def mutate(config: dict[str, Any]) -> None:
        environment = config["services"]["api"]["environment"]
        environment["DATABASE_URL"] = environment["DATABASE_URL"].replace(old, new)

    assert _failures_after(mutate)


@pytest.mark.parametrize("query", ["host=evil", "port=5433", "dbname=other", "database=other"])
def test_database_query_target_override_is_rejected(query: str) -> None:
    def mutate(config: dict[str, Any]) -> None:
        environment = config["services"]["api"]["environment"]
        environment["DATABASE_URL"] = f"{environment['DATABASE_URL']}?{query}"

    assert _failures_after(mutate)


def test_invalid_database_url_is_rejected() -> None:
    def mutate(config: dict[str, Any]) -> None:
        config["services"]["seed"]["environment"]["DATABASE_URL"] = "not a URL"

    assert _failures_after(mutate)


def test_missing_database_url_is_rejected() -> None:
    def mutate(config: dict[str, Any]) -> None:
        config["services"]["migrate"]["environment"].pop("DATABASE_URL")

    assert _failures_after(mutate)


def test_service_extra_network_is_rejected() -> None:
    def mutate(config: dict[str, Any]) -> None:
        config["services"]["api"]["networks"]["shared"] = None

    assert _failures_after(mutate)


@pytest.mark.parametrize(
    "mount",
    [
        {"type": "volume", "source": "other", "target": "/var/lib/postgresql/data"},
        {"type": "bind", "source": "/var/lib/postgresql", "target": "/data"},
    ],
    ids=("unapproved-volume", "host-bind"),
)
def test_service_unapproved_volume_or_bind_mount_is_rejected(mount: dict[str, str]) -> None:
    def mutate(config: dict[str, Any]) -> None:
        config["services"]["postgres"]["volumes"] = [mount]

    assert _failures_after(mutate)


@pytest.mark.parametrize("key", ["PGHOST", "ALTERNATE_DATABASE_URL"])
def test_alternate_database_target_environment_is_rejected(key: str) -> None:
    def mutate(config: dict[str, Any]) -> None:
        config["services"]["seed"]["environment"][key] = "database.example.invalid"

    assert _failures_after(mutate)


def test_database_service_command_override_is_rejected() -> None:
    def mutate(config: dict[str, Any]) -> None:
        config["services"]["seed"]["command"] = ["psql", "--host", "database.example.invalid"]

    assert _failures_after(mutate)


def test_external_compose_project_environment_is_removed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COMPOSE_PROJECT_NAME", "production")

    environment = demo_lifecycle._subprocess_environment()

    assert "COMPOSE_PROJECT_NAME" not in environment
    assert demo_lifecycle._compose("config")[:4] == [
        "docker",
        "compose",
        "--project-name",
        PROJECT_NAME,
    ]


def test_demo_environment_rejects_database_identity_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    candidate = tmp_path / "demo.env"
    candidate.write_text(
        demo_lifecycle.ENV_FILE.read_text(encoding="utf-8") + "DEMO_DATABASE_NAME=production\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(demo_lifecycle, "ENV_FILE", candidate)

    with pytest.raises(RuntimeError, match=r"DEMO_\* values only"):
        demo_lifecycle._read_demo_environment()


def test_demo_environment_rejects_database_password_url_delimiter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    candidate = tmp_path / "demo.env"
    contents = demo_lifecycle.ENV_FILE.read_text(encoding="utf-8").replace(
        "synthetic-demo-admin-password", "synthetic@demo/password"
    )
    candidate.write_text(contents, encoding="utf-8")
    monkeypatch.setattr(demo_lifecycle, "ENV_FILE", candidate)

    with pytest.raises(RuntimeError, match="URL-safe unreserved"):
        demo_lifecycle._read_demo_environment()


def test_runtime_volume_label_mismatch_prevents_destructive_command(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    commands: list[list[str]] = []

    def fake_run(command: list[str], *, capture: bool = False) -> subprocess.CompletedProcess[str]:
        del capture
        commands.append(command)
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=json.dumps(
                [
                    {
                        "Name": f"{PROJECT_NAME}_phase2e_demo_postgres",
                        "Labels": {
                            **DEMO_LABELS,
                            "com.docker.compose.project": "different-project",
                            "com.docker.compose.volume": "phase2e_demo_postgres",
                        },
                    }
                ]
            ),
            stderr="",
        )

    monkeypatch.setattr(demo_lifecycle, "_require_tools", lambda: True)
    monkeypatch.setattr(demo_lifecycle, "_validate_config", lambda: True)
    monkeypatch.setattr(demo_lifecycle, "_run", fake_run)

    assert demo_lifecycle.reset() == 2
    assert commands == [["docker", "volume", "inspect", f"{PROJECT_NAME}_phase2e_demo_postgres"]]
    assert not any("down" in command for command in commands)


def test_validator_nonzero_prevents_down_migration_and_seed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lifecycle_commands: list[list[str]] = []

    def fake_lifecycle_run(
        command: list[str], *, capture: bool = False
    ) -> subprocess.CompletedProcess[str]:
        del capture
        lifecycle_commands.append(command)
        return subprocess.CompletedProcess(command, 0, stdout="{}", stderr="")

    def fake_validator_run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        del kwargs
        return subprocess.CompletedProcess(command, 2, stdout="", stderr="invalid")

    monkeypatch.setattr(demo_lifecycle, "_require_tools", lambda: True)
    monkeypatch.setattr(demo_lifecycle, "_run", fake_lifecycle_run)
    monkeypatch.setattr(demo_lifecycle.subprocess, "run", fake_validator_run)

    assert demo_lifecycle.reset() == 2
    assert len(lifecycle_commands) == 1
    assert lifecycle_commands[0][-3:] == ["config", "--format", "json"]
    assert not any(
        token in {"down", "up", "migrate", "seed"}
        for command in lifecycle_commands
        for token in command
    )
