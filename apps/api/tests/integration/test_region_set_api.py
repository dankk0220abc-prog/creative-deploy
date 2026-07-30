"""Real PostgreSQL, private image, and API closure for Phase 1F RegionSets."""

import concurrent.futures
import io
import os
import subprocess
import uuid
from collections.abc import Iterator
from pathlib import Path

import psycopg
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from psycopg import sql
from sqlalchemy.engine import URL, make_url

from creativedeploy_api.app_factory import create_app
from creativedeploy_api.core.config import Settings

pytestmark = pytest.mark.integration

REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
ALEMBIC_COMMAND = (
    "uv",
    "run",
    "--project",
    "apps/api",
    "alembic",
    "-c",
    "apps/api/alembic.ini",
)
SCHEMA_PREFIX = "phase1f_api_test_"
MARKER_TABLE = "fixture_ownership"


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


def _schema_database_url(base_url: URL, schema_name: str) -> URL:
    return base_url.update_query_dict({"options": f"-csearch_path={schema_name}"})


def _run_alembic(database_url: URL, *arguments: str) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["DATABASE_URL"] = database_url.render_as_string(hide_password=False)
    completed = subprocess.run(
        [*ALEMBIC_COMMAND, *arguments],
        cwd=REPOSITORY_ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert completed.returncode == 0, (
        f"Alembic {' '.join(arguments)} failed.\n"
        f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
    )
    return completed


@pytest.fixture
def region_set_integration_settings(tmp_path: Path) -> Iterator[Settings]:
    development = Settings()
    base_url = make_url(development.database_url.get_secret_value())
    schema_name = f"{SCHEMA_PREFIX}{uuid.uuid4().hex}"
    ownership_token = uuid.uuid4().hex
    with psycopg.connect(**_connection_kwargs(base_url), autocommit=True) as connection:
        try:
            connection.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema_name)))
        except psycopg.errors.DuplicateSchema:
            pytest.fail("Random isolated schema already existed; cleanup was refused.")
        connection.execute(
            sql.SQL("CREATE TABLE {}.{} (token text PRIMARY KEY)").format(
                sql.Identifier(schema_name),
                sql.Identifier(MARKER_TABLE),
            )
        )
        connection.execute(
            sql.SQL("INSERT INTO {}.{} (token) VALUES (%s)").format(
                sql.Identifier(schema_name),
                sql.Identifier(MARKER_TABLE),
            ),
            (ownership_token,),
        )
    schema_url = _schema_database_url(base_url, schema_name)
    _run_alembic(schema_url, "upgrade", "head")
    settings = Settings(
        app_env="test",
        database_url=schema_url.render_as_string(hide_password=False),
        database_lock_timeout_ms=3_000,
        database_statement_timeout_ms=5_000,
        paintpilot_demo_principal_id=f"phase1f-owner-{uuid.uuid4().hex}",
        paintpilot_demo_principal_display_name="Phase 1F Integration Owner",
        image_storage_root=tmp_path / "private-images",
        _env_file=None,
    )
    try:
        yield settings
    finally:
        with psycopg.connect(
            **_connection_kwargs(base_url),
            autocommit=True,
        ) as connection:
            marker = connection.execute(
                sql.SQL("SELECT token FROM {}.{}").format(
                    sql.Identifier(schema_name),
                    sql.Identifier(MARKER_TABLE),
                )
            ).fetchone()
            assert marker == (ownership_token,)
            connection.execute(
                sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema_name))
            )
            residual = connection.execute(
                "SELECT count(*) FROM pg_namespace WHERE nspname = %s",
                (schema_name,),
            ).fetchone()
            assert residual == (0,)


def _image_bytes(color: str, image_format: str = "JPEG") -> bytes:
    output = io.BytesIO()
    image = Image.new("RGB", (900, 768), color)
    image.save(output, format=image_format, quality=90)
    return output.getvalue()


def _create_project(client: TestClient, title: str = "Synthetic Phase 1F case") -> dict:
    response = client.post(
        "/api/v1/paint-projects",
        headers={"Idempotency-Key": str(uuid.uuid4())},
        json={"title": title, "description": "Program-generated images and polygons only."},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _upload(
    client: TestClient,
    project_id: str,
    *,
    role: str,
    color: str,
    key: uuid.UUID | None = None,
) -> object:
    return client.post(
        f"/api/v1/paint-projects/{project_id}/images",
        headers={"Idempotency-Key": str(key or uuid.uuid4())},
        data={
            "role": role,
            "source_type": "user_provided",
            "intended_usage": "private_project",
            "rights_attestation_confirmed": "true",
            "rights_attestation_version": "1",
        },
        files={
            "file": (
                f"{role}.jpg",
                _image_bytes(color),
                "image/jpeg",
            )
        },
    )


def _ready_image_set(client: TestClient, project_id: str) -> dict:
    colors = {
        "primary_front": "#d05040",
        "reference_back": "#3060b0",
        "reference_angle": "#40a060",
    }
    for role, color in colors.items():
        uploaded = _upload(client, project_id, role=role, color=color)
        assert uploaded.status_code == 201, uploaded.text
    review = client.post(
        f"/api/v1/paint-projects/{project_id}/image-set/readiness-reviews",
        headers={"Idempotency-Key": str(uuid.uuid4())},
        json={"verdict": "ready", "reason": None},
    )
    assert review.status_code == 201, review.text
    image_set = client.get(f"/api/v1/paint-projects/{project_id}/image-set")
    assert image_set.status_code == 200
    assert image_set.json()["status"] == "ready"
    return image_set.json()


def _regions(*, offset: int = 0) -> list[dict[str, object]]:
    definitions = [
        ("paint", "hair", 50_000, 50_000),
        ("paint", "skin", 400_000, 80_000),
        ("paint", "shirt", 200_000, 450_000),
        ("exclude", "background", 650_000, 600_000),
    ]
    result: list[dict[str, object]] = []
    for z_index, (kind, label, x, y) in enumerate(definitions):
        x += offset
        result.append(
            {
                "stable_region_key": str(uuid.uuid5(uuid.NAMESPACE_URL, f"phase1f:{kind}:{label}")),
                "kind": kind,
                "label": label,
                "z_index": z_index,
                "opacity_ppm": 500_000,
                "notes": f"Human {label} annotation.",
                "vertices": [
                    {"x_ppm": x, "y_ppm": y},
                    {"x_ppm": x + 180_000, "y_ppm": y},
                    {"x_ppm": x + 180_000, "y_ppm": y + 180_000},
                    {"x_ppm": x, "y_ppm": y + 180_000},
                ],
            }
        )
    return result


def _save(
    client: TestClient,
    project_id: str,
    *,
    base: dict | None,
    regions: list[dict[str, object]],
    key: uuid.UUID,
) -> object:
    return client.post(
        f"/api/v1/paint-projects/{project_id}/region-sets",
        headers={"Idempotency-Key": str(key)},
        json={
            "base_region_set_id": None if base is None else base["id"],
            "base_version": None if base is None else base["version"],
            "regions": regions,
        },
    )


def _submit(
    client: TestClient,
    project_id: str,
    region_set_id: str,
    key: uuid.UUID,
) -> object:
    return client.post(
        f"/api/v1/paint-projects/{project_id}/region-sets/{region_set_id}/submit",
        headers={"Idempotency-Key": str(key)},
        json={},
    )


def _fork(
    client: TestClient,
    project_id: str,
    source_region_set_id: str,
    *,
    expected_current: dict,
    key: uuid.UUID,
) -> object:
    return client.post(
        f"/api/v1/paint-projects/{project_id}/region-sets/{source_region_set_id}/drafts",
        headers={"Idempotency-Key": str(key)},
        json={
            "expected_current_region_set_id": expected_current["id"],
            "expected_current_version": expected_current["version"],
        },
    )


def _review(
    client: TestClient,
    project_id: str,
    region_set_id: str,
    *,
    verdict: str,
    reason: str | None,
    key: uuid.UUID,
) -> object:
    return client.post(
        f"/api/v1/paint-projects/{project_id}/region-sets/{region_set_id}/reviews",
        headers={"Idempotency-Key": str(key)},
        json={"verdict": verdict, "reason": reason},
    )


def test_phase_1f_migration_round_trip_and_catalog(
    region_set_integration_settings: Settings,
) -> None:
    database_url = make_url(region_set_integration_settings.database_url.get_secret_value())
    _run_alembic(database_url, "downgrade", "d4c8a1f7b2e9")
    _run_alembic(database_url, "upgrade", "head")
    with psycopg.connect(**_connection_kwargs(database_url)) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = current_schema()
                """
            )
        }
        assert {
            "region_sets",
            "regions",
            "region_vertices",
            "region_set_reviews",
        } <= tables
        triggers = {
            row[0]
            for row in connection.execute(
                """
                SELECT trigger_name
                FROM information_schema.triggers
                WHERE event_object_schema = current_schema()
                """
            )
        }
        assert {
            "trg_region_sets_append_only",
            "trg_regions_append_only",
            "trg_region_vertices_append_only",
            "trg_region_set_reviews_append_only",
        } <= triggers


def test_region_set_version_idempotency_lifecycle_stale_restart_and_owner_isolation(
    region_set_integration_settings: Settings,
) -> None:
    settings = region_set_integration_settings
    with TestClient(create_app(settings)) as client:
        project = _create_project(client)
        project_id = project["id"]
        image_set = _ready_image_set(client, project_id)
        workbench = client.get(f"/api/v1/paint-projects/{project_id}/region-sets/workbench")
        assert workbench.status_code == 200
        assert workbench.json()["image_set_status"] == "ready"
        assert workbench.json()["current_region_set"] is None
        assert workbench.json()["source_primary_image_asset_id"] == next(
            slot["current"]["id"] for slot in image_set["roles"] if slot["role"] == "primary_front"
        )

        invalid = _regions()
        invalid[0]["vertices"] = [
            {"x_ppm": 100_000, "y_ppm": 100_000},
            {"x_ppm": 400_000, "y_ppm": 400_000},
            {"x_ppm": 100_000, "y_ppm": 400_000},
            {"x_ppm": 400_000, "y_ppm": 100_000},
        ]
        rejected = _save(
            client,
            project_id,
            base=None,
            regions=invalid,
            key=uuid.uuid4(),
        )
        assert rejected.status_code == 422
        assert rejected.json()["error_code"] == "REGION_GEOMETRY_INVALID", rejected.text
        assert rejected.json()["safe_details"]["geometry_code"] == ("polygon_self_intersection")

        first_key = uuid.uuid4()
        first_response = _save(
            client,
            project_id,
            base=None,
            regions=_regions(),
            key=first_key,
        )
        assert first_response.status_code == 201, first_response.text
        first = first_response.json()
        assert first["version"] == 1
        assert first["lifecycle"] == "draft"
        assert first["effective_lifecycle"] == "draft"
        assert first["region_count"] == 4
        assert first["total_vertex_count"] == 16
        assert first["stale"] is False
        assert len(first["geometry_fingerprint"]) == 64

        replay = _save(
            client,
            project_id,
            base=None,
            regions=_regions(),
            key=first_key,
        )
        assert replay.status_code == 201
        assert replay.json() == first
        changed_replay = _save(
            client,
            project_id,
            base=None,
            regions=_regions(offset=10_000),
            key=first_key,
        )
        assert changed_replay.status_code == 409
        assert changed_replay.json()["error_code"] == "IDEMPOTENCY_KEY_REUSED"

        def concurrent_save(offset: int) -> tuple[int, dict]:
            with TestClient(create_app(settings)) as concurrent_client:
                response = _save(
                    concurrent_client,
                    project_id,
                    base=first,
                    regions=_regions(offset=offset),
                    key=uuid.uuid4(),
                )
                return response.status_code, response.json()

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(concurrent_save, (5_000, 10_000)))
        assert sorted(status for status, _ in outcomes) == [201, 409]
        winner = next(payload for status, payload in outcomes if status == 201)
        loser = next(payload for status, payload in outcomes if status == 409)
        assert winner["version"] == 2
        assert loser["error_code"] == "REGION_SET_STALE_VERSION"

        direct = client.get(f"/api/v1/paint-projects/{project_id}/region-sets/{winner['id']}")
        assert direct.status_code == 200
        assert direct.json()["regions"] == winner["regions"]

        submit_key = uuid.uuid4()
        submitted_response = _submit(
            client,
            project_id,
            winner["id"],
            submit_key,
        )
        assert submitted_response.status_code == 201, submitted_response.text
        submitted = submitted_response.json()
        assert submitted["version"] == 3
        assert submitted["lifecycle"] == "submitted"
        assert submitted["effective_lifecycle"] == "submitted"
        assert [
            {key: value for key, value in region.items() if key != "id"}
            for region in submitted["regions"]
        ] == [
            {key: value for key, value in region.items() if key != "id"}
            for region in winner["regions"]
        ]
        submit_replay = _submit(
            client,
            project_id,
            winner["id"],
            submit_key,
        )
        assert submit_replay.status_code == 201
        assert submit_replay.json() == submitted

        approve_key = uuid.uuid4()
        approval_response = _review(
            client,
            project_id,
            submitted["id"],
            verdict="approved",
            reason=None,
            key=approve_key,
        )
        assert approval_response.status_code == 201, approval_response.text
        approval = approval_response.json()
        assert approval["verdict"] == "approved"
        approval_replay = _review(
            client,
            project_id,
            submitted["id"],
            verdict="approved",
            reason=None,
            key=approve_key,
        )
        assert approval_replay.status_code == 201
        assert approval_replay.json() == approval
        duplicate_review = _review(
            client,
            project_id,
            submitted["id"],
            verdict="changes_requested",
            reason="Changed review.",
            key=uuid.uuid4(),
        )
        assert duplicate_review.status_code == 409
        assert duplicate_review.json()["error_code"] == "REGION_SET_LIFECYCLE_CONFLICT"
        approved_detail = client.get(
            f"/api/v1/paint-projects/{project_id}/region-sets/{submitted['id']}"
        ).json()
        assert approved_detail["effective_lifecycle"] == "approved"

    with TestClient(create_app(settings)) as restarted:
        persisted = restarted.get(f"/api/v1/paint-projects/{project_id}/region-sets/workbench")
        assert persisted.status_code == 200
        assert persisted.json()["current_region_set"]["effective_lifecycle"] == "approved"
        assert len(persisted.json()["current_region_set"]["regions"]) == 4

        replacement = _upload(
            restarted,
            project_id,
            role="reference_angle",
            color="#8020a0",
        )
        assert replacement.status_code == 201, replacement.text
        stale = restarted.get(f"/api/v1/paint-projects/{project_id}/region-sets/{submitted['id']}")
        assert stale.status_code == 200
        assert stale.json()["stale"] is True
        assert "image_set_fingerprint_changed" in stale.json()["stale_reasons"]

        blocked_review = _review(
            restarted,
            project_id,
            submitted["id"],
            verdict="approved",
            reason=None,
            key=uuid.uuid4(),
        )
        assert blocked_review.status_code == 409

        new_ready = restarted.post(
            f"/api/v1/paint-projects/{project_id}/image-set/readiness-reviews",
            headers={"Idempotency-Key": str(uuid.uuid4())},
            json={"verdict": "ready", "reason": None},
        )
        assert new_ready.status_code == 201, new_ready.text

        from_approved = _save(
            restarted,
            project_id,
            base=submitted,
            regions=_regions(offset=20_000),
            key=uuid.uuid4(),
        )
        assert from_approved.status_code == 201, from_approved.text
        revised_draft = from_approved.json()
        assert revised_draft["version"] == 4
        revised_submit = _submit(
            restarted,
            project_id,
            revised_draft["id"],
            uuid.uuid4(),
        )
        assert revised_submit.status_code == 201
        submitted_v5 = revised_submit.json()
        changes = _review(
            restarted,
            project_id,
            submitted_v5["id"],
            verdict="changes_requested",
            reason="Adjust the shirt edge before approval.",
            key=uuid.uuid4(),
        )
        assert changes.status_code == 201
        assert changes.json()["reason"] == "Adjust the shirt edge before approval."
        detail_v5 = restarted.get(
            f"/api/v1/paint-projects/{project_id}/region-sets/{submitted_v5['id']}"
        ).json()
        assert detail_v5["effective_lifecycle"] == "changes_requested"

        history = restarted.get(f"/api/v1/paint-projects/{project_id}/region-sets")
        assert history.status_code == 200
        assert [item["version"] for item in history.json()["items"]] == [5, 4, 3, 2, 1]
        review_history = restarted.get(
            f"/api/v1/paint-projects/{project_id}/region-sets/{submitted_v5['id']}/reviews"
        )
        assert review_history.status_code == 200
        assert [item["verdict"] for item in review_history.json()["items"]] == ["changes_requested"]

        unknown = restarted.post(
            f"/api/v1/paint-projects/{project_id}/region-sets",
            headers={"Idempotency-Key": str(uuid.uuid4())},
            json={
                "base_region_set_id": submitted_v5["id"],
                "base_version": submitted_v5["version"],
                "regions": _regions(),
                "owner_id": "forged-owner",
            },
        )
        assert unknown.status_code == 422
        assert "forged-owner" not in unknown.text

    other_settings = settings.model_copy(
        update={
            "paintpilot_demo_principal_id": f"phase1f-other-{uuid.uuid4().hex}",
            "paintpilot_demo_principal_display_name": "Other Phase 1F Owner",
        }
    )
    with TestClient(create_app(other_settings)) as other:
        for path in (
            f"/api/v1/paint-projects/{project_id}/region-sets/workbench",
            f"/api/v1/paint-projects/{project_id}/region-sets",
            f"/api/v1/paint-projects/{project_id}/region-sets/{submitted_v5['id']}",
            f"/api/v1/paint-projects/{project_id}/region-sets/{submitted_v5['id']}/reviews",
        ):
            assert other.get(path).status_code == 404

    database_url = make_url(settings.database_url.get_secret_value())
    with psycopg.connect(**_connection_kwargs(database_url)) as connection:
        table_counts = {
            table: connection.execute(
                sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(table))
            ).fetchone()[0]
            for table in (
                "region_sets",
                "regions",
                "region_vertices",
                "region_set_reviews",
            )
        }
        assert table_counts == {
            "region_sets": 5,
            "regions": 20,
            "region_vertices": 80,
            "region_set_reviews": 2,
        }
        with pytest.raises(psycopg.errors.ObjectNotInPrerequisiteState):
            connection.execute(
                "UPDATE region_sets SET lifecycle = 'approved' WHERE id = %s",
                (submitted["id"],),
            )
        connection.rollback()
        with pytest.raises(psycopg.errors.ObjectNotInPrerequisiteState):
            connection.execute(
                "DELETE FROM region_set_reviews WHERE region_set_id = %s",
                (submitted["id"],),
            )
        connection.rollback()


def test_historical_fork_is_exact_idempotent_owner_scoped_and_serialized(
    region_set_integration_settings: Settings,
) -> None:
    settings = region_set_integration_settings
    database_url = make_url(settings.database_url.get_secret_value())

    def counts(project_id: str) -> dict[str, int]:
        with psycopg.connect(**_connection_kwargs(database_url)) as connection:
            return {
                "region_sets": connection.execute(
                    "SELECT count(*) FROM region_sets WHERE paint_project_id = %s",
                    (project_id,),
                ).fetchone()[0],
                "regions": connection.execute(
                    "SELECT count(*) FROM regions WHERE paint_project_id = %s",
                    (project_id,),
                ).fetchone()[0],
                "vertices": connection.execute(
                    """
                    SELECT count(*)
                    FROM region_vertices AS vertex
                    JOIN region_sets AS snapshot ON snapshot.id = vertex.region_set_id
                    WHERE snapshot.paint_project_id = %s
                    """,
                    (project_id,),
                ).fetchone()[0],
                "fork_commands": connection.execute(
                    """
                    SELECT count(*)
                    FROM command_idempotency_records
                    WHERE command_type = 'fork_region_set_draft'
                      AND scope_key LIKE %s
                    """,
                    (f"%:project:{project_id}:%",),
                ).fetchone()[0],
                "events": connection.execute(
                    "SELECT count(*) FROM state_transition_events WHERE project_id = %s",
                    (project_id,),
                ).fetchone()[0],
            }

    def immutable_content(snapshot: dict) -> dict[str, object]:
        return {
            "id": snapshot["id"],
            "lifecycle": snapshot["lifecycle"],
            "geometry_fingerprint": snapshot["geometry_fingerprint"],
            "created_at": snapshot["created_at"],
            "regions": [
                {key: value for key, value in region.items() if key != "id"}
                for region in snapshot["regions"]
            ],
        }

    with TestClient(create_app(settings)) as client:
        project_id = _create_project(client, "Historical fork contract")["id"]
        _ready_image_set(client, project_id)
        first_response = _save(
            client,
            project_id,
            base=None,
            regions=_regions(),
            key=uuid.uuid4(),
        )
        assert first_response.status_code == 201
        first = first_response.json()
        second_response = _save(
            client,
            project_id,
            base=first,
            regions=_regions(offset=5_000),
            key=uuid.uuid4(),
        )
        assert second_response.status_code == 201
        second = second_response.json()
        third_response = _submit(
            client,
            project_id,
            second["id"],
            uuid.uuid4(),
        )
        assert third_response.status_code == 201
        third = third_response.json()
        assert third["version"] == 3
        first_before = immutable_content(
            client.get(f"/api/v1/paint-projects/{project_id}/region-sets/{first['id']}").json()
        )
        third_before = immutable_content(third)

        baseline = counts(project_id)
        wrong_id = _fork(
            client,
            project_id,
            first["id"],
            expected_current={**third, "id": str(uuid.uuid4())},
            key=uuid.uuid4(),
        )
        assert wrong_id.status_code == 409
        assert wrong_id.json()["error_code"] == "REGION_SET_STALE_VERSION"
        wrong_version = _fork(
            client,
            project_id,
            first["id"],
            expected_current={**third, "version": third["version"] + 1},
            key=uuid.uuid4(),
        )
        assert wrong_version.status_code == 409
        assert wrong_version.json()["error_code"] == "REGION_SET_STALE_VERSION"
        forged = client.post(
            f"/api/v1/paint-projects/{project_id}/region-sets/{first['id']}/drafts",
            headers={"Idempotency-Key": str(uuid.uuid4())},
            json={
                "expected_current_region_set_id": third["id"],
                "expected_current_version": third["version"],
                "owner_id": "forged-owner",
            },
        )
        assert forged.status_code == 422
        assert counts(project_id) == baseline

        other_project_id = _create_project(client, "Other source project")["id"]
        _ready_image_set(client, other_project_id)
        other_source_response = _save(
            client,
            other_project_id,
            base=None,
            regions=_regions(offset=15_000),
            key=uuid.uuid4(),
        )
        assert other_source_response.status_code == 201
        other_project_source = _fork(
            client,
            project_id,
            other_source_response.json()["id"],
            expected_current=third,
            key=uuid.uuid4(),
        )
        assert other_project_source.status_code == 404

        replacement = _upload(
            client,
            project_id,
            role="reference_detail",
            color="#204080",
        )
        assert replacement.status_code == 201
        not_ready_baseline = counts(project_id)
        not_ready = _fork(
            client,
            project_id,
            first["id"],
            expected_current=third,
            key=uuid.uuid4(),
        )
        assert not_ready.status_code == 409
        assert not_ready.json()["error_code"] == "REGION_IMAGE_SET_NOT_READY"
        assert counts(project_id) == not_ready_baseline

        ready = client.post(
            f"/api/v1/paint-projects/{project_id}/image-set/readiness-reviews",
            headers={"Idempotency-Key": str(uuid.uuid4())},
            json={"verdict": "ready", "reason": None},
        )
        assert ready.status_code == 201
        workbench = client.get(f"/api/v1/paint-projects/{project_id}/region-sets/workbench").json()
        assert workbench["current_region_set"]["id"] == third["id"]
        fork_key = uuid.uuid4()
        fork_response = _fork(
            client,
            project_id,
            first["id"],
            expected_current=third,
            key=fork_key,
        )
        assert fork_response.status_code == 201, fork_response.text
        fourth = fork_response.json()
        assert fourth["version"] == 4
        assert fourth["lifecycle"] == "draft"
        assert fourth["based_on_region_set_id"] == first["id"]
        assert fourth["supersedes_region_set_id"] == third["id"]
        assert (
            fourth["source_image_set_fingerprint"] == (workbench["current_image_set_fingerprint"])
        )
        assert (
            fourth["source_primary_image_asset_id"] == (workbench["source_primary_image_asset_id"])
        )
        assert fourth["stale"] is False
        assert immutable_content(fourth)["regions"] == first_before["regions"]
        assert (
            immutable_content(
                client.get(f"/api/v1/paint-projects/{project_id}/region-sets/{first['id']}").json()
            )
            == first_before
        )
        assert (
            immutable_content(
                client.get(f"/api/v1/paint-projects/{project_id}/region-sets/{third['id']}").json()
            )
            == third_before
        )

        after_fork = counts(project_id)
        assert after_fork == {
            **not_ready_baseline,
            "region_sets": not_ready_baseline["region_sets"] + 1,
            "regions": not_ready_baseline["regions"] + 4,
            "vertices": not_ready_baseline["vertices"] + 16,
            "fork_commands": not_ready_baseline["fork_commands"] + 1,
        }
        replay = _fork(
            client,
            project_id,
            first["id"],
            expected_current=third,
            key=fork_key,
        )
        assert replay.status_code == 201
        assert replay.json() == fourth
        assert counts(project_id) == after_fork
        changed_source = _fork(
            client,
            project_id,
            second["id"],
            expected_current=third,
            key=fork_key,
        )
        assert changed_source.status_code == 409
        assert changed_source.json()["error_code"] == "IDEMPOTENCY_KEY_REUSED"
        assert counts(project_id) == after_fork

    other_settings = settings.model_copy(
        update={
            "paintpilot_demo_principal_id": f"phase1f-other-{uuid.uuid4().hex}",
            "paintpilot_demo_principal_display_name": "Other Phase 1F Owner",
        }
    )
    with TestClient(create_app(other_settings)) as other_owner:
        hidden_source = _fork(
            other_owner,
            project_id,
            first["id"],
            expected_current=fourth,
            key=uuid.uuid4(),
        )
        assert hidden_source.status_code == 404

    def concurrent_fork() -> tuple[int, dict]:
        with TestClient(create_app(settings)) as concurrent_client:
            response = _fork(
                concurrent_client,
                project_id,
                second["id"],
                expected_current=fourth,
                key=uuid.uuid4(),
            )
            return response.status_code, response.json()

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda _: concurrent_fork(), range(2)))
    assert sorted(status for status, _ in outcomes) == [201, 409]
    winner = next(payload for status, payload in outcomes if status == 201)
    loser = next(payload for status, payload in outcomes if status == 409)
    assert winner["version"] == 5
    assert winner["based_on_region_set_id"] == second["id"]
    assert winner["supersedes_region_set_id"] == fourth["id"]
    assert loser["error_code"] == "REGION_SET_STALE_VERSION"

    with TestClient(create_app(settings)) as client:
        history = client.get(f"/api/v1/paint-projects/{project_id}/region-sets").json()["items"]
        versions = [item["version"] for item in history]
        assert versions == [5, 4, 3, 2, 1]
        assert len(versions) == len(set(versions))
        historical_submit = _submit(
            client,
            project_id,
            first["id"],
            uuid.uuid4(),
        )
        assert historical_submit.status_code == 409
        submitted_winner = _submit(
            client,
            project_id,
            winner["id"],
            uuid.uuid4(),
        )
        assert submitted_winner.status_code == 201
        exact_submitted = submitted_winner.json()
        exact_review = _review(
            client,
            project_id,
            exact_submitted["id"],
            verdict="approved",
            reason=None,
            key=uuid.uuid4(),
        )
        assert exact_review.status_code == 201
        assert exact_review.json()["region_set_id"] == exact_submitted["id"]
        with psycopg.connect(**_connection_kwargs(database_url)) as connection:
            persisted_target = connection.execute(
                "SELECT region_set_id FROM region_set_reviews WHERE id = %s",
                (exact_review.json()["id"],),
            ).fetchone()
            assert persisted_target == (uuid.UUID(exact_submitted["id"]),)


def test_submit_review_and_image_mutation_races_are_serialized_safely(
    region_set_integration_settings: Settings,
) -> None:
    settings = region_set_integration_settings

    def prepare_draft(title: str) -> tuple[str, dict]:
        with TestClient(create_app(settings)) as client:
            project_id = _create_project(client, title)["id"]
            _ready_image_set(client, project_id)
            saved = _save(
                client,
                project_id,
                base=None,
                regions=_regions(),
                key=uuid.uuid4(),
            )
            assert saved.status_code == 201, saved.text
            return project_id, saved.json()

    submit_project_id, submit_draft = prepare_draft("Submit and image race")

    def racing_submit() -> tuple[int, dict]:
        with TestClient(create_app(settings)) as client:
            response = _submit(
                client,
                submit_project_id,
                submit_draft["id"],
                uuid.uuid4(),
            )
            return response.status_code, response.json()

    def racing_submit_image() -> tuple[int, dict]:
        with TestClient(create_app(settings)) as client:
            response = _upload(
                client,
                submit_project_id,
                role="reference_detail",
                color="#255080",
            )
            return response.status_code, response.json()

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        submit_future = pool.submit(racing_submit)
        image_future = pool.submit(racing_submit_image)
        submit_outcome = submit_future.result()
        image_outcome = image_future.result()
    assert image_outcome[0] == 201
    assert submit_outcome[0] in (201, 409)
    if submit_outcome[0] == 409:
        assert submit_outcome[1]["error_code"] == "REGION_SET_STALE"
    else:
        with TestClient(create_app(settings)) as client:
            detail = client.get(
                f"/api/v1/paint-projects/{submit_project_id}/region-sets/{submit_outcome[1]['id']}"
            )
            assert detail.status_code == 200
            assert detail.json()["stale"] is True

    review_project_id, review_draft = prepare_draft("Review and image race")
    with TestClient(create_app(settings)) as client:
        submitted_response = _submit(
            client,
            review_project_id,
            review_draft["id"],
            uuid.uuid4(),
        )
        assert submitted_response.status_code == 201
        review_submitted = submitted_response.json()

    def racing_review() -> tuple[int, dict]:
        with TestClient(create_app(settings)) as client:
            response = _review(
                client,
                review_project_id,
                review_submitted["id"],
                verdict="approved",
                reason=None,
                key=uuid.uuid4(),
            )
            return response.status_code, response.json()

    def racing_review_image() -> tuple[int, dict]:
        with TestClient(create_app(settings)) as client:
            response = _upload(
                client,
                review_project_id,
                role="reference_detail",
                color="#702050",
            )
            return response.status_code, response.json()

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        review_future = pool.submit(racing_review)
        image_future = pool.submit(racing_review_image)
        review_outcome = review_future.result()
        image_outcome = image_future.result()
    assert image_outcome[0] == 201
    assert review_outcome[0] in (201, 409)
    if review_outcome[0] == 409:
        assert review_outcome[1]["error_code"] == "REGION_SET_STALE"
    else:
        with TestClient(create_app(settings)) as client:
            reviewed_detail = client.get(
                f"/api/v1/paint-projects/{review_project_id}/region-sets/{review_submitted['id']}"
            )
            assert reviewed_detail.status_code == 200
            assert reviewed_detail.json()["stale"] is True
            assert reviewed_detail.json()["effective_lifecycle"] == "approved"

    decision_project_id, decision_draft = prepare_draft("Concurrent reviewers")
    with TestClient(create_app(settings)) as client:
        decision_submit = _submit(
            client,
            decision_project_id,
            decision_draft["id"],
            uuid.uuid4(),
        )
        assert decision_submit.status_code == 201
        decision_submitted = decision_submit.json()

    def racing_decision(verdict: str) -> tuple[int, dict]:
        with TestClient(create_app(settings)) as client:
            response = _review(
                client,
                decision_project_id,
                decision_submitted["id"],
                verdict=verdict,
                reason=(
                    "The exact submitted edge requires revision."
                    if verdict == "changes_requested"
                    else None
                ),
                key=uuid.uuid4(),
            )
            return response.status_code, response.json()

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        decisions = list(pool.map(racing_decision, ("approved", "changes_requested")))
    assert sorted(status for status, _ in decisions) == [201, 409]
    assert next(payload for status, payload in decisions if status == 409)["error_code"] == (
        "REGION_SET_LIFECYCLE_CONFLICT"
    )
    with TestClient(create_app(settings)) as client:
        history = client.get(
            f"/api/v1/paint-projects/{decision_project_id}"
            f"/region-sets/{decision_submitted['id']}/reviews"
        )
        assert history.status_code == 200
        assert len(history.json()["items"]) == 1
