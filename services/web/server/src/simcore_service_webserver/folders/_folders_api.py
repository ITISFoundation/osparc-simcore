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
from ..users.api import get_user

_logger = logging.getLogger(__name__)


async def create_folder_via_access_gid(
    app: web.Application,
    user_id: UserID,
    access_via_gid: GroupID,
    folder_name: str,
    description: str | None,
    parent_folder_id: FolderID | None,
    product_name: ProductName,
) -> FolderGet:

    # TODO: Check user has permissions to the group

    engine: Engine = app[APP_DB_ENGINE_KEY]
    async with engine.acquire() as connection:
        # NOTE: folder permissions are checked inside the function
        await folders_db.folder_create(
            connection,
            product_name=product_name,
            name=folder_name,
            gid=access_via_gid,
            description=description if description else "",
            parent=parent_folder_id,
        )


async def get_folder_via_access_gid(
    app: web.Application,
    user_id: UserID,
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

    # TODO: Check user has permissions to the group

    engine: Engine = app[APP_DB_ENGINE_KEY]
    async with engine.acquire() as connection:
        await folders_db.folder_list(connection, product_name=product_name, folder_id=folder_id, gid)


async def update_folder_via_access_gid(
    app: web.Application,
    user_id: UserID,
    folder_id: FolderID,
    name: str,
    description: str | None,
    product_name: ProductName,
) -> FolderGet:
    # TODO: Check user has permissions to the group

    engine: Engine = app[APP_DB_ENGINE_KEY]
    async with engine.acquire() as connection:
        await folders_db.folder_list(connection, product_name=product_name, folder_id=folder_id, gid)


async def delete_folder_via_access_gid(
    app: web.Application,
    user_id: UserID,
    folder_id: FolderID,
    product_name: ProductName,
) -> None:

    # TODO: Check user has permissions to the group

    engine: Engine = app[APP_DB_ENGINE_KEY]
    async with engine.acquire() as connection:
        await folders_db.folder_list(connection, product_name=product_name, folder_id=folder_id, gid)
