#!/bin/sh
set -eu

REPOSITORY_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
COMPOSE_FILE="${REPOSITORY_ROOT}/compose.artifact-smoke.yaml"
RUN_ID="${RUN_ID:-local_$(date -u +%Y%m%d%H%M%S)_$(uuidgen | tr '[:upper:]' '[:lower:]' | tr -d '-' | cut -c1-12)}"
if ! printf '%s\n' "${RUN_ID}" | grep -Eq '^[a-z0-9][a-z0-9_]{0,39}$'; then
  echo "RUN_ID must match ^[a-z0-9][a-z0-9_]{0,39}$" >&2
  exit 1
fi
if [ -z "${ARTIFACT_SMOKE_PORT:-}" ]; then
  ARTIFACT_SMOKE_PORT=$(
    /usr/bin/python3 -c \
      'import socket; s=socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1]); s.close()'
  )
fi
case "${ARTIFACT_SMOKE_PORT}" in
  *[!0-9]* | "")
    echo "ARTIFACT_SMOKE_PORT must be numeric" >&2
    exit 1
    ;;
esac

PROJECT_NAME="creativedeploy-phase2b1-${RUN_ID}"
SMOKE_DATABASE_ID="phase2b1_${RUN_ID}"
export ARTIFACT_SMOKE_PORT
export SMOKE_RUN_ID="${RUN_ID}"
export SMOKE_DATABASE_ADMIN_USER="${SMOKE_DATABASE_ID}_admin"
export SMOKE_DATABASE_ADMIN_PASSWORD="synthetic_admin_${RUN_ID}_password"
export SMOKE_DATABASE_MIGRATOR_USER="${SMOKE_DATABASE_ID}_migrator"
export SMOKE_DATABASE_MIGRATOR_PASSWORD="synthetic_migrator_${RUN_ID}_password"
export SMOKE_DATABASE_RUNTIME_USER="${SMOKE_DATABASE_ID}_runtime"
export SMOKE_DATABASE_RUNTIME_PASSWORD="synthetic_runtime_${RUN_ID}_password"
export SMOKE_DATABASE_NAME="${SMOKE_DATABASE_ID}"
export SMOKE_OIDC_CLIENT_ID="phase2b1-smoke-client"
export SMOKE_OIDC_CLIENT_SECRET="synthetic_oidc_${RUN_ID}_secret"
export SMOKE_OIDC_USERS_JSON='[{"subject":"owner-a","name":"Phase 2B-1 Owner A","email":"owner-a@example.test"},{"subject":"owner-b","name":"Phase 2B-1 Owner B","email":"owner-b@example.test"},{"subject":"reviewer-c","name":"Phase 2B-1 Reviewer","email":"reviewer-c@example.test"}]'
export SMOKE_S3_BUCKET="phase2b1-private-images"
export SMOKE_S3_ACCESS_KEY_ID="phase2b1minio"
export SMOKE_S3_SECRET_ACCESS_KEY="synthetic_minio_${RUN_ID}_secret"

TEMP_ROOT=$(mktemp -d "${TMPDIR:-/tmp}/creativedeploy-phase2b1-smoke-${RUN_ID}.XXXXXX")
BASE_URL="http://127.0.0.1:${ARTIFACT_SMOKE_PORT}"

cleanup() {
  if [ "${KEEP_SMOKE_ON_FAILURE:-0}" = "1" ]; then
    echo "diagnostic smoke resources retained for ${PROJECT_NAME}" >&2
    return
  fi
  docker compose --project-name "${PROJECT_NAME}" --file "${COMPOSE_FILE}" \
    down --volumes --remove-orphans --rmi local >/dev/null 2>&1 || true
  rm -rf -- "${TEMP_ROOT}"
}
trap cleanup EXIT HUP INT TERM

assert_header() {
  header_name=$1
  expected=$2
  if ! awk -v name="${header_name}" -v expected="${expected}" '
    BEGIN { found = 0 }
    index(tolower($0), tolower(name ":")) == 1 &&
      index(tolower($0), tolower(expected)) > 0 { found = 1 }
    END { exit found ? 0 : 1 }
  ' "${TEMP_ROOT}/headers"; then
    echo "missing or incorrect response header: ${header_name} (${expected})" >&2
    exit 1
  fi
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

oidc_login() {
  subject=$1
  cookie_jar=$2
  session_output=$3
  curl --silent --show-error --cookie "${cookie_jar}" --cookie-jar "${cookie_jar}" \
    --dump-header "${TEMP_ROOT}/headers" --output /dev/null \
    "${BASE_URL}/api/v1/auth/login?return_to=%2Fpaintpilot%2Fprojects"
  authorize_url=$(header_value "Location")
  if [ -z "${authorize_url}" ]; then
    echo "OIDC login did not return an authorization redirect" >&2
    exit 1
  fi
  curl --fail --silent --show-error --cookie "${cookie_jar}" \
    --cookie-jar "${cookie_jar}" --output "${TEMP_ROOT}/authorize.html" \
    "${authorize_url}"
  request_id=$(sed -n 's/.*name="request_id" value="\([^"]*\)".*/\1/p' \
    "${TEMP_ROOT}/authorize.html")
  oidc_csrf=$(sed -n 's/.*name="csrf_token" value="\([^"]*\)".*/\1/p' \
    "${TEMP_ROOT}/authorize.html")
  if [ -z "${request_id}" ] || [ -z "${oidc_csrf}" ]; then
    echo "OIDC authorization form did not contain its one-time bindings" >&2
    exit 1
  fi
  curl --silent --show-error --cookie "${cookie_jar}" --cookie-jar "${cookie_jar}" \
    --dump-header "${TEMP_ROOT}/headers" --output /dev/null \
    --request POST \
    --data-urlencode "request_id=${request_id}" \
    --data-urlencode "csrf_token=${oidc_csrf}" \
    --data-urlencode "subject=${subject}" \
    "${BASE_URL}/authorize"
  callback_url=$(header_value "Location")
  if [ -z "${callback_url}" ]; then
    echo "OIDC authorization did not return a callback redirect" >&2
    exit 1
  fi
  callback_status=$(curl --silent --show-error --cookie "${cookie_jar}" \
    --cookie-jar "${cookie_jar}" --dump-header "${TEMP_ROOT}/headers" \
    --output "${TEMP_ROOT}/callback.json" --write-out '%{http_code}' "${callback_url}")
  callback_return=$(header_value "Location")
  case "${callback_return}" in
    "/paintpilot/projects" | "${BASE_URL}/paintpilot/projects")
      ;;
    *)
      echo "OIDC callback returned ${callback_status} without the governed return route" >&2
      sed -n '1,20p' "${TEMP_ROOT}/headers" >&2
      sed -n '1,20p' "${TEMP_ROOT}/callback.json" >&2
      exit 1
      ;;
  esac
  replay_status=$(curl --silent --show-error --cookie "${cookie_jar}" \
    --output /dev/null --write-out '%{http_code}' "${callback_url}")
  if [ "${replay_status}" != "400" ]; then
    echo "OIDC callback replay returned ${replay_status}, expected 400" >&2
    exit 1
  fi
  curl --fail --silent --show-error --cookie "${cookie_jar}" \
    --output "${session_output}" "${BASE_URL}/api/v1/auth/session"
  grep -q '"authenticated":true' "${session_output}"
}

csrf_from_jar() {
  awk '$6 == "paintpilot_csrf" { print $7; exit }' "$1"
}

echo "LOCAL_PRODUCTION_STYLE_SMOKE · NOT_REAL_PRODUCTION"
docker compose --project-name "${PROJECT_NAME}" --file "${COMPOSE_FILE}" \
  up --detach --build --wait

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

anonymous_status=$(curl --silent --show-error --output /dev/null --write-out '%{http_code}' \
  "${BASE_URL}/api/v1/paint-projects")
if [ "${anonymous_status}" != "401" ]; then
  echo "anonymous project access returned ${anonymous_status}, expected 401" >&2
  exit 1
fi

OWNER_JAR="${TEMP_ROOT}/owner.cookies"
OLD_OWNER_JAR="${TEMP_ROOT}/old-owner.cookies"
OWNER_B_JAR="${TEMP_ROOT}/owner-b.cookies"
REVIEWER_JAR="${TEMP_ROOT}/reviewer.cookies"
oidc_login "owner-a" "${OWNER_JAR}" "${TEMP_ROOT}/owner-session.json"
owner_id=$(uv run --project "${REPOSITORY_ROOT}/apps/api" python -c \
  'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["user"]["id"])' \
  "${TEMP_ROOT}/owner-session.json")
cp "${OWNER_JAR}" "${OLD_OWNER_JAR}"
oidc_login "owner-a" "${OWNER_JAR}" "${TEMP_ROOT}/owner-session-rotated.json"
rotated_owner_id=$(uv run --project "${REPOSITORY_ROOT}/apps/api" python -c \
  'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["user"]["id"])' \
  "${TEMP_ROOT}/owner-session-rotated.json")
if [ "${owner_id}" != "${rotated_owner_id}" ]; then
  echo "stable issuer+subject produced a different internal user ID" >&2
  exit 1
fi
curl --fail --silent --show-error --cookie "${OLD_OWNER_JAR}" \
  "${BASE_URL}/api/v1/auth/session" | grep -q '"authenticated":false'
owner_csrf=$(csrf_from_jar "${OWNER_JAR}")
if [ -z "${owner_csrf}" ]; then
  echo "OIDC callback did not issue the bound CSRF cookie" >&2
  exit 1
fi

missing_csrf_status=$(curl --silent --show-error --cookie "${OWNER_JAR}" \
  --output /dev/null --write-out '%{http_code}' \
  --request POST --header "Content-Type: application/json" \
  --header "Idempotency-Key: $(uuidgen)" \
  --data '{"title":"CSRF refusal probe"}' \
  "${BASE_URL}/api/v1/paint-projects")
if [ "${missing_csrf_status}" != "403" ]; then
  echo "missing CSRF returned ${missing_csrf_status}, expected 403" >&2
  exit 1
fi

create_status=$(curl --silent --show-error --cookie "${OWNER_JAR}" \
  --dump-header "${TEMP_ROOT}/headers" \
  --output "${TEMP_ROOT}/created-project.json" --write-out '%{http_code}' \
  --request POST --header "Content-Type: application/json" \
  --header "X-CSRF-Token: ${owner_csrf}" \
  --header "Idempotency-Key: $(uuidgen)" \
  --data '{"title":"Synthetic Phase 2B-1 smoke project"}' \
  "${BASE_URL}/api/v1/paint-projects")
if [ "${create_status}" != "201" ]; then
  echo "authorized project create returned ${create_status}, expected 201" >&2
  exit 1
fi
assert_header "Cache-Control" "no-store"
project_id=$(json_field "${TEMP_ROOT}/created-project.json" "id")

uv run --project "${REPOSITORY_ROOT}/apps/api" python -c \
  'from PIL import Image; import sys; Image.new("RGB",(768,768),"#345f73").save(sys.argv[1],"JPEG",quality=90)' \
  "${TEMP_ROOT}/primary.jpg"
upload_status=$(curl --silent --show-error --cookie "${OWNER_JAR}" \
  --output "${TEMP_ROOT}/created-image.json" --write-out '%{http_code}' \
  --request POST --header "X-CSRF-Token: ${owner_csrf}" \
  --header "Idempotency-Key: $(uuidgen)" \
  --form "file=@${TEMP_ROOT}/primary.jpg;type=image/jpeg" \
  --form "role=primary_front" \
  --form "source_type=user_photographed" \
  --form "intended_usage=private_project" \
  --form "rights_attestation_confirmed=true" \
  --form "rights_attestation_version=1" \
  "${BASE_URL}/api/v1/paint-projects/${project_id}/images")
if [ "${upload_status}" != "201" ]; then
  echo "private S3 upload returned ${upload_status}, expected 201" >&2
  exit 1
fi
if grep -Eqi 'minio|s3|storage_key|presign|X-Amz-' "${TEMP_ROOT}/created-image.json"; then
  echo "image response exposed storage-provider details" >&2
  exit 1
fi
image_id=$(json_field "${TEMP_ROOT}/created-image.json" "id")
for image_role in reference_back reference_angle; do
  case "${image_role}" in
    reference_back)
      image_color="#6c4f7d"
      ;;
    reference_angle)
      image_color="#8a6b35"
      ;;
  esac
  uv run --project "${REPOSITORY_ROOT}/apps/api" python -c \
    'from PIL import Image; import sys; Image.new("RGB",(768,768),sys.argv[2]).save(sys.argv[1],"JPEG",quality=90)' \
    "${TEMP_ROOT}/${image_role}.jpg" "${image_color}"
  role_upload_status=$(curl --silent --show-error --cookie "${OWNER_JAR}" \
    --output "${TEMP_ROOT}/${image_role}.json" --write-out '%{http_code}' \
    --request POST --header "X-CSRF-Token: ${owner_csrf}" \
    --header "Idempotency-Key: $(uuidgen)" \
    --form "file=@${TEMP_ROOT}/${image_role}.jpg;type=image/jpeg" \
    --form "role=${image_role}" \
    --form "source_type=user_photographed" \
    --form "intended_usage=private_project" \
    --form "rights_attestation_confirmed=true" \
    --form "rights_attestation_version=1" \
    "${BASE_URL}/api/v1/paint-projects/${project_id}/images")
  if [ "${role_upload_status}" != "201" ]; then
    echo "${image_role} private S3 upload returned ${role_upload_status}, expected 201" >&2
    exit 1
  fi
done
curl --fail --silent --show-error --cookie "${OWNER_JAR}" \
  --output "${TEMP_ROOT}/streamed-primary.jpg" \
  "${BASE_URL}/api/v1/paint-projects/${project_id}/images/${image_id}/content"
if [ "$(shasum -a 256 "${TEMP_ROOT}/primary.jpg" | awk '{print $1}')" != \
  "$(shasum -a 256 "${TEMP_ROOT}/streamed-primary.jpg" | awk '{print $1}')" ]; then
  echo "API-streamed private object did not match uploaded bytes" >&2
  exit 1
fi
if docker compose --project-name "${PROJECT_NAME}" --file "${COMPOSE_FILE}" exec -T api \
  python -c \
  "import urllib.request; urllib.request.urlopen('http://minio:9000/${SMOKE_S3_BUCKET}/', timeout=2)" \
  >"${TEMP_ROOT}/public-bucket.out" 2>&1; then
  echo "unauthenticated direct bucket access unexpectedly succeeded" >&2
  exit 1
fi
grep -Eq 'HTTP Error (401|403)' "${TEMP_ROOT}/public-bucket.out"

docker compose --project-name "${PROJECT_NAME}" --file "${COMPOSE_FILE}" exec -T api \
  python - <<'PY'
import hashlib
import io

from creativedeploy_api.core.config import Settings
from creativedeploy_api.storage.s3 import S3ImageStorageAdapter

settings = Settings.model_validate({})
endpoint, region, bucket, access_key, secret_key, staging_root = (
    settings.require_s3_image_storage()
)
storage = S3ImageStorageAdapter(
    endpoint_url=endpoint,
    region=region,
    bucket=bucket,
    access_key_id=access_key,
    secret_access_key=secret_key,
    force_path_style=settings.s3_force_path_style,
    staging_root=staging_root,
    create_bucket=False,
)
payload = b"synthetic legacy copy post-write verification"
checksum = hashlib.sha256(payload).hexdigest()
key = "objects/fa/fafafafafafafafafafafafafafafafa.jpg"
first = storage.copy_verified_object(
    key=key,
    source=io.BytesIO(payload),
    byte_size=len(payload),
    sha256=checksum,
    content_type="image/jpeg",
)
second = storage.copy_verified_object(
    key=key,
    source=io.BytesIO(payload),
    byte_size=len(payload),
    sha256=checksum,
    content_type="image/jpeg",
)
assert first.created_by_this_call is True
assert second.created_by_this_call is False
print("legacy copy post-write verification: PASS")
PY

docker compose --project-name "${PROJECT_NAME}" --file "${COMPOSE_FILE}" \
  restart minio api oidc web >/dev/null
recovery_attempt=0
until curl --fail --silent --show-error "${BASE_URL}/health/ready" \
  | grep -q '"database":{"status":"ok"'; do
  recovery_attempt=$((recovery_attempt + 1))
  if [ "${recovery_attempt}" -ge 60 ]; then
    echo "artifact services did not recover after restart" >&2
    exit 1
  fi
  sleep 1
done
curl --fail --silent --show-error --cookie "${OWNER_JAR}" \
  --output "${TEMP_ROOT}/streamed-after-restart.jpg" \
  "${BASE_URL}/api/v1/paint-projects/${project_id}/images/${image_id}/content"
if [ "$(shasum -a 256 "${TEMP_ROOT}/primary.jpg" | awk '{print $1}')" != \
  "$(shasum -a 256 "${TEMP_ROOT}/streamed-after-restart.jpg" | awk '{print $1}')" ]; then
  echo "private object did not recover after service restart" >&2
  exit 1
fi

oidc_login "owner-b" "${OWNER_B_JAR}" "${TEMP_ROOT}/owner-b-session.json"
owner_b_id=$(uv run --project "${REPOSITORY_ROOT}/apps/api" python -c \
  'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["user"]["id"])' \
  "${TEMP_ROOT}/owner-b-session.json")
owner_b_project_status=$(curl --silent --show-error --cookie "${OWNER_B_JAR}" \
  --output /dev/null --write-out '%{http_code}' \
  "${BASE_URL}/api/v1/paint-projects/${project_id}")
owner_b_object_status=$(curl --silent --show-error --cookie "${OWNER_B_JAR}" \
  --output /dev/null --write-out '%{http_code}' \
  "${BASE_URL}/api/v1/paint-projects/${project_id}/images/${image_id}/content")
if [ "${owner_b_project_status}" != "404" ] || [ "${owner_b_object_status}" != "404" ]; then
  echo "Owner B isolation returned project=${owner_b_project_status}, object=${owner_b_object_status}" >&2
  exit 1
fi
expired_session_count=$(docker compose --project-name "${PROJECT_NAME}" \
  --file "${COMPOSE_FILE}" exec -T postgres \
  psql -U "${SMOKE_DATABASE_ADMIN_USER}" -d "${SMOKE_DATABASE_NAME}" -At \
  -c "UPDATE auth_sessions SET created_at = now() - interval '2 minutes', \
      expires_at = now() - interval '1 minute' \
      WHERE user_id = '${owner_b_id}' AND revoked_at IS NULL RETURNING 1")
if [ "$(printf '%s\n' "${expired_session_count}" | grep -c '^1$')" != "1" ]; then
  echo "session-expiry fixture did not update exactly one Owner B session" >&2
  exit 1
fi
curl --fail --silent --show-error --cookie "${OWNER_B_JAR}" \
  "${BASE_URL}/api/v1/auth/session" | grep -q '"authenticated":false'
expired_object_status=$(curl --silent --show-error --cookie "${OWNER_B_JAR}" \
  --output /dev/null --write-out '%{http_code}' \
  "${BASE_URL}/api/v1/paint-projects/${project_id}/images/${image_id}/content")
if [ "${expired_object_status}" != "401" ]; then
  echo "expired-session object access returned ${expired_object_status}, expected 401" >&2
  exit 1
fi

oidc_login "reviewer-c" "${REVIEWER_JAR}" "${TEMP_ROOT}/reviewer-session.json"
reviewer_id=$(uv run --project "${REPOSITORY_ROOT}/apps/api" python -c \
  'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["user"]["id"])' \
  "${TEMP_ROOT}/reviewer-session.json")
reviewer_csrf=$(csrf_from_jar "${REVIEWER_JAR}")
curl --silent --show-error --cookie "${OWNER_JAR}" \
  --output "${TEMP_ROOT}/membership-a.json" --write-out '%{http_code}' \
  --request PUT --header "Content-Type: application/json" \
  --header "X-CSRF-Token: ${owner_csrf}" \
  --data "{\"user_id\":\"${reviewer_id}\"}" \
  "${BASE_URL}/api/v1/paint-projects/${project_id}/memberships/${reviewer_id}" \
  >"${TEMP_ROOT}/membership-a.status" &
assign_pid_a=$!
curl --silent --show-error --cookie "${OWNER_JAR}" \
  --output "${TEMP_ROOT}/membership-b.json" --write-out '%{http_code}' \
  --request PUT --header "Content-Type: application/json" \
  --header "X-CSRF-Token: ${owner_csrf}" \
  --data "{\"user_id\":\"${reviewer_id}\"}" \
  "${BASE_URL}/api/v1/paint-projects/${project_id}/memberships/${reviewer_id}" \
  >"${TEMP_ROOT}/membership-b.status" &
assign_pid_b=$!
wait "${assign_pid_a}"
wait "${assign_pid_b}"
assign_status_a=$(cat "${TEMP_ROOT}/membership-a.status")
assign_status_b=$(cat "${TEMP_ROOT}/membership-b.status")
if [ "${assign_status_a}" != "200" ] || [ "${assign_status_b}" != "200" ]; then
  echo "concurrent reviewer assignment returned ${assign_status_a}/${assign_status_b}, expected 200/200" >&2
  exit 1
fi
repeat_assign_status=$(curl --silent --show-error --cookie "${OWNER_JAR}" \
  --output /dev/null --write-out '%{http_code}' \
  --request PUT --header "Content-Type: application/json" \
  --header "X-CSRF-Token: ${owner_csrf}" \
  --data "{\"user_id\":\"${reviewer_id}\"}" \
  "${BASE_URL}/api/v1/paint-projects/${project_id}/memberships/${reviewer_id}")
if [ "${repeat_assign_status}" != "200" ]; then
  echo "idempotent reviewer assignment returned ${repeat_assign_status}, expected 200" >&2
  exit 1
fi
curl --fail --silent --show-error --cookie "${OWNER_JAR}" \
  --output "${TEMP_ROOT}/memberships.json" \
  "${BASE_URL}/api/v1/paint-projects/${project_id}/memberships"
membership_count=$(uv run --project "${REPOSITORY_ROOT}/apps/api" python -c \
  'import json,sys; print(len(json.load(open(sys.argv[1], encoding="utf-8"))["items"]))' \
  "${TEMP_ROOT}/memberships.json")
if [ "${membership_count}" != "1" ]; then
  echo "concurrent/idempotent reviewer assignment created ${membership_count} rows" >&2
  exit 1
fi
second_reviewer_status=$(curl --silent --show-error --cookie "${OWNER_JAR}" \
  --output /dev/null --write-out '%{http_code}' \
  --request PUT --header "Content-Type: application/json" \
  --header "X-CSRF-Token: ${owner_csrf}" \
  --data "{\"user_id\":\"${owner_b_id}\"}" \
  "${BASE_URL}/api/v1/paint-projects/${project_id}/memberships/${owner_b_id}")
if [ "${second_reviewer_status}" != "200" ]; then
  echo "second reviewer assignment returned ${second_reviewer_status}, expected 200" >&2
  exit 1
fi
curl --fail --silent --show-error --cookie "${OWNER_JAR}" \
  --output "${TEMP_ROOT}/memberships-two-reviewers.json" \
  "${BASE_URL}/api/v1/paint-projects/${project_id}/memberships"
membership_count=$(uv run --project "${REPOSITORY_ROOT}/apps/api" python -c \
  'import json,sys; print(len(json.load(open(sys.argv[1], encoding="utf-8"))["items"]))' \
  "${TEMP_ROOT}/memberships-two-reviewers.json")
if [ "${membership_count}" != "2" ]; then
  echo "multi-reviewer assignment produced ${membership_count} rows, expected 2" >&2
  exit 1
fi
second_project_status=$(curl --silent --show-error --cookie "${OWNER_JAR}" \
  --output "${TEMP_ROOT}/second-project.json" --write-out '%{http_code}' \
  --request POST --header "Content-Type: application/json" \
  --header "X-CSRF-Token: ${owner_csrf}" \
  --header "Idempotency-Key: $(uuidgen)" \
  --data '{"title":"Synthetic Phase 2B-1 second project"}' \
  "${BASE_URL}/api/v1/paint-projects")
if [ "${second_project_status}" != "201" ]; then
  echo "second project create returned ${second_project_status}, expected 201" >&2
  exit 1
fi
second_project_id=$(json_field "${TEMP_ROOT}/second-project.json" "id")
second_project_assignment_status=$(curl --silent --show-error --cookie "${OWNER_JAR}" \
  --output /dev/null --write-out '%{http_code}' \
  --request PUT --header "Content-Type: application/json" \
  --header "X-CSRF-Token: ${owner_csrf}" \
  --data "{\"user_id\":\"${reviewer_id}\"}" \
  "${BASE_URL}/api/v1/paint-projects/${second_project_id}/memberships/${reviewer_id}")
if [ "${second_project_assignment_status}" != "200" ]; then
  echo "cross-project reviewer assignment returned ${second_project_assignment_status}, expected 200" >&2
  exit 1
fi
curl --fail --silent --show-error --cookie "${REVIEWER_JAR}" \
  --output "${TEMP_ROOT}/reviewer-projects.json" \
  "${BASE_URL}/api/v1/paint-projects"
reviewer_project_count=$(uv run --project "${REPOSITORY_ROOT}/apps/api" python -c \
  'import json,sys; print(len(json.load(open(sys.argv[1], encoding="utf-8"))["items"]))' \
  "${TEMP_ROOT}/reviewer-projects.json")
if [ "${reviewer_project_count}" != "2" ]; then
  echo "reviewer multi-project list returned ${reviewer_project_count}, expected 2" >&2
  exit 1
fi
curl --fail --silent --show-error --cookie "${REVIEWER_JAR}" \
  "${BASE_URL}/api/v1/paint-projects/${project_id}" \
  | grep -q '"access_role":"reviewer"'
curl --fail --silent --show-error --cookie "${REVIEWER_JAR}" \
  --output "${TEMP_ROOT}/reviewer-streamed-primary.jpg" \
  "${BASE_URL}/api/v1/paint-projects/${project_id}/images/${image_id}/content"
if [ "$(shasum -a 256 "${TEMP_ROOT}/primary.jpg" | awk '{print $1}')" != \
  "$(shasum -a 256 "${TEMP_ROOT}/reviewer-streamed-primary.jpg" | awk '{print $1}')" ]; then
  echo "reviewer API stream did not match the private object" >&2
  exit 1
fi
review_status=$(curl --silent --show-error --cookie "${REVIEWER_JAR}" \
  --output "${TEMP_ROOT}/reviewer-readiness.json" --write-out '%{http_code}' \
  --request POST --header "Content-Type: application/json" \
  --header "X-CSRF-Token: ${reviewer_csrf}" \
  --header "Idempotency-Key: $(uuidgen)" \
  --data '{"verdict":"ready","reason":"Synthetic reviewer verified the complete private image set."}' \
  "${BASE_URL}/api/v1/paint-projects/${project_id}/image-set/readiness-reviews")
if [ "${review_status}" != "201" ]; then
  echo "assigned reviewer readiness review returned ${review_status}, expected 201" >&2
  exit 1
fi
grep -q '"verdict":"ready"' "${TEMP_ROOT}/reviewer-readiness.json"
reviewer_membership_status=$(curl --silent --show-error --cookie "${REVIEWER_JAR}" \
  --output /dev/null --write-out '%{http_code}' \
  "${BASE_URL}/api/v1/paint-projects/${project_id}/memberships")
if [ "${reviewer_membership_status}" != "404" ]; then
  echo "reviewer membership management returned ${reviewer_membership_status}, expected 404" >&2
  exit 1
fi
remove_status=$(curl --silent --show-error --cookie "${OWNER_JAR}" \
  --output /dev/null --write-out '%{http_code}' \
  --request DELETE --header "X-CSRF-Token: ${owner_csrf}" \
  "${BASE_URL}/api/v1/paint-projects/${project_id}/memberships/${reviewer_id}")
if [ "${remove_status}" != "204" ]; then
  echo "owner reviewer removal returned ${remove_status}, expected 204" >&2
  exit 1
fi
revoked_status=$(curl --silent --show-error --cookie "${REVIEWER_JAR}" \
  --output /dev/null --write-out '%{http_code}' \
  "${BASE_URL}/api/v1/paint-projects/${project_id}")
if [ "${revoked_status}" != "404" ]; then
  echo "removed reviewer access returned ${revoked_status}, expected 404" >&2
  exit 1
fi
revoked_object_status=$(curl --silent --show-error --cookie "${REVIEWER_JAR}" \
  --output /dev/null --write-out '%{http_code}' \
  "${BASE_URL}/api/v1/paint-projects/${project_id}/images/${image_id}/content")
if [ "${revoked_object_status}" != "404" ]; then
  echo "removed reviewer object access returned ${revoked_object_status}, expected 404" >&2
  exit 1
fi
logout_status=$(curl --silent --show-error --cookie "${REVIEWER_JAR}" \
  --cookie-jar "${REVIEWER_JAR}" --output /dev/null --write-out '%{http_code}' \
  --request POST --header "X-CSRF-Token: ${reviewer_csrf}" \
  "${BASE_URL}/api/v1/auth/logout")
if [ "${logout_status}" != "204" ]; then
  echo "logout returned ${logout_status}, expected 204" >&2
  exit 1
fi
curl --fail --silent --show-error --cookie "${REVIEWER_JAR}" \
  "${BASE_URL}/api/v1/auth/session" | grep -q '"authenticated":false'
logged_out_object_status=$(curl --silent --show-error --cookie "${REVIEWER_JAR}" \
  --output /dev/null --write-out '%{http_code}' \
  "${BASE_URL}/api/v1/paint-projects/${project_id}/images/${image_id}/content")
if [ "${logged_out_object_status}" != "401" ]; then
  echo "logged-out object access returned ${logged_out_object_status}, expected 401" >&2
  exit 1
fi

if docker compose --project-name "${PROJECT_NAME}" --file "${COMPOSE_FILE}" exec -T api \
  python -c \
  'import os,psycopg; u=os.environ["DATABASE_URL"].replace("postgresql+psycopg://","postgresql://",1); c=psycopg.connect(u); c.execute("CREATE TABLE runtime_ddl_probe(id integer)")' \
  >"${TEMP_ROOT}/runtime-ddl.out" 2>&1; then
  echo "runtime database role unexpectedly executed DDL" >&2
  exit 1
fi
grep -qi 'permission denied' "${TEMP_ROOT}/runtime-ddl.out"
table_owner_count=$(docker compose --project-name "${PROJECT_NAME}" \
  --file "${COMPOSE_FILE}" exec -T postgres \
  psql -U "${SMOKE_DATABASE_ADMIN_USER}" -d "${SMOKE_DATABASE_NAME}" -At \
  -c "SELECT count(*) FROM pg_tables WHERE schemaname='public' AND tableowner='${SMOKE_DATABASE_MIGRATOR_USER}'")
if [ "${table_owner_count}" -lt 14 ]; then
  echo "migrator does not own all Phase 2B-1 tables" >&2
  exit 1
fi

asset_path=$(grep -Eo 'src="[^"]*/assets/[^"]+\.js"' \
  "${TEMP_ROOT}/index.html" | head -n 1 | cut -d '"' -f 2)
curl --fail --silent --show-error --dump-header "${TEMP_ROOT}/asset-headers" \
  --output /dev/null "${BASE_URL}${asset_path}"
cp "${TEMP_ROOT}/asset-headers" "${TEMP_ROOT}/headers"
assert_header "Cache-Control" "max-age=31536000, immutable"

for service_name in api oidc web; do
  service_uid=$(docker compose --project-name "${PROJECT_NAME}" \
    --file "${COMPOSE_FILE}" exec -T "${service_name}" id -u)
  if [ "${service_uid}" = "0" ]; then
    echo "${service_name} unexpectedly runs as root" >&2
    exit 1
  fi
done
docker compose --project-name "${PROJECT_NAME}" --file "${COMPOSE_FILE}" exec -T api \
  python -c "import importlib.util; assert importlib.util.find_spec('pytest') is None"
docker compose --project-name "${PROJECT_NAME}" --file "${COMPOSE_FILE}" exec -T api \
  sh -c 'test ! -e /app/.env && test ! -e /app/tests && test ! -e /app/src'

oversized_status=$(
  head -c 21037057 /dev/zero \
    | curl --silent --show-error --cookie "${OWNER_JAR}" \
      --dump-header "${TEMP_ROOT}/headers" --output /dev/null --write-out '%{http_code}' \
      --request POST --header 'Content-Type: application/octet-stream' \
      --data-binary @- "${BASE_URL}/api/v1/paint-projects"
)
if [ "${oversized_status}" != "413" ]; then
  echo "oversized request returned ${oversized_status}, expected 413" >&2
  exit 1
fi

unknown_host_status=$(curl --silent --dump-header "${TEMP_ROOT}/headers" \
  --output /dev/null --write-out '%{http_code}' \
  --header 'Host: untrusted.invalid' "${BASE_URL}/")
if [ "${unknown_host_status}" != "400" ]; then
  echo "unknown Host was not rejected" >&2
  exit 1
fi

if docker compose --project-name "${PROJECT_NAME}" --file "${COMPOSE_FILE}" run \
  --rm --no-deps --env APP_ENV=production api \
  sh -c 'unset DATABASE_URL; exec python -c "import creativedeploy_api.main"' \
  >"${TEMP_ROOT}/production.out" 2>&1; then
  echo "production startup unexpectedly accepted missing DATABASE_URL" >&2
  exit 1
fi
grep -q 'Production requires an explicitly provided DATABASE_URL' \
  "${TEMP_ROOT}/production.out"

docker compose --project-name "${PROJECT_NAME}" --file "${COMPOSE_FILE}" stop postgres
degraded_status=$(curl --silent --show-error --output "${TEMP_ROOT}/degraded.json" \
  --write-out '%{http_code}' "${BASE_URL}/health/ready")
if [ "${degraded_status}" != "503" ]; then
  echo "readiness returned ${degraded_status} after PostgreSQL stopped, expected 503" >&2
  exit 1
fi
curl --fail --silent --show-error "${BASE_URL}/health/live" \
  | grep -q '"status":"ok"'

echo "artifact smoke validation: PASS"
