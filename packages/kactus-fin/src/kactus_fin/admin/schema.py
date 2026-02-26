"""Admin feature — Pydantic schemas."""

from __future__ import annotations

from kactus_common.schemas import BaseSchema


class AdminCreateUserRequest(BaseSchema):
    """Admin request to create a user."""

    email: str
    name: str
    password: str
    is_superuser: bool = False


class UpdateUserRoleRequest(BaseSchema):
    """Admin request to update a user's superuser status."""

    is_superuser: bool


class ResetPasswordResponse(BaseSchema):
    """Response with the new generated password."""

    new_password: str
