import logging
from datetime import datetime

import arrow
from aiohttp import web
from common_library.pagination_tools import iter_pagination_params
from models_library.access_rights import AccessRights
from models_library.basic_types import IDStr
from models_library.folders import FolderDB, FolderID
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.rest_ordering import OrderBy, OrderDirection
from models_library.rest_pagination import MAXIMUM_NUMBER_OF_ITEMS_PER_PAGE
from models_library.users import UserID
from models_library.workspaces import WorkspaceID
from simcore_postgres_database.utils_repos import transaction_context
from sqlalchemy.ext.asyncio import AsyncConnection

from ..db.plugin import get_asyncpg_engine
from ..projects._trash_service import trash_project, untrash_project
from ..workspaces.api import check_user_workspace_access
from . import _folders_repository, _folders_service
from .errors import FolderBatchDeleteError, FolderNotTrashedError

_logger = logging.getLogger(__name__)


async def _check_exists_and_access(
    app: web.Application,
    *,
    product_name: ProductName,
    user_id: UserID,
    folder_id: FolderID,
) -> bool:
    # exists?
    #   check whether this folder exists
    #   otherwise raise not-found error
    folder_db = await _folders_repository.get(
        app, folder_id=folder_id, product_name=product_name
    )

    # can?
    #  check whether user in product has enough permissions to delete this folder
    #  otherwise raise forbidden error
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

    await _folders_repository.get_for_user_or_workspace(
        app,
        folder_id=folder_id,
        product_name=product_name,
        user_id=user_id if workspace_is_private else None,
        workspace_id=folder_db.workspace_id,
    )
    return workspace_is_private


async def _folders_db_trashed_state_update(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    product_name: ProductName,
    folder_id: FolderID,
    trashed_at: datetime | None,
    trashed_explicitly: bool,
    trashed_by: UserID | None,
):
    # EXPLICIT or IMPLICIT un/trash
    await _folders_repository.update(
        app,
        connection,
        folders_id_or_ids=folder_id,
        product_name=product_name,
        trashed=trashed_at,
        trashed_explicitly=trashed_explicitly,
        trashed_by=trashed_by,
    )

    # IMPLICIT un/trash
    child_folders: set[FolderID] = {
        f
        for f in await _folders_repository.get_folders_recursively(
            app, connection, folder_id=folder_id, product_name=product_name
        )
        if f != folder_id
    }

    if child_folders:
        await _folders_repository.update(
            app,
            connection,
            folders_id_or_ids=child_folders,
            product_name=product_name,
            trashed=trashed_at,
            trashed_explicitly=False,
            trashed_by=trashed_by,
        )


async def trash_folder(
    app: web.Application,
    *,
    product_name: ProductName,
    user_id: UserID,
    folder_id: FolderID,
    force_stop_first: bool,
    explicit: bool,
):

    workspace_is_private = await _check_exists_and_access(
        app, product_name=product_name, user_id=user_id, folder_id=folder_id
    )

    # Trash
    trashed_at = arrow.utcnow().datetime

    async with transaction_context(get_asyncpg_engine(app)) as connection:

        # 1. Trash folder and children
        await _folders_db_trashed_state_update(
            app,
            connection,
            folder_id=folder_id,
            product_name=product_name,
            trashed_at=trashed_at,
            trashed_explicitly=explicit,
            trashed_by=user_id,
        )

        # 2. Trash all child projects that I am an owner
        child_projects: list[ProjectID] = (
            await _folders_repository.get_projects_recursively_only_if_user_is_owner(
                app,
                connection,
                folder_id=folder_id,
                private_workspace_user_id_or_none=(
                    user_id if workspace_is_private else None
                ),
                user_id=user_id,
                product_name=product_name,
            )
        )

        for project_id in child_projects:
            await trash_project(
                app,
                # NOTE: this needs to be included in the unit-of-work, i.e. connection,
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
    await _folders_db_trashed_state_update(
        app,
        folder_id=folder_id,
        product_name=product_name,
        trashed_at=None,
        trashed_by=None,
        trashed_explicitly=False,
    )

    # 3.2 UNtrash all child projects that I am an owner
    child_projects: list[ProjectID] = (
        await _folders_repository.get_projects_recursively_only_if_user_is_owner(
            app,
            folder_id=folder_id,
            private_workspace_user_id_or_none=user_id if workspace_is_private else None,
            user_id=user_id,
            product_name=product_name,
        )
    )

    for project_id in child_projects:
        await untrash_project(
            app, product_name=product_name, user_id=user_id, project_id=project_id
        )


def _can_delete(
    folder_db: FolderDB,
    my_access_rights: AccessRights,
    user_id: UserID,
    until_equal_datetime: datetime | None,
) -> bool:
    return bool(
        folder_db.trashed
        and (until_equal_datetime is None or folder_db.trashed < until_equal_datetime)
        and my_access_rights.delete
        and folder_db.trashed_by == user_id
        and folder_db.trashed_explicitly
    )


async def list_explicitly_trashed_folders(
    app: web.Application,
    *,
    product_name: ProductName,
    user_id: UserID,
    until_equal_datetime: datetime | None = None,
) -> list[FolderID]:
    trashed_folder_ids: list[FolderID] = []

    for page_params in iter_pagination_params(
        offset=0, limit=MAXIMUM_NUMBER_OF_ITEMS_PER_PAGE
    ):
        (
            folders,
            page_params.total_number_of_items,
        ) = await _folders_service.list_folders_full_depth(
            app,
            user_id=user_id,
            product_name=product_name,
            text=None,
            trashed=True,  # NOTE: lists only explicitly trashed!
            offset=page_params.offset,
            limit=page_params.limit,
            order_by=OrderBy(field=IDStr("trashed"), direction=OrderDirection.ASC),
        )

        # NOTE: Applying POST-FILTERING
        trashed_folder_ids.extend(
            [
                f.folder_db.folder_id
                for f in folders
                if _can_delete(
                    f.folder_db,
                    my_access_rights=f.my_access_rights,
                    user_id=user_id,
                    until_equal_datetime=until_equal_datetime,
                )
            ]
        )
    return trashed_folder_ids


async def delete_trashed_folder(
    app: web.Application,
    *,
    product_name: ProductName,
    user_id: UserID,
    folder_id: FolderID,
    until_equal_datetime: datetime | None = None,
) -> None:

    folder = await _folders_service.get_folder(
        app, user_id=user_id, folder_id=folder_id, product_name=product_name
    )

    if not _can_delete(
        folder.folder_db,
        folder.my_access_rights,
        user_id=user_id,
        until_equal_datetime=until_equal_datetime,
    ):
        raise FolderNotTrashedError(
            folder_id=folder_id,
            user_id=user_id,
            details="Cannot delete trashed folder since it does not fit current criteria",
        )

    # NOTE: this function deletes folder AND its content recursively!
    await _folders_service.delete_folder_with_all_content(
        app, user_id=user_id, folder_id=folder_id, product_name=product_name
    )


async def batch_delete_trashed_folders_as_admin(
    app: web.Application,
    trashed_before: datetime,
    *,
    product_name: ProductName,
    fail_fast: bool,
) -> None:
    """
    Raises:
        FolderBatchDeleteError: if error and fail_fast=False
        Exception: any other exception during delete_recursively
    """
    errors: list[tuple[FolderID, Exception]] = []

    for page_params in iter_pagination_params(
        offset=0, limit=MAXIMUM_NUMBER_OF_ITEMS_PER_PAGE
    ):
        (
            page_params.total_number_of_items,
            expired_trashed_folders,
        ) = await _folders_repository.list_folders_db_as_admin(
            app,
            trashed_explicitly=True,
            trashed_before=trashed_before,
            offset=page_params.offset,
            limit=page_params.limit,
            order_by=OrderBy(field=IDStr("trashed"), direction=OrderDirection.ASC),
        )

        # BATCH delete
        for folder in expired_trashed_folders:
            try:
                await _folders_repository.delete_recursively(
                    app, folder_id=folder.folder_id, product_name=product_name
                )
                # NOTE: projects in folders are NOT deleted

            except Exception as err:  # pylint: disable=broad-exception-caught
                if fail_fast:
                    raise
                errors.append((folder.folder_id, err))

    if errors:
        raise FolderBatchDeleteError(
            errors=errors, trashed_before=trashed_before, product_name=product_name
        )


async def batch_delete_folders_with_content_in_root_workspace_as_admin(
    app: web.Application,
    *,
    workspace_id: WorkspaceID,
    product_name: ProductName,
    fail_fast: bool,
) -> None:
    """
    Deletes all folders recursively in the workspace root.

    Raises:
        FolderBatchDeleteError: If there are errors during the deletion process.
    """
    deleted_folder_ids: list[FolderID] = []
    errors: list[tuple[FolderID, Exception]] = []

    for page_params in iter_pagination_params(
        offset=0, limit=MAXIMUM_NUMBER_OF_ITEMS_PER_PAGE
    ):
        (
            page_params.total_number_of_items,
            folders_for_deletion,
        ) = await _folders_repository.list_folders_db_as_admin(
            app,
            shared_workspace_id=workspace_id,  # <-- Workspace filter
            offset=page_params.offset,
            limit=page_params.limit,
            order_by=OrderBy(field=IDStr("folder_id")),
        )
        # BATCH delete
        for folder in folders_for_deletion:
            try:
                await _folders_repository.delete_recursively(
                    app, folder_id=folder.folder_id, product_name=product_name
                )
                deleted_folder_ids.append(folder.folder_id)
            except Exception as err:  # pylint: disable=broad-exception-caught
                if fail_fast:
                    raise
                errors.append((folder.folder_id, err))

    if errors:
        raise FolderBatchDeleteError(
            errors=errors,
        )
