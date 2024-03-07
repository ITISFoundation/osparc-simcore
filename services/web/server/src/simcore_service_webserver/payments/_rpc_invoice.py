from decimal import Decimal

import pycountry
from aiohttp import web
from models_library.api_schemas_webserver import WEBSERVER_RPC_NAMESPACE
from models_library.payments import InvoiceDataGet, UserInvoiceAddress
from models_library.products import CreditResultGet, ProductName, ProductStripeInfoGet
from models_library.users import UserBillingDetails, UserID
from servicelib.rabbitmq import RPCRouter

from ..products.api import get_credit_amount, get_product_stripe_info
from ..rabbitmq import get_rabbitmq_rpc_server
from ..users.api import get_user_billing_details

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
    user_billing_details: UserBillingDetails = await get_user_billing_details(
        app, user_id=user_id
    )

    _user_billing_country = pycountry.countries.lookup(user_billing_details.country)
    _user_billing_country_alpha_2_format = _user_billing_country.alpha_2

    _user_invoice_address = UserInvoiceAddress(
        line1=user_billing_details.address,
        state=user_billing_details.state,
        postal_code=user_billing_details.postal_code,
        city=user_billing_details.city,
        country=_user_billing_country_alpha_2_format,
    )

    return InvoiceDataGet(
        credit_amount=credit_result_get.credit_amount,
        stripe_price_id=product_stripe_info_get.stripe_price_id,
        stripe_tax_rate_id=product_stripe_info_get.stripe_tax_rate_id,
        user_invoice_address=_user_invoice_address,
    )


async def register_rpc_routes_on_startup(app: web.Application):
    rpc_server = get_rabbitmq_rpc_server(app)
    await rpc_server.register_router(router, WEBSERVER_RPC_NAMESPACE, app)
