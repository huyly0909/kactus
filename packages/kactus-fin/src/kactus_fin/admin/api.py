"""Admin API — superuser-only endpoints for user and project management."""

from __future__ import annotations

import secrets
import string

from fastapi import Request
from kactus_common.authorization.casbin_service import get_casbin_service
from kactus_common.exceptions import NotFoundError
from kactus_common.project.schema import ProjectSchema
from kactus_common.project.service import ProjectService
from kactus_common.router import KactusAPIRouter
from kactus_common.schemas import Pagination
from kactus_common.user.model import User
from kactus_common.user.schema import UserInfo
from kactus_common.user.service import UserService
from kactus_fin.admin.schema import (
    AdminCreateUserRequest,
    ResetPasswordResponse,
    UpdateUserRoleRequest,
)
from kactus_fin.dependencies import provide_session
from sqlalchemy.ext.asyncio import AsyncSession

router = KactusAPIRouter(prefix="/api/admin", tags=["admin"])


def _generate_random_password(length: int = 16) -> str:
    """Generate a cryptographically secure random password."""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return "".join(secrets.choice(alphabet) for _ in range(length))


# ---------------------------------------------------------------------------
# User management
# ---------------------------------------------------------------------------


@router.get("/users")
@provide_session
async def list_users(request: Request, session: AsyncSession) -> Pagination[UserInfo]:
    """List all users (admin only)."""
    users = await User.all(session)
    items = [UserInfo.model_validate(u) for u in users]
    return Pagination(total=len(items), items=items)


@router.post("/users")
@provide_session
async def create_user(
    body: AdminCreateUserRequest,
    request: Request,
    session: AsyncSession,
) -> UserInfo:
    """Create a new user (admin only)."""
    user = User.init(
        email=body.email,
        username=body.email,
        name=body.name,
        password_hash=body.password,
        is_superuser=body.is_superuser,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return UserInfo.model_validate(user)


@router.post("/users/{user_id}/reset-password")
@provide_session
async def reset_user_password(
    user_id: int,
    request: Request,
    session: AsyncSession,
) -> ResetPasswordResponse:
    """Reset a user's password with a random password (admin only)."""
    user = await UserService.get_by_id(session, user_id)
    if not user:
        raise NotFoundError("User not found")

    new_password = _generate_random_password()
    user.password_hash = new_password  # PasswordHash TypeDecorator auto-hashes
    await user.save(session)

    return ResetPasswordResponse(new_password=new_password)


@router.post("/users/{user_id}/deactivate")
@provide_session
async def deactivate_user(
    user_id: int,
    request: Request,
    session: AsyncSession,
) -> UserInfo:
    """Deactivate a user (admin only)."""
    user = await UserService.get_by_id(session, user_id)
    if not user:
        raise NotFoundError("User not found")

    user.status = "inactive"
    await user.save(session)
    return UserInfo.model_validate(user)


# ---------------------------------------------------------------------------
# User role management
# ---------------------------------------------------------------------------


@router.put("/users/{user_id}/role")
@provide_session
async def update_user_role(
    user_id: int,
    body: UpdateUserRoleRequest,
    request: Request,
    session: AsyncSession,
) -> UserInfo:
    """Update a user's superuser status (admin only)."""
    user = await UserService.get_by_id(session, user_id)
    if not user:
        raise NotFoundError("User not found")

    user.is_superuser = body.is_superuser
    await user.save(session)
    return UserInfo.model_validate(user)


# ---------------------------------------------------------------------------
# Authorization / role-permission mapping
# ---------------------------------------------------------------------------


@router.get("/authorization")
async def get_authorization(request: Request) -> dict:
    """Get all role-permission mappings (admin only)."""
    casbin_svc = get_casbin_service()
    roles = casbin_svc.get_all_roles()
    return {
        role: [
            {"permission": p, "act": a}
            for p, a in casbin_svc.get_role_permissions(role)
        ]
        for role in roles
    }


# ---------------------------------------------------------------------------
# Project management (admin sees all)
# ---------------------------------------------------------------------------


@router.get("/projects")
@provide_session
async def list_all_projects(
    request: Request,
    session: AsyncSession,
) -> Pagination[ProjectSchema]:
    """List all projects (admin only)."""
    projects = await ProjectService.list_all(session)
    items = [ProjectSchema.model_validate(p) for p in projects]
    return Pagination(total=len(items), items=items)
