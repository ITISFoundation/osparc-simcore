from decimal import Decimal

from aiohttp import web
from models_library.api_schemas_webserver import WEBSERVER_RPC_NAMESPACE
from models_library.products import CreditResultGet, ProductName
from servicelib.rabbitmq import RPCRouter

from ..rabbitmq import get_rabbitmq_rpc_server
from . import _api

router = RPCRouter()


@router.expose()
async def get_credit_amount(
    app: web.Application,
    *,
    dollar_amount: Decimal,
    product_name: ProductName,
) -> CreditResultGet:
    credit_result_get: CreditResultGet = await _api.get_credit_amount(
        app, dollar_amount=dollar_amount, product_name=product_name
    )
    return credit_result_get


async def register_rpc_routes_on_startup(app: web.Application):
    rpc_server = get_rabbitmq_rpc_server(app)
    await rpc_server.register_router(router, WEBSERVER_RPC_NAMESPACE, app)
