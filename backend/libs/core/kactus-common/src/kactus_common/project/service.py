"""Project service — database operations for projects and members."""

from __future__ import annotations

import time

from kactus_common.exceptions import ConflictError, NotFoundError
from sqlalchemy.ext.asyncio import AsyncSession

from .const import PERSONAL_PROJECT_NAME, DefaultRole
from .model import Project, ProjectMember


class ProjectService:
    """Stateless database operations for Project and ProjectMember."""

    # -------------------------------------------------------------------
    # Project CRUD
    # -------------------------------------------------------------------

    @staticmethod
    async def create(
        session: AsyncSession,
        *,
        name: str,
        code: str,
        description: str | None = None,
        creator_id: int,
    ) -> Project:
        """Create a new project and assign the creator as owner."""
        existing = await Project.first(session, code=code)
        if existing:
            raise ConflictError(
                f"Project with code '{code}' already exists",
                data={"code": code},
            )

        project = Project.init(
            name=name,
            code=code,
            description=description,
            created_by=creator_id,
        )
        session.add(project)
        await session.flush()

        # Auto-assign creator as owner
        member = ProjectMember.init(
            project_id=project.id,
            user_id=creator_id,
            role=DefaultRole.OWNER,
        )
        session.add(member)
        await session.commit()
        await session.refresh(project)
        return project

    @staticmethod
    async def ensure_personal_project(session: AsyncSession, *, user) -> Project | None:
        """Ensure a non-admin user has their personal project (idempotent).

        Superusers get none — they hold full cross-project access already and act
        as operators, not as regular project members. Idempotent via the
        deterministic ``user-<id>`` code, so it is safe to call on every user
        creation and to re-run in the backfill.
        """
        if user.is_superuser:
            return None
        code = f"user-{user.id}"
        existing = await Project.first(session, code=code)
        if existing:
            return existing
        return await ProjectService.create(
            session,
            name=PERSONAL_PROJECT_NAME,
            code=code,
            description="Personal project",
            creator_id=user.id,
        )

    @staticmethod
    async def get_by_id(session: AsyncSession, project_id: int) -> Project | None:
        """Find a project by primary key."""
        return await Project.get(session, project_id)

    @staticmethod
    async def get_or_404(session: AsyncSession, project_id: int) -> Project:
        """Find a project by primary key or raise NotFoundError."""
        return await Project.get_or_404(session, project_id)

    @staticmethod
    async def update(
        session: AsyncSession,
        project: Project,
        *,
        name: str | None = None,
        code: str | None = None,
        description: str | None = None,
    ) -> Project:
        """Update project fields."""
        if code and code != project.code:
            existing = await Project.first(session, code=code)
            if existing:
                raise ConflictError(
                    f"Project with code '{code}' already exists",
                    data={"code": code},
                )

        if name is not None:
            project.name = name
        if code is not None:
            project.code = code
        if description is not None:
            project.description = description

        await project.save(session)
        return project

    @staticmethod
    async def delete(session: AsyncSession, project: Project) -> None:
        """Logical delete a project."""
        project.deleted_timestamp = int(time.time())
        await project.save(session)

    @staticmethod
    async def list_all(session: AsyncSession) -> list[Project]:
        """List all active projects (admin use)."""
        return await Project.all(session)

    # -------------------------------------------------------------------
    # User's projects
    # -------------------------------------------------------------------

    @staticmethod
    async def get_user_projects(session: AsyncSession, user_id: int) -> list[Project]:
        """Get all projects a user is a member of."""
        from sqlalchemy import select

        stmt = (
            select(Project)
            .join(
                ProjectMember,
                ProjectMember.project_id == Project.id,
            )
            .where(ProjectMember.user_id == user_id)
        )
        result = await session.scalars(stmt)
        return list(result.all())

    # -------------------------------------------------------------------
    # Member management
    # -------------------------------------------------------------------

    @staticmethod
    async def add_member(
        session: AsyncSession,
        *,
        project_id: int,
        user_id: int,
        role: str = DefaultRole.MEMBER,
    ) -> ProjectMember:
        """Add a user to a project."""
        existing = await ProjectMember.first(
            session, project_id=project_id, user_id=user_id
        )
        if existing:
            raise ConflictError(
                "User is already a member of this project",
                data={"project_id": project_id, "user_id": user_id},
            )

        member = ProjectMember.init(
            project_id=project_id,
            user_id=user_id,
            role=role,
        )
        session.add(member)
        await session.commit()
        await session.refresh(member)
        return member

    @staticmethod
    async def count_owners(session: AsyncSession, project_id: int) -> int:
        """Number of OWNER members in a project."""
        owners = await ProjectMember.all(
            session, project_id=project_id, role=DefaultRole.OWNER
        )
        return len(owners)

    @staticmethod
    async def remove_member(
        session: AsyncSession,
        *,
        project_id: int,
        user_id: int,
    ) -> None:
        """Remove a user from a project.

        Refuses to remove the last OWNER — a project must always have one.
        """
        member = await ProjectMember.first(
            session, project_id=project_id, user_id=user_id
        )
        if not member:
            raise NotFoundError("Member not found in this project")
        if (
            member.role == DefaultRole.OWNER
            and await ProjectService.count_owners(session, project_id) <= 1
        ):
            raise ConflictError("Cannot remove the last owner of a project")
        await member.delete(session)

    @staticmethod
    async def get_members(
        session: AsyncSession, project_id: int
    ) -> list[ProjectMember]:
        """Get all members of a project."""
        return await ProjectMember.all(session, project_id=project_id)

    @staticmethod
    async def get_member_role(
        session: AsyncSession, *, project_id: int, user_id: int
    ) -> str | None:
        """Get the role of a user in a project, or None if not a member."""
        member = await ProjectMember.first(
            session, project_id=project_id, user_id=user_id
        )
        return member.role if member else None

    @staticmethod
    async def update_member_role(
        session: AsyncSession,
        *,
        project_id: int,
        user_id: int,
        role: str,
    ) -> ProjectMember:
        """Update a member's role in a project."""
        member = await ProjectMember.first(
            session, project_id=project_id, user_id=user_id
        )
        if not member:
            raise NotFoundError("Member not found in this project")
        # Demoting the last owner would leave the project ownerless.
        if (
            member.role == DefaultRole.OWNER
            and role != DefaultRole.OWNER
            and await ProjectService.count_owners(session, project_id) <= 1
        ):
            raise ConflictError("Cannot demote the last owner of a project")
        member.role = role
        await member.save(session)
        return member
