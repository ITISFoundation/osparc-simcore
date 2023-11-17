""" RPC client-side for the RPC server at the payments service

"""

import logging
from decimal import Decimal

from aiohttp import web
from models_library.api_schemas_payments import PAYMENTS_RPC_NAMESPACE
from models_library.api_schemas_webserver.wallets import (
    PaymentID,
    PaymentMethodGet,
    PaymentMethodID,
    PaymentMethodInitiated,
    PaymentTransaction,
    WalletPaymentInitiated,
)
from models_library.basic_types import IDStr
from models_library.rabbitmq_basic_types import RPCMethodName
from models_library.users import UserID
from models_library.wallets import WalletID
from pydantic import EmailStr, parse_obj_as
from servicelib.logging_utils import log_decorator
from servicelib.rabbitmq import RabbitMQRPCClient

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
) -> WalletPaymentInitiated:
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
    assert isinstance(result, WalletPaymentInitiated)  # nosec
    return result


@log_decorator(_logger, level=logging.DEBUG)
async def cancel_payment(
    app: web.Application,
    *,
    payment_id: PaymentID,
    user_id: UserID,
    wallet_id: WalletID,
) -> None:
    rpc_client = app[_APP_PAYMENTS_RPC_CLIENT_KEY]

    await rpc_client.request(
        PAYMENTS_RPC_NAMESPACE,
        parse_obj_as(RPCMethodName, "cancel_payment"),
        payment_id=payment_id,
        user_id=user_id,
        wallet_id=wallet_id,
    )


@log_decorator(_logger, level=logging.DEBUG)
async def get_payments_page(
    app: web.Application,
    *,
    user_id: UserID,
    limit: int | None,
    offset: int | None,
) -> tuple[int, list[PaymentTransaction]]:
    rpc_client = app[_APP_PAYMENTS_RPC_CLIENT_KEY]

    result: tuple[int, list[PaymentTransaction]] = await rpc_client.request(
        PAYMENTS_RPC_NAMESPACE,
        parse_obj_as(RPCMethodName, "get_payments_page"),
        user_id=user_id,
        limit=limit,
        offset=offset,
    )
    assert (  # nosec
        parse_obj_as(tuple[int, list[PaymentTransaction]], result) is not None
    )
    return result


@log_decorator(_logger, level=logging.DEBUG)
async def init_creation_of_payment_method(
    app: web.Application,
    *,
    wallet_id: WalletID,
    wallet_name: IDStr,
    user_id: UserID,
    user_name: IDStr,
    user_email: EmailStr,
) -> PaymentMethodInitiated:
    rpc_client = app[_APP_PAYMENTS_RPC_CLIENT_KEY]

    result = await rpc_client.request(
        PAYMENTS_RPC_NAMESPACE,
        parse_obj_as(RPCMethodName, "init_creation_of_payment_method"),
        wallet_id=wallet_id,
        wallet_name=wallet_name,
        user_id=user_id,
        user_name=user_name,
        user_email=user_email,
    )
    assert isinstance(result, PaymentMethodInitiated)  # nosec
    return result


@log_decorator(_logger, level=logging.DEBUG)
async def cancel_creation_of_payment_method(
    app: web.Application,
    *,
    payment_method_id: PaymentMethodID,
    user_id: UserID,
    wallet_id: WalletID,
) -> None:
    rpc_client = app[_APP_PAYMENTS_RPC_CLIENT_KEY]

    result = await rpc_client.request(
        PAYMENTS_RPC_NAMESPACE,
        parse_obj_as(RPCMethodName, "cancel_creation_of_payment_method"),
        payment_method_id=payment_method_id,
        user_id=user_id,
        wallet_id=wallet_id,
    )
    assert result is None  # nosec


@log_decorator(_logger, level=logging.DEBUG)
async def list_payment_methods(
    app: web.Application,
    *,
    user_id: UserID,
    wallet_id: WalletID,
) -> list[PaymentMethodGet]:
    rpc_client = app[_APP_PAYMENTS_RPC_CLIENT_KEY]

    result = await rpc_client.request(
        PAYMENTS_RPC_NAMESPACE,
        parse_obj_as(RPCMethodName, "list_payment_methods"),
        user_id=user_id,
        wallet_id=wallet_id,
    )
    assert isinstance(result, list)  # nosec
    return result


@log_decorator(_logger, level=logging.DEBUG)
async def get_payment_method(
    app: web.Application,
    *,
    payment_method_id: PaymentMethodID,
    user_id: UserID,
    wallet_id: WalletID,
) -> PaymentMethodGet:
    rpc_client = app[_APP_PAYMENTS_RPC_CLIENT_KEY]

    result = await rpc_client.request(
        PAYMENTS_RPC_NAMESPACE,
        parse_obj_as(RPCMethodName, "get_payment_method"),
        payment_method_id=payment_method_id,
        user_id=user_id,
        wallet_id=wallet_id,
    )
    assert isinstance(result, PaymentMethodGet)  # nosec
    return result


@log_decorator(_logger, level=logging.DEBUG)
async def delete_payment_method(
    app: web.Application,
    *,
    payment_method_id: PaymentMethodID,
    user_id: UserID,
    wallet_id: WalletID,
) -> None:
    rpc_client = app[_APP_PAYMENTS_RPC_CLIENT_KEY]

    result = await rpc_client.request(
        PAYMENTS_RPC_NAMESPACE,
        parse_obj_as(RPCMethodName, "delete_payment_method"),
        payment_method_id=payment_method_id,
        user_id=user_id,
        wallet_id=wallet_id,
    )
    assert result is None  # nosec


@log_decorator(_logger, level=logging.DEBUG)
async def pay_with_payment_method(  # noqa: PLR0913 # pylint: disable=too-many-arguments
    app: web.Application,
    *,
    payment_method_id: PaymentMethodID,
    amount_dollars: Decimal,
    target_credits: Decimal,
    product_name: str,
    wallet_id: WalletID,
    wallet_name: str,
    user_id: UserID,
    user_name: str,
    user_email: EmailStr,
    comment: str | None = None,
) -> PaymentTransaction:

    rpc_client = app[_APP_PAYMENTS_RPC_CLIENT_KEY]

    result = await rpc_client.request(
        PAYMENTS_RPC_NAMESPACE,
        parse_obj_as(RPCMethodName, "pay_with_payment_method"),
        payment_method_id=payment_method_id,
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

    assert isinstance(result, PaymentTransaction)  # nosec
    return result
