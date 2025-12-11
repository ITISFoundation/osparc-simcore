"""Handlers for CRUD operations on /projects/{*}/tags/{*}"""

import logging

from aiohttp import web
from models_library.projects import ProjectID
from models_library.users import UserID
from models_library.workspaces import UserWorkspaceWithAccessRights

from ..workspaces import _workspaces_repository as workspaces_workspaces_repository
from . import _projects_repository
from ._access_rights_service import check_user_project_permission
from ._projects_repository_legacy import ProjectDBAPI
from .models import ProjectDict

_logger = logging.getLogger(__name__)


async def add_tag(
    app: web.Application, user_id: UserID, project_uuid: ProjectID, tag_id: int
) -> ProjectDict:
    db: ProjectDBAPI = ProjectDBAPI.get_from_app_context(app)

    product_name = await _projects_repository.get_project_product(
        app, project_uuid=project_uuid
    )
    await check_user_project_permission(
        app,
        project_id=project_uuid,
        user_id=user_id,
        product_name=product_name,
        permission="write",  # NOTE: before there was only read access necessary
    )

    project: ProjectDict = await db.add_tag(
        project_uuid=f"{project_uuid}", user_id=user_id, tag_id=int(tag_id)
    )

    if project["workspaceId"] is not None:
        workspace: UserWorkspaceWithAccessRights = (
            await workspaces_workspaces_repository.get_workspace_for_user(
                app=app,
                user_id=user_id,
                workspace_id=project["workspaceId"],
                product_name=product_name,
            )
        )
        project["accessRights"] = {
            gid: access.model_dump() for gid, access in workspace.access_rights.items()
        }

    return project


async def remove_tag(
    app: web.Application, user_id: UserID, project_uuid: ProjectID, tag_id: int
) -> ProjectDict:
    db: ProjectDBAPI = ProjectDBAPI.get_from_app_context(app)

    product_name = await db.get_project_product(project_uuid)
    await check_user_project_permission(
        app,
        project_id=project_uuid,
        user_id=user_id,
        product_name=product_name,
        permission="write",  # NOTE: before there was only read access necessary
    )

    project: ProjectDict = await db.remove_tag(
        project_uuid=f"{project_uuid}", user_id=user_id, tag_id=tag_id
    )

    if project["workspaceId"] is not None:
        workspace: UserWorkspaceWithAccessRights = (
            await workspaces_workspaces_repository.get_workspace_for_user(
                app=app,
                user_id=user_id,
                workspace_id=project["workspaceId"],
                product_name=product_name,
            )
        )
        project["accessRights"] = {
            gid: access.model_dump() for gid, access in workspace.access_rights.items()
        }

    return project
