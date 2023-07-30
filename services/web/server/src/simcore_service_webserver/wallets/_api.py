import logging

from aiohttp import web
from models_library.users import UserID
from models_library.wallets import (
    UserWalletGetDB,
    WalletGet,
    WalletGetDB,
    WalletGetWithAvailableCredits,
    WalletID,
    WalletStatus,
)

from ..users import api as users_api
from . import _db as db

log = logging.getLogger(__name__)


async def create_wallet(
    app: web.Application,
    user_id: UserID,
    wallet_name: str,
    description: str | None,
    thumbnail: str | None,
) -> WalletGet:
    user: dict = await users_api.get_user(app, user_id)
    wallet_db: WalletGetDB = await db.create_wallet(
        app=app,
        owner=user["primary_gid"],
        wallet_name=wallet_name,
        description=description,
        thumbnail=thumbnail,
    )
    wallet_api: WalletGet = WalletGet(**wallet_db.dict())
    return wallet_api


async def list_wallets_with_available_credits_for_user(
    app: web.Application,
    user_id: UserID,
) -> list[WalletGetWithAvailableCredits]:
    user_wallets: list[UserWalletGetDB] = await db.list_wallets_for_user(
        app=app, user_id=user_id
    )

    # TODO: Now we need to get current available credits from resource-usage-tracker for each wallet
    available_credits: float = 0.0

    # Now we return the user wallets with available credits
    wallets_api: list[WalletGetWithAvailableCredits] = []
    for wallet in user_wallets:
        wallets_api.append(
            WalletGetWithAvailableCredits(
                wallet_id=wallet.wallet_id,
                name=wallet.name,
                description=wallet.description,
                owner=wallet.owner,
                thumbnail=wallet.thumbnail,
                status=wallet.status,
                created=wallet.created,
                modified=wallet.modified,
                available_credits=available_credits,
            )
        )

    return wallets_api


async def update_wallet(
    app: web.Application,
    user_id: UserID,
    wallet_id: WalletID,
    name: str,
    description: str,
    thumbnail: str,
    status: WalletStatus,
) -> WalletGet:
    wallet: UserWalletGetDB = await db.get_wallet_for_user(
        app=app, user_id=user_id, wallet_id=wallet_id
    )
    if wallet.write is False:
        raise web.HTTPForbidden(
            reason="User does not have permission to modify wallet",
        )

    wallet_db: WalletGetDB = await db.update_wallet(
        app=app,
        wallet_id=wallet_id,
        name=name,
        description=description,
        thumbnail=thumbnail,
        status=status,
    )

    wallet_api: WalletGet = WalletGet(**wallet_db.model_dump())
    return wallet_api


async def delete_wallet(
    app: web.Application,
    user_id: UserID,
    wallet_id: WalletID,
) -> None:
    wallet: UserWalletGetDB = await db.get_wallet_for_user(
        app=app, user_id=user_id, wallet_id=wallet_id
    )
    if wallet.delete is False:
        raise web.HTTPForbidden(
            reason="User does not have permission to delete wallet",
        )

    raise NotImplementedError


### API that can be exposed


async def can_wallet_be_used_by_user(
    app: web.Application,
    user_id: UserID,
    wallet_id: WalletID,
) -> WalletGet:
    wallet: UserWalletGetDB = await db.get_wallet_for_user(
        app=app, user_id=user_id, wallet_id=wallet_id
    )
    if wallet.read is False:
        raise web.HTTPForbidden(
            reason="User does not have permission to use the wallet",
        )

    wallet_api: WalletGet = WalletGet(
        id=wallet.wallet_id,
        name=wallet.name,
        description=wallet.description,
        owner=wallet.owner,
        thumbnail=wallet.thumbnail,
        status=wallet.status,
        created=wallet.created,
        modified=wallet.modified,
    )
    return wallet_api
