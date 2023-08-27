from aiohttp import web
from models_library.api_schemas_webserver.wallets import WalletWithUserPermissions
from models_library.products import ProductName
from models_library.users import UserID
from models_library.wallets import WalletID
from pydantic import NonNegativeInt

from ..wallets import api as wallet_api
from . import resource_usage_tracker_client as resource_tracker_client


async def list_usage_services(
    app: web.Application,
    user_id: UserID,
    product_name: ProductName,
    wallet_id: WalletID | None,
    offset: int,
    limit: NonNegativeInt,
):
    if not wallet_id:
        data: dict = (
            await resource_tracker_client.list_service_runs_by_user_and_product(
                app=app,
                user_id=user_id,
                product_name=product_name,
                offset=offset,
                limit=limit,
            )
        )
    else:
        wallet: WalletWithUserPermissions = (
            await wallet_api.get_wallet_with_permissions_by_user(
                app=app, user_id=user_id, wallet_id=wallet_id
            )
        )
        access_all_wallet_usage = wallet.write is True

        data: dict = await resource_tracker_client.list_service_runs_by_user_and_product_and_wallet(
            app=app,
            user_id=user_id,
            product_name=product_name,
            wallet_id=wallet_id,
            access_all_wallet_usage=access_all_wallet_usage,
            offset=offset,
            limit=limit,
        )

    return data
