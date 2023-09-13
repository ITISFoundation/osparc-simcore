import logging
from decimal import Decimal
from typing import Any

import arrow
from aiohttp import web
from models_library.api_schemas_webserver.wallets import (
    CreatePaymentMethodInitiated,
    PaymentID,
    PaymentMethodGet,
    PaymentMethodID,
    PaymentTransaction,
    WalletPaymentCreated,
)
from models_library.users import UserID
from models_library.utils.fastapi_encoders import jsonable_encoder
from models_library.wallets import WalletID
from pydantic import parse_obj_as
from simcore_postgres_database.models.payments_methods import InitPromptAckFlowState
from simcore_postgres_database.models.payments_transactions import (
    PaymentTransactionState,
)
from yarl import URL

from ..application_settings import get_settings
from ..users.api import get_user_name_and_email
from ..wallets.api import get_wallet_with_permissions_by_user
from ..wallets.errors import WalletAccessForbiddenError
from . import _db
from ._client import get_payments_service_api
from ._socketio import notify_payment_completed

_logger = logging.getLogger(__name__)


async def _check_wallet_permissions(
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
    await _check_wallet_permissions(app, user_id=user_id, wallet_id=wallet_id)

    # hold timestamp
    initiated_at = arrow.utcnow().datetime

    # payment service
    payment_service_api = get_payments_service_api(app)
    submission_link, payment_id = await payment_service_api.create_payment(
        price_dollars=price_dollars,
        product_name=product_name,
        user_id=user_id,
        name=user.name,
        email=user.email,
        osparc_credits=osparc_credits,
    )
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
        # TODO: connect with https://github.com/ITISFoundation/osparc-simcore/pull/4692
        settings = get_settings(app)
        assert settings.WEBSERVER_RESOURCE_USAGE_TRACKER  # nosec
        if base_url := settings.WEBSERVER_RESOURCE_USAGE_TRACKER.base_url:
            url = URL(f"{base_url}/v1/credit-transaction")
            body = (jsonable_encoder(payment, by_alias=False),)
            _logger.debug("-> @RUTH  POST %s: %s", url, body)

    return payment


async def cancel_payment_to_wallet(
    app: web.Application,
    *,
    payment_id: PaymentID,
    user_id: UserID,
    wallet_id: WalletID,
) -> PaymentTransaction:
    await _check_wallet_permissions(app, user_id=user_id, wallet_id=wallet_id)

    return await complete_payment(
        app,
        payment_id=payment_id,
        completion_state=PaymentTransactionState.CANCELED,
        message="Payment aborted by user",
    )


#
# Payment-methods
#


async def init_creation_of_wallet_payment_method(
    app: web.Application, *, user_id: UserID, wallet_id: WalletID
) -> CreatePaymentMethodInitiated:
    # check permissions
    await _check_wallet_permissions(app, user_id=user_id, wallet_id=wallet_id)

    # hold timestamp
    initiated_at = arrow.utcnow().datetime

    raise NotImplementedError


async def complete_create_of_wallet_payment_method(
    app: web.Application,
    *,
    payment_method_id: PaymentMethodID,
    completion_state: InitPromptAckFlowState,
    message: str | None = None,
):
    raise NotImplementedError


async def cancel_creation_of_wallet_payment_method(
    app: web.Application,
    *,
    user_id: UserID,
    wallet_id: WalletID,
    payment_method_id: PaymentMethodID,
):
    await _check_wallet_permissions(app, user_id=user_id, wallet_id=wallet_id)

    acked = await complete_create_of_wallet_payment_method(
        app,
        payment_method_id=payment_method_id,
        completion_state=InitPromptAckFlowState.CANCELED,
        message="Creation of payment-method aborted by user",
    )

    # FIXME: delete???

    return acked


async def list_wallet_payment_methods(
    app: web.Application, *, user_id: UserID, wallet_id: WalletID
) -> list[PaymentMethodGet]:
    # check permissions
    await _check_wallet_permissions(app, user_id=user_id, wallet_id=wallet_id)

    # FIXME: fake!!
    return parse_obj_as(
        list[PaymentMethodGet],
        [
            {**p, "wallet_id": wallet_id}
            for p in PaymentMethodGet.Config.schema_extra["examples"]
        ],
    )


async def get_wallet_payment_method(
    app: web.Application,
    *,
    user_id: UserID,
    wallet_id: WalletID,
    payment_method_id: PaymentMethodID,
) -> PaymentMethodGet:
    # check permissions
    await _check_wallet_permissions(app, user_id=user_id, wallet_id=wallet_id)

    # FIXME: fake!!
    # TODO: call gateway to get payment-method
    # NOTE: if not found? should I delete my database?
    return parse_obj_as(
        PaymentMethodGet,
        {
            **PaymentMethodGet.Config.schema_extra["examples"][0],
            "idr": payment_method_id,
            "wallet_id": wallet_id,
        },
    )


async def delete_wallet_payment_method(
    app: web.Application,
    *,
    user_id: UserID,
    wallet_id: WalletID,
    payment_method_id: PaymentMethodID,
):
    # check permissions
    await _check_wallet_permissions(app, user_id=user_id, wallet_id=wallet_id)
    assert payment_method_id  # nosec

    # FIXME: fake!!
    # TODO: call gateway to delete payment-method
    # TODO: drop payment-method from db
