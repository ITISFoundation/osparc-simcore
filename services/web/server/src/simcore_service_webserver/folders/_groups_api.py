# pylint: disable=unused-argument

import logging
from datetime import datetime

from aiohttp import web
from models_library.folders import FolderID
from models_library.products import ProductName
from models_library.users import GroupID, UserID
from pydantic import BaseModel

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
) -> FolderGroupGet:
    raise NotImplementedError


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
) -> FolderGroupGet:
    raise NotImplementedError


async def delete_folder_group_by_user(
    app: web.Application,
    *,
    user_id: UserID,
    folder_id: FolderID,
    group_id: GroupID,
    product_name: ProductName,
) -> None:
    raise NotImplementedError
