"""Real PostgreSQL/API proof for the Arcana core vertical slice."""

from __future__ import annotations

import os
import subprocess
import uuid
from collections.abc import Iterator
from pathlib import Path

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg import sql
from sqlalchemy.engine import URL, make_url

from creativedeploy_api.api.dependencies import get_current_principal
from creativedeploy_api.app_factory import create_app
from creativedeploy_api.core.config import Settings
from creativedeploy_api.core.principal import AuthenticationMode, PrincipalContext, PrincipalType

pytestmark = pytest.mark.integration

REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
SCHEMA_PREFIX = "arcana_api_test_"


def _connection_kwargs(database_url: URL) -> dict[str, object]:
    values: dict[str, object] = {
        "dbname": database_url.database,
        "user": database_url.username,
        "password": database_url.password,
        "host": database_url.host,
        "port": database_url.port,
    }
    options = database_url.query.get("options")
    if isinstance(options, str):
        values["options"] = options
    return values


def _schema_url(base_url: URL, schema_name: str) -> URL:
    return base_url.update_query_dict({"options": f"-csearch_path={schema_name}"})


@pytest.fixture
def arcana_database(tmp_path: Path) -> Iterator[tuple[URL, str]]:
    base_url = make_url(Settings().require_database_url().get_secret_value())
    schema_name = f"{SCHEMA_PREFIX}{uuid.uuid4().hex}"
    with psycopg.connect(**_connection_kwargs(base_url), autocommit=True) as connection:
        connection.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema_name)))
    schema_url = _schema_url(base_url, schema_name)
    environment = os.environ.copy()
    for name in (
        "POSTGRES_HOST",
        "POSTGRES_PORT",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
        "POSTGRES_DB",
    ):
        environment.pop(name, None)
    environment["DATABASE_URL"] = schema_url.render_as_string(hide_password=False)
    environment["CREATIVEDEPLOY_ENV_FILE"] = "/dev/null"
    completed = subprocess.run(
        [
            "uv",
            "run",
            "--project",
            "apps/api",
            "alembic",
            "-c",
            "apps/api/alembic.ini",
            "upgrade",
            "head",
        ],
        cwd=REPOSITORY_ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert completed.returncode == 0, completed.stderr
    try:
        yield schema_url, schema_name
    finally:
        with psycopg.connect(**_connection_kwargs(base_url), autocommit=True) as connection:
            connection.execute(
                sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema_name))
            )


def _principal(principal_id: str) -> PrincipalContext:
    return PrincipalContext(
        principal_id=principal_id,
        principal_type=PrincipalType.HUMAN,
        display_name=principal_id,
        authentication_mode=AuthenticationMode.CONFIGURED_DEMO_OPERATOR,
    )


def test_arcana_complete_owner_scoped_fixture_loop(
    arcana_database: tuple[URL, str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database_url, _schema_name = arcana_database
    for name in (
        "POSTGRES_HOST",
        "POSTGRES_PORT",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
        "POSTGRES_DB",
    ):
        monkeypatch.delenv(name, raising=False)
    settings = Settings(
        app_env="test",
        database_url=database_url.render_as_string(hide_password=False),
        identity_provider="configured_demo",
        paintpilot_demo_principal_id="arcana-owner-a",
        paintpilot_demo_principal_display_name="Arcana Owner A",
        image_storage_provider="local_filesystem",
        image_storage_root=tmp_path,
        _env_file=None,
    )
    app = create_app(settings)

    with TestClient(app) as client:
        catalog = client.get("/api/v1/arcana/catalog")
        assert catalog.status_code == 200
        assert len(catalog.json()["cards"]) == 78

        created = client.post(
            "/api/v1/arcana/readings",
            json={"question": "What deserves my attention?", "generation_locale": "en-US"},
        )
        assert created.status_code == 201
        reading_id = created.json()["id"]

        drawn = client.post(f"/api/v1/arcana/readings/{reading_id}/draw")
        assert drawn.status_code == 200
        cards = drawn.json()["cards"]
        assert len(cards) == 3
        assert len({card["card"]["id"] for card in cards}) == 3
        assert {card["orientation"] for card in cards} <= {"upright", "reversed"}
        assert client.post(f"/api/v1/arcana/readings/{reading_id}/draw").status_code == 409

        interpreted = client.post(f"/api/v1/arcana/readings/{reading_id}/interpret")
        assert interpreted.status_code == 200
        document = interpreted.json()["interpretation"]["document"]
        assert document["schema_version"] == "tarot-reading.v2"
        assert len(document["positions"]) == 3
        assert 3 <= len(document["relationship_analysis"]) <= 4
        assert 1 <= len(document["actionable_reflections"]) <= 3
        assert 2 <= len(document["reflection_prompts"]) <= 4
        assert len(document["knowledge_basis"]) == 3
        assert {item["retrieval_mode"] for item in document["knowledge_basis"]} == {
            "repository_local_only"
        }

        saved = client.put(
            f"/api/v1/arcana/readings/{reading_id}/journal",
            json={"personal_interpretation": "My view", "notes": "My private note"},
        )
        assert saved.status_code == 200
        assert saved.json()["status"] == "saved"
        assert saved.json()["journal"]["notes"] == "My private note"
        assert saved.json()["interpretation"]["document"] == document

        history = client.get("/api/v1/arcana/readings")
        assert history.status_code == 200
        assert [item["id"] for item in history.json()["items"]] == [reading_id]
        share = client.get(f"/api/v1/arcana/readings/{reading_id}/share-preview")
        assert share.status_code == 200
        assert share.json()["private_local_preview"] is True

        app.dependency_overrides[get_current_principal] = lambda: _principal("arcana-owner-b")
        assert client.get(f"/api/v1/arcana/readings/{reading_id}").status_code == 404
        assert client.get("/api/v1/arcana/readings").json()["items"] == []

    with psycopg.connect(**_connection_kwargs(database_url)) as connection:
        assert connection.execute("SELECT count(*) FROM tarot_card_definitions").fetchone() == (78,)
        assert connection.execute("SELECT count(*) FROM tarot_reading_cards").fetchone() == (3,)
        assert connection.execute(
            "SELECT count(*) FROM tarot_interpretation_revisions"
        ).fetchone() == (1,)
        assert connection.execute("SELECT count(*) FROM tarot_journal_entries").fetchone() == (1,)
