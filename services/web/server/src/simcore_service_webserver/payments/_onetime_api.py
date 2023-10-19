import logging
from decimal import Decimal
from typing import Any

from aiohttp import web
from models_library.api_schemas_webserver.wallets import (
    PaymentID,
    PaymentTransaction,
    WalletPaymentCreated,
)
from models_library.products import ProductName
from models_library.users import UserID
from models_library.wallets import WalletID
from pydantic import HttpUrl
from simcore_postgres_database.models.payments_transactions import (
    PaymentTransactionState,
)

from ..resource_usage.api import add_credits_to_wallet
from ..users.api import get_user_name_and_email
from ..wallets.api import get_wallet_by_user, get_wallet_with_permissions_by_user
from ..wallets.errors import WalletAccessForbiddenError
from . import _onetime_db, _rpc
from ._socketio import notify_payment_completed

_logger = logging.getLogger(__name__)


async def check_wallet_permissions(
    app: web.Application,
    user_id: UserID,
    wallet_id: WalletID,
    product_name: ProductName,
):
    permissions = await get_wallet_with_permissions_by_user(
        app, user_id=user_id, wallet_id=wallet_id, product_name=product_name
    )
    if not permissions.read or not permissions.write:
        raise WalletAccessForbiddenError(
            reason=f"User {user_id} does not have necessary permissions to do a payment into wallet {wallet_id}"
        )


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


async def init_creation_of_wallet_payment(
    app: web.Application,
    *,
    price_dollars: Decimal,
    osparc_credits: Decimal,
    product_name: str,
    user_id: UserID,
    wallet_id: WalletID,
    comment: str | None,
) -> WalletPaymentCreated:
    """

    Raises:
        UserNotFoundError
        WalletAccessForbiddenError
    """

    # wallet: check permissions
    await check_wallet_permissions(
        app, user_id=user_id, wallet_id=wallet_id, product_name=product_name
    )
    user_wallet = await get_wallet_by_user(
        app, user_id=user_id, wallet_id=wallet_id, product_name=product_name
    )
    assert user_wallet.wallet_id == wallet_id  # nosec

    # user info
    user = await get_user_name_and_email(app, user_id=user_id)

    # call to payment-service
    payment_inited: WalletPaymentCreated = await _rpc.init_payment(
        app,
        amount_dollars=price_dollars,
        target_credits=osparc_credits,
        product_name=product_name,
        wallet_id=wallet_id,
        wallet_name=user_wallet.name,
        user_id=user_id,
        user_name=user.name,
        user_email=user.email,
        comment=comment,
    )
    return payment_inited


async def _ack_creation_of_wallet_payment(
    app: web.Application,
    *,
    payment_id: PaymentID,
    completion_state: PaymentTransactionState,
    message: str | None = None,
    invoice_url: HttpUrl | None = None,
) -> PaymentTransaction:
    #
    # NOTE: implements endpoint in payment service hit by the gateway (ONLY for testing or fake completion!)
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
    await notify_payment_completed(app, user_id=transaction.user_id, payment=payment)

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


async def cancel_payment_to_wallet(
    app: web.Application,
    *,
    payment_id: PaymentID,
    user_id: UserID,
    wallet_id: WalletID,
    product_name: ProductName,
) -> PaymentTransaction:
    await check_wallet_permissions(
        app, user_id=user_id, wallet_id=wallet_id, product_name=product_name
    )

    return await _ack_creation_of_wallet_payment(
        app,
        payment_id=payment_id,
        completion_state=PaymentTransactionState.CANCELED,
        message="Payment aborted by user",
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

    (
        total_number_of_items,
        transactions,
    ) = await _onetime_db.list_user_payment_transactions(
        app, user_id=user_id, offset=offset, limit=limit
    )

    return [_to_api_model(t) for t in transactions], total_number_of_items
