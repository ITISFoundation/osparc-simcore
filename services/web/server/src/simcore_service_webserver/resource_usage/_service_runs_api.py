from aiohttp import web
from models_library.api_schemas_resource_usage_tracker.service_runs import (
    ServiceRunPage,
)
from models_library.api_schemas_webserver.wallets import WalletGetPermissions
from models_library.products import ProductName
from models_library.resource_tracker import ServiceResourceUsagesFilters
from models_library.rest_ordering import OrderBy
from models_library.users import UserID
from models_library.wallets import WalletID
from pydantic import NonNegativeInt
from servicelib.rabbitmq.rpc_interfaces.resource_usage_tracker import service_runs

from ..rabbitmq import get_rabbitmq_rpc_client
from ..wallets import api as wallet_api


async def list_usage_services(
    app: web.Application,
    user_id: UserID,
    product_name: ProductName,
    wallet_id: WalletID | None,
    offset: int,
    limit: NonNegativeInt,
    order_by: list[OrderBy] | None,
    filters: ServiceResourceUsagesFilters | None,
) -> ServiceRunPage:
    access_all_wallet_usage = False
    if wallet_id:
        wallet: WalletGetPermissions = (
            await wallet_api.get_wallet_with_permissions_by_user(
                app=app, user_id=user_id, wallet_id=wallet_id, product_name=product_name
            )
        )
        access_all_wallet_usage = wallet.write is True

    rpc_client = get_rabbitmq_rpc_client(app)
    return await service_runs.get_service_run_page(
        rpc_client,
        user_id=user_id,
        product_name=product_name,
        wallet_id=wallet_id,
        access_all_wallet_usage=access_all_wallet_usage,
        offset=offset,
        limit=limit,
        order_by=order_by,
        filters=filters,
    )
