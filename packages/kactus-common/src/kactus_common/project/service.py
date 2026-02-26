"""Project service — database operations for projects and members."""

from __future__ import annotations

import time

from kactus_common.exceptions import ConflictError, NotFoundError
from sqlalchemy.ext.asyncio import AsyncSession

from .const import DefaultRole
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
    async def remove_member(
        session: AsyncSession,
        *,
        project_id: int,
        user_id: int,
    ) -> None:
        """Remove a user from a project."""
        member = await ProjectMember.first(
            session, project_id=project_id, user_id=user_id
        )
        if not member:
            raise NotFoundError("Member not found in this project")
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
        member.role = role
        await member.save(session)
        return member
