# pylint: disable=unused-argument

import logging
from datetime import datetime

from aiohttp import web
from aiopg.sa.engine import Engine
from models_library.folders import FolderID
from models_library.products import ProductName
from models_library.users import GroupID, UserID
from pydantic import BaseModel
from simcore_postgres_database import utils_folders as folders_db

from .._constants import APP_DB_ENGINE_KEY
from ..groups.api import list_all_user_groups

log = logging.getLogger(__name__)


class FolderGroupGet(BaseModel):
    gid: GroupID
    read: bool
    write: bool
    delete: bool
    created: datetime
    modified: datetime


async def create_folder_group_by_user(
    app: web.Application,
    *,
    user_id: UserID,
    folder_id: FolderID,
    group_id: GroupID,
    read: bool,
    write: bool,
    delete: bool,
    product_name: ProductName,
) -> None:
    user_groups = await list_all_user_groups(app, user_id=user_id)
    user_gids = {group.gid for group in user_groups}

    engine: Engine = app[APP_DB_ENGINE_KEY]
    async with engine.acquire() as connection:
        # folder_db: folders_db.FolderEntry = await folders_db.folder_get(
        #     connection,
        #     product_name=product_name,
        #     folder_id=folder_id,
        #     gids=user_gids,
        # )
        # user_folder_access_rights = folder_db.my_access_rights

        recipient_role = folders_db.get_role_from_permissions(
            read=read, write=write, delete=delete
        )
        await folders_db.folder_share_or_update_permissions(
            connection,
            product_name=product_name,
            folder_id=folder_id,
            sharing_gids=user_gids,
            recipient_gid=group_id,
            recipient_role=recipient_role,
        )


async def list_folder_groups_by_user(
    app: web.Application,
    *,
    user_id: UserID,
    folder_id: FolderID,
    product_name: ProductName,
) -> list[FolderGroupGet]:
    raise NotImplementedError


async def get_folder_group_by_user(
    app: web.Application,
    *,
    user_id: UserID,
    folder_id: FolderID,
    product_name: ProductName,
) -> FolderGroupGet:
    raise NotImplementedError


async def update_folder_group_by_user(
    app: web.Application,
    *,
    user_id: UserID,
    folder_id: FolderID,
    group_id: GroupID,
    read: bool,
    write: bool,
    delete: bool,
    product_name: ProductName,
) -> None:
    user_groups = await list_all_user_groups(app, user_id=user_id)
    user_gids = {group.gid for group in user_groups}

    engine: Engine = app[APP_DB_ENGINE_KEY]
    async with engine.acquire() as connection:
        recipient_role = folders_db.get_role_from_permissions(
            read=read, write=write, delete=delete
        )
        await folders_db.folder_share_or_update_permissions(
            connection,
            product_name=product_name,
            folder_id=folder_id,
            sharing_gids=user_gids,
            recipient_gid=group_id,
            recipient_role=recipient_role,
        )


async def delete_folder_group_by_user(
    app: web.Application,
    *,
    user_id: UserID,
    folder_id: FolderID,
    group_id: GroupID,
    product_name: ProductName,
) -> None:
    user_groups = await list_all_user_groups(app, user_id=user_id)
    user_gids = {group.gid for group in user_groups}

    engine: Engine = app[APP_DB_ENGINE_KEY]
    async with engine.acquire() as connection:
        # folder_db: folders_db.FolderEntry = await folders_db.folder_get(
        #     connection,
        #     product_name=product_name,
        #     folder_id=folder_id,
        #     gids=user_gids,
        # )
        # user_folder_access_rights = folder_db.my_access_rights

        await folders_db.folder_share_or_update_permissions(
            connection,
            product_name=product_name,
            folder_id=folder_id,
            sharing_gids=user_gids,
            recipient_gid=group_id,
            recipient_role=folders_db.FolderAccessRole.NO_ACCESS,
        )
