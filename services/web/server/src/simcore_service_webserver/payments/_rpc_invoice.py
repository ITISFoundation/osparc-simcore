from decimal import Decimal

from aiohttp import web
from models_library.api_schemas_webserver import WEBSERVER_RPC_NAMESPACE
from models_library.emails import LowerCaseEmailStr
from models_library.payments import InvoiceDataGet, UserInvoiceAddress
from models_library.products import CreditResultGet, ProductName, ProductStripeInfoGet
from models_library.users import UserID
from servicelib.rabbitmq import RPCRouter

from ..products.api import get_credit_amount, get_product_stripe_info
from ..rabbitmq import get_rabbitmq_rpc_server
from ..users.api import get_user_display_and_id_names, get_user_invoice_address

router = RPCRouter()


@router.expose()
async def get_invoice_data(
    app: web.Application,
    *,
    user_id: UserID,
    dollar_amount: Decimal,
    product_name: ProductName,
) -> InvoiceDataGet:
    credit_result_get: CreditResultGet = await get_credit_amount(
        app, dollar_amount=dollar_amount, product_name=product_name
    )
    product_stripe_info_get: ProductStripeInfoGet = await get_product_stripe_info(
        app, product_name=product_name
    )
    user_invoice_address: UserInvoiceAddress = await get_user_invoice_address(
        app, user_id=user_id
    )
    user_info = await get_user_display_and_id_names(app, user_id=user_id)

    return InvoiceDataGet(
        credit_amount=credit_result_get.credit_amount,
        stripe_price_id=product_stripe_info_get.stripe_price_id,
        stripe_tax_rate_id=product_stripe_info_get.stripe_tax_rate_id,
        user_invoice_address=user_invoice_address,
        user_name=user_info.full_name,
        user_email=LowerCaseEmailStr(user_info.email),
    )


async def register_rpc_routes_on_startup(app: web.Application):
    rpc_server = get_rabbitmq_rpc_server(app)
    await rpc_server.register_router(router, WEBSERVER_RPC_NAMESPACE, app)
