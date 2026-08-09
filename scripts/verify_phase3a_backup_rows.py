"""Seed and verify synthetic Phase 3A relationships for the staging recovery drill."""

from __future__ import annotations

import sys
import uuid
from collections.abc import Sequence
from typing import Any

import psycopg

from creativedeploy_api.core.config import Settings
from creativedeploy_api.tools.staging_backup_restore import (
    EXPECTED_ALEMBIC_REVISION,
    PHASE3A_TABLES,
    _database_connection,
)

PROVIDER_ID = uuid.UUID("3a000000-0000-4000-8000-000000000001")
MODEL_ID = uuid.UUID("3a000000-0000-4000-8000-000000000101")
CAPABILITY_ID = uuid.UUID("3a000000-0000-4000-8000-000000001001")

OLD_CREDENTIAL_ID = uuid.UUID("3b000000-0000-4000-8000-000000000002")
CREDENTIAL_ID = uuid.UUID("3b000000-0000-4000-8000-000000000001")
GRANT_ID = uuid.UUID("3b000000-0000-4000-8000-000000000003")
PREFERENCE_ID = uuid.UUID("3b000000-0000-4000-8000-000000000004")
POLICY_ID = uuid.UUID("3b000000-0000-4000-8000-000000000005")
POLICY_PROVIDER_ID = uuid.UUID("3b000000-0000-4000-8000-000000000006")
POLICY_MODEL_ID = uuid.UUID("3b000000-0000-4000-8000-000000000007")
POLICY_CAPABILITY_ID = uuid.UUID("3b000000-0000-4000-8000-000000000008")
POLICY_CREDENTIAL_ID = uuid.UUID("3b000000-0000-4000-8000-000000000009")
USER_BUDGET_POLICY_ID = uuid.UUID("3b000000-0000-4000-8000-000000000010")
PROJECT_BUDGET_POLICY_ID = uuid.UUID("3b000000-0000-4000-8000-000000000011")
USER_COUNTER_ID = uuid.UUID("3b000000-0000-4000-8000-000000000012")
PROJECT_COUNTER_ID = uuid.UUID("3b000000-0000-4000-8000-000000000013")
INVOCATION_ID = uuid.UUID("3b000000-0000-4000-8000-000000000014")
FIRST_ATTEMPT_ID = uuid.UUID("3b000000-0000-4000-8000-000000000016")
FINAL_ATTEMPT_ID = uuid.UUID("3b000000-0000-4000-8000-000000000015")
RESERVATION_ID = uuid.UUID("3b000000-0000-4000-8000-000000000017")
INVOCATION_EVENT_ID = uuid.UUID("3b000000-0000-4000-8000-000000000018")
USAGE_ID = uuid.UUID("3b000000-0000-4000-8000-000000000019")
COST_ID = uuid.UUID("3b000000-0000-4000-8000-000000000020")
AUDIT_ID = uuid.UUID("3b000000-0000-4000-8000-000000000021")
COMMAND_ID = uuid.UUID("3b000000-0000-4000-8000-000000000022")
REQUEST_ID = uuid.UUID("3b000000-0000-4000-8000-000000000023")
IDEMPOTENCY_KEY = uuid.UUID("3b000000-0000-4000-8000-000000000024")

EXPECTED_COUNTS = {table: 1 for table in PHASE3A_TABLES}
EXPECTED_COUNTS.update(
    {
        "capability_definitions": 3,
        "model_definitions": 2,
        "provider_capabilities": 3,
        "model_capabilities": 5,
        "credential_records": 2,
        "invocation_attempts": 2,
    }
)


def _revision(connection: psycopg.Connection[dict[str, Any]]) -> str:
    row = connection.execute("SELECT version_num FROM alembic_version").fetchone()
    if row is None:
        raise AssertionError("missing Alembic revision")
    revision = str(row["version_num"])
    if revision != EXPECTED_ALEMBIC_REVISION:
        raise AssertionError("unexpected Alembic revision")
    return revision


def seed(
    connection: psycopg.Connection[dict[str, Any]],
    owner_id: uuid.UUID,
    project_id: uuid.UUID,
) -> None:
    _revision(connection)
    with connection.transaction():
        connection.execute(
            """
            INSERT INTO credential_records (
                id, owner_user_id, provider_definition_id, provider_key,
                key_fingerprint, alias, status, revoked_at, revision, created_at, updated_at
            ) VALUES (
                %s, %s, %s, 'fixture_local', 'synthetic-staging-fingerprint',
                'Synthetic replaced credential', 'revoked', now(), 1, now(), now()
            )
            """,
            (OLD_CREDENTIAL_ID, owner_id, PROVIDER_ID),
        )
        connection.execute(
            """
            INSERT INTO credential_records (
                id, owner_user_id, provider_definition_id, provider_key,
                key_fingerprint, last_four, alias, status, encryption_version,
                data_algorithm, ciphertext, data_nonce, data_authentication_tag,
                wrapped_dek, wrap_algorithm, wrap_nonce, wrap_authentication_tag,
                aad_version, replaces_credential_id, revision, created_at, updated_at
            ) VALUES (
                %s, %s, %s, 'fixture_local', 'synthetic-staging-fingerprint-active',
                '0000', 'Synthetic active credential', 'active', 'fixture-envelope-v1',
                'AES-256-GCM', %s, %s, %s, %s, 'AES-256-GCM', %s, %s,
                'phase3a-v1', %s, 1, now(), now()
            )
            """,
            (
                CREDENTIAL_ID,
                owner_id,
                PROVIDER_ID,
                b"synthetic-ciphertext-only",
                bytes(range(12)),
                b"\x01" * 16,
                b"synthetic-wrapped-dek-only",
                bytes(range(12, 24)),
                b"\x02" * 16,
                OLD_CREDENTIAL_ID,
            ),
        )
        connection.execute(
            """
            INSERT INTO credential_project_grants (
                id, credential_id, project_id, granted_by_user_id, created_at, revision
            ) VALUES (%s, %s, %s, %s, now(), 1)
            """,
            (GRANT_ID, CREDENTIAL_ID, project_id, owner_id),
        )
        connection.execute(
            """
            INSERT INTO user_provider_preferences (
                id, user_id, enabled, default_provider_definition_id,
                default_model_definition_id, default_credential_id, timeout_ms,
                streaming_enabled, revision, updated_at
            ) VALUES (%s, %s, true, %s, %s, %s, 30000, false, 1, now())
            """,
            (PREFERENCE_ID, owner_id, PROVIDER_ID, MODEL_ID, CREDENTIAL_ID),
        )
        connection.execute(
            """
            INSERT INTO project_model_policies (
                id, project_id, enabled, default_provider_definition_id,
                default_model_definition_id, default_credential_id,
                per_invocation_limit_minor_units, currency, allow_unknown_cost,
                unknown_cost_reservation_minor_units, allow_manual_model_id,
                allow_fallback, require_paid_call_confirmation, updated_by_user_id,
                revision, updated_at
            ) VALUES (
                %s, %s, true, %s, %s, %s, 100, 'FIXTURE_CREDITS', false,
                0, false, false, false, %s, 1, now()
            )
            """,
            (POLICY_ID, project_id, PROVIDER_ID, MODEL_ID, CREDENTIAL_ID, owner_id),
        )
        for statement, values in (
            (
                "INSERT INTO project_model_policy_providers (id, project_model_policy_id, provider_definition_id, created_at) VALUES (%s, %s, %s, now())",
                (POLICY_PROVIDER_ID, POLICY_ID, PROVIDER_ID),
            ),
            (
                "INSERT INTO project_model_policy_models (id, project_model_policy_id, model_definition_id, created_at) VALUES (%s, %s, %s, now())",
                (POLICY_MODEL_ID, POLICY_ID, MODEL_ID),
            ),
            (
                "INSERT INTO project_model_policy_capabilities (id, project_model_policy_id, capability_definition_id, created_at) VALUES (%s, %s, %s, now())",
                (POLICY_CAPABILITY_ID, POLICY_ID, CAPABILITY_ID),
            ),
            (
                "INSERT INTO project_model_policy_credentials (id, project_model_policy_id, credential_record_id, created_at) VALUES (%s, %s, %s, now())",
                (POLICY_CREDENTIAL_ID, POLICY_ID, CREDENTIAL_ID),
            ),
        ):
            connection.execute(statement, values)
        for table, identifier, subject_column, subject_id in (
            ("user_budget_policies", USER_BUDGET_POLICY_ID, "user_id", owner_id),
            (
                "project_budget_policies",
                PROJECT_BUDGET_POLICY_ID,
                "project_id",
                project_id,
            ),
        ):
            connection.execute(
                f"""
                INSERT INTO {table} (
                    id, {subject_column}, product_space, currency, enabled,
                    per_invocation_limit_minor_units, cumulative_limit_minor_units,
                    window_seconds, allow_unknown_cost,
                    unknown_cost_reservation_minor_units, revision, updated_at
                ) VALUES (%s, %s, 'paintpilot', 'FIXTURE_CREDITS', true,
                          100, 1000, 3600, false, 0, 1, now())
                """,
                (identifier, subject_id),
            )
        for table, identifier, subject_column, subject_id in (
            ("user_budget_counters", USER_COUNTER_ID, "user_id", owner_id),
            ("project_budget_counters", PROJECT_COUNTER_ID, "project_id", project_id),
        ):
            connection.execute(
                f"""
                INSERT INTO {table} (
                    id, {subject_column}, product_space, currency, window_start,
                    window_end, limit_minor_units, committed_minor_units,
                    reserved_minor_units, revision
                ) VALUES (%s, %s, 'paintpilot', 'FIXTURE_CREDITS',
                          now() - interval '1 minute', now() + interval '59 minutes',
                          1000, 2, 0, 1)
                """,
                (identifier, subject_id),
            )
        connection.execute(
            """
            INSERT INTO invocation_requests (
                id, requesting_user_id, product_space, project_id, project_scope_id,
                invocation_family, idempotency_key, canonicalization_version,
                canonical_request_payload_hash, requested_capabilities,
                requested_provider_definition_id, requested_model_definition_id,
                requested_credential_id, request_id, max_attempts,
                total_elapsed_time_limit_ms, confirmation_snapshot, budget_snapshot,
                safe_payload, status, started_at, terminal_at, revision,
                created_at, updated_at
            ) VALUES (
                %s, %s, 'paintpilot', %s, %s, 'fixture_invocation', %s,
                'phase3a-v1', %s, '["text_generation"]'::jsonb, %s, %s, %s,
                %s, 2, 30000, '{}'::jsonb, '{"currency":"FIXTURE_CREDITS"}'::jsonb,
                '{"fixture":"staging-backup"}'::jsonb, 'succeeded', now(), now(),
                1, now(), now()
            )
            """,
            (
                INVOCATION_ID,
                owner_id,
                project_id,
                project_id,
                IDEMPOTENCY_KEY,
                "sha256:" + "1" * 64,
                PROVIDER_ID,
                MODEL_ID,
                CREDENTIAL_ID,
                REQUEST_ID,
            ),
        )
        connection.execute(
            """
            INSERT INTO invocation_attempts (
                id, invocation_id, attempt_number, provider_definition_id,
                model_definition_id, provider_key, model_id, adapter_version,
                capability_snapshot, credential_id,
                credential_encryption_version_snapshot, temporary_credential,
                fallback_decision, currency, status, terminal_at,
                final_error_category, safe_provider_metadata, latency_ms,
                revision, created_at
            ) VALUES (
                %s, %s, 1, %s, %s, 'fixture_local', 'fixture-text-v1',
                'fixture-v1', '["text_generation"]'::jsonb, %s,
                'fixture-envelope-v1', false, 'disabled', 'FIXTURE_CREDITS',
                'failed', now(), 'synthetic_retry', '{}'::jsonb, 1, 1, now()
            )
            """,
            (FIRST_ATTEMPT_ID, INVOCATION_ID, PROVIDER_ID, MODEL_ID, CREDENTIAL_ID),
        )
        connection.execute(
            """
            INSERT INTO invocation_attempts (
                id, invocation_id, attempt_number, provider_definition_id,
                model_definition_id, provider_key, model_id, adapter_version,
                capability_snapshot, credential_id,
                credential_encryption_version_snapshot, temporary_credential,
                retry_of_attempt_id, fallback_decision, currency, status,
                dispatched_at, terminal_at, safe_provider_metadata, latency_ms,
                revision, created_at
            ) VALUES (
                %s, %s, 2, %s, %s, 'fixture_local', 'fixture-text-v1',
                'fixture-v1', '["text_generation"]'::jsonb, %s,
                'fixture-envelope-v1', false, %s, 'disabled', 'FIXTURE_CREDITS',
                'succeeded', now(), now(), '{"fixture":"local"}'::jsonb, 2, 1, now()
            )
            """,
            (
                FINAL_ATTEMPT_ID,
                INVOCATION_ID,
                PROVIDER_ID,
                MODEL_ID,
                CREDENTIAL_ID,
                FIRST_ATTEMPT_ID,
            ),
        )
        connection.execute(
            "UPDATE invocation_requests SET final_attempt_id = %s WHERE id = %s",
            (FINAL_ATTEMPT_ID, INVOCATION_ID),
        )
        connection.execute(
            """
            INSERT INTO budget_reservations (
                id, invocation_id, attempt_id, user_counter_id, project_counter_id,
                currency, reserved_amount, state, created_at, admission_expires_at,
                dispatch_committed_at, settled_at, revision
            ) VALUES (
                %s, %s, %s, %s, %s, 'FIXTURE_CREDITS', 2, 'settled', now(),
                now() + interval '1 minute', now(), now(), 1
            )
            """,
            (
                RESERVATION_ID,
                INVOCATION_ID,
                FINAL_ATTEMPT_ID,
                USER_COUNTER_ID,
                PROJECT_COUNTER_ID,
            ),
        )
        connection.execute(
            """
            INSERT INTO ai_invocation_events (
                id, invocation_id, attempt_id, event_type, from_status,
                to_status, safe_metadata, created_at
            ) VALUES (%s, %s, %s, 'fixture_completed', 'running', 'succeeded',
                      '{}'::jsonb, now())
            """,
            (INVOCATION_EVENT_ID, INVOCATION_ID, FINAL_ATTEMPT_ID),
        )
        connection.execute(
            """
            INSERT INTO ai_usage_ledger (
                id, invocation_id, attempt_id, provider_definition_id,
                model_definition_id, source, canonical_sequence, input_units,
                output_units, safe_metadata, created_at
            ) VALUES (%s, %s, %s, %s, %s, 'fixture_staging', 1, 1, 1,
                      '{}'::jsonb, now())
            """,
            (USAGE_ID, INVOCATION_ID, FINAL_ATTEMPT_ID, PROVIDER_ID, MODEL_ID),
        )
        connection.execute(
            """
            INSERT INTO ai_cost_ledger (
                id, invocation_id, attempt_id, provider_definition_id,
                model_definition_id, source, canonical_sequence,
                amount_minor_units, currency, created_at
            ) VALUES (%s, %s, %s, %s, %s, 'fixture_staging', 1, 2,
                      'FIXTURE_CREDITS', now())
            """,
            (COST_ID, INVOCATION_ID, FINAL_ATTEMPT_ID, PROVIDER_ID, MODEL_ID),
        )
        connection.execute(
            """
            INSERT INTO ai_audit_events (
                id, actor_user_id, product_space, project_id, credential_id,
                invocation_id, attempt_id, provider_definition_id,
                model_definition_id, action, outcome, request_id, safe_metadata,
                created_at
            ) VALUES (%s, %s, 'paintpilot', %s, %s, %s, %s, %s, %s,
                      'fixture_invocation', 'succeeded', %s,
                      '{"fixture":"staging-backup"}'::jsonb, now())
            """,
            (
                AUDIT_ID,
                owner_id,
                project_id,
                CREDENTIAL_ID,
                INVOCATION_ID,
                FINAL_ATTEMPT_ID,
                PROVIDER_ID,
                MODEL_ID,
                REQUEST_ID,
            ),
        )
        connection.execute(
            """
            INSERT INTO ai_command_idempotency_records (
                id, requesting_user_id, command_scope, idempotency_key,
                payload_hash, response_snapshot, http_status, created_at
            ) VALUES (%s, %s, 'staging-backup-fixture', %s, %s,
                      '{"status":"synthetic"}'::jsonb, 200, now())
            """,
            (COMMAND_ID, owner_id, IDEMPOTENCY_KEY, "sha256:" + "2" * 64),
        )
    print(
        "PHASE3A_BACKUP_FIXTURE_SEEDED"
        f" alembic={EXPECTED_ALEMBIC_REVISION} tables={len(PHASE3A_TABLES)}"
        " provider_network_calls=0 real_keys=0 real_cost=0"
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
        for table in PHASE3A_TABLES
    }
    if counts != EXPECTED_COUNTS:
        raise AssertionError(
            "Phase 3A recovery table counts differ from the synthetic source"
        )
    credential_graph = connection.execute(
        """
        SELECT active.owner_user_id, active.replaces_credential_id, grant_row.project_id,
               octet_length(active.ciphertext) AS ciphertext_size,
               old.status AS old_status, active.status AS active_status
        FROM credential_records AS active
        JOIN credential_records AS old ON old.id = active.replaces_credential_id
        JOIN credential_project_grants AS grant_row ON grant_row.credential_id = active.id
        WHERE active.id = %s
        """,
        (CREDENTIAL_ID,),
    ).fetchone()
    if credential_graph != {
        "owner_user_id": owner_id,
        "replaces_credential_id": OLD_CREDENTIAL_ID,
        "project_id": project_id,
        "ciphertext_size": len(b"synthetic-ciphertext-only"),
        "old_status": "revoked",
        "active_status": "active",
    }:
        raise AssertionError("credential and Grant recovery relationship mismatch")
    policy_links = connection.execute(
        """
        SELECT p.default_provider_definition_id, p.default_model_definition_id,
               p.default_credential_id,
               (SELECT count(*) FROM project_model_policy_providers WHERE project_model_policy_id = p.id) AS providers,
               (SELECT count(*) FROM project_model_policy_models WHERE project_model_policy_id = p.id) AS models,
               (SELECT count(*) FROM project_model_policy_capabilities WHERE project_model_policy_id = p.id) AS capabilities,
               (SELECT count(*) FROM project_model_policy_credentials WHERE project_model_policy_id = p.id) AS credentials
        FROM project_model_policies AS p WHERE p.id = %s
        """,
        (POLICY_ID,),
    ).fetchone()
    if policy_links is None or tuple(policy_links.values()) != (
        PROVIDER_ID,
        MODEL_ID,
        CREDENTIAL_ID,
        1,
        1,
        1,
        1,
    ):
        raise AssertionError("policy and Registry recovery relationship mismatch")
    invocation_graph = connection.execute(
        """
        SELECT request.final_attempt_id, final_attempt.retry_of_attempt_id,
               reservation.user_counter_id, reservation.project_counter_id,
               usage.input_units, cost.amount_minor_units,
               event.to_status, audit.outcome
        FROM invocation_requests AS request
        JOIN invocation_attempts AS final_attempt ON final_attempt.id = request.final_attempt_id
        JOIN budget_reservations AS reservation ON reservation.attempt_id = final_attempt.id
        JOIN ai_usage_ledger AS usage ON usage.attempt_id = final_attempt.id
        JOIN ai_cost_ledger AS cost ON cost.attempt_id = final_attempt.id
        JOIN ai_invocation_events AS event ON event.attempt_id = final_attempt.id
        JOIN ai_audit_events AS audit ON audit.attempt_id = final_attempt.id
        WHERE request.id = %s
        """,
        (INVOCATION_ID,),
    ).fetchone()
    if invocation_graph is None or tuple(invocation_graph.values()) != (
        FINAL_ATTEMPT_ID,
        FIRST_ATTEMPT_ID,
        USER_COUNTER_ID,
        PROJECT_COUNTER_ID,
        1,
        2,
        "succeeded",
        "succeeded",
    ):
        raise AssertionError(
            "invocation, budget, ledger, and audit recovery relationship mismatch"
        )
    print(
        "PHASE3A_BACKUP_FIXTURE_VERIFIED"
        f" alembic={EXPECTED_ALEMBIC_REVISION} tables={len(PHASE3A_TABLES)}"
        " relationships=credential-grant-policy-invocation-budget-ledger-audit"
        " provider_network_calls=0 real_keys=0 real_cost=0"
    )


def main(argv: Sequence[str]) -> int:
    if len(argv) != 4 or argv[1] not in {"seed", "verify"}:
        raise SystemExit(
            "usage: verify_phase3a_backup_rows.py seed|verify OWNER_ID PROJECT_ID"
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
