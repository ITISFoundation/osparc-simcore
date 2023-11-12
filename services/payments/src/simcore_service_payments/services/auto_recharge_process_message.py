import logging
from decimal import Decimal

from fastapi import FastAPI
from models_library.api_schemas_webserver.wallets import GetWalletAutoRecharge
from models_library.rabbitmq_messages import WalletCreditsMessage
from pydantic import parse_raw_as
from simcore_service_payments.db.auto_recharge_repo import AutoRechargeRepo
from simcore_service_payments.db.payments_methods_repo import PaymentsMethodsRepo
from simcore_service_payments.services.payments_gateway import PaymentsGatewayApi

from ..core.settings import ApplicationSettings
from .auto_recharge import get_wallet_payment_autorecharge
from .payments_methods import get_payment_method

_logger = logging.getLogger(__name__)


async def process_message(app: FastAPI, data: bytes) -> bool:
    assert app  # nosec
    rabbit_message = parse_raw_as(WalletCreditsMessage, data)
    _logger.debug("Process msg: %s", rabbit_message)

    settings: ApplicationSettings = app.state.settings
    auto_recharge_repo: AutoRechargeRepo = AutoRechargeRepo(db_engine=app.state.engine)

    # 1. Check if wallet credits are bellow the threshold
    if rabbit_message.credits > Decimal(100):  # TODO: from settings MIN CREDITS
        return True

    # 2. Check if auto-recharge functionality is ON for wallet_id
    payment_autorecharge: GetWalletAutoRecharge | None = (
        await get_wallet_payment_autorecharge(
            settings, auto_recharge_repo, wallet_id=rabbit_message.wallet_id
        )
    )
    if (
        payment_autorecharge is None
        or payment_autorecharge.enabled is False
        or payment_autorecharge.payment_method_id is None
    ):
        return True

    # 3. Get Payment method
    _payments_gateway = PaymentsGatewayApi.get_from_app_state(app)
    _payments_repo = PaymentsMethodsRepo(db_engine=app.state.engine)
    await get_payment_method(
        _payments_gateway,
        _payments_repo,
        payment_method_id=payment_autorecharge.payment_method_id,
        user_id=1,  # TODO: Why user_id/wallet_id is here? I would query purly based on payment_method_id
        wallet_id=rabbit_message.wallet_id,
    )

    # 4. Pay with payment method
    # TODO: I will need to query webserver for user email & wallet name?

    return True
