import logging
from datetime import datetime

import arrow
from aiohttp import web
from models_library.folders import FolderID
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.users import UserID

from ..projects._trash_api import trash_project, untrash_project
from ..workspaces.api import check_user_workspace_access
from . import _folders_db

_logger = logging.getLogger(__name__)


async def _check_exists_and_access(
    app: web.Application,
    *,
    product_name: ProductName,
    user_id: UserID,
    folder_id: FolderID,
) -> bool:
    # 1. exists ?
    folder_db = await _folders_db.get(
        app, folder_id=folder_id, product_name=product_name
    )

    # 2. can ?
    workspace_is_private = True
    if folder_db.workspace_id:
        await check_user_workspace_access(
            app,
            user_id=user_id,
            workspace_id=folder_db.workspace_id,
            product_name=product_name,
            permission="delete",
        )
        workspace_is_private = False

    await _folders_db.get_for_user_or_workspace(
        app,
        folder_id=folder_id,
        product_name=product_name,
        user_id=user_id if workspace_is_private else None,
        workspace_id=folder_db.workspace_id,
    )
    return workspace_is_private


async def _batch_update_folders(
    app: web.Application,
    *,
    product_name: ProductName,
    folder_id: FolderID,
    trashed_at: datetime | None,
):
    # EXPLICIT un/trash
    await _folders_db.update(
        app,
        folder_id=folder_id,
        product_name=product_name,
        trashed_at=trashed_at,
        trashed_explicitly=trashed_at is not None,
    )

    # IMPLICIT un/trash
    child_folders: set[FolderID] = {
        f
        for f in await _folders_db.get_folders_recursively(
            app, folder_id=folder_id, product_name=product_name
        )
        if f != folder_id
    }

    if child_folders:
        await _folders_db.update(
            app,
            folder_id=child_folders,
            product_name=product_name,
            trashed_at=trashed_at,
            trashed_explicitly=False,
        )


async def trash_folder(
    app: web.Application,
    *,
    product_name: ProductName,
    user_id: UserID,
    folder_id: FolderID,
    force_stop_first: bool,
):

    workspace_is_private = await _check_exists_and_access(
        app, product_name=product_name, user_id=user_id, folder_id=folder_id
    )

    # 3. Trash
    trashed_at = arrow.utcnow().datetime

    _logger.debug(
        "TODO: Unit of work for all folders and projects and fails if force_stop_first=%s  is False",
        force_stop_first,
    )

    # 3.1 Trash folder and children
    await _batch_update_folders(
        app,
        folder_id=folder_id,
        product_name=product_name,
        trashed_at=trashed_at,
    )

    # 3.2 Trash all child projects that I am an owner
    child_projects: list[
        ProjectID
    ] = await _folders_db.get_projects_recursively_only_if_user_is_owner(
        app,
        folder_id=folder_id,
        private_workspace_user_id_or_none=user_id if workspace_is_private else None,
        user_id=user_id,
        product_name=product_name,
    )

    for project_id in child_projects:
        await trash_project(
            app,
            product_name=product_name,
            user_id=user_id,
            project_id=project_id,
            force_stop_first=force_stop_first,
            explicit=False,
        )


async def untrash_folder(
    app: web.Application,
    *,
    product_name: ProductName,
    user_id: UserID,
    folder_id: FolderID,
):
    workspace_is_private = await _check_exists_and_access(
        app, product_name=product_name, user_id=user_id, folder_id=folder_id
    )

    # 3. UNtrash

    # 3.1 UNtrash folder and children
    await _batch_update_folders(
        app,
        folder_id=folder_id,
        product_name=product_name,
        trashed_at=None,
    )

    # 3.2 UNtrash all child projects that I am an owner
    child_projects: list[
        ProjectID
    ] = await _folders_db.get_projects_recursively_only_if_user_is_owner(
        app,
        folder_id=folder_id,
        private_workspace_user_id_or_none=user_id if workspace_is_private else None,
        user_id=user_id,
        product_name=product_name,
    )

    for project_id in child_projects:
        await untrash_project(
            app, product_name=product_name, user_id=user_id, project_id=project_id
        )
