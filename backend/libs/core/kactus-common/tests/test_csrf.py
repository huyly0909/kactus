"""CSRF core: token derivation, ``verify_csrf``, and how ``AppManager`` wires it.

The end-to-end attacker cases (guessed / stolen / tossed tokens against a real
login) live in ``services/kactus-fin/tests/test_csrf.py``; this file pins the
infrastructure contract with no database.
"""

from __future__ import annotations

import re

import pytest
from fastapi import FastAPI, Request
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from kactus_common.app_registry import AppManager, KactusApp
from kactus_common.config import CommonSettings, clear_settings, register_settings
from kactus_common.exceptions import install_exception_handlers
from kactus_common.router import KactusAPIRouter
from kactus_common.user.const import (
    CSRF_COOKIE_NAME,
    CSRF_FORM_FIELD,
    CSRF_HEADER_NAME,
    SESSION_COOKIE_NAME,
)
from kactus_common.user.csrf import CSRF_ERROR_CODE, csrf_token_for, verify_csrf

SESSION = "a" * 32


async def _fake_auth(request: Request) -> None:
    """Stands in for session auth: lets anything through."""


async def _fake_superuser(request: Request) -> None:
    """Stands in for superuser auth."""


@pytest.fixture(autouse=True)
def common_settings():
    register_settings(CommonSettings())
    yield
    clear_settings()


def _build_app(*, csrf: bool = True) -> FastAPI:
    public = KactusAPIRouter(prefix="/public")
    session = KactusAPIRouter(prefix="/session")
    admin = KactusAPIRouter(prefix="/admin")

    @public.post("/login")
    async def login() -> dict:
        return {}

    @session.get("/me")
    async def me() -> dict:
        return {}

    @session.post("/write")
    async def write() -> dict:
        return {}

    @admin.post("/write")
    async def admin_write() -> dict:
        return {}

    manager = AppManager()
    manager.register(
        KactusApp(
            name="t",
            public_routes=[public],
            session_routes=[session],
            superuser_routes=[admin],
        )
    )
    manager.set_auth_dependencies(
        session_dep=_fake_auth,
        superuser_dep=_fake_superuser,
        csrf_dep=verify_csrf if csrf else None,
    )
    app = FastAPI()
    install_exception_handlers(app)
    manager.init_fastapi(app)
    return app


def _deps(app: FastAPI, path: str) -> list:
    route = next(r for r in app.routes if isinstance(r, APIRoute) and r.path == path)
    return [d.dependency for d in route.dependencies]


# ---------------------------------------------------------------------------
# Token
# ---------------------------------------------------------------------------


def test_token_is_deterministic_hex_and_session_bound():
    token = csrf_token_for(SESSION)
    assert token == csrf_token_for(SESSION)
    assert re.fullmatch(r"[0-9a-f]{64}", token)
    assert token != csrf_token_for("b" * 32)
    # One-way: the session id does not appear in what the browser can read.
    assert SESSION not in token


# ---------------------------------------------------------------------------
# AppManager wiring
# ---------------------------------------------------------------------------


def test_csrf_runs_after_auth_on_protected_routers_only():
    app = _build_app()
    assert _deps(app, "/session/write") == [_fake_auth, verify_csrf]
    assert _deps(app, "/admin/write") == [_fake_superuser, verify_csrf]
    assert _deps(app, "/public/login") == []


def test_no_csrf_dep_leaves_routers_as_before():
    app = _build_app(csrf=False)
    assert _deps(app, "/session/write") == [_fake_auth]
    assert _deps(app, "/admin/write") == [_fake_superuser]


# ---------------------------------------------------------------------------
# verify_csrf
# ---------------------------------------------------------------------------


@pytest.fixture
def client():
    with TestClient(_build_app()) as c:
        c.cookies.set(SESSION_COOKIE_NAME, SESSION)
        yield c


def test_unsafe_without_token_is_403(client):
    resp = client.post("/session/write")
    assert resp.status_code == 403
    assert resp.json()["code"] == CSRF_ERROR_CODE


def test_unsafe_with_header_passes(client):
    resp = client.post(
        "/session/write", headers={CSRF_HEADER_NAME: csrf_token_for(SESSION)}
    )
    assert resp.status_code == 200


def test_superuser_router_is_checked_too(client):
    assert client.post("/admin/write").status_code == 403


def test_form_field_is_accepted_only_for_urlencoded_bodies(client):
    token = csrf_token_for(SESSION)
    ok = client.post("/session/write", data={CSRF_FORM_FIELD: token})
    assert ok.status_code == 200

    # The same field in a JSON body is not a token source.
    resp = client.post("/session/write", json={CSRF_FORM_FIELD: token})
    assert resp.status_code == 403


def test_public_routes_are_not_checked(client):
    assert client.post("/public/login").status_code == 200


def test_missing_session_cookie_fails_closed():
    with TestClient(_build_app()) as c:
        resp = c.post("/session/write", headers={CSRF_HEADER_NAME: "x"})
    assert resp.status_code == 403


def test_safe_method_heals_the_cookie(client):
    resp = client.get("/session/me")
    assert resp.status_code == 200
    assert resp.cookies[CSRF_COOKIE_NAME] == csrf_token_for(SESSION)

    # Already current → no Set-Cookie churn on every request.
    again = client.get("/session/me")
    assert CSRF_COOKIE_NAME not in again.cookies
