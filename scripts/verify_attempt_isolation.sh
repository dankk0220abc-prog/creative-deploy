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

PROJECT_A="creativedeploy-phase2a1-${RUN_A}"
PROJECT_B="creativedeploy-phase2a1-${RUN_B}"

compose_for() {
  run_id=$1
  project_name=$2
  shift 2
  database_id="phase2a1_${run_id}"
  SMOKE_RUN_ID="${run_id}" \
  SMOKE_DATABASE_USER="${database_id}" \
  SMOKE_DATABASE_PASSWORD="synthetic_${run_id}_password" \
  SMOKE_DATABASE_NAME="${database_id}" \
    docker compose --project-name "${project_name}" --file "${COMPOSE_FILE}" "$@"
}

cleanup() {
  compose_for "${RUN_A}" "${PROJECT_A}" down --volumes --remove-orphans >/dev/null 2>&1 || true
  compose_for "${RUN_B}" "${PROJECT_B}" down --volumes --remove-orphans >/dev/null 2>&1 || true
}
trap cleanup EXIT HUP INT TERM

compose_for "${RUN_A}" "${PROJECT_A}" up --detach --wait postgres &
pid_a=$!
compose_for "${RUN_B}" "${PROJECT_B}" up --detach --wait postgres &
pid_b=$!
wait "${pid_a}"
wait "${pid_b}"

container_a=$(compose_for "${RUN_A}" "${PROJECT_A}" ps --quiet postgres)
container_b=$(compose_for "${RUN_B}" "${PROJECT_B}" ps --quiet postgres)
if [ -z "${container_a}" ] || [ -z "${container_b}" ] || [ "${container_a}" = "${container_b}" ]; then
  echo "parallel attempts did not create distinct exact containers" >&2
  exit 1
fi

compose_for "${RUN_A}" "${PROJECT_A}" down --volumes --remove-orphans
if [ -z "$(compose_for "${RUN_B}" "${PROJECT_B}" ps --quiet postgres)" ]; then
  echo "cleanup for attempt A removed attempt B" >&2
  exit 1
fi
compose_for "${RUN_B}" "${PROJECT_B}" down --volumes --remove-orphans

if [ -n "$(compose_for "${RUN_A}" "${PROJECT_A}" ps --quiet)" ] \
  || [ -n "$(compose_for "${RUN_B}" "${PROJECT_B}" ps --quiet)" ]; then
  echo "attempt-specific cleanup left containers behind" >&2
  exit 1
fi

echo "attempt isolation validation: PASS"
