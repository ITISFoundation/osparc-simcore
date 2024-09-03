# pylint: disable=unused-argument

import logging

from aiohttp import web
from models_library.api_schemas_webserver.workspaces import (
    WorkspaceGet,
    WorkspaceGetPage,
)
from models_library.products import ProductName
from models_library.rest_ordering import OrderBy
from models_library.users import UserID
from models_library.workspaces import UserWorkspaceAccessRightsDB, WorkspaceID
from pydantic import NonNegativeInt
from simcore_service_webserver.projects._db_utils import PermissionStr
from simcore_service_webserver.workspaces.errors import WorkspaceAccessForbiddenError

from ..users.api import get_user
from . import _workspaces_db as db

_logger = logging.getLogger(__name__)


async def create_workspace(
    app: web.Application,
    user_id: UserID,
    name: str,
    description: str | None,
    thumbnail: str | None,
    product_name: ProductName,
) -> WorkspaceGet:
    user = await get_user(app, user_id=user_id)

    created_workspace_db = await db.create_workspace(
        app,
        product_name=product_name,
        owner_primary_gid=user["primary_gid"],
        name=name,
        description=description,
        thumbnail=thumbnail,
    )
    workspace_db = await db.get_workspace_for_user(
        app,
        user_id=user_id,
        workspace_id=created_workspace_db.workspace_id,
        product_name=product_name,
    )
    return WorkspaceGet(
        workspace_id=workspace_db.workspace_id,
        name=workspace_db.name,
        description=workspace_db.description,
        thumbnail=workspace_db.thumbnail,
        created_at=workspace_db.created,
        modified_at=workspace_db.modified,
        my_access_rights=workspace_db.my_access_rights,
        access_rights=workspace_db.access_rights,
    )


async def get_workspace(
    app: web.Application,
    user_id: UserID,
    workspace_id: WorkspaceID,
    product_name: ProductName,
) -> WorkspaceGet:
    workspace_db = await check_user_workspace_access(
        app=app,
        user_id=user_id,
        workspace_id=workspace_id,
        product_name=product_name,
        permission="read",
    )
    return WorkspaceGet(
        workspace_id=workspace_db.workspace_id,
        name=workspace_db.name,
        description=workspace_db.description,
        thumbnail=workspace_db.thumbnail,
        created_at=workspace_db.created,
        modified_at=workspace_db.modified,
        my_access_rights=workspace_db.my_access_rights,
        access_rights=workspace_db.access_rights,
    )


async def list_workspaces(
    app: web.Application,
    user_id: UserID,
    product_name: ProductName,
    offset: NonNegativeInt,
    limit: int,
    order_by: OrderBy,
) -> WorkspaceGetPage:
    total_count, workspaces = await db.list_workspaces_for_user(
        app,
        user_id=user_id,
        product_name=product_name,
        offset=offset,
        limit=limit,
        order_by=order_by,
    )

    return WorkspaceGetPage(
        items=[
            WorkspaceGet(
                workspace_id=workspace.workspace_id,
                name=workspace.name,
                description=workspace.description,
                thumbnail=workspace.thumbnail,
                created_at=workspace.created,
                modified_at=workspace.modified,
                my_access_rights=workspace.my_access_rights,
                access_rights=workspace.access_rights,
            )
            for workspace in workspaces
        ],
        total=total_count,
    )


async def update_workspace(
    app: web.Application,
    user_id: UserID,
    workspace_id: WorkspaceID,
    name: str,
    description: str | None,
    thumbnail: str | None,
    product_name: ProductName,
) -> WorkspaceGet:
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
        name=name,
        description=description,
        thumbnail=thumbnail,
        product_name=product_name,
    )
    workspace_db = await db.get_workspace_for_user(
        app,
        user_id=user_id,
        workspace_id=workspace_id,
        product_name=product_name,
    )
    return WorkspaceGet(
        workspace_id=workspace_db.workspace_id,
        name=workspace_db.name,
        description=workspace_db.description,
        thumbnail=workspace_db.thumbnail,
        created_at=workspace_db.created,
        modified_at=workspace_db.modified,
        my_access_rights=workspace_db.my_access_rights,
        access_rights=workspace_db.access_rights,
    )


async def delete_workspace(
    app: web.Application,
    user_id: UserID,
    workspace_id: WorkspaceID,
    product_name: ProductName,
) -> None:
    await check_user_workspace_access(
        app=app,
        user_id=user_id,
        workspace_id=workspace_id,
        product_name=product_name,
        permission="delete",
    )

    await db.delete_workspace(app, workspace_id=workspace_id, product_name=product_name)


async def check_user_workspace_access(
    app: web.Application,
    *,
    user_id: UserID,
    workspace_id: WorkspaceID,
    product_name: ProductName,
    permission: PermissionStr = "read",
) -> UserWorkspaceAccessRightsDB:
    """
    Raises WorkspaceAccessForbiddenError if no access
    """
    workspace_db: UserWorkspaceAccessRightsDB = await db.get_workspace_for_user(
        app=app, user_id=user_id, workspace_id=workspace_id, product_name=product_name
    )
    if getattr(workspace_db.my_access_rights, permission, False) is False:
        raise WorkspaceAccessForbiddenError
    return workspace_db
