"""Project request/response schemas."""

from __future__ import annotations

from kactus_common.schemas import AwareUTCDatetime, BaseSchema, FancyInt


class ProjectSchema(BaseSchema):
    """Public project information returned by API.

    The fields below ``created_by`` are **derived**, not columns: the owner's
    name/email live on ``users``, the member count on ``project_members``, and
    ``my_role`` depends on who is asking. They are resolved in batch by
    ``ProjectService.build_schemas`` — a plain ``model_validate(project)`` leaves
    them at their defaults, which is why every one of them has one.
    """

    id: FancyInt
    name: str
    code: str
    description: str | None = None
    status: str
    created_by: FancyInt | None = None
    create_time: AwareUTCDatetime | None = None
    owner_name: str | None = None
    owner_email: str | None = None
    member_count: FancyInt = 0
    my_role: str | None = None


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
    #: Archive/restore — one of :class:`ProjectStatus`. Validated in the service.
    status: str | None = None


class ProjectMemberSchema(BaseSchema):
    """Project member information."""

    id: FancyInt
    project_id: FancyInt
    user_id: FancyInt
    role: str


class ProjectMemberDetailSchema(ProjectMemberSchema):
    """Project member enriched with the user's email/name for display."""

    email: str | None = None
    name: str | None = None


class AddMemberRequest(BaseSchema):
    """Invite an existing user to a project by email."""

    email: str
    role: str = "member"


class UpdateMemberRoleRequest(BaseSchema):
    """Change a member's role."""

    role: str


class ProjectDetailSchema(ProjectSchema):
    """Project detail with members."""

    members: list[ProjectMemberSchema] = []
