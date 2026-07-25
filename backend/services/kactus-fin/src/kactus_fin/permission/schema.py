"""Permission feature — Pydantic schemas."""

from __future__ import annotations

from kactus_common.schemas import BaseSchema


class PermissionItem(BaseSchema):
    """A single permission entry."""

    permission: str
    act: str


class PermissionsResponse(BaseSchema):
    """Response model for user permissions in a project."""

    project_id: str | None = None
    permissions: list[PermissionItem | dict] = []
    role: str | None = None
    is_superuser: bool = False
