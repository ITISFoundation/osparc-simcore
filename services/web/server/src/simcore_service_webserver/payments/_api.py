import logging
from decimal import Decimal

import arrow
from aiohttp import web
from models_library.api_schemas_payments.payments import (
    PaymentInitiated,
    PaymentTransaction,
)
from models_library.basic_types import IDStr
from models_library.users import UserID
from models_library.wallets import WalletID

from . import _db
from ._client import get_payments_service_api
from ._socketio import notify_payment_completed

_logger = logging.getLogger(__name__)


async def create_payment_to_wallet(
    app: web.Application,
    *,
    price_dollars: Decimal,
    osparc_credit: Decimal,
    product_name: str,
    user_id: UserID,
    wallet_id: WalletID,
    wallet_name: str,
    comment: str | None,
) -> PaymentInitiated:
    # TODO: user's wallet is verified or should we verify it here?
    # TODO: implement users.api.get_user_name_and_email
    user_email, user_name = f"fake_email_for_user_{user_id}@email.com", "fake_user"

    initiated_at = arrow.utcnow().datetime

    # payment service
    payment_service_api = get_payments_service_api(app)
    submission_link, payment_id = await payment_service_api.create_payment(
        price_dollars=price_dollars,
        product_name=product_name,
        user_id=user_id,
        name=user_name,
        email=user_email,
        osparc_credits=osparc_credit,
    )
    # gateway responded, we store the transaction
    transaction = await _db.create_payment_transaction(
        app,
        payment_id=payment_id,
        price_dollars=price_dollars,
        osparc_credits=osparc_credit,
        product_name=product_name,
        user_id=user_id,
        user_email=user_email,
        wallet_id=wallet_id,
        wallet_name=wallet_name,
        comment=comment,
        initiated_at=initiated_at,
    )

    return PaymentInitiated(
        payment_id=transaction.payment_id,
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

    return [
        PaymentTransaction(
            payment_id=t.payment_id,
            price_dollars=t.price_dollars,
            osparc_credits=t.osparc_credits,
            comment=t.comment,
            wallet_id=t.wallet_id,
            state=t.get_state(),
            created=t.initiated_at,
            completed=t.completed_at,
        )
        for t in transactions
    ], total_number_of_items


async def complete_payment(
    app: web.Application,
    *,
    payment_id: IDStr,
    success: bool,
):
    # NOTE: implements endpoint in payment service hit by the gateway
    # check and complete
    transaction: await _db.update_payment_transaction(app, payment_id=payment_id)
    assert transaction.payment_id == payment_id  # nosec

    # TODO: top up credits
    await notify_payment_completed(
        app,
        user_id=transaction.user_id,
        payment_id=payment_id,
        wallet_id=transaction.wallet_id,
        error=None if success else "Payment rejected",
    )
