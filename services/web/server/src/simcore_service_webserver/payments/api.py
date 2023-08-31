import logging
from decimal import Decimal

import arrow
from aiohttp import web
from models_library.api_schemas_payments.payments import PaymentGet, PaymentItemList
from models_library.users import UserID
from models_library.wallets import WalletID

from . import _db
from ._client import get_payments_service_api

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
) -> PaymentGet:
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

    return PaymentGet(
        idr=transaction.payment_id,
        submission_link=f"{submission_link}",
    )


async def get_user_payments_page(
    app: web.Application,
    product_name: str,
    user_id: UserID,
    *,
    limit: int,
    offset: int,
) -> tuple[list[PaymentItemList], int]:
    assert limit > 1  # nosec
    assert offset >= 0  # nosec
    assert product_name  # nosec

    payments_service = get_payments_service_api(app)
    assert payments_service  # nosec

    total_number_of_items, transactions = await _db.list_user_payment_transactions(
        app, user_id=user_id, offset=offset, limit=limit
    )

    return [
        PaymentItemList(
            idr=t.payment_id,
            price_dollars=t.price_dollars,
            credit=t.osparc_credits,
            comment=t.comment,
            wallet_id=t.wallet_id,
            state=t.get_state(),
            created=t.initiated_at,
            completed=t.completed_at,
        )
        for t in transactions
    ], total_number_of_items


assert get_payments_service_api  # nosec

__all__: tuple[str, ...] = (
    "get_payments_service_api",
    "create_payment_to_wallet",
    "get_user_payments_page",
)
