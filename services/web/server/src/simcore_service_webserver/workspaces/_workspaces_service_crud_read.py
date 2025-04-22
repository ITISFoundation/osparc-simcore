# pylint: disable=unused-argument

import logging

from aiohttp import web
from models_library.products import ProductName
from models_library.rest_ordering import OrderBy
from models_library.users import UserID
from models_library.workspaces import (
    UserWorkspaceWithAccessRights,
    WorkspaceID,
)
from pydantic import NonNegativeInt

from ..projects._projects_repository_legacy_utils import PermissionStr
from . import _workspaces_repository as db
from .errors import WorkspaceAccessForbiddenError

_logger = logging.getLogger(__name__)


async def get_workspace(
    app: web.Application,
    *,
    user_id: UserID,
    workspace_id: WorkspaceID,
    product_name: ProductName,
) -> UserWorkspaceWithAccessRights:
    return await get_user_workspace(
        app=app,
        user_id=user_id,
        workspace_id=workspace_id,
        product_name=product_name,
        permission="read",
    )


async def list_workspaces(
    app: web.Application,
    *,
    user_id: UserID,
    product_name: ProductName,
    filter_trashed: bool | None,
    filter_by_text: str | None,
    offset: NonNegativeInt,
    limit: int,
    order_by: OrderBy,
) -> tuple[int, list[UserWorkspaceWithAccessRights]]:
    total_count, workspaces = await db.list_workspaces_for_user(
        app,
        user_id=user_id,
        product_name=product_name,
        filter_trashed=filter_trashed,
        filter_by_text=filter_by_text,
        offset=offset,
        limit=limit,
        order_by=order_by,
    )

    return total_count, workspaces


async def get_user_workspace(
    app: web.Application,
    *,
    user_id: UserID,
    workspace_id: WorkspaceID,
    product_name: ProductName,
    permission: PermissionStr | None,
) -> UserWorkspaceWithAccessRights:
    """

    Here checking access is optional. A use case is when the caller has guarantees that
    `user_id` has granted access and we do not want to re-check

    Raises:
        WorkspaceAccessForbiddenError: if permission not None and user_id does not have access
    """
    workspace: UserWorkspaceWithAccessRights = await db.get_workspace_for_user(
        app=app, user_id=user_id, workspace_id=workspace_id, product_name=product_name
    )

    # NOTE: check here is optional
    if permission is not None:
        has_user_granted_permission = getattr(
            workspace.my_access_rights, permission, False
        )
        if not has_user_granted_permission:
            raise WorkspaceAccessForbiddenError(
                user_id=user_id,
                workspace_id=workspace_id,
                product_name=product_name,
                permission_checked=permission,
            )
    return workspace


async def check_user_workspace_access(
    app: web.Application,
    *,
    user_id: UserID,
    workspace_id: WorkspaceID,
    product_name: ProductName,
    permission: PermissionStr,
) -> UserWorkspaceWithAccessRights:
    """
    As `get_user_workspace` but here access check is required

    Raises:
        WorkspaceAccessForbiddenError
    """
    return await get_user_workspace(
        app,
        user_id=user_id,
        workspace_id=workspace_id,
        product_name=product_name,
        # NOTE: check here is required
        permission=permission,
    )
