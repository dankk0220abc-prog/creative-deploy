"""Seed and verify synthetic Phase 3B relationships for the staging recovery drill."""

from __future__ import annotations

import sys
import uuid
from collections.abc import Sequence
from typing import Any

import psycopg

from creativedeploy_api.core.config import Settings
from creativedeploy_api.tools.staging_backup_restore import (
    EXPECTED_ALEMBIC_REVISION,
    PHASE3B_TABLES,
    _database_connection,
)

PROVIDER_ID = uuid.UUID("3a000000-0000-4000-8000-000000000001")
MODEL_ID = uuid.UUID("3a000000-0000-4000-8000-000000000101")
INVOCATION_ID = uuid.UUID("3b000000-0000-4000-8000-000000000014")
FINAL_ATTEMPT_ID = uuid.UUID("3b000000-0000-4000-8000-000000000015")
PRICING_ID = uuid.UUID("3b000000-0000-4000-8000-000000000201")
PROMPT_ID = uuid.UUID("3b000000-0000-4000-8000-000000000301")
READINESS_REVIEW_ID = uuid.UUID("3c000000-0000-4000-8000-000000000001")
REGION_SET_ID = uuid.UUID("3c000000-0000-4000-8000-000000000002")
REGION_IDS = (
    uuid.UUID("3c000000-0000-4000-8000-000000000003"),
    uuid.UUID("3c000000-0000-4000-8000-000000000004"),
)
REGION_SET_REVIEW_ID = uuid.UUID("3c000000-0000-4000-8000-000000000005")
PLAN_IDS = (
    uuid.UUID("3c000000-0000-4000-8000-000000000100"),
    uuid.UUID("3c000000-0000-4000-8000-000000000101"),
)
INSTRUCTION_IDS = (
    uuid.UUID("3c000000-0000-4000-8000-000000000200"),
    uuid.UUID("3c000000-0000-4000-8000-000000000201"),
    uuid.UUID("3c000000-0000-4000-8000-000000000202"),
    uuid.UUID("3c000000-0000-4000-8000-000000000203"),
)
REVIEW_EVENT_IDS = (
    uuid.UUID("3c000000-0000-4000-8000-000000000300"),
    uuid.UUID("3c000000-0000-4000-8000-000000000301"),
)
IMAGE_SET_FINGERPRINT = "4" * 64
GEOMETRY_FINGERPRINT = "5" * 64
PROMPT_HASH = "8f946b8ae444637aa56b8624118f45b539eb314bf5bb6ed9013e7b89b0561de6"
EXPECTED_COUNTS = {
    "provider_pricing_snapshots": 3,
    "prompt_template_definitions": 1,
    "paint_plans": 2,
    "paint_plan_region_instructions": 4,
    "paint_plan_review_events": 2,
}


def _revision(connection: psycopg.Connection[dict[str, Any]]) -> None:
    row = connection.execute("SELECT version_num FROM alembic_version").fetchone()
    if row is None or row["version_num"] != EXPECTED_ALEMBIC_REVISION:
        raise AssertionError("unexpected Alembic revision")


def _insert_instruction(
    connection: psycopg.Connection[dict[str, Any]],
    *,
    instruction_id: uuid.UUID,
    plan_id: uuid.UUID,
    region_id: uuid.UUID,
    stable_region_key: uuid.UUID,
    label: str,
    sequence: int,
) -> None:
    connection.execute(
        """
        INSERT INTO paint_plan_region_instructions (
            id, paint_plan_id, region_set_id, region_id, stable_region_key,
            region_label_snapshot, region_kind_snapshot, sequence, target_color,
            preparation, base_coat, layer_strategy, edge_treatment,
            lighting_guidance, material_guidance, warnings, confidence_ppm, created_at
        ) VALUES (
            %s, %s, %s, %s, %s, %s, 'paint', %s, 'Synthetic neutral blue',
            'Synthetic surface preparation only', 'Synthetic fixture base coat',
            'Synthetic fixture layer strategy', 'Synthetic fixture edge treatment',
            'Synthetic fixture lighting guidance', 'Synthetic fixture material guidance',
            '[]'::jsonb, 800000, now()
        )
        """,
        (
            instruction_id,
            plan_id,
            REGION_SET_ID,
            region_id,
            stable_region_key,
            label,
            sequence,
        ),
    )


def _insert_plan(
    connection: psycopg.Connection[dict[str, Any]],
    *,
    plan_id: uuid.UUID,
    owner_principal_id: str,
    project_id: uuid.UUID,
    version: int,
    lineage_revision: int,
    revision_kind: str,
    lifecycle: str,
    parent_plan_id: uuid.UUID | None,
    actor_type: str,
    actor_id: str,
    actor_display_name: str,
    content_hash: str,
) -> None:
    connection.execute(
        """
        INSERT INTO paint_plans (
            id, owner_principal_id, paint_project_id, lineage_id, version,
            lineage_revision, revision_kind, lifecycle, parent_plan_id,
            source_readiness_review_id, source_readiness_review_version,
            source_image_set_fingerprint, source_region_set_id,
            source_region_set_version, source_geometry_fingerprint,
            source_invocation_id, source_attempt_id, provider_definition_id,
            provider_key_snapshot, provider_revision_snapshot, model_definition_id,
            model_id_snapshot, model_revision_snapshot, provider_pricing_snapshot_id,
            prompt_template_definition_id, prompt_template_key_snapshot,
            prompt_template_version_snapshot, prompt_content_hash,
            response_schema_version, title, overall_approach, safety_notes,
            instruction_count, content_hash, created_by_actor_type,
            created_by_actor_id, created_by_actor_display_name_snapshot, created_at
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, 1, %s, %s, 1, %s, %s, %s, %s,
            'fixture_local', 1, %s, 'fixture-text-v1', 1, NULL,
            %s, 'paint-plan', 1, %s, 'paint-plan.v1',
            'Synthetic Phase 3B recovery plan',
            'Synthetic offline staging recovery approach.', '[]'::jsonb,
            2, %s, %s, %s, %s, now()
        )
        """,
        (
            plan_id,
            owner_principal_id,
            project_id,
            PLAN_IDS[0],
            version,
            lineage_revision,
            revision_kind,
            lifecycle,
            parent_plan_id,
            READINESS_REVIEW_ID,
            IMAGE_SET_FINGERPRINT,
            REGION_SET_ID,
            GEOMETRY_FINGERPRINT,
            INVOCATION_ID,
            FINAL_ATTEMPT_ID,
            PROVIDER_ID,
            MODEL_ID,
            PROMPT_ID,
            PROMPT_HASH,
            content_hash,
            actor_type,
            actor_id,
            actor_display_name,
        ),
    )


def seed(
    connection: psycopg.Connection[dict[str, Any]],
    owner_id: uuid.UUID,
    project_id: uuid.UUID,
) -> None:
    _revision(connection)
    project = connection.execute(
        """
        SELECT project.owner_principal_id, account.display_name
        FROM paint_projects AS project
        JOIN user_accounts AS account ON account.id = %s
        WHERE project.id = %s
        """,
        (owner_id, project_id),
    ).fetchone()
    if project is None:
        raise AssertionError("missing Phase 3B staging project owner")
    owner_principal_id = str(project["owner_principal_id"])
    owner_display_name = str(project["display_name"])
    images = {
        str(row["role"]): row["id"]
        for row in connection.execute(
            """
            SELECT id, role FROM image_assets
            WHERE paint_project_id = %s AND is_current
            """,
            (project_id,),
        ).fetchall()
    }
    if set(images) != {"primary_front", "reference_back", "reference_angle"}:
        raise AssertionError("Phase 3B staging source image roles are incomplete")
    connection.commit()

    with connection.transaction():
        connection.execute(
            """
            INSERT INTO image_set_readiness_reviews (
                id, owner_principal_id, paint_project_id, version, verdict, reason,
                primary_front_image_asset_id, primary_front_role,
                reference_back_image_asset_id, reference_back_role,
                reference_angle_image_asset_id, reference_angle_role,
                image_set_fingerprint, actor_type, actor_id,
                actor_display_name_snapshot, created_at
            ) VALUES (
                %s, %s, %s, 1, 'ready', NULL,
                %s, 'primary_front', %s, 'reference_back', %s, 'reference_angle',
                %s, 'user', %s, %s, now()
            )
            """,
            (
                READINESS_REVIEW_ID,
                owner_principal_id,
                project_id,
                images["primary_front"],
                images["reference_back"],
                images["reference_angle"],
                IMAGE_SET_FINGERPRINT,
                owner_principal_id,
                owner_display_name,
            ),
        )
        connection.execute(
            """
            INSERT INTO region_sets (
                id, owner_principal_id, paint_project_id, version, lifecycle,
                source_primary_image_asset_id, source_primary_image_role,
                source_image_set_fingerprint, source_image_width, source_image_height,
                region_count, total_vertex_count, geometry_fingerprint,
                created_by_actor_type, created_by_actor_id,
                created_by_actor_display_name_snapshot, created_at
            ) VALUES (
                %s, %s, %s, 1, 'submitted', %s, 'primary_front', %s,
                768, 768, 2, 8, %s, 'user', %s, %s, now()
            )
            """,
            (
                REGION_SET_ID,
                owner_principal_id,
                project_id,
                images["primary_front"],
                IMAGE_SET_FINGERPRINT,
                GEOMETRY_FINGERPRINT,
                owner_principal_id,
                owner_display_name,
            ),
        )
        region_facts = (
            (
                REGION_IDS[0],
                uuid.UUID("3c000000-0000-4000-8000-000000000010"),
                "panel-a",
                0,
                100000,
            ),
            (
                REGION_IDS[1],
                uuid.UUID("3c000000-0000-4000-8000-000000000011"),
                "panel-b",
                1,
                400000,
            ),
        )
        for region_id, stable_key, label, z_index, start in region_facts:
            connection.execute(
                """
                INSERT INTO regions (
                    id, region_set_id, paint_project_id, owner_principal_id,
                    stable_region_key, kind, label, normalized_label, z_index,
                    opacity_ppm, notes, vertex_count, area_twice_ppm_squared,
                    bbox_min_x_ppm, bbox_min_y_ppm, bbox_max_x_ppm,
                    bbox_max_y_ppm, created_at
                ) VALUES (
                    %s, %s, %s, %s, %s, 'paint', %s, %s, %s, 600000,
                    'Synthetic staging recovery region.', 4, 80000000000,
                    %s, 100000, %s, 300000, now()
                )
                """,
                (
                    region_id,
                    REGION_SET_ID,
                    project_id,
                    owner_principal_id,
                    stable_key,
                    label,
                    label,
                    z_index,
                    start,
                    start + 200000,
                ),
            )
            for sequence, (x_ppm, y_ppm) in enumerate(
                (
                    (start, 100000),
                    (start + 200000, 100000),
                    (start + 200000, 300000),
                    (start, 300000),
                )
            ):
                connection.execute(
                    """
                    INSERT INTO region_vertices (region_id, sequence, region_set_id, x_ppm, y_ppm)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (region_id, sequence, REGION_SET_ID, x_ppm, y_ppm),
                )
        connection.execute(
            """
            INSERT INTO region_set_reviews (
                id, owner_principal_id, paint_project_id, region_set_id, version,
                verdict, reason, actor_type, actor_id,
                actor_display_name_snapshot, created_at
            ) VALUES (%s, %s, %s, %s, 1, 'approved', NULL, 'user', %s, %s, now())
            """,
            (
                REGION_SET_REVIEW_ID,
                owner_principal_id,
                project_id,
                REGION_SET_ID,
                owner_principal_id,
                owner_display_name,
            ),
        )
        _insert_plan(
            connection,
            plan_id=PLAN_IDS[0],
            owner_principal_id=owner_principal_id,
            project_id=project_id,
            version=1,
            lineage_revision=1,
            revision_kind="generated",
            lifecycle="generated",
            parent_plan_id=None,
            actor_type="provider",
            actor_id="fixture_local",
            actor_display_name="Fixture Provider",
            content_hash="6" * 64,
        )
        for offset, (region_id, stable_key, label, _z_index, _start) in enumerate(
            region_facts
        ):
            _insert_instruction(
                connection,
                instruction_id=INSTRUCTION_IDS[offset],
                plan_id=PLAN_IDS[0],
                region_id=region_id,
                stable_region_key=stable_key,
                label=label,
                sequence=offset,
            )

    with connection.transaction():
        connection.execute(
            "UPDATE paint_plans SET lifecycle = 'superseded' WHERE id = %s",
            (PLAN_IDS[0],),
        )
        _insert_plan(
            connection,
            plan_id=PLAN_IDS[1],
            owner_principal_id=owner_principal_id,
            project_id=project_id,
            version=2,
            lineage_revision=2,
            revision_kind="edited",
            lifecycle="edited",
            parent_plan_id=PLAN_IDS[0],
            actor_type="user",
            actor_id=owner_principal_id,
            actor_display_name=owner_display_name,
            content_hash="7" * 64,
        )
        for offset, (region_id, stable_key, label, _z_index, _start) in enumerate(
            region_facts
        ):
            _insert_instruction(
                connection,
                instruction_id=INSTRUCTION_IDS[offset + 2],
                plan_id=PLAN_IDS[1],
                region_id=region_id,
                stable_region_key=stable_key,
                label=label,
                sequence=offset,
            )

    with connection.transaction():
        connection.execute(
            """
            INSERT INTO paint_plan_review_events (
                id, owner_principal_id, paint_project_id, paint_plan_id,
                paint_plan_version, action, actor_user_id, actor_principal_id,
                actor_display_name_snapshot, reason, created_at
            ) VALUES (%s, %s, %s, %s, 2, 'submit', %s, %s, %s, NULL, now())
            """,
            (
                REVIEW_EVENT_IDS[0],
                owner_principal_id,
                project_id,
                PLAN_IDS[1],
                owner_id,
                owner_principal_id,
                owner_display_name,
            ),
        )
        connection.execute(
            "UPDATE paint_plans SET lifecycle = 'under_review' WHERE id = %s",
            (PLAN_IDS[1],),
        )

    with connection.transaction():
        connection.execute(
            """
            INSERT INTO paint_plan_review_events (
                id, owner_principal_id, paint_project_id, paint_plan_id,
                paint_plan_version, action, actor_user_id, actor_principal_id,
                actor_display_name_snapshot, reason, created_at
            ) VALUES (%s, %s, %s, %s, 2, 'approve', %s, %s, %s, NULL, now())
            """,
            (
                REVIEW_EVENT_IDS[1],
                owner_principal_id,
                project_id,
                PLAN_IDS[1],
                owner_id,
                owner_principal_id,
                owner_display_name,
            ),
        )
        connection.execute(
            "UPDATE paint_plans SET lifecycle = 'approved' WHERE id = %s",
            (PLAN_IDS[1],),
        )
    print(
        "PHASE3B_BACKUP_FIXTURE_SEEDED"
        f" alembic={EXPECTED_ALEMBIC_REVISION} tables={len(PHASE3B_TABLES)}"
        " plans=2 instructions=4 review_events=2"
        " provider_network_calls=0 real_keys=0 billable_usage=0"
    )


def verify(
    connection: psycopg.Connection[dict[str, Any]],
    owner_id: uuid.UUID,
    project_id: uuid.UUID,
) -> None:
    _revision(connection)
    counts = {
        table: int(
            connection.execute(f"SELECT count(*) AS count FROM {table}").fetchone()[
                "count"
            ]
        )
        for table in PHASE3B_TABLES
    }
    if counts != EXPECTED_COUNTS:
        raise AssertionError(
            "Phase 3B recovery table counts differ from the synthetic source"
        )
    plan_graph = connection.execute(
        """
        SELECT current_plan.lifecycle, current_plan.parent_plan_id,
               current_plan.lineage_id, current_plan.lineage_revision,
               source_plan.lifecycle AS source_lifecycle,
               readiness.verdict AS readiness_verdict,
               region_review.verdict AS region_verdict,
               invocation.final_attempt_id, attempt.retry_of_attempt_id,
               provider.provider_key, model.model_id, prompt.template_key,
               (SELECT count(*) FROM paint_plan_region_instructions instruction
                WHERE instruction.paint_plan_id = current_plan.id) AS instruction_count,
               (SELECT string_agg(event.action, ',' ORDER BY event.created_at, event.id)
                FROM paint_plan_review_events event
                WHERE event.paint_plan_id = current_plan.id) AS review_history
        FROM paint_plans AS current_plan
        JOIN paint_plans AS source_plan ON source_plan.id = current_plan.parent_plan_id
        JOIN image_set_readiness_reviews AS readiness
          ON readiness.id = current_plan.source_readiness_review_id
        JOIN region_set_reviews AS region_review
          ON region_review.region_set_id = current_plan.source_region_set_id
        JOIN invocation_requests AS invocation ON invocation.id = current_plan.source_invocation_id
        JOIN invocation_attempts AS attempt ON attempt.id = current_plan.source_attempt_id
        JOIN provider_definitions AS provider ON provider.id = current_plan.provider_definition_id
        JOIN model_definitions AS model ON model.id = current_plan.model_definition_id
        JOIN prompt_template_definitions AS prompt
          ON prompt.id = current_plan.prompt_template_definition_id
        WHERE current_plan.id = %s AND current_plan.paint_project_id = %s
        """,
        (PLAN_IDS[1], project_id),
    ).fetchone()
    if plan_graph is None or tuple(plan_graph.values()) != (
        "approved",
        PLAN_IDS[0],
        PLAN_IDS[0],
        2,
        "superseded",
        "ready",
        "approved",
        FINAL_ATTEMPT_ID,
        uuid.UUID("3b000000-0000-4000-8000-000000000016"),
        "fixture_local",
        "fixture-text-v1",
        "paint-plan",
        2,
        "submit,approve",
    ):
        raise AssertionError("Phase 3B Paint Plan recovery relationship mismatch")
    pricing = connection.execute(
        """
        SELECT pricing.id, provider.enabled, model.status
        FROM provider_pricing_snapshots AS pricing
        JOIN provider_definitions AS provider ON provider.id = pricing.provider_definition_id
        JOIN model_definitions AS model ON model.id = pricing.model_definition_id
        WHERE pricing.id = %s
        """,
        (PRICING_ID,),
    ).fetchone()
    if pricing is None or tuple(pricing.values()) != (PRICING_ID, False, "disabled"):
        raise AssertionError("Phase 3B pricing snapshot recovery relationship mismatch")
    actor = connection.execute(
        "SELECT id FROM user_accounts WHERE id = %s",
        (owner_id,),
    ).fetchone()
    if actor is None:
        raise AssertionError("Phase 3B review actor recovery relationship mismatch")
    print(
        "PHASE3B_BACKUP_FIXTURE_VERIFIED"
        f" alembic={EXPECTED_ALEMBIC_REVISION} tables={len(PHASE3B_TABLES)}"
        " relationships=project-readiness-region-invocation-attempt-provider-model-prompt-pricing-lineage-review"
        " provider_network_calls=0 real_keys=0 billable_usage=0"
    )


def main(argv: Sequence[str]) -> int:
    if len(argv) != 4 or argv[1] not in {"seed", "verify"}:
        raise SystemExit(
            "usage: verify_phase3b_backup_rows.py seed|verify OWNER_ID PROJECT_ID"
        )
    owner_id = uuid.UUID(argv[2])
    project_id = uuid.UUID(argv[3])
    with _database_connection(Settings.model_validate({})) as connection:
        if argv[1] == "seed":
            seed(connection, owner_id, project_id)
        else:
            verify(connection, owner_id, project_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
