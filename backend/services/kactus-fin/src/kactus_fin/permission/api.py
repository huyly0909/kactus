"""Permission API — query current user's permissions for a project."""

from __future__ import annotations

from fastapi import Query, Request
from kactus_common.authorization.casbin_service import get_casbin_service
from kactus_common.project.service import ProjectService
from kactus_common.router import KactusAPIRouter
from kactus_fin.dependencies import provide_session
from kactus_fin.permission.schema import PermissionsResponse
from sqlalchemy.ext.asyncio import AsyncSession

router = KactusAPIRouter(prefix="/api/me", tags=["permissions"])


@router.get("/permissions")
@provide_session
async def get_my_permissions(
    request: Request,
    session: AsyncSession,
    project_id: int | None = Query(
        None, description="Project ID (falls back to cookie)"
    ),
) -> PermissionsResponse:
    """Get all permissions for the current user in a given project.

    If ``project_id`` is not provided as a query parameter, the selected
    project from the cookie is used.  If no project is selected at all,
    an empty permission list is returned.

    Superusers get all permissions.  Regular users get permissions based
    on their role in the project.
    """
    user = request.state.user
    project_id = project_id or getattr(request.state, "project_id", None)

    if project_id is None:
        return PermissionsResponse(
            permissions=[], role=None, is_superuser=user.is_superuser
        )

    casbin_svc = get_casbin_service()

    if user.is_superuser:
        all_perms = casbin_svc.get_all_permissions()
        permissions = [{"permission": p, "act": a} for p, a in all_perms]
        return PermissionsResponse(
            project_id=str(project_id),
            permissions=permissions,
            role="admin",
            is_superuser=True,
        )

    role = await ProjectService.get_member_role(
        session, project_id=project_id, user_id=user.id
    )

    if role:
        role_perms = casbin_svc.get_role_permissions(role)
        permissions = [{"permission": p, "act": a} for p, a in role_perms]
    else:
        permissions = []

    return PermissionsResponse(
        project_id=str(project_id),
        permissions=permissions,
        role=role,
        is_superuser=False,
    )
