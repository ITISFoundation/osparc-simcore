import logging
from decimal import Decimal
from typing import Any, cast
from uuid import uuid4

import arrow
from aiohttp import web
from models_library.api_schemas_webserver.wallets import (
    PaymentID,
    PaymentMethodID,
    PaymentTransaction,
    WalletPaymentInitiated,
)
from models_library.basic_types import IDStr
from models_library.products import ProductName
from models_library.users import UserID
from models_library.wallets import WalletID
from pydantic import HttpUrl, parse_obj_as
from servicelib.logging_utils import log_decorator
from simcore_postgres_database.models.payments_transactions import (
    PaymentTransactionState,
)
from simcore_postgres_database.utils_payments import insert_init_payment_transaction
from yarl import URL

from ..db.plugin import get_database_engine
from ..products.api import get_product_stripe_info
from ..resource_usage.api import add_credits_to_wallet
from ..users.api import get_user_display_and_id_names, get_user_invoice_address
from ..wallets.api import get_wallet_by_user, get_wallet_with_permissions_by_user
from ..wallets.errors import WalletAccessForbiddenError
from . import _onetime_db, _rpc
from ._socketio import notify_payment_completed
from .settings import PaymentsSettings, get_plugin_settings

_logger = logging.getLogger(__name__)


MSG_WALLET_NO_ACCESS_ERROR = "User {user_id} does not have necessary permissions to do a payment into wallet {wallet_id}"
_FAKE_PAYMENT_TRANSACTION_ID_PREFIX = "fpt"


def _to_api_model(
    transaction: _onetime_db.PaymentsTransactionsDB,
) -> PaymentTransaction:
    data: dict[str, Any] = {
        "payment_id": transaction.payment_id,
        "price_dollars": transaction.price_dollars,
        "osparc_credits": transaction.osparc_credits,
        "wallet_id": transaction.wallet_id,
        "created_at": transaction.initiated_at,
        "state": transaction.state,
        "completed_at": transaction.completed_at,
    }

    if transaction.comment:
        data["comment"] = transaction.comment

    if transaction.state_message:
        data["state_message"] = transaction.state_message

    if transaction.invoice_url:
        data["invoice_url"] = transaction.invoice_url

    return PaymentTransaction.parse_obj(data)


@log_decorator(_logger, level=logging.INFO)
async def _fake_init_payment(
    app,
    amount_dollars,
    target_credits,
    product_name,
    wallet_id,
    user_id,
    user_email,
    comment,
):
    # (1) Init payment
    payment_id = f"{_FAKE_PAYMENT_TRANSACTION_ID_PREFIX}_{uuid4()}"
    # get_form_payment_url
    settings: PaymentsSettings = get_plugin_settings(app)
    external_form_link = (
        URL(settings.PAYMENTS_FAKE_GATEWAY_URL)
        .with_path("/pay")
        .with_query(id=payment_id)
    )
    # (2) Annotate INIT transaction
    async with get_database_engine(app).acquire() as conn:
        await insert_init_payment_transaction(
            conn,
            payment_id=payment_id,
            price_dollars=amount_dollars,
            osparc_credits=target_credits,
            product_name=product_name,
            user_id=user_id,
            user_email=user_email,
            wallet_id=wallet_id,
            comment=comment,
            initiated_at=arrow.utcnow().datetime,
        )
    return WalletPaymentInitiated(
        payment_id=IDStr(payment_id), payment_form_url=f"{external_form_link}"  # type: ignore[arg-type]
    )


async def _ack_creation_of_wallet_payment(
    app: web.Application,
    *,
    payment_id: PaymentID,
    completion_state: PaymentTransactionState,
    message: str | None = None,
    invoice_url: HttpUrl | None = None,
    notify_enabled: bool = True,
) -> PaymentTransaction:
    #
    # NOTE: implements endpoint in payment service hit by the gateway
    # IMPORTANT: ONLY for testing or fake completion!
    #
    transaction = await _onetime_db.complete_payment_transaction(
        app,
        payment_id=payment_id,
        completion_state=completion_state,
        state_message=message,
        invoice_url=invoice_url,
    )
    assert transaction.payment_id == payment_id  # nosec
    assert transaction.completed_at is not None  # nosec
    assert transaction.initiated_at < transaction.completed_at  # nosec

    _logger.info("Transaction completed: %s", transaction.json(indent=1))

    payment = _to_api_model(transaction)

    # notifying front-end via web-sockets
    if notify_enabled:
        await notify_payment_completed(
            app, user_id=transaction.user_id, payment=payment
        )

    if completion_state == PaymentTransactionState.SUCCESS:
        # notifying RUT
        user_wallet = await get_wallet_by_user(
            app, transaction.user_id, transaction.wallet_id, transaction.product_name
        )
        await add_credits_to_wallet(
            app=app,
            product_name=transaction.product_name,
            wallet_id=transaction.wallet_id,
            wallet_name=user_wallet.name,
            user_id=transaction.user_id,
            user_email=transaction.user_email,
            osparc_credits=transaction.osparc_credits,
            payment_id=transaction.payment_id,
            created_at=transaction.completed_at,
        )

    return payment


@log_decorator(_logger, level=logging.INFO)
async def _fake_cancel_payment(app, payment_id) -> None:
    await _ack_creation_of_wallet_payment(
        app,
        payment_id=payment_id,
        completion_state=PaymentTransactionState.CANCELED,
        message="Payment aborted by user",
    )


@log_decorator(_logger, level=logging.INFO)
async def _fake_pay_with_payment_method(  # noqa: PLR0913 pylint: disable=too-many-arguments
    app,
    amount_dollars,
    target_credits,
    product_name,
    wallet_id,
    wallet_name,
    user_id,
    user_name,
    user_email,
    payment_method_id: PaymentMethodID,
    comment,
) -> PaymentTransaction:

    assert user_name  # nosec
    assert wallet_name  # nosec

    inited = await _fake_init_payment(
        app,
        amount_dollars,
        target_credits,
        product_name,
        wallet_id,
        user_id,
        user_email,
        comment,
    )
    return await _ack_creation_of_wallet_payment(
        app,
        payment_id=inited.payment_id,
        completion_state=PaymentTransactionState.SUCCESS,
        message=f"Fake payment completed with {payment_method_id=}",
        invoice_url=f"https://fake-invoice.com/?id={inited.payment_id}",  # type: ignore
        notify_enabled=False,
    )


@log_decorator(_logger, level=logging.INFO)
async def _fake_get_payments_page(
    app: web.Application,
    user_id: UserID,
    limit: int,
    offset: int,
):

    (
        total_number_of_items,
        transactions,
    ) = await _onetime_db.list_user_payment_transactions(
        app, user_id=user_id, offset=offset, limit=limit
    )

    return total_number_of_items, [_to_api_model(t) for t in transactions]


@log_decorator(_logger, level=logging.INFO)
async def _fake_get_payment_invoice_url(
    app: web.Application,
    user_id: UserID,
    wallet_id: WalletID,
    payment_id: PaymentID,
) -> HttpUrl:
    assert app  ## nosec
    assert user_id  # nosec
    assert wallet_id  # nosec

    return cast(
        HttpUrl, parse_obj_as(HttpUrl, f"https://fake-invoice.com/?id={payment_id}")
    )


async def raise_for_wallet_payments_permissions(
    app: web.Application,
    *,
    user_id: UserID,
    wallet_id: WalletID,
    product_name: ProductName,
):
    """
    NOTE: payments can only be done to owned wallets therefore
    we cannot allow users with read-only access to even read any
    payment information associated to this wallet.
    SEE some context about this in https://github.com/ITISFoundation/osparc-simcore/pull/4897
    """
    permissions = await get_wallet_with_permissions_by_user(
        app, user_id=user_id, wallet_id=wallet_id, product_name=product_name
    )
    if not permissions.read or not permissions.write:
        raise WalletAccessForbiddenError(
            reason=MSG_WALLET_NO_ACCESS_ERROR.format(
                user_id=user_id, wallet_id=wallet_id
            )
        )


async def init_creation_of_wallet_payment(
    app: web.Application,
    *,
    price_dollars: Decimal,
    osparc_credits: Decimal,
    product_name: str,
    user_id: UserID,
    wallet_id: WalletID,
    comment: str | None,
) -> WalletPaymentInitiated:
    """

    Raises:
        UserNotFoundError
        WalletAccessForbiddenError
    """

    # wallet: check permissions
    await raise_for_wallet_payments_permissions(
        app, user_id=user_id, wallet_id=wallet_id, product_name=product_name
    )
    user_wallet = await get_wallet_by_user(
        app, user_id=user_id, wallet_id=wallet_id, product_name=product_name
    )
    assert user_wallet.wallet_id == wallet_id  # nosec

    # user info
    user = await get_user_display_and_id_names(app, user_id=user_id)
    user_invoice_address = await get_user_invoice_address(app, user_id=user_id)
    # stripe info
    product_stripe_info = await get_product_stripe_info(app, product_name=product_name)

    settings: PaymentsSettings = get_plugin_settings(app)
    payment_inited: WalletPaymentInitiated
    if settings.PAYMENTS_FAKE_COMPLETION:
        payment_inited = await _fake_init_payment(
            app,
            price_dollars,
            osparc_credits,
            product_name,
            wallet_id,
            user_id,
            user.email,
            comment,
        )
    else:
        # call to payment-service
        assert not settings.PAYMENTS_FAKE_COMPLETION  # nosec
        payment_inited = await _rpc.init_payment(
            app,
            amount_dollars=price_dollars,
            target_credits=osparc_credits,
            product_name=product_name,
            wallet_id=wallet_id,
            wallet_name=user_wallet.name,
            user_id=user_id,
            user_name=user.full_name,
            user_email=user.email,
            user_address=user_invoice_address,
            stripe_price_id=product_stripe_info.stripe_price_id,
            stripe_tax_rate_id=product_stripe_info.stripe_tax_rate_id,
            comment=comment,
        )

    return payment_inited


async def cancel_payment_to_wallet(
    app: web.Application,
    *,
    payment_id: PaymentID,
    user_id: UserID,
    wallet_id: WalletID,
    product_name: ProductName,
) -> None:
    await raise_for_wallet_payments_permissions(
        app, user_id=user_id, wallet_id=wallet_id, product_name=product_name
    )

    settings: PaymentsSettings = get_plugin_settings(app)
    if settings.PAYMENTS_FAKE_COMPLETION:
        await _fake_cancel_payment(app, payment_id)

    else:
        assert not settings.PAYMENTS_FAKE_COMPLETION  # nosec
        await _rpc.cancel_payment(
            app, payment_id=payment_id, user_id=user_id, wallet_id=wallet_id
        )


async def pay_with_payment_method(
    app: web.Application,
    *,
    price_dollars: Decimal,
    osparc_credits: Decimal,
    product_name: str,
    user_id: UserID,
    wallet_id: WalletID,
    payment_method_id: PaymentMethodID,
    comment: str | None,
) -> PaymentTransaction:

    # wallet: check permissions
    await raise_for_wallet_payments_permissions(
        app, user_id=user_id, wallet_id=wallet_id, product_name=product_name
    )
    user_wallet = await get_wallet_by_user(
        app, user_id=user_id, wallet_id=wallet_id, product_name=product_name
    )
    assert user_wallet.wallet_id == wallet_id  # nosec

    # stripe info
    product_stripe_info = await get_product_stripe_info(app, product_name=product_name)

    # user info
    user = await get_user_display_and_id_names(app, user_id=user_id)
    user_invoice_address = await get_user_invoice_address(app, user_id=user_id)

    settings: PaymentsSettings = get_plugin_settings(app)
    if settings.PAYMENTS_FAKE_COMPLETION:
        return await _fake_pay_with_payment_method(
            app,
            payment_method_id=payment_method_id,
            amount_dollars=price_dollars,
            target_credits=osparc_credits,
            product_name=product_name,
            wallet_id=wallet_id,
            wallet_name=user_wallet.name,
            user_id=user_id,
            user_name=user.full_name,
            user_email=user.email,
            comment=comment,
        )

    assert not settings.PAYMENTS_FAKE_COMPLETION  # nosec

    return await _rpc.pay_with_payment_method(
        app,
        payment_method_id=payment_method_id,
        amount_dollars=price_dollars,
        target_credits=osparc_credits,
        product_name=product_name,
        wallet_id=wallet_id,
        wallet_name=user_wallet.name,
        user_id=user_id,
        user_name=user.full_name,
        user_email=user.email,
        user_address=user_invoice_address,
        stripe_price_id=product_stripe_info.stripe_price_id,
        stripe_tax_rate_id=product_stripe_info.stripe_tax_rate_id,
        comment=comment,
    )


async def list_user_payments_page(
    app: web.Application,
    product_name: str,
    user_id: UserID,
    *,
    limit: int,
    offset: int,
) -> tuple[list[PaymentTransaction], int]:
    assert limit > 1  # nosec
    assert offset >= 0  # nosec
    assert product_name  # nosec

    settings: PaymentsSettings = get_plugin_settings(app)
    if settings.PAYMENTS_FAKE_COMPLETION:
        total_number_of_items, payments = await _fake_get_payments_page(
            app, user_id=user_id, offset=offset, limit=limit
        )

    else:
        assert not settings.PAYMENTS_FAKE_COMPLETION  # nosec
        total_number_of_items, payments = await _rpc.get_payments_page(
            app, user_id=user_id, product_name=product_name, offset=offset, limit=limit
        )

    return payments, total_number_of_items


async def get_payment_invoice_url(
    app: web.Application,
    product_name: str,
    user_id: UserID,
    *,
    wallet_id: WalletID,
    payment_id: PaymentID,
) -> HttpUrl:
    assert product_name  # nosec
    assert wallet_id  # nosec

    payment_invoice_url: HttpUrl
    settings: PaymentsSettings = get_plugin_settings(app)
    if settings.PAYMENTS_FAKE_COMPLETION:
        payment_invoice_url = await _fake_get_payment_invoice_url(
            app, user_id=user_id, wallet_id=wallet_id, payment_id=payment_id
        )

    else:
        assert not settings.PAYMENTS_FAKE_COMPLETION  # nosec
        payment_invoice_url = await _rpc.get_payment_invoice_url(
            app, user_id=user_id, wallet_id=wallet_id, payment_id=payment_id
        )

    return payment_invoice_url
