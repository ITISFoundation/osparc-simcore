import asyncio
import json
import logging
from typing import Any
from uuid import uuid4

import arrow
from aiohttp import web
from faker import Faker
from models_library.api_schemas_webserver.wallets import (
    PaymentMethodGet,
    PaymentMethodID,
    PaymentMethodInit,
    PaymentMethodTransaction,
)
from models_library.users import UserID
from models_library.wallets import WalletID
from simcore_postgres_database.models.payments_methods import InitPromptAckFlowState
from yarl import URL

from ._api import check_wallet_permissions
from ._methods_db import (
    PaymentsMethodsDB,
    delete_payment_method,
    get_successful_payment_method,
    insert_init_payment_method,
    list_successful_payment_methods,
    udpate_payment_method,
)
from ._socketio import notify_payment_method_acked
from .settings import PaymentsSettings, get_plugin_settings

_logger = logging.getLogger(__name__)


def _generate_fake_data(fake: Faker):
    return {
        "idr": fake.uuid4(),
        "card_holder_name": fake.name(),
        "card_number_masked": f"**** **** **** {fake.credit_card_number()[:4]}",
        "card_type": fake.credit_card_provider(),
        "expiration_month": fake.random_int(min=1, max=12),
        "expiration_year": fake.future_date().year,
        "street_address": fake.street_address(),
        "zipcode": fake.zipcode(),
        "country": fake.country(),
    }


def _to_api_model(
    entry: PaymentsMethodsDB, payment_method_details_from_gateway: dict[str, Any]
) -> PaymentMethodGet:
    assert entry.completed_at  # nosec

    return PaymentMethodGet.parse_obj(
        {
            **payment_method_details_from_gateway,
            "idr": entry.payment_method_id,
            "wallet_id": entry.wallet_id,
            "created": entry.completed_at,
        }
    )


#
# Payment-methods
#


async def init_creation_of_wallet_payment_method(
    app: web.Application, *, user_id: UserID, wallet_id: WalletID
) -> PaymentMethodInit:
    """

    Raises:
        WalletAccessForbiddenError
        PaymentMethodUniqueViolationError
    """

    # check permissions
    await check_wallet_permissions(app, user_id=user_id, wallet_id=wallet_id)

    # hold timestamp
    initiated_at = arrow.utcnow().datetime

    # FAKE -----
    _logger.debug("FAKE Payments Gateway: /payment-methods:init")
    settings: PaymentsSettings = get_plugin_settings(app)
    await asyncio.sleep(1)
    payment_method_id = PaymentMethodID(f"{uuid4()}".upper())
    form_link = (
        URL(settings.PAYMENTS_FAKE_GATEWAY_URL)
        .with_path("/payment-methods/form")
        .with_query(id=payment_method_id)
    )
    # -----

    # annotate
    await insert_init_payment_method(
        app,
        payment_method_id=payment_method_id,
        user_id=user_id,
        wallet_id=wallet_id,
        initiated_at=initiated_at,
    )

    return PaymentMethodInit(
        wallet_id=wallet_id,
        payment_method_id=payment_method_id,
        payment_method_form_url=f"{form_link}",
    )


async def _complete_create_of_wallet_payment_method(
    app: web.Application,
    *,
    payment_method_id: PaymentMethodID,
    completion_state: InitPromptAckFlowState,
    message: str | None = None,
) -> PaymentsMethodsDB:
    """Acks as completed (i.e. SUCCESSFUL, FAILED, CANCELED )"""
    assert completion_state != InitPromptAckFlowState.PENDING  # nosec

    # annotate
    updated: PaymentsMethodsDB = await udpate_payment_method(
        app,
        payment_method_id=payment_method_id,
        state=completion_state,
        state_message=message,
    )

    # notify front-end
    await notify_payment_method_acked(
        app,
        user_id=updated.user_id,
        payment_method_transaction=PaymentMethodTransaction(
            wallet_id=updated.wallet_id,
            payment_method_id=updated.payment_method_id,
            state=updated.state.value,
        ),
    )

    return updated


async def cancel_creation_of_wallet_payment_method(
    app: web.Application,
    *,
    user_id: UserID,
    wallet_id: WalletID,
    payment_method_id: PaymentMethodID,
):
    """Acks as CANCELED"""
    await check_wallet_permissions(app, user_id=user_id, wallet_id=wallet_id)

    await _complete_create_of_wallet_payment_method(
        app,
        payment_method_id=payment_method_id,
        completion_state=InitPromptAckFlowState.CANCELED,
        message="Creation of payment-method aborted by user",
    )
    # FAKE -----
    _logger.debug(
        "FAKE Payments Gateway: DELETE /payment-methods/%s", payment_method_id
    )
    await asyncio.sleep(1)
    # response is OK
    # -----

    await delete_payment_method(
        app,
        user_id=user_id,
        wallet_id=wallet_id,
        payment_method_id=payment_method_id,
    )


async def list_wallet_payment_methods(
    app: web.Application, *, user_id: UserID, wallet_id: WalletID
) -> list[PaymentMethodGet]:
    # check permissions
    await check_wallet_permissions(app, user_id=user_id, wallet_id=wallet_id)

    # get acked
    acked = await list_successful_payment_methods(
        app,
        user_id=user_id,
        wallet_id=wallet_id,
    )

    # FAKE -----
    _logger.debug(
        "FAKE Payments Gateway: POST /payment-methods:batchGet: %s",
        json.dumps(
            {"payment_methods_ids": [p.payment_method_id for p in acked]}, indent=1
        ),
    )
    await asyncio.sleep(1)

    # response
    fake = Faker()
    fake.seed_instance(user_id)
    payments_methods: list[PaymentMethodGet] = [
        _to_api_model(
            ack,
            payment_method_details_from_gateway=_generate_fake_data(fake),
        )
        for ack in acked
    ]
    # -----

    return payments_methods


async def get_wallet_payment_method(
    app: web.Application,
    *,
    user_id: UserID,
    wallet_id: WalletID,
    payment_method_id: PaymentMethodID,
) -> PaymentMethodGet:
    # check permissions
    await check_wallet_permissions(app, user_id=user_id, wallet_id=wallet_id)

    acked = await get_successful_payment_method(
        app, user_id=user_id, wallet_id=wallet_id, payment_method_id=payment_method_id
    )

    # FAKE -----
    _logger.debug(
        "FAKE Payments Gateway: GET /payment-methods/%s", acked.payment_method_id
    )
    await asyncio.sleep(1)
    # response
    fake = Faker()
    fake.seed_instance(user_id)
    return _to_api_model(
        acked, payment_method_details_from_gateway=_generate_fake_data(fake)
    )
    # -----


async def delete_wallet_payment_method(
    app: web.Application,
    *,
    user_id: UserID,
    wallet_id: WalletID,
    payment_method_id: PaymentMethodID,
):
    # check permissions
    await check_wallet_permissions(app, user_id=user_id, wallet_id=wallet_id)
    assert payment_method_id  # nosec

    acked = await get_successful_payment_method(
        app, user_id=user_id, wallet_id=wallet_id, payment_method_id=payment_method_id
    )

    # FAKE -----
    _logger.debug(
        "FAKE Payments Gateway: DELETE /payment-methods/%s", acked.payment_method_id
    )
    await asyncio.sleep(1)
    # response is OK
    # ------

    # delete since it was deleted from gateway
    await delete_payment_method(
        app, user_id=user_id, wallet_id=wallet_id, payment_method_id=payment_method_id
    )
