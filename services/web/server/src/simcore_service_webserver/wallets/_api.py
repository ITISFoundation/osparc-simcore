import logging

from aiohttp import web
from models_library.api_schemas_resource_usage_tracker.credit_transactions import (
    WalletTotalCredits,
)
from models_library.api_schemas_webserver.wallets import (
    WalletGet,
    WalletGetPermissions,
    WalletGetWithAvailableCredits,
)
from models_library.basic_types import IDStr
from models_library.products import ProductName
from models_library.users import UserID
from models_library.wallets import UserWalletDB, WalletDB, WalletID, WalletStatus
from pydantic import parse_obj_as

from ..resource_usage.api import get_wallet_total_available_credits
from ..users import api as users_api
from ..users import preferences_api as user_preferences_api
from ..users.exceptions import UserDefaultWalletNotFoundError
from . import _db as db
from .errors import WalletAccessForbiddenError

_logger = logging.getLogger(__name__)


async def create_wallet(
    app: web.Application,
    user_id: UserID,
    wallet_name: str,
    description: str | None,
    thumbnail: str | None,
    product_name: ProductName,
) -> WalletGet:
    user: dict = await users_api.get_user(app, user_id)
    wallet_db: WalletDB = await db.create_wallet(
        app=app,
        owner=user["primary_gid"],
        wallet_name=wallet_name,
        description=description,
        thumbnail=thumbnail,
        product_name=product_name,
    )
    wallet_api: WalletGet = parse_obj_as(WalletGet, wallet_db)
    return wallet_api


async def list_wallets_with_available_credits_for_user(
    app: web.Application,
    user_id: UserID,
    product_name: ProductName,
) -> list[WalletGetWithAvailableCredits]:
    user_wallets: list[UserWalletDB] = await db.list_wallets_for_user(
        app=app, user_id=user_id, product_name=product_name
    )

    # Now we return the user wallets with available credits
    wallets_api = []
    for wallet in user_wallets:
        available_credits: WalletTotalCredits = (
            await get_wallet_total_available_credits(
                app, product_name, wallet.wallet_id
            )
        )
        wallets_api.append(
            WalletGetWithAvailableCredits(
                wallet_id=wallet.wallet_id,
                name=IDStr(wallet.name),
                description=wallet.description,
                owner=wallet.owner,
                thumbnail=wallet.thumbnail,
                status=wallet.status,
                created=wallet.created,
                modified=wallet.modified,
                available_credits=available_credits.available_osparc_credits,
            )
        )

    return wallets_api


async def get_wallet_with_available_credits_by_user_and_wallet(
    app: web.Application,
    *,
    user_id: UserID,
    wallet_id: WalletID,
    product_name: ProductName,
) -> WalletGetWithAvailableCredits:
    user_wallet_db: UserWalletDB = await db.get_wallet_for_user(
        app=app, user_id=user_id, wallet_id=wallet_id, product_name=product_name
    )

    available_credits: WalletTotalCredits = await get_wallet_total_available_credits(
        app, product_name, user_wallet_db.wallet_id
    )

    return WalletGetWithAvailableCredits(
        wallet_id=user_wallet_db.wallet_id,
        name=IDStr(user_wallet_db.name),
        description=user_wallet_db.description,
        owner=user_wallet_db.owner,
        thumbnail=user_wallet_db.thumbnail,
        status=user_wallet_db.status,
        created=user_wallet_db.created,
        modified=user_wallet_db.modified,
        available_credits=available_credits.available_osparc_credits,
    )


async def get_user_default_wallet_with_available_credits(
    app: web.Application,
    *,
    user_id: UserID,
    product_name: ProductName,
) -> WalletGetWithAvailableCredits:
    user_default_wallet_preference = await user_preferences_api.get_frontend_user_preference(
        app,
        user_id=user_id,
        product_name=product_name,
        preference_class=user_preferences_api.PreferredWalletIdFrontendUserPreference,
    )
    if user_default_wallet_preference is None:
        raise UserDefaultWalletNotFoundError(uid=user_id)
    default_wallet_id = parse_obj_as(WalletID, user_default_wallet_preference.value)
    return await get_wallet_with_available_credits_by_user_and_wallet(
        app, user_id=user_id, wallet_id=default_wallet_id, product_name=product_name
    )


async def list_wallets_for_user(
    app: web.Application,
    user_id: UserID,
    product_name: ProductName,
) -> list[WalletGet]:
    user_wallets: list[UserWalletDB] = await db.list_wallets_for_user(
        app=app, user_id=user_id, product_name=product_name
    )
    return parse_obj_as(list[WalletGet], user_wallets)


async def any_wallet_owned_by_user(
    app: web.Application,
    user_id: UserID,
    product_name: ProductName,
) -> bool:
    wallet_ids = await db.list_wallets_owned_by_user(
        app, user_id=user_id, product_name=product_name
    )

    if len(wallet_ids) > 1:
        _logger.warning(
            "User %s owns more than one wallet for %s. Check %s",
            f"{user_id=}",
            f"{product_name=}",
            f"{wallet_ids=}",
        )

    return len(wallet_ids) != 0


async def update_wallet(
    app: web.Application,
    user_id: UserID,
    wallet_id: WalletID,
    name: str,
    description: str | None,
    thumbnail: str | None,
    status: WalletStatus,
    product_name: ProductName,
) -> WalletGet:
    wallet: UserWalletDB = await db.get_wallet_for_user(
        app=app, user_id=user_id, wallet_id=wallet_id, product_name=product_name
    )
    if wallet.write is False:
        raise WalletAccessForbiddenError(
            reason=f"Wallet {wallet_id} does not have write permission"
        )

    wallet_db: WalletDB = await db.update_wallet(
        app=app,
        wallet_id=wallet_id,
        name=name,
        description=description,
        thumbnail=thumbnail,
        status=status,
        product_name=product_name,
    )

    wallet_api: WalletGet = parse_obj_as(WalletGet, wallet_db)
    return wallet_api


async def delete_wallet(
    app: web.Application,
    user_id: UserID,
    wallet_id: WalletID,
    product_name: ProductName,
) -> None:
    wallet: UserWalletDB = await db.get_wallet_for_user(
        app=app, user_id=user_id, wallet_id=wallet_id, product_name=product_name
    )
    if wallet.delete is False:
        raise WalletAccessForbiddenError(
            reason=f"Wallet {wallet_id} does not have delete permission"
        )

    raise NotImplementedError


async def get_wallet_by_user(
    app: web.Application,
    user_id: UserID,
    wallet_id: WalletID,
    product_name: ProductName,
) -> WalletGet:
    wallet: UserWalletDB = await db.get_wallet_for_user(
        app=app, user_id=user_id, wallet_id=wallet_id, product_name=product_name
    )
    if wallet.read is False:
        raise WalletAccessForbiddenError(
            reason=f"User {user_id} does not have read permission on wallet {wallet_id}"
        )

    wallet_api: WalletGet = WalletGet(
        wallet_id=wallet.wallet_id,
        name=IDStr(wallet.name),
        description=wallet.description,
        owner=wallet.owner,
        thumbnail=wallet.thumbnail,
        status=wallet.status,
        created=wallet.created,
        modified=wallet.modified,
    )
    return wallet_api


async def get_wallet_with_permissions_by_user(
    app: web.Application,
    user_id: UserID,
    wallet_id: WalletID,
    product_name: ProductName,
) -> WalletGetPermissions:
    wallet: UserWalletDB = await db.get_wallet_for_user(
        app=app, user_id=user_id, wallet_id=wallet_id, product_name=product_name
    )

    permissions: WalletGetPermissions = parse_obj_as(WalletGetPermissions, wallet)
    return permissions
