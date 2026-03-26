"""Tests for the kactus_common exception hierarchy."""

from __future__ import annotations

import pytest
from kactus_common.exceptions import (
    AuthenticationError,
    ConfigurationError,
    ConflictError,
    DataSourceError,
    DatabaseError,
    ExternalServiceError,
    InternalError,
    InvalidArgumentError,
    KactusException,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
    TimeoutError,
    ValidationError,
    _STATUS_CODE_MAP,
    install_exception_handlers,
)


# ---------------------------------------------------------------------------
# Serialisation
# ---------------------------------------------------------------------------


def test_to_dict_with_all_fields():
    exc = KactusException(
        "Something went wrong",
        code="TEST_ERROR",
        title="Test",
        tip="Try again",
        data={"key": "value"},
    )
    d = exc.to_dict()
    assert d["code"] == "TEST_ERROR"
    assert d["title"] == "Test"
    assert d["message"] == "Something went wrong"
    assert d["tip"] == "Try again"
    assert d["data"] == {"key": "value"}


def test_to_dict_omits_none_values():
    exc = KactusException("Oops")
    d = exc.to_dict()
    assert "tip" not in d
    assert "data" not in d


# ---------------------------------------------------------------------------
# Subclass defaults
# ---------------------------------------------------------------------------

_EXPECTED_CODES = {
    InvalidArgumentError: "INVALID_ARGUMENT",
    NotFoundError: "NOT_FOUND",
    ConfigurationError: "CONFIGURATION_ERROR",
    DatabaseError: "DATABASE_ERROR",
    DataSourceError: "DATA_SOURCE_ERROR",
    AuthenticationError: "AUTHENTICATION_ERROR",
    PermissionDeniedError: "PERMISSION_DENIED",
    ValidationError: "VALIDATION_ERROR",
    ConflictError: "CONFLICT",
    RateLimitError: "RATE_LIMIT_EXCEEDED",
    TimeoutError: "TIMEOUT",
    ExternalServiceError: "EXTERNAL_SERVICE_ERROR",
    InternalError: "INTERNAL_ERROR",
}


@pytest.mark.parametrize("cls,expected_code", _EXPECTED_CODES.items(), ids=lambda c: getattr(c, "__name__", str(c)))
def test_subclass_has_correct_code(cls, expected_code):
    exc = cls("test")
    assert exc.code == expected_code
    assert exc.title is not None


# ---------------------------------------------------------------------------
# HTTP status mapping
# ---------------------------------------------------------------------------

_EXPECTED_STATUS = {
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


@pytest.mark.parametrize("cls,expected_status", _EXPECTED_STATUS.items(), ids=lambda c: getattr(c, "__name__", str(c)))
def test_status_code_mapping(cls, expected_status):
    assert _STATUS_CODE_MAP[cls] == expected_status


# ---------------------------------------------------------------------------
# Exception with data payload
# ---------------------------------------------------------------------------


def test_exception_with_data():
    exc = ConflictError("duplicate", data={"id": 42})
    d = exc.to_dict()
    assert d["data"] == {"id": 42}
    assert d["code"] == "CONFLICT"


# ---------------------------------------------------------------------------
# Exception handler integration
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_install_exception_handlers():
    """Register handlers on a minimal FastAPI app and verify JSON responses."""
    from fastapi import FastAPI
    from httpx import ASGITransport, AsyncClient

    app = FastAPI()
    install_exception_handlers(app)

    @app.get("/not-found")
    async def _():
        raise NotFoundError("Thing not found")

    @app.get("/auth-error")
    async def _2():
        raise AuthenticationError("Bad creds")

    @app.get("/conflict")
    async def _3():
        raise ConflictError("Already exists", data={"code": "ABC"})

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/not-found")
        assert r.status_code == 404
        assert r.json()["code"] == "NOT_FOUND"

        r = await client.get("/auth-error")
        assert r.status_code == 401
        assert r.json()["code"] == "AUTHENTICATION_ERROR"

        r = await client.get("/conflict")
        assert r.status_code == 409
        body = r.json()
        assert body["code"] == "CONFLICT"
        assert body["data"] == {"code": "ABC"}


# ---------------------------------------------------------------------------
# Override class-level code/title at instantiation
# ---------------------------------------------------------------------------


def test_override_code_at_init():
    exc = NotFoundError("x", code="CUSTOM_CODE", title="Custom Title")
    assert exc.code == "CUSTOM_CODE"
    assert exc.title == "Custom Title"
