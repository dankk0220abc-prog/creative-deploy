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
REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
POSTGRES_IMAGE = (
    "postgres:17.10-alpine3.24@"
    "sha256:742f40ea20b9ff2ff31db5458d127452988a2164df9e17441e191f3b72252193"
)
MINIO_IMAGE = (
    "minio/minio:RELEASE.2025-09-07T16-13-09Z@"
    "sha256:14cea493d9a34af32f524e538b8346cf79f3321eff8e708c1e2960462bd8936e"
)
MERGE_SOURCE_CASES = (
    f"name: {PROJECT_NAME}\nbase: &base\n  services: {{}}\n\n<<: *base\n",
    f"name: {PROJECT_NAME}\nbase: &base\n  services: {{}}\n\n!!merge alternate: *base\n",
)


def _api_build(target: str = "demo-runtime") -> dict[str, str]:
    return {
        "context": str(REPOSITORY_ROOT),
        "dockerfile": "apps/api/Dockerfile",
        "target": target,
    }


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
                image=POSTGRES_IMAGE,
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
                image=MINIO_IMAGE,
                command=["server", "/data", "--console-address", ":9001"],
                volumes=[
                    {
                        "type": "volume",
                        "source": "phase2e_demo_minio",
                        "target": "/data",
                    }
                ],
            ),
            "oidc": _service(
                build=_api_build(),
                command=[
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
            ),
            "role_provision": _service(
                build=_api_build(),
                command=role_command,
                environment=dict(role_environment),
                depends_on={"postgres": {"condition": "service_healthy"}},
            ),
            "migrate": _service(
                build=_api_build("migration"),
                environment={"DATABASE_URL": _database_url("paintpilot_demo_migrator")},
                depends_on={"role_provision": {"condition": "service_completed_successfully"}},
            ),
            "role_grant": _service(
                build=_api_build(),
                command=role_command,
                environment=dict(role_environment),
                depends_on={"migrate": {"condition": "service_completed_successfully"}},
            ),
            "seed": _service(
                build=_api_build(),
                command=["python", "-m", "creativedeploy_api.tools.seed_demo"],
                environment={
                    "DATABASE_URL": _database_url("paintpilot_demo_runtime"),
                    "PAINTPILOT_DEMO_SEED_ENABLED": "true",
                },
                depends_on={"role_grant": {"condition": "service_completed_successfully"}},
            ),
            "api": _service(
                build=_api_build(),
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
                build={
                    "context": str(REPOSITORY_ROOT),
                    "dockerfile": "apps/web/Dockerfile",
                    "target": "demo-runtime",
                    "args": {"VITE_RUNTIME_PROFILE": "public-demo"},
                },
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


def test_correct_source_project_name_is_accepted() -> None:
    source = f"name: {PROJECT_NAME}\nservices: {{}}\n"

    assert validate_demo_config.validate_source(source) == []


def test_source_name_tracked_demo_source_is_accepted() -> None:
    assert validate_demo_config.validate_source_file(REPOSITORY_ROOT / "compose.demo.yaml") == []


@pytest.mark.parametrize("source", MERGE_SOURCE_CASES, ids=("plain-key", "explicit-tag"))
def test_yaml_merge_source_key_is_rejected(source: str) -> None:
    assert validate_demo_config.validate_source(source) == [
        "compose source must not contain YAML merge keys"
    ]


@pytest.mark.parametrize(
    "source",
    [
        "services: {}\n",
        "name: not-the-demo\nservices: {}\n",
        "name: ''\nservices: {}\n",
        "name: null\nservices: {}\n",
        "name: 123\nservices: {}\n",
        "name: ${DEMO_PROJECT_NAME}\nservices: {}\n",
        f"x-project: &project {PROJECT_NAME}\nname: *project\nservices: {{}}\n",
        f"name: {PROJECT_NAME}\nname: {PROJECT_NAME}\nservices: {{}}\n",
    ],
    ids=(
        "missing",
        "wrong",
        "empty",
        "null",
        "non-string",
        "interpolation",
        "alias",
        "duplicate",
    ),
)
def test_invalid_source_project_name_is_rejected(source: str) -> None:
    assert validate_demo_config.validate_source(source)


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


@pytest.mark.parametrize(
    "mutator",
    [
        lambda config: config["services"]["oidc"].update(
            command=[
                "sh",
                "-c",
                "write-to-external-postgres; start-oidc --port 18090",
            ]
        ),
        lambda config: config["services"]["oidc"].update(command=["malicious-command", "18090"]),
        lambda config: config["services"]["oidc"].update(
            command=[
                "sh",
                "-c",
                "python -m uvicorn creativedeploy_api.local_oidc:app --port 18090",
            ]
        ),
        lambda config: config["services"]["migrate"].update(
            command=["python", "-m", "alembic", "downgrade", "base"]
        ),
        lambda config: config["services"]["seed"].update(
            command=["python", "-m", "creativedeploy_api.tools.other_seed"]
        ),
        lambda config: config["services"]["role_provision"].update(
            command=["python", "-m", "creativedeploy_api.tools.other_roles"]
        ),
        lambda config: config["services"]["api"].update(command=["python", "other.py"]),
        lambda config: config["services"]["web"].update(command=["sh", "-c", "nginx"]),
        lambda config: config["services"]["api"].update(entrypoint=["sh", "-c"]),
        lambda config: config["services"]["web"].update(entrypoint=["malicious-entrypoint"]),
    ],
    ids=(
        "oidc-external-postgres-with-port-token",
        "oidc-arbitrary-command",
        "oidc-shell-wrapper",
        "migration-command",
        "seed-command",
        "role-provision-command",
        "api-command",
        "web-command",
        "api-entrypoint",
        "web-entrypoint",
    ),
)
def test_command_or_entrypoint_identity_drift_is_rejected(
    mutator: Callable[[dict[str, Any]], None],
) -> None:
    assert _failures_after(mutator)


@pytest.mark.parametrize(
    "mutator",
    [
        lambda config: config["services"]["postgres"].update(image="postgres:latest"),
        lambda config: config["services"]["postgres"].update(build={"context": "."}),
        lambda config: config["services"]["api"]["build"].update(context="/tmp/outside"),
        lambda config: config["services"]["oidc"]["build"].update(
            context="https://example.invalid/source.git"
        ),
        lambda config: config["services"]["api"]["build"].update(
            dockerfile="Dockerfile.unapproved"
        ),
        lambda config: config["services"]["migrate"]["build"].update(target="demo-runtime"),
        lambda config: config["services"]["api"].update(image="unapproved:latest"),
        lambda config: config["services"]["web"]["build"].update(
            args={
                "VITE_RUNTIME_PROFILE": "public-demo",
                "UNAPPROVED_BUILD_ARG": "1",
            }
        ),
    ],
    ids=(
        "image-reference",
        "image-plus-build",
        "absolute-outside-context",
        "remote-context",
        "dockerfile",
        "target",
        "build-plus-image",
        "build-args",
    ),
)
def test_image_or_build_identity_drift_is_rejected(
    mutator: Callable[[dict[str, Any]], None],
) -> None:
    assert _failures_after(mutator)


def test_extra_service_is_rejected() -> None:
    def mutate(config: dict[str, Any]) -> None:
        config["services"]["unapproved"] = _service(image="busybox:latest")

    assert _failures_after(mutate)


def test_required_service_missing_is_rejected() -> None:
    def mutate(config: dict[str, Any]) -> None:
        config["services"].pop("oidc")

    assert _failures_after(mutate)


def test_service_profile_membership_drift_is_rejected() -> None:
    def mutate(config: dict[str, Any]) -> None:
        config["services"]["seed"]["profiles"] = ["unapproved"]

    assert _failures_after(mutate)


def test_external_compose_environment_cannot_change_project_or_profiles(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("COMPOSE_PROJECT_NAME", "production")
    monkeypatch.setenv("COMPOSE_PROFILES", "unapproved")

    environment = demo_lifecycle._subprocess_environment()

    assert "COMPOSE_PROJECT_NAME" not in environment
    assert "COMPOSE_PROFILES" not in environment
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


def test_source_name_failure_precedes_render_and_prevents_mutation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lifecycle_commands: list[list[str]] = []
    validator_commands: list[list[str]] = []

    def fake_lifecycle_run(
        command: list[str], *, capture: bool = False
    ) -> subprocess.CompletedProcess[str]:
        del capture
        lifecycle_commands.append(command)
        return subprocess.CompletedProcess(command, 0, stdout="{}", stderr="")

    def fake_validator_run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        del kwargs
        validator_commands.append(command)
        return subprocess.CompletedProcess(command, 2, stdout="", stderr="source invalid")

    monkeypatch.setattr(demo_lifecycle, "_require_tools", lambda: True)
    monkeypatch.setattr(demo_lifecycle, "_run", fake_lifecycle_run)
    monkeypatch.setattr(demo_lifecycle.subprocess, "run", fake_validator_run)

    assert demo_lifecycle.reset() == 2
    assert lifecycle_commands == []
    assert len(validator_commands) == 1
    assert "--source-compose" in validator_commands[0]
    assert "--project-name" not in validator_commands[0]


@pytest.mark.parametrize("source", MERGE_SOURCE_CASES, ids=("plain-key", "explicit-tag"))
def test_source_merge_failure_precedes_render_and_prevents_mutation(
    source: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    candidate = tmp_path / "compose.demo.yaml"
    candidate.write_text(source, encoding="utf-8")
    lifecycle_commands: list[list[str]] = []
    validator_commands: list[list[str]] = []

    def fake_lifecycle_run(
        command: list[str], *, capture: bool = False
    ) -> subprocess.CompletedProcess[str]:
        del capture
        lifecycle_commands.append(command)
        return subprocess.CompletedProcess(command, 0, stdout="{}", stderr="")

    def fake_validator_run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        del kwargs
        validator_commands.append(command)
        source_path = Path(command[command.index("--source-compose") + 1])
        failures = validate_demo_config.validate_source_file(source_path)
        return subprocess.CompletedProcess(
            command,
            2 if failures else 0,
            stdout="",
            stderr="YAML merge key rejected" if failures else "",
        )

    monkeypatch.setattr(demo_lifecycle, "COMPOSE_FILE", candidate)
    monkeypatch.setattr(demo_lifecycle, "_require_tools", lambda: True)
    monkeypatch.setattr(demo_lifecycle, "_run", fake_lifecycle_run)
    monkeypatch.setattr(demo_lifecycle.subprocess, "run", fake_validator_run)

    assert demo_lifecycle.reset() == 2
    assert lifecycle_commands == []
    assert len(validator_commands) == 1
    assert "--source-compose" in validator_commands[0]


@pytest.mark.parametrize(
    "mutator",
    [
        lambda config: config["services"]["oidc"].update(
            command=["sh", "-c", "external-postgres-write; normal-oidc --port 18090"]
        ),
        lambda config: config["services"]["web"].update(entrypoint=["sh", "-c"]),
        lambda config: config["services"]["postgres"].update(image="postgres:latest"),
        lambda config: config["services"]["api"]["build"].update(context="/tmp/outside"),
    ],
    ids=("command", "entrypoint", "image", "build"),
)
def test_execution_identity_failure_prevents_destructive_or_mutating_commands(
    mutator: Callable[[dict[str, Any]], None],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _valid_config()
    mutator(config)
    lifecycle_commands: list[list[str]] = []

    def fake_lifecycle_run(
        command: list[str], *, capture: bool = False
    ) -> subprocess.CompletedProcess[str]:
        del capture
        lifecycle_commands.append(command)
        return subprocess.CompletedProcess(command, 0, stdout=json.dumps(config), stderr="")

    def fake_validator_run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if "--source-compose" in command:
            return subprocess.CompletedProcess(command, 0, stdout="source valid", stderr="")
        rendered = json.loads(kwargs["input"])
        failures = validate_demo_config.validate(rendered)
        return subprocess.CompletedProcess(
            command,
            2 if failures else 0,
            stdout="" if failures else "valid",
            stderr="invalid" if failures else "",
        )

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
