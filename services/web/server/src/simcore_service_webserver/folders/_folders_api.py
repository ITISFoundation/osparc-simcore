# pylint: disable=unused-argument

import logging

from aiohttp import web
from models_library.api_schemas_webserver.folders import FolderGet
from models_library.folders import FolderID
from models_library.products import ProductName
from models_library.rest_ordering import OrderBy
from models_library.users import UserID
from pydantic import NonNegativeInt

_logger = logging.getLogger(__name__)


async def create_folder_by_user(
    app: web.Application,
    user_id: UserID,
    folder_name: str,
    description: str | None,
    product_name: ProductName,
) -> FolderGet:
    raise NotImplementedError


async def get_folder_by_user(
    app: web.Application,
    user_id: UserID,
    folder_id: FolderID,
    product_name: ProductName,
) -> FolderGet:
    raise NotImplementedError


async def list_folders_by_user(
    app: web.Application,
    user_id: UserID,
    product_name: ProductName,
    offset: NonNegativeInt,
    limit: int,
    order_by: OrderBy,
) -> list[FolderGet]:
    raise NotImplementedError


async def update_folder_by_user(
    app: web.Application,
    user_id: UserID,
    folder_id: FolderID,
    name: str,
    description: str | None,
    product_name: ProductName,
) -> FolderGet:
    raise NotImplementedError


async def delete_folder_by_user(
    app: web.Application,
    user_id: UserID,
    folder_id: FolderID,
    product_name: ProductName,
) -> None:
    raise NotImplementedError
