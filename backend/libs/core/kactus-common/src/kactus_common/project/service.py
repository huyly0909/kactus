"""Project service — database operations for projects and members."""

from __future__ import annotations

import time

from kactus_common.exceptions import ConflictError, NotFoundError, ValidationError
from kactus_common.user.model import User
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from .const import (
    PERSONAL_PROJECT_NAME,
    PROJECT_CODE_MAX_LENGTH,
    PROJECT_CODE_PATTERN,
    DefaultRole,
    ProjectStatus,
)
from .model import Project, ProjectMember
from .schema import ProjectSchema

_VALID_STATUSES = {s.value for s in ProjectStatus}


def _validate_code(code: str) -> None:
    """Reject a ``code`` the column or the slug rule cannot hold.

    Raised from the service rather than declared as a Pydantic constraint on the
    request schema: no ``RequestValidationError`` handler is installed, so a
    constraint failure would return FastAPI's default 422 body, which carries no
    ``message`` field — and that is exactly what the frontend reads to show the
    user why their input was refused.
    """
    if not code:
        raise ValidationError("Project code is required", data={"code": code})
    if len(code) > PROJECT_CODE_MAX_LENGTH:
        raise ValidationError(
            f"Project code must be at most {PROJECT_CODE_MAX_LENGTH} characters",
            data={"code": code, "max_length": PROJECT_CODE_MAX_LENGTH},
        )
    if not PROJECT_CODE_PATTERN.match(code):
        raise ValidationError(
            "Project code may contain only lowercase letters, numbers and hyphens",
            data={"code": code},
        )


async def _assert_code_available(
    session: AsyncSession, code: str, *, exclude_id: int | None = None
) -> None:
    """Raise :class:`ConflictError` if any project already holds ``code``.

    ``skip_deleted_filter`` is the point of this function. ``Project.first()``
    goes through the global soft-delete filter, so a code held by a deleted
    project reads as free — while ``ix_projects_code`` is a *plain* unique index
    with no partial predicate and still reserves it. Without this the write
    reaches the database and dies as an unhandled ``IntegrityError`` (a 500)
    instead of a conflict the caller can act on.

    Hence "already in use" and not "already exists": the holder may be a project
    the user cannot see, so pointing them at it would be a lie.
    """
    stmt = (
        select(Project.id)
        .where(Project.code == code)
        .execution_options(skip_deleted_filter=True)
    )
    if exclude_id is not None:
        stmt = stmt.where(Project.id != exclude_id)
    existing = await session.scalar(stmt.limit(1))
    if existing is not None:
        raise ConflictError(
            f"Project code '{code}' is already in use", data={"code": code}
        )


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
        _validate_code(code)
        await _assert_code_available(session, code)

        project = Project.init(
            name=name,
            code=code,
            description=description,
            created_by=creator_id,
        )
        session.add(project)

        try:
            await session.flush()

            # Auto-assign creator as owner
            member = ProjectMember.init(
                project_id=project.id,
                user_id=creator_id,
                role=DefaultRole.OWNER,
            )
            session.add(member)
            await session.commit()
        except IntegrityError as exc:
            # The check above lost a race with a concurrent create. Roll back
            # first — an errored session refuses every later statement with a
            # confusing PendingRollbackError — then report the real conflict.
            await session.rollback()
            raise ConflictError(
                f"Project code '{code}' is already in use", data={"code": code}
            ) from exc

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
        # ``skip_deleted_filter`` for the same reason as ``_assert_code_available``,
        # and it has to match it: a *soft-deleted* personal project still holds
        # the code in the plain unique index, so without this the lookup reads
        # "free", falls through to ``create``, and dies on the conflict check —
        # leaving the user permanently unable to get their project back.
        existing = await session.scalar(
            select(Project)
            .where(Project.code == code)
            .execution_options(skip_deleted_filter=True)
            .limit(1)
        )
        if existing:
            if existing.is_deleted:
                # "Ensure" has to mean the user ends up *with* a project. The
                # backfill moves their portfolios/channels into whatever this
                # returns, so handing back a deleted row would quietly park
                # their data somewhere invisible.
                existing.deleted_timestamp = 0
                await existing.save(session)
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
        status: str | None = None,
    ) -> Project:
        """Update project fields.

        ``status`` archives or restores the project — it is the only writer of
        :class:`ProjectStatus`, and the list UI hides non-active projects by
        default.
        """
        # Re-submitting the unchanged code is a no-op, not a self-conflict — the
        # form posts every field, so most saves land here.
        if code is not None and code != project.code:
            _validate_code(code)
            await _assert_code_available(session, code, exclude_id=project.id)

        if status is not None and status not in _VALID_STATUSES:
            raise ValidationError(
                f"Invalid project status '{status}'",
                data={"valid": sorted(_VALID_STATUSES)},
            )

        if name is not None:
            project.name = name
        if code is not None:
            project.code = code
        if description is not None:
            project.description = description
        if status is not None:
            project.status = status

        try:
            await project.save(session)
        except IntegrityError as exc:
            await session.rollback()
            raise ConflictError(
                f"Project code '{project.code}' is already in use",
                data={"code": project.code},
            ) from exc
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
    # Read-model assembly
    # -------------------------------------------------------------------

    @staticmethod
    async def build_schemas(
        session: AsyncSession,
        projects: list[Project],
        *,
        viewer_id: int | None,
    ) -> list[ProjectSchema]:
        """Serialise projects with their owner, member count and viewer's role.

        Three queries total regardless of how many projects are passed —
        deliberately *not* the per-row ``UserService.get_by_id`` loop used by the
        members endpoint, which would be an N+1 on the main project list.

        ``viewer_id=None`` (admin listing) leaves ``my_role`` unset: "my role" is
        meaningless for an operator listing projects they are not a member of.
        """
        if not projects:
            return []

        project_ids = [p.id for p in projects]

        # 1. member counts, grouped
        count_rows = await session.execute(
            select(ProjectMember.project_id, func.count())
            .where(ProjectMember.project_id.in_(project_ids))
            .group_by(ProjectMember.project_id)
        )
        counts: dict[int, int] = dict(count_rows.all())  # type: ignore[arg-type]

        # 2. every membership we care about: the OWNER rows (for the owner
        #    column) and the viewer's own rows (for my_role). One query, because
        #    both are ProjectMember rows over the same project set.
        member_rows = await session.scalars(
            select(ProjectMember).where(
                ProjectMember.project_id.in_(project_ids),
                (ProjectMember.role == DefaultRole.OWNER.value)
                | (ProjectMember.user_id == (viewer_id or 0)),
            )
        )
        owner_of: dict[int, int] = {}
        my_role_of: dict[int, str] = {}
        for m in member_rows.all():
            if m.role == DefaultRole.OWNER.value:
                owner_of.setdefault(m.project_id, m.user_id)
            if viewer_id is not None and m.user_id == viewer_id:
                my_role_of[m.project_id] = m.role

        # Everything resolved so far is a *real* owner. Remember that before the
        # fallback below blurs the two — ``has_owner`` is the only thing telling
        # the UI apart an owned project from a repaired-looking one.
        owned_ids = set(owner_of)

        # A project with no OWNER row (legacy/imported data, or a membership
        # deleted out of band — the schema has no foreign keys) still has a
        # creator worth naming. It is shown, but never *as* the owner.
        for p in projects:
            if p.id not in owner_of and p.created_by is not None:
                owner_of[p.id] = p.created_by

        # 3. resolve those owner ids to a name/email
        users_by_id: dict[int, User] = {}
        if owner_of:
            user_rows = await session.scalars(
                select(User).where(User.id.in_(set(owner_of.values())))
            )
            users_by_id = {u.id: u for u in user_rows.all()}

        items: list[ProjectSchema] = []
        for p in projects:
            owner_id = owner_of.get(p.id)
            owner = users_by_id.get(owner_id) if owner_id is not None else None
            items.append(
                ProjectSchema(
                    id=p.id,
                    name=p.name,
                    code=p.code,
                    description=p.description,
                    status=p.status,
                    created_by=p.created_by,
                    create_time=p.create_time,
                    owner_id=owner_id,
                    owner_name=owner.name if owner else None,
                    owner_email=owner.email if owner else None,
                    has_owner=p.id in owned_ids,
                    member_count=counts.get(p.id, 0),
                    my_role=my_role_of.get(p.id),
                )
            )
        return items

    @staticmethod
    async def build_schema(
        session: AsyncSession,
        project: Project,
        *,
        viewer_id: int | None,
    ) -> ProjectSchema:
        """Single-project counterpart of :meth:`build_schemas`."""
        items = await ProjectService.build_schemas(
            session, [project], viewer_id=viewer_id
        )
        return items[0]

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

    # -------------------------------------------------------------------
    # Ownership
    #
    # A project must always have at least one OWNER member — that row *is* the
    # ownership record, there is no ``projects.owner_id`` column. ``create``
    # writes it in the same transaction as the project, and ``remove_member`` /
    # ``update_member_role`` refuse to drop or demote the last one, so the only
    # remaining way to lose it is an out-of-band row deletion (the schema has no
    # foreign keys). The helpers below detect that state, repair it, and stop
    # user deactivation from causing it.
    # -------------------------------------------------------------------

    @staticmethod
    async def owner_ids(session: AsyncSession, project_id: int) -> list[int]:
        """User ids holding OWNER here. Empty means the project is unassigned."""
        stmt = select(ProjectMember.user_id).where(
            ProjectMember.project_id == project_id,
            ProjectMember.role == DefaultRole.OWNER.value,
        )
        return list((await session.scalars(stmt)).all())

    @staticmethod
    async def sole_owner_project_ids(session: AsyncSession, user_id: int) -> list[int]:
        """Live projects where ``user_id`` is the **only** owner.

        One grouped query rather than a ``count_owners`` loop, because the caller
        (user deactivation) has no project in hand to loop over. The join to
        ``Project`` is what applies the global soft-delete filter — an archived
        or deleted project must not block deactivating its owner.
        """
        mine = select(ProjectMember.project_id).where(
            ProjectMember.user_id == user_id,
            ProjectMember.role == DefaultRole.OWNER.value,
        )
        stmt = (
            select(ProjectMember.project_id)
            .join(Project, Project.id == ProjectMember.project_id)
            .where(
                ProjectMember.role == DefaultRole.OWNER.value,
                ProjectMember.project_id.in_(mine),
            )
            .group_by(ProjectMember.project_id)
            .having(func.count() == 1)
        )
        return list((await session.scalars(stmt)).all())

    @staticmethod
    async def assign_owner(
        session: AsyncSession, *, project_id: int, user_id: int
    ) -> ProjectMember:
        """Make ``user_id`` an OWNER, adding the membership when absent.

        The repair path for a project with **zero** members:
        ``update_member_role`` cannot help there because there is nobody to
        promote. Idempotent, and deliberately additive — it never demotes the
        sitting owner, since co-owners are legal and handing ownership over is
        "promote B, then demote A" (safe in that order thanks to the last-owner
        guard on :meth:`update_member_role`).
        """
        member = await ProjectMember.first(
            session, project_id=project_id, user_id=user_id
        )
        if member is None:
            return await ProjectService.add_member(
                session,
                project_id=project_id,
                user_id=user_id,
                role=DefaultRole.OWNER,
            )
        if member.role != DefaultRole.OWNER.value:
            member.role = DefaultRole.OWNER.value
            await member.save(session)
        return member

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
