import logging
from datetime import datetime

from aiohttp import web
from models_library.groups import GroupID
from models_library.products import ProductName
from models_library.users import UserID
from models_library.workspaces import UserWorkspaceWithAccessRights, WorkspaceID
from pydantic import BaseModel, ConfigDict

from ..users import users_service
from . import _groups_repository as workspaces_groups_db
from . import _workspaces_repository as workspaces_workspaces_repository
from ._groups_repository import WorkspaceGroupGetDB
from ._workspaces_service_crud_read import check_user_workspace_access
from .errors import WorkspaceAccessForbiddenError

log = logging.getLogger(__name__)


class WorkspaceGroupGet(BaseModel):
    gid: GroupID
    read: bool
    write: bool
    delete: bool
    created: datetime
    modified: datetime

    model_config = ConfigDict(from_attributes=True)


async def create_workspace_group(
    app: web.Application,
    *,
    user_id: UserID,
    workspace_id: WorkspaceID,
    group_id: GroupID,
    read: bool,
    write: bool,
    delete: bool,
    product_name: ProductName,
) -> WorkspaceGroupGet:
    await check_user_workspace_access(
        app=app,
        user_id=user_id,
        workspace_id=workspace_id,
        product_name=product_name,
        permission="write",
    )

    workspace_group_db: WorkspaceGroupGetDB = (
        await workspaces_groups_db.create_workspace_group(
            app=app,
            workspace_id=workspace_id,
            group_id=group_id,
            read=read,
            write=write,
            delete=delete,
        )
    )
    workspace_group_api: WorkspaceGroupGet = WorkspaceGroupGet(
        **workspace_group_db.model_dump()
    )

    return workspace_group_api


async def list_workspace_groups_by_user_and_workspace(
    app: web.Application,
    *,
    user_id: UserID,
    workspace_id: WorkspaceID,
    product_name: ProductName,
) -> list[WorkspaceGroupGet]:
    await check_user_workspace_access(
        app=app,
        user_id=user_id,
        workspace_id=workspace_id,
        product_name=product_name,
        permission="read",
    )

    workspace_groups_db: list[WorkspaceGroupGetDB] = (
        await workspaces_groups_db.list_workspace_groups(
            app=app, workspace_id=workspace_id
        )
    )

    workspace_groups_api: list[WorkspaceGroupGet] = [
        WorkspaceGroupGet.model_validate(group) for group in workspace_groups_db
    ]

    return workspace_groups_api


async def list_workspace_groups_with_read_access_by_workspace(
    app: web.Application,
    *,
    workspace_id: WorkspaceID,
) -> list[WorkspaceGroupGet]:
    workspace_groups_db: list[WorkspaceGroupGetDB] = (
        await workspaces_groups_db.list_workspace_groups(
            app=app, workspace_id=workspace_id
        )
    )

    workspace_groups_api: list[WorkspaceGroupGet] = [
        WorkspaceGroupGet.model_validate(group)
        for group in workspace_groups_db
        if group.read is True
    ]

    return workspace_groups_api


async def update_workspace_group(
    app: web.Application,
    *,
    user_id: UserID,
    workspace_id: WorkspaceID,
    group_id: GroupID,
    read: bool,
    write: bool,
    delete: bool,
    product_name: ProductName,
) -> WorkspaceGroupGet:
    workspace: UserWorkspaceWithAccessRights = (
        await workspaces_workspaces_repository.get_workspace_for_user(
            app=app,
            user_id=user_id,
            workspace_id=workspace_id,
            product_name=product_name,
        )
    )
    if workspace.my_access_rights.write is False:
        raise WorkspaceAccessForbiddenError(
            details=f"User does not have write access to workspace {workspace_id}"
        )
    if workspace.owner_primary_gid == group_id:
        user: dict = await users_service.get_user(app, user_id)
        if user["primary_gid"] != workspace.owner_primary_gid:
            # Only the owner of the workspace can modify the owner group
            raise WorkspaceAccessForbiddenError(
                details=f"User does not have access to modify owner workspace group in workspace {workspace_id}"
            )

    workspace_group_db: WorkspaceGroupGetDB = (
        await workspaces_groups_db.update_workspace_group(
            app=app,
            workspace_id=workspace_id,
            group_id=group_id,
            read=read,
            write=write,
            delete=delete,
        )
    )

    workspace_api: WorkspaceGroupGet = WorkspaceGroupGet(
        **workspace_group_db.model_dump()
    )
    return workspace_api


async def delete_workspace_group(
    app: web.Application,
    *,
    user_id: UserID,
    workspace_id: WorkspaceID,
    group_id: GroupID,
    product_name: ProductName,
) -> None:
    user: dict = await users_service.get_user(app, user_id=user_id)
    workspace: UserWorkspaceWithAccessRights = (
        await workspaces_workspaces_repository.get_workspace_for_user(
            app=app,
            user_id=user_id,
            workspace_id=workspace_id,
            product_name=product_name,
        )
    )
    if user["primary_gid"] != group_id and workspace.my_access_rights.delete is False:
        raise WorkspaceAccessForbiddenError(
            details=f"User does not have delete access to workspace {workspace_id}"
        )
    if (
        workspace.owner_primary_gid == group_id
        and user["primary_gid"] != workspace.owner_primary_gid
    ):
        # Only the owner of the workspace can delete the owner group
        raise WorkspaceAccessForbiddenError(
            details=f"User does not have access to modify owner workspace group in workspace {workspace_id}"
        )

    await workspaces_groups_db.delete_workspace_group(
        app=app, workspace_id=workspace_id, group_id=group_id
    )
