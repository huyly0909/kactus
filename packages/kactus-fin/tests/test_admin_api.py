"""Tests for admin API endpoints — superuser-only user/project management.

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
from kactus_common.project.model import Project, ProjectMember

TEST_DB_URL = "sqlite+aiosqlite://"


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
    from kactus_common.config import CommonSettings, register_settings, clear_settings

    from kactus_fin.app import create_app

    register_settings(CommonSettings())
    session_mod._db = db
    auth_mod._auth = None

    _app = create_app()
    yield _app

    session_mod._db = None
    auth_mod._auth = None
    clear_settings()


@pytest_asyncio.fixture(autouse=True)
async def clean_tables(db):
    yield
    async with db.get_session() as session:
        await session.execute(ProjectMember.__table__.delete())
        await session.execute(Project.__table__.delete())
        await session.execute(UserSession.__table__.delete())
        await session.execute(User.__table__.delete())
        await session.commit()


@pytest_asyncio.fixture
async def superuser(db) -> User:
    async with db.get_session() as session:
        user = User.init(
            email="admin@kactus.io",
            username="admin",
            password_hash="Admin123!",
            name="Admin User",
            status="active",
            is_superuser=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
    return user


@pytest_asyncio.fixture
async def regular_user(db) -> User:
    async with db.get_session() as session:
        user = User.init(
            email="regular@kactus.io",
            username="regular",
            password_hash="Pass123!",
            name="Regular User",
            status="active",
            is_superuser=False,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
    return user


@pytest_asyncio.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _login(client: AsyncClient, email: str, password: str) -> dict:
    """Helper to login and return cookies."""
    resp = await client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    client.cookies.update(dict(resp.cookies))
    return dict(resp.cookies)


# ---------------------------------------------------------------------------
# Tests — superuser access
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_users_as_superuser(client, superuser):
    await _login(client, "admin@kactus.io", "Admin123!")
    resp = await client.get("/api/admin/users")
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["total"] >= 1
    client.cookies.clear()


@pytest.mark.asyncio
async def test_list_users_as_non_superuser_returns_403(client, regular_user):
    await _login(client, "regular@kactus.io", "Pass123!")
    resp = await client.get("/api/admin/users")
    assert resp.status_code == 403
    client.cookies.clear()


# ---------------------------------------------------------------------------
# Tests — user CRUD
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_user(client, superuser):
    await _login(client, "admin@kactus.io", "Admin123!")
    resp = await client.post(
        "/api/admin/users",
        json={"email": "new@kactus.io", "name": "New User", "password": "NewPass123!"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["email"] == "new@kactus.io"
    assert body["data"]["name"] == "New User"
    client.cookies.clear()


@pytest.mark.asyncio
async def test_create_user_as_superuser(client, superuser):
    await _login(client, "admin@kactus.io", "Admin123!")
    resp = await client.post(
        "/api/admin/users",
        json={
            "email": "super2@kactus.io",
            "name": "Super 2",
            "password": "Pass123!",
            "is_superuser": True,
        },
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["is_superuser"] is True
    client.cookies.clear()


@pytest.mark.asyncio
async def test_reset_password(client, superuser, regular_user):
    await _login(client, "admin@kactus.io", "Admin123!")
    resp = await client.post(f"/api/admin/users/{regular_user.id}/reset-password")
    assert resp.status_code == 200
    body = resp.json()
    assert "new_password" in body["data"]
    assert len(body["data"]["new_password"]) >= 16
    client.cookies.clear()


@pytest.mark.asyncio
async def test_deactivate_user(client, superuser, regular_user):
    await _login(client, "admin@kactus.io", "Admin123!")
    resp = await client.post(f"/api/admin/users/{regular_user.id}/deactivate")
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "inactive"
    client.cookies.clear()


@pytest.mark.asyncio
async def test_update_user_role(client, superuser, regular_user):
    await _login(client, "admin@kactus.io", "Admin123!")
    resp = await client.put(
        f"/api/admin/users/{regular_user.id}/role",
        json={"is_superuser": True},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["is_superuser"] is True
    client.cookies.clear()


@pytest.mark.asyncio
async def test_reset_password_not_found(client, superuser):
    await _login(client, "admin@kactus.io", "Admin123!")
    resp = await client.post("/api/admin/users/999999999/reset-password")
    assert resp.status_code == 404
    client.cookies.clear()


# ---------------------------------------------------------------------------
# Tests — project listing
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_all_projects_admin(client, superuser, db):
    # Create a project in DB
    async with db.get_session() as session:
        from kactus_common.project.service import ProjectService

        await ProjectService.create(
            session, name="TestProj", code="TP1", creator_id=superuser.id
        )

    await _login(client, "admin@kactus.io", "Admin123!")
    resp = await client.get("/api/admin/projects")
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["total"] >= 1
    client.cookies.clear()
