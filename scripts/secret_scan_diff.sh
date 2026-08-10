#!/bin/sh
set -eu

umask 077

REPOSITORY_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
BASE_SHA="${BASE_SHA:-}"
RUN_ID="${RUN_ID:-local_$(date -u +%Y%m%d%H%M%S)_$(uuidgen | tr '[:upper:]' '[:lower:]' | tr -d '-' | cut -c1-12)}"

if [ -z "${BASE_SHA}" ]; then
  echo "BASE_SHA is required for a diff-scoped secret scan." >&2
  exit 1
fi
if ! printf '%s\n' "${RUN_ID}" | grep -Eq '^[a-z0-9][a-z0-9_]{0,39}$'; then
  echo "RUN_ID must match ^[a-z0-9][a-z0-9_]{0,39}$" >&2
  exit 1
fi
if ! BASE_COMMIT=$(git -C "${REPOSITORY_ROOT}" rev-parse --verify --end-of-options "${BASE_SHA}^{commit}" 2>/dev/null); then
  echo "BASE_SHA must resolve to a commit in this repository." >&2
  exit 1
fi
case "${BASE_COMMIT}" in
  '' | *[!0-9a-f]*)
    echo "BASE_SHA did not resolve to a canonical commit identifier." >&2
    exit 1
    ;;
esac

TEMP_ROOT=$(mktemp -d "${TMPDIR:-/tmp}/creativedeploy-secret-scan-diff-${RUN_ID}.XXXXXX")
SNAPSHOT_ROOT="${TEMP_ROOT}/snapshot"
REPORT_ROOT="${TEMP_ROOT}/report"
PATH_LIST="${TEMP_ROOT}/paths.nul"
FILE_COUNT_PATH="${TEMP_ROOT}/file-count"
CONTAINER_NAME="creativedeploy-gitleaks-diff-${RUN_ID}"

cleanup() {
  docker rm --force "${CONTAINER_NAME}" >/dev/null 2>&1 || true
  rm -rf -- "${TEMP_ROOT}"
}
trap cleanup EXIT HUP INT TERM

mkdir -m 700 "${SNAPSHOT_ROOT}" "${REPORT_ROOT}"
: >"${PATH_LIST}"
git -C "${REPOSITORY_ROOT}" diff --no-ext-diff --name-only -z \
  --diff-filter=ACMRTUXB "${BASE_COMMIT}" -- >>"${PATH_LIST}"
git -C "${REPOSITORY_ROOT}" ls-files --others --exclude-standard -z -- \
  >>"${PATH_LIST}"

python3 - "${REPOSITORY_ROOT}" "${PATH_LIST}" "${SNAPSHOT_ROOT}" \
  "${FILE_COUNT_PATH}" <<'PY'
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys


repository_root = Path(sys.argv[1])
path_list = Path(sys.argv[2])
snapshot_root = Path(sys.argv[3])
file_count_path = Path(sys.argv[4])


def refuse(kind: str, relative_path: str) -> None:
    location = json.dumps(relative_path, ensure_ascii=True)
    print(f"diff secret scan refused {kind} path={location}", file=sys.stderr)
    raise SystemExit(1)


raw_paths = path_list.read_bytes().split(b"\0")
seen: set[bytes] = set()
paths: list[bytes] = []
for raw_path in raw_paths:
    if not raw_path or raw_path in seen:
        continue
    seen.add(raw_path)
    paths.append(raw_path)


def is_ignored(relative_path: str) -> bool:
    result = subprocess.run(
        [
            "git",
            "-C",
            str(repository_root),
            "check-ignore",
            "--quiet",
            "--no-index",
            "--",
            relative_path,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if result.returncode not in {0, 1}:
        refuse("ignore-status-unknown", relative_path)
    return result.returncode == 0


directories = [(repository_root, "")]
while directories:
    directory, relative_directory = directories.pop()
    try:
        entries = list(os.scandir(directory))
    except OSError:
        refuse("unreadable-directory", relative_directory or ".")
    for entry in entries:
        relative_path = (
            f"{relative_directory}/{entry.name}" if relative_directory else entry.name
        )
        if relative_path == ".git":
            continue
        try:
            entry_stat = entry.stat(follow_symlinks=False)
        except OSError:
            refuse("unstable", relative_path)
        if stat.S_ISDIR(entry_stat.st_mode):
            if not is_ignored(relative_path):
                directories.append((Path(entry.path), relative_path))
            continue
        if stat.S_ISREG(entry_stat.st_mode) or stat.S_ISLNK(entry_stat.st_mode):
            continue
        raw_path = os.fsencode(relative_path)
        if raw_path not in seen and not is_ignored(relative_path):
            seen.add(raw_path)
            paths.append(raw_path)

for raw_path in paths:
    relative_path = os.fsdecode(raw_path)
    components = relative_path.split("/")
    if (
        relative_path.startswith("/")
        or not components
        or any(component in {"", ".", ".."} for component in components)
        or components[0] == ".git"
    ):
        refuse("unsafe", relative_path)

    source_parent = repository_root
    for component in components[:-1]:
        source_parent /= component
        try:
            parent_stat = os.lstat(source_parent)
        except OSError:
            refuse("missing-parent", relative_path)
        if stat.S_ISLNK(parent_stat.st_mode):
            refuse("symlink-parent", relative_path)
        if not stat.S_ISDIR(parent_stat.st_mode):
            refuse("non-directory-parent", relative_path)

    source = source_parent / components[-1]
    try:
        source_stat = os.lstat(source)
    except OSError:
        refuse("missing", relative_path)
    if stat.S_ISLNK(source_stat.st_mode):
        refuse("symlink", relative_path)
    if not stat.S_ISREG(source_stat.st_mode):
        refuse("special", relative_path)

    destination = snapshot_root.joinpath(*components)
    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    open_flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        open_flags |= os.O_NOFOLLOW
    try:
        source_fd = os.open(source, open_flags)
    except OSError:
        refuse("unstable", relative_path)

    try:
        opened_stat = os.fstat(source_fd)
        if (
            not stat.S_ISREG(opened_stat.st_mode)
            or (opened_stat.st_dev, opened_stat.st_ino)
            != (source_stat.st_dev, source_stat.st_ino)
        ):
            refuse("unstable", relative_path)
        with os.fdopen(source_fd, "rb", closefd=False) as source_file:
            with destination.open("xb") as destination_file:
                shutil.copyfileobj(source_file, destination_file)
        completed_stat = os.fstat(source_fd)
        if (
            completed_stat.st_size != opened_stat.st_size
            or completed_stat.st_mtime_ns != opened_stat.st_mtime_ns
        ):
            destination.unlink(missing_ok=True)
            refuse("changed-during-copy", relative_path)
    finally:
        os.close(source_fd)
    destination.chmod(0o600)

file_count_path.write_text(f"{len(paths)}\n", encoding="ascii")
PY

FILE_COUNT=$(tr -d '\n' <"${FILE_COUNT_PATH}")
if [ "${FILE_COUNT}" -eq 0 ]; then
  printf 'DIFF_SECRET_SCAN_PASS files=0 base=%s\n' "${BASE_COMMIT}"
  exit 0
fi

REPORT_PATH="${REPORT_ROOT}/findings.json"
if docker run --pull=never --name "${CONTAINER_NAME}" --rm --network none \
  --volume "${SNAPSHOT_ROOT}:/repo:ro" \
  --volume "${REPORT_ROOT}:/report:rw" \
  zricethezav/gitleaks:v8.30.1@sha256:c00b6bd0aeb3071cbcb79009cb16a60dd9e0a7c60e2be9ab65d25e6bc8abbb7f \
  dir /repo --no-banner --redact --exit-code 1 \
  --report-format json --report-path /report/findings.json \
  >/dev/null 2>&1; then
  SCAN_STATUS=0
else
  SCAN_STATUS=$?
fi

case "${SCAN_STATUS}" in
  0)
    printf 'DIFF_SECRET_SCAN_PASS files=%s base=%s\n' "${FILE_COUNT}" "${BASE_COMMIT}"
    ;;
  1)
    if [ ! -f "${REPORT_PATH}" ]; then
      echo "Diff secret scan reported findings without a location report." >&2
      exit 2
    fi
    python3 - "${REPORT_PATH}" <<'PY'
import json
from pathlib import Path
import re
import sys


report_path = Path(sys.argv[1])
try:
    findings = json.loads(report_path.read_text(encoding="utf-8"))
except (OSError, UnicodeError, json.JSONDecodeError):
    print("Diff secret scan location report is invalid.", file=sys.stderr)
    raise SystemExit(2)
if not isinstance(findings, list) or not findings:
    print("Diff secret scan location report is empty.", file=sys.stderr)
    raise SystemExit(2)

for finding in findings:
    if not isinstance(finding, dict):
        print("Diff secret scan location report is invalid.", file=sys.stderr)
        raise SystemExit(2)
    raw_rule = finding.get("RuleID")
    rule = raw_rule if isinstance(raw_rule, str) else "unknown"
    if re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", rule) is None:
        rule = "unknown"
    raw_path = finding.get("File")
    location = raw_path if isinstance(raw_path, str) else "unknown"
    if location.startswith("/repo/"):
        location = location.removeprefix("/repo/")
    raw_line = finding.get("StartLine")
    line = raw_line if isinstance(raw_line, int) and raw_line >= 1 else 0
    encoded_location = json.dumps(location, ensure_ascii=True)
    print(f"SECRET_FINDING rule={rule} path={encoded_location} line={line}")
PY
    exit 1
    ;;
  *)
    printf 'Diff secret scanner failed with exit status %s.\n' "${SCAN_STATUS}" >&2
    exit "${SCAN_STATUS}"
    ;;
esac
