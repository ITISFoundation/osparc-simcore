import logging

from aiohttp import web
from models_library.products import ProductName
from models_library.users import UserID
from simcore_service_webserver.folders._folders_api import FolderID

_logger = logging.getLogger(__name__)


async def trash_folder(
    app: web.Application,
    *,
    product_name: ProductName,
    user_id: UserID,
    folder_id: FolderID,
    force_stop_first: bool,
):
    raise NotImplementedError


async def untrash_folder(
    app: web.Application,
    *,
    product_name: ProductName,
    user_id: UserID,
    folder_id: FolderID,
):
    raise NotImplementedError
