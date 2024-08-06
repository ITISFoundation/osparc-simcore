# pylint: disable=unused-argument

import logging

from aiohttp import web
from aiopg.sa.engine import Engine
from models_library.api_schemas_webserver.folders import FolderGet
from models_library.folders import FolderID
from models_library.products import ProductName
from models_library.rest_ordering import OrderBy
from models_library.users import GroupID, UserID
from pydantic import NonNegativeInt
from simcore_postgres_database import utils_folders as folders_db

from .._constants import APP_DB_ENGINE_KEY
from ..groups.api import get_user_group

_logger = logging.getLogger(__name__)


async def create_folder_via_access_gid(
    app: web.Application,
    user_id: UserID,
    access_via_gid: GroupID,
    folder_name: str,
    description: str | None,
    parent_folder_id: FolderID | None,
    product_name: ProductName,
) -> FolderID:

    # Check whether user has access to the group
    await get_user_group(app, user_id=user_id, gid=access_via_gid)

    engine: Engine = app[APP_DB_ENGINE_KEY]
    async with engine.acquire() as connection:
        # NOTE: folder permissions are checked inside the function
        folder_id = await folders_db.folder_create(
            connection,
            product_name=product_name,
            name=folder_name,
            gid=access_via_gid,
            description=description if description else "",
            parent=parent_folder_id,
        )
    return FolderID(folder_id)


async def get_folder_via_access_gid(
    app: web.Application,
    user_id: UserID,
    access_via_gid: GroupID,
    folder_id: FolderID,
    product_name: ProductName,
) -> FolderGet:
    raise NotImplementedError


async def list_folders_via_access_gid(
    app: web.Application,
    user_id: UserID,
    product_name: ProductName,
    access_via_gid: GroupID,
    folder_id: FolderID | None,
    offset: NonNegativeInt,
    limit: int,
    order_by: OrderBy,
) -> list[FolderGet]:

    # Check whether user has access to the group
    await get_user_group(app, user_id=user_id, gid=access_via_gid)

    engine: Engine = app[APP_DB_ENGINE_KEY]
    async with engine.acquire() as connection:
        # NOTE: folder permissions are checked inside the function
        folder_list_db: list[folders_db.FolderEntry] = await folders_db.folder_list(
            connection,
            product_name=product_name,
            folder_id=folder_id,
            gid=access_via_gid,
            offset=offset,
            limit=limit,
        )
    return [
        FolderGet.construct(
            folder_id=folder.id,
            name=folder.name,
            description=folder.description,
            modified_at=folder.modified,
        )
        for folder in folder_list_db
    ]


async def update_folder_via_access_gid(
    app: web.Application,
    user_id: UserID,
    access_via_gid: GroupID,
    folder_id: FolderID,
    name: str,
    description: str | None,
    product_name: ProductName,
) -> None:

    # Check whether user has access to the group
    await get_user_group(app, user_id=user_id, gid=access_via_gid)

    engine: Engine = app[APP_DB_ENGINE_KEY]
    async with engine.acquire() as connection:
        # NOTE: folder permissions are checked inside the function
        await folders_db.folder_update(
            connection,
            product_name=product_name,
            folder_id=folder_id,
            gid=access_via_gid,
            name=name,
            description=description,
        )


async def delete_folder_via_access_gid(
    app: web.Application,
    user_id: UserID,
    access_via_gid: GroupID,
    folder_id: FolderID,
    product_name: ProductName,
) -> None:

    # Check whether user has access to the group
    await get_user_group(app, user_id=user_id, gid=access_via_gid)

    engine: Engine = app[APP_DB_ENGINE_KEY]
    async with engine.acquire() as connection:
        # NOTE: folder permissions are checked inside the function
        await folders_db.folder_delete(
            connection,
            product_name=product_name,
            folder_id=folder_id,
            gid=access_via_gid,
        )
