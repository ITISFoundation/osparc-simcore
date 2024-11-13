# pylint: disable=unused-argument

import logging

from aiohttp import web
from models_library.access_rights import AccessRights
from models_library.api_schemas_webserver.folders_v2 import FolderGet, FolderGetPage
from models_library.folders import FolderID, FolderQuery, FolderScope
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.rest_ordering import OrderBy
from models_library.users import UserID
from models_library.workspaces import WorkspaceID, WorkspaceQuery, WorkspaceScope
from pydantic import NonNegativeInt
from servicelib.aiohttp.application_keys import APP_FIRE_AND_FORGET_TASKS_KEY
from servicelib.common_headers import UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE
from servicelib.utils import fire_and_forget_task

from ..folders.errors import FolderValueNotPermittedError
from ..projects.projects_api import submit_delete_project_task
from ..users.api import get_user
from ..workspaces.api import check_user_workspace_access
from ..workspaces.errors import (
    WorkspaceAccessForbiddenError,
    WorkspaceFolderInconsistencyError,
)
from . import _folders_db as folders_db

_logger = logging.getLogger(__name__)


async def create_folder(
    app: web.Application,
    user_id: UserID,
    name: str,
    parent_folder_id: FolderID | None,
    product_name: ProductName,
    workspace_id: WorkspaceID | None,
) -> FolderGet:
    user = await get_user(app, user_id=user_id)

    workspace_is_private = True
    user_folder_access_rights = AccessRights(read=True, write=True, delete=True)
    if workspace_id:
        user_workspace_access_rights = await check_user_workspace_access(
            app,
            user_id=user_id,
            workspace_id=workspace_id,
            product_name=product_name,
            permission="write",
        )
        workspace_is_private = False
        user_folder_access_rights = user_workspace_access_rights.my_access_rights

        # Check parent_folder_id lives in the workspace
        if parent_folder_id:
            parent_folder_db = await folders_db.get(
                app, folder_id=parent_folder_id, product_name=product_name
            )
            if parent_folder_db.workspace_id != workspace_id:
                raise WorkspaceFolderInconsistencyError(
                    folder_id=parent_folder_id, workspace_id=workspace_id
                )

    if parent_folder_id:
        # Check user has access to the parent folder
        parent_folder_db = await folders_db.get_for_user_or_workspace(
            app,
            folder_id=parent_folder_id,
            product_name=product_name,
            user_id=user_id if workspace_is_private else None,
            workspace_id=workspace_id,
        )
        if workspace_id and parent_folder_db.workspace_id != workspace_id:
            # Check parent folder id exists inside the same workspace
            raise WorkspaceAccessForbiddenError(
                reason=f"Folder {parent_folder_id} does not exists in workspace {workspace_id}."
            )

    folder_db = await folders_db.create(
        app,
        product_name=product_name,
        created_by_gid=user["primary_gid"],
        folder_name=name,
        parent_folder_id=parent_folder_id,
        user_id=user_id if workspace_is_private else None,
        workspace_id=workspace_id,
    )
    return FolderGet(
        folder_id=folder_db.folder_id,
        parent_folder_id=folder_db.parent_folder_id,
        name=folder_db.name,
        created_at=folder_db.created,
        modified_at=folder_db.modified,
        trashed_at=folder_db.trashed_at,
        owner=folder_db.created_by_gid,
        workspace_id=workspace_id,
        my_access_rights=user_folder_access_rights,
    )


async def get_folder(
    app: web.Application,
    user_id: UserID,
    folder_id: FolderID,
    product_name: ProductName,
) -> FolderGet:
    folder_db = await folders_db.get(
        app, folder_id=folder_id, product_name=product_name
    )

    workspace_is_private = True
    user_folder_access_rights = AccessRights(read=True, write=True, delete=True)
    if folder_db.workspace_id:
        user_workspace_access_rights = await check_user_workspace_access(
            app,
            user_id=user_id,
            workspace_id=folder_db.workspace_id,
            product_name=product_name,
            permission="read",
        )
        workspace_is_private = False
        user_folder_access_rights = user_workspace_access_rights.my_access_rights

    folder_db = await folders_db.get_for_user_or_workspace(
        app,
        folder_id=folder_id,
        product_name=product_name,
        user_id=user_id if workspace_is_private else None,
        workspace_id=folder_db.workspace_id,
    )
    return FolderGet(
        folder_id=folder_db.folder_id,
        parent_folder_id=folder_db.parent_folder_id,
        name=folder_db.name,
        created_at=folder_db.created,
        modified_at=folder_db.modified,
        trashed_at=folder_db.trashed_at,
        owner=folder_db.created_by_gid,
        workspace_id=folder_db.workspace_id,
        my_access_rights=user_folder_access_rights,
    )


async def list_folders(
    app: web.Application,
    user_id: UserID,
    product_name: ProductName,
    folder_id: FolderID | None,
    workspace_id: WorkspaceID | None,
    trashed: bool | None,
    offset: NonNegativeInt,
    limit: int,
    order_by: OrderBy,
) -> FolderGetPage:
    # NOTE: Folder access rights for listing are checked within the listing DB function.

    total_count, folders = await folders_db.list_(
        app,
        product_name=product_name,
        user_id=user_id,
        folder_query=(
            FolderQuery(folder_scope=FolderScope.SPECIFIC, folder_id=folder_id)
            if folder_id
            else FolderQuery(folder_scope=FolderScope.ROOT)
        ),
        workspace_query=(
            WorkspaceQuery(
                workspace_scope=WorkspaceScope.SHARED, workspace_id=workspace_id
            )
            if workspace_id
            else WorkspaceQuery(workspace_scope=WorkspaceScope.PRIVATE)
        ),
        filter_trashed=trashed,
        filter_by_text=None,
        offset=offset,
        limit=limit,
        order_by=order_by,
    )
    return FolderGetPage(
        items=[
            FolderGet(
                folder_id=folder.folder_id,
                parent_folder_id=folder.parent_folder_id,
                name=folder.name,
                created_at=folder.created,
                modified_at=folder.modified,
                trashed_at=folder.trashed_at,
                owner=folder.created_by_gid,
                workspace_id=folder.workspace_id,
                my_access_rights=folder.my_access_rights,
            )
            for folder in folders
        ],
        total=total_count,
    )


async def list_folders_full_search(
    app: web.Application,
    user_id: UserID,
    product_name: ProductName,
    text: str | None,
    trashed: bool | None,
    offset: NonNegativeInt,
    limit: int,
    order_by: OrderBy,
) -> FolderGetPage:
    # NOTE: Folder access rights for listing are checked within the listing DB function.

    total_count, folders = await folders_db.list_(
        app,
        product_name=product_name,
        user_id=user_id,
        folder_query=FolderQuery(folder_scope=FolderScope.ALL),
        workspace_query=WorkspaceQuery(workspace_scope=WorkspaceScope.ALL),
        filter_trashed=trashed,
        filter_by_text=text,
        offset=offset,
        limit=limit,
        order_by=order_by,
    )
    return FolderGetPage(
        items=[
            FolderGet(
                folder_id=folder.folder_id,
                parent_folder_id=folder.parent_folder_id,
                name=folder.name,
                created_at=folder.created,
                modified_at=folder.modified,
                trashed_at=folder.trashed_at,
                owner=folder.created_by_gid,
                workspace_id=folder.workspace_id,
                my_access_rights=folder.my_access_rights,
            )
            for folder in folders
        ],
        total=total_count,
    )


async def update_folder(
    app: web.Application,
    user_id: UserID,
    folder_id: FolderID,
    *,
    name: str,
    parent_folder_id: FolderID | None,
    product_name: ProductName,
) -> FolderGet:
    folder_db = await folders_db.get(
        app, folder_id=folder_id, product_name=product_name
    )

    workspace_is_private = True
    user_folder_access_rights = AccessRights(read=True, write=True, delete=True)
    if folder_db.workspace_id:
        user_workspace_access_rights = await check_user_workspace_access(
            app,
            user_id=user_id,
            workspace_id=folder_db.workspace_id,
            product_name=product_name,
            permission="write",
        )
        workspace_is_private = False
        user_folder_access_rights = user_workspace_access_rights.my_access_rights

    # Check user has access to the folder
    await folders_db.get_for_user_or_workspace(
        app,
        folder_id=folder_id,
        product_name=product_name,
        user_id=user_id if workspace_is_private else None,
        workspace_id=folder_db.workspace_id,
    )

    if folder_db.parent_folder_id != parent_folder_id and parent_folder_id is not None:
        # Check user has access to the parent folder
        await folders_db.get_for_user_or_workspace(
            app,
            folder_id=parent_folder_id,
            product_name=product_name,
            user_id=user_id if workspace_is_private else None,
            workspace_id=folder_db.workspace_id,
        )
        # Do not allow to move to a child folder id
        _child_folders = await folders_db.get_folders_recursively(
            app, folder_id=folder_id, product_name=product_name
        )
        if parent_folder_id in _child_folders:
            raise FolderValueNotPermittedError(
                reason="Parent folder id should not be one of children"
            )

    folder_db = await folders_db.update(
        app,
        folders_id_or_ids=folder_id,
        name=name,
        parent_folder_id=parent_folder_id,
        product_name=product_name,
    )
    return FolderGet(
        folder_id=folder_db.folder_id,
        parent_folder_id=folder_db.parent_folder_id,
        name=folder_db.name,
        created_at=folder_db.created,
        modified_at=folder_db.modified,
        trashed_at=folder_db.trashed_at,
        owner=folder_db.created_by_gid,
        workspace_id=folder_db.workspace_id,
        my_access_rights=user_folder_access_rights,
    )


async def delete_folder(
    app: web.Application,
    user_id: UserID,
    folder_id: FolderID,
    product_name: ProductName,
) -> None:
    folder_db = await folders_db.get(
        app, folder_id=folder_id, product_name=product_name
    )

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

    # Check user has access to the folder
    await folders_db.get_for_user_or_workspace(
        app,
        folder_id=folder_id,
        product_name=product_name,
        user_id=user_id if workspace_is_private else None,
        workspace_id=folder_db.workspace_id,
    )

    # 1. Delete folder content
    # 1.1 Delete all child projects that I am an owner
    project_id_list: list[
        ProjectID
    ] = await folders_db.get_projects_recursively_only_if_user_is_owner(
        app,
        folder_id=folder_id,
        private_workspace_user_id_or_none=user_id if workspace_is_private else None,
        user_id=user_id,
        product_name=product_name,
    )

    # fire and forget task for project deletion
    for project_id in project_id_list:
        fire_and_forget_task(
            submit_delete_project_task(
                app,
                project_uuid=project_id,
                user_id=user_id,
                simcore_user_agent=UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE,
            ),
            task_suffix_name=f"delete_project_task_{project_id}",
            fire_and_forget_tasks_collection=app[APP_FIRE_AND_FORGET_TASKS_KEY],
        )

    # 1.2 Delete all child folders
    await folders_db.delete_recursively(
        app, folder_id=folder_id, product_name=product_name
    )
