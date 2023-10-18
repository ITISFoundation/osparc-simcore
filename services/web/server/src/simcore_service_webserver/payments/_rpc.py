""" RPC client-side for the RPC server at the payments service

"""

import logging
from decimal import Decimal

from aiohttp import web
from models_library.api_schemas_payments import PAYMENTS_RPC_NAMESPACE
from models_library.api_schemas_webserver.wallets import WalletPaymentCreated
from models_library.users import UserID
from models_library.wallets import WalletID
from pydantic import parse_obj_as
from servicelib.logging_utils import log_decorator
from servicelib.rabbitmq import RabbitMQRPCClient, RPCMethodName

from ..rabbitmq_settings import RabbitSettings
from ..rabbitmq_settings import get_plugin_settings as get_rabbitmq_settings

_logger = logging.getLogger(__name__)


_APP_PAYMENTS_RPC_CLIENT_KEY = f"{__name__}.RabbitMQRPCClient"


async def rabbitmq_rpc_client_lifespan(app: web.Application):
    settings: RabbitSettings = get_rabbitmq_settings(app)
    rpc_client = await RabbitMQRPCClient.create(
        client_name="webserver_payments_client",
        settings=settings,
    )

    assert rpc_client  # nosec
    assert rpc_client.client_name == "webserver_payments_client"  # nosec
    assert rpc_client.settings == settings  # nosec

    app[_APP_PAYMENTS_RPC_CLIENT_KEY] = rpc_client

    yield

    await rpc_client.close()


#
# rpc client functions
#


@log_decorator(_logger, level=logging.DEBUG)
async def init_payment(
    app: web.Application,
    *,
    amount_dollars: Decimal,
    target_credits: Decimal,
    product_name: str,
    wallet_id: WalletID,
    wallet_name: str,
    user_id: UserID,
    user_name: str,
    user_email: str,
    comment: str | None = None,
) -> WalletPaymentCreated:
    rpc_client = app[_APP_PAYMENTS_RPC_CLIENT_KEY]

    # NOTE: remote errors are aio_pika.MessageProcessError
    result = await rpc_client.request(
        PAYMENTS_RPC_NAMESPACE,
        parse_obj_as(RPCMethodName, "init_payment"),
        amount_dollars=amount_dollars,
        target_credits=target_credits,
        product_name=product_name,
        wallet_id=wallet_id,
        wallet_name=wallet_name,
        user_id=user_id,
        user_name=user_name,
        user_email=user_email,
        comment=comment,
    )
    assert isinstance(result, WalletPaymentCreated)  # nosec
    return result
