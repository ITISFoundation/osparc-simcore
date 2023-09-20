import logging
from decimal import Decimal
from typing import Any

import arrow
from aiohttp import web
from models_library.api_schemas_webserver.wallets import (
    PaymentID,
    PaymentTransaction,
    WalletPaymentCreated,
)
from models_library.users import UserID
from models_library.wallets import WalletID
from simcore_postgres_database.models.payments_transactions import (
    PaymentTransactionState,
)

from ..resource_usage.api import add_credits_to_wallet
from ..users.api import get_user_name_and_email
from ..wallets.api import get_wallet_by_user, get_wallet_with_permissions_by_user
from ..wallets.errors import WalletAccessForbiddenError
from . import _db
from ._client import create_fake_payment, get_payments_service_api
from ._socketio import notify_payment_completed

_logger = logging.getLogger(__name__)


async def check_wallet_permissions(
    app: web.Application, user_id: UserID, wallet_id: WalletID
):
    permissions = await get_wallet_with_permissions_by_user(
        app, user_id=user_id, wallet_id=wallet_id
    )
    if not permissions.read or not permissions.write:
        raise WalletAccessForbiddenError(
            reason=f"User {user_id} does not have necessary permissions to do a payment into wallet {wallet_id}"
        )


def _to_api_model(transaction: _db.PaymentsTransactionsDB) -> PaymentTransaction:
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

    return PaymentTransaction.parse_obj(data)


#
# One-time Payments
#


async def create_payment_to_wallet(
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
    # get user info
    user = await get_user_name_and_email(app, user_id=user_id)

    # check permissions
    await check_wallet_permissions(app, user_id=user_id, wallet_id=wallet_id)

    # hold timestamp
    initiated_at = arrow.utcnow().datetime

    # payment service
    # FAKE ------------
    submission_link, payment_id = await create_fake_payment(
        app,
        price_dollars=price_dollars,
        product_name=product_name,
        user_id=user_id,
        name=user.name,
        email=user.email,
        osparc_credits=osparc_credits,
    )
    # -----
    # gateway responded, we store the transaction
    await _db.create_payment_transaction(
        app,
        payment_id=payment_id,
        price_dollars=price_dollars,
        osparc_credits=osparc_credits,
        product_name=product_name,
        user_id=user_id,
        user_email=user.email,
        wallet_id=wallet_id,
        comment=comment,
        initiated_at=initiated_at,
    )

    return WalletPaymentCreated(
        payment_id=payment_id,
        payment_form_url=f"{submission_link}",
    )


async def get_user_payments_page(
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

    payments_service = get_payments_service_api(app)
    assert payments_service  # nosec

    total_number_of_items, transactions = await _db.list_user_payment_transactions(
        app, user_id=user_id, offset=offset, limit=limit
    )

    return [_to_api_model(t) for t in transactions], total_number_of_items


async def complete_payment(
    app: web.Application,
    *,
    payment_id: PaymentID,
    completion_state: PaymentTransactionState,
    message: str | None = None,
) -> PaymentTransaction:
    # NOTE: implements endpoint in payment service hit by the gateway
    transaction = await _db.complete_payment_transaction(
        app,
        payment_id=payment_id,
        completion_state=completion_state,
        state_message=message,
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
            app, transaction.user_id, transaction.wallet_id
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
) -> PaymentTransaction:
    await check_wallet_permissions(app, user_id=user_id, wallet_id=wallet_id)

    return await complete_payment(
        app,
        payment_id=payment_id,
        completion_state=PaymentTransactionState.CANCELED,
        message="Payment aborted by user",
    )
