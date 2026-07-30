"""Safe exception-to-error-contract mapping for the API boundary."""

import logging
from typing import cast

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import (
    DataError,
    DBAPIError,
    DisconnectionError,
    IntegrityError,
    InterfaceError,
    OperationalError,
    ProgrammingError,
    SQLAlchemyError,
)
from sqlalchemy.exc import (
    TimeoutError as SQLAlchemyTimeoutError,
)

from creativedeploy_api.api.dependencies import get_request_id
from creativedeploy_api.schemas.errors import ErrorCategory, ErrorResponse
from creativedeploy_api.services.paint_projects import (
    DatabaseWaitTimeoutError,
    PaintProjectApplicationError,
)

logger = logging.getLogger(__name__)


def _response(
    request: Request,
    *,
    status_code: int,
    error_code: str,
    category: ErrorCategory,
    message: str,
    retryable: bool,
    current_state: str | None = None,
    allowed_actions: list[str] | None = None,
    safe_details: dict[str, object] | None = None,
) -> JSONResponse:
    payload = ErrorResponse(
        error_code=error_code,
        category=category,
        message=message,
        retryable=retryable,
        request_id=get_request_id(request),
        current_state=current_state,
        allowed_actions=allowed_actions or [],
        safe_details=safe_details or {},
    )
    return JSONResponse(
        status_code=status_code,
        content=payload.model_dump(mode="json"),
        headers={"Cache-Control": "no-store"},
    )


def _validation_message(error_type: str) -> str:
    messages = {
        "extra_forbidden": "Unexpected field.",
        "int_parsing": "Value must be an integer.",
        "less_than_equal": "Value is above the allowed maximum.",
        "greater_than_equal": "Value is below the allowed minimum.",
        "missing": "Field is required.",
        "string_too_long": "Value is too long.",
        "string_too_short": "Value is too short.",
        "uuid_parsing": "Value must be a valid UUID.",
    }
    return messages.get(error_type, "Value is invalid.")


async def _handle_validation_error(
    request: Request,
    error: Exception,
) -> JSONResponse:
    validation_error = cast(RequestValidationError, error)
    fields: list[dict[str, str]] = []
    for item in validation_error.errors():
        location = ".".join(str(part) for part in item["loc"] if part != "body")
        fields.append(
            {
                "field": location or "request",
                "message": _validation_message(str(item["type"])),
            }
        )
    return _response(
        request,
        status_code=422,
        error_code="REQUEST_VALIDATION_FAILED",
        category="VALIDATION_ERROR",
        message="One or more request fields are invalid.",
        retryable=False,
        allowed_actions=["correct_request"],
        safe_details={"fields": fields},
    )


async def _handle_application_error(
    request: Request,
    error: Exception,
) -> JSONResponse:
    application_error = cast(PaintProjectApplicationError, error)
    return _response(
        request,
        status_code=application_error.status_code,
        error_code=application_error.error_code,
        category=application_error.category,
        message=application_error.message,
        retryable=application_error.retryable,
        current_state=application_error.current_state,
        allowed_actions=list(application_error.allowed_actions),
        safe_details=dict(application_error.safe_details),
    )


def _database_sqlstate(error: SQLAlchemyError) -> str | None:
    if not isinstance(error, DBAPIError):
        return None
    original = error.orig
    for attribute in ("sqlstate", "pgcode"):
        value = getattr(original, attribute, None)
        if isinstance(value, str):
            return value
    diagnostic = getattr(original, "diag", None)
    value = getattr(diagnostic, "sqlstate", None)
    return value if isinstance(value, str) else None


def _is_retryable_database_infrastructure_error(error: SQLAlchemyError) -> bool:
    sqlstate = _database_sqlstate(error)
    if isinstance(error, DBAPIError) and error.connection_invalidated:
        return True
    if sqlstate is not None and sqlstate.startswith("08"):
        return True
    if isinstance(error, (DisconnectionError, SQLAlchemyTimeoutError)):
        return True
    return isinstance(error, (OperationalError, InterfaceError)) and sqlstate is None


def _log_database_error(
    request: Request,
    error: SQLAlchemyError,
    *,
    classification: str,
    warning: bool,
) -> None:
    log_method = logger.warning if warning else logger.error
    log_method(
        "PaintPilot database request failed (%s; classification=%s)",
        type(error).__name__,
        classification,
        extra={
            "request_id": str(get_request_id(request)),
            "database_error_classification": classification,
            "database_sqlstate": _database_sqlstate(error),
        },
    )


async def _handle_database_wait_timeout(
    request: Request,
    error: Exception,
) -> JSONResponse:
    timeout_error = cast(DatabaseWaitTimeoutError, error)
    logger.warning(
        "PaintPilot database request exceeded its configured wait policy",
        extra={
            "request_id": str(get_request_id(request)),
            "database_error_classification": "wait_timeout",
            "database_sqlstate": timeout_error.sqlstate,
        },
    )
    return await _handle_application_error(request, timeout_error)


async def _handle_non_retryable_database_error(
    request: Request,
    error: Exception,
) -> JSONResponse:
    database_error = cast(SQLAlchemyError, error)
    _log_database_error(
        request,
        database_error,
        classification="non_retryable_internal",
        warning=False,
    )
    return _response(
        request,
        status_code=500,
        error_code="INTERNAL_ERROR",
        category="INTERNAL_ERROR",
        message="The request could not be completed.",
        retryable=False,
    )


async def _handle_sqlalchemy_error(
    request: Request,
    error: Exception,
) -> JSONResponse:
    database_error = cast(SQLAlchemyError, error)
    if not _is_retryable_database_infrastructure_error(database_error):
        return await _handle_non_retryable_database_error(request, database_error)

    _log_database_error(
        request,
        database_error,
        classification="retryable_infrastructure",
        warning=True,
    )
    return _response(
        request,
        status_code=503,
        error_code="DATABASE_UNAVAILABLE",
        category="DATABASE_UNAVAILABLE",
        message="The database is temporarily unavailable.",
        retryable=True,
        allowed_actions=["retry"],
    )


async def _handle_unexpected_error(
    request: Request,
    error: Exception,
) -> JSONResponse:
    logger.error(
        "Unhandled API request failure (%s)",
        type(error).__name__,
        extra={"request_id": str(get_request_id(request))},
    )
    return _response(
        request,
        status_code=500,
        error_code="INTERNAL_ERROR",
        category="INTERNAL_ERROR",
        message="The request could not be completed.",
        retryable=False,
    )


def register_error_handlers(app: FastAPI) -> None:
    """Install the stable error contract without exposing raw exceptions."""
    app.add_exception_handler(RequestValidationError, _handle_validation_error)
    app.add_exception_handler(DatabaseWaitTimeoutError, _handle_database_wait_timeout)
    app.add_exception_handler(PaintProjectApplicationError, _handle_application_error)
    app.add_exception_handler(IntegrityError, _handle_non_retryable_database_error)
    app.add_exception_handler(ProgrammingError, _handle_non_retryable_database_error)
    app.add_exception_handler(DataError, _handle_non_retryable_database_error)
    app.add_exception_handler(SQLAlchemyError, _handle_sqlalchemy_error)
    app.add_exception_handler(Exception, _handle_unexpected_error)
