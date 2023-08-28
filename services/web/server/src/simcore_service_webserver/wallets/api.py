import logging

from aiohttp import web
from models_library.api_schemas_webserver.wallets import WalletGet, WalletGetPermissions
from models_library.users import UserID
from models_library.wallets import UserWalletDB, WalletID

from . import _db as db
from .errors import WalletAccessForbiddenError

log = logging.getLogger(__name__)


async def get_wallet_by_user(
    app: web.Application,
    user_id: UserID,
    wallet_id: WalletID,
) -> WalletGet:
    wallet: UserWalletDB = await db.get_wallet_for_user(
        app=app, user_id=user_id, wallet_id=wallet_id
    )
    if wallet.read is False:
        raise WalletAccessForbiddenError(
            reason=f"User {user_id} does not have read permission on wallet {wallet_id}"
        )

    wallet_api: WalletGet = WalletGet(
        wallet_id=wallet.wallet_id,
        name=wallet.name,
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
) -> WalletGetPermissions:
    wallet: UserWalletDB = await db.get_wallet_for_user(
        app=app, user_id=user_id, wallet_id=wallet_id
    )

    output = WalletGetPermissions.construct(**wallet.dict())
    return output
