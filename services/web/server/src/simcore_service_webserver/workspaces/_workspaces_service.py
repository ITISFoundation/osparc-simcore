# pylint: disable=unused-argument

import logging

from aiohttp import web
from common_library.pagination_tools import iter_pagination_params
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

from ..folders.service import delete_folder_with_all_content, list_folders
from ..projects.api import delete_project_by_user, list_projects
from ..projects.models import ProjectTypeAPI
from ..users.api import get_user
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
    user = await get_user(app, user_id=user_id)
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
    for page_params in iter_pagination_params(
        offset=0, limit=MAXIMUM_NUMBER_OF_ITEMS_PER_PAGE
    ):
        (
            projects,
            page_params.total_number_of_items,
        ) = await list_projects(
            app,
            user_id=user_id,
            product_name=product_name,
            show_hidden=False,
            workspace_id=workspace_id,
            project_type=ProjectTypeAPI.all,
            template_type=None,
            folder_id=None,
            trashed=None,
            offset=page_params.offset,
            limit=page_params.limit,
            order_by=OrderBy(
                field=IDStr("last_change_date"), direction=OrderDirection.DESC
            ),
        )

        workspace_root_projects: list[ProjectID] = [
            Project(**project).uuid for project in projects
        ]

        # Delete projects properly
        for project_uuid in workspace_root_projects:
            await delete_project_by_user(
                app, project_uuid=project_uuid, user_id=user_id
            )

    # Get all root folders
    for page_params in iter_pagination_params(
        offset=0, limit=MAXIMUM_NUMBER_OF_ITEMS_PER_PAGE
    ):
        (
            folders,
            page_params.total_number_of_items,
        ) = await list_folders(
            app,
            user_id=user_id,
            product_name=product_name,
            workspace_id=workspace_id,
            folder_id=None,
            trashed=None,
            offset=page_params.offset,
            limit=page_params.limit,
            order_by=OrderBy(field=IDStr("folder_id"), direction=OrderDirection.ASC),
        )

        workspace_root_folders: list[FolderID] = [
            folder.folder_db.folder_id for folder in folders
        ]

        # Delete folders properly
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
