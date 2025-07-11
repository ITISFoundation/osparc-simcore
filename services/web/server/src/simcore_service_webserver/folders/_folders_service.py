# pylint: disable=unused-argument

import logging

from aiohttp import web
from models_library.access_rights import AccessRights
from models_library.folders import FolderID, FolderQuery, FolderScope, FolderTuple
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.rest_ordering import OrderBy
from models_library.users import UserID
from models_library.workspaces import WorkspaceID, WorkspaceQuery, WorkspaceScope
from pydantic import NonNegativeInt

from ..projects._projects_service import delete_project_by_user
from ..users.users_service import get_user
from ..workspaces.api import check_user_workspace_access
from ..workspaces.errors import (
    WorkspaceAccessForbiddenError,
    WorkspaceFolderInconsistencyError,
)
from . import _folders_repository
from .errors import FolderValueNotPermittedError

_logger = logging.getLogger(__name__)


async def create_folder(
    app: web.Application,
    user_id: UserID,
    name: str,
    parent_folder_id: FolderID | None,
    product_name: ProductName,
    workspace_id: WorkspaceID | None,
) -> FolderTuple:
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
            parent_folder_db = await _folders_repository.get(
                app, folder_id=parent_folder_id, product_name=product_name
            )
            if parent_folder_db.workspace_id != workspace_id:
                raise WorkspaceFolderInconsistencyError(
                    folder_id=parent_folder_id, workspace_id=workspace_id
                )

    if parent_folder_id:
        # Check user has access to the parent folder
        parent_folder_db = await _folders_repository.get_for_user_or_workspace(
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

    folder_db = await _folders_repository.create(
        app,
        product_name=product_name,
        created_by_gid=user["primary_gid"],
        folder_name=name,
        parent_folder_id=parent_folder_id,
        user_id=user_id if workspace_is_private else None,
        workspace_id=workspace_id,
    )

    assert folder_db.trashed_by is None  # nosec

    return FolderTuple(
        folder_db=folder_db,
        trashed_by_primary_gid=None,  # cannot be trashed upon creation
        my_access_rights=user_folder_access_rights,
    )


async def get_folder(
    app: web.Application,
    user_id: UserID,
    folder_id: FolderID,
    product_name: ProductName,
) -> FolderTuple:
    folder_db = await _folders_repository.get(
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

    folder_db = await _folders_repository.get_for_user_or_workspace(
        app,
        folder_id=folder_id,
        product_name=product_name,
        user_id=user_id if workspace_is_private else None,
        workspace_id=folder_db.workspace_id,
    )

    trashed_by_primary_gid = (
        await _folders_repository.get_trashed_by_primary_gid(
            app, folder_id=folder_db.folder_id
        )
        if folder_db.trashed_by
        else None
    )

    return FolderTuple(
        folder_db=folder_db,
        trashed_by_primary_gid=trashed_by_primary_gid,
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
) -> tuple[list[FolderTuple], int]:
    # NOTE: Folder access rights for listing are checked within the listing DB function.

    total_count, folders = await _folders_repository.list_(
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

    _trashed_by_primary_gid_values = (
        await _folders_repository.batch_get_trashed_by_primary_gid(
            app, folders_ids=[f.folder_id for f in folders]
        )
    )

    return (
        [
            FolderTuple(
                folder_db=folder,
                trashed_by_primary_gid=trashed_by_primary_gid,
                my_access_rights=folder.my_access_rights,
            )
            for folder, trashed_by_primary_gid in zip(
                folders, _trashed_by_primary_gid_values, strict=True
            )
        ],
        total_count,
    )


async def list_folders_full_depth(
    app: web.Application,
    *,
    user_id: UserID,
    product_name: ProductName,
    text: str | None,
    trashed: bool | None,
    offset: NonNegativeInt,
    limit: int,
    order_by: OrderBy,
) -> tuple[list[FolderTuple], int]:
    # NOTE: Folder access rights for listing are checked within the listing DB function.

    total_count, folders = await _folders_repository.list_(
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
    _trashed_by_primary_gid_values = (
        await _folders_repository.batch_get_trashed_by_primary_gid(
            app, folders_ids=[f.folder_id for f in folders]
        )
    )

    return (
        [
            FolderTuple(
                folder_db=folder,
                trashed_by_primary_gid=trashed_by_primary_gid,
                my_access_rights=folder.my_access_rights,
            )
            for folder, trashed_by_primary_gid in zip(
                folders, _trashed_by_primary_gid_values, strict=True
            )
        ],
        total_count,
    )


async def update_folder(
    app: web.Application,
    user_id: UserID,
    folder_id: FolderID,
    *,
    name: str,
    parent_folder_id: FolderID | None,
    product_name: ProductName,
) -> FolderTuple:
    folder_db = await _folders_repository.get(
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
    await _folders_repository.get_for_user_or_workspace(
        app,
        folder_id=folder_id,
        product_name=product_name,
        user_id=user_id if workspace_is_private else None,
        workspace_id=folder_db.workspace_id,
    )

    if folder_db.parent_folder_id != parent_folder_id and parent_folder_id is not None:
        # Check user has access to the parent folder
        await _folders_repository.get_for_user_or_workspace(
            app,
            folder_id=parent_folder_id,
            product_name=product_name,
            user_id=user_id if workspace_is_private else None,
            workspace_id=folder_db.workspace_id,
        )
        # Do not allow to move to a child folder id
        _child_folders = await _folders_repository.get_folders_recursively(
            app, folder_id=folder_id, product_name=product_name
        )
        if parent_folder_id in _child_folders:
            raise FolderValueNotPermittedError(
                reason="Parent folder id should not be one of children"
            )

    folder_db = await _folders_repository.update(
        app,
        folders_id_or_ids=folder_id,
        name=name,
        parent_folder_id=parent_folder_id,
        product_name=product_name,
    )

    trashed_by_primary_gid = (
        await _folders_repository.get_trashed_by_primary_gid(
            app, folder_id=folder_db.folder_id
        )
        if folder_db.trashed_by
        else None
    )

    return FolderTuple(
        folder_db=folder_db,
        trashed_by_primary_gid=trashed_by_primary_gid,
        my_access_rights=user_folder_access_rights,
    )


async def delete_folder_with_all_content(
    app: web.Application,
    user_id: UserID,
    folder_id: FolderID,
    product_name: ProductName,
) -> None:
    folder_db = await _folders_repository.get(
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
    await _folders_repository.get_for_user_or_workspace(
        app,
        folder_id=folder_id,
        product_name=product_name,
        user_id=user_id if workspace_is_private else None,
        workspace_id=folder_db.workspace_id,
    )

    # 1. Delete folder content
    # 1.1 Delete all child projects that I am an owner
    # NOTE: The reason for this is to be cautious and not delete projects by accident that
    # are not owned by the user (even if the user was granted delete permissions). As a consequence, after deleting the folder,
    # projects that the user does not own will appear in the root. (Maybe this can be changed as we now have a trash system).
    project_id_list: list[ProjectID] = (
        await _folders_repository.get_projects_recursively_only_if_user_is_owner(
            app,
            folder_id=folder_id,
            private_workspace_user_id_or_none=user_id if workspace_is_private else None,
            user_id=user_id,
            product_name=product_name,
        )
    )

    for project_id in project_id_list:
        await delete_project_by_user(
            app,
            project_uuid=project_id,
            user_id=user_id,
        )

    # 1.2 Delete all child folders
    await _folders_repository.delete_recursively(
        app, folder_id=folder_id, product_name=product_name
    )
