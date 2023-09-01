import logging
from decimal import Decimal

import arrow
from aiohttp import web
from models_library.api_schemas_webserver.wallets import (
    PaymentTransaction,
    WalletPaymentCreated,
)
from models_library.basic_types import IDStr
from models_library.users import UserID
from models_library.utils.fastapi_encoders import jsonable_encoder
from models_library.wallets import WalletID
from simcore_service_webserver.application_settings import get_settings
from yarl import URL

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
) -> WalletPaymentCreated:
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

    return WalletPaymentCreated(
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
            created_at=t.initiated_at,
            completed_at=t.completed_at,
        )
        for t in transactions
    ], total_number_of_items


async def complete_payment(
    app: web.Application,
    *,
    payment_id: IDStr,
    success: bool,
    message: str | None = None,
):
    # NOTE: implements endpoint in payment service hit by the gateway
    transaction = await _db.complete_payment_transaction(
        app,
        payment_id=payment_id,
        success=success,
        error_msg=None if success else message,
    )
    assert transaction.payment_id == payment_id  # nosec
    assert transaction.completed_at is not None  # nosec
    assert transaction.initiated_at < transaction.completed_at  # nosec

    _logger.info("Transaction completed: %s", transaction.json(indent=1))

    # notifying front-end via web-sockets
    await notify_payment_completed(
        app,
        user_id=transaction.user_id,
        payment_id=transaction.payment_id,
        wallet_id=transaction.wallet_id,
        completed_at=transaction.completed_at,
        completed_success=success,
        completed_message=message,
    )

    # notifying RUT
    # TODO: connect with https://github.com/ITISFoundation/osparc-simcore/pull/4692
    settings = get_settings(app)
    assert settings.WEBSERVER_RESOURCE_USAGE_TRACKER  # nosec
    if base_url := settings.WEBSERVER_RESOURCE_USAGE_TRACKER.base_url:
        url = URL(f"{base_url}/v1/credit-transaction")
        body = jsonable_encoder(
            {
                "product_name": transaction.product_name,
                "wallet_id": transaction.wallet_id,
                "wallet_name": transaction.wallet_name,
                "user_id": transaction.user_id,
                "user_email": transaction.user_email,
                "credits": transaction.osparc_credits,
                "payment_transaction_id": transaction.payment_id,
                "created_at": transaction.initiated_at,
            }
        )
        _logger.debug("-> @RUTH  POST %s: %s", url, body)
