import logging
from datetime import datetime

from aiohttp import web
from models_library.products import ProductName
from models_library.users import GroupID, UserID
from models_library.wallets import UserWalletDB, WalletID
from pydantic import BaseModel, ConfigDict

from ..users import api as users_api
from . import _db as wallets_db
from . import _groups_db as wallets_groups_db
from ._groups_db import WalletGroupGetDB
from .errors import WalletAccessForbiddenError

log = logging.getLogger(__name__)


class WalletGroupGet(BaseModel):
    gid: GroupID
    read: bool
    write: bool
    delete: bool
    created: datetime
    modified: datetime
    
    model_config = ConfigDict(
        from_attributes=True
    )


async def create_wallet_group(
    app: web.Application,
    *,
    user_id: UserID,
    wallet_id: WalletID,
    group_id: GroupID,
    read: bool,
    write: bool,
    delete: bool,
    product_name: ProductName,
) -> WalletGroupGet:
    wallet: UserWalletDB = await wallets_db.get_wallet_for_user(
        app=app, user_id=user_id, wallet_id=wallet_id, product_name=product_name
    )
    if wallet.write is False:
        raise WalletAccessForbiddenError(
            reason=f"User does not have write access to wallet {wallet_id}",
            user_id=user_id,
            wallet_id=wallet_id,
            product_name=product_name,
            user_acces_rights_on_wallet=wallet.model_dump(
                include={"read", "write", "delete"}
            ),
        )

    wallet_group_db: WalletGroupGetDB = await wallets_groups_db.create_wallet_group(
        app=app,
        wallet_id=wallet_id,
        group_id=group_id,
        read=read,
        write=write,
        delete=delete,
    )
    wallet_group_api: WalletGroupGet = WalletGroupGet(**wallet_group_db.model_dump())

    return wallet_group_api


async def list_wallet_groups_by_user_and_wallet(
    app: web.Application,
    *,
    user_id: UserID,
    wallet_id: WalletID,
    product_name: ProductName,
) -> list[WalletGroupGet]:
    wallet: UserWalletDB = await wallets_db.get_wallet_for_user(
        app=app, user_id=user_id, wallet_id=wallet_id, product_name=product_name
    )
    if wallet.read is False:
        raise WalletAccessForbiddenError(
            reason=f"User does not have read access to wallet {wallet_id}",
            user_id=user_id,
            wallet_id=wallet_id,
            product_name=product_name,
            user_acces_rights_on_wallet=wallet.model_dump(
                include={"read", "write", "delete"}
            ),
        )

    wallet_groups_db: list[
        WalletGroupGetDB
    ] = await wallets_groups_db.list_wallet_groups(app=app, wallet_id=wallet_id)

    wallet_groups_api: list[WalletGroupGet] = [
        WalletGroupGet.model_validate(group) for group in wallet_groups_db
    ]

    return wallet_groups_api


async def list_wallet_groups_with_read_access_by_wallet(
    app: web.Application,
    *,
    wallet_id: WalletID,
) -> list[WalletGroupGet]:
    wallet_groups_db: list[
        WalletGroupGetDB
    ] = await wallets_groups_db.list_wallet_groups(app=app, wallet_id=wallet_id)

    wallet_groups_api: list[WalletGroupGet] = [
        WalletGroupGet.model_validate(group)
        for group in wallet_groups_db
        if group.read is True
    ]

    return wallet_groups_api


async def update_wallet_group(
    app: web.Application,
    *,
    user_id: UserID,
    wallet_id: WalletID,
    group_id: GroupID,
    read: bool,
    write: bool,
    delete: bool,
    product_name: ProductName,
) -> WalletGroupGet:
    wallet: UserWalletDB = await wallets_db.get_wallet_for_user(
        app=app, user_id=user_id, wallet_id=wallet_id, product_name=product_name
    )
    if wallet.write is False:
        raise WalletAccessForbiddenError(
            reason=f"User does not have write access to wallet {wallet_id}"
        )
    if wallet.owner == group_id:
        user: dict = await users_api.get_user(app, user_id)
        if user["primary_gid"] != wallet.owner:
            # Only the owner of the wallet can modify the owner group
            raise WalletAccessForbiddenError(
                reason=f"User does not have access to modify owner wallet group in wallet {wallet_id}",
                user_id=user_id,
                wallet_id=wallet_id,
                product_name=product_name,
                user_acces_rights_on_wallet=wallet.model_dump(
                    include={"read", "write", "delete"}
                ),
            )

    wallet_group_db: WalletGroupGetDB = await wallets_groups_db.update_wallet_group(
        app=app,
        wallet_id=wallet_id,
        group_id=group_id,
        read=read,
        write=write,
        delete=delete,
    )

    wallet_api: WalletGroupGet = WalletGroupGet(**wallet_group_db.model_dump())
    return wallet_api


async def delete_wallet_group(
    app: web.Application,
    *,
    user_id: UserID,
    wallet_id: WalletID,
    group_id: GroupID,
    product_name: ProductName,
) -> None:
    wallet: UserWalletDB = await wallets_db.get_wallet_for_user(
        app=app, user_id=user_id, wallet_id=wallet_id, product_name=product_name
    )
    if wallet.delete is False:
        raise WalletAccessForbiddenError(
            reason=f"User does not have delete access to wallet {wallet_id}"
        )
    if wallet.owner == group_id:
        user: dict = await users_api.get_user(app, user_id)
        if user["primary_gid"] != wallet.owner:
            # Only the owner of the wallet can delete the owner group
            raise WalletAccessForbiddenError(
                reason=f"User does not have access to modify owner wallet group in wallet {wallet_id}"
            )

    await wallets_groups_db.delete_wallet_group(
        app=app, wallet_id=wallet_id, group_id=group_id
    )
