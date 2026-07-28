"""Tests for project scoping, member/invite management, and audit.

Covers the end-to-end behaviour introduced with project scoping:

* every non-admin user gets a personal project (OWNER membership) on creation;
* projects are listed by membership, not globally;
* members are invited by exact email (no directory enumeration), role-gated
  (MEMBER read-only, MANAGER/OWNER read-write), with last-owner and
  owner-grant guard rails;
* domain entities (portfolios here) are isolated across projects — a record in
  another project reads as 404, never leaking its existence;
* per-project routes authorise against the **path** project, not the selected
  one, so a role in your own project grants nothing elsewhere;
* the list read model carries owner/member-count/my-role without an N+1;
* ``status`` archives and restores a project;
* ``code`` is freely editable but must stay a unique slug — including against
  soft-deleted holders, which the unique index still reserves;
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
from kactus_common.project.const import PERSONAL_PROJECT_NAME, DefaultRole
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
        project = await ProjectService.get_by_id(session, user._project_id)
    assert role == DefaultRole.OWNER.value
    assert project.name == PERSONAL_PROJECT_NAME
    assert project.code == f"user-{user.id}"


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


@pytest.mark.asyncio
async def test_list_projects_carries_owner_members_and_role(app, db):
    owner = await _make_user(db, "owner@kactus.io", "Owner")
    await _make_user(db, "member@kactus.io", "Member")

    oc = await _client(app, "owner@kactus.io", project_id=owner._project_id)
    await oc.post(
        f"/api/projects/{owner._project_id}/members",
        json={"email": "member@kactus.io", "role": "member"},
    )
    resp = await oc.get("/api/projects")
    await oc.aclose()

    assert resp.status_code == 200
    row = resp.json()["data"]["items"][0]
    # Derived, not columns: resolved from users + project_members.
    assert row["owner_name"] == "Owner"
    assert row["owner_email"] == "owner@kactus.io"
    assert row["my_role"] == DefaultRole.OWNER.value
    assert int(row["member_count"]) == 2  # owner + invited member
    # AwareUTCDatetime — carries an explicit UTC marker ("Z" or "+00:00"), so the
    # client can localise it instead of guessing the zone.
    assert row["create_time"].endswith(("Z", "+00:00"))


@pytest.mark.asyncio
async def test_build_schemas_does_not_n_plus_one(db):
    """Query count must not grow with the number of projects."""
    from sqlalchemy import event

    owner = await _make_user(db, "owner@kactus.io", "Owner")
    async with db.get_session() as session:
        for i in range(4):
            await ProjectService.create(
                session, name=f"P{i}", code=f"p-{i}", creator_id=owner.id
            )
        projects = await ProjectService.get_user_projects(session, owner.id)
        assert len(projects) == 5  # personal + 4

        counts: list[str] = []

        def _count(conn, cursor, statement, *a):  # noqa: ANN001
            counts.append(statement)

        engine = session.get_bind().engine
        event.listen(engine, "before_cursor_execute", _count)
        try:
            items = await ProjectService.build_schemas(
                session, projects, viewer_id=owner.id
            )
        finally:
            event.remove(engine, "before_cursor_execute", _count)

    assert len(items) == 5
    # 3 batched reads: member counts, membership rows, owner users.
    assert len(counts) == 3, counts


# --------------------------------------------------------------------------- #
# Per-project routes authorise on the path project, not the cookie
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_other_project_is_forbidden_even_when_owner_of_own(app, db):
    """A role in the *selected* project must not authorise another project.

    ``@permission`` resolved the role from the project cookie while the handler
    loaded the project from the path — being OWNER of your own project made you
    OWNER of everyone's. The projects list edits non-active projects, so the two
    ids routinely differ.
    """
    owner = await _make_user(db, "owner@kactus.io", "Owner")
    stranger = await _make_user(db, "stranger@kactus.io", "Stranger")

    # Cookie = own project (where this user is OWNER); path = someone else's.
    oc = await _client(app, "owner@kactus.io", project_id=owner._project_id)
    read = await oc.get(f"/api/projects/{stranger._project_id}")
    written = await oc.put(
        f"/api/projects/{stranger._project_id}", json={"name": "pwned"}
    )
    members = await oc.get(f"/api/projects/{stranger._project_id}/members")
    await oc.aclose()

    assert read.status_code == 403
    assert written.status_code == 403
    assert members.status_code == 403


@pytest.mark.asyncio
async def test_member_of_non_selected_project_may_still_read_it(app, db):
    """The converse: membership in the path project is what counts."""
    owner = await _make_user(db, "owner@kactus.io", "Owner")
    guest = await _make_user(db, "guest@kactus.io", "Guest")

    oc = await _client(app, "owner@kactus.io", project_id=owner._project_id)
    await oc.post(
        f"/api/projects/{owner._project_id}/members",
        json={"email": "guest@kactus.io", "role": "member"},
    )
    await oc.aclose()

    # Guest still has their *own* project selected, but is a member of owner's.
    gc = await _client(app, "guest@kactus.io", project_id=guest._project_id)
    resp = await gc.get(f"/api/projects/{owner._project_id}")
    await gc.aclose()
    assert resp.status_code == 200
    assert resp.json()["data"]["my_role"] == DefaultRole.MEMBER.value


# --------------------------------------------------------------------------- #
# Archive / restore
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_archive_and_restore_project(app, db):
    owner = await _make_user(db, "owner@kactus.io", "Owner")
    oc = await _client(app, "owner@kactus.io", project_id=owner._project_id)

    archived = await oc.put(
        f"/api/projects/{owner._project_id}", json={"status": "archived"}
    )
    assert archived.status_code == 200
    assert archived.json()["data"]["status"] == "archived"
    # Archiving is not deletion — it still lists (the UI filters it out).
    listed = await oc.get("/api/projects")
    assert [int(p["id"]) for p in listed.json()["data"]["items"]] == [owner._project_id]

    restored = await oc.put(
        f"/api/projects/{owner._project_id}", json={"status": "active"}
    )
    await oc.aclose()
    assert restored.json()["data"]["status"] == "active"


@pytest.mark.asyncio
async def test_invalid_status_is_rejected(app, db):
    owner = await _make_user(db, "owner@kactus.io", "Owner")
    oc = await _client(app, "owner@kactus.io", project_id=owner._project_id)
    resp = await oc.put(
        f"/api/projects/{owner._project_id}", json={"status": "deleted"}
    )
    await oc.aclose()
    assert resp.status_code == 400
    assert "deleted" in resp.text


# --------------------------------------------------------------------------- #
# ``code`` is freely editable — the only rules are slug, length and uniqueness
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_duplicate_code_is_a_conflict(app, db):
    owner = await _make_user(db, "owner@kactus.io", "Owner")
    oc = await _client(app, "owner@kactus.io", project_id=owner._project_id)
    await oc.post("/api/projects", json={"name": "Team", "code": "team-x"})

    # Rename the personal project onto the code the new one holds.
    resp = await oc.put(f"/api/projects/{owner._project_id}", json={"code": "team-x"})
    await oc.aclose()
    assert resp.status_code == 409
    # The field is named in ``data`` so the form can put the message under it.
    assert resp.json()["data"]["code"] == "team-x"


@pytest.mark.asyncio
async def test_code_of_soft_deleted_project_stays_taken(app, db):
    """The real regression: a deleted holder still reserves the code.

    ``ix_projects_code`` has no partial predicate, so the row keeps the code even
    though the soft-delete filter hides it from every ordinary read. Before the
    explicit ``skip_deleted_filter`` lookup this reached the database and came
    back as an unhandled ``IntegrityError`` — a 500.
    """
    owner = await _make_user(db, "owner@kactus.io", "Owner")
    oc = await _client(app, "owner@kactus.io", project_id=owner._project_id)
    created = await oc.post("/api/projects", json={"name": "Team", "code": "team-x"})
    dead_id = int(created.json()["data"]["id"])

    async with db.get_session() as session:
        project = await ProjectService.get_by_id(session, dead_id)
        await ProjectService.delete(session, project)

    renamed = await oc.put(
        f"/api/projects/{owner._project_id}", json={"code": "team-x"}
    )
    recreated = await oc.post("/api/projects", json={"name": "Again", "code": "team-x"})
    await oc.aclose()
    assert renamed.status_code == 409, renamed.text
    assert recreated.status_code == 409, recreated.text


@pytest.mark.asyncio
async def test_resubmitting_own_code_is_not_a_conflict(app, db):
    """The edit form posts every field, so most saves re-send the same code."""
    owner = await _make_user(db, "owner@kactus.io", "Owner")
    oc = await _client(app, "owner@kactus.io", project_id=owner._project_id)
    resp = await oc.put(
        f"/api/projects/{owner._project_id}",
        json={"name": "Renamed", "code": f"user-{owner.id}"},
    )
    await oc.aclose()
    assert resp.status_code == 200
    assert resp.json()["data"]["name"] == "Renamed"


@pytest.mark.asyncio
@pytest.mark.parametrize("code", ["x" * 51, "Team X", "TEAM-X", "team_x", ""])
async def test_invalid_code_is_rejected(app, db, code):
    """Length and slug are enforced server-side, not only in the zod schema.

    An over-long code is a ``StringDataRightTruncation`` on Postgres (a 500) and
    is silently accepted by the SQLite the tests run on — so the check has to be
    in the service, where both back ends behave the same.
    """
    owner = await _make_user(db, "owner@kactus.io", "Owner")
    oc = await _client(app, "owner@kactus.io", project_id=owner._project_id)
    resp = await oc.put(f"/api/projects/{owner._project_id}", json={"code": code})
    await oc.aclose()
    assert resp.status_code == 400, resp.text


@pytest.mark.asyncio
async def test_integrity_error_is_reported_as_conflict(app, db, monkeypatch):
    """The pre-check exists for the message; this is what closes the race.

    Two concurrent writers both pass the SELECT and one loses at the index. The
    no-op monkeypatch reproduces that without threads.
    """
    from kactus_common.project import service as service_mod

    owner = await _make_user(db, "owner@kactus.io", "Owner")
    oc = await _client(app, "owner@kactus.io", project_id=owner._project_id)
    await oc.post("/api/projects", json={"name": "Team", "code": "team-x"})

    async def _no_op(session, code, *, exclude_id=None):  # noqa: ANN001, ANN202
        return None

    monkeypatch.setattr(service_mod, "_assert_code_available", _no_op)

    clash = await oc.post("/api/projects", json={"name": "Clash", "code": "team-x"})
    assert clash.status_code == 409, clash.text

    # The rollback ran: without it the session stays errored and the next
    # statement fails with PendingRollbackError instead of answering.
    monkeypatch.undo()
    listed = await oc.get("/api/projects")
    await oc.aclose()
    assert listed.status_code == 200


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
