"""Project request/response schemas."""

from __future__ import annotations

from kactus_common.schemas import BaseSchema, FancyInt


class ProjectSchema(BaseSchema):
    """Public project information returned by API."""

    id: FancyInt
    name: str
    code: str
    description: str | None = None
    status: str
    created_by: FancyInt | None = None


class ProjectCreateRequest(BaseSchema):
    """Request body for creating a project."""

    name: str
    code: str
    description: str | None = None


class ProjectUpdateRequest(BaseSchema):
    """Request body for updating a project."""

    name: str | None = None
    code: str | None = None
    description: str | None = None


class ProjectMemberSchema(BaseSchema):
    """Project member information."""

    id: FancyInt
    project_id: FancyInt
    user_id: FancyInt
    role: str


class ProjectDetailSchema(ProjectSchema):
    """Project detail with members."""

    members: list[ProjectMemberSchema] = []
