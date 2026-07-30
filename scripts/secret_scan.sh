#!/bin/sh
set -eu

REPOSITORY_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
RUN_ID="${RUN_ID:-local_$(date -u +%Y%m%d%H%M%S)_$(uuidgen | tr '[:upper:]' '[:lower:]' | tr -d '-' | cut -c1-12)}"
if ! printf '%s\n' "${RUN_ID}" | grep -Eq '^[a-z0-9][a-z0-9_]{0,39}$'; then
  echo "RUN_ID must match ^[a-z0-9][a-z0-9_]{0,39}$" >&2
  exit 1
fi
TEMP_ROOT=$(mktemp -d "${TMPDIR:-/tmp}/creativedeploy-secret-scan-${RUN_ID}.XXXXXX")
CONTAINER_NAME="creativedeploy-gitleaks-${RUN_ID}"

cleanup() {
  docker rm --force "${CONTAINER_NAME}" >/dev/null 2>&1 || true
  rm -rf -- "${TEMP_ROOT}"
}
trap cleanup EXIT HUP INT TERM

git -C "${REPOSITORY_ROOT}" ls-files --cached --others --exclude-standard -z \
  | tar --null --files-from=- --create --file=- -C "${REPOSITORY_ROOT}" \
  | tar --extract --file=- --directory="${TEMP_ROOT}"

docker run --name "${CONTAINER_NAME}" --rm --network none \
  --volume "${TEMP_ROOT}:/repo:ro" \
  zricethezav/gitleaks:v8.30.1@sha256:c00b6bd0aeb3071cbcb79009cb16a60dd9e0a7c60e2be9ab65d25e6bc8abbb7f \
  dir /repo --no-banner --redact
