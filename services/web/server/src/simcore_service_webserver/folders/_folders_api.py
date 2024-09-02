# pylint: disable=unused-argument

import logging

from aiohttp import web
from models_library.api_schemas_webserver.folders_v2 import FolderGet, FolderGetPage
from models_library.folders import FolderID
from models_library.products import ProductName
from models_library.rest_ordering import OrderBy
from models_library.users import UserID
from models_library.workspaces import WorkspaceID
from pydantic import NonNegativeInt

from ..users.api import get_user
from ..workspaces.api import get_workspace
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

    _personal_workspace_user_id_or_none: UserID | None = user_id
    if workspace_id:
        # Check access to workspace
        workspace = await get_workspace(
            app, user_id=user_id, workspace_id=workspace_id, product_name=product_name
        )
        if workspace.my_access_rights.write is False:
            raise WorkspaceAccessForbiddenError(
                reason=f"User {user_id} does not have write permission on workspace {workspace_id}."
            )
        # Setup folder user id to None, as this is not a private workspace
        _personal_workspace_user_id_or_none = None

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
            user_id=_personal_workspace_user_id_or_none,
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
        user_id=_personal_workspace_user_id_or_none,
        workspace_id=workspace_id,
    )
    return FolderGet(
        folder_id=folder_db.folder_id,
        parent_folder_id=folder_db.parent_folder_id,
        name=folder_db.name,
        created_at=folder_db.created,
        modified_at=folder_db.modified,
        owner=folder_db.created_by_gid,
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

    _personal_workspace_user_id_or_none: UserID | None = user_id
    if folder_db.workspace_id:
        # Check access to workspace
        await get_workspace(
            app,
            user_id=user_id,
            workspace_id=folder_db.workspace_id,
            product_name=product_name,
        )
        # Setup folder user id to None, as this is not a private workspace
        _personal_workspace_user_id_or_none = None

    folder_db = await folders_db.get_for_user_or_workspace(
        app,
        folder_id=folder_id,
        product_name=product_name,
        user_id=_personal_workspace_user_id_or_none,
        workspace_id=folder_db.workspace_id,
    )
    return FolderGet(
        folder_id=folder_db.folder_id,
        parent_folder_id=folder_db.parent_folder_id,
        name=folder_db.name,
        created_at=folder_db.created,
        modified_at=folder_db.modified,
        owner=folder_db.created_by_gid,
    )


async def list_folders(
    app: web.Application,
    user_id: UserID,
    product_name: ProductName,
    folder_id: FolderID | None,
    workspace_id: WorkspaceID | None,
    offset: NonNegativeInt,
    limit: int,
    order_by: OrderBy,
) -> FolderGetPage:
    _personal_workspace_user_id_or_none: UserID | None = user_id

    # Check user access to workspace
    if workspace_id:
        await get_workspace(
            app, user_id=user_id, workspace_id=workspace_id, product_name=product_name
        )
        # Setup folder user id to None, as this is not a personal workspace
        _personal_workspace_user_id_or_none = None

    if folder_id:
        # Check user access to folder
        await folders_db.get_for_user_or_workspace(
            app,
            folder_id=folder_id,
            product_name=product_name,
            user_id=_personal_workspace_user_id_or_none,
            workspace_id=workspace_id,
        )

    total_count, folders = await folders_db.list_(
        app,
        content_of_folder_id=folder_id,
        user_id=_personal_workspace_user_id_or_none,
        workspace_id=workspace_id,
        product_name=product_name,
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
                owner=folder.created_by_gid,
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

    _personal_workspace_user_id_or_none: UserID | None = user_id
    if folder_db.workspace_id:
        # Check access to workspace
        workspace = await get_workspace(
            app,
            user_id=user_id,
            workspace_id=folder_db.workspace_id,
            product_name=product_name,
        )
        if workspace.my_access_rights.write is False:
            raise WorkspaceAccessForbiddenError(
                reason=f"User {user_id} does not have write permission on workspace {folder_db.workspace_id}."
            )
        # Setup folder user id to None, as this is not a private workspace
        _personal_workspace_user_id_or_none = None

    # Check user has acces to the folder
    await folders_db.get_for_user_or_workspace(
        app,
        folder_id=folder_id,
        product_name=product_name,
        user_id=_personal_workspace_user_id_or_none,
        workspace_id=folder_db.workspace_id,
    )

    folder_db = await folders_db.update(
        app,
        folder_id=folder_id,
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
        owner=folder_db.created_by_gid,
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

    _personal_workspace_user_id_or_none: UserID | None = user_id
    if folder_db.workspace_id:
        # Check access to workspace
        workspace = await get_workspace(
            app,
            user_id=user_id,
            workspace_id=folder_db.workspace_id,
            product_name=product_name,
        )
        if workspace.my_access_rights.delete is False:
            raise WorkspaceAccessForbiddenError(
                reason=f"User {user_id} does not have delete permission on workspace {folder_db.workspace_id}."
            )
        # Setup folder user id to None, as this is not a private workspace
        _personal_workspace_user_id_or_none = None

    # Check user has acces to the folder
    await folders_db.get_for_user_or_workspace(
        app,
        folder_id=folder_id,
        product_name=product_name,
        user_id=_personal_workspace_user_id_or_none,
        workspace_id=folder_db.workspace_id,
    )

    await folders_db.delete(app, folder_id=folder_id, product_name=product_name)
