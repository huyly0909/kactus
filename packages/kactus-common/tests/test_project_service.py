"""Tests for ProjectService — CRUD, membership, and edge cases.

Uses in-memory SQLite (aiosqlite) so no external DB required.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from kactus_common.database.oltp.models import Base
from kactus_common.database.oltp.session import DatabaseSessionManager
from kactus_common.exceptions import ConflictError, NotFoundError
from kactus_common.project.const import DefaultRole
from kactus_common.project.model import Project, ProjectMember
from kactus_common.project.service import ProjectService
from kactus_common.user.model import User, UserSession

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


@pytest_asyncio.fixture(autouse=True)
async def clean_tables(db):
    yield
    async with db.get_session() as session:
        for table in (ProjectMember, Project, UserSession, User):
            await session.execute(table.__table__.delete())
        await session.commit()


@pytest_asyncio.fixture
async def user(db) -> User:
    async with db.get_session() as session:
        u = User.init(
            email="alice@kactus.io",
            username="alice",
            password_hash="Pass123!",
            name="Alice",
            status="active",
        )
        session.add(u)
        await session.commit()
        await session.refresh(u)
    return u


@pytest_asyncio.fixture
async def user2(db) -> User:
    async with db.get_session() as session:
        u = User.init(
            email="bob@kactus.io",
            username="bob",
            password_hash="Pass123!",
            name="Bob",
            status="active",
        )
        session.add(u)
        await session.commit()
        await session.refresh(u)
    return u


# ---------------------------------------------------------------------------
# Project CRUD
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_project_success(db, user):
    async with db.get_session() as session:
        project = await ProjectService.create(
            session, name="My Project", code="MP-01", description="test", creator_id=user.id
        )
    assert project.name == "My Project"
    assert project.code == "MP-01"
    assert project.description == "test"

    # Creator should be auto-assigned as owner
    async with db.get_session() as session:
        role = await ProjectService.get_member_role(session, project_id=project.id, user_id=user.id)
    assert role == DefaultRole.OWNER


@pytest.mark.asyncio
async def test_create_project_duplicate_code(db, user):
    async with db.get_session() as session:
        await ProjectService.create(session, name="P1", code="DUP", creator_id=user.id)

    with pytest.raises(ConflictError):
        async with db.get_session() as session:
            await ProjectService.create(session, name="P2", code="DUP", creator_id=user.id)


@pytest.mark.asyncio
async def test_get_by_id(db, user):
    async with db.get_session() as session:
        project = await ProjectService.create(session, name="P", code="GET1", creator_id=user.id)

    async with db.get_session() as session:
        found = await ProjectService.get_by_id(session, project.id)
    assert found is not None
    assert found.code == "GET1"


@pytest.mark.asyncio
async def test_get_by_id_not_found(db):
    async with db.get_session() as session:
        found = await ProjectService.get_by_id(session, 999999999)
    assert found is None


@pytest.mark.asyncio
async def test_get_or_404_raises(db):
    with pytest.raises(NotFoundError):
        async with db.get_session() as session:
            await ProjectService.get_or_404(session, 999999999)


@pytest.mark.asyncio
async def test_update_project_name(db, user):
    async with db.get_session() as session:
        project = await ProjectService.create(session, name="Old", code="UPD1", creator_id=user.id)

    async with db.get_session() as session:
        project = await ProjectService.get_or_404(session, project.id)
        updated = await ProjectService.update(session, project, name="New")
    assert updated.name == "New"


@pytest.mark.asyncio
async def test_update_project_code_conflict(db, user):
    async with db.get_session() as session:
        await ProjectService.create(session, name="A", code="CODE-A", creator_id=user.id)
    async with db.get_session() as session:
        p2 = await ProjectService.create(session, name="B", code="CODE-B", creator_id=user.id)

    with pytest.raises(ConflictError):
        async with db.get_session() as session:
            p2 = await ProjectService.get_or_404(session, p2.id)
            await ProjectService.update(session, p2, code="CODE-A")


@pytest.mark.asyncio
async def test_delete_sets_deleted_timestamp(db, user):
    async with db.get_session() as session:
        project = await ProjectService.create(session, name="Del", code="DEL1", creator_id=user.id)
        pid = project.id

    async with db.get_session() as session:
        project = await ProjectService.get_or_404(session, pid)
        await ProjectService.delete(session, project)

    # Should no longer appear in normal queries (LogicalDeleteMixin filters)
    async with db.get_session() as session:
        found = await ProjectService.get_by_id(session, pid)
    assert found is None


@pytest.mark.asyncio
async def test_list_all(db, user):
    async with db.get_session() as session:
        await ProjectService.create(session, name="A", code="LA1", creator_id=user.id)
    async with db.get_session() as session:
        await ProjectService.create(session, name="B", code="LA2", creator_id=user.id)

    async with db.get_session() as session:
        projects = await ProjectService.list_all(session)
    assert len(projects) >= 2


# ---------------------------------------------------------------------------
# User projects
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_user_projects(db, user, user2):
    async with db.get_session() as session:
        p1 = await ProjectService.create(session, name="P1", code="UP1", creator_id=user.id)
    async with db.get_session() as session:
        await ProjectService.create(session, name="P2", code="UP2", creator_id=user2.id)

    # user is only a member of P1
    async with db.get_session() as session:
        projects = await ProjectService.get_user_projects(session, user.id)
    codes = [p.code for p in projects]
    assert "UP1" in codes
    assert "UP2" not in codes


# ---------------------------------------------------------------------------
# Membership
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_add_member(db, user, user2):
    async with db.get_session() as session:
        project = await ProjectService.create(session, name="M", code="MEM1", creator_id=user.id)

    async with db.get_session() as session:
        member = await ProjectService.add_member(
            session, project_id=project.id, user_id=user2.id, role=DefaultRole.MEMBER
        )
    assert member.role == DefaultRole.MEMBER


@pytest.mark.asyncio
async def test_add_member_duplicate_raises(db, user, user2):
    async with db.get_session() as session:
        project = await ProjectService.create(session, name="D", code="DM1", creator_id=user.id)

    async with db.get_session() as session:
        await ProjectService.add_member(session, project_id=project.id, user_id=user2.id)

    with pytest.raises(ConflictError):
        async with db.get_session() as session:
            await ProjectService.add_member(session, project_id=project.id, user_id=user2.id)


@pytest.mark.asyncio
async def test_remove_member(db, user, user2):
    async with db.get_session() as session:
        project = await ProjectService.create(session, name="R", code="RM1", creator_id=user.id)
    async with db.get_session() as session:
        await ProjectService.add_member(session, project_id=project.id, user_id=user2.id)

    async with db.get_session() as session:
        await ProjectService.remove_member(session, project_id=project.id, user_id=user2.id)

    async with db.get_session() as session:
        role = await ProjectService.get_member_role(session, project_id=project.id, user_id=user2.id)
    assert role is None


@pytest.mark.asyncio
async def test_remove_member_not_found(db, user):
    async with db.get_session() as session:
        project = await ProjectService.create(session, name="RN", code="RNF1", creator_id=user.id)

    with pytest.raises(NotFoundError):
        async with db.get_session() as session:
            await ProjectService.remove_member(session, project_id=project.id, user_id=999999999)


@pytest.mark.asyncio
async def test_get_member_role(db, user):
    async with db.get_session() as session:
        project = await ProjectService.create(session, name="GR", code="GR1", creator_id=user.id)

    async with db.get_session() as session:
        role = await ProjectService.get_member_role(session, project_id=project.id, user_id=user.id)
    assert role == DefaultRole.OWNER


@pytest.mark.asyncio
async def test_get_member_role_non_member(db, user):
    async with db.get_session() as session:
        project = await ProjectService.create(session, name="NM", code="NM1", creator_id=user.id)

    async with db.get_session() as session:
        role = await ProjectService.get_member_role(session, project_id=project.id, user_id=999999999)
    assert role is None


@pytest.mark.asyncio
async def test_update_member_role(db, user, user2):
    async with db.get_session() as session:
        project = await ProjectService.create(session, name="UR", code="UR1", creator_id=user.id)
    async with db.get_session() as session:
        await ProjectService.add_member(session, project_id=project.id, user_id=user2.id)

    async with db.get_session() as session:
        member = await ProjectService.update_member_role(
            session, project_id=project.id, user_id=user2.id, role=DefaultRole.MANAGER
        )
    assert member.role == DefaultRole.MANAGER
