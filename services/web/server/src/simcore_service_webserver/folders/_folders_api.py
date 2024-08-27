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
from ..workspaces.errors import WorkspaceAccessForbiddenError
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
    user = get_user(app, user_id=user_id)

    _private_workspace_user_id = user_id
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
        _private_workspace_user_id = None

    folder_db = await folders_db.create_folder(
        app,
        product_name=product_name,
        created_by_gid=user["primary_gid"],
        folder_name=name,
        parent_folder_id=parent_folder_id,
        user_id=_private_workspace_user_id,
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
    workspace_id: WorkspaceID | None,
) -> FolderGet:
    _private_workspace_user_id = user_id
    if workspace_id:
        # Check access to workspace
        await get_workspace(
            app, user_id=user_id, workspace_id=workspace_id, product_name=product_name
        )
        # Setup folder user id to None, as this is not a private workspace
        _private_workspace_user_id = None

    folder_db = await folders_db.get_folder(
        app,
        folder_id=folder_id,
        product_name=product_name,
        user_id=_private_workspace_user_id,
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
    _private_workspace_user_id = user_id
    if workspace_id:
        # Check access to workspace
        await get_workspace(
            app, user_id=user_id, workspace_id=workspace_id, product_name=product_name
        )
        # Setup folder user id to None, as this is not a private workspace
        _private_workspace_user_id = None

    total_count, folders = await folders_db.list_folders(
        app,
        content_of_folder_id=folder_id,
        user_id=_private_workspace_user_id,
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
    name: str,
    parent_folder_id: FolderID | None,
    workspace_id: WorkspaceID | None,
    product_name: ProductName,
) -> FolderGet:
    _private_workspace_user_id = user_id
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
        _private_workspace_user_id = None

    # Check user has acces to the folder
    await folders_db.get_folder(
        app,
        folder_id=folder_id,
        product_name=product_name,
        user_id=_private_workspace_user_id,
        workspace_id=workspace_id,
    )

    folder_db = await folders_db.update_folder(
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
    workspace_id: WorkspaceID | None,
    product_name: ProductName,
) -> None:
    _private_workspace_user_id = user_id
    if workspace_id:
        # Check access to workspace
        workspace = await get_workspace(
            app, user_id=user_id, workspace_id=workspace_id, product_name=product_name
        )
        if workspace.my_access_rights.delete is False:
            raise WorkspaceAccessForbiddenError(
                reason=f"User {user_id} does not have delete permission on workspace {workspace_id}."
            )
        # Setup folder user id to None, as this is not a private workspace
        _private_workspace_user_id = None

    # Check user has acces to the folder
    await folders_db.get_folder(
        app,
        folder_id=folder_id,
        product_name=product_name,
        user_id=_private_workspace_user_id,
        workspace_id=workspace_id,
    )

    await folders_db.delete_folder(app, folder_id=folder_id, product_name=product_name)
