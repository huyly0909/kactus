"""
Kactus exception hierarchy.

All application exceptions should inherit from KactusException so that
the FastAPI exception handler can catch them uniformly and return
structured JSON error responses.
"""

from __future__ import annotations

from typing import Any


class KactusException(Exception):
    """Base exception for all Kactus applications.

    Attributes:
        code:    Machine-readable error code (e.g. ``"DATABASE_ERROR"``).
        title:   Short human-readable title.
        message: Detailed error description.
        tip:     Actionable suggestion for the caller.
        data:    Arbitrary context payload.
    """

    code: str | None = None
    title: str | None = None

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        title: str | None = None,
        tip: str | None = None,
        data: dict[str, Any] | None = None,
    ) -> None:
        self.message = message or str(self)
        if code is not None:
            self.code = code
        if title is not None:
            self.title = title
        self.tip = tip
        self.data = data
        super().__init__(self.message)

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a JSON-friendly dict (``None`` values omitted)."""
        payload: dict[str, Any] = {}
        for key in ("code", "title", "message", "tip", "data"):
            value = getattr(self, key, None)
            if value is not None:
                payload[key] = value
        return payload


# ---------------------------------------------------------------------------
# Concrete subclasses — each provides a sensible default ``code``.
# ---------------------------------------------------------------------------


class InvalidArgumentError(KactusException):
    """Raised when a function/API receives an invalid argument."""

    code = "INVALID_ARGUMENT"
    title = "Invalid Argument"


class NotFoundError(KactusException):
    """Raised when a requested resource cannot be found."""

    code = "NOT_FOUND"
    title = "Not Found"


class ConfigurationError(KactusException):
    """Raised when configuration is missing or invalid."""

    code = "CONFIGURATION_ERROR"
    title = "Configuration Error"


class DatabaseError(KactusException):
    """Raised on database-related failures."""

    code = "DATABASE_ERROR"
    title = "Database Error"


class DataSourceError(KactusException):
    """Raised when a data source operation fails."""

    code = "DATA_SOURCE_ERROR"
    title = "Data Source Error"


class AuthenticationError(KactusException):
    """Raised when authentication fails (missing/invalid credentials)."""

    code = "AUTHENTICATION_ERROR"
    title = "Authentication Error"


class PermissionDeniedError(KactusException):
    """Raised when the user lacks permission for the requested action."""

    code = "PERMISSION_DENIED"
    title = "Permission Denied"


class ValidationError(KactusException):
    """Raised when input data fails validation rules."""

    code = "VALIDATION_ERROR"
    title = "Validation Error"


class ConflictError(KactusException):
    """Raised when an operation conflicts with existing state (e.g. duplicate)."""

    code = "CONFLICT"
    title = "Conflict"


class RateLimitError(KactusException):
    """Raised when a rate limit is exceeded."""

    code = "RATE_LIMIT_EXCEEDED"
    title = "Rate Limit Exceeded"


class TimeoutError(KactusException):
    """Raised when an operation times out."""

    code = "TIMEOUT"
    title = "Timeout"


class ExternalServiceError(KactusException):
    """Raised when a call to an external service/API fails."""

    code = "EXTERNAL_SERVICE_ERROR"
    title = "External Service Error"


class InternalError(KactusException):
    """Raised for unexpected internal errors (catch-all 500)."""

    code = "INTERNAL_ERROR"
    title = "Internal Error"


# ---------------------------------------------------------------------------
# HTTP status code mapping
# ---------------------------------------------------------------------------

_STATUS_CODE_MAP: dict[type[KactusException], int] = {
    InvalidArgumentError: 400,
    ValidationError: 400,
    AuthenticationError: 401,
    PermissionDeniedError: 403,
    NotFoundError: 404,
    ConflictError: 409,
    RateLimitError: 429,
    TimeoutError: 504,
    ConfigurationError: 500,
    DatabaseError: 500,
    DataSourceError: 502,
    ExternalServiceError: 502,
    InternalError: 500,
}


# ---------------------------------------------------------------------------
# FastAPI exception handler installer
# ---------------------------------------------------------------------------


def install_exception_handlers(app) -> None:
    """Register a global handler on *app* that catches :class:`KactusException`
    and returns a structured JSON response.

    Usage::

        from kactus_common.exceptions import install_exception_handlers

        app = FastAPI()
        install_exception_handlers(app)
    """
    from fastapi import Request
    from fastapi.responses import JSONResponse

    @app.exception_handler(KactusException)
    async def _handle_kactus_exception(request: Request, exc: KactusException):
        status_code = _STATUS_CODE_MAP.get(type(exc), 400)
        return JSONResponse(status_code=status_code, content=exc.to_dict())
