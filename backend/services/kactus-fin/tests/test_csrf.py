"""CSRF protection on kactus-fin's session routes, and the same-origin CORS default.

The check (``kactus_common.user.csrf.verify_csrf``) runs on every session and
superuser router, after auth. The tests that matter most are the ones an
attacker would try: no header, a guessed header, a header lifted from another
session, and a tossed cookie with a matching header — every one of them must be
a 403, while the real SPA flow (echo the cookie it was given) must pass.

Uses in-memory SQLite (aiosqlite) so no external DB required.
"""

from __future__ import annotations

import pytest_asyncio
from httpx import ASGITransport, AsyncClient, Response
from kactus_common.database.oltp import session as session_mod
from kactus_common.database.oltp.models import Base
from kactus_common.database.oltp.session import DatabaseSessionManager
from kactus_common.user import auth as auth_mod
from kactus_common.user.const import (
    CSRF_COOKIE_NAME,
    CSRF_FORM_FIELD,
    CSRF_HEADER_NAME,
    SESSION_COOKIE_NAME,
)
from kactus_common.user.csrf import CSRF_ERROR_CODE, csrf_token_for
from kactus_common.user.model import User, UserSession
from kactus_fin.config import get_settings

TEST_DB_URL = "sqlite+aiosqlite://"
PASSWORD = "Test123!"

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="module")
async def db():
    manager = DatabaseSessionManager(database_url=TEST_DB_URL)
    async with manager.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield manager
    async with manager.engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await manager.close()


@pytest_asyncio.fixture(scope="module")
async def app(db):
    from kactus_common.config import CommonSettings, clear_settings, register_settings
    from kactus_fin.app import create_app

    register_settings(CommonSettings())
    session_mod._db = db
    auth_mod._auth = None

    yield create_app()

    session_mod._db = None
    auth_mod._auth = None
    clear_settings()


@pytest_asyncio.fixture(autouse=True)
async def clean_tables(db):
    yield
    async with db.get_session() as session:
        await session.execute(UserSession.__table__.delete())
        await session.execute(User.__table__.delete())
        await session.commit()


async def _make_user(db, email: str, *, is_superuser: bool = False) -> User:
    async with db.get_session() as session:
        user = User.init(
            email=email,
            username=email.split("@")[0],
            password_hash=PASSWORD,
            name=email.split("@")[0].title(),
            status="active",
            is_superuser=is_superuser,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
    return user


@pytest_asyncio.fixture
async def user(db) -> User:
    return await _make_user(db, "trader@kactus.io")


@pytest_asyncio.fixture
async def client(app):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


async def _login(client: AsyncClient, email: str) -> Response:
    """Log in and keep the cookies — but deliberately *not* the header."""
    resp = await client.post(
        "/api/auth/login", json={"email": email, "password": PASSWORD}
    )
    assert resp.status_code == 200, resp.text
    client.cookies.update(dict(resp.cookies))
    return resp


def _set_cookie_for(resp: Response, name: str) -> str | None:
    """The raw ``Set-Cookie`` line for *name*, attributes included."""
    for line in resp.headers.get_list("set-cookie"):
        if line.startswith(f"{name}="):
            return line
    return None


def _is_csrf_failure(resp: Response) -> bool:
    return resp.status_code == 403 and resp.json().get("code") == CSRF_ERROR_CODE


# ---------------------------------------------------------------------------
# Issuing the token
# ---------------------------------------------------------------------------


async def test_login_issues_a_readable_token_bound_to_the_session(client, user):
    resp = await _login(client, user.email)

    session_id = resp.cookies[SESSION_COOKIE_NAME]
    assert resp.cookies[CSRF_COOKIE_NAME] == csrf_token_for(session_id)

    # The SPA must be able to read the token; it must never read the session.
    csrf_line = _set_cookie_for(resp, CSRF_COOKIE_NAME)
    session_line = _set_cookie_for(resp, SESSION_COOKIE_NAME)
    assert csrf_line is not None and "httponly" not in csrf_line.lower()
    assert session_line is not None and "httponly" in session_line.lower()
    assert "samesite=lax" in csrf_line.lower()


async def test_login_needs_no_token_even_with_a_stale_session(client, user):
    """Login is public: a leftover session cookie must not make it demand one."""
    client.cookies.set(SESSION_COOKIE_NAME, "expired-session")
    resp = await client.post(
        "/api/auth/login", json={"email": user.email, "password": PASSWORD}
    )
    assert resp.status_code == 200


async def test_get_reissues_a_missing_or_stale_cookie(client, user):
    """Sessions that predate the check heal on the SPA's boot ``GET /me``."""
    login = await _login(client, user.email)
    expected = csrf_token_for(login.cookies[SESSION_COOKIE_NAME])

    client.cookies.delete(CSRF_COOKIE_NAME)
    resp = await client.get("/api/auth/me")
    assert resp.status_code == 200
    assert resp.cookies[CSRF_COOKIE_NAME] == expected

    client.cookies.delete(CSRF_COOKIE_NAME)
    client.cookies.set(CSRF_COOKIE_NAME, "stale")
    resp = await client.get("/api/auth/me")
    assert resp.cookies[CSRF_COOKIE_NAME] == expected


async def test_get_with_a_current_cookie_sets_nothing(client, user):
    await _login(client, user.email)
    resp = await client.get("/api/auth/me")
    assert resp.status_code == 200
    assert _set_cookie_for(resp, CSRF_COOKIE_NAME) is None


async def test_logout_clears_the_token_cookie(client, user):
    login = await _login(client, user.email)
    resp = await client.post(
        "/api/auth/logout",
        headers={CSRF_HEADER_NAME: login.cookies[CSRF_COOKIE_NAME]},
    )
    assert resp.status_code == 200
    line = _set_cookie_for(resp, CSRF_COOKIE_NAME)
    assert line is not None and "max-age=0" in line.lower()


# ---------------------------------------------------------------------------
# Enforcing it
# ---------------------------------------------------------------------------


async def test_unsafe_request_without_the_header_is_403(client, user):
    await _login(client, user.email)
    resp = await client.patch("/api/auth/me", json={"language": "en"})
    assert _is_csrf_failure(resp), resp.text


async def test_a_guessed_header_is_403(client, user):
    await _login(client, user.email)
    resp = await client.patch(
        "/api/auth/me", json={"language": "en"}, headers={CSRF_HEADER_NAME: "0" * 64}
    )
    assert _is_csrf_failure(resp)


async def test_the_echoed_cookie_passes(client, user):
    login = await _login(client, user.email)
    resp = await client.patch(
        "/api/auth/me",
        json={"language": "en"},
        headers={CSRF_HEADER_NAME: login.cookies[CSRF_COOKIE_NAME]},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["language"] == "en"


async def test_a_token_from_another_session_is_rejected(app, client, user):
    other = await _login(client, user.email)
    stolen = other.cookies[CSRF_COOKIE_NAME]

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as victim:
        await _login(victim, user.email)
        resp = await victim.patch(
            "/api/auth/me", json={"language": "en"}, headers={CSRF_HEADER_NAME: stolen}
        )
    assert _is_csrf_failure(resp)


async def test_a_tossed_cookie_with_a_matching_header_is_rejected(client, user):
    """Plain double-submit would accept this; the session binding does not."""
    await _login(client, user.email)
    client.cookies.delete(CSRF_COOKIE_NAME)
    client.cookies.set(CSRF_COOKIE_NAME, "attacker-chosen")
    resp = await client.patch(
        "/api/auth/me",
        json={"language": "en"},
        headers={CSRF_HEADER_NAME: "attacker-chosen"},
    )
    assert _is_csrf_failure(resp)


async def test_a_non_ascii_header_is_403_not_500(client, user):
    await _login(client, user.email)
    resp = await client.patch(
        "/api/auth/me",
        json={"language": "en"},
        headers={CSRF_HEADER_NAME: "tökén".encode("latin-1")},
    )
    assert _is_csrf_failure(resp)


async def test_unauthenticated_unsafe_request_is_still_401(client):
    """Auth runs first, so a missing session stays a 401 the SPA redirects on."""
    resp = await client.post("/api/auth/logout")
    assert resp.status_code == 401


async def test_superuser_routes_are_protected(db, client, user):
    admin = await _make_user(db, "admin@kactus.io", is_superuser=True)
    login = await _login(client, admin.email)
    url = f"/api/admin/users/{user.id}/reset-password"

    assert _is_csrf_failure(await client.post(url))

    resp = await client.post(
        url, headers={CSRF_HEADER_NAME: login.cookies[CSRF_COOKIE_NAME]}
    )
    assert resp.status_code == 200


async def test_a_plain_form_may_carry_the_token_in_a_field(client, user):
    """The action-link page posts a real HTML form, which cannot set headers."""
    login = await _login(client, user.email)
    token = login.cookies[CSRF_COOKIE_NAME]

    resp = await client.post("/api/auth/logout", data={CSRF_FORM_FIELD: "wrong"})
    assert _is_csrf_failure(resp)

    resp = await client.post("/api/auth/logout", data={CSRF_FORM_FIELD: token})
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# CORS — same-origin unless configured
# ---------------------------------------------------------------------------


async def test_cors_is_same_origin_by_default(client):
    resp = await client.get("/api/auth/me", headers={"Origin": "http://evil.test"})
    assert "access-control-allow-origin" not in resp.headers


async def test_cors_echoes_only_listed_origins(db, monkeypatch):
    from kactus_fin.app import create_app

    monkeypatch.setenv("KACTUS_CORS_ALLOW_ORIGINS", '["http://allowed.test"]')
    get_settings.cache_clear()
    try:
        app = create_app()
    finally:
        get_settings.cache_clear()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        allowed = await c.get("/api/auth/me", headers={"Origin": "http://allowed.test"})
        other = await c.get("/api/auth/me", headers={"Origin": "http://evil.test"})

    assert allowed.headers["access-control-allow-origin"] == "http://allowed.test"
    assert "access-control-allow-origin" not in other.headers


# ---------------------------------------------------------------------------
# Swagger UI — must keep working for unsafe calls
# ---------------------------------------------------------------------------


async def test_swagger_ui_echoes_the_csrf_cookie(app, client):
    resp = await client.get("/docs")
    assert resp.status_code == 200
    html = resp.text
    assert "SwaggerUIBundle({" in html
    assert "requestInterceptor" in html
    assert f'"{CSRF_COOKIE_NAME}"' in html
    assert f'"{CSRF_HEADER_NAME}"' in html
    # Exactly one /docs route — ours, not FastAPI's default alongside it.
    assert [r.path for r in app.routes].count("/docs") == 1
