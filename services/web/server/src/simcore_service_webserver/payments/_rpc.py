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
from models_library.payments import UserInvoiceAddress
from models_library.products import ProductName, StripePriceID, StripeTaxRateID
from models_library.rabbitmq_basic_types import RPCMethodName
from models_library.users import UserID
from models_library.wallets import WalletID
from pydantic import EmailStr, HttpUrl, TypeAdapter
from servicelib.logging_utils import log_decorator
from servicelib.rabbitmq import RPC_REQUEST_DEFAULT_TIMEOUT_S

from ..rabbitmq import get_rabbitmq_rpc_client

_logger = logging.getLogger(__name__)


@log_decorator(_logger, level=logging.DEBUG)
async def init_payment(  # pylint: disable=too-many-arguments
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
    user_address: UserInvoiceAddress,
    stripe_price_id: StripePriceID,
    stripe_tax_rate_id: StripeTaxRateID,
    comment: str | None = None,
) -> WalletPaymentInitiated:
    rpc_client = get_rabbitmq_rpc_client(app)

    # NOTE: remote errors are aio_pika.MessageProcessError
    result = await rpc_client.request(
        PAYMENTS_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python("init_payment"),
        amount_dollars=amount_dollars,
        target_credits=target_credits,
        product_name=product_name,
        wallet_id=wallet_id,
        wallet_name=wallet_name,
        user_id=user_id,
        user_name=user_name,
        user_email=user_email,
        user_address=user_address,
        stripe_price_id=stripe_price_id,
        stripe_tax_rate_id=stripe_tax_rate_id,
        comment=comment,
        timeout_s=2 * RPC_REQUEST_DEFAULT_TIMEOUT_S,
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
    rpc_client = get_rabbitmq_rpc_client(app)

    await rpc_client.request(
        PAYMENTS_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python("cancel_payment"),
        payment_id=payment_id,
        user_id=user_id,
        wallet_id=wallet_id,
        timeout_s=2 * RPC_REQUEST_DEFAULT_TIMEOUT_S,
    )


@log_decorator(_logger, level=logging.DEBUG)
async def get_payments_page(
    app: web.Application,
    *,
    user_id: UserID,
    product_name: ProductName,
    limit: int | None,
    offset: int | None,
) -> tuple[int, list[PaymentTransaction]]:
    rpc_client = get_rabbitmq_rpc_client(app)

    result: tuple[int, list[PaymentTransaction]] = await rpc_client.request(
        PAYMENTS_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python("get_payments_page"),
        user_id=user_id,
        product_name=product_name,
        limit=limit,
        offset=offset,
        timeout_s=2 * RPC_REQUEST_DEFAULT_TIMEOUT_S,
    )
    assert (  # nosec
        TypeAdapter(tuple[int, list[PaymentTransaction]]).validate_python(result)
        is not None
    )
    return result


@log_decorator(_logger, level=logging.DEBUG)
async def get_payment_invoice_url(
    app: web.Application,
    *,
    user_id: UserID,
    wallet_id: WalletID,
    payment_id: PaymentID,
) -> HttpUrl:
    rpc_client = get_rabbitmq_rpc_client(app)

    result: HttpUrl = await rpc_client.request(
        PAYMENTS_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python("get_payment_invoice_url"),
        user_id=user_id,
        wallet_id=wallet_id,
        payment_id=payment_id,
        timeout_s=2 * RPC_REQUEST_DEFAULT_TIMEOUT_S,
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
    rpc_client = get_rabbitmq_rpc_client(app)

    result = await rpc_client.request(
        PAYMENTS_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python("init_creation_of_payment_method"),
        wallet_id=wallet_id,
        wallet_name=wallet_name,
        user_id=user_id,
        user_name=user_name,
        user_email=user_email,
        timeout_s=2 * RPC_REQUEST_DEFAULT_TIMEOUT_S,
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
    rpc_client = get_rabbitmq_rpc_client(app)

    result = await rpc_client.request(
        PAYMENTS_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python("cancel_creation_of_payment_method"),
        payment_method_id=payment_method_id,
        user_id=user_id,
        wallet_id=wallet_id,
        timeout_s=2 * RPC_REQUEST_DEFAULT_TIMEOUT_S,
    )
    assert result is None  # nosec


@log_decorator(_logger, level=logging.DEBUG)
async def list_payment_methods(
    app: web.Application,
    *,
    user_id: UserID,
    wallet_id: WalletID,
) -> list[PaymentMethodGet]:
    rpc_client = get_rabbitmq_rpc_client(app)

    result = await rpc_client.request(
        PAYMENTS_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python("list_payment_methods"),
        user_id=user_id,
        wallet_id=wallet_id,
        timeout_s=2 * RPC_REQUEST_DEFAULT_TIMEOUT_S,
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
    rpc_client = get_rabbitmq_rpc_client(app)

    result = await rpc_client.request(
        PAYMENTS_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python("get_payment_method"),
        payment_method_id=payment_method_id,
        user_id=user_id,
        wallet_id=wallet_id,
        timeout_s=2 * RPC_REQUEST_DEFAULT_TIMEOUT_S,
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
    rpc_client = get_rabbitmq_rpc_client(app)

    result = await rpc_client.request(
        PAYMENTS_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python("delete_payment_method"),
        payment_method_id=payment_method_id,
        user_id=user_id,
        wallet_id=wallet_id,
        timeout_s=2 * RPC_REQUEST_DEFAULT_TIMEOUT_S,
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
    user_address: UserInvoiceAddress,
    stripe_price_id: StripePriceID,
    stripe_tax_rate_id: StripeTaxRateID,
    comment: str | None = None,
) -> PaymentTransaction:
    rpc_client = get_rabbitmq_rpc_client(app)

    result = await rpc_client.request(
        PAYMENTS_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python("pay_with_payment_method"),
        payment_method_id=payment_method_id,
        amount_dollars=amount_dollars,
        target_credits=target_credits,
        product_name=product_name,
        wallet_id=wallet_id,
        wallet_name=wallet_name,
        user_id=user_id,
        user_name=user_name,
        user_email=user_email,
        user_address=user_address,
        stripe_price_id=stripe_price_id,
        stripe_tax_rate_id=stripe_tax_rate_id,
        comment=comment,
        timeout_s=3 * RPC_REQUEST_DEFAULT_TIMEOUT_S,
    )

    assert isinstance(result, PaymentTransaction)  # nosec
    return result
