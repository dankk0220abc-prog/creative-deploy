"""Seed and verify a deterministic Arcana graph for the staging recovery drill."""

from __future__ import annotations

import sys
import uuid
from collections.abc import Sequence
from typing import Any

import psycopg

from creativedeploy_api.core.config import Settings
from creativedeploy_api.tools.staging_backup_restore import (
    ARCANA_TABLES,
    EXPECTED_ALEMBIC_REVISION,
    _database_connection,
)

READING_ID = uuid.UUID("4d000000-0000-4000-8000-000000000001")
READING_CARD_IDS = (
    uuid.UUID("4d000000-0000-4000-8000-000000000101"),
    uuid.UUID("4d000000-0000-4000-8000-000000000102"),
    uuid.UUID("4d000000-0000-4000-8000-000000000103"),
)
INTERPRETATION_ID = uuid.UUID("4d000000-0000-4000-8000-000000000201")
JOURNAL_ID = uuid.UUID("4d000000-0000-4000-8000-000000000301")
CARD_IDS = ("major-00-fool", "major-01-magician", "major-02-high-priestess")
POSITIONS = (
    (0, "past", "Past", "过去", "upright", 1),
    (1, "present", "Present", "现在", "reversed", 2),
    (2, "future", "Future", "未来", "upright", 3),
)
EXPECTED_COUNTS = {
    "tarot_card_definitions": 78,
    "tarot_spread_definitions": 1,
    "tarot_readings": 1,
    "tarot_reading_cards": 3,
    "tarot_interpretation_revisions": 1,
    "tarot_journal_entries": 1,
}
RETRIEVED_CONTEXT = [
    {
        "source_id": "arcana-core-v1",
        "chunk_id": "card:major-00-fool:upright",
        "source_title": "CreativeDeploy Arcana Core v1",
        "section": "card/major-00-fool/upright",
        "content": "Synthetic offline recovery context.",
        "metadata": {"fixture": True},
    }
]
CITATIONS = [
    {
        "source_id": "arcana-core-v1",
        "chunk_id": "card:major-00-fool:upright",
        "target_path": "/positions/0",
    }
]
DOCUMENT = {
    "schema_version": "tarot-reading.v2",
    "generation_locale": "zh-CN",
    "summary": "确定性离线恢复演练解读。",
    "positions": [
        {
            "position_key": position[1],
            "card_id": card_id,
            "orientation": position[4],
        }
        for card_id, position in zip(CARD_IDS, POSITIONS, strict=True)
    ],
    "knowledge_basis": CITATIONS,
}


def _assert_revision(connection: psycopg.Connection[dict[str, Any]]) -> None:
    row = connection.execute("SELECT version_num FROM alembic_version").fetchone()
    if row is None or row["version_num"] != EXPECTED_ALEMBIC_REVISION:
        raise AssertionError("unexpected Alembic revision")


def seed(
    connection: psycopg.Connection[dict[str, Any]],
    owner_id: uuid.UUID,
    project_id: uuid.UUID,
) -> None:
    _assert_revision(connection)
    owner = connection.execute(
        """
        SELECT project.owner_principal_id
        FROM paint_projects AS project
        JOIN user_accounts AS account ON account.id = %s
        WHERE project.id = %s
        """,
        (owner_id, project_id),
    ).fetchone()
    if owner is None:
        raise AssertionError("missing Arcana staging owner")
    owner_principal_id = str(owner["owner_principal_id"])
    connection.commit()
    with connection.transaction():
        connection.execute(
            """
            INSERT INTO tarot_readings (
                id, owner_principal_id, status, question, generation_locale,
                spread_key, spread_version, drawn_at, interpreted_at, saved_at
            ) VALUES (
                %s, %s, 'saved', '恢复后哪个务实选择值得关注？', 'zh-CN',
                'past-present-future', 1, now(), now(), now()
            )
            """,
            (READING_ID, owner_principal_id),
        )
        for row_id, card_id, position in zip(
            READING_CARD_IDS, CARD_IDS, POSITIONS, strict=True
        ):
            connection.execute(
                """
                INSERT INTO tarot_reading_cards (
                    id, reading_id, card_definition_id, position_index,
                    position_key, position_name_en, position_name_zh,
                    orientation, draw_order
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (row_id, READING_ID, card_id, *position),
            )
        connection.execute(
            """
            INSERT INTO tarot_interpretation_revisions (
                id, reading_id, revision, source, schema_version, provider_key,
                model_id, adapter_version, prompt_version, input_hash, document,
                retrieved_context_snapshot, citation_snapshot,
                source_invocation_id, source_attempt_id
            ) VALUES (
                %s, %s, 1, 'fixture_local', 'tarot-reading.v2', 'fixture_local',
                'fixture-tarot-v2', 'fixture-tarot-v2', 1, %s, %s, %s, %s,
                NULL, NULL
            )
            """,
            (
                INTERPRETATION_ID,
                READING_ID,
                "d" * 64,
                psycopg.types.json.Jsonb(DOCUMENT),
                psycopg.types.json.Jsonb(RETRIEVED_CONTEXT),
                psycopg.types.json.Jsonb(CITATIONS),
            ),
        )
        connection.execute(
            """
            INSERT INTO tarot_journal_entries (
                id, reading_id, owner_principal_id, personal_interpretation, notes
            ) VALUES (%s, %s, %s, %s, %s)
            """,
            (
                JOURNAL_ID,
                READING_ID,
                owner_principal_id,
                "恢复演练中的个人解读。",
                "仅限私密日志的确定性离线备注。",
            ),
        )
    verify(connection, owner_id, project_id)


def verify(
    connection: psycopg.Connection[dict[str, Any]],
    owner_id: uuid.UUID,
    project_id: uuid.UUID,
) -> None:
    _assert_revision(connection)
    counts = {
        table: int(
            connection.execute(f"SELECT count(*) AS count FROM {table}").fetchone()[
                "count"
            ]
        )
        for table in ARCANA_TABLES
    }
    if counts != EXPECTED_COUNTS:
        raise AssertionError(
            "Arcana recovery table counts differ from the synthetic source"
        )
    owner = connection.execute(
        """
        SELECT project.owner_principal_id
        FROM paint_projects AS project
        JOIN user_accounts AS account ON account.id = %s
        WHERE project.id = %s
        """,
        (owner_id, project_id),
    ).fetchone()
    if owner is None:
        raise AssertionError("missing restored Arcana owner")
    owner_principal_id = str(owner["owner_principal_id"])
    reading = connection.execute(
        """
        SELECT id, owner_principal_id, status, generation_locale, spread_key,
               spread_version, drawn_at IS NOT NULL AS drawn,
               interpreted_at IS NOT NULL AS interpreted,
               saved_at IS NOT NULL AS saved
        FROM tarot_readings WHERE id = %s
        """,
        (READING_ID,),
    ).fetchone()
    if reading is None or tuple(reading.values()) != (
        READING_ID,
        owner_principal_id,
        "saved",
        "zh-CN",
        "past-present-future",
        1,
        True,
        True,
        True,
    ):
        raise AssertionError("Arcana reading identity or lifecycle mismatch")
    cards = connection.execute(
        """
        SELECT draw.id, draw.reading_id, draw.card_definition_id,
               draw.position_index, draw.position_key, draw.orientation, draw.draw_order,
               definition.id AS definition_id
        FROM tarot_reading_cards AS draw
        JOIN tarot_card_definitions AS definition
          ON definition.id = draw.card_definition_id
        WHERE draw.reading_id = %s
        ORDER BY draw.position_index
        """,
        (READING_ID,),
    ).fetchall()
    expected_cards = [
        (
            row_id,
            READING_ID,
            card_id,
            position[0],
            position[1],
            position[4],
            position[5],
            card_id,
        )
        for row_id, card_id, position in zip(
            READING_CARD_IDS, CARD_IDS, POSITIONS, strict=True
        )
    ]
    if [tuple(row.values()) for row in cards] != expected_cards:
        raise AssertionError("Arcana draw identifiers or foreign keys mismatch")
    interpretation = connection.execute(
        """
        SELECT id, reading_id, revision, source, schema_version, provider_key,
               model_id, document, retrieved_context_snapshot, citation_snapshot,
               source_invocation_id, source_attempt_id
        FROM tarot_interpretation_revisions WHERE id = %s
        """,
        (INTERPRETATION_ID,),
    ).fetchone()
    if interpretation is None or tuple(interpretation.values()) != (
        INTERPRETATION_ID,
        READING_ID,
        1,
        "fixture_local",
        "tarot-reading.v2",
        "fixture_local",
        "fixture-tarot-v2",
        DOCUMENT,
        RETRIEVED_CONTEXT,
        CITATIONS,
        None,
        None,
    ):
        raise AssertionError("Arcana interpretation, citations, or provenance mismatch")
    journal = connection.execute(
        """
        SELECT id, reading_id, owner_principal_id, personal_interpretation, notes
        FROM tarot_journal_entries WHERE id = %s
        """,
        (JOURNAL_ID,),
    ).fetchone()
    if journal is None or tuple(journal.values()) != (
        JOURNAL_ID,
        READING_ID,
        owner_principal_id,
        "恢复演练中的个人解读。",
        "仅限私密日志的确定性离线备注。",
    ):
        raise AssertionError("Arcana private journal mismatch")
    print(
        "ARCANA_BACKUP_FIXTURE_VERIFIED"
        f" alembic={EXPECTED_ALEMBIC_REVISION} tables={len(ARCANA_TABLES)}"
        " reading=1 draw=3 interpretation=1 citations=1 journal=1"
        " provider_network_calls=0 real_keys=0 billable_usage=0"
    )


def main(argv: Sequence[str]) -> int:
    if len(argv) != 4 or argv[1] not in {"seed", "verify"}:
        raise SystemExit(
            "usage: verify_arcana_backup_rows.py seed|verify OWNER_ID PROJECT_ID"
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
