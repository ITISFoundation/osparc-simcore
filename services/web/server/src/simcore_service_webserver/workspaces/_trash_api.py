import logging

import arrow
from aiohttp import web
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.users import UserID
from models_library.workspaces import WorkspaceID

from ..projects._trash_api import trash_project, untrash_project

_logger = logging.getLogger(__name__)


async def trash_workspace(
    app: web.Application,
    *,
    product_name: ProductName,
    user_id: UserID,
    workspace_id: WorkspaceID,
    force_stop_first: bool,
):
    # TODO: Check

    # Trash
    trashed_at = arrow.utcnow().datetime

    _logger.debug(
        "TODO: Unit of work for all workspaces and projects and fails if force_stop_first=%s  is False",
        force_stop_first,
    )

    # 1. TODO: Trash workspace

    # 2. Trash all child folders

    # 2. Trash all child projects that I am an owner
    child_projects: list[ProjectID] = []

    for project_id in child_projects:
        await trash_project(
            app,
            product_name=product_name,
            user_id=user_id,
            project_id=project_id,
            force_stop_first=force_stop_first,
            explicit=False,
        )


async def untrash_workspace(
    app: web.Application,
    *,
    product_name: ProductName,
    user_id: UserID,
    workspace_id: WorkspaceID,
):
    # TODO: Check

    # 3. UNtrash

    # 3.1 UNtrash workspace and children

    # 3.2 UNtrash all child projects that I am an owner
    child_projects: list[ProjectID] = []
    for project_id in child_projects:
        await untrash_project(
            app, product_name=product_name, user_id=user_id, project_id=project_id
        )
