#!/bin/sh

# Shared fail-safe capture and redaction helpers for the staging drill.

redact_staging_diagnostic_log() {
  raw_log=$1
  shift
  if [ "${STAGING_DIAGNOSTICS_FORCE_REDACTOR_FAILURE:-0}" = "1" ]; then
    return 97
  fi
  uv run --project "${STAGING_DIAGNOSTIC_PYTHON_PROJECT:?required}" python -c '
from pathlib import Path
from urllib.parse import unquote, urlsplit
import sys

raw_log = Path(sys.argv[1])
logs = raw_log.read_text(encoding="utf-8", errors="replace")
tokens: set[str] = set()
for root_value in sys.argv[2:]:
    if not root_value:
        continue
    root = Path(root_value)
    if not root.is_dir():
        continue
    for path in root.iterdir():
        if not path.is_file():
            continue
        raw = path.read_text(encoding="utf-8", errors="strict").strip()
        if raw:
            tokens.add(raw)
            tokens.update(line for line in raw.splitlines() if line)
        if "://" in raw:
            password = urlsplit(raw).password
            if password:
                tokens.add(unquote(password))
for token in sorted(tokens, key=len, reverse=True):
    logs = logs.replace(token, "[REDACTED_SECRET]")
sys.stdout.write(logs)
' "${raw_log}" "$@"
}

emit_redacted_staging_diagnostic_log() {
  raw_log=$1
  shift
  redacted_log="${raw_log}.redacted"
  if ! (umask 077 && : > "${redacted_log}"); then
    printf '%s\n' 'diagnostic log redaction failed; raw log withheld' >&2
    return 0
  fi
  chmod 600 "${redacted_log}"
  if redact_staging_diagnostic_log "${raw_log}" "$@" \
      > "${redacted_log}" 2>/dev/null; then
    cat "${redacted_log}" || \
      printf '%s\n' 'diagnostic log redaction failed; raw log withheld' >&2
  else
    printf '%s\n' 'diagnostic log redaction failed; raw log withheld' >&2
  fi
  rm -f -- "${redacted_log}" >/dev/null 2>&1 || true
  return 0
}

run_with_staging_log_capture() {
  raw_log=$1
  source_secret_root=$2
  restore_secret_root=$3
  shift 3
  if [ "${1:-}" != "--" ]; then
    printf '%s\n' 'staging diagnostic capture requires -- before the command' >&2
    return 64
  fi
  shift
  if ! (umask 077 && : > "${raw_log}"); then
    printf '%s\n' 'diagnostic log capture failed; command not started' >&2
    return 74
  fi
  chmod 600 "${raw_log}"
  case $- in
    *e*) restore_errexit=1 ;;
    *) restore_errexit=0 ;;
  esac
  set +e
  "$@" > "${raw_log}" 2>&1
  command_status=$?
  emit_redacted_staging_diagnostic_log \
    "${raw_log}" "${source_secret_root}" "${restore_secret_root}"
  if [ "${restore_errexit}" = "1" ]; then
    set -e
  fi
  return "${command_status}"
}
