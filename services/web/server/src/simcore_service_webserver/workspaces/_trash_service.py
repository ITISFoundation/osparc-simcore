import logging
from datetime import datetime

import arrow
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
from simcore_postgres_database.utils_repos import transaction_context

from ..db.plugin import get_asyncpg_engine
from ..folders._trash_service import (
    batch_delete_folders_with_content_in_root_workspace_as_admin,
    trash_folder,
    untrash_folder,
)
from ..folders.service import list_folders
from ..projects._trash_service import (
    batch_delete_projects_in_root_workspace_as_admin,
    trash_project,
    untrash_project,
)
from ..projects.api import list_projects
from ..projects.models import ProjectTypeAPI
from . import _workspaces_repository, _workspaces_service, _workspaces_service_crud_read
from .errors import WorkspaceBatchDeleteError, WorkspaceNotTrashedError

_logger = logging.getLogger(__name__)


async def _check_exists_and_access(
    app: web.Application,
    *,
    product_name: ProductName,
    user_id: UserID,
    workspace_id: WorkspaceID,
):
    await _workspaces_service_crud_read.check_user_workspace_access(
        app=app,
        user_id=user_id,
        workspace_id=workspace_id,
        product_name=product_name,
        permission="delete",
    )


async def _list_root_child_folders(
    app: web.Application,
    *,
    product_name: ProductName,
    user_id: UserID,
    workspace_id: WorkspaceID,
) -> list[FolderID]:

    child_folders: list[FolderID] = []
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
            folder_id=None,
            workspace_id=workspace_id,
            trashed=None,
            offset=page_params.offset,
            limit=page_params.limit,
            order_by=OrderBy(field=IDStr("trashed"), direction=OrderDirection.ASC),
        )

        child_folders.extend([folder.folder_db.folder_id for folder in folders])

    return child_folders


async def _list_root_child_projects(
    app: web.Application,
    *,
    product_name: ProductName,
    user_id: UserID,
    workspace_id: WorkspaceID,
) -> list[ProjectID]:

    child_projects: list[ProjectID] = []
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

        child_projects.extend([Project(**project).uuid for project in projects])

    return child_projects


async def trash_workspace(
    app: web.Application,
    *,
    product_name: ProductName,
    user_id: UserID,
    workspace_id: WorkspaceID,
    force_stop_first: bool,
):
    await _check_exists_and_access(
        app, product_name=product_name, user_id=user_id, workspace_id=workspace_id
    )

    trashed_at = arrow.utcnow().datetime

    async with transaction_context(get_asyncpg_engine(app)) as connection:
        # EXPLICIT trash
        await _workspaces_repository.update_workspace(
            app,
            connection,
            product_name=product_name,
            workspace_id=workspace_id,
            updates=WorkspaceUpdates(trashed=trashed_at, trashed_by=user_id),
        )

        # IMPLICIT trash
        child_folders: list[FolderID] = await _list_root_child_folders(
            app,
            product_name=product_name,
            user_id=user_id,
            workspace_id=workspace_id,
        )

        for folder_id in child_folders:
            await trash_folder(
                app,
                product_name=product_name,
                user_id=user_id,
                folder_id=folder_id,
                force_stop_first=force_stop_first,
                explicit=False,
            )

        child_projects: list[ProjectID] = await _list_root_child_projects(
            app,
            product_name=product_name,
            user_id=user_id,
            workspace_id=workspace_id,
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


async def untrash_workspace(
    app: web.Application,
    *,
    product_name: ProductName,
    user_id: UserID,
    workspace_id: WorkspaceID,
):
    await _check_exists_and_access(
        app, product_name=product_name, user_id=user_id, workspace_id=workspace_id
    )

    async with transaction_context(get_asyncpg_engine(app)) as connection:
        # EXPLICIT UNtrash
        await _workspaces_repository.update_workspace(
            app,
            connection,
            product_name=product_name,
            workspace_id=workspace_id,
            updates=WorkspaceUpdates(trashed=None, trashed_by=None),
        )

        child_folders: list[FolderID] = await _list_root_child_folders(
            app,
            product_name=product_name,
            user_id=user_id,
            workspace_id=workspace_id,
        )

        for folder_id in child_folders:
            await untrash_folder(
                app,
                product_name=product_name,
                user_id=user_id,
                folder_id=folder_id,
            )

        child_projects: list[ProjectID] = await _list_root_child_projects(
            app,
            product_name=product_name,
            user_id=user_id,
            workspace_id=workspace_id,
        )

        for project_id in child_projects:
            await untrash_project(
                app, product_name=product_name, user_id=user_id, project_id=project_id
            )


def _can_delete(
    workspace: UserWorkspaceWithAccessRights,
    user_id: UserID,
    until_equal_datetime: datetime | None,
) -> bool:
    return bool(
        workspace.trashed
        and (until_equal_datetime is None or workspace.trashed < until_equal_datetime)
        and workspace.my_access_rights.delete
        and workspace.trashed_by == user_id
    )


async def delete_trashed_workspace(
    app: web.Application,
    *,
    product_name: ProductName,
    user_id: UserID,
    workspace_id: WorkspaceID,
    until_equal_datetime: datetime | None = None,
) -> None:

    workspace = await _workspaces_service_crud_read.get_workspace(
        app,
        user_id=user_id,
        product_name=product_name,
        workspace_id=workspace_id,
    )

    if not _can_delete(
        workspace,
        user_id=user_id,
        until_equal_datetime=until_equal_datetime,
    ):
        raise WorkspaceNotTrashedError(
            workspace_id=workspace_id,
            user_id=user_id,
            details="Cannot delete trashed workspace since it does not fit current criteria",
        )

    # NOTE: this function deletes workspace AND its content recursively!
    await _workspaces_service.delete_workspace_with_all_content(
        app,
        user_id=user_id,
        product_name=product_name,
        workspace_id=workspace_id,
    )


async def list_trashed_workspaces(
    app: web.Application,
    product_name: ProductName,
    user_id: UserID,
    until_equal_datetime: datetime | None = None,
) -> list[WorkspaceID]:
    trashed_workspace_ids: list[WorkspaceID] = []

    for page_params in iter_pagination_params(
        offset=0, limit=MAXIMUM_NUMBER_OF_ITEMS_PER_PAGE
    ):
        (
            page_params.total_number_of_items,
            workspaces,
        ) = await _workspaces_service_crud_read.list_workspaces(
            app,
            user_id=user_id,
            product_name=product_name,
            filter_trashed=True,
            filter_by_text=None,
            offset=page_params.offset,
            limit=page_params.limit,
            order_by=OrderBy(field=IDStr("trashed"), direction=OrderDirection.ASC),
        )

        # NOTE: Applying POST-FILTERING
        trashed_workspace_ids.extend(
            [
                ws.workspace_id
                for ws in workspaces
                if _can_delete(
                    ws,
                    user_id=user_id,
                    until_equal_datetime=until_equal_datetime,
                )
            ]
        )

    return trashed_workspace_ids


async def batch_delete_trashed_workspaces_as_admin(
    app: web.Application,
    *,
    trashed_before: datetime,
    fail_fast: bool,
) -> list[WorkspaceID]:

    deleted_workspace_ids: list[WorkspaceID] = []
    errors: list[tuple[WorkspaceID, Exception]] = []

    for page_params in iter_pagination_params(
        offset=0, limit=MAXIMUM_NUMBER_OF_ITEMS_PER_PAGE
    ):
        (
            page_params.total_number_of_items,
            expired_trashed_workspaces,
        ) = await _workspaces_repository.list_workspaces_db_get_as_admin(
            app,
            trashed_before=trashed_before,
            offset=page_params.offset,
            limit=page_params.limit,
            order_by=OrderBy(
                field=IDStr("workspace_id"), direction=OrderDirection.DESC
            ),
        )
        # BATCH delete
        for trashed_workspace in expired_trashed_workspaces:
            assert trashed_workspace.trashed  # nosec
            deleted_workspace_ids.append(trashed_workspace.workspace_id)

            workspace_db_get = await _workspaces_repository.get_workspace_db_get(
                app, workspace_id=trashed_workspace.workspace_id
            )

            try:
                await batch_delete_projects_in_root_workspace_as_admin(
                    app, workspace_id=trashed_workspace.workspace_id, fail_fast=False
                )
            except Exception as err:  # pylint: disable=broad-exception-caught
                if fail_fast:
                    raise
                errors.append((trashed_workspace.workspace_id, err))

            try:
                await batch_delete_folders_with_content_in_root_workspace_as_admin(
                    app,
                    workspace_id=trashed_workspace.workspace_id,
                    product_name=workspace_db_get.product_name,
                    fail_fast=False,
                )
            except Exception as err:  # pylint: disable=broad-exception-caught
                if fail_fast:
                    raise
                errors.append((trashed_workspace.workspace_id, err))

            try:
                await _workspaces_repository.delete_workspace(
                    app,
                    workspace_id=trashed_workspace.workspace_id,
                    product_name=workspace_db_get.product_name,
                )
            except Exception as err:  # pylint: disable=broad-exception-caught
                if fail_fast:
                    raise
                errors.append((trashed_workspace.workspace_id, err))

    if errors:
        raise WorkspaceBatchDeleteError(
            errors=errors,
            deleted_workspace_ids=deleted_workspace_ids,
        )

    return deleted_workspace_ids
