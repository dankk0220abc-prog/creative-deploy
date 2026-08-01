#!/bin/sh
set -eu

REPOSITORY_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
COMPOSE_FILE="${REPOSITORY_ROOT}/compose.artifact-smoke.yaml"
BASE_RUN_ID="${RUN_ID:-local_$(date -u +%Y%m%d%H%M%S)_$(uuidgen | tr '[:upper:]' '[:lower:]' | tr -d '-' | cut -c1-12)}"
RUN_A="${BASE_RUN_ID}_a"
RUN_B="${BASE_RUN_ID}_b"

for run_id in "${RUN_A}" "${RUN_B}"; do
  if ! printf '%s\n' "${run_id}" | grep -Eq '^[a-z0-9][a-z0-9_]{0,47}$'; then
    echo "derived isolation RUN_ID is invalid" >&2
    exit 1
  fi
done

PROJECT_A="creativedeploy-phase2b1-${RUN_A}"
PROJECT_B="creativedeploy-phase2b1-${RUN_B}"

compose_for() {
  run_id=$1
  project_name=$2
  smoke_port=$3
  shift 3
  database_id="phase2b1_${run_id}"
  SMOKE_RUN_ID="${run_id}" \
  ARTIFACT_SMOKE_PORT="${smoke_port}" \
  SMOKE_DATABASE_ADMIN_USER="${database_id}_admin" \
  SMOKE_DATABASE_ADMIN_PASSWORD="synthetic_admin_${run_id}_password" \
  SMOKE_DATABASE_MIGRATOR_USER="${database_id}_migrator" \
  SMOKE_DATABASE_MIGRATOR_PASSWORD="synthetic_migrator_${run_id}_password" \
  SMOKE_DATABASE_RUNTIME_USER="${database_id}_runtime" \
  SMOKE_DATABASE_RUNTIME_PASSWORD="synthetic_runtime_${run_id}_password" \
  SMOKE_DATABASE_NAME="${database_id}" \
  SMOKE_OIDC_CLIENT_ID="phase2b1-isolation-client" \
  SMOKE_OIDC_CLIENT_SECRET="synthetic_oidc_${run_id}_secret" \
  SMOKE_OIDC_USERS_JSON='[{"subject":"isolation-user","name":"Isolation User","email":"isolation@example.test"}]' \
  SMOKE_S3_BUCKET="phase2b1-private-images" \
  SMOKE_S3_ACCESS_KEY_ID="phase2b1minio" \
  SMOKE_S3_SECRET_ACCESS_KEY="synthetic_minio_${run_id}_secret" \
    docker compose --project-name "${project_name}" --file "${COMPOSE_FILE}" "$@"
}

cleanup() {
  compose_for "${RUN_A}" "${PROJECT_A}" 54801 down --volumes --remove-orphans >/dev/null 2>&1 || true
  compose_for "${RUN_B}" "${PROJECT_B}" 54802 down --volumes --remove-orphans >/dev/null 2>&1 || true
}
trap cleanup EXIT HUP INT TERM

compose_for "${RUN_A}" "${PROJECT_A}" 54801 up --detach --wait postgres &
pid_a=$!
compose_for "${RUN_B}" "${PROJECT_B}" 54802 up --detach --wait postgres &
pid_b=$!
wait "${pid_a}"
wait "${pid_b}"

container_a=$(compose_for "${RUN_A}" "${PROJECT_A}" 54801 ps --quiet postgres)
container_b=$(compose_for "${RUN_B}" "${PROJECT_B}" 54802 ps --quiet postgres)
if [ -z "${container_a}" ] || [ -z "${container_b}" ] || [ "${container_a}" = "${container_b}" ]; then
  echo "parallel attempts did not create distinct exact containers" >&2
  exit 1
fi

compose_for "${RUN_A}" "${PROJECT_A}" 54801 down --volumes --remove-orphans
if [ -z "$(compose_for "${RUN_B}" "${PROJECT_B}" 54802 ps --quiet postgres)" ]; then
  echo "cleanup for attempt A removed attempt B" >&2
  exit 1
fi
compose_for "${RUN_B}" "${PROJECT_B}" 54802 down --volumes --remove-orphans

if [ -n "$(compose_for "${RUN_A}" "${PROJECT_A}" 54801 ps --quiet)" ] \
  || [ -n "$(compose_for "${RUN_B}" "${PROJECT_B}" 54802 ps --quiet)" ]; then
  echo "attempt-specific cleanup left containers behind" >&2
  exit 1
fi

echo "attempt isolation validation: PASS"
