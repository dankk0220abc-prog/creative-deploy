#!/bin/sh
set -eu

REPOSITORY_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
COMPOSE_FILE="${REPOSITORY_ROOT}/compose.artifact-smoke.yaml"
RUN_ID="${RUN_ID:-local_$(date -u +%Y%m%d%H%M%S)_$(uuidgen | tr '[:upper:]' '[:lower:]' | tr -d '-' | cut -c1-12)}"
if ! printf '%s\n' "${RUN_ID}" | grep -Eq '^[a-z0-9][a-z0-9_]{0,39}$'; then
  echo "RUN_ID must match ^[a-z0-9][a-z0-9_]{0,39}$" >&2
  exit 1
fi
PROJECT_NAME="creativedeploy-phase2a1-${RUN_ID}"
SMOKE_DATABASE_ID="phase2a1_${RUN_ID}"
export SMOKE_RUN_ID="${RUN_ID}"
export SMOKE_DATABASE_USER="${SMOKE_DATABASE_ID}"
export SMOKE_DATABASE_PASSWORD="synthetic_${RUN_ID}_password"
export SMOKE_DATABASE_NAME="${SMOKE_DATABASE_ID}"
TEMP_ROOT=$(mktemp -d "${TMPDIR:-/tmp}/creativedeploy-phase2a1-smoke-${RUN_ID}.XXXXXX")

cleanup() {
  docker compose --project-name "${PROJECT_NAME}" --file "${COMPOSE_FILE}" \
    down --volumes --remove-orphans --rmi local >/dev/null 2>&1 || true
  rm -rf -- "${TEMP_ROOT}"
}
trap cleanup EXIT HUP INT TERM

assert_header() {
  header_name=$1
  expected=$2
  if ! awk -v name="${header_name}" -v expected="${expected}" '
    BEGIN { IGNORECASE = 1; found = 0 }
    index($0, name ":") == 1 && index(tolower($0), tolower(expected)) > 0 { found = 1 }
    END { exit found ? 0 : 1 }
  ' "${TEMP_ROOT}/headers"; then
    echo "missing or incorrect response header: ${header_name} (${expected})" >&2
    exit 1
  fi
}

echo "LOCAL_PRODUCTION_STYLE_SMOKE · NOT_REAL_PRODUCTION"
docker compose --project-name "${PROJECT_NAME}" --file "${COMPOSE_FILE}" \
  up --detach --no-build --wait
published_endpoint=$(docker compose --project-name "${PROJECT_NAME}" \
  --file "${COMPOSE_FILE}" port web 8080)
SMOKE_PORT=${published_endpoint##*:}
case "${SMOKE_PORT}" in
  *[!0-9]* | "")
    echo "dynamic smoke port could not be resolved" >&2
    exit 1
    ;;
esac
BASE_URL="http://127.0.0.1:${SMOKE_PORT}"

curl --fail --silent --show-error --dump-header "${TEMP_ROOT}/headers" \
  --output "${TEMP_ROOT}/index.html" "${BASE_URL}/"
assert_header "Cache-Control" "no-store"
assert_header "Content-Security-Policy" "default-src 'self'"
assert_header "Content-Security-Policy" "frame-ancestors 'none'"
assert_header "X-Content-Type-Options" "nosniff"
assert_header "Referrer-Policy" "no-referrer"
assert_header "X-Frame-Options" "DENY"
assert_header "Permissions-Policy" "camera=()"
if grep -qi '^Strict-Transport-Security:' "${TEMP_ROOT}/headers"; then
  echo "HSTS must not be emitted by the HTTP-only smoke artifact" >&2
  exit 1
fi

curl --fail --silent --show-error "${BASE_URL}/health/live" \
  | grep -q '"service":"creativedeploy-web-proxy"'
curl --fail --silent --show-error "${BASE_URL}/health/ready" \
  | grep -q '"database":{"status":"ok"'
curl --fail --silent --show-error --dump-header "${TEMP_ROOT}/headers" \
  --output "${TEMP_ROOT}/projects.json" "${BASE_URL}/api/v1/paint-projects"
assert_header "Cache-Control" "no-store"
not_found_status=$(curl --silent --show-error --dump-header "${TEMP_ROOT}/headers" \
  --output "${TEMP_ROOT}/not-found.json" --write-out '%{http_code}' \
  "${BASE_URL}/api/v1/paint-projects/00000000-0000-4000-8000-000000000001")
if [ "${not_found_status}" != "404" ]; then
  echo "API not-found returned ${not_found_status}, expected 404" >&2
  exit 1
fi
assert_header "Cache-Control" "no-store"
create_status=$(curl --silent --show-error --dump-header "${TEMP_ROOT}/headers" \
  --output "${TEMP_ROOT}/created-project.json" --write-out '%{http_code}' \
  --request POST --header "Content-Type: application/json" \
  --header "Idempotency-Key: $(uuidgen)" \
  --data '{"title":"Synthetic artifact smoke project"}' \
  "${BASE_URL}/api/v1/paint-projects")
if [ "${create_status}" != "201" ]; then
  echo "API create returned ${create_status}, expected 201" >&2
  exit 1
fi
assert_header "Cache-Control" "no-store"
validation_status=$(curl --silent --show-error --dump-header "${TEMP_ROOT}/headers" \
  --output "${TEMP_ROOT}/validation.json" --write-out '%{http_code}' \
  --request POST --header "Content-Type: application/json" \
  --data '{"title":""}' "${BASE_URL}/api/v1/paint-projects")
if [ "${validation_status}" != "422" ]; then
  echo "API validation returned ${validation_status}, expected 422" >&2
  exit 1
fi
assert_header "Cache-Control" "no-store"
curl --fail --silent --show-error \
  "${BASE_URL}/paintpilot/projects/00000000-0000-4000-8000-000000000001/regions?version=1" \
  | grep -q '<div id="root"></div>'

asset_path=$(grep -Eo 'src="[^"]*/assets/[^"]+\.js"' \
  "${TEMP_ROOT}/index.html" | head -n 1 | cut -d '"' -f 2)
if [ -z "${asset_path}" ]; then
  echo "hashed JavaScript asset was not found in index.html" >&2
  exit 1
fi
curl --fail --silent --show-error --dump-header "${TEMP_ROOT}/asset-headers" \
  --output /dev/null "${BASE_URL}${asset_path}"
cp "${TEMP_ROOT}/asset-headers" "${TEMP_ROOT}/headers"
assert_header "Cache-Control" "max-age=31536000, immutable"

api_uid=$(docker compose --project-name "${PROJECT_NAME}" --file "${COMPOSE_FILE}" \
  exec -T api id -u)
web_uid=$(docker compose --project-name "${PROJECT_NAME}" --file "${COMPOSE_FILE}" \
  exec -T web id -u)
if [ "${api_uid}" = "0" ] || [ "${web_uid}" = "0" ]; then
  echo "artifact container unexpectedly runs as root" >&2
  exit 1
fi
docker compose --project-name "${PROJECT_NAME}" --file "${COMPOSE_FILE}" exec -T api \
  python -c "import importlib.util; assert importlib.util.find_spec('pytest') is None"
docker compose --project-name "${PROJECT_NAME}" --file "${COMPOSE_FILE}" exec -T api \
  sh -c 'test ! -e /app/.env && test ! -e /app/tests && test ! -e /app/src'
docker compose --project-name "${PROJECT_NAME}" --file "${COMPOSE_FILE}" run \
  --rm --no-deps --entrypoint python migrate -c \
  "import importlib.util as i; assert i.find_spec('alembic'); assert i.find_spec('psycopg'); assert i.find_spec('pytest') is None; assert i.find_spec('pip_audit') is None; assert i.find_spec('ruff') is None; assert i.find_spec('mypy') is None"

oversized_status=$(
  head -c 21037057 /dev/zero \
    | curl --silent --show-error --dump-header "${TEMP_ROOT}/headers" \
      --output /dev/null --write-out '%{http_code}' \
      --request POST --header 'Content-Type: application/octet-stream' \
      --data-binary @- "${BASE_URL}/api/v1/paint-projects"
)
if [ "${oversized_status}" != "413" ]; then
  echo "oversized request returned ${oversized_status}, expected 413" >&2
  exit 1
fi
assert_header "Cache-Control" "no-store"

unknown_host_status=$(curl --silent --dump-header "${TEMP_ROOT}/headers" \
  --output /dev/null --write-out '%{http_code}' \
  --header 'Host: untrusted.invalid' "${BASE_URL}/")
if [ "${unknown_host_status}" != "400" ]; then
  echo "unknown Host was not rejected at the default server boundary" >&2
  exit 1
fi
assert_header "Cache-Control" "no-store"

if docker compose --project-name "${PROJECT_NAME}" --file "${COMPOSE_FILE}" run \
  --rm --no-deps --env APP_ENV=production \
  --env POSTGRES_HOST=postgres --env POSTGRES_PORT=5432 \
  --env POSTGRES_USER="${SMOKE_DATABASE_USER}" \
  --env POSTGRES_PASSWORD="${SMOKE_DATABASE_PASSWORD}" \
  --env POSTGRES_DB="${SMOKE_DATABASE_NAME}" api \
  sh -c 'unset DATABASE_URL; exec python -c "import creativedeploy_api.main"' \
  >"${TEMP_ROOT}/production.out" 2>&1; then
  echo "production startup unexpectedly accepted POSTGRES_* without DATABASE_URL" >&2
  exit 1
fi
if ! grep -q 'Production requires an explicitly provided DATABASE_URL' \
  "${TEMP_ROOT}/production.out"; then
  echo "production startup failed without the expected DATABASE_URL policy message" >&2
  exit 1
fi

docker compose --project-name "${PROJECT_NAME}" --file "${COMPOSE_FILE}" stop postgres
degraded_status=$(curl --silent --show-error --output "${TEMP_ROOT}/degraded.json" \
  --write-out '%{http_code}' "${BASE_URL}/health/ready")
if [ "${degraded_status}" != "503" ]; then
  echo "readiness returned ${degraded_status} after PostgreSQL stopped, expected 503" >&2
  exit 1
fi
curl --fail --silent --show-error "${BASE_URL}/health/live" \
  | grep -q '"status":"ok"'
docker compose --project-name "${PROJECT_NAME}" --file "${COMPOSE_FILE}" \
  up --detach --wait postgres

echo "artifact smoke validation: PASS"
