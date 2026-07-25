"""User request/response schemas."""

from __future__ import annotations

from kactus_common.schemas import BaseSchema, FancyInt


class LoginRequest(BaseSchema):
    """Login request body."""

    email: str
    password: str
    remember: bool = False


class UserInfo(BaseSchema):
    """Public user information returned by API."""

    id: FancyInt
    email: str
    username: str
    name: str
    status: str
    is_superuser: bool = False


class LoginResponse(BaseSchema):
    """Login response body."""

    user: UserInfo
