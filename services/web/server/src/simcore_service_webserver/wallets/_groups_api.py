import logging
from datetime import datetime

from aiohttp import web
from models_library.users import GroupID, UserID
from models_library.wallets import UserWalletGetDB, WalletID
from pydantic import BaseModel, parse_obj_as

from ..users import api as users_api
from . import _db as wallets_db
from . import _groups_db as wallets_groups_db
from ._groups_db import WalletGroupGetDB
from .exceptions import WalletAccessForbiddenError

log = logging.getLogger(__name__)


class WalletGroupGet(BaseModel):
    gid: GroupID
    read: bool
    write: bool
    delete: bool
    created: datetime
    modified: datetime


async def create_wallet_group(
    app: web.Application,
    user_id: UserID,
    wallet_id: WalletID,
    group_id: GroupID,
    read: bool,
    write: bool,
    delete: bool,
) -> WalletGroupGet:
    wallet: UserWalletGetDB = await wallets_db.get_wallet_for_user(
        app=app, user_id=user_id, wallet_id=wallet_id
    )
    if wallet.write is False:
        raise WalletAccessForbiddenError(wallet_id=wallet_id)

    wallet_group_db: WalletGroupGetDB = await wallets_groups_db.create_wallet_group(
        app=app,
        wallet_id=wallet_id,
        group_id=group_id,
        read=read,
        write=write,
        delete=delete,
    )
    wallet_group_api: WalletGroupGet = WalletGroupGet(**wallet_group_db.dict())

    return wallet_group_api


async def list_wallet_groups(
    app: web.Application,
    user_id: UserID,
    wallet_id: WalletID,
) -> list[WalletGroupGet]:
    wallet: UserWalletGetDB = await wallets_db.get_wallet_for_user(
        app=app, user_id=user_id, wallet_id=wallet_id
    )
    if wallet.read is False:
        raise WalletAccessForbiddenError(wallet_id=wallet_id)

    wallet_groups_db: list[
        WalletGroupGetDB
    ] = await wallets_groups_db.list_wallet_groups(app=app, wallet_id=wallet_id)

    wallet_groups_api: list[WalletGroupGet] = [
        parse_obj_as(WalletGroupGet, group) for group in wallet_groups_db
    ]

    return wallet_groups_api


async def update_wallet_group(
    app: web.Application,
    user_id: UserID,
    wallet_id: WalletID,
    group_id: GroupID,
    read: bool,
    write: bool,
    delete: bool,
) -> WalletGroupGet:
    wallet: UserWalletGetDB = await wallets_db.get_wallet_for_user(
        app=app, user_id=user_id, wallet_id=wallet_id
    )
    if wallet.write is False:
        raise WalletAccessForbiddenError(wallet_id=wallet_id)
    if wallet.owner == group_id:
        user: dict = await users_api.get_user(app, user_id)
        if user["primary_gid"] != wallet.owner:
            # Only the owner of the wallet can modify the owner group
            raise WalletAccessForbiddenError(wallet_id=wallet_id)

    wallet_group_db: WalletGroupGetDB = await wallets_groups_db.update_wallet_group(
        app=app,
        wallet_id=wallet_id,
        group_id=group_id,
        read=read,
        write=write,
        delete=delete,
    )

    wallet_api: WalletGroupGet = WalletGroupGet(**wallet_group_db.dict())
    return wallet_api


async def delete_wallet_group(
    app: web.Application,
    user_id: UserID,
    wallet_id: WalletID,
    group_id: GroupID,
) -> None:
    wallet: UserWalletGetDB = await wallets_db.get_wallet_for_user(
        app=app, user_id=user_id, wallet_id=wallet_id
    )
    if wallet.delete is False:
        raise WalletAccessForbiddenError(wallet_id=wallet_id)
    if wallet.owner == group_id:
        user: dict = await users_api.get_user(app, user_id)
        if user["primary_gid"] != wallet.owner:
            # Only the owner of the wallet can delete the owner group
            raise WalletAccessForbiddenError(wallet_id=wallet_id)

    await wallets_groups_db.delete_wallet_group(
        app=app, wallet_id=wallet_id, group_id=group_id
    )
