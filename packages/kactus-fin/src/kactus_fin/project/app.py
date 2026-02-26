"""Project feature — KactusApp declaration for kactus-fin."""

from __future__ import annotations

from kactus_common.app_registry import KactusApp
from kactus_common.authorization.const import PermissionAct
from kactus_common.project.const import DefaultRole, ProjectPermission
from kactus_fin.project.api import router

project_app = KactusApp(
    name="project",
    session_routes=[router],
    permissions=[ProjectPermission.project],
    role_permissions={
        DefaultRole.OWNER: [(ProjectPermission.project, PermissionAct.manage)],
        DefaultRole.MANAGER: [(ProjectPermission.project, PermissionAct.write)],
        DefaultRole.MEMBER: [(ProjectPermission.project, PermissionAct.read)],
    },
)
