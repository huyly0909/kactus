"""Project CRUD API — create, read, update, delete projects + member management."""

from __future__ import annotations

from fastapi import Request
from kactus_common.audit import audit
from kactus_common.authorization.casbin_service import get_casbin_service
from kactus_common.authorization.const import PermissionAct
from kactus_common.exceptions import (
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from kactus_common.project.const import DefaultRole, ProjectPermission
from kactus_common.project.schema import (
    AddMemberRequest,
    AssignOwnerRequest,
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


async def _require(
    session: AsyncSession,
    request: Request,
    project_id: int,
    act: PermissionAct,
) -> str:
    """Enforce a project permission against the **path** project.

    Deliberately not ``@permission``: that decorator resolves the caller's role in
    ``request.state.project_id`` — the *cookie* project — while every handler here
    operates on the project named in the path, and ``Project`` is not
    ``ProjectScopedMixin`` so nothing else narrows it. Your role in the project
    you happen to have selected must not authorise you against a different one:
    the projects list lets you open and edit projects that are not the active one,
    so path and cookie routinely disagree.
    """
    role = await _actor_role(session, request, project_id)
    if not role:
        raise PermissionDeniedError("You are not a member of this project")
    if not get_casbin_service().enforce(role, ProjectPermission.project, act):
        raise PermissionDeniedError("Insufficient permissions")
    return role


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
    return await ProjectService.build_schema(session, project, viewer_id=user.id)


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

    items = await ProjectService.build_schemas(session, projects, viewer_id=user.id)
    return Pagination(total=len(items), items=items)


@router.get("/{project_id}")
@provide_session
async def get_project(
    project_id: int,
    request: Request,
    session: AsyncSession,
) -> ProjectSchema:
    """Get a project by ID."""
    await _require(session, request, project_id, PermissionAct.read)
    project = await ProjectService.get_or_404(session, project_id)
    return await ProjectService.build_schema(
        session, project, viewer_id=request.state.user.id
    )


@router.put("/{project_id}")
@provide_session
async def update_project(
    project_id: int,
    body: ProjectUpdateRequest,
    request: Request,
    session: AsyncSession,
) -> ProjectSchema:
    """Update a project (including archive/restore via ``status``)."""
    await _require(session, request, project_id, PermissionAct.write)
    project = await ProjectService.get_or_404(session, project_id)
    project = await ProjectService.update(
        session,
        project,
        name=body.name,
        code=body.code,
        description=body.description,
        status=body.status,
    )
    audit("project.update", "project", project.id, meta={"status": body.status})
    return await ProjectService.build_schema(
        session, project, viewer_id=request.state.user.id
    )


@router.delete("/{project_id}")
@provide_session
async def delete_project(
    project_id: int,
    request: Request,
    session: AsyncSession,
) -> dict:
    """Logical delete a project."""
    await _require(session, request, project_id, PermissionAct.manage)
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
@provide_session
async def list_members(
    project_id: int,
    request: Request,
    session: AsyncSession,
) -> Pagination[ProjectMemberDetailSchema]:
    """List the project's members with their email/name."""
    await _require(session, request, project_id, PermissionAct.read)
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
@provide_session
async def add_member(
    project_id: int,
    body: AddMemberRequest,
    request: Request,
    session: AsyncSession,
) -> ProjectMemberDetailSchema:
    """Invite an existing user to the project by exact email."""
    actor = await _require(session, request, project_id, PermissionAct.write)
    role = _validate_role(body.role)
    if role == DefaultRole.OWNER.value and actor != DefaultRole.OWNER.value:
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


@router.post("/{project_id}/owner")
@provide_session
async def assign_project_owner(
    project_id: int,
    body: AssignOwnerRequest,
    request: Request,
    session: AsyncSession,
) -> ProjectMemberDetailSchema:
    """Give an existing user OWNER on this project, adding them if needed.

    Distinct from ``POST /members`` with ``role=owner``, which fails once the
    user is already a member: this is the repair path for a project whose OWNER
    row was lost, where the user may or may not still be a member and there may
    be **no** members at all to promote. Additive — the sitting owner keeps the
    role, so handing ownership over stays "assign B, then demote A".

    Only an OWNER may grant OWNER, exactly as in ``update_member_role``. A
    superuser passes because ``_actor_role`` reports them as OWNER, which is
    what makes an ownerless project repairable from the UI at all.
    """
    actor = await _require(session, request, project_id, PermissionAct.write)
    if actor != DefaultRole.OWNER.value:
        raise PermissionDeniedError("Only an owner can grant the owner role")

    user = await UserService.get_by_email(session, body.email.strip())
    if user is None:
        # Generic message — do not confirm whether the email exists.
        raise NotFoundError("No registered user with that email")

    member = await ProjectService.assign_owner(
        session, project_id=project_id, user_id=user.id
    )
    audit("project.owner.assign", "project", project_id, meta={"user_id": user.id})
    return ProjectMemberDetailSchema(
        id=member.id,
        project_id=member.project_id,
        user_id=member.user_id,
        role=member.role,
        email=user.email,
        name=user.name,
    )


@router.patch("/{project_id}/members/{user_id}")
@provide_session
async def update_member_role(
    project_id: int,
    user_id: int,
    body: UpdateMemberRoleRequest,
    request: Request,
    session: AsyncSession,
) -> ProjectMemberDetailSchema:
    """Change a member's role (only an OWNER may grant/revoke OWNER)."""
    actor = await _require(session, request, project_id, PermissionAct.write)
    role = _validate_role(body.role)
    current = await ProjectService.get_member_role(
        session, project_id=project_id, user_id=user_id
    )
    if DefaultRole.OWNER.value in (role, current) and actor != DefaultRole.OWNER.value:
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
@provide_session
async def remove_member(
    project_id: int,
    user_id: int,
    request: Request,
    session: AsyncSession,
) -> MessageResponse:
    """Remove a member (only an OWNER may remove an OWNER; last OWNER protected)."""
    actor = await _require(session, request, project_id, PermissionAct.write)
    current = await ProjectService.get_member_role(
        session, project_id=project_id, user_id=user_id
    )
    if current == DefaultRole.OWNER.value and actor != DefaultRole.OWNER.value:
        raise PermissionDeniedError("Only an owner can remove an owner")

    await ProjectService.remove_member(session, project_id=project_id, user_id=user_id)
    audit("project.member.remove", "project", project_id, meta={"user_id": user_id})
    return MessageResponse(message="removed")
