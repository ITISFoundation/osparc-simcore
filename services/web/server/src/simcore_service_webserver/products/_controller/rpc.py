from decimal import Decimal

from aiohttp import web
from models_library.api_schemas_webserver.products import CreditResultRpcGet
from models_library.products import ProductName
from servicelib.rabbitmq import RPCRouter

from ...application_keys import APP_SETTINGS_APPKEY
from ...rabbitmq import register_webserver_rpc_router, setup_rabbitmq
from .. import _service
from .._models import CreditResult

router = RPCRouter()


@router.expose()
async def get_credit_amount(
    app: web.Application,
    *,
    dollar_amount: Decimal,
    product_name: ProductName,
) -> CreditResultRpcGet:
    credit_result: CreditResult = await _service.get_credit_amount(
        app, dollar_amount=dollar_amount, product_name=product_name
    )
    return CreditResultRpcGet.model_validate(credit_result, from_attributes=True)


async def _register_rpc_routes_on_startup(app: web.Application):
    await register_webserver_rpc_router(app, router)


def setup_rpc(app: web.Application):
    setup_rabbitmq(app)
    if app[APP_SETTINGS_APPKEY].WEBSERVER_RABBITMQ:
        app.on_startup.append(_register_rpc_routes_on_startup)
