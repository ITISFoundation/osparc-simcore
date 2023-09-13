import asyncio
import json
import logging
from typing import Any
from uuid import uuid4

import arrow
from aiohttp import web
from models_library.api_schemas_webserver.wallets import (
    PaymentMethodGet,
    PaymentMethodID,
    PaymentMethodInit,
)
from models_library.users import UserID
from models_library.wallets import WalletID
from pydantic import parse_obj_as
from simcore_postgres_database.models.payments_methods import InitPromptAckFlowState
from yarl import URL

from ._api import check_wallet_permissions
from ._methods_db import (
    PaymentsMethodsDB,
    get_successful_payment_methods,
    insert_init_payment_method,
    udpate_payment_method,
)
from .settings import PaymentsSettings, get_plugin_settings

_logger = logging.getLogger(__name__)


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
    _logger.debug("init -> FAKE Payments Gateway: /payment-methods:init")
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


async def complete_create_of_wallet_payment_method(
    app: web.Application,
    *,
    payment_method_id: PaymentMethodID,
    completion_state: InitPromptAckFlowState,
    message: str | None = None,
) -> PaymentsMethodsDB:
    assert completion_state != InitPromptAckFlowState.PENDING  # nosec

    # annotate
    updated: PaymentsMethodsDB = await udpate_payment_method(
        app,
        payment_method_id=payment_method_id,
        state=completion_state,
        state_message=message,
    )

    return updated


async def cancel_creation_of_wallet_payment_method(
    app: web.Application,
    *,
    user_id: UserID,
    wallet_id: WalletID,
    payment_method_id: PaymentMethodID,
):
    await check_wallet_permissions(app, user_id=user_id, wallet_id=wallet_id)

    return await complete_create_of_wallet_payment_method(
        app,
        payment_method_id=payment_method_id,
        completion_state=InitPromptAckFlowState.CANCELED,
        message="Creation of payment-method aborted by user",
    )

    # FIXME: delete???


async def list_wallet_payment_methods(
    app: web.Application, *, user_id: UserID, wallet_id: WalletID
) -> list[PaymentMethodGet]:
    # check permissions
    await check_wallet_permissions(app, user_id=user_id, wallet_id=wallet_id)

    # get acked
    entries = await get_successful_payment_methods(
        app,
        user_id=user_id,
        wallet_id=wallet_id,
    )

    # FAKE -----
    _logger.debug(
        "init -> FAKE Payments Gateway: POST /payment-methods:batchGet: %s",
        json.dumps(
            {"payment_methods_ids": [p.payment_method_id for p in entries]}, indent=1
        ),
    )
    await asyncio.sleep(1)
    # merge both updated and response

    # FIXME: fake!!
    payments_methods: list[PaymentMethodGet] = [
        _to_api_model(
            e,
            payment_method_details_from_gateway=PaymentMethodGet.Config.schema_extra[
                "examples"
            ][0],
        )
        for e in entries
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
    await check_wallet_permissions(app, user_id=user_id, wallet_id=wallet_id)
    assert payment_method_id  # nosec

    # FIXME: fake!!
    # TODO: call gateway to delete payment-method
    # TODO: drop payment-method from db
