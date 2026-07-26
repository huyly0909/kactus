"""Project CRUD API — create, read, update, delete projects + member management."""

from __future__ import annotations

from fastapi import Request
from kactus_common.audit import audit
from kactus_common.authorization.const import PermissionAct
from kactus_common.authorization.decorator import permission
from kactus_common.exceptions import (
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from kactus_common.project.const import DefaultRole, ProjectPermission
from kactus_common.project.schema import (
    AddMemberRequest,
    ProjectCreateRequest,
    ProjectMemberDetailSchema,
    ProjectSchema,
    ProjectUpdateRequest,
    UpdateMemberRoleRequest,
)
from kactus_common.project.service import ProjectService
from kactus_common.router import KactusAPIRouter
from kactus_common.schemas import MessageResponse, Pagination
from kactus_common.user.service import UserService
from kactus_fin.dependencies import provide_session
from sqlalchemy.ext.asyncio import AsyncSession

router = KactusAPIRouter(prefix="/api/projects", tags=["projects"])

_VALID_ROLES = {r.value for r in DefaultRole}


def _validate_role(role: str) -> str:
    if role not in _VALID_ROLES:
        raise ValidationError(
            f"Invalid role '{role}'", data={"valid": sorted(_VALID_ROLES)}
        )
    return role


async def _actor_role(session: AsyncSession, request: Request, project_id: int) -> str:
    """The acting user's role in the project (superusers act as OWNER)."""
    user = request.state.user
    if user.is_superuser:
        return DefaultRole.OWNER.value
    role = await ProjectService.get_member_role(
        session, project_id=project_id, user_id=user.id
    )
    return role or ""


@router.post("")
@provide_session
async def create_project(
    body: ProjectCreateRequest,
    request: Request,
    session: AsyncSession,
) -> ProjectSchema:
    """Create a new project. Creator is automatically assigned as owner."""
    user = request.state.user
    project = await ProjectService.create(
        session,
        name=body.name,
        code=body.code,
        description=body.description,
        creator_id=user.id,
    )
    audit("project.create", "project", project.id, meta={"code": body.code})
    return ProjectSchema.model_validate(project)


@router.get("")
@provide_session
async def list_projects(
    request: Request,
    session: AsyncSession,
) -> Pagination[ProjectSchema]:
    """List projects the current user is a member of.

    Superusers see all projects.
    """
    user = request.state.user
    if user.is_superuser:
        projects = await ProjectService.list_all(session)
    else:
        projects = await ProjectService.get_user_projects(session, user.id)

    items = [ProjectSchema.model_validate(p) for p in projects]
    return Pagination(total=len(items), items=items)


@router.get("/{project_id}")
@permission(ProjectPermission.project, PermissionAct.read)
@provide_session
async def get_project(
    project_id: int,
    request: Request,
    session: AsyncSession,
) -> ProjectSchema:
    """Get a project by ID."""
    project = await ProjectService.get_or_404(session, project_id)
    return ProjectSchema.model_validate(project)


@router.put("/{project_id}")
@permission(ProjectPermission.project, PermissionAct.write)
@provide_session
async def update_project(
    project_id: int,
    body: ProjectUpdateRequest,
    request: Request,
    session: AsyncSession,
) -> ProjectSchema:
    """Update a project."""
    project = await ProjectService.get_or_404(session, project_id)
    project = await ProjectService.update(
        session,
        project,
        name=body.name,
        code=body.code,
        description=body.description,
    )
    audit("project.update", "project", project.id)
    return ProjectSchema.model_validate(project)


@router.delete("/{project_id}")
@permission(ProjectPermission.project, PermissionAct.manage)
@provide_session
async def delete_project(
    project_id: int,
    request: Request,
    session: AsyncSession,
) -> dict:
    """Logical delete a project."""
    project = await ProjectService.get_or_404(session, project_id)
    await ProjectService.delete(session, project)
    audit("project.delete", "project", project_id)
    return {}


# --------------------------------------------------------------------------- #
# Member management
#
# All gated `write`, so OWNER + MANAGER manage members and MEMBER is read-only.
# Granting or revoking OWNER additionally requires the actor to be an OWNER, and
# the last OWNER can never be removed/demoted (enforced in ProjectService).
# There is deliberately no endpoint that lists/searches all users by email —
# invitation is by exact email only, to avoid leaking the user directory.
# --------------------------------------------------------------------------- #
@router.get("/{project_id}/members")
@permission(ProjectPermission.project, PermissionAct.read)
@provide_session
async def list_members(
    project_id: int,
    request: Request,
    session: AsyncSession,
) -> Pagination[ProjectMemberDetailSchema]:
    """List the project's members with their email/name."""
    members = await ProjectService.get_members(session, project_id)
    items: list[ProjectMemberDetailSchema] = []
    for m in members:
        user = await UserService.get_by_id(session, m.user_id)
        items.append(
            ProjectMemberDetailSchema(
                id=m.id,
                project_id=m.project_id,
                user_id=m.user_id,
                role=m.role,
                email=user.email if user else None,
                name=user.name if user else None,
            )
        )
    return Pagination(total=len(items), items=items)


@router.post("/{project_id}/members")
@permission(ProjectPermission.project, PermissionAct.write)
@provide_session
async def add_member(
    project_id: int,
    body: AddMemberRequest,
    request: Request,
    session: AsyncSession,
) -> ProjectMemberDetailSchema:
    """Invite an existing user to the project by exact email."""
    role = _validate_role(body.role)
    if role == DefaultRole.OWNER.value:
        actor = await _actor_role(session, request, project_id)
        if actor != DefaultRole.OWNER.value:
            raise PermissionDeniedError("Only an owner can grant the owner role")

    user = await UserService.get_by_email(session, body.email.strip())
    if user is None:
        # Generic message — do not confirm whether the email exists.
        raise NotFoundError("No registered user with that email")

    member = await ProjectService.add_member(
        session, project_id=project_id, user_id=user.id, role=role
    )
    audit(
        "project.member.add",
        "project",
        project_id,
        meta={"user_id": user.id, "role": role},
    )
    return ProjectMemberDetailSchema(
        id=member.id,
        project_id=member.project_id,
        user_id=member.user_id,
        role=member.role,
        email=user.email,
        name=user.name,
    )


@router.patch("/{project_id}/members/{user_id}")
@permission(ProjectPermission.project, PermissionAct.write)
@provide_session
async def update_member_role(
    project_id: int,
    user_id: int,
    body: UpdateMemberRoleRequest,
    request: Request,
    session: AsyncSession,
) -> ProjectMemberDetailSchema:
    """Change a member's role (only an OWNER may grant/revoke OWNER)."""
    role = _validate_role(body.role)
    current = await ProjectService.get_member_role(
        session, project_id=project_id, user_id=user_id
    )
    if DefaultRole.OWNER.value in (role, current):
        actor = await _actor_role(session, request, project_id)
        if actor != DefaultRole.OWNER.value:
            raise PermissionDeniedError("Only an owner can change the owner role")

    member = await ProjectService.update_member_role(
        session, project_id=project_id, user_id=user_id, role=role
    )
    audit(
        "project.member.update",
        "project",
        project_id,
        meta={"user_id": user_id, "role": role},
    )
    user = await UserService.get_by_id(session, user_id)
    return ProjectMemberDetailSchema(
        id=member.id,
        project_id=member.project_id,
        user_id=member.user_id,
        role=member.role,
        email=user.email if user else None,
        name=user.name if user else None,
    )


@router.delete("/{project_id}/members/{user_id}")
@permission(ProjectPermission.project, PermissionAct.write)
@provide_session
async def remove_member(
    project_id: int,
    user_id: int,
    request: Request,
    session: AsyncSession,
) -> MessageResponse:
    """Remove a member (only an OWNER may remove an OWNER; last OWNER protected)."""
    current = await ProjectService.get_member_role(
        session, project_id=project_id, user_id=user_id
    )
    if current == DefaultRole.OWNER.value:
        actor = await _actor_role(session, request, project_id)
        if actor != DefaultRole.OWNER.value:
            raise PermissionDeniedError("Only an owner can remove an owner")

    await ProjectService.remove_member(session, project_id=project_id, user_id=user_id)
    audit("project.member.remove", "project", project_id, meta={"user_id": user_id})
    return MessageResponse(message="removed")
