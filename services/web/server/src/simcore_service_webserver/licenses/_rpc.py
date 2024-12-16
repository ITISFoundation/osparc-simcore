from aiohttp import web
from models_library.api_schemas_webserver import WEBSERVER_RPC_NAMESPACE
from models_library.api_schemas_webserver.licensed_items import LicensedItemGetPage
from models_library.basic_types import IDStr
from models_library.licensed_items import LicensedItemID
from models_library.products import ProductName
from models_library.rest_ordering import OrderBy
from models_library.services_types import ServiceRunID
from models_library.users import UserID
from models_library.wallets import WalletID
from servicelib.rabbitmq import RPCRouter

from ..rabbitmq import get_rabbitmq_rpc_server
from . import _licensed_items_api

router = RPCRouter()


@router.expose()
async def get_licensed_items(
    app: web.Application,
    *,
    product_name: ProductName,
    offset: int,
    limit: int,
) -> LicensedItemGetPage:
    licensed_item_get_page: LicensedItemGetPage = (
        await _licensed_items_api.list_licensed_items(
            app=app,
            product_name=product_name,
            offset=offset,
            limit=limit,
            order_by=OrderBy(field=IDStr("name")),
        )
    )
    return licensed_item_get_page


@router.expose(reraise_if_error_type=(NotImplementedError,))
async def get_licensed_items_for_wallet(
    app: web.Application,
    *,
    user_id: UserID,
    product_name: ProductName,
    wallet_id: WalletID,
) -> None:
    raise NotImplementedError


@router.expose(reraise_if_error_type=(NotImplementedError,))
async def checkout_licensed_item_for_wallet(
    app: web.Application,
    *,
    user_id: UserID,
    product_name: ProductName,
    wallet_id: WalletID,
    licensed_item_id: LicensedItemID,
    num_of_seats: int,
    service_run_id: ServiceRunID,
) -> None:
    raise NotImplementedError


@router.expose(reraise_if_error_type=(NotImplementedError,))
async def release_licensed_item_for_wallet(
    app: web.Application,
    *,
    user_id: str,
    product_name: str,
    wallet_id: WalletID,
    licensed_item_id: LicensedItemID,
    num_of_seats: int,
    service_run_id: ServiceRunID,
) -> None:
    raise NotImplementedError


async def register_rpc_routes_on_startup(app: web.Application):
    rpc_server = get_rabbitmq_rpc_server(app)
    await rpc_server.register_router(router, WEBSERVER_RPC_NAMESPACE, app)
