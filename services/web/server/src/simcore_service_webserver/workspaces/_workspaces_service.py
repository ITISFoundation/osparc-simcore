# pylint: disable=unused-argument

import logging

from aiohttp import web
from models_library.basic_types import IDStr
from models_library.folders import FolderID
from models_library.products import ProductName
from models_library.projects import Project, ProjectID
from models_library.rest_ordering import OrderBy, OrderDirection
from models_library.rest_pagination import MAXIMUM_NUMBER_OF_ITEMS_PER_PAGE
from models_library.users import UserID
from models_library.workspaces import (
    UserWorkspaceWithAccessRights,
    WorkspaceID,
    WorkspaceUpdates,
)
from servicelib.logging_utils import log_context

from ..folders.folders_service import delete_folder_with_all_content, list_folders
from ..projects import projects_trash_service
from ..projects.api import list_projects
from ..projects.models import ProjectTypeAPI
from ..users import users_service
from . import _workspaces_repository as db
from ._workspaces_service_crud_read import check_user_workspace_access

_logger = logging.getLogger(__name__)


async def create_workspace(
    app: web.Application,
    *,
    user_id: UserID,
    name: str,
    description: str | None,
    thumbnail: str | None,
    product_name: ProductName,
) -> UserWorkspaceWithAccessRights:
    user = await users_service.get_user(app, user_id=user_id)
    created = await db.create_workspace(
        app,
        product_name=product_name,
        owner_primary_gid=user["primary_gid"],
        name=name,
        description=description,
        thumbnail=thumbnail,
    )
    return await db.get_workspace_for_user(
        app,
        user_id=user_id,
        workspace_id=created.workspace_id,
        product_name=product_name,
    )


async def update_workspace(
    app: web.Application,
    *,
    product_name: ProductName,
    user_id: UserID,
    workspace_id: WorkspaceID,
    **updates,
) -> UserWorkspaceWithAccessRights:
    await check_user_workspace_access(
        app=app,
        user_id=user_id,
        workspace_id=workspace_id,
        product_name=product_name,
        permission="write",
    )
    await db.update_workspace(
        app,
        workspace_id=workspace_id,
        product_name=product_name,
        updates=WorkspaceUpdates(**updates),
    )
    return await db.get_workspace_for_user(
        app,
        user_id=user_id,
        workspace_id=workspace_id,
        product_name=product_name,
    )


async def delete_workspace_with_all_content(
    app: web.Application,
    *,
    product_name: ProductName,
    user_id: UserID,
    workspace_id: WorkspaceID,
) -> None:
    await check_user_workspace_access(
        app=app,
        user_id=user_id,
        workspace_id=workspace_id,
        product_name=product_name,
        permission="delete",
    )

    # Get all root projects
    while True:
        projects, total_number_projects = await list_projects(
            app,
            user_id=user_id,
            product_name=product_name,
            show_hidden=False,
            workspace_id=workspace_id,
            project_type=ProjectTypeAPI.all,
            template_type=None,
            folder_id=None,
            trashed=None,
            offset=0,
            limit=MAXIMUM_NUMBER_OF_ITEMS_PER_PAGE,
            order_by=OrderBy(field=IDStr("last_change_date"), direction=OrderDirection.DESC),
        )
        if not projects:
            break

        workspace_root_projects: list[ProjectID] = [Project(**project).uuid for project in projects]

        # Delete projects properly
        with log_context(
            _logger,
            logging.INFO,
            "Deleting %d root projects out of %d",
            len(workspace_root_projects),
            total_number_projects,
        ):
            for project_uuid in workspace_root_projects:
                await projects_trash_service.delete_project_as_user(
                    app, project_id=project_uuid, user_id=user_id, product_name=product_name
                )

    # Get all root folders
    while True:
        folders, folders_total_count = await list_folders(
            app,
            user_id=user_id,
            product_name=product_name,
            workspace_id=workspace_id,
            folder_id=None,
            trashed=None,
            offset=0,
            limit=MAXIMUM_NUMBER_OF_ITEMS_PER_PAGE,
            order_by=OrderBy(field=IDStr("folder_id"), direction=OrderDirection.ASC),
        )
        if not folders:
            break

        workspace_root_folders: list[FolderID] = [folder.folder_db.folder_id for folder in folders]

        # Delete folders properly
        with log_context(
            _logger,
            logging.INFO,
            "Deleting %d root folders out of %d",
            len(workspace_root_folders),
            folders_total_count,
        ):
            for folder_id in workspace_root_folders:
                await delete_folder_with_all_content(
                    app,
                    user_id=user_id,
                    product_name=product_name,
                    folder_id=folder_id,
                )

    await db.delete_workspace(
        app,
        workspace_id=workspace_id,
        product_name=product_name,
    )
