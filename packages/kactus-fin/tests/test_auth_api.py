"""Tests for kactus_fin auth API — login, logout, me endpoints.

Uses in-memory SQLite (aiosqlite) so no external DB required.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from kactus_common.database.oltp.models import Base
from kactus_common.database.oltp.session import DatabaseSessionManager
from kactus_common.database.oltp import session as session_mod
from kactus_common.user import auth as auth_mod
from kactus_common.user.model import User, UserSession

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

TEST_DB_URL = "sqlite+aiosqlite://"


@pytest_asyncio.fixture(scope="module")
async def db():
    """In-memory SQLite for testing."""
    manager = DatabaseSessionManager(database_url=TEST_DB_URL)
    async with manager.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield manager
    async with manager.engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await manager.close()


@pytest_asyncio.fixture(scope="module")
async def app(db):
    """Create a test app with overridden dependencies."""
    from kactus_common.config import CommonSettings, register_settings, clear_settings
    from kactus_fin.app import create_app

    # Register settings so get_db/get_auth singletons work
    register_settings(CommonSettings())

    # Patch the get_db singleton to use our test db
    session_mod._db = db
    # Reset auth singleton so it picks up the patched db
    auth_mod._auth = None

    _app = create_app()
    yield _app

    # Restore
    session_mod._db = None
    auth_mod._auth = None
    clear_settings()


@pytest_asyncio.fixture(autouse=True)
async def clean_tables(db):
    """Clean up data between tests (keep tables, delete rows)."""
    yield
    async with db.get_session() as session:
        await session.execute(UserSession.__table__.delete())
        await session.execute(User.__table__.delete())
        await session.commit()


@pytest_asyncio.fixture
async def seed_user(db) -> User:
    """Create a test user in the database."""
    async with db.get_session() as session:
        user = User.init(
            email="test@kactus.io",
            username="testuser",
            password_hash="Test123!",
            name="Test User",
            status="active",
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
    return user


@pytest_asyncio.fixture
async def client(app):
    """Async HTTP client for testing."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_login_success(client, seed_user):
    """Login with valid credentials returns user info and sets cookie."""
    resp = await client.post(
        "/api/auth/login",
        json={"email": "test@kactus.io", "password": "Test123!"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == "0"
    assert body["data"]["user"]["email"] == "test@kactus.io"
    assert body["data"]["user"]["username"] == "testuser"

    # Cookie should be set
    assert "kactus_session_id" in resp.cookies


@pytest.mark.asyncio
async def test_login_wrong_password(client, seed_user):
    """Login with wrong password returns 401."""
    resp = await client.post(
        "/api/auth/login",
        json={"email": "test@kactus.io", "password": "WrongPass"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_unknown_email(client):
    """Login with unknown email returns 401."""
    resp = await client.post(
        "/api/auth/login",
        json={"email": "nobody@kactus.io", "password": "Test123!"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_without_session(client):
    """GET /me without cookie returns 401."""
    resp = await client.get("/api/auth/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_with_session(client, seed_user):
    """GET /me with valid session cookie returns user info."""
    # Login first
    login_resp = await client.post(
        "/api/auth/login",
        json={"email": "test@kactus.io", "password": "Test123!"},
    )
    cookies = dict(login_resp.cookies)

    # Call /me with cookie
    client.cookies.update(cookies)
    resp = await client.get("/api/auth/me")
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["email"] == "test@kactus.io"
    client.cookies.clear()


@pytest.mark.asyncio
async def test_logout(client, seed_user):
    """Logout clears the session."""
    # Login
    login_resp = await client.post(
        "/api/auth/login",
        json={"email": "test@kactus.io", "password": "Test123!"},
    )
    cookies = dict(login_resp.cookies)

    # Logout
    client.cookies.update(cookies)
    logout_resp = await client.post("/api/auth/logout")
    assert logout_resp.status_code == 200

    # /me should now fail
    client.cookies.update(cookies)
    resp = await client.get("/api/auth/me")
    assert resp.status_code == 401
    client.cookies.clear()


@pytest.mark.asyncio
async def test_login_with_remember(client, seed_user):
    """Login with remember=True should still work and set cookie."""
    resp = await client.post(
        "/api/auth/login",
        json={
            "email": "test@kactus.io",
            "password": "Test123!",
            "remember": True,
        },
    )
    assert resp.status_code == 200
    assert "kactus_session_id" in resp.cookies
