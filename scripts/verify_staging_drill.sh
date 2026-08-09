#!/bin/sh
set -eu

REPOSITORY_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
STAGING_DIAGNOSTIC_PYTHON_PROJECT="${REPOSITORY_ROOT}/apps/api"
export STAGING_DIAGNOSTIC_PYTHON_PROJECT
. "${REPOSITORY_ROOT}/scripts/staging_failure_diagnostics.sh"
RUN_ID=${RUN_ID:-local_$(date -u +%Y%m%d%H%M%S)}
if ! printf '%s\n' "${RUN_ID}" | grep -Eq '^[a-z0-9][a-z0-9_]{0,39}$'; then
  echo "RUN_ID must match ^[a-z0-9][a-z0-9_]{0,39}$" >&2
  exit 1
fi

RUN_STEM=$(printf '%s' "${RUN_ID}" | cut -c1-36)
SOURCE_RUN_ID="${RUN_STEM}_src"
RESTORE_RUN_ID="${RUN_STEM}_rst"
SOURCE_PROJECT="creativedeploy-phase2b2-${SOURCE_RUN_ID}"
RESTORE_PROJECT="creativedeploy-phase2b2-${RESTORE_RUN_ID}"
SOURCE_DATABASE="p2b2s_${SOURCE_RUN_ID}"
RESTORE_DATABASE="p2b2r_${RESTORE_RUN_ID}"
STAGING_HOST=localhost
BACKUP_ID="backup_${RUN_STEM}"
SIGNING_KEY_ID="p2b2-${RUN_STEM}-v1"
BUCKET="p2b2-private-$(printf '%s' "${RUN_STEM}" | tr '_' '-')"
OIDC_USERS='[{"subject":"owner-a","name":"Phase 2B-2 Owner A","email":"owner-a@example.test"},{"subject":"reviewer-c","name":"Phase 2B-2 Reviewer","email":"reviewer-c@example.test"}]'
SOURCE_COMMIT=$(git -C "${REPOSITORY_ROOT}" rev-parse HEAD)
TEMP_ROOT=$(mktemp -d "${TMPDIR:-/tmp}/creativedeploy-phase2b2-drill-${RUN_STEM}.XXXXXX")
SOURCE_SECRET_ROOT="${TEMP_ROOT}/source-secrets"
RESTORE_SECRET_ROOT="${TEMP_ROOT}/restore-secrets"
BACKUP_ROOT="${TEMP_ROOT}/backups"
OPERATIONS_UID=$(id -u)
OPERATIONS_GID=$(id -g)

source_down=0
restore_down=0
emit_failed_one_shot_logs() {
  project=$1
  source_secret_root=$2
  restore_secret_root=$3
  compose_command=$4
  for service in role_provision migrate role_grant; do
    container_id=$(${compose_command} ps --all --quiet "${service}" 2>/dev/null || true)
    if [ -z "${container_id}" ]; then
      continue
    fi
    exit_code=$(docker inspect --format '{{.State.ExitCode}}' "${container_id}" 2>/dev/null || true)
    if [ -z "${exit_code}" ] || [ "${exit_code}" = "0" ]; then
      continue
    fi
    log_path="${TEMP_ROOT}/${project}-${service}-failure.log"
    printf 'STAGING_ONE_SHOT_FAILURE project=%s service=%s exit_code=%s\n' \
      "${project}" "${service}" "${exit_code}" >&2
    run_with_staging_log_capture \
      "${log_path}" "${source_secret_root}" "${restore_secret_root}" -- \
      ${compose_command} logs --no-color "${service}" || true
  done
}

cleanup() {
  original_status=$?
  trap - EXIT HUP INT TERM
  set +eu
  if [ "${original_status}" != "0" ] && \
     command -v compose_restore >/dev/null 2>&1 && \
     command -v compose_source >/dev/null 2>&1; then
    emit_failed_one_shot_logs \
      "${RESTORE_PROJECT}" "${SOURCE_SECRET_ROOT}" "${RESTORE_SECRET_ROOT}" compose_restore
    emit_failed_one_shot_logs \
      "${SOURCE_PROJECT}" "${SOURCE_SECRET_ROOT}" "" compose_source
  fi
  if [ "${restore_down}" != "1" ] && command -v make_restore >/dev/null 2>&1; then
    make_restore staging-down >/dev/null 2>&1 || true
  fi
  if [ "${source_down}" != "1" ] && command -v make_source >/dev/null 2>&1; then
    make_source staging-down >/dev/null 2>&1 || true
  fi
  case "${TEMP_ROOT}" in
    "${TMPDIR:-/tmp}"/creativedeploy-phase2b2-drill-*)
      rm -rf -- "${TEMP_ROOT}" >/dev/null 2>&1 || true
      ;;
    *)
      echo "refusing to remove unexpected staging drill root" >&2
      ;;
  esac
  exit "${original_status}"
}
trap cleanup EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM

make_source() {
  make --no-print-directory -C "${REPOSITORY_ROOT}" "$@" \
    RUN_ID="${SOURCE_RUN_ID}" \
    STAGING_HOST="${STAGING_HOST}" \
    STAGING_HTTP_PORT="${STAGING_HTTP_PORT}" \
    STAGING_HTTPS_PORT="${STAGING_HTTPS_PORT}" \
    STAGING_SECRET_ROOT="${SOURCE_SECRET_ROOT}" \
    STAGING_BACKUP_ROOT="${BACKUP_ROOT}" \
    STAGING_OPERATIONS_UID="${OPERATIONS_UID}" \
    STAGING_OPERATIONS_GID="${OPERATIONS_GID}" \
    STAGING_BACKUP_READ_ONLY=false \
    STAGING_BACKUP_SIGNING_KEY_FILE="${SOURCE_SECRET_ROOT}/backup_signing_key" \
    STAGING_BACKUP_SIGNING_KEY_ID="${SIGNING_KEY_ID}" \
    STAGING_S3_BUCKET="${BUCKET}" \
    SOURCE_GIT_COMMIT="${SOURCE_COMMIT}"
}

make_restore() {
  make --no-print-directory -C "${REPOSITORY_ROOT}" "$@" \
    RUN_ID="${RESTORE_RUN_ID}" \
    STAGING_DATABASE_PREFIX=p2b2r \
    STAGING_HOST="${STAGING_HOST}" \
    STAGING_HTTP_PORT="${STAGING_HTTP_PORT}" \
    STAGING_HTTPS_PORT="${STAGING_HTTPS_PORT}" \
    STAGING_SECRET_ROOT="${RESTORE_SECRET_ROOT}" \
    STAGING_BACKUP_ROOT="${BACKUP_ROOT}" \
    STAGING_OPERATIONS_UID="${OPERATIONS_UID}" \
    STAGING_OPERATIONS_GID="${OPERATIONS_GID}" \
    STAGING_BACKUP_READ_ONLY=true \
    STAGING_BACKUP_SIGNING_KEY_FILE="${SOURCE_SECRET_ROOT}/backup_signing_key" \
    STAGING_BACKUP_SIGNING_KEY_ID="${SIGNING_KEY_ID}" \
    STAGING_S3_BUCKET="${BUCKET}" \
    SOURCE_GIT_COMMIT="${SOURCE_COMMIT}"
}

compose_source() {
  STAGING_RUN_ID="${SOURCE_RUN_ID}" \
  STAGING_HOST="${STAGING_HOST}" \
  STAGING_HTTP_PORT="${STAGING_HTTP_PORT}" \
  STAGING_HTTPS_PORT="${STAGING_HTTPS_PORT}" \
  STAGING_SECRET_ROOT="${SOURCE_SECRET_ROOT}" \
  STAGING_BACKUP_ROOT="${BACKUP_ROOT}" \
  STAGING_OPERATIONS_UID="${OPERATIONS_UID}" \
  STAGING_OPERATIONS_GID="${OPERATIONS_GID}" \
  STAGING_BACKUP_READ_ONLY=false \
  STAGING_BACKUP_SIGNING_KEY_FILE="${SOURCE_SECRET_ROOT}/backup_signing_key" \
  STAGING_BACKUP_SIGNING_KEY_ID="${SIGNING_KEY_ID}" \
  STAGING_DATABASE_NAME="${SOURCE_DATABASE}" \
  STAGING_DATABASE_ADMIN_USER="${SOURCE_DATABASE}_admin" \
  STAGING_DATABASE_MIGRATOR_USER="${SOURCE_DATABASE}_migrator" \
  STAGING_DATABASE_RUNTIME_USER="${SOURCE_DATABASE}_runtime" \
  STAGING_OIDC_CLIENT_ID=phase2b2-staging-client \
  STAGING_OIDC_USERS_JSON="${OIDC_USERS}" \
  STAGING_S3_BUCKET="${BUCKET}" \
  SOURCE_GIT_COMMIT="${SOURCE_COMMIT}" \
  docker compose --project-name "${SOURCE_PROJECT}" \
    --file "${REPOSITORY_ROOT}/compose.staging.yaml" "$@"
}

compose_restore() {
  STAGING_RUN_ID="${RESTORE_RUN_ID}" \
  STAGING_HOST="${STAGING_HOST}" \
  STAGING_HTTP_PORT="${STAGING_HTTP_PORT}" \
  STAGING_HTTPS_PORT="${STAGING_HTTPS_PORT}" \
  STAGING_SECRET_ROOT="${RESTORE_SECRET_ROOT}" \
  STAGING_BACKUP_ROOT="${BACKUP_ROOT}" \
  STAGING_OPERATIONS_UID="${OPERATIONS_UID}" \
  STAGING_OPERATIONS_GID="${OPERATIONS_GID}" \
  STAGING_BACKUP_READ_ONLY=true \
  STAGING_BACKUP_SIGNING_KEY_FILE="${SOURCE_SECRET_ROOT}/backup_signing_key" \
  STAGING_BACKUP_SIGNING_KEY_ID="${SIGNING_KEY_ID}" \
  STAGING_DATABASE_NAME="${RESTORE_DATABASE}" \
  STAGING_DATABASE_ADMIN_USER="${RESTORE_DATABASE}_admin" \
  STAGING_DATABASE_MIGRATOR_USER="${RESTORE_DATABASE}_migrator" \
  STAGING_DATABASE_RUNTIME_USER="${RESTORE_DATABASE}_runtime" \
  STAGING_OIDC_CLIENT_ID=phase2b2-staging-client \
  STAGING_OIDC_USERS_JSON="${OIDC_USERS}" \
  STAGING_S3_BUCKET="${BUCKET}" \
  SOURCE_GIT_COMMIT="${SOURCE_COMMIT}" \
  docker compose --project-name "${RESTORE_PROJECT}" \
    --file "${REPOSITORY_ROOT}/compose.staging.yaml" "$@"
}

prepare_attempt() {
  attempt_run_id=$1
  secret_root=$2
  database_name=$3
  backup_root=${4:-}
  set -- uv run --project "${REPOSITORY_ROOT}/apps/api" python \
    "${REPOSITORY_ROOT}/scripts/prepare_staging_attempt.py" \
    --run-id "${attempt_run_id}" \
    --secret-root "${secret_root}" \
    --host "${STAGING_HOST}" \
    --database-name "${database_name}" \
    --admin-user "${database_name}_admin" \
    --migrator-user "${database_name}_migrator" \
    --runtime-user "${database_name}_runtime"
  if [ -n "${backup_root}" ]; then
    set -- "$@" --backup-root "${backup_root}"
  fi
  "$@"
}

set -- $(/usr/bin/python3 -c '
import socket
ports=[]
for _ in range(2):
    sock=socket.socket()
    sock.bind(("127.0.0.1", 0))
    ports.append(sock.getsockname()[1])
    sock.close()
print(*ports)
')
STAGING_HTTP_PORT=$1
STAGING_HTTPS_PORT=$2
if [ "${STAGING_HTTP_PORT}" = "${STAGING_HTTPS_PORT}" ]; then
  echo "staging drill port allocation collided" >&2
  exit 1
fi
BASE_URL="https://${STAGING_HOST}:${STAGING_HTTPS_PORT}"

ACTIVE_CERT="${SOURCE_SECRET_ROOT}/tls_certificate.pem"
https_curl() {
  curl --cacert "${ACTIVE_CERT}" "$@"
}

header_value() {
  header_name=$1
  awk -v name="${header_name}" '
    index(tolower($0), tolower(name ":")) == 1 {
      sub(/^[^:]+:[[:space:]]*/, "")
      sub(/\r$/, "")
      print
      exit
    }
  ' "${TEMP_ROOT}/headers"
}

json_field() {
  json_path=$1
  field_name=$2
  uv run --project "${REPOSITORY_ROOT}/apps/api" python -c \
    'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))[sys.argv[2]])' \
    "${json_path}" "${field_name}"
}

json_user_id() {
  json_path=$1
  uv run --project "${REPOSITORY_ROOT}/apps/api" python -c \
    'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["user"]["id"])' \
    "${json_path}"
}

csrf_from_jar() {
  awk '$6 ~ /paintpilot_csrf$/ { print $7; exit }' "$1"
}

oidc_login() {
  subject=$1
  cookie_jar=$2
  session_output=$3
  https_curl --silent --show-error --cookie "${cookie_jar}" --cookie-jar "${cookie_jar}" \
    --dump-header "${TEMP_ROOT}/headers" --output /dev/null \
    "${BASE_URL}/api/v1/auth/login?return_to=%2Fpaintpilot%2Fprojects"
  authorize_url=$(header_value Location)
  case "${authorize_url}" in
    "${BASE_URL}"/authorize*) ;;
    *) echo "staging OIDC login returned an invalid authorization URL" >&2; exit 1 ;;
  esac
  https_curl --fail --silent --show-error --cookie "${cookie_jar}" \
    --cookie-jar "${cookie_jar}" --output "${TEMP_ROOT}/authorize.html" \
    "${authorize_url}"
  request_id=$(sed -n 's/.*name="request_id" value="\([^"]*\)".*/\1/p' \
    "${TEMP_ROOT}/authorize.html")
  oidc_csrf=$(sed -n 's/.*name="csrf_token" value="\([^"]*\)".*/\1/p' \
    "${TEMP_ROOT}/authorize.html")
  if [ -z "${request_id}" ] || [ -z "${oidc_csrf}" ]; then
    echo "staging OIDC authorization form is incomplete" >&2
    exit 1
  fi
  https_curl --silent --show-error --cookie "${cookie_jar}" \
    --cookie-jar "${cookie_jar}" --dump-header "${TEMP_ROOT}/headers" \
    --output /dev/null --request POST \
    --data-urlencode "request_id=${request_id}" \
    --data-urlencode "csrf_token=${oidc_csrf}" \
    --data-urlencode "subject=${subject}" "${BASE_URL}/authorize"
  callback_url=$(header_value Location)
  case "${callback_url}" in
    "${BASE_URL}/api/v1/auth/callback"*) ;;
    *) echo "staging OIDC authorization returned an invalid callback" >&2; exit 1 ;;
  esac
  callback_status=$(https_curl --silent --show-error --cookie "${cookie_jar}" \
    --cookie-jar "${cookie_jar}" --dump-header "${TEMP_ROOT}/headers" \
    --output /dev/null --write-out '%{http_code}' "${callback_url}")
  if [ "${callback_status}" != "303" ]; then
    echo "staging OIDC callback returned ${callback_status}, expected 303" >&2
    exit 1
  fi
  session_cookie_line=$(tr '[:upper:]' '[:lower:]' < "${TEMP_ROOT}/headers" | \
    grep '^set-cookie: __host-paintpilot_session=' || true)
  case "${session_cookie_line}" in
    *'; secure'*'; httponly'*'; samesite=lax'* | \
    *'; secure'*'; samesite=lax'*'; httponly'* | \
    *'; httponly'*'; secure'*'; samesite=lax'* | \
    *'; httponly'*'; samesite=lax'*'; secure'* | \
    *'; samesite=lax'*'; secure'*'; httponly'* | \
    *'; samesite=lax'*'; httponly'*'; secure'*) ;;
    *) echo "staging session cookie is missing production-style protections" >&2; exit 1 ;;
  esac
  https_curl --fail --silent --show-error --cookie "${cookie_jar}" \
    --output "${session_output}" "${BASE_URL}/api/v1/auth/session"
  grep -q '"authenticated":true' "${session_output}"
}

wait_ready() {
  attempt=0
  while [ "${attempt}" -lt 40 ]; do
    if https_curl --fail --silent --show-error --max-time 5 \
        "${BASE_URL}/health/ready" > /dev/null 2>&1; then
      return
    fi
    attempt=$((attempt + 1))
    sleep 1
  done
  echo "staging readiness did not recover" >&2
  exit 1
}

capture_safe_logs() {
  project=$1
  log_path=$2
  shift 2
  : > "${log_path}"
  for service in postgres minio oidc role_provision migrate role_grant api web tls_proxy; do
    docker logs "${project}-${service}-1" >> "${log_path}" 2>&1 || true
  done
  uv run --project "${REPOSITORY_ROOT}/apps/api" python -c '
from pathlib import Path
import sys
log_path = Path(sys.argv[1])
logs = log_path.read_text(encoding="utf-8", errors="replace")
for secret_root in map(Path, sys.argv[2:]):
    for path in secret_root.iterdir():
        if path.is_file():
            for token in path.read_text(encoding="utf-8", errors="replace").splitlines():
                if len(token) >= 12 and token in logs:
                    raise SystemExit("generated secret material appeared in staging logs")
if "do-not-log-query-marker" in logs:
    raise SystemExit("a query-string marker appeared in staging logs")
' "${log_path}" "$@"
}

echo "STAGING_STYLE_SYNTHETIC · NOT_REAL_PRODUCTION"
prepare_attempt \
  "${SOURCE_RUN_ID}" "${SOURCE_SECRET_ROOT}" "${SOURCE_DATABASE}" "${BACKUP_ROOT}"
make_source staging-up
wait_ready

redirect_location=$(curl --silent --show-error --head \
  "http://${STAGING_HOST}:${STAGING_HTTP_PORT}/paintpilot/projects/deep-link" | \
  awk 'tolower($1) == "location:" { sub(/\r$/, "", $2); print $2 }')
if [ "${redirect_location}" != "${BASE_URL}/paintpilot/projects/deep-link" ]; then
  echo "HTTP ingress did not produce the exact HTTPS redirect" >&2
  exit 1
fi
https_curl --fail --silent --show-error --header \
  'X-Request-ID: aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa' \
  --dump-header "${TEMP_ROOT}/headers" --output "${TEMP_ROOT}/ready.json" \
  "${BASE_URL}/health/ready"
request_header_count=$(awk 'tolower($1) == "x-request-id:" { count++ } END { print count+0 }' \
  "${TEMP_ROOT}/headers")
if [ "${request_header_count}" != "1" ] || \
   [ "$(header_value X-Request-ID)" != "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa" ]; then
  echo "staging correlation ID was not preserved exactly once" >&2
  exit 1
fi
grep -q '"database":{"status":"ok"' "${TEMP_ROOT}/ready.json"
grep -q '"storage":{"status":"ok"' "${TEMP_ROOT}/ready.json"
grep -q '"identity":{"status":"ok"' "${TEMP_ROOT}/ready.json"
grep -qi '^Strict-Transport-Security: max-age=86400' "${TEMP_ROOT}/headers"
wrong_host_status=$(curl --insecure --silent --show-error --header 'Host: invalid.example' \
  --output /dev/null --write-out '%{http_code}' "https://127.0.0.1:${STAGING_HTTPS_PORT}/")
if [ "${wrong_host_status}" != "400" ]; then
  echo "wrong staging Host returned ${wrong_host_status}, expected 400" >&2
  exit 1
fi
origin_status=$(https_curl --silent --show-error --request POST \
  --header 'Origin: https://invalid.example' --output /dev/null --write-out '%{http_code}' \
  "${BASE_URL}/api/v1/health/live")
if [ "${origin_status}" != "400" ]; then
  echo "wrong staging Origin returned ${origin_status}, expected 400" >&2
  exit 1
fi
if openssl s_client -connect "127.0.0.1:${STAGING_HTTPS_PORT}" -tls1_1 \
    < /dev/null 2>&1 | grep -q 'BEGIN CERTIFICATE'; then
  echo "TLS 1.1 unexpectedly completed a certificate handshake" >&2
  exit 1
fi
if ! openssl s_client -connect "127.0.0.1:${STAGING_HTTPS_PORT}" -tls1_2 \
    < /dev/null 2>&1 | grep -q 'BEGIN CERTIFICATE'; then
  echo "TLS 1.2 did not complete a certificate handshake" >&2
  exit 1
fi

OWNER_JAR="${TEMP_ROOT}/owner.cookies"
REVIEWER_JAR="${TEMP_ROOT}/reviewer.cookies"
oidc_login owner-a "${OWNER_JAR}" "${TEMP_ROOT}/owner-session.json"
owner_id=$(json_user_id "${TEMP_ROOT}/owner-session.json")
owner_csrf=$(csrf_from_jar "${OWNER_JAR}")
create_status=$(https_curl --silent --show-error --cookie "${OWNER_JAR}" \
  --output "${TEMP_ROOT}/project.json" --write-out '%{http_code}' --request POST \
  --header "Origin: ${BASE_URL}" --header 'Content-Type: application/json' \
  --header "X-CSRF-Token: ${owner_csrf}" --header "Idempotency-Key: $(uuidgen)" \
  --data '{"title":"Synthetic Phase 2B-2 staging recovery project"}' \
  "${BASE_URL}/api/v1/paint-projects")
if [ "${create_status}" != "201" ]; then
  echo "staging project create returned ${create_status}, expected 201" >&2
  exit 1
fi
project_id=$(json_field "${TEMP_ROOT}/project.json" id)
uv run --project "${REPOSITORY_ROOT}/apps/api" python -c \
  'from PIL import Image; import sys; Image.new("RGB",(768,768),"#345f73").save(sys.argv[1],"JPEG",quality=90)' \
  "${TEMP_ROOT}/primary.jpg"
upload_status=$(https_curl --silent --show-error --cookie "${OWNER_JAR}" \
  --output "${TEMP_ROOT}/image.json" --write-out '%{http_code}' --request POST \
  --header "Origin: ${BASE_URL}" --header "X-CSRF-Token: ${owner_csrf}" \
  --header "Idempotency-Key: $(uuidgen)" \
  --form "file=@${TEMP_ROOT}/primary.jpg;type=image/jpeg" \
  --form role=primary_front --form source_type=user_photographed \
  --form intended_usage=private_project --form rights_attestation_confirmed=true \
  --form rights_attestation_version=1 \
  "${BASE_URL}/api/v1/paint-projects/${project_id}/images")
if [ "${upload_status}" != "201" ]; then
  echo "staging private image upload returned ${upload_status}, expected 201" >&2
  exit 1
fi
image_id=$(json_field "${TEMP_ROOT}/image.json" id)
oidc_login reviewer-c "${REVIEWER_JAR}" "${TEMP_ROOT}/reviewer-session.json"
reviewer_id=$(json_user_id "${TEMP_ROOT}/reviewer-session.json")
membership_status=$(https_curl --silent --show-error --cookie "${OWNER_JAR}" \
  --output /dev/null --write-out '%{http_code}' --request PUT \
  --header "Origin: ${BASE_URL}" --header 'Content-Type: application/json' \
  --header "X-CSRF-Token: ${owner_csrf}" --data "{\"user_id\":\"${reviewer_id}\"}" \
  "${BASE_URL}/api/v1/paint-projects/${project_id}/memberships/${reviewer_id}")
if [ "${membership_status}" != "200" ]; then
  echo "staging reviewer assignment returned ${membership_status}, expected 200" >&2
  exit 1
fi
compose_source exec -T api python - seed "${owner_id}" "${project_id}" \
  < "${REPOSITORY_ROOT}/scripts/verify_phase3a_backup_rows.py"
compose_source exec -T api python - verify "${owner_id}" "${project_id}" \
  < "${REPOSITORY_ROOT}/scripts/verify_phase3a_backup_rows.py"
https_curl --fail --silent --show-error --cookie "${REVIEWER_JAR}" \
  --output "${TEMP_ROOT}/source-object.jpg" \
  "${BASE_URL}/api/v1/paint-projects/${project_id}/images/${image_id}/content"
source_object_sha=$(shasum -a 256 "${TEMP_ROOT}/source-object.jpg" | awk '{print $1}')

source_failure="${TEMP_ROOT}/backup-without-quiesce.raw.log"
set +e
run_with_staging_log_capture \
  "${source_failure}" "${SOURCE_SECRET_ROOT}" "" -- \
  compose_source --profile operations run --rm operations backup \
  --backup-id must_not_exist
failure_status=$?
set -e
if [ "${failure_status}" = "0" ] || \
   ! grep -q 'OPERATIONS_QUIESCED=true is required' "${source_failure}" || \
   [ -e "${BACKUP_ROOT}/must_not_exist" ]; then
  echo "non-quiesced backup did not fail closed" >&2
  exit 1
fi

docker stop "${SOURCE_PROJECT}-minio-1" >/dev/null
degraded_status=$(https_curl --silent --show-error --max-time 10 \
  --output "${TEMP_ROOT}/degraded.json" --write-out '%{http_code}' \
  "${BASE_URL}/health/ready")
live_status=$(https_curl --silent --show-error --max-time 5 \
  --output /dev/null --write-out '%{http_code}' "${BASE_URL}/health/live")
if [ "${degraded_status}" != "503" ] || [ "${live_status}" != "200" ] || \
   ! grep -q '"storage":{"status":"error"' "${TEMP_ROOT}/degraded.json"; then
  echo "storage fault did not produce bounded readiness degradation" >&2
  exit 1
fi
docker start "${SOURCE_PROJECT}-minio-1" >/dev/null
wait_ready

https_curl --fail --silent --show-error \
  "${BASE_URL}/health/live?probe=do-not-log-query-marker" >/dev/null
backup_started=$(date +%s)
run_with_staging_log_capture \
  "${TEMP_ROOT}/staging-backup.raw.log" "${SOURCE_SECRET_ROOT}" "" -- \
  make_source staging-backup BACKUP_ID="${BACKUP_ID}"
backup_finished=$(date +%s)
backup_seconds=$((backup_finished - backup_started))
wait_ready
uv run --project "${REPOSITORY_ROOT}/apps/api" python -c '
import json,sys
from pathlib import Path
root=Path(sys.argv[1])
manifest=json.loads((root/"manifest.json").read_text(encoding="utf-8"))
assert manifest["format"] == "creativedeploy-staging-backup-v1"
assert manifest["manifest_version"] == 1
assert manifest["alembic_revision"] == "3a04fab2e7a5"
assert manifest["backup_id"] == sys.argv[2]
assert manifest["object_count"] == 1
assert len(manifest["objects"]) == 1
assert manifest["authenticity"] == {
    "algorithm": "HMAC-SHA-256",
    "canonicalization": "json-sort-keys-compact-ascii-v1",
    "key_id": sys.argv[3],
    "signature_file": "manifest.hmac.json",
}
assert (root/"manifest.hmac.json").is_file()
assert manifest["table_counts"]["paint_projects"] == 1
assert manifest["table_counts"]["project_memberships"] == 1
assert manifest["table_counts"]["image_assets"] == 1
phase3a_counts={table:1 for table in (
    "provider_definitions",
    "capability_definitions",
    "model_definitions",
    "provider_capabilities",
    "model_capabilities",
    "credential_records",
    "credential_project_grants",
    "user_provider_preferences",
    "project_model_policies",
    "project_model_policy_providers",
    "project_model_policy_models",
    "project_model_policy_capabilities",
    "project_model_policy_credentials",
    "user_budget_policies",
    "project_budget_policies",
    "user_budget_counters",
    "project_budget_counters",
    "invocation_requests",
    "invocation_attempts",
    "budget_reservations",
    "ai_invocation_events",
    "ai_usage_ledger",
    "ai_cost_ledger",
    "ai_audit_events",
    "ai_command_idempotency_records",
)}
phase3a_counts.update({
    "capability_definitions":3,
    "model_definitions":2,
    "provider_capabilities":3,
    "model_capabilities":5,
    "credential_records":2,
    "invocation_attempts":2,
})
assert set(manifest["table_counts"]) == {
    "user_accounts", "external_identities", "paint_projects", "project_memberships",
    "oidc_login_flows", "auth_sessions", "state_transition_events",
    "command_idempotency_records", "image_assets", "image_set_readiness_reviews",
    "region_sets", "regions", "region_vertices", "region_set_reviews", *phase3a_counts,
}
assert {table:manifest["table_counts"][table] for table in phase3a_counts} == phase3a_counts
' "${BACKUP_ROOT}/${BACKUP_ID}" "${BACKUP_ID}" "${SIGNING_KEY_ID}"
capture_safe_logs "${SOURCE_PROJECT}" "${TEMP_ROOT}/source-services.log" \
  "${SOURCE_SECRET_ROOT}"

make_source staging-down >/dev/null
source_down=1
prepare_attempt "${RESTORE_RUN_ID}" "${RESTORE_SECRET_ROOT}" "${RESTORE_DATABASE}"
ACTIVE_CERT="${RESTORE_SECRET_ROOT}/tls_certificate.pem"
make_restore staging-up
wait_ready
restore_started=$(date +%s)
run_with_staging_log_capture \
  "${TEMP_ROOT}/staging-restore.raw.log" \
  "${SOURCE_SECRET_ROOT}" "${RESTORE_SECRET_ROOT}" -- \
  make_restore staging-restore BACKUP_ID="${BACKUP_ID}"
restore_finished=$(date +%s)
restore_seconds=$((restore_finished - restore_started))
wait_ready

# A second restore is an exact, resumable retry and must not duplicate state.
run_with_staging_log_capture \
  "${TEMP_ROOT}/staging-restore-retry.raw.log" \
  "${SOURCE_SECRET_ROOT}" "${RESTORE_SECRET_ROOT}" -- \
  make_restore staging-restore BACKUP_ID="${BACKUP_ID}"
wait_ready
compose_restore exec -T api python - verify "${owner_id}" "${project_id}" \
  < "${REPOSITORY_ROOT}/scripts/verify_phase3a_backup_rows.py"

# Deliberately alter only the isolated restore target object while retaining the
# signed size, content type, and metadata checksum. Run this before restored
# logins add session rows, so the database exact-retry precondition still holds.
tamper_raw_log="${TEMP_ROOT}/tampered-target.raw.log"
run_with_staging_log_capture \
  "${tamper_raw_log}" "${SOURCE_SECRET_ROOT}" "${RESTORE_SECRET_ROOT}" -- \
  compose_restore --profile operations run --rm --entrypoint python operations -c '
import hashlib,json,sys
from pathlib import Path
from creativedeploy_api.core.config import Settings
from creativedeploy_api.tools.staging_backup_restore import _s3_client
item=json.loads((Path("/backups")/sys.argv[1]/"objects.json").read_text(encoding="utf-8"))[0]
payload=b"x"*int(item["byte_size"])
if hashlib.sha256(payload).hexdigest()==item["sha256"]:
    payload=b"y"*int(item["byte_size"])
client,bucket=_s3_client(Settings.model_validate({}))
client.put_object(Bucket=bucket,Key=item["key"],Body=payload,ContentLength=len(payload),ContentType=item["content_type"],Metadata={"sha256":item["sha256"]})
response=client.get_object(Bucket=bucket,Key=item["key"])
observed=response["Body"].read()
response["Body"].close()
observed_sha=hashlib.sha256(observed).hexdigest()
if observed_sha != hashlib.sha256(payload).hexdigest():
    raise SystemExit("target tamper was not persisted")
if response.get("ContentLength") != item["byte_size"] or response.get("ContentType") != item["content_type"]:
    raise SystemExit("target tamper did not retain signed response facts")
if response.get("Metadata",{}).get("sha256") != item["sha256"]:
    raise SystemExit("target tamper did not retain signed checksum metadata")
print(observed_sha)
' "${BACKUP_ID}"
tampered_target_sha=$(tail -n 1 "${tamper_raw_log}")
if ! printf '%s' "${tampered_target_sha}" | grep -Eq '^[0-9a-f]{64}$' || \
   [ "${tampered_target_sha}" = "${source_object_sha}" ]; then
  echo "same-size target tamper precondition was not established" >&2
  exit 1
fi
docker stop "${RESTORE_PROJECT}-api-1" >/dev/null
set +e
byte_mismatch_log="${TEMP_ROOT}/byte-mismatch-restore.raw.log"
run_with_staging_log_capture \
  "${byte_mismatch_log}" "${SOURCE_SECRET_ROOT}" "${RESTORE_SECRET_ROOT}" -- \
  compose_restore --profile operations run --rm \
  --env OPERATIONS_QUIESCED=true --env RESTORE_TEMPORARY=true operations \
  restore --backup-id "${BACKUP_ID}" --dry-run
byte_mismatch_status=$?
set -e
if [ "${byte_mismatch_status}" = "0" ] || \
   ! grep -q 'private object byte checksum does not match' \
     "${byte_mismatch_log}"; then
  echo "same-size metadata-matched byte mismatch was not refused status=${byte_mismatch_status}" >&2
  exit 1
fi
run_with_staging_log_capture \
  "${TEMP_ROOT}/target-repair.raw.log" \
  "${SOURCE_SECRET_ROOT}" "${RESTORE_SECRET_ROOT}" -- \
  compose_restore --profile operations run --rm --entrypoint python operations -c '
import hashlib,json,sys
from pathlib import Path
from creativedeploy_api.core.config import Settings
from creativedeploy_api.tools.staging_backup_restore import _s3_client
root=Path("/backups")/sys.argv[1]
item=json.loads((root/"objects.json").read_text(encoding="utf-8"))[0]
client,bucket=_s3_client(Settings.model_validate({}))
response=client.get_object(Bucket=bucket,Key=item["key"])
tampered=response["Body"].read()
response["Body"].close()
if hashlib.sha256(tampered).hexdigest()!=sys.argv[2]:
    raise SystemExit("byte mismatch refusal changed the target object")
source=(root/"objects"/item["key"]).read_bytes()
if hashlib.sha256(source).hexdigest()!=item["sha256"]:
    raise SystemExit("backup object repair source is invalid")
client.put_object(Bucket=bucket,Key=item["key"],Body=source,ContentLength=len(source),ContentType=item["content_type"],Metadata={"sha256":item["sha256"]})
response=client.get_object(Bucket=bucket,Key=item["key"])
repaired=response["Body"].read()
response["Body"].close()
if hashlib.sha256(repaired).hexdigest()!=item["sha256"]:
    raise SystemExit("isolated target object repair failed")
' "${BACKUP_ID}" "${tampered_target_sha}"
docker start "${RESTORE_PROJECT}-api-1" >/dev/null
wait_ready

rm -f -- "${OWNER_JAR}" "${REVIEWER_JAR}"
oidc_login owner-a "${OWNER_JAR}" "${TEMP_ROOT}/restored-owner-session.json"
restored_owner_id=$(json_user_id "${TEMP_ROOT}/restored-owner-session.json")
oidc_login reviewer-c "${REVIEWER_JAR}" "${TEMP_ROOT}/restored-reviewer-session.json"
restored_reviewer_id=$(json_user_id "${TEMP_ROOT}/restored-reviewer-session.json")
if [ "${owner_id}" != "${restored_owner_id}" ] || \
   [ "${reviewer_id}" != "${restored_reviewer_id}" ]; then
  echo "restored OIDC identities did not preserve internal user IDs" >&2
  exit 1
fi
https_curl --fail --silent --show-error --cookie "${OWNER_JAR}" \
  "${BASE_URL}/api/v1/paint-projects/${project_id}" | grep -q '"access_role":"owner"'
https_curl --fail --silent --show-error --cookie "${REVIEWER_JAR}" \
  "${BASE_URL}/api/v1/paint-projects/${project_id}" | grep -q '"access_role":"reviewer"'
https_curl --fail --silent --show-error --cookie "${REVIEWER_JAR}" \
  --output "${TEMP_ROOT}/restored-object.jpg" \
  "${BASE_URL}/api/v1/paint-projects/${project_id}/images/${image_id}/content"
restored_object_sha=$(shasum -a 256 "${TEMP_ROOT}/restored-object.jpg" | awk '{print $1}')
if [ "${source_object_sha}" != "${restored_object_sha}" ]; then
  echo "restored private object bytes do not match the source" >&2
  exit 1
fi

BAD_BACKUP_ID="${BACKUP_ID}_tampered"
cp -R "${BACKUP_ROOT}/${BACKUP_ID}" "${BACKUP_ROOT}/${BAD_BACKUP_ID}"
truncate -s 1 "${BACKUP_ROOT}/${BAD_BACKUP_ID}/tables/paint_projects.csv"
docker stop "${RESTORE_PROJECT}-api-1" >/dev/null
set +e
tampered_restore_log="${TEMP_ROOT}/tampered-restore.raw.log"
run_with_staging_log_capture \
  "${tampered_restore_log}" "${SOURCE_SECRET_ROOT}" "${RESTORE_SECRET_ROOT}" -- \
  compose_restore --profile operations run --rm \
  --env OPERATIONS_QUIESCED=true --env RESTORE_TEMPORARY=true operations \
  restore --backup-id "${BAD_BACKUP_ID}" --dry-run
tampered_status=$?
set -e
docker start "${RESTORE_PROJECT}-api-1" >/dev/null
if [ "${tampered_status}" = "0" ] || \
   ! grep -q 'Backup file size or checksum validation failed' \
     "${tampered_restore_log}"; then
  echo "tampered backup did not fail checksum validation" >&2
  exit 1
fi
wait_ready
https_curl --fail --silent --show-error --cookie "${REVIEWER_JAR}" \
  --output "${TEMP_ROOT}/post-refusal-object.jpg" \
  "${BASE_URL}/api/v1/paint-projects/${project_id}/images/${image_id}/content"
if [ "$(shasum -a 256 "${TEMP_ROOT}/post-refusal-object.jpg" | awk '{print $1}')" != \
     "${source_object_sha}" ]; then
  echo "tampered restore refusal changed restored private data" >&2
  exit 1
fi

BAD_MANIFEST_ID="${BACKUP_ID}_manifest_tampered"
cp -R "${BACKUP_ROOT}/${BACKUP_ID}" "${BACKUP_ROOT}/${BAD_MANIFEST_ID}"
uv run --project "${REPOSITORY_ROOT}/apps/api" python -c '
import json,sys
from pathlib import Path
path=Path(sys.argv[1])/"manifest.json"
manifest=json.loads(path.read_text(encoding="utf-8"))
manifest["source_commit"]="tampered-manifest-field"
path.write_text(json.dumps(manifest,sort_keys=True)+"\n",encoding="utf-8")
' "${BACKUP_ROOT}/${BAD_MANIFEST_ID}"
docker stop "${RESTORE_PROJECT}-api-1" >/dev/null
set +e
manifest_tampered_log="${TEMP_ROOT}/manifest-tampered-restore.raw.log"
run_with_staging_log_capture \
  "${manifest_tampered_log}" "${SOURCE_SECRET_ROOT}" "${RESTORE_SECRET_ROOT}" -- \
  compose_restore --profile operations run --rm \
  --env OPERATIONS_QUIESCED=true --env RESTORE_TEMPORARY=true operations \
  restore --backup-id "${BAD_MANIFEST_ID}" --dry-run
manifest_tampered_status=$?
set -e
docker start "${RESTORE_PROJECT}-api-1" >/dev/null
if [ "${manifest_tampered_status}" = "0" ] || \
   ! grep -q 'Backup manifest authenticity verification failed' \
     "${manifest_tampered_log}"; then
  echo "tampered manifest did not fail detached authenticity verification" >&2
  exit 1
fi
wait_ready
https_curl --fail --silent --show-error --cookie "${REVIEWER_JAR}" \
  --output "${TEMP_ROOT}/post-manifest-refusal-object.jpg" \
  "${BASE_URL}/api/v1/paint-projects/${project_id}/images/${image_id}/content"
if [ "$(shasum -a 256 "${TEMP_ROOT}/post-manifest-refusal-object.jpg" | awk '{print $1}')" != \
     "${source_object_sha}" ]; then
  echo "manifest authenticity refusal changed restored private data" >&2
  exit 1
fi

capture_safe_logs "${RESTORE_PROJECT}" "${TEMP_ROOT}/restore-services.log" \
  "${RESTORE_SECRET_ROOT}" "${SOURCE_SECRET_ROOT}"
make_restore staging-down >/dev/null
restore_down=1

echo "STAGING_DRILL_PASS backup_format=creativedeploy-staging-backup-v1"
echo "STAGING_DRILL_METRICS backup_seconds=${backup_seconds} restore_seconds=${restore_seconds} synthetic_rpo_seconds=0"
echo "STAGING_DRILL_PROOFS https=pass tls_policy=pass exact_host_origin=pass file_secrets=pass structured_logs=pass"
echo "STAGING_DRILL_PROOFS backup=pass detached_authenticity=pass restore=pass exact_retry=pass checksum_refusal=pass manifest_tamper_refusal=pass byte_mismatch_refusal=pass private_object=pass permissions=pass phase3a_data=pass"
echo "STAGING_DRILL_CLEANUP source=removed restore=removed temporary_evidence=scheduled"
