"""
Global exception handlers registered on the FastAPI app.
Maps domain exceptions to consistent error envelope responses.
"""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError

from core.exceptions import (
    MuleCatchError,
    NotFoundError,
    AuthenticationError,
    AuthorizationError,
    ValidationError,
    ConflictError,
    ServiceUnavailableError,
)
from core.response import error_response

logger = logging.getLogger(__name__)

# Map exception types to (status_code, error_code)
_EXCEPTION_MAP = {
    NotFoundError: (404, "NOT_FOUND"),
    AuthenticationError: (401, "AUTHENTICATION_ERROR"),
    AuthorizationError: (403, "AUTHORIZATION_ERROR"),
    ValidationError: (400, "VALIDATION_ERROR"),
    ConflictError: (409, "CONFLICT"),
    ServiceUnavailableError: (503, "SERVICE_UNAVAILABLE"),
}


def register_error_handlers(app: FastAPI) -> None:
    """Register all exception handlers on the FastAPI application."""

    @app.exception_handler(MuleCatchError)
    async def mulecatch_error_handler(_request: Request, exc: MuleCatchError):
        status_code, code = _EXCEPTION_MAP.get(type(exc), (500, "INTERNAL_ERROR"))
        logger.warning("Domain error [%s]: %s", code, exc.message)
        return error_response(
            code=code,
            message=exc.message,
            status_code=status_code,
            details=exc.details or None,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(_request: Request, exc: RequestValidationError):
        errors = exc.errors()
        detail = "; ".join(
            f"{'.'.join(str(loc) for loc in e['loc'])}: {e['msg']}" for e in errors
        )
        return error_response(
            code="VALIDATION_ERROR",
            message="Request validation failed",
            status_code=422,
            details=detail,
        )

    @app.exception_handler(Exception)
    async def generic_error_handler(_request: Request, exc: Exception):
        logger.exception("Unhandled exception: %s", exc)
        return error_response(
            code="INTERNAL_ERROR",
            message="An unexpected error occurred",
            status_code=500,
        )
