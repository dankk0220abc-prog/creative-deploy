"""Secret-safe structured runtime logging for staging and production profiles."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

SAFE_RECORD_FIELDS = (
    "request_id",
    "method",
    "path",
    "status_code",
    "duration_ms",
    "event",
    "error_type",
    "database_error_classification",
    "database_sqlstate",
    "storage_provider",
)


class JsonLogFormatter(logging.Formatter):
    """Render only explicit operational fields; exception values are never serialized."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname.lower(),
            "logger": record.name,
            "message": record.getMessage(),
        }
        for field_name in SAFE_RECORD_FIELDS:
            value = getattr(record, field_name, None)
            if value is not None:
                payload[field_name] = value
        return json.dumps(payload, ensure_ascii=True, separators=(",", ":"))


def configure_structured_logging() -> None:
    """Install one JSON stderr handler for application and Uvicorn loggers."""
    handler = logging.StreamHandler()
    handler.setFormatter(JsonLogFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)
    for logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        configured = logging.getLogger(logger_name)
        configured.handlers = []
        configured.propagate = True
