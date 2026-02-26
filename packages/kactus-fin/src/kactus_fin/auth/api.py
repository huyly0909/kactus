"""Auth API — login, logout, get current user."""

from __future__ import annotations

from fastapi import Request, Response
from kactus_common.crypto import verify_password
from kactus_common.exceptions import AuthenticationError
from kactus_common.router import KactusAPIRouter
from kactus_common.user.schema import LoginRequest, LoginResponse, UserInfo
from kactus_common.user.service import UserService
from kactus_fin.dependencies import get_auth

router = KactusAPIRouter(prefix="/api/auth", tags=["auth"])
session_router = KactusAPIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login")
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
) -> LoginResponse:
    """Authenticate with email + password, set session cookie."""
    auth = get_auth()

    async with auth._config.db.get_session() as session:
        user = await UserService.get_by_email(session, body.email)

        if user is None:
            raise AuthenticationError("Invalid email or password")

        # Read raw bcrypt hash (bypassing PasswordHash TypeDecorator mask)
        raw_hash = await UserService.get_password_hash(session, user.id)

    if not raw_hash or not verify_password(body.password, raw_hash):
        raise AuthenticationError("Invalid email or password")

    await auth.login_user(request, response, user, remember=body.remember)

    user_info = UserInfo.model_validate(user)
    return LoginResponse(user=user_info)


@session_router.post("/logout")
async def logout(request: Request, response: Response) -> dict:
    """Clear session cookie and delete session from database."""
    auth = get_auth()
    await auth.logout_user(request, response)
    return {}


@session_router.get("/me")
async def me(request: Request) -> UserInfo:
    """Get current authenticated user info from session cookie."""
    user = request.state.user
    return UserInfo.model_validate(user)
