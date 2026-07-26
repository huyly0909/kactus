"""@permission decorator — declarative endpoint-level authorization.

Usage::

    from kactus_common.authorization.decorator import permission
    from kactus_common.authorization.const import PermissionAct
    from kactus_common.project.const import ProjectPermission

    @router.put("/{project_id}")
    @permission(ProjectPermission.project, PermissionAct.write)
    @provide_session
    async def update_project(project_id: int, request: Request, session: AsyncSession):
        ...
"""

from __future__ import annotations

from functools import wraps
from typing import TYPE_CHECKING

from fastapi import Request
from kactus_common.exceptions import PermissionDeniedError

if TYPE_CHECKING:
    from kactus_common.authorization.const import Permission, PermissionAct


def permission(perm: Permission, act: PermissionAct):
    """Decorator that enforces project-scoped permission on an endpoint.

    Reads ``request.state.user`` (set by session auth) and
    ``request.state.project_id`` (set from cookie) to determine the
    user's role in the project and check the permission via Casbin.

    Superusers bypass all permission checks.

    Args:
        perm: Required permission (e.g. ``ProjectPermission.project``).
        act: Required permission act (e.g. ``PermissionAct.write``).
    """

    def decorator(fn):
        @wraps(fn)
        async def wrapper(*args, **kwargs):
            request: Request | None = kwargs.get("request")
            if request is None:
                # Try positional args — shouldn't happen with FastAPI
                for arg in args:
                    if isinstance(arg, Request):
                        request = arg
                        break

            if request is None:
                raise PermissionDeniedError(
                    "Cannot resolve request for permission check"
                )

            user = getattr(request.state, "user", None)
            if user is None:
                raise PermissionDeniedError("User not authenticated")

            # Superusers bypass all permission checks
            if user.is_superuser:
                return await fn(*args, **kwargs)

            project_id = getattr(request.state, "project_id", None)
            if project_id is None:
                raise PermissionDeniedError("No project selected")

            # Look up the user's role in this project. Use our own short-lived
            # session rather than the handler's: ``@permission`` is the outer
            # wrapper and runs *before* ``@provide_session`` injects a session, so
            # ``kwargs["session"]`` is not populated yet. A quick independent read
            # keeps the decorator order-independent (works above or below
            # ``@provide_session``).
            from kactus_common.database.oltp.session import get_db
            from kactus_common.project.service import ProjectService

            session = kwargs.get("session")
            if session is not None:
                role = await ProjectService.get_member_role(
                    session, project_id=project_id, user_id=user.id
                )
            else:
                async with get_db().get_session() as check_session:
                    role = await ProjectService.get_member_role(
                        check_session, project_id=project_id, user_id=user.id
                    )
            if not role:
                raise PermissionDeniedError("You are not a member of this project")

            # Enforce via CasbinService
            from kactus_common.authorization.casbin_service import get_casbin_service

            casbin_svc = get_casbin_service()
            if not casbin_svc.enforce(role, perm, act):
                raise PermissionDeniedError("Insufficient permissions")

            return await fn(*args, **kwargs)

        return wrapper

    return decorator
