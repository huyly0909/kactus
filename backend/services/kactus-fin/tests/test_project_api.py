"""Tests for project scoping, member/invite management, and audit.

Covers the end-to-end behaviour introduced with project scoping:

* every non-admin user gets a personal project (OWNER membership) on creation;
* projects are listed by membership, not globally;
* members are invited by exact email (no directory enumeration), role-gated
  (MEMBER read-only, MANAGER/OWNER read-write), with last-owner and
  owner-grant guard rails;
* domain entities (portfolios here) are isolated across projects — a record in
  another project reads as 404, never leaking its existence;
* user actions land in the append-only ``audit_logs`` table.

In-memory SQLite (shared pool) for the OLTP side; the market data plane is faked
by ``conftest.py`` but unused here.
"""

from __future__ import annotations

import asyncio

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from kactus_common.audit.model import AuditLog
from kactus_common.database.oltp import session as session_mod
from kactus_common.database.oltp.models import Base
from kactus_common.database.oltp.session import DatabaseSessionManager
from kactus_common.project.const import DefaultRole
from kactus_common.project.service import ProjectService
from kactus_common.user import auth as auth_mod
from kactus_common.user.model import User

TEST_DB_URL = "sqlite+aiosqlite://"
PASSWORD = "Test123!"


@pytest_asyncio.fixture
async def db():
    manager = DatabaseSessionManager(database_url=TEST_DB_URL)
    async with manager.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield manager
    async with manager.engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await manager.close()


@pytest_asyncio.fixture
async def app(db):
    from kactus_common.config import clear_settings, register_settings
    from kactus_common.sse.market import register_sse_handler, reset_sse_handler
    from kactus_fin.app import create_app
    from kactus_fin.config import Settings

    register_settings(Settings(internal_service_token="test-token"))
    session_mod._db = db
    auth_mod._auth = None
    register_sse_handler()

    yield create_app()

    reset_sse_handler()
    session_mod._db = None
    auth_mod._auth = None
    clear_settings()


async def _make_user(db, email: str, name: str, *, is_superuser: bool = False) -> User:
    """Create a user and (for non-admins) their personal project.

    Stashes the personal project id on ``user._project_id`` for cookie setup.
    """
    async with db.get_session() as session:
        user = User.init(
            email=email,
            username=name,
            password_hash=PASSWORD,
            name=name,
            status="active",
            is_superuser=is_superuser,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        project = await ProjectService.ensure_personal_project(session, user=user)
        user._project_id = project.id if project else None
    return user


async def _client(app, email: str, *, project_id: int | None = None) -> AsyncClient:
    """A cookie-authenticated client for ``email`` with an optional project cookie."""
    c = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    login = await c.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert login.status_code == 200, login.text
    c.cookies.update(dict(login.cookies))
    if project_id is not None:
        c.cookies.set("kactus_project_id", str(project_id))
    return c


async def _drain_audit() -> None:
    """Let fire-and-forget audit tasks finish before asserting on the table."""
    from kactus_common.audit.service import _pending

    if _pending:
        await asyncio.gather(*list(_pending), return_exceptions=True)


# --------------------------------------------------------------------------- #
# Personal project bootstrap
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_personal_project_created_with_owner_membership(db):
    user = await _make_user(db, "owner@kactus.io", "Owner")
    async with db.get_session() as session:
        role = await ProjectService.get_member_role(
            session, project_id=user._project_id, user_id=user.id
        )
    assert role == DefaultRole.OWNER.value


@pytest.mark.asyncio
async def test_superuser_gets_no_personal_project(db):
    admin = await _make_user(db, "admin@kactus.io", "Admin", is_superuser=True)
    assert admin._project_id is None


# --------------------------------------------------------------------------- #
# Listing is by membership
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_list_projects_only_shows_membership(app, db):
    owner = await _make_user(db, "owner@kactus.io", "Owner")
    await _make_user(db, "other@kactus.io", "Other")

    c = await _client(app, "owner@kactus.io", project_id=owner._project_id)
    resp = await c.get("/api/projects")
    await c.aclose()
    assert resp.status_code == 200
    items = resp.json()["data"]["items"]
    # Owner sees exactly their personal project, not Other's.
    assert [int(p["id"]) for p in items] == [owner._project_id]


# --------------------------------------------------------------------------- #
# Invite by email + shared-within-project read + role gating
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_invite_member_then_shared_read_but_no_write(app, db):
    owner = await _make_user(db, "owner@kactus.io", "Owner")
    await _make_user(db, "member@kactus.io", "Member")

    oc = await _client(app, "owner@kactus.io", project_id=owner._project_id)
    # Owner creates a portfolio in their project.
    pid = (await oc.post("/api/portfolios", json={"name": "WL"})).json()["data"]["id"]
    # Owner invites member (MEMBER role) by exact email.
    invite = await oc.post(
        f"/api/projects/{owner._project_id}/members",
        json={"email": "member@kactus.io", "role": "member"},
    )
    assert invite.status_code == 200
    assert invite.json()["data"]["role"] == DefaultRole.MEMBER.value
    await oc.aclose()

    # Member selects the owner's project and reads the shared portfolio.
    mc = await _client(app, "member@kactus.io", project_id=owner._project_id)
    listed = await mc.get("/api/portfolios")
    assert listed.status_code == 200
    assert [p["id"] for p in listed.json()["data"]["items"]] == [pid]
    # …but a MEMBER cannot write.
    denied = await mc.post("/api/portfolios", json={"name": "nope"})
    await mc.aclose()
    assert denied.status_code == 403


@pytest.mark.asyncio
async def test_invite_unknown_email_is_generic_404(app, db):
    owner = await _make_user(db, "owner@kactus.io", "Owner")
    oc = await _client(app, "owner@kactus.io", project_id=owner._project_id)
    resp = await oc.post(
        f"/api/projects/{owner._project_id}/members",
        json={"email": "ghost@kactus.io", "role": "member"},
    )
    await oc.aclose()
    assert resp.status_code == 404
    # Generic message — must not confirm whether the email exists.
    assert "member@" not in resp.text


@pytest.mark.asyncio
async def test_manager_cannot_grant_owner(app, db):
    owner = await _make_user(db, "owner@kactus.io", "Owner")
    await _make_user(db, "manager@kactus.io", "Manager")
    await _make_user(db, "victim@kactus.io", "Victim")

    oc = await _client(app, "owner@kactus.io", project_id=owner._project_id)
    await oc.post(
        f"/api/projects/{owner._project_id}/members",
        json={"email": "manager@kactus.io", "role": "manager"},
    )
    await oc.aclose()

    # The manager (write, not manage) may invite, but not as OWNER.
    mc = await _client(app, "manager@kactus.io", project_id=owner._project_id)
    resp = await mc.post(
        f"/api/projects/{owner._project_id}/members",
        json={"email": "victim@kactus.io", "role": "owner"},
    )
    await mc.aclose()
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_last_owner_cannot_be_removed(app, db):
    owner = await _make_user(db, "owner@kactus.io", "Owner")
    oc = await _client(app, "owner@kactus.io", project_id=owner._project_id)
    resp = await oc.request(
        "DELETE", f"/api/projects/{owner._project_id}/members/{owner.id}"
    )
    await oc.aclose()
    assert resp.status_code == 409


# --------------------------------------------------------------------------- #
# Cross-project isolation
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_cross_project_portfolio_isolation(app, db):
    owner = await _make_user(db, "owner@kactus.io", "Owner")
    stranger = await _make_user(db, "stranger@kactus.io", "Stranger")

    oc = await _client(app, "owner@kactus.io", project_id=owner._project_id)
    pid = (await oc.post("/api/portfolios", json={"name": "WL"})).json()["data"]["id"]
    await oc.aclose()

    # A user in a different project cannot see it — 404, no existence leak.
    sc = await _client(app, "stranger@kactus.io", project_id=stranger._project_id)
    resp = await sc.get(f"/api/portfolios/{pid}")
    await sc.aclose()
    assert resp.status_code == 404


# --------------------------------------------------------------------------- #
# Audit
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_action_is_audited(app, db):
    owner = await _make_user(db, "owner@kactus.io", "Owner")
    oc = await _client(app, "owner@kactus.io", project_id=owner._project_id)
    created = await oc.post(
        "/api/projects",
        json={"name": "Team", "code": "team-x", "description": None},
    )
    await oc.aclose()
    assert created.status_code == 200
    new_id = int(created.json()["data"]["id"])

    await _drain_audit()
    async with db.get_session() as session:
        rows = await AuditLog.all(session)
    entry = next(r for r in rows if r.action == "project.create")
    assert entry.user_id == owner.id
    assert entry.resource_type == "project"
    assert entry.resource_id == new_id
