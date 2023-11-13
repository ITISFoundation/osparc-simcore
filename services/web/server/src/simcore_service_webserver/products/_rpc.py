from aiohttp import web
from models_library.api_schemas_webserver import WEBSERVER_RPC_NAMESPACE
from models_library.basic_types import NonNegativeDecimal
from models_library.products import ProductName
from servicelib.rabbitmq import RPCRouter

from ..rabbitmq import get_rabbitmq_rpc_server
from . import _api

router = RPCRouter()


@router.expose()
async def get_product_credit_price_by_app_and_product(
    app: web.Application,
    *,
    product_name: ProductName,
) -> NonNegativeDecimal | None:
    return await _api.get_product_credit_price_by_app_and_product(
        app, product_name=product_name
    )


async def register_rpc_routes_on_startup(app: web.Application):
    rpc_server = get_rabbitmq_rpc_server(app)
    await rpc_server.register_router(router, WEBSERVER_RPC_NAMESPACE, app)
