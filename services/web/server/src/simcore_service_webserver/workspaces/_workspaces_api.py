# pylint: disable=unused-argument

import logging

from aiohttp import web
from models_library.access_rights import AccessRights
from models_library.api_schemas_webserver.workspaces import (
    WorkspaceGet,
    WorkspaceGetPage,
)
from models_library.products import ProductName
from models_library.rest_ordering import OrderBy
from models_library.users import UserID
from models_library.workspaces import UserWorkspaceDB, WorkspaceID
from pydantic import NonNegativeInt
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
        owner_primary_gid=workspace_db.owner_primary_gid,
        my_access_rights=AccessRights(
            read=workspace_db.read, write=workspace_db.write, delete=workspace_db.delete
        ),
    )


async def get_workspace(
    app: web.Application,
    user_id: UserID,
    workspace_id: WorkspaceID,
    product_name: ProductName,
) -> WorkspaceGet:
    workspace_db: UserWorkspaceDB = await db.get_workspace_for_user(
        app=app, user_id=user_id, workspace_id=workspace_id, product_name=product_name
    )
    if workspace_db.read is False:
        raise WorkspaceAccessForbiddenError(
            reason=f"User {user_id} does not have read permission on workspace {workspace_id}."
        )
    return WorkspaceGet(
        workspace_id=workspace_db.workspace_id,
        name=workspace_db.name,
        description=workspace_db.description,
        thumbnail=workspace_db.thumbnail,
        created_at=workspace_db.created,
        modified_at=workspace_db.modified,
        owner_primary_gid=workspace_db.owner_primary_gid,
        my_access_rights=AccessRights(
            read=workspace_db.read, write=workspace_db.write, delete=workspace_db.delete
        ),
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
                owner_primary_gid=workspace.owner_primary_gid,
                my_access_rights=AccessRights(
                    read=workspace.read, write=workspace.write, delete=workspace.delete
                ),
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
    workspace_db: UserWorkspaceDB = await db.get_workspace_for_user(
        app=app, user_id=user_id, workspace_id=workspace_id, product_name=product_name
    )
    if workspace_db.write is False:
        raise WorkspaceAccessForbiddenError(
            reason=f"User {user_id} does not have write permission on workspace {workspace_id}."
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
        owner_primary_gid=workspace_db.owner_primary_gid,
        my_access_rights=AccessRights(
            read=workspace_db.read, write=workspace_db.write, delete=workspace_db.delete
        ),
    )


async def delete_workspace(
    app: web.Application,
    user_id: UserID,
    workspace_id: WorkspaceID,
    product_name: ProductName,
) -> None:
    workspace_db: UserWorkspaceDB = await db.get_workspace_for_user(
        app=app, user_id=user_id, workspace_id=workspace_id, product_name=product_name
    )
    if workspace_db.delete is False:
        raise WorkspaceAccessForbiddenError(
            reason=f"User {user_id} does not have delete permission on workspace {workspace_id}"
        )

    await db.delete_workspace(app, workspace_id=workspace_id, product_name=product_name)
