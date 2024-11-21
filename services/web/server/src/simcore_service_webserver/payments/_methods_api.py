import asyncio
import logging
from typing import Any
from uuid import uuid4

import arrow
from aiohttp import web
from faker import Faker
from models_library.api_schemas_webserver.wallets import (
    PaymentMethodGet,
    PaymentMethodID,
    PaymentMethodInitiated,
    PaymentMethodTransaction,
)
from models_library.products import ProductName
from models_library.users import UserID
from models_library.wallets import WalletID
from pydantic import HttpUrl, TypeAdapter
from servicelib.logging_utils import log_decorator
from simcore_postgres_database.models.payments_methods import InitPromptAckFlowState
from yarl import URL

from ..users.api import get_user_display_and_id_names
from ..wallets.api import get_wallet_by_user
from . import _rpc
from ._autorecharge_db import get_wallet_autorecharge
from ._methods_db import (
    PaymentsMethodsDB,
    delete_payment_method,
    get_successful_payment_method,
    insert_init_payment_method,
    list_successful_payment_methods,
    udpate_payment_method,
)
from ._onetime_api import raise_for_wallet_payments_permissions
from ._socketio import notify_payment_method_acked
from .settings import PaymentsSettings, get_plugin_settings

_logger = logging.getLogger(__name__)

_FAKE_PAYMENT_METHOD_ID_PREFIX = "fpm"


def _get_payment_methods_from_fake_gateway(fake: Faker):
    return {
        "card_holder_name": fake.name(),
        "card_number_masked": f"**** **** **** {fake.credit_card_number()[:4]}",
        "card_type": fake.credit_card_provider(),
        "expiration_month": fake.random_int(min=1, max=12),
        "expiration_year": fake.future_date().year,
    }


def _to_api_model(
    entry: PaymentsMethodsDB, payment_method_details_from_gateway: dict[str, Any]
) -> PaymentMethodGet:
    assert entry.completed_at  # nosec

    return PaymentMethodGet.model_validate(
        {
            **payment_method_details_from_gateway,
            "idr": entry.payment_method_id,
            "wallet_id": entry.wallet_id,
            "created": entry.completed_at,
        }
    )


@log_decorator(_logger, level=logging.INFO)
async def _fake_init_creation_of_wallet_payment_method(
    app, settings, user_id, wallet_id
) -> PaymentMethodInitiated:
    # NOTE: this will be removed as soon as dev payment gateway is available in master
    # hold timestamp
    initiated_at = arrow.utcnow().datetime

    # FAKE -----
    _logger.debug("FAKE Payments Gateway: /payment-methods:init")
    await asyncio.sleep(1)
    payment_method_id = PaymentMethodID(f"{_FAKE_PAYMENT_METHOD_ID_PREFIX}_{uuid4()}")
    form_link = (
        URL(f"{settings.PAYMENTS_FAKE_GATEWAY_URL}")
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

    return PaymentMethodInitiated(
        wallet_id=wallet_id,
        payment_method_id=payment_method_id,
        payment_method_form_url=TypeAdapter(HttpUrl).validate_python(f"{form_link}"),
    )


async def _ack_creation_of_wallet_payment_method(
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


@log_decorator(_logger, level=logging.INFO)
async def _fake_cancel_creation_of_wallet_payment_method(
    app, payment_method_id, user_id, wallet_id
):
    await _ack_creation_of_wallet_payment_method(
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


@log_decorator(_logger, level=logging.INFO)
async def _fake_list_wallet_payment_methods(
    app, user_id, wallet_id
) -> list[PaymentMethodGet]:
    # get acked
    acked = await list_successful_payment_methods(
        app,
        user_id=user_id,
        wallet_id=wallet_id,
    )

    # FAKE -----
    _logger.debug(
        "FAKE Payments Gateway: POST /payment-methods:batchGet: %s",
        {"payment_methods_ids": [p.payment_method_id for p in acked]},
    )
    await asyncio.sleep(1)

    # response
    fake = Faker()
    fake.seed_instance(user_id)
    payments_methods: list[PaymentMethodGet] = [
        _to_api_model(
            ack,
            payment_method_details_from_gateway=_get_payment_methods_from_fake_gateway(
                fake
            ),
        )
        for ack in acked
    ]
    return payments_methods


@log_decorator(_logger, level=logging.INFO)
async def _fake_get_wallet_payment_method(
    app, user_id, wallet_id, payment_method_id
) -> PaymentMethodGet:
    acked = await get_successful_payment_method(
        app,
        user_id=user_id,
        wallet_id=wallet_id,
        payment_method_id=payment_method_id,
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
        acked,
        payment_method_details_from_gateway=_get_payment_methods_from_fake_gateway(
            fake
        ),
    )


@log_decorator(_logger, level=logging.INFO)
async def _fake_delete_wallet_payment_method(
    app, user_id, wallet_id, payment_method_id
) -> None:
    acked = await get_successful_payment_method(
        app,
        user_id=user_id,
        wallet_id=wallet_id,
        payment_method_id=payment_method_id,
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
        app,
        user_id=user_id,
        wallet_id=wallet_id,
        payment_method_id=payment_method_id,
    )


async def init_creation_of_wallet_payment_method(
    app: web.Application,
    *,
    user_id: UserID,
    wallet_id: WalletID,
    product_name: ProductName,
) -> PaymentMethodInitiated:
    """

    Raises:
        WalletAccessForbiddenError
    """

    # check permissions
    await raise_for_wallet_payments_permissions(
        app, user_id=user_id, wallet_id=wallet_id, product_name=product_name
    )

    settings: PaymentsSettings = get_plugin_settings(app)
    if settings.PAYMENTS_FAKE_COMPLETION:
        return await _fake_init_creation_of_wallet_payment_method(
            app, settings, user_id, wallet_id
        )

    assert not settings.PAYMENTS_FAKE_COMPLETION  # nosec

    user_wallet = await get_wallet_by_user(
        app, user_id=user_id, wallet_id=wallet_id, product_name=product_name
    )
    assert user_wallet.wallet_id == wallet_id  # nosec

    user = await get_user_display_and_id_names(app, user_id=user_id)
    return await _rpc.init_creation_of_payment_method(
        app,
        wallet_id=wallet_id,
        wallet_name=user_wallet.name,
        user_id=user_id,
        user_name=user.full_name,
        user_email=user.email,
    )


async def cancel_creation_of_wallet_payment_method(
    app: web.Application,
    *,
    user_id: UserID,
    wallet_id: WalletID,
    payment_method_id: PaymentMethodID,
    product_name: ProductName,
) -> None:
    """Acks as CANCELED"""
    await raise_for_wallet_payments_permissions(
        app, user_id=user_id, wallet_id=wallet_id, product_name=product_name
    )
    settings: PaymentsSettings = get_plugin_settings(app)
    if settings.PAYMENTS_FAKE_COMPLETION:
        await _fake_cancel_creation_of_wallet_payment_method(
            app, payment_method_id, user_id, wallet_id
        )
    else:
        assert not settings.PAYMENTS_FAKE_COMPLETION  # nosec
        await _rpc.cancel_creation_of_payment_method(
            app,
            payment_method_id=payment_method_id,
            user_id=user_id,
            wallet_id=wallet_id,
        )


async def list_wallet_payment_methods(
    app: web.Application,
    *,
    user_id: UserID,
    wallet_id: WalletID,
    product_name: ProductName,
) -> list[PaymentMethodGet]:
    # check permissions
    await raise_for_wallet_payments_permissions(
        app, user_id=user_id, wallet_id=wallet_id, product_name=product_name
    )

    payments_methods: list[PaymentMethodGet] = []
    settings: PaymentsSettings = get_plugin_settings(app)
    if settings.PAYMENTS_FAKE_COMPLETION:
        payments_methods = await _fake_list_wallet_payment_methods(
            app, user_id, wallet_id
        )
    else:
        assert not settings.PAYMENTS_FAKE_COMPLETION  # nosec
        payments_methods = await _rpc.list_payment_methods(
            app,
            user_id=user_id,
            wallet_id=wallet_id,
        )

    # sets auto-recharge flag
    assert all(not pm.auto_recharge for pm in payments_methods)  # nosec
    if auto_rechage := await get_wallet_autorecharge(app, wallet_id=wallet_id):
        assert payments_methods  # nosec
        for pm in payments_methods:
            pm.auto_recharge = pm.idr == auto_rechage.primary_payment_method_id

    return payments_methods


async def get_wallet_payment_method(
    app: web.Application,
    *,
    user_id: UserID,
    wallet_id: WalletID,
    payment_method_id: PaymentMethodID,
    product_name: ProductName,
) -> PaymentMethodGet:
    # check permissions
    await raise_for_wallet_payments_permissions(
        app, user_id=user_id, wallet_id=wallet_id, product_name=product_name
    )

    settings: PaymentsSettings = get_plugin_settings(app)
    if settings.PAYMENTS_FAKE_COMPLETION:
        return await _fake_get_wallet_payment_method(
            app, user_id, wallet_id, payment_method_id
        )

    assert not settings.PAYMENTS_FAKE_COMPLETION  # nosec
    return await _rpc.get_payment_method(
        app,
        payment_method_id=payment_method_id,
        user_id=user_id,
        wallet_id=wallet_id,
    )


async def delete_wallet_payment_method(
    app: web.Application,
    *,
    user_id: UserID,
    wallet_id: WalletID,
    payment_method_id: PaymentMethodID,
    product_name: ProductName,
):
    # check permissions
    await raise_for_wallet_payments_permissions(
        app, user_id=user_id, wallet_id=wallet_id, product_name=product_name
    )
    assert payment_method_id  # nosec

    settings: PaymentsSettings = get_plugin_settings(app)
    if settings.PAYMENTS_FAKE_COMPLETION:
        await _fake_delete_wallet_payment_method(
            app, user_id, wallet_id, payment_method_id
        )
    else:
        assert not settings.PAYMENTS_FAKE_COMPLETION  # nosec

        await _rpc.delete_payment_method(
            app,
            payment_method_id=payment_method_id,
            user_id=user_id,
            wallet_id=wallet_id,
        )
