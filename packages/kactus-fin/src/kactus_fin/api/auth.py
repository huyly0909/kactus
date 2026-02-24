"""Auth API — login, logout, get current user."""

from __future__ import annotations

from fastapi import APIRouter, Request, Response
from kactus_common.crypto import verify_password
from kactus_common.exceptions import AuthenticationError
from kactus_common.schemas import ResponseModel
from kactus_common.user.schema import LoginRequest, LoginResponse, UserInfo
from kactus_common.user.service import UserService
from kactus_fin.dependencies import get_auth

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=ResponseModel[LoginResponse])
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
) -> ResponseModel[LoginResponse]:
    """Authenticate with email + password, set session cookie."""
    auth = get_auth()

    async with auth._config.db.get_session() as session:
        user = await UserService.get_by_email(session, body.email)

    if user is None:
        raise AuthenticationError("Invalid email or password")

    if not verify_password(body.password, user.password_hash):
        raise AuthenticationError("Invalid email or password")

    await auth.login_user(request, response, user, remember=body.remember)

    user_info = UserInfo.model_validate(user)
    return ResponseModel(data=LoginResponse(user=user_info))


@router.post("/logout", response_model=ResponseModel[dict])
async def logout(request: Request, response: Response) -> ResponseModel[dict]:
    """Clear session cookie and delete session from database."""
    auth = get_auth()
    await auth.logout_user(request, response)
    return ResponseModel(data={})


@router.get("/me", response_model=ResponseModel[UserInfo])
async def me(request: Request) -> ResponseModel[UserInfo]:
    """Get current authenticated user info from session cookie."""
    auth = get_auth()
    user = await auth.get_current_user(request)
    user_info = UserInfo.model_validate(user)
    return ResponseModel(data=user_info)
