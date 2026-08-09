"""Real PostgreSQL, private storage, and API integration for Phase 1E-2 ImageSets."""

import concurrent.futures
import hashlib
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
from creativedeploy_api.storage.images import LocalFilesystemImageStorageAdapter

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
SCHEMA_PREFIX = "phase1e2_api_test_"
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


def _run_alembic(database_url: URL, *arguments: str) -> None:
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
        f"Alembic {' '.join(arguments)} failed for isolated schema.\n"
        f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
    )


def _run_alembic_expect_failure(
    database_url: URL,
    *arguments: str,
) -> subprocess.CompletedProcess[str]:
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
    assert completed.returncode != 0
    return completed


@pytest.fixture
def image_set_integration_settings(tmp_path: Path) -> Iterator[Settings]:
    development = Settings()
    base_url = make_url(development.database_url.get_secret_value())
    schema_name = f"{SCHEMA_PREFIX}{uuid.uuid4().hex}"
    ownership_token = uuid.uuid4().hex
    created = False
    with psycopg.connect(**_connection_kwargs(base_url), autocommit=True) as connection:
        try:
            connection.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema_name)))
        except psycopg.errors.DuplicateSchema:
            pytest.fail("Random isolated schema already existed; cleanup was refused.")
        created = True
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
        paintpilot_demo_principal_id=f"phase1e2-owner-{uuid.uuid4().hex}",
        paintpilot_demo_principal_display_name="Phase 1E-2 Integration Owner",
        image_storage_root=tmp_path / "private-images",
        _env_file=None,
    )
    try:
        yield settings
    finally:
        if created:
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


def _image_bytes(image_format: str, color: str) -> bytes:
    output = io.BytesIO()
    image = Image.new("RGB", (768, 768), color)
    save_options = {"quality": 90} if image_format == "JPEG" else {}
    image.save(output, format=image_format, **save_options)
    return output.getvalue()


def _create_project(client: TestClient, title: str = "Phase 1E-2 synthetic set") -> dict:
    response = client.post(
        "/api/v1/paint-projects",
        headers={"Idempotency-Key": str(uuid.uuid4())},
        json={"title": title, "description": "Program-generated images only."},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _upload(
    client: TestClient,
    project_id: str,
    *,
    role: str,
    content: bytes,
    filename: str,
    content_type: str,
    idempotency_key: uuid.UUID | None = None,
) -> object:
    return client.post(
        f"/api/v1/paint-projects/{project_id}/images",
        headers={"Idempotency-Key": str(idempotency_key or uuid.uuid4())},
        data={
            "role": role,
            "source_type": "user_provided",
            "intended_usage": "private_project",
            "rights_attestation_confirmed": "true",
            "rights_attestation_version": "1",
        },
        files={"file": (filename, content, content_type)},
    )


def _review(
    client: TestClient,
    project_id: str,
    *,
    verdict: str,
    reason: str | None,
    idempotency_key: uuid.UUID,
) -> object:
    payload = {"verdict": verdict, "reason": reason}
    return client.post(
        f"/api/v1/paint-projects/{project_id}/image-set/readiness-reviews",
        headers={"Idempotency-Key": str(idempotency_key)},
        json=payload,
    )


def _set_project_status_for_contract_test(
    settings: Settings,
    project_id: str,
    status: str,
) -> None:
    """Prepare an isolated negative-contract state without claiming a user transition."""
    database_url = make_url(settings.database_url.get_secret_value())
    with psycopg.connect(**_connection_kwargs(database_url)) as connection:
        updated = connection.execute(
            """
            UPDATE paint_projects
            SET status = %s, updated_at = now()
            WHERE id = %s
            RETURNING id
            """,
            (status, project_id),
        ).fetchone()
        assert updated == (uuid.UUID(project_id),)


def _mutation_snapshot(settings: Settings, project_id: str) -> dict[str, object]:
    """Capture every governed database and private-file side effect for one Project."""
    database_url = make_url(settings.database_url.get_secret_value())
    with psycopg.connect(**_connection_kwargs(database_url)) as connection:
        project = connection.execute(
            """
            SELECT status, current_image_asset_id, updated_at
            FROM paint_projects
            WHERE id = %s
            """,
            (project_id,),
        ).fetchone()
        assets = connection.execute(
            """
            SELECT id, role, version, supersedes_image_asset_id, is_current,
                   lifecycle_status, storage_key, sha256
            FROM image_assets
            WHERE paint_project_id = %s
            ORDER BY role, version, id
            """,
            (project_id,),
        ).fetchall()
        events = connection.execute(
            """
            SELECT id, from_state, to_state, event, reason, event_metadata
            FROM state_transition_events
            WHERE project_id = %s
            ORDER BY created_at, id
            """,
            (project_id,),
        ).fetchall()
        commands = connection.execute(
            """
            SELECT id, command_type, idempotency_key, execution_status,
                   resource_type, resource_id, http_status, response_snapshot
            FROM command_idempotency_records
            WHERE resource_id = %s
               OR scope_key LIKE %s
            ORDER BY created_at, id
            """,
            (project_id, f"%:project:{project_id}:%"),
        ).fetchall()
        reviews = connection.execute(
            """
            SELECT id, version, verdict, reason, image_set_fingerprint,
                   primary_front_image_asset_id, reference_back_image_asset_id,
                   reference_angle_image_asset_id, reference_detail_image_asset_id
            FROM image_set_readiness_reviews
            WHERE paint_project_id = %s
            ORDER BY version, id
            """,
            (project_id,),
        ).fetchall()

    storage_root = Path(settings.image_storage_root)
    objects_root = storage_root / "objects"
    staging_root = storage_root / "staging"
    formal_objects = tuple(
        (
            path.relative_to(storage_root).as_posix(),
            path.stat().st_size,
            hashlib.sha256(path.read_bytes()).hexdigest(),
        )
        for path in sorted(objects_root.glob("*/*"))
        if path.is_file()
    )
    staging_objects = tuple(
        path.relative_to(storage_root).as_posix()
        for path in sorted(staging_root.glob("*"))
        if path.is_file()
    )
    return {
        "project": project,
        "assets": assets,
        "events": events,
        "commands": commands,
        "reviews": reviews,
        "formal_objects": formal_objects,
        "staging_objects": staging_objects,
    }


READINESS_INSERT = """
    INSERT INTO image_set_readiness_reviews (
        id, owner_principal_id, paint_project_id, version, verdict, reason,
        primary_front_image_asset_id, primary_front_role,
        reference_back_image_asset_id, reference_back_role,
        reference_angle_image_asset_id, reference_angle_role,
        reference_detail_image_asset_id, reference_detail_role,
        image_set_fingerprint, actor_type, actor_id,
        actor_display_name_snapshot, created_at
    )
    VALUES (
        %(id)s, %(owner)s, %(project_id)s, %(version)s, %(verdict)s, %(reason)s,
        %(front_id)s, %(front_role)s, %(back_id)s, %(back_role)s,
        %(angle_id)s, %(angle_role)s, NULL, NULL,
        %(fingerprint)s, 'user', %(owner)s, 'Database Constraint Owner', now()
    )
"""


def _expect_database_rejection(
    connection: psycopg.Connection,
    parameters: dict[str, object],
    *,
    sqlstate: str,
    constraint_name: str,
) -> None:
    try:
        with connection.transaction():
            connection.execute(READINESS_INSERT, parameters)
    except psycopg.Error as error:
        assert error.sqlstate == sqlstate
        assert error.diag.constraint_name == constraint_name
    else:
        pytest.fail(f"Database accepted invalid readiness row for {constraint_name}.")
    with connection.transaction():
        assert connection.execute("SELECT 1").fetchone() == (1,)


def _complete_required_set(
    client: TestClient,
    project_id: str,
) -> tuple[dict, dict, dict, bytes]:
    front_bytes = _image_bytes("JPEG", "#cf642f")
    front = _upload(
        client,
        project_id,
        role="primary_front",
        content=front_bytes,
        filename="front.jpg",
        content_type="image/jpeg",
    )
    back = _upload(
        client,
        project_id,
        role="reference_back",
        content=_image_bytes("PNG", "#315f76"),
        filename="back.png",
        content_type="image/png",
    )
    angle = _upload(
        client,
        project_id,
        role="reference_angle",
        content=_image_bytes("WEBP", "#7c5b92"),
        filename="angle.webp",
        content_type="image/webp",
    )
    assert front.status_code == back.status_code == angle.status_code == 201
    return front.json(), back.json(), angle.json(), front_bytes


def test_phase_1e_1_primary_asset_is_mapped_in_place_and_remains_readable(
    tmp_path: Path,
) -> None:
    development = Settings()
    base_url = make_url(development.database_url.get_secret_value())
    schema_name = f"{SCHEMA_PREFIX}{uuid.uuid4().hex}"
    ownership_token = uuid.uuid4().hex
    owner_id = f"phase1e1-owner-{uuid.uuid4().hex}"
    project_id = uuid.uuid4()
    image_id = uuid.uuid4()
    storage_key = f"objects/ab/{uuid.uuid4().hex}.png"
    image_bytes = _image_bytes("PNG", "#ad5f31")
    image_sha256 = hashlib.sha256(image_bytes).hexdigest()
    created = False

    with psycopg.connect(**_connection_kwargs(base_url), autocommit=True) as connection:
        try:
            connection.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema_name)))
        except psycopg.errors.DuplicateSchema:
            pytest.fail("Random isolated schema already existed; cleanup was refused.")
        created = True
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
    storage_root = tmp_path / "phase1e1-private-images"
    object_path = storage_root / storage_key
    object_path.parent.mkdir(parents=True)
    object_path.write_bytes(image_bytes)
    try:
        _run_alembic(schema_url, "upgrade", "5ed9906e7d33")
        with psycopg.connect(**_connection_kwargs(schema_url)) as connection:
            connection.execute(
                """
                INSERT INTO paint_projects (
                    id, owner_principal_id, title, description, status
                )
                VALUES (%s, %s, %s, %s, 'IMAGE_UPLOADED')
                """,
                (
                    project_id,
                    owner_id,
                    "Sealed Phase 1E-1 project",
                    "Legacy primary image compatibility fixture.",
                ),
            )
            connection.execute(
                """
                INSERT INTO image_assets (
                    id, paint_project_id, owner_principal_id, role, version,
                    supersedes_image_asset_id, is_current, lifecycle_status,
                    storage_provider, storage_key, original_filename,
                    declared_content_type, detected_format, byte_size, width,
                    height, pixel_count, color_mode, has_alpha, exif_orientation,
                    sha256, upload_validation_result, upload_validation_details,
                    source_type, rights_attestation_status,
                    rights_attestation_version, intended_usage,
                    rights_attested_by_principal_id, rights_attested_at,
                    created_by_actor_type, created_by_actor_id,
                    created_by_actor_display_name_snapshot
                )
                VALUES (
                    %s, %s, %s, 'primary_mvp_input', 1,
                    NULL, TRUE, 'current',
                    'local_filesystem', %s, 'sealed-primary.png',
                    'image/png', 'png', %s, 768,
                    768, 589824, 'RGB', FALSE, NULL,
                    %s, 'accepted', '{"policy_version":"image_upload_validation.v1"}'::jsonb,
                    'user_provided', 'confirmed',
                    1, '["private_project"]'::jsonb,
                    %s, now(),
                    'user', %s, 'Phase 1E-1 Owner'
                )
                """,
                (
                    image_id,
                    project_id,
                    owner_id,
                    storage_key,
                    len(image_bytes),
                    image_sha256,
                    owner_id,
                    owner_id,
                ),
            )
            connection.execute(
                "UPDATE paint_projects SET current_image_asset_id = %s WHERE id = %s",
                (image_id, project_id),
            )
            before = connection.execute(
                """
                SELECT id, paint_project_id, owner_principal_id, role, version,
                       supersedes_image_asset_id, is_current, lifecycle_status,
                       storage_key, sha256
                FROM image_assets
                WHERE id = %s
                """,
                (image_id,),
            ).fetchone()
            pointer_before = connection.execute(
                "SELECT current_image_asset_id FROM paint_projects WHERE id = %s",
                (project_id,),
            ).fetchone()
            connection.commit()

        assert before is not None
        assert before[3] == "primary_mvp_input"
        assert pointer_before == (image_id,)
        _run_alembic(schema_url, "upgrade", "head")

        with psycopg.connect(**_connection_kwargs(schema_url)) as connection:
            after = connection.execute(
                """
                SELECT id, paint_project_id, owner_principal_id, role, version,
                       supersedes_image_asset_id, is_current, lifecycle_status,
                       storage_key, sha256
                FROM image_assets
                WHERE id = %s
                """,
                (image_id,),
            ).fetchone()
            pointer_after = connection.execute(
                "SELECT current_image_asset_id FROM paint_projects WHERE id = %s",
                (project_id,),
            ).fetchone()

        assert after is not None
        assert after[:3] == before[:3]
        assert after[3] == "primary_front"
        assert after[4:] == before[4:]
        assert pointer_after == pointer_before

        settings = Settings(
            app_env="test",
            database_url=schema_url.render_as_string(hide_password=False),
            paintpilot_demo_principal_id=owner_id,
            paintpilot_demo_principal_display_name="Phase 1E-1 Owner",
            image_storage_root=storage_root,
            _env_file=None,
        )
        with TestClient(create_app(settings)) as client:
            legacy_list = client.get(f"/api/v1/paint-projects/{project_id}/images")
            assert legacy_list.status_code == 200
            listed_assets = [
                (item["id"], item["role"], item["version"]) for item in legacy_list.json()["items"]
            ]
            assert listed_assets == [(str(image_id), "primary_front", 1)]
            image_set = client.get(f"/api/v1/paint-projects/{project_id}/image-set")
            assert image_set.status_code == 200
            front = image_set.json()["roles"][0]
            assert front["current"]["id"] == str(image_id)
            assert [item["version"] for item in front["history"]] == [1]
            assert front["object_available"] is True
            content = client.get(front["current"]["content_url"])
            assert content.status_code == 200
            assert content.content == image_bytes
    finally:
        if created:
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


def test_multi_role_ready_stale_duplicate_not_ready_history_restart_and_owner_isolation(
    image_set_integration_settings: Settings,
) -> None:
    settings = image_set_integration_settings
    ready_key = uuid.uuid4()
    with TestClient(create_app(settings)) as client:
        project = _create_project(client)
        project_id = str(project["id"])
        front, back, angle, front_bytes = _complete_required_set(client, project_id)

        image_set = client.get(f"/api/v1/paint-projects/{project_id}/image-set")
        assert image_set.status_code == 200
        initial = image_set.json()
        assert initial["status"] == "incomplete"
        assert initial["checklist"] == {
            "required_roles_present": True,
            "deterministic_validation_accepted": True,
            "rights_complete": True,
            "content_distinct": True,
            "objects_available": True,
            "snapshot_current": False,
            "can_mark_ready": True,
            "blockers": [],
        }
        assert [slot["role"] for slot in initial["roles"]] == [
            "primary_front",
            "reference_back",
            "reference_angle",
            "reference_detail",
        ]
        assert initial["roles"][3]["required"] is False
        assert initial["roles"][3]["missing"] is True

        ready = _review(
            client,
            project_id,
            verdict="ready",
            reason=None,
            idempotency_key=ready_key,
        )
        assert ready.status_code == 201, ready.text
        first_review = ready.json()
        assert first_review["version"] == 1
        assert first_review["primary_front_image_asset_id"] == front["id"]
        assert first_review["reference_back_image_asset_id"] == back["id"]
        assert first_review["reference_angle_image_asset_id"] == angle["id"]
        assert first_review["reference_detail_image_asset_id"] is None

        replay = _review(
            client,
            project_id,
            verdict="ready",
            reason=None,
            idempotency_key=ready_key,
        )
        assert replay.status_code == 201
        assert replay.json() == first_review
        conflict = _review(
            client,
            project_id,
            verdict="ready",
            reason="Changed payload.",
            idempotency_key=ready_key,
        )
        assert conflict.status_code == 409
        assert conflict.json()["error_code"] == "IDEMPOTENCY_KEY_REUSED"

        current = client.get(f"/api/v1/paint-projects/{project_id}/image-set").json()
        assert current["status"] == "ready"
        assert current["checklist"]["snapshot_current"] is True

    with TestClient(create_app(settings)) as restarted:
        persisted = restarted.get(f"/api/v1/paint-projects/{project_id}/image-set")
        assert persisted.status_code == 200
        assert persisted.json()["status"] == "ready"

        replacement = _upload(
            restarted,
            project_id,
            role="reference_angle",
            content=_image_bytes("WEBP", "#275f43"),
            filename="angle-v2.webp",
            content_type="image/webp",
        )
        assert replacement.status_code == 201, replacement.text
        stale = restarted.get(f"/api/v1/paint-projects/{project_id}/image-set").json()
        assert stale["status"] == "stale"
        assert stale["stale_reasons"] == ["reference_angle_changed"]
        angle_slot = next(slot for slot in stale["roles"] if slot["role"] == "reference_angle")
        assert [item["version"] for item in angle_slot["history"]] == [2, 1]
        assert restarted.get(angle["content_url"]).status_code == 200

        second_ready = _review(
            restarted,
            project_id,
            verdict="ready",
            reason=None,
            idempotency_key=uuid.uuid4(),
        )
        assert second_ready.status_code == 201
        assert second_ready.json()["version"] == 2
        assert (
            restarted.get(f"/api/v1/paint-projects/{project_id}/image-set").json()["status"]
            == "ready"
        )

        duplicate = _upload(
            restarted,
            project_id,
            role="reference_back",
            content=front_bytes,
            filename="duplicate-front-as-back.jpg",
            content_type="image/jpeg",
        )
        assert duplicate.status_code == 201
        blocked = restarted.get(f"/api/v1/paint-projects/{project_id}/image-set").json()
        assert blocked["status"] == "stale"
        assert blocked["checklist"]["content_distinct"] is False
        assert blocked["checklist"]["can_mark_ready"] is False
        assert "duplicate_or_missing_required_content" in blocked["checklist"]["blockers"]

        rejected_ready = _review(
            restarted,
            project_id,
            verdict="ready",
            reason=None,
            idempotency_key=uuid.uuid4(),
        )
        assert rejected_ready.status_code == 409
        assert rejected_ready.json()["error_code"] == "IMAGE_SET_READY_PREREQUISITES_NOT_MET"
        not_ready = _review(
            restarted,
            project_id,
            verdict="not_ready",
            reason="Reference back duplicates the primary image.",
            idempotency_key=uuid.uuid4(),
        )
        assert not_ready.status_code == 201
        assert not_ready.json()["version"] == 3
        history = restarted.get(f"/api/v1/paint-projects/{project_id}/image-set/readiness-reviews")
        assert history.status_code == 200
        assert [item["version"] for item in history.json()["items"]] == [3, 2, 1]
        assert (
            restarted.get(f"/api/v1/paint-projects/{project_id}/image-set").json()["status"]
            == "not_ready"
        )

        unknown = restarted.post(
            f"/api/v1/paint-projects/{project_id}/image-set/readiness-reviews",
            headers={"Idempotency-Key": str(uuid.uuid4())},
            json={"verdict": "not_ready", "reason": "Reason.", "snapshot": {}},
        )
        assert unknown.status_code == 422
        missing_reason = restarted.post(
            f"/api/v1/paint-projects/{project_id}/image-set/readiness-reviews",
            headers={"Idempotency-Key": str(uuid.uuid4())},
            json={"verdict": "not_ready", "reason": None},
        )
        assert missing_reason.status_code == 422

    other_settings = settings.model_copy(
        update={
            "paintpilot_demo_principal_id": f"phase1e2-other-{uuid.uuid4().hex}",
            "paintpilot_demo_principal_display_name": "Other Integration Owner",
        }
    )
    with TestClient(create_app(other_settings)) as other:
        for path in (
            f"/api/v1/paint-projects/{project_id}/image-set",
            f"/api/v1/paint-projects/{project_id}/image-set/readiness-reviews",
        ):
            assert other.get(path).status_code == 404
        assert (
            _review(
                other,
                project_id,
                verdict="not_ready",
                reason="Should not disclose the project.",
                idempotency_key=uuid.uuid4(),
            ).status_code
            == 404
        )


def test_primary_workflow_gate_allows_only_sealed_first_upload_and_replacement_paths(
    image_set_integration_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = image_set_integration_settings
    first_bytes = _image_bytes("JPEG", "#cf642f")
    review_replacement_bytes = _image_bytes("JPEG", "#245f77")
    failed_replacement_bytes = _image_bytes("JPEG", "#7a4e91")
    with TestClient(create_app(settings)) as client:
        project_id = str(_create_project(client, "Primary workflow-gate matrix")["id"])

        first = _upload(
            client,
            project_id,
            role="primary_front",
            content=first_bytes,
            filename="primary-v1.jpg",
            content_type="image/jpeg",
        )
        assert first.status_code == 201, first.text
        first_asset = first.json()
        assert first_asset["version"] == 1
        assert client.get(f"/api/v1/paint-projects/{project_id}").json()["status"] == (
            "IMAGE_UPLOADED"
        )

        before_uploaded_rejection = _mutation_snapshot(settings, project_id)

        async def reject_unexpected_staging(
            _storage: LocalFilesystemImageStorageAdapter,
            _upload_file: object,
            *,
            max_bytes: int,
        ) -> object:
            del max_bytes
            pytest.fail("Workflow-rejected mutation reached private staging.")

        with monkeypatch.context() as patch:
            patch.setattr(
                LocalFilesystemImageStorageAdapter,
                "stage_upload",
                reject_unexpected_staging,
            )
            rejected_uploaded = _upload(
                client,
                project_id,
                role="primary_front",
                content=review_replacement_bytes,
                filename="primary-blocked-uploaded.jpg",
                content_type="image/jpeg",
            )
        assert rejected_uploaded.status_code == 409
        assert rejected_uploaded.json() == {
            **rejected_uploaded.json(),
            "error_code": "INVALID_STATE_TRANSITION",
            "category": "INVALID_STATE_TRANSITION",
            "message": "The project state does not allow this image operation.",
            "retryable": False,
            "current_state": "IMAGE_UPLOADED",
            "allowed_actions": ["view_project", "abandon_project"],
            "safe_details": {"operation": "replacement"},
        }
        assert _mutation_snapshot(settings, project_id) == before_uploaded_rejection

        _set_project_status_for_contract_test(settings, project_id, "DRAFT")
        before_draft_rejection = _mutation_snapshot(settings, project_id)
        rejected_draft_replacement = _upload(
            client,
            project_id,
            role="primary_front",
            content=review_replacement_bytes,
            filename="primary-blocked-draft.jpg",
            content_type="image/jpeg",
        )
        assert rejected_draft_replacement.status_code == 409
        assert rejected_draft_replacement.json()["current_state"] == "DRAFT"
        assert _mutation_snapshot(settings, project_id) == before_draft_rejection

        _set_project_status_for_contract_test(
            settings,
            project_id,
            "IMAGE_REVIEW_REQUIRED",
        )
        review_replacement = _upload(
            client,
            project_id,
            role="primary_front",
            content=review_replacement_bytes,
            filename="primary-v2-review.jpg",
            content_type="image/jpeg",
        )
        assert review_replacement.status_code == 201, review_replacement.text
        second_asset = review_replacement.json()
        assert second_asset["version"] == 2
        assert second_asset["supersedes_image_asset_id"] == first_asset["id"]
        assert client.get(first_asset["content_url"]).content == first_bytes
        assert client.get(f"/api/v1/paint-projects/{project_id}").json()["status"] == (
            "IMAGE_UPLOADED"
        )

        _set_project_status_for_contract_test(
            settings,
            project_id,
            "IMAGE_VALIDATION_FAILED",
        )
        failed_replacement = _upload(
            client,
            project_id,
            role="primary_front",
            content=failed_replacement_bytes,
            filename="primary-v3-failed.jpg",
            content_type="image/jpeg",
        )
        assert failed_replacement.status_code == 201, failed_replacement.text
        third_asset = failed_replacement.json()
        assert third_asset["version"] == 3
        assert third_asset["supersedes_image_asset_id"] == second_asset["id"]
        assert client.get(second_asset["content_url"]).content == review_replacement_bytes
        assert client.get(first_asset["content_url"]).content == first_bytes

        _set_project_status_for_contract_test(settings, project_id, "IMAGE_VALIDATED")
        before_validated_rejection = _mutation_snapshot(settings, project_id)
        rejected_validated = _upload(
            client,
            project_id,
            role="primary_front",
            content=_image_bytes("JPEG", "#44614d"),
            filename="primary-blocked-validated.jpg",
            content_type="image/jpeg",
        )
        assert rejected_validated.status_code == 409
        assert rejected_validated.json()["current_state"] == "IMAGE_VALIDATED"
        assert _mutation_snapshot(settings, project_id) == before_validated_rejection
        assert (
            client.get(f"/api/v1/paint-projects/{project_id}").json()["current_image_asset_id"]
            == third_asset["id"]
        )


def test_reference_role_first_upload_and_replacement_matrix_preserves_workflow_state(
    image_set_integration_settings: Settings,
) -> None:
    settings = image_set_integration_settings
    roles = ("reference_back", "reference_angle", "reference_detail")
    allowed_states = (
        "DRAFT",
        "IMAGE_UPLOADED",
        "IMAGE_REVIEW_REQUIRED",
        "IMAGE_VALIDATION_FAILED",
    )
    with TestClient(create_app(settings)) as client:
        for role_index, role in enumerate(roles):
            for state_index, state in enumerate(allowed_states):
                project_id = str(
                    _create_project(
                        client,
                        f"{role} mutation matrix in {state}",
                    )["id"]
                )
                if state != "DRAFT":
                    _set_project_status_for_contract_test(settings, project_id, state)
                first_bytes = _image_bytes(
                    "PNG",
                    f"#{32 + role_index * 40:02x}{64 + state_index * 24:02x}72",
                )
                replacement_bytes = _image_bytes(
                    "PNG",
                    f"#72{48 + role_index * 40:02x}{48 + state_index * 24:02x}",
                )
                first = _upload(
                    client,
                    project_id,
                    role=role,
                    content=first_bytes,
                    filename=f"{role}-v1.png",
                    content_type="image/png",
                )
                assert first.status_code == 201, first.text
                assert client.get(f"/api/v1/paint-projects/{project_id}").json()["status"] == state

                replacement = _upload(
                    client,
                    project_id,
                    role=role,
                    content=replacement_bytes,
                    filename=f"{role}-v2.png",
                    content_type="image/png",
                )
                assert replacement.status_code == 201, replacement.text
                assert replacement.json()["version"] == 2
                assert replacement.json()["supersedes_image_asset_id"] == first.json()["id"]
                assert client.get(first.json()["content_url"]).content == first_bytes
                assert client.get(f"/api/v1/paint-projects/{project_id}").json()["status"] == state


def test_image_validated_rejects_first_upload_and_replacement_for_every_role(
    image_set_integration_settings: Settings,
) -> None:
    settings = image_set_integration_settings
    roles = (
        "primary_front",
        "reference_back",
        "reference_angle",
        "reference_detail",
    )
    with TestClient(create_app(settings)) as client:
        empty_project_id = str(
            _create_project(client, "Validated first-upload rejection matrix")["id"]
        )
        _set_project_status_for_contract_test(
            settings,
            empty_project_id,
            "IMAGE_VALIDATED",
        )
        for index, role in enumerate(roles):
            before = _mutation_snapshot(settings, empty_project_id)
            rejected = _upload(
                client,
                empty_project_id,
                role=role,
                content=_image_bytes("PNG", f"#{40 + index * 30:02x}5060"),
                filename=f"{role}-blocked-first.png",
                content_type="image/png",
            )
            assert rejected.status_code == 409
            assert rejected.json()["safe_details"] == {"operation": "first_upload"}
            assert _mutation_snapshot(settings, empty_project_id) == before

        current_project_id = str(
            _create_project(client, "Validated replacement rejection matrix")["id"]
        )
        current_assets: dict[str, dict] = {}
        for index, role in enumerate(roles[1:]):
            created = _upload(
                client,
                current_project_id,
                role=role,
                content=_image_bytes("PNG", f"#{50 + index * 40:02x}6575"),
                filename=f"{role}-current.png",
                content_type="image/png",
            )
            assert created.status_code == 201, created.text
            current_assets[role] = created.json()
        primary = _upload(
            client,
            current_project_id,
            role="primary_front",
            content=_image_bytes("JPEG", "#a15131"),
            filename="primary-current.jpg",
            content_type="image/jpeg",
        )
        assert primary.status_code == 201, primary.text
        current_assets["primary_front"] = primary.json()
        _set_project_status_for_contract_test(
            settings,
            current_project_id,
            "IMAGE_VALIDATED",
        )

        for index, role in enumerate(roles):
            before = _mutation_snapshot(settings, current_project_id)
            rejected = _upload(
                client,
                current_project_id,
                role=role,
                content=_image_bytes("PNG", f"#6070{50 + index * 30:02x}"),
                filename=f"{role}-blocked-replacement.png",
                content_type="image/png",
            )
            assert rejected.status_code == 409
            assert rejected.json()["safe_details"] == {"operation": "replacement"}
            assert _mutation_snapshot(settings, current_project_id) == before
            assert client.get(current_assets[role]["content_url"]).status_code == 200


def test_primary_replacement_stales_ready_review_and_rejections_preserve_current_ready_facts(
    image_set_integration_settings: Settings,
) -> None:
    settings = image_set_integration_settings
    with TestClient(create_app(settings)) as client:
        project_id = str(_create_project(client, "Primary readiness regression")["id"])
        front, _back, _angle, front_bytes = _complete_required_set(client, project_id)
        detail = _upload(
            client,
            project_id,
            role="reference_detail",
            content=_image_bytes("PNG", "#956443"),
            filename="detail.png",
            content_type="image/png",
        )
        assert detail.status_code == 201, detail.text
        first_ready = _review(
            client,
            project_id,
            verdict="ready",
            reason=None,
            idempotency_key=uuid.uuid4(),
        )
        assert first_ready.status_code == 201, first_ready.text
        initial_ready = client.get(f"/api/v1/paint-projects/{project_id}/image-set").json()
        assert initial_ready["status"] == "ready"

        _set_project_status_for_contract_test(
            settings,
            project_id,
            "IMAGE_REVIEW_REQUIRED",
        )
        replacement = _upload(
            client,
            project_id,
            role="primary_front",
            content=_image_bytes("JPEG", "#365d78"),
            filename="primary-reviewed-replacement.jpg",
            content_type="image/jpeg",
        )
        assert replacement.status_code == 201, replacement.text
        assert replacement.json()["supersedes_image_asset_id"] == front["id"]
        assert client.get(front["content_url"]).content == front_bytes
        stale = client.get(f"/api/v1/paint-projects/{project_id}/image-set").json()
        assert stale["status"] == "stale"
        assert stale["stale_reasons"] == ["primary_front_changed"]
        assert stale["latest_review"]["id"] == first_ready.json()["id"]
        assert stale["image_set_fingerprint"] != initial_ready["image_set_fingerprint"]

        before_uploaded_rejection = _mutation_snapshot(settings, project_id)
        fingerprint_before_rejection = stale["image_set_fingerprint"]
        rejected_uploaded = _upload(
            client,
            project_id,
            role="primary_front",
            content=_image_bytes("JPEG", "#654933"),
            filename="primary-blocked-while-uploaded.jpg",
            content_type="image/jpeg",
        )
        assert rejected_uploaded.status_code == 409
        assert _mutation_snapshot(settings, project_id) == before_uploaded_rejection
        assert (
            client.get(f"/api/v1/paint-projects/{project_id}/image-set").json()[
                "image_set_fingerprint"
            ]
            == fingerprint_before_rejection
        )

        current_ready = _review(
            client,
            project_id,
            verdict="ready",
            reason=None,
            idempotency_key=uuid.uuid4(),
        )
        assert current_ready.status_code == 201
        assert (
            client.get(f"/api/v1/paint-projects/{project_id}/image-set").json()["status"] == "ready"
        )
        _set_project_status_for_contract_test(settings, project_id, "IMAGE_VALIDATED")
        validated_snapshot = _mutation_snapshot(settings, project_id)
        validated_image_set = client.get(f"/api/v1/paint-projects/{project_id}/image-set").json()

        for index, role in enumerate(
            (
                "primary_front",
                "reference_back",
                "reference_angle",
                "reference_detail",
            )
        ):
            rejected = _upload(
                client,
                project_id,
                role=role,
                content=_image_bytes("PNG", f"#7180{50 + index * 30:02x}"),
                filename=f"{role}-validated-ready-blocked.png",
                content_type="image/png",
            )
            assert rejected.status_code == 409
            assert _mutation_snapshot(settings, project_id) == validated_snapshot
            assert (
                client.get(f"/api/v1/paint-projects/{project_id}/image-set").json()
                == validated_image_set
            )


@pytest.mark.parametrize(
    ("blocking_fact", "expected_message"),
    [
        ("readiness_review", "readiness review history would be lost"),
        ("reference_asset", "multi-role image history would be lost"),
    ],
)
def test_phase_1e_2_downgrade_refuses_to_discard_governed_facts(
    image_set_integration_settings: Settings,
    blocking_fact: str,
    expected_message: str,
) -> None:
    settings = image_set_integration_settings
    with TestClient(create_app(settings)) as client:
        project_id = str(_create_project(client, f"Downgrade blocker: {blocking_fact}")["id"])
        if blocking_fact == "readiness_review":
            response = _review(
                client,
                project_id,
                verdict="not_ready",
                reason="Preserve this append-only decision.",
                idempotency_key=uuid.uuid4(),
            )
        else:
            response = _upload(
                client,
                project_id,
                role="reference_back",
                content=_image_bytes("PNG", "#425a7d"),
                filename="preserve-back.png",
                content_type="image/png",
            )
        assert response.status_code == 201

    database_url = make_url(settings.database_url.get_secret_value())
    with psycopg.connect(**_connection_kwargs(database_url)) as connection:
        revision_before_attempt = connection.execute(
            "SELECT version_num FROM alembic_version"
        ).fetchone()
    assert revision_before_attempt is not None
    assert revision_before_attempt[0]

    failed = _run_alembic_expect_failure(
        database_url,
        "downgrade",
        "5ed9906e7d33",
    )
    assert expected_message in failed.stderr

    with psycopg.connect(**_connection_kwargs(database_url)) as connection:
        revision_after_attempt = connection.execute(
            "SELECT version_num FROM alembic_version"
        ).fetchone()
        assert revision_after_attempt == revision_before_attempt
        if blocking_fact == "readiness_review":
            assert connection.execute(
                "SELECT count(*) FROM image_set_readiness_reviews"
            ).fetchone() == (1,)
        else:
            assert connection.execute(
                "SELECT count(*) FROM image_assets WHERE role = 'reference_back'"
            ).fetchone() == (1,)


def test_readiness_database_constraints_enforce_snapshot_roles_and_verdicts(
    image_set_integration_settings: Settings,
) -> None:
    settings = image_set_integration_settings
    with TestClient(create_app(settings)) as client:
        project_id = str(_create_project(client, "Readiness database constraints")["id"])
        front, back, angle, _front_bytes = _complete_required_set(client, project_id)
        ready = _review(
            client,
            project_id,
            verdict="ready",
            reason=None,
            idempotency_key=uuid.uuid4(),
        )
        assert ready.status_code == 201
        fingerprint = ready.json()["image_set_fingerprint"]

    base = {
        "id": uuid.uuid4(),
        "owner": settings.paintpilot_demo_principal_id,
        "project_id": project_id,
        "version": 2,
        "verdict": "not_ready",
        "reason": "Independent database constraint probe.",
        "front_id": front["id"],
        "front_role": "primary_front",
        "back_id": back["id"],
        "back_role": "reference_back",
        "angle_id": angle["id"],
        "angle_role": "reference_angle",
        "fingerprint": fingerprint,
    }
    database_url = make_url(settings.database_url.get_secret_value())
    with psycopg.connect(**_connection_kwargs(database_url)) as connection:
        for updates, sqlstate, constraint_name in (
            (
                {"version": 0},
                "23514",
                "ck_image_set_readiness_reviews_version_positive",
            ),
            (
                {"version": 1},
                "23505",
                "uq_image_set_readiness_reviews_project_version",
            ),
            (
                {"verdict": "unknown"},
                "23514",
                "ck_image_set_readiness_reviews_verdict_allowed",
            ),
            (
                {"reason": None},
                "23514",
                "ck_image_set_readiness_reviews_not_ready_reason_required",
            ),
            (
                {"fingerprint": "A" * 64},
                "23514",
                "ck_image_set_readiness_reviews_fingerprint_format",
            ),
            (
                {"front_id": back["id"]},
                "23503",
                "fk_image_set_readiness_reviews_primary_front_asset",
            ),
            (
                {"verdict": "ready", "reason": None, "angle_id": None, "angle_role": None},
                "23514",
                "ck_image_set_readiness_reviews_ready_required_assets",
            ),
        ):
            candidate = {**base, **updates, "id": uuid.uuid4()}
            _expect_database_rejection(
                connection,
                candidate,
                sqlstate=sqlstate,
                constraint_name=constraint_name,
            )


def test_readiness_project_scoped_idempotency_concurrency_and_append_only_database(
    image_set_integration_settings: Settings,
) -> None:
    settings = image_set_integration_settings
    shared_key = uuid.uuid4()
    with TestClient(create_app(settings)) as client:
        first_project = _create_project(client, "First concurrency project")
        second_project = _create_project(client, "Second concurrency project")
        first_id = str(first_project["id"])
        second_id = str(second_project["id"])

        first_review = _review(
            client,
            first_id,
            verdict="not_ready",
            reason="Required roles are still missing.",
            idempotency_key=shared_key,
        )
        second_review = _review(
            client,
            second_id,
            verdict="not_ready",
            reason="Required roles are still missing.",
            idempotency_key=shared_key,
        )
        assert first_review.status_code == second_review.status_code == 201
        assert first_review.json()["id"] != second_review.json()["id"]

        concurrent_key = uuid.uuid4()

        def submit_same_key() -> tuple[int, str]:
            with TestClient(create_app(settings)) as concurrent_client:
                response = _review(
                    concurrent_client,
                    first_id,
                    verdict="not_ready",
                    reason="Concurrent safe retry.",
                    idempotency_key=concurrent_key,
                )
                return response.status_code, response.json()["id"]

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = list(executor.map(lambda _index: submit_same_key(), range(2)))
        assert {status for status, _review_id in outcomes} == {201}
        assert len({_review_id for _status, _review_id in outcomes}) == 1

        def submit_new_key() -> tuple[int, int]:
            with TestClient(create_app(settings)) as concurrent_client:
                response = _review(
                    concurrent_client,
                    first_id,
                    verdict="not_ready",
                    reason="Independent concurrent review.",
                    idempotency_key=uuid.uuid4(),
                )
                return response.status_code, response.json()["version"]

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            versions = list(executor.map(lambda _index: submit_new_key(), range(2)))
        assert {status for status, _version in versions} == {201}
        assert sorted(version for _status, version in versions) == [3, 4]

        review_id = first_review.json()["id"]
        database_url = make_url(settings.database_url.get_secret_value())
        with psycopg.connect(**_connection_kwargs(database_url)) as connection:
            for statement in (
                "UPDATE image_set_readiness_reviews SET reason = 'changed' WHERE id = %s",
                "DELETE FROM image_set_readiness_reviews WHERE id = %s",
            ):
                try:
                    with connection.transaction():
                        connection.execute(statement, (review_id,))
                except psycopg.Error as error:
                    assert error.sqlstate == "55000"
                else:
                    pytest.fail("Append-only readiness history accepted a mutation.")


def test_upload_and_ready_review_race_never_marks_an_old_snapshot_current(
    image_set_integration_settings: Settings,
) -> None:
    settings = image_set_integration_settings
    with TestClient(create_app(settings)) as client:
        project_id = str(_create_project(client, "Upload review race")["id"])
        _complete_required_set(client, project_id)

    def replace_angle() -> int:
        with TestClient(create_app(settings)) as concurrent_client:
            response = _upload(
                concurrent_client,
                project_id,
                role="reference_angle",
                content=_image_bytes("WEBP", "#166d83"),
                filename="race-angle.webp",
                content_type="image/webp",
            )
            return response.status_code

    def confirm_ready() -> tuple[int, str | None]:
        with TestClient(create_app(settings)) as concurrent_client:
            response = _review(
                concurrent_client,
                project_id,
                verdict="ready",
                reason=None,
                idempotency_key=uuid.uuid4(),
            )
            body = response.json()
            return response.status_code, body.get("image_set_fingerprint")

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        upload_future = executor.submit(replace_angle)
        review_future = executor.submit(confirm_ready)
        upload_status = upload_future.result()
        review_status, reviewed_fingerprint = review_future.result()
    assert upload_status == review_status == 201

    with TestClient(create_app(settings)) as client:
        final = client.get(f"/api/v1/paint-projects/{project_id}/image-set").json()
    if final["status"] == "ready":
        assert final["latest_review"]["image_set_fingerprint"] == final["image_set_fingerprint"]
        assert reviewed_fingerprint == final["image_set_fingerprint"]
    else:
        assert final["status"] == "stale"
        assert final["latest_review"]["image_set_fingerprint"] != final["image_set_fingerprint"]
