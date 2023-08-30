import logging

import arrow
from aiohttp import web
from models_library.api_schemas_payments.payments import PaymentGet
from models_library.basic_types import IDStr
from models_library.users import UserID
from models_library.wallets import PaymentTransactionState, WalletID
from pydantic import PositiveFloat

from ._client import get_payments_service_api

_logger = logging.getLogger(__name__)


_FAKE_PAYMENTS_TRANSACTIONS: dict[UserID, dict[IDStr, PaymentGet]] = {}


async def create_payment_to_wallet(
    app: web.Application,
    product_name: str,
    user_id: UserID,
    wallet_id: WalletID,
    wallet_name: str,
    prize: PositiveFloat,
    credit: PositiveFloat,
    comment: str | None,
) -> PaymentGet:
    # TODO: user's wallet is verified or should we verify it here?

    # TODO: implement users.api.get_user_name_and_email
    user_email, user_name = f"fake_email_for_user_{user_id}@email.com", "fake_user"

    payment_service_api = get_payments_service_api(app)
    submission_link, transaction_id = await payment_service_api.create_payment(
        product_name=product_name,
        user_id=user_id,
        name=user_name,
        email=user_email,
        credit=credit,
    )

    payment = PaymentGet(
        idr=transaction_id,
        prize=prize,
        wallet_id=wallet_id,
        credit=credit,
        comment=comment or f"Payments to top wallet {wallet_name}",
        state=PaymentTransactionState.INIT,
        created=arrow.utcnow().datetime,
        completed=None,
        submission_link=f"{submission_link}",
    )
    assert payment.idr not in _FAKE_PAYMENTS_TRANSACTIONS[user_id]  # nosec
    _FAKE_PAYMENTS_TRANSACTIONS[user_id][payment.idr] = payment

    return payment


async def get_user_payments_page(
    app: web.Application,
    product_name: str,
    user_id: UserID,
    *,
    limit: int,
    offset: int,
) -> tuple[list, int]:
    assert limit > 1  # nosec
    assert offset >= 0  # nosec
    assert product_name  # nosec

    payments_service = get_payments_service_api(app)
    assert payments_service  # nosec

    user_payments: list[PaymentGet] = list(
        _FAKE_PAYMENTS_TRANSACTIONS[user_id].values()
    )
    total_number_of_items = len(user_payments)
    payments = user_payments[offset : offset + limit]

    return payments, total_number_of_items


assert get_payments_service_api  # nosec

__all__: tuple[str, ...] = (
    "get_payments_service_api",
    "create_payment_to_wallet",
    "get_user_payments_page",
)
