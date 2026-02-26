"""Project CRUD API — create, read, update, delete projects."""

from __future__ import annotations

from fastapi import Request
from kactus_common.authorization.const import PermissionAct
from kactus_common.authorization.decorator import permission
from kactus_common.project.const import ProjectPermission
from kactus_common.project.schema import (
    ProjectCreateRequest,
    ProjectSchema,
    ProjectUpdateRequest,
)
from kactus_common.project.service import ProjectService
from kactus_common.router import KactusAPIRouter
from kactus_common.schemas import Pagination
from kactus_fin.dependencies import provide_session
from sqlalchemy.ext.asyncio import AsyncSession

router = KactusAPIRouter(prefix="/api/projects", tags=["projects"])


@router.post("")
@provide_session
async def create_project(
    body: ProjectCreateRequest,
    request: Request,
    session: AsyncSession,
) -> ProjectSchema:
    """Create a new project. Creator is automatically assigned as owner."""
    user = request.state.user
    project = await ProjectService.create(
        session,
        name=body.name,
        code=body.code,
        description=body.description,
        creator_id=user.id,
    )
    return ProjectSchema.model_validate(project)


@router.get("")
@provide_session
async def list_projects(
    request: Request,
    session: AsyncSession,
) -> Pagination[ProjectSchema]:
    """List projects the current user is a member of.

    Superusers see all projects.
    """
    user = request.state.user
    if user.is_superuser:
        projects = await ProjectService.list_all(session)
    else:
        projects = await ProjectService.get_user_projects(session, user.id)

    items = [ProjectSchema.model_validate(p) for p in projects]
    return Pagination(total=len(items), items=items)


@router.get("/{project_id}")
@permission(ProjectPermission.project, PermissionAct.read)
@provide_session
async def get_project(
    project_id: int,
    request: Request,
    session: AsyncSession,
) -> ProjectSchema:
    """Get a project by ID."""
    project = await ProjectService.get_or_404(session, project_id)
    return ProjectSchema.model_validate(project)


@router.put("/{project_id}")
@permission(ProjectPermission.project, PermissionAct.write)
@provide_session
async def update_project(
    project_id: int,
    body: ProjectUpdateRequest,
    request: Request,
    session: AsyncSession,
) -> ProjectSchema:
    """Update a project."""
    project = await ProjectService.get_or_404(session, project_id)
    project = await ProjectService.update(
        session,
        project,
        name=body.name,
        code=body.code,
        description=body.description,
    )
    return ProjectSchema.model_validate(project)


@router.delete("/{project_id}")
@permission(ProjectPermission.project, PermissionAct.manage)
@provide_session
async def delete_project(
    project_id: int,
    request: Request,
    session: AsyncSession,
) -> dict:
    """Logical delete a project."""
    project = await ProjectService.get_or_404(session, project_id)
    await ProjectService.delete(session, project)
    return {}
